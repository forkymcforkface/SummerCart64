"""Generate isolated four-client ownership and exact stock MCU memory slice.

Admission is a scheduling gate, never a direct cancel signal: pending GIF
clients require continued grants to drain. This is not the whole job owner.
"""
import importlib.util
import pathlib
import sys
sys.dont_write_bytecode = True


def generate(out):
    here = pathlib.Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location('mux3', here.parent/'transport-mux/run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = module.derivative((here.parent/'sc64-transport-abort/gif_transport_mux.sv').read_text())
    source = source.replace('module gif_transport_mux (', 'module gif_transport_mcu_mux (')
    source = source.replace('input logic clk,reset,', 'input logic clk,reset,gif_admit,')
    source = source.replace('output logic idle,', 'output logic idle,gif_idle,')
    source = source.replace('scratch,source,packet,', 'scratch,source,packet,mcu,')
    begin = source.index('        case(next_owner)')
    end = source.index('        scratch.ack=', begin)
    names = ['scratch', 'source', 'packet', 'mcu']
    lines = ['        case(next_owner)']
    for state in range(4):
        lines.append('            %d:begin' % state)
        for i in range(4):
            owner = (state+i) % 4
            condition = names[owner]+'.request' + ('&&gif_admit' if owner != 3 else '')
            lines.append('                %s(%s)begin found=1;choice=%d;end' %
                         ('if' if i == 0 else 'else if', condition, owner))
        lines.append('            end')
    lines += ['            default:begin end', '        endcase']
    source = source[:begin]+'\n'.join(lines)+'\n'+source[end:]
    source = source.replace('        scratch.rdata=', '        mcu.ack=state==ACTIVE&&owner==3&&memory.ack;\n        mcu.rdata=memory.rdata;\n        scratch.rdata=')
    packet_check = next(line for line in source.splitlines() if '2:if(!packet.request' in line)
    source = source.replace(packet_check, packet_check+'\n'+packet_check.replace('2:if', '3:if').replace('packet', 'mcu'))
    packet = ('                    2:begin memory.write<=packet.write;memory.address<=packet.address;\n'
              '                        memory.wdata<=packet.wdata;memory.wmask<=packet.wmask;end')
    assert packet in source
    source = source.replace(packet, packet+'\n'+packet.replace('2:begin', '3:begin').replace('packet', 'mcu'))
    source = source.replace("next_owner<=owner==2?0:owner+1'b1", "next_owner<=owner+1'b1")
    source = source.replace('        idle=state==FREE&&!memory.ack;',
                            '        idle=state==FREE&&!memory.ack;\n'
                            '        gif_idle=!scratch.request&&!source.request&&!packet.request&&\n'
                            '            (owner==3||(state!=ACTIVE&&!memory.ack));')
    (out/'gif_transport_mcu_mux.sv').write_text(source)
    stock = (here.parents[2]/'fw/rtl/mcu/mcu_top.sv').read_text()
    body = stock[stock.index('    logic [15:0] mem_buffer'):stock.index('    // Register list')]
    for declaration in ['    logic mem_start;','    logic mem_stop;', '    logic mem_direction;',
                        '    logic [8:0] mem_length;', '    logic [31:0] mem_address;', '    logic mem_busy;']:
        assert declaration in body
        body = body.replace(declaration, '')
    for old,new in [('mem_bus.address <= mem_address;', 'mem_bus.address <= mem_address[26:0];'),
                    ("mem_bus.address + 2'd2", "mem_bus.address + 27'd2")]:
        assert body.count(old)==1
        body = body.replace(old,new)
    header = '''/* Exact stock memory-controller slice; SPI/register decoder excluded. */
module stock_memory_slice(input clk,reset,mem_start,mem_stop,mem_direction,
input [8:0] mem_length,input [31:0] mem_address,
input mem_read,mem_write,input [7:0] address,input mem_word_select,
input [15:0] mem_wdata,output logic [15:0] mem_rdata,
output logic mem_busy,mem_bus.controller mem_bus);
'''
    (out/'stock_memory_slice.sv').write_text(header+body+'endmodule\n')


if __name__ == '__main__':
    output = pathlib.Path(sys.argv[1]).resolve()
    assert not output.exists() and not output.is_relative_to(pathlib.Path(__file__).resolve().parents[2])
    output.mkdir(parents=True)
    generate(output)
