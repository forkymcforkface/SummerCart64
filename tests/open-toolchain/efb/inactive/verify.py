"""Run exact-wrapper routing and emission barriers in the diagnostic image."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode = True
from prepare import prepare

p = argparse.ArgumentParser()
p.add_argument('sc64', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=False)
here = Path(__file__).resolve().parent

def run(name, command, expected=0):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
    (a.output / (name + '.log')).write_text(result.stdout)
    assert result.returncode == expected, (name, result.returncode)
    return result.stdout

run('baseline', [sys.executable, '-B', str(here.parent / 'verify.py'), str(a.sc64), '/usr/local/bin/nextpnr-machxo2', str(a.output / 'baseline')])
source = json.loads((a.output / 'baseline/wrapper.json').read_text())
result, removed = prepare(source)
assert len(removed) == 24
path = a.output / 'prepared.json'
path.write_text(json.dumps(result))
base = ['/usr/local/bin/nextpnr-machxo2', '--device', 'LCMXO2-7000HC-6TG144C', '--json', str(path), '--lpf-allow-unconstrained', '--freq', '100']
run('normal-rejection', base, 125)
run('routing', base + ['--efb-routing-diagnostic', '--write', str(a.output / 'routed.json')])
log = run('emission-rejection', base + ['--efb-routing-diagnostic', '--no-place', '--no-route', '--textcfg', str(a.output / 'forbidden.config')], 125)
assert 'configuration bits are unmapped' in log
assert not (a.output / 'forbidden.config').exists()
run('saved-setting-rejection', ['/usr/local/bin/nextpnr-machxo2', '--device', 'LCMXO2-7000HC-6TG144C', '--json', str(a.output / 'routed.json'), '--no-pack', '--no-place', '--no-route', '--textcfg', str(a.output / 'replay.config')], 125)
run('graph', [sys.executable, '-B', str(here / 'graph.py')])
print('PASS exact wrapper route at requested 100 MHz; no EFB timing model; all configuration/replay barriers retained')
