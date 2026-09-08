"""Count real MachXO2 packer cells without claiming an observation wrapper fits.

Exit 3 explicitly denotes an unqualified packing-only result, even when the
packer succeeds. No placement, routing, configuration or bitstream is requested.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mapped', type=Path)
    parser.add_argument('nextpnr', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    tests = Path(__file__).resolve().parents[2]
    if out.exists() or out == tests or tests in out.parents:
        parser.error('output must be fresh and outside tests')
    out.mkdir(parents=True)
    command = [str(args.nextpnr.resolve()), '--device','LCMXO2-7000HC-6TG144C',
               '--json',str(args.mapped.resolve()),'--pack-only','--write',str(out/'packed.json')]
    with (out/'pack.log').open('w') as log:
        result = subprocess.run(command,stdout=log,stderr=log,timeout=120)
    report = {'packer_exit':result.returncode,'hardware_qualified':False,
              'fit_demonstrated':False,'placement_performed':False,'route_performed':False,
              'command':command,'input_sha256':hashlib.sha256(args.mapped.read_bytes()).hexdigest(),
              'executable_sha256':hashlib.sha256(args.nextpnr.read_bytes()).hexdigest()}
    if result.returncode == 0:
        packed = json.loads((out/'packed.json').read_text())
        report['packed_cells'] = dict(Counter(c['type'] for m in packed['modules'].values() for c in m['cells'].values()))
        report['observation_io_exceeds_device'] = report['packed_cells'].get('TRELLIS_IO',0)>336
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 3 if result.returncode == 0 else result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
