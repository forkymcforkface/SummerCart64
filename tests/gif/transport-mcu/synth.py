"""Compare isolated three/four-client mux logic with one synthesis flow."""
import importlib.util
import json
import pathlib
import re
import sys
sys.dont_write_bytecode = True


def main():
    out = pathlib.Path(sys.argv[1]).resolve()
    here = pathlib.Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location('mux3', here.parent/'transport-mux/run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    width = out/'width-proof.v'
    width.write_text('module miter(input [31:0] a,input [26:0] b,output eq);'
                     "wire[26:0] old_address=a,new_address=a[26:0];"
                     "wire[26:0] old_next=b+2'd2,new_next=b+27'd2;"
                     'assign eq=(old_address==new_address)&&(old_next==new_next);endmodule\n')
    module.execute(['yosys','-p','read_verilog %s; prep -top miter; sat -verify -prove eq 1' % width],
                   out/'width-proof.log',diagnostic='SUCCESS')
    source = module.derivative((here.parent/'sc64-transport-abort/gif_transport_mux.sv').read_text())
    three = module.flat(source, 'three')
    four = (out/'gif_transport_mcu_mux.sv').read_text()
    four = four.replace('module gif_transport_mcu_mux (', 'module four (')
    widths = {'request': '', 'ack': '', 'write': '', 'wmask': '[1:0] ',
              'address': '[26:0] ', 'rdata': '[15:0] ', 'wdata': '[15:0] '}
    ports = []
    for bus in ['scratch','source','packet','mcu','memory']:
        for field,width in widths.items():
            output = (field in ('ack','rdata')) != (bus=='memory')
            ports.append(('output' if output else 'input')+' logic '+width+bus+'_'+field)
            four = four.replace(bus+'.'+field,bus+'_'+field)
    four = four.replace('    mem_bus.memory scratch,source,packet,mcu,\n    mem_bus.controller memory',
                        '    '+',\n    '.join(ports))
    four,count = re.subn(r'\$fatal\(1,"[^"]+"\);','begin end',four)
    assert count==5 and 'mem_bus' not in four
    results = {'hardware_qualified':False}
    for name,text in [('three',three),('four',four)]:
        path = out/(name+'.v')
        with path.open('x') as stream:
            stream.write(text)
        module.execute(['yosys','-p','read_verilog -sv %s; synth_lattice -family xo2 -top %s; write_json %s' %
                        (path,name,out/(name+'.json'))],out/(name+'-synth.log'))
        cells = json.loads((out/(name+'.json')).read_text())['modules'][name]['cells'].values()
        counts = {}
        for cell in cells:
            counts[cell['type']]=counts.get(cell['type'],0)+1
        results[name]=counts
    (out/'synth-result.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results))


if __name__=='__main__':
    main()
