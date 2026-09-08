"""Measure width reductions in the canvas-bounded LZW decoder.

The passed bounded reference is immutable. Generated variants retain cycle
ordering and external-memory ownership; full differential tests and deliberate
undersized-counter/reservoir negative controls accompany component mapping.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess


def replace(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError('Source anchor changed: '+old)
    return text.replace(old,new)


def derivative(source, variant):
    if 'count' in variant:
        source = replace(source,'logic [31:0] emitted, limit;','logic [16:0] emitted, limit;')
        source = replace(source,'limit <= output_limit;','limit <= output_limit[16:0];')
        source = replace(source,"32'(stack_size) > limit-emitted","17'(stack_size) > limit-emitted")
    if 'bits' in variant:
        source = replace(source,'logic [23:0] reservoir;','logic [18:0] reservoir;')
        source = replace(source,"24'(in_byte)","19'(in_byte)")
        source = replace(source,"reservoir & ((24'd1 << width)-24'd1)","reservoir[11:0] & ((12'd1 << width)-12'd1)")
    if 'stack' in variant:
        source = replace(source,'next_code, clear_code, stop_code, stack_size;',
                         'next_code, clear_code, stop_code;\n    logic [9:0] stack_size;')
        source = replace(source,"state == EMIT ? 13'd2 : 13'd1","state == EMIT ? 10'd2 : 10'd1")
    if 'codes' in variant:
        source = replace(source,'logic [12:0] next_code, clear_code, stop_code;',
                         'logic [12:0] next_code;\n    logic [8:0] clear_code, stop_code;')
        source = replace(source,"clear_code <= 13'd1 << minimum;","clear_code <= 9'd1 << minimum;")
        source = replace(source,"stop_code <= (13'd1 << minimum)+1;","stop_code <= (9'd1 << minimum)+1;")
        source = replace(source,'next_code <= clear_code+2;',"next_code <= 13'(clear_code)+2;")
        for old in ['== clear_code', '< clear_code', '== stop_code', '<= stop_code']:
            operator, name = old.split()
            source = replace(source,old,operator+" 13'("+name+")")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bounded',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    prior,out=args.bounded.resolve(),args.output.resolve()
    here=Path(__file__).resolve().parent
    if out.exists() or here.parent.parent in out.parents:
        raise ValueError('Output must be new and outside tests')
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    passed=json.loads((prior/'result.json').read_text())
    if passed['status']!='pass' or passed['mode']!='core' or passed['focused']:
        raise ValueError('Requires a passed full bounded-core result')
    for name,expected in passed['generated_hashes'].items():
        if digest(prior/name)!=expected:
            raise ValueError('Passed artifact changed: '+name)
    out.mkdir(parents=True)
    result={'status':'running','hardware_qualified':False,'mapped':{}}
    def run(command,name,negative=False):
        with (out/(name+'.log')).open('w') as log:
            completed=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=900)
        text=(out/(name+'.log')).read_text()
        if negative:
            if completed.returncode==0 or not any(s in text for s in ['mismatch frame','completion frame']):
                raise ValueError('Negative control did not fail in output comparison: '+name)
        elif completed.returncode:
            raise ValueError('Command failed: '+name)
        return text
    try:
        source=(prior/'gif_lzw_cached.sv').read_text()
        variants=['baseline','count','count-bits','count-bits-stack','count-bits-stack-codes']
        for variant in variants:
            path=out/(variant+'.sv')
            path.write_text(derivative(source,variant))
            script=(f'read_verilog -sv "{path}" "{prior}/cached_dictionary.sv"; '
                    f'synth_lattice -family xo2 -top gif_lzw_cached; stat; write_json "{out}/{variant}.json"')
            run(['yosys','-Q','-T','-p',script],variant+'-mapping')
            cells=json.loads((out/(variant+'.json')).read_text())['modules']['gif_lzw_cached']['cells']
            result['mapped'][variant]=dict(Counter(c['type'] for c in cells.values()))
        candidate=(out/(variants[-1]+'.sv')).read_text()
        for name,code in [('candidate',candidate),
                          ('negative-count',candidate.replace('[16:0] emitted, limit','[15:0] emitted, limit').replace('output_limit[16:0]','output_limit[15:0]')),
                          ('negative-bits',candidate.replace('[18:0] reservoir','[17:0] reservoir').replace("19'(in_byte)","18'(in_byte)"))]:
            path=out/(name+'.sv')
            path.write_text(code)
            run(['verilator','--cc','--exe','--build','-j','2','--top-module','gif_lzw_cached',
                 '--Mdir',str(out/(name+'-obj')),str(path),str(prior/'cached_dictionary.sv'),str(prior/'driver.cpp')],name+'-compile')
            text=run([str(out/(name+'-obj/Vgif_lzw_cached')),str(prior/'fixtures.bin')],name+'-simulation',name.startswith('negative'))
            result[name]=text.strip().splitlines()[-2:]
        result.update(status='pass',source_hashes={str(p):digest(p) for p in
                      [prior/'result.json',prior/'gif_lzw_cached.sv',prior/'cached_dictionary.sv',prior/'driver.cpp',prior/'fixtures.bin',Path(__file__)]},
                      generated_hashes={p.name:digest(p) for p in out.glob('*.sv')},
                      versions={t:subprocess.check_output([t,f],text=True).strip() for t,f in [('yosys','-V'),('verilator','--version')]})
    except Exception as exc:
        result.update(status='failed',error=str(exc))
        raise
    finally:
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    main()
