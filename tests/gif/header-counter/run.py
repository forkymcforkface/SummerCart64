"""Compare a bounded header position against the transport's packet counter.

Only generated wrappers change. A one-step inductive relation covers arbitrary
stalls and resets within the compositor's 76,992-byte maximum packet; actual
controller transport and cancellation tests check integration independently.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--decoder', required=True, type=Path)
    parser.add_argument('--mux', required=True, type=Path)
    parser.add_argument('--mode', choices=['behavior','mapping'], required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    gif = here.parent
    rtl = gif.parents[1]/'fw/rtl'
    out = args.output.resolve()
    if out.exists() or out.is_relative_to(gif.parent):
        parser.error('output must be fresh and outside tests')
    out.mkdir(parents=True)
    result = {'status': 'running', 'mode': args.mode, 'hardware_qualified': False}
    def run(command, label, negative=False):
        with (out/(label+'.log')).open('w') as log:
            completed = subprocess.run(command, stdout=log, stderr=log, timeout=900)
        if negative:
            if completed.returncode == 0 or 'proof did fail' not in (out/(label+'.log')).read_text():
                raise ValueError('negative control did not fail semantically')
        elif completed.returncode:
            raise ValueError(label+' failed with exit '+str(completed.returncode))
    try:
        source = gif/'sc64-transport-abort/gif_transport_abort_pipeline.sv'
        baseline = source.read_text()
        if re.findall(r'emitted[^;\n]*', baseline) != [
            'emitted', 'emitted<=0', 'emitted<=0', "emitted<=emitted+1'b1",
            'emitted>=28&&emitted<=31)header_payload<={header_payload[23:0],out_byte}',
            'emitted==31) begin', 'emitted<=0']:
            raise ValueError('counter uses differ from the extracted recurrence')
        candidate = baseline
        for old, new in [("logic [26:0] source_limit, emitted;", "logic [26:0] source_limit;\n    logic [5:0] emitted;"),
                         ("emitted<=emitted+1'b1;", "if(emitted<32)emitted<=emitted+1'b1;")]:
            if candidate.count(old) != 1:
                raise ValueError('counter source anchor changed')
            candidate = candidate.replace(old, new)
        (out/'candidate.sv').write_text(candidate)
        proof = '''module proof(input [26:0] old_count,input [5:0] small,
input push,clear,output good);
wire related=(small==((old_count<32)?old_count:27'd32));
wire domain=old_count<=76992 && (!push || old_count<76992);
wire [26:0] old_next=clear?27'd0:old_count+{26'd0,push};
wire [5:0] small_next=clear?6'd0:small+{5'd0,(push && small<LIMIT)};
wire events=((old_count>=28 && old_count<=31)==(small>=28 && small<=31))
 && ((old_count==31)==(small==31));
assign good=!(related && domain) || (events &&
 (small_next==((old_next<32)?old_next:27'd32)));
endmodule
'''
        for label, limit in [('proof', '32'), ('negative', '31')]:
            path = out/(label+'.v')
            path.write_text(proof.replace('LIMIT', limit))
            run(['yosys', '-Q', '-p', f'read_verilog {path}; prep -top proof; sat -verify -prove good 1 -show-inputs'], label, label=='negative')
        if args.mode=='behavior':
            run([sys.executable, '-B', str(gif/'compositor/fixtures.py'), str(args.original), str(out)], 'fixtures')
        actual = [rtl/p for p in ['memory/mem_bus.sv','memory/dma_scb.sv','fifo/fifo_bus.sv',
                  'n64/n64_scb.sv','memory/memory_dma.sv','memory/memory_arbiter.sv','memory/memory_sdram.sv']]
        common = actual + [gif/'sc64-bus/gif_sc64_bus.sv',gif/'compositor/gif_ci8_compose.sv',
                          args.decoder/'gif_lzw_cached.sv',args.decoder/'cached_dictionary.sv',args.mux]
        driver = out/'normal.cpp'
        driver.write_text((gif/'sc64-transport/driver.cpp').read_text().replace('Vgif_transport_pipeline','Vgif_transport_abort_pipeline'))
        summaries = {}
        cases = [('baseline',source,driver),('candidate',out/'candidate.sv',driver),
                 ('abort',out/'candidate.sv',gif/'sc64-transport-abort/driver.cpp')]
        for label, wrapper, cpp in cases if args.mode=='behavior' else []:
            dest = out/label
            dest.mkdir()
            run(['verilator','--cc','--exe','--build','-j','2','--top-module','gif_transport_abort_pipeline',
                 '--Mdir',str(dest/'obj'),*map(str,common+[wrapper,cpp])],label+'-compile')
            run([str(dest/'obj/Vgif_transport_abort_pipeline'),str(out/'fixtures.bin'),str(dest)]+
                ([] if label=='abort' else ['8']), label+'-simulation')
            summaries[label]=(out/(label+'-simulation.log')).read_text()
        if summaries and summaries['baseline'] != summaries['candidate']:
            raise ValueError('transport baseline differs')
        counts = {}
        for label, wrapper in [('baseline',baseline),('candidate',candidate)] if args.mode=='mapping' else []:
            mapped = out/(label+'-mapped.json')
            cleaned, removed = re.subn(r'\$fatal\([^;]+\);','begin end',wrapper)
            mux, mux_removed = re.subn(r'\$fatal\([^;]+\);','begin end',args.mux.read_text())
            if (removed,mux_removed)!=(6,4):
                raise ValueError('simulation assertion inventory changed')
            wpath, mpath = out/(label+'-synth.sv'),out/'mux-synth.sv'
            wpath.write_text(cleaned)
            mpath.write_text(mux)
            converted = out/(label+'.v')
            with converted.open('w') as handle, (out/(label+'-sv2v.log')).open('w') as log:
                subprocess.run(['sv2v','--top=gif_transport_abort_pipeline',*map(str,common[:-1]+[mpath,wpath])],
                               stdout=handle,stderr=log,check=True,timeout=120)
            run(['yosys','-Q','-p',f'read_verilog {converted}; synth_lattice -family xo2 -top gif_transport_abort_pipeline; check -assert; write_json {mapped}'],label+'-synthesis')
            cells=json.loads(mapped.read_text())['modules']['gif_transport_abort_pipeline']['cells']
            counts[label]=dict(Counter(c['type'] for c in cells.values()))
        fixtures = [gif/p for p in ['compositor/fixtures.py','gif_reference.py',
                    'sc64-transport/driver.cpp','sc64-transport-abort/driver.cpp']]
        result.update(status='pass',mapped_cells=counts,transport=summaries,
                      source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in common+fixtures+[source,Path(__file__),args.original]},
                      candidate_sha256=hashlib.sha256((out/'candidate.sv').read_bytes()).hexdigest(),
                      versions={tool:subprocess.check_output([tool,flag],text=True).strip() for tool,flag in
                                [('yosys','-V'),('sv2v' if args.mode=='mapping' else 'verilator','--version')]})
    except Exception as exc:
        result.update(status='failed',error=str(exc))
        raise
    finally:
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    main()
