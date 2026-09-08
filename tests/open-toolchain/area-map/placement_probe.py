"""Localize placement failure with a stricter search cap, unchanged legality.

The divisor 100000 selects the 10000-attempt floor for a pinned candidate.
All route constraints and hard-cell diagnostic barriers match the baseline.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


EXPECTED = {
    'executable': 'c6fac50f2c98a7f94aadaffa29793900e8d1e5965b3905b8097274f749e9e607',
    'physical': '1e119761b3652b70b9bea735d6995d52e088666e67232a03d370a891604642ac',
    'compact_physical': '83ebf876c086953404991ff1643d88b21fa2c023c0ced9606872f45e07134037',
    'lpf': 'cea5c416f963c8302b33af7c2a02ba60a951b60cc0628f486da3351320b3369e',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['executable','physical','lpf','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--compact',action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() or out.is_relative_to(Path(__file__).resolve().parents[2]):
        parser.error('fresh output outside tests required')
    hashes = {str(p):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [args.executable,args.physical,args.lpf,Path(__file__)]}
    expected = [(args.executable,EXPECTED['executable']),
                (args.physical,EXPECTED['compact_physical'] if args.compact else EXPECTED['physical']),
                (args.lpf,EXPECTED['lpf'])]
    if any(hashes[str(p)]!=value for p,value in expected):
        parser.error('baseline input hash mismatch')
    out.mkdir(parents=True)
    command = [str(args.executable),'--device','LCMXO2-7000HC-6TG144C',
               '--json',str(args.physical),'--lpf',str(args.lpf),'--oddr-diagnostic',
               '--efb-routing-diagnostic','--fifo-routing-diagnostic','--freq','100',
               '--placer-heap-cell-placement-timeout','100000','--write',str(out/'routed.json')]
    with (out/'probe.log').open('x') as log:
        try:
            code = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=120).returncode
        except subprocess.TimeoutExpired:
            code = 124
    text = (out/'probe.log').read_text()
    result = {'hardware_qualified':False,'timing_qualified':False,'exit':code,
              'command':command,'sha256':hashes,'timeout_seconds':120,
              'route_complete':'Routing complete' in text,'netlist_written':(out/'routed.json').exists(),
              'placement_failures':re.findall(r"Unable to find legal placement[^\n]*",text),
              'errors':re.findall(r'ERROR:[^\n]*',text),
              'frequency_reports':re.findall(r'Max frequency[^\n]*',text)}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    return (code if code>=0 else 128-code) if code else (
        0 if result['route_complete'] and result['netlist_written'] else 1)


if __name__=='__main__':
    raise SystemExit(main())
