"""Run original raw-image DMA checks and cancel/error restart probes.

The functional wrapper reuses the actual stock arbiter/SDRAM chip harness;
the same raw pipeline transform is used by the resource probe.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
from generate import raw


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('original',type=Path)
    p.add_argument('decoder',type=Path)
    p.add_argument('mux',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('--all-frames',action='store_true',help='check every original image instead of the first eight')
    a=p.parse_args()
    here=Path(__file__).resolve().parent;gif=here.parent;rtl=here.parents[2]/'fw/rtl'
    out=a.output.resolve()
    if out.exists() or here.parents[1] in out.parents:p.error('fresh output outside tests required')
    out.mkdir(parents=True)
    sys.path.insert(0,str(gif))
    from gif_reference import read_gif,decode
    w,h,bg,palette,frames=read_gif(a.original)
    assert (w,h)==(320,240) and len(frames)>=8
    selected=frames if a.all_frames else frames[:8]
    with (out/'fixtures.bin').open('wb') as f:
        f.write(struct.pack('<I',len(selected)))
        for frame in selected:
            assert (frame['w'],frame['h'])==(320,240)
            expected,_=decode(frame['raw'],frame['bits'],76800)
            assert len(expected)==76800
            f.write(struct.pack('<5I',frame['bits'],76800,len(frame['raw']),len(expected),0))
            f.write(frame['raw']);f.write(expected)
    original=gif/'sc64-transport-abort/gif_transport_abort_pipeline.sv'
    text=raw(original.read_text())
    text=text.replace('    input logic clk, reset, session_start, frame_start, emit_packet,',
        '    output logic raw_output_request,\n    input logic clk, reset, session_start, frame_start, emit_packet,')
    text=text.replace('    mem_bus scratch_bus(), source_bus(), output_bus();',
        '    mem_bus scratch_bus(), source_bus(), output_bus();\n    assign raw_output_request=output_bus.request;')
    old='gif_transport_mux mux (.clk(clk),.reset(reset),.idle(mux_idle),.scratch(scratch_bus),\n        .source(source_bus),.packet(output_bus),.memory(cfg_bus));'
    assert text.count(old)==1
    text=text.replace(old,"mem_bus mcu_bus();\n    assign mcu_bus.request=1'b0;\n    assign mcu_bus.write=1'b0;\n    assign mcu_bus.address=27'd0;\n    assign mcu_bus.wdata=16'd0;\n    assign mcu_bus.wmask=2'b00;\n    gif_transport_mcu_mux mux (.clk(clk),.reset(reset),.idle(),.gif_idle(mux_idle),\n        .gif_admit(1'b1),.scratch(scratch_bus),.source(source_bus),.packet(output_bus),\n        .mcu(mcu_bus),.memory(cfg_bus));")
    assert text.count('!scratch_bus.request&&!cfg_bus.request')==1
    text=text.replace('!scratch_bus.request&&!cfg_bus.request','!scratch_bus.request')
    (out/'pipeline.sv').write_text(text)
    driver=gif/'sc64-transport-abort/driver.cpp'
    rig=driver.read_text().split('    void initialize() {')[0]+'};\n'
    (out/'rig.hpp').write_text(rig)
    sources=[rtl/'memory/mem_bus.sv',rtl/'memory/dma_scb.sv',rtl/'fifo/fifo_bus.sv',
        rtl/'n64/n64_scb.sv',rtl/'memory/memory_dma.sv',rtl/'memory/memory_arbiter.sv',
        rtl/'memory/memory_sdram.sv',gif/'sc64-bus/gif_sc64_bus.sv',
        a.decoder/'gif_lzw_cached.sv',a.decoder/'cached_dictionary.sv',a.mux,out/'pipeline.sv',here/'driver.cpp']
    command=['verilator','--cc','--exe','--build','-j','4','--top-module','gif_transport_abort_pipeline',
        '--Mdir',str(out/'obj'),'-CFLAGS','-I'+str(out),*map(str,sources)]
    with (out/'compile.log').open('w') as log:
        subprocess.run(command,stdout=log,stderr=log,check=True,timeout=180)
    with (out/'results.log').open('w') as log:
        subprocess.run([str(out/'obj/Vgif_transport_abort_pipeline'),str(out/'fixtures.bin')],stdout=log,stderr=log,check=True,timeout=max(180,len(selected)*5))
    lines=(out/'results.log').read_text().splitlines()
    assert sum(line.startswith('PASS original raw frame=') for line in lines)==len(selected)
    assert sum(line.startswith('PASS cancel phase=') for line in lines)==4
    report={'qualification':False,'raw_original_frames':len(selected),'all_frames':a.all_frames,'cancel_cases':4,
        'source_sha256':hashlib.sha256(a.original.read_bytes()).hexdigest(),
        'fixture_sha256':hashlib.sha256((out/'fixtures.bin').read_bytes()).hexdigest(),
        'verilator_version':subprocess.check_output(['verilator','--version'],text=True).strip(),
        'python_version':sys.version,
        'sources':{str(x):hashlib.sha256(x.read_bytes()).hexdigest()
            for x in sources+[original,driver,here/'generate.py',Path(__file__).resolve(),gif/'gif_reference.py']}}
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print((out/'results.log').read_text())


if __name__=='__main__':main()
