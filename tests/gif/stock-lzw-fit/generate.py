"""Derive a raw-index LZW resource probe from the audited stock-pin skeleton.

This has no GIF composition or packet protocol. A full 76800-byte output DMA
starts with the decoder; errors require explicit caller cancellation.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def raw(text):
    def replace(text,old,new):
        if text.count(old)!=1:raise ValueError('nonunique raw adapter anchor')
        return text.replace(old,new)
    start=text.index('    gif_ci8_compose compositor (')
    end=text.index('    mem_bus scratch_bus()',start)
    text=text[:start]+'''    assign busy=1'b0;
    assign initialized=configured;
    assign frame_done=decode_done;
    assign packet_done=1'b0;
    assign cancelled=retired;
    assign compose_error=1'b0;
    assign compose_ready=output_ready;
    assign out_valid=pixel_valid;
    assign out_byte=pixel_byte;
    assign out_last=1'b0;
    assign mem_valid=1'b0;
    assign mem_write=1'b0;
    assign mem_address=17'd0;
    assign mem_wdata=8'd0;
'''+text[end:]
    text=replace(text,'    wire emit_accept=emit_packet&&admit;',
        '    wire emit_accept=frame_accept;')
    text=replace(text,'            if(emit_accept) begin\n                output_count<=0;output_head<=0;output_tail<=0;emitted<=0;header_payload<=0;',
        "            if(emit_accept) begin\n                output_start<=1'b1;output_length<=27'd76800;\n                output_count<=0;output_head<=0;output_tail<=0;emitted<=0;header_payload<=0;")
    start=text.index('                    emitted<=emitted+1\'b1;')
    end=text.index('                if(output_pop)',start)
    text=text[:start]+'                end\n'+text[end:]
    return text


def main():
    here=Path(__file__).resolve().parent
    base=here.parent/'stock-fit/generate.py'
    subprocess.run([sys.executable,'-B',str(base),*sys.argv[1:]],check=True)
    out=Path(sys.argv[4])
    path=out/'pipeline.sv'
    text=raw(path.read_text())
    path.write_text(text)
    report=json.loads((out/'inputs.json').read_text())
    report['architecture']='raw LZW output, fixed 76800 bytes, no composition or dirty packet'
    report['base_generator_sha256']=hashlib.sha256(base.read_bytes()).hexdigest()
    report['lzw_generator_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['sha256'][str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    (out/'inputs.json').write_text(json.dumps(report,indent=2)+'\n')
    with (out/'converted.v').open('w') as result,(out/'conversion.log').open('w') as log:
        subprocess.run(report['command'],stdout=result,stderr=log,check=True,timeout=120)


if __name__=='__main__':
    main()
