"""Exercise the isolated diagnostic backend; generated artifacts stay in the chosen output directory."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

p = argparse.ArgumentParser()
p.add_argument('sc64', type=Path)
p.add_argument('output', type=Path)
p.add_argument('--nextpnr', default='/src/nextpnr/build/nextpnr-machxo2')
p.add_argument('--database', default='/src/prjtrellis/database')
p.add_argument('--nextpnr-source', default='/src/nextpnr')
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=False)
here = Path(__file__).resolve().parent
source = a.sc64.resolve() / 'fw/rtl/vendor/lcmxo2/generated/fifo_8kb_lattice_generated.v'
top = a.output / 'top.json'

def run(name, args, expected=0, contains=None):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=180)
    (a.output / (name + '.log')).write_text(result.stdout)
    assert result.returncode == expected, (name, result.returncode)
    if contains:
        assert contains in result.stdout, (name, contains)
    return result.stdout

run('synthesis', ['yosys', '-p', f'read_verilog -lib +/lattice/cells_bb_xo2.v; read_verilog {source}; synth_lattice -family xo2 -top fifo_8kb_lattice_generated -json {top}'])
base = [a.nextpnr, '--device', 'LCMXO2-7000HC-6TG144C', '--lpf-allow-unconstrained']
run('default-rejection', base + ['--json', str(top)], 125, 'FIFO8KB timing is not characterized')
diagnostic = base + ['--fifo-routing-diagnostic']
log = run('route', diagnostic + ['--json', str(top), '--textcfg', str(a.output / 'top.config'), '--write', str(a.output / 'routed.json'), '--pre-route', str(here / 'reachability.py')])
run('saved-setting-rejection', base + ['--json', str(a.output / 'routed.json'), '--no-pack', '--no-place', '--no-route', '--textcfg', str(a.output / 'rejected.config')], 125, 'FIFO8KB configuration requires fresh')
run('saved-timing-rejection', base + ['--json', str(a.output / 'routed.json'), '--no-pack', '--no-place'], 125, 'FIFO8KB timing requires fresh')
run('saved-setting-opt-in', diagnostic + ['--json', str(a.output / 'routed.json'), '--no-pack', '--no-place', '--no-route', '--textcfg', str(a.output / 'reloaded.config')])
rows = json.loads(next(line.split('=', 1)[1] for line in log.splitlines() if line.startswith('FIFO_FLAG_REACHABILITY=')))
assert len(rows) == 26 and all(flag['downhill_pips'] > 0 for row in rows for flag in row['flags'].values())
for name, edit, message in (
    ('unsupported-width', lambda params: params.update(DATA_WIDTH_W=format(18, '032b')), 'supports only SC64 9-bit/NOREG'),
    ('invalid-pointer', lambda params: params.update(AEPOINTER='0b0000000000100x'), 'requires explicit 14-bit AEPOINTER'),
    ('missing-csdecode', lambda params: params.pop('CSDECODE_W'), 'requires explicit 2-bit CSDECODE_W'),
    ('invalid-csdecode', lambda params: params.update(CSDECODE_R='0b1x'), 'requires explicit 2-bit CSDECODE_R'),
    ('short-csdecode', lambda params: params.update(CSDECODE_W='0b1'), 'requires explicit 2-bit CSDECODE_W'),
    ('missing-pointer', lambda params: params.pop('AEPOINTER'), 'requires explicit 14-bit AEPOINTER'),
):
    data = json.loads(top.read_text())
    cells = data['modules']['fifo_8kb_lattice_generated']['cells']
    fifo = next(cell for cell in cells.values() if cell['type'] == 'FIFO8KB')
    edit(fifo['parameters'])
    path = a.output / (name + '.json')
    path.write_text(json.dumps(data))
    run(name, diagnostic + ['--json', str(path), '--textcfg', str(a.output / (name + '.config'))], 125, message)
bit = a.output / 'diagnostic.bit'
repacked = a.output / 'repacked.bit'
run('pack', ['ecppack', '--db', a.database, str(a.output / 'top.config'), str(bit)])
run('unpack', ['ecpunpack', '--db', a.database, str(bit), str(a.output / 'roundtrip.config')])
run('repack', ['ecppack', '--db', a.database, str(a.output / 'roundtrip.config'), str(repacked)])
assert bit.read_bytes() == repacked.read_bytes()
atomic = a.output / 'atomic-fixture'
before = {}
for tile in ('EBR0', 'EBR0_END'):
    path = atomic / 'database/MachXO2/tiledata' / tile / 'bits.db'
    path.parent.mkdir(parents=True)
    text = (Path(a.database) / 'MachXO2/tiledata' / tile / 'bits.db').read_text()
    for flag, route in (('AE', 'E1_JQ4'), ('AF', 'E1_JF4'), ('EF', 'E1_JQ3'), ('FF', 'E1_JF3')):
        text = text.replace(f'.fixed_conn {route} J{flag}_EBR', f'.fixed_conn J{flag}_EBR {route}')
    path.write_text(text)
    before[path] = path.read_bytes()
path = atomic / 'fuzzers/machxo2/040-ebr_routing/mk_nets.py'
path.parent.mkdir(parents=True)
path.write_text('deliberately missing final-file anchors\n')
before[path] = path.read_bytes()
run('atomic-anchor-rejection', ['/usr/bin/python3', '-B', str(here / 'apply_trellis.py'), str(atomic)], 1, 'flag direction missing')
assert all(path.read_bytes() == data for path, data in before.items())
atomic_nextpnr = a.output / 'atomic-nextpnr'
(atomic_nextpnr / 'machxo2').mkdir(parents=True)
before = {}
for name in ('main.cc', 'pack.cc', 'arch.cc', 'bitstream.cc'):
    text = subprocess.check_output(['git', '-C', a.nextpnr_source, 'show', '8dbcee5c3c4415770b6fd06d5ccb2db89545b8ec:machxo2/' + name], text=True, timeout=30)
    if name == 'bitstream.cc':
        text = text.replace('    void write_bram(CellInfo *ci)\n    {', '    void intentionally_missing_final_anchor(CellInfo *ci)\n    {')
    path = atomic_nextpnr / 'machxo2' / name
    path.write_text(text)
    before[path] = path.read_bytes()
run('atomic-nextpnr-rejection', ['/usr/bin/python3', '-B', str(here / 'apply.py'), str(atomic_nextpnr)], 1, 'bitstream.cc: patch anchor is not unique')
assert all(path.read_bytes() == data for path, data in before.items())
summary = dict(flag_outputs=104, reachable=104, roundtrip_sha256=hashlib.sha256(bit.read_bytes()).hexdigest(), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), qualified=False)
(a.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print('PASS diagnostic routing, default/mode/parameter rejection, bitstream roundtrip; timing and hardware remain unqualified')
