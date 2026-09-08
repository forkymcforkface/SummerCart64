"""Generate an isolated modulo-free mux and prove/synthesize both actual muxes.

The derivative changes only the priority selector. Formal/synthesis copies
flatten the fixed mem_bus interface and omit the same four simulation fatal
checks; these checks remain unchanged in the usable candidate source.
"""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess


def derivative(source):
    start = source.index('        for(integer offset=0;')
    end = source.index('        scratch.ack=', start)
    old = source[start:end]
    assert old.count("case((int'(next_owner)+offset)%3)") == 1
    orders = [(0, [0, 1, 2]), (1, [1, 2, 0]), (2, [2, 0, 1])]
    names = ['scratch', 'source', 'packet']
    lines = ['        case(next_owner)']
    for state, order in orders:
        label = '0,3' if state == 0 else str(state)
        lines.append('            ' + label + ':begin')
        for i, owner in enumerate(order):
            lines.append('                ' + ('if' if i == 0 else 'else if') +
                         '(' + names[owner] + '.request)begin found=1;choice=' + str(owner) + ';end')
        lines.append('            end')
    lines += ['            default:begin end', '        endcase']
    return source[:start] + '\n'.join(lines) + '\n' + source[end:]


def flat(source, name):
    source = source.replace('module gif_transport_mux (', 'module ' + name + ' (', 1)
    ports = []
    widths = {'request': '', 'ack': '', 'write': '', 'wmask': '[1:0] ',
              'address': '[26:0] ', 'rdata': '[15:0] ', 'wdata': '[15:0] '}
    for bus in ['scratch', 'source', 'packet', 'memory']:
        for field, width in widths.items():
            output = (field in ('ack', 'rdata')) != (bus == 'memory')
            ports.append(('output' if output else 'input') + ' logic ' + width + bus + '_' + field)
            source = source.replace(bus + '.' + field, bus + '_' + field)
    source = source.replace('    mem_bus.memory scratch,source,packet,\n    mem_bus.controller memory',
                            '    ' + ',\n    '.join(ports))
    source, count = re.subn(r'\$fatal\(1,"[^"]+"\);', 'begin end', source)
    assert count == 4
    assert 'mem_bus' not in source and '$fatal' not in source
    source = source.replace("int'(next_owner)", "$signed({30'b0,next_owner})")
    return source


def execute(command, log, expected=0, diagnostic=None):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, timeout=180)
    log.write_text(result.stdout)
    if result.returncode != expected:
        raise RuntimeError(str(log) + ' exit=' + str(result.returncode))
    if diagnostic is not None and diagnostic not in result.stdout:
        raise RuntimeError(str(log) + ' missing expected semantic diagnostic')


