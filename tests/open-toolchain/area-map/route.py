"""Bound one explicitly unqualified 100 MHz diagnostic route to 120 seconds.

Existing physical preparation and pin/clock contracts are inputs, not changed
here. No timing-allow-fail, bitstream output, hardware access or option sweep.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['executable','physical','lpf','output']:
        p.add_argument('--'+name,type=Path,required=True)
    a = p.parse_args()
    out = a.output.resolve()
    if out.exists() or out.is_relative_to(Path(__file__).resolve().parents[2]):
        p.error('fresh output outside tests required')
    hashes = {str(x):hashlib.sha256(x.read_bytes()).hexdigest()
              for x in [a.executable,a.physical,a.lpf,Path(__file__)]}
    if hashes[str(a.executable)] != 'c6fac50f2c98a7f94aadaffa29793900e8d1e5965b3905b8097274f749e9e607':
        p.error('unexpected diagnostic nextpnr executable')
    if hashes[str(a.lpf)] != 'cea5c416f963c8302b33af7c2a02ba60a951b60cc0628f486da3351320b3369e':
        p.error('unexpected diagnostic LPF')
    out.mkdir(parents=True)
    command = [str(a.executable),'--device','LCMXO2-7000HC-6TG144C',
               '--json',str(a.physical),'--lpf',str(a.lpf),
               '--oddr-diagnostic','--efb-routing-diagnostic','--fifo-routing-diagnostic',
               '--freq','100','--write',str(out/'routed.json')]
    with (out/'route.log').open('x') as log:
        try:
            code = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=120).returncode
        except subprocess.TimeoutExpired:
            code = 124
    text = (out/'route.log').read_text()
    result = {'hardware_qualified':False,'timing_qualified':False,'exit':code,
              'command':command,'timeout_seconds':120,'source_sha256':hashes,
              'route_complete':'Routing complete' in text,
              'frequency_reports':re.findall(r'Max frequency[^\n]*',text),
              'errors':re.findall(r'ERROR:[^\n]*',text),
              'netlist_written':(out/'routed.json').exists()}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    if code == 0 and not (result['route_complete'] and result['netlist_written']):
        return 1
    return code if code >= 0 else 128-code


if __name__ == '__main__':
    raise SystemExit(main())
