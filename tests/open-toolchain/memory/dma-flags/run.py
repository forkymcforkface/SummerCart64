"""Research-only registered DMA predicates and actual-source equivalence gate.

Generated candidates stay in a fresh output directory. The source tree and
configuration encoder are untouched; passing RTL proof does not prove timing.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def transform(source):
    for name, operator, bound in [('last', '==', 0), ('almost_last', '<=', 2)]:
        anchor = f'        mem_bus_{name}_transfer = (mem_bus_remaining_bytes {operator} 27\'d{bound});\n'
        if source.count(anchor) != 1:
            raise ValueError('unexpected predicate anchor ' + name)
        source = source.replace(anchor, '')
    pattern = r'(?m)^(\s*)mem_bus_remaining_bytes <= (.*);$'
    matches = list(re.finditer(pattern, source))
    if len(matches) != 6:
        raise ValueError('unexpected remaining counter assignments')
    def update(match):
        indent, expression = match.groups()
        return (match.group(0) + f'\n{indent}mem_bus_last_transfer <= (({expression}) == 27\'d0);'
                + f'\n{indent}mem_bus_almost_last_transfer <= (({expression}) <= 27\'d2);')
    return re.sub(pattern, update, source)


def run(out, name, args):
    with (out / (name + '.log')).open('w') as log:
        result = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, timeout=180)
    if result.returncode:
        raise RuntimeError(name + ' failed; see log')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sc64', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    tests = Path(__file__).resolve().parents[3]
    if out == tests or tests in out.parents:
        parser.error('output must be outside tests')
    out.mkdir(parents=True, exist_ok=False)
    rtl = args.sc64.resolve() / 'fw/rtl'
    path = rtl / 'memory/memory_dma.sv'
    source = path.read_text()
    candidate = transform(source)
    (out / 'memory_dma.sv').write_text(candidate)
    negative = candidate.replace("mem_bus_last_transfer <= ((dma_scb.transfer_length) == 27'd0);", "mem_bus_last_transfer <= ((dma_scb.transfer_length) == 27'd1);")
    if negative == candidate:
        raise RuntimeError('negative control anchor missing')
    (out / 'negative.sv').write_text(negative)
    wrapper = '''module top(input clk, reset, start, stop, direction, byte_swap,
input [26:0] starting_address, transfer_length, input rx_empty, tx_full,
input [7:0] rx_rdata, input ack, input [15:0] rdata,
output busy, rx_read, tx_write, request, write, output [7:0] tx_wdata,
output [1:0] wmask, output [26:0] address, output [15:0] wdata);
dma_scb d(); fifo_bus f(); mem_bus m();
assign d.start=start; assign d.stop=stop; assign d.direction=direction;
assign d.byte_swap=byte_swap; assign d.starting_address=starting_address;
assign d.transfer_length=transfer_length; assign busy=d.busy;
assign f.rx_empty=rx_empty; assign f.rx_rdata=rx_rdata; assign f.tx_full=tx_full;
assign rx_read=f.rx_read; assign tx_write=f.tx_write; assign tx_wdata=f.tx_wdata;
assign m.ack=ack; assign m.rdata=rdata; assign request=m.request;
assign write=m.write; assign wmask=m.wmask; assign address=m.address; assign wdata=m.wdata;
memory_dma dut(clk,reset,d,f,m);
endmodule
'''
    (out / 'wrapper.sv').write_text(wrapper)
    interfaces = [rtl / 'memory/dma_scb.sv', rtl / 'fifo/fifo_bus.sv', rtl / 'memory/mem_bus.sv']
    for name, dma in [('gold', path), ('gate', out / 'memory_dma.sv'), ('negative', out / 'negative.sv')]:
        with (out / (name + '.v')).open('w') as target, (out / (name + '-sv2v.log')).open('w') as log:
            result = subprocess.run(['sv2v', '--top=top', *map(str, interfaces), str(dma), str(out / 'wrapper.sv')], stdout=target, stderr=log, timeout=60)
        if result.returncode:
            raise RuntimeError('sv2v failed')
    script = ''
    for name in ['gold', 'gate']:
        script += f'read_verilog {out}/{name}.v\nprep -top top\nrename top {name}\ndesign -stash {name}\n'
    script += '''design -copy-from gold -as gold gold
design -copy-from gate -as gate gate
equiv_make gold gate equiv
hierarchy -top equiv
equiv_simple -undef
equiv_induct -undef -seq 8
equiv_status -assert
'''
    (out / 'equivalence.ys').write_text(script)
    run(out, 'equivalence', ['yosys', '-Q', '-T', '-s', str(out / 'equivalence.ys')])
    negative_script = script.replace(f'{out}/gate.v', f'{out}/negative.v')
    (out / 'negative.ys').write_text(negative_script)
    with (out / 'negative.log').open('w') as log:
        result = subprocess.run(['yosys', '-Q', '-T', '-s', str(out / 'negative.ys')], stdout=log, stderr=subprocess.STDOUT, timeout=180)
    diagnostic = "ERROR: Found 2 unproven $equiv cells in 'equiv_status -assert'."
    if result.returncode != 1 or diagnostic not in (out / 'negative.log').read_text():
        raise RuntimeError('negative control did not fail equivalence')
    (out / 'result.json').write_text(json.dumps({'proof_passed': True, 'hardware_qualified': False,
        'negative_rejected': True,
        'proof_scope': 'All matched internal and output points; source-undefined startup remains undefined under equiv_simple -undef, not a physical power-up proof',
        'source_path': str(path),
        'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'candidate_sha256': hashlib.sha256(candidate.encode()).hexdigest()}, indent=2) + '\n')
    print('PASS actual DMA equivalence and negative control; uninitialized source state remains undefined')


if __name__ == '__main__':
    main()