def selector(source, name, lower=True):
    body = source[source.index('    always_comb begin'):source.index('        scratch.ack=')]
    if lower:
        body = body.replace("int'(next_owner)", "$signed({30'b0,next_owner})")
    for bus in ['scratch', 'source', 'packet']:
        body = body.replace(bus + '.request', bus)
    return ('module ' + name + '(input [1:0] next_owner,input scratch,source,packet,'
            'output logic found,output logic [1:0] choice);\n' + body + 'end\nendmodule\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=pathlib.Path)
    args = parser.parse_args()
    out = args.output.resolve()
    tests = pathlib.Path(__file__).resolve().parents[2]
    assert not out.is_relative_to(tests) and not out.exists()
    out.mkdir(parents=True)
    baseline = pathlib.Path(__file__).resolve().parent.parent / 'sc64-transport-abort/gif_transport_mux.sv'
    source = baseline.read_text()
    schema = baseline.parents[3] / 'fw/rtl/memory/mem_bus.sv'
    schema_text = schema.read_text()
    assert re.findall(r'logic\s*(\[[^\]]+\])?\s*(\w+)\s*;', schema_text) == [
        ('', 'request'), ('', 'ack'), ('', 'write'), ('[1:0]', 'wmask'),
        ('[26:0]', 'address'), ('[15:0]', 'rdata'), ('[15:0]', 'wdata')]
    for port in ['controller', 'memory']:
        body = re.search(r'modport\s+' + port + r'\s*\((.*?)\);', schema_text, re.S).group(1)
        expected = [('input' if ((field in ('ack', 'rdata')) == (port == 'controller'))
                     else 'output', field)
                    for field in ['request', 'ack', 'write', 'wmask', 'address', 'rdata', 'wdata']]
        assert re.findall(r'(input|output)\s+(\w+)', body) == expected
    candidate = derivative(source)
    (out / 'gif_transport_mux.sv').write_text(candidate)
    (out / 'gold.v').write_text(flat(source, 'gold'))
    (out / 'gate.v').write_text(flat(candidate, 'gate'))
    negative = candidate.replace('0,3:begin\n                if(scratch.request)',
                                 '0,3:begin\n                if(source.request)', 1)
    assert negative != candidate
    (out / 'negative.v').write_text(flat(negative, 'gate'))
    proof = 'read_verilog -sv {gold} {gate}; proc; opt; equiv_make gold gate equiv; hierarchy -top equiv; equiv_simple; equiv_induct -seq 4; equiv_status -assert'
    execute(['yosys', '-p', proof.format(gold=out/'gold.v', gate=out/'gate.v')], out/'equivalence.log')
    execute(['yosys', '-p', proof.format(gold=out/'gold.v', gate=out/'negative.v')],
            out/'negative.log', 1, "unproven $equiv cells in 'equiv_status -assert'")
    for label, variant, expected in [('selector', candidate, 0), ('selector-negative', negative, 1)]:
        miter = ('module miter(input [1:0] n,input a,b,c,output eq); wire f,g;wire [1:0] x,y;'
                 'sel_gold u(n,a,b,c,f,x);sel_gate v(n,a,b,c,g,y);'
                 'assign eq=(f==g)&&(x==y);endmodule\n')
        path = out/(label+'.v')
        path.write_text(selector(source, 'sel_gold') + selector(variant, 'sel_gate') + miter)
        execute(['yosys', '-p', 'read_verilog -sv %s; prep -top miter -flatten; '
                 'sat -verify -prove eq 1 -show-inputs' % path], out/(label+'.log'), expected,
                'proof did fail' if expected else 'SUCCESS')
    tb = ('module tb; logic [1:0] n;logic a,b,c;wire f,g,h;wire[1:0] x,y,z;'
          'sel_actual u(n,a,b,c,f,x);sel_lowered v(n,a,b,c,g,y);'
          'sel_candidate w(n,a,b,c,h,z);initial begin '
          'for(integer i=0;i<32;i=i+1)begin {n,a,b,c}=5\'(i);#1;'
          'if({f,x}!={g,y}||{f,x}!={h,z})$fatal(1,"selector mismatch");end '
          '$display("PASS actual SV selector 32 states");$finish;end endmodule\n')
    actual = out/'actual-selector.sv'
    actual.write_text(selector(source, 'sel_actual', False) + selector(source, 'sel_lowered') +
                      selector(candidate, 'sel_candidate', False) + tb)
    execute(['verilator', '--binary', '--timing', '--top-module', 'tb', '--Mdir',
             str(out/'selector-obj'), str(actual)], out/'actual-compile.log')
    execute([str(out/'selector-obj/Vtb')], out/'actual-selector.log',
            diagnostic='PASS actual SV selector 32 states')
    for name in ['gold', 'gate']:
        execute(['yosys', '-p', 'read_verilog -sv %s; synth_lattice -family xo2 -top %s; stat; write_json %s' %
                 (out/(name+'.v'), name, out/(name+'.json'))], out/(name+'-synth.log'))
    result = {'hardware_qualified': False, 'baseline_sha256': hashlib.sha256(baseline.read_bytes()).hexdigest(),
              'mem_bus_sha256': hashlib.sha256(schema.read_bytes()).hexdigest(),
              'candidate_sha256': hashlib.sha256((out/'gif_transport_mux.sv').read_bytes()).hexdigest()}
    for name in ['gold', 'gate']:
        data = json.loads((out/(name+'.json')).read_text())
        cells = data['modules'][name]['cells'].values()
        counts = {}
        for cell in cells:
            counts[cell['type']] = counts.get(cell['type'], 0) + 1
        result[name] = counts
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
