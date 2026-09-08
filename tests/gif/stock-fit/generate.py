"""Generate an unqualified stock-pin synthesis skeleton; never a board image.

The SPI taps are research-only and the fixed GIF memory windows are unsafe
for production. Stock source files are read only; every substitution is exact.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'nonunique source anchor: {old[:80]}')
    return text.replace(old, new)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest', type=Path)
    p.add_argument('decoder', type=Path)
    p.add_argument('mux', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--disconnect', choices=['start','status'])
    a = p.parse_args()
    here = Path(__file__).resolve().parent
    gif = here.parent
    out = a.output.resolve()
    if out.exists() or here.parents[1] in out.parents:
        p.error('fresh output outside tests required')
    out.mkdir(parents=True)
    manifest = json.loads(a.manifest.read_text())
    command = manifest['command'][:]
    originals = [Path(x) for x in command if x.endswith(('.v', '.sv'))]
    top_path = next(x for x in originals if x.name == 'top.sv')
    mcu_path = next(x for x in originals if x.name == 'mcu_top.sv')
    for relative, expected in manifest['inputs'].items():
        source = top_path.parents[2]/relative
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError('stock source hash mismatch: '+relative)
    pipeline = gif/'sc64-transport-abort/gif_transport_abort_pipeline.sv'
    text = pipeline.read_text()
    start = text.index('    input logic chip_drive,')
    end = text.index(');', start)
    text = text[:start] + '    output logic decode_busy, decode_done, decode_error,\n    mem_bus.memory mcu_bus,\n    mem_bus.controller memory\n' + text[end:]
    start = text.index('    mem_bus n64_bus()')
    end = text.index('    gif_sc64_bus adapter', start)
    text = text[:start] + text[end:]
    start = text.index('    memory_arbiter arbiter')
    end = text.index('    dma_scb source_control()', start)
    text = text[:start] + text[end:]
    text = replace(text, '!scratch_bus.request&&!cfg_bus.request', '!scratch_bus.request')
    text = replace(text, 'gif_transport_mux mux (.clk(clk),.reset(reset),.idle(mux_idle),.scratch(scratch_bus),\n        .source(source_bus),.packet(output_bus),.memory(cfg_bus));',
        "gif_transport_mcu_mux mux (.clk(clk),.reset(reset),.idle(),.gif_idle(mux_idle),\n        .gif_admit(1'b1),.scratch(scratch_bus),.source(source_bus),\n        .packet(output_bus),.mcu(mcu_bus),.memory(memory));")
    checks = re.findall(r'\$fatal\([^;]+\);', text)
    if len(checks) != 6:
        raise ValueError('pipeline assertion inventory changed')
    text = re.sub(r'\$fatal\([^;]+\);', 'begin end', text)
    (out/'pipeline.sv').write_text(text)
    mux = a.mux.read_text()
    mux_checks = re.findall(r'\$fatal\([^;]+\);', mux)
    if not mux_checks:
        raise ValueError('missing mux assertions')
    (out/'mux.sv').write_text(re.sub(r'\$fatal\([^;]+\);', 'begin end', mux))
    mcu = replace(mcu_path.read_text(), '    output mcu_miso\n',
        '    output mcu_miso,\n    output gif_write,\n    output [7:0] gif_address,\n    output [31:0] gif_wdata,\n    input [31:0] gif_status\n')
    mcu = replace(mcu, '    logic reg_read;',
        '    assign gif_write=reg_write;\n    assign gif_address=address;\n    assign gif_wdata=reg_wdata;\n    logic reg_read;')
    mcu = replace(mcu, "            reg_rdata <= 32'd0;\n\n            case (address)",
        "            reg_rdata <= 32'd0;\n\n            case (address)\n                8'hA0: reg_rdata <= gif_status;")
    (out/'mcu_top.sv').write_text(mcu)
    top = replace(top_path.read_text(), '    mem_bus cfg_mem_bus ();',
        '    mem_bus cfg_mem_bus ();\n    mem_bus mcu_cfg_mem_bus ();\n    wire gif_write;\n    wire [7:0] gif_address;\n    wire [31:0] gif_wdata, gif_status;')
    top = replace(top, '.mem_bus(cfg_mem_bus)', '.mem_bus(mcu_cfg_mem_bus)')
    top = replace(top, '        .mcu_miso(mcu_miso)',
        '        .mcu_miso(mcu_miso),\n        .gif_write(gif_write),.gif_address(gif_address),\n        .gif_wdata(gif_wdata),.gif_status(gif_status)')
    bank = '''
    logic [5:0] gif_control;
    logic [31:0] gif_regs[1:7];
    integer gif_i;
    always_ff @(posedge clk) begin
        gif_control<=0;
        if(reset) begin
            for(gif_i=1;gif_i<=7;gif_i=gif_i+1)gif_regs[gif_i]<=0;
        end else if(gif_write) begin
            case(gif_address)
                8'hA0:gif_control<=gif_wdata[5:0];
'''
    bank += ''.join(f"                8'hA{i}:gif_regs[{i}]<=gif_wdata;\n" for i in range(1,8))
    bank += '''                default:begin end
            endcase
        end
    end
    wire gif_busy,gif_initialized,gif_frame_done,gif_packet_done,gif_error;
    wire gif_aborting,gif_retired,gif_source_busy,gif_output_busy,gif_configured;
    wire gif_decode_busy,gif_decode_error;
    assign gif_status={20'd0,gif_decode_error,gif_decode_busy,gif_configured,
        gif_output_busy,gif_source_busy,gif_retired,gif_aborting,gif_error,
        gif_packet_done,gif_frame_done,gif_initialized,gif_busy};
    gif_transport_abort_pipeline gif_engine (
        .clk(clk),.reset(reset),.session_start(gif_control[0]),
        .frame_start(gif_control[1]),.emit_packet(gif_control[2]),
        .packet_ack(gif_control[3]),.cancel(gif_control[4]),.configure(gif_control[5]),
        .generation(gif_regs[1]),.initial_reference(gif_regs[2]),.frame_id(gif_regs[3]),
        .ack_generation(gif_regs[4]),.ack_frame(gif_regs[5]),.source_length(gif_regs[6][26:0]),
        .minimum(gif_regs[7][3:0]),.transparent(gif_regs[7][4]),
        .transparent_index(gif_regs[7][15:8]),.background_index(gif_regs[7][23:16]),
        .frame_width(16'd320),.frame_height(16'd240),.frame_left(16'd0),.frame_top(16'd0),
        .disposal(3'd1),.interlaced(1'b0),.local_palette(1'b0),.bypass_lzw(1'b0),
        .in_valid(1'b0),.in_end(1'b0),.in_byte(8'd0),.out_ready(1'b0),
        .verify_start(1'b0),.verify_ready(1'b0),.pi_active(n64_scb.pi_sdram_active),
        .busy(gif_busy),.initialized(gif_initialized),.frame_done(gif_frame_done),
        .packet_done(gif_packet_done),.error(gif_error),.aborting(gif_aborting),
        .retired(gif_retired),.source_busy(gif_source_busy),.output_busy(gif_output_busy),
        .configured(gif_configured),.decode_busy(gif_decode_busy),.decode_error(gif_decode_error),
        .mcu_bus(mcu_cfg_mem_bus),.memory(cfg_mem_bus));
'''
    top = replace(top, 'endmodule', bank+'\nendmodule')
    if a.disconnect == 'start':
        top = replace(top, '.frame_start(gif_control[1])', ".frame_start(1'b0)")
    if a.disconnect == 'status':
        top = replace(top, '.gif_status(gif_status)', ".gif_status(32'd0)")
    (out/'top.sv').write_text(top)
    substitutions = {str(top_path): str(out/'top.sv'),str(mcu_path): str(out/'mcu_top.sv')}
    command = [substitutions.get(x,x) for x in command]
    extras = [gif/'sc64-bus/gif_sc64_bus.sv', a.decoder/'gif_lzw_cached.sv',
        a.decoder/'cached_dictionary.sv', gif/'compositor/gif_ci8_compose.sv',out/'mux.sv',out/'pipeline.sv']
    command += list(map(str,extras))
    sources = originals+extras+[pipeline,a.mux,out/'top.sv',out/'mcu_top.sv']
    report = {'qualification':False,'source_commit':manifest['commit'],
        'assertions_removed_for_synthesis':checks+mux_checks,'command':command,
        'sha256':{str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in sources}}
    (out/'inputs.json').write_text(json.dumps(report,indent=2)+'\n')
    with (out/'converted.v').open('w') as result, (out/'conversion.log').open('w') as log:
        subprocess.run(command,stdout=result,stderr=log,check=True,timeout=120)


if __name__ == '__main__':
    main()
