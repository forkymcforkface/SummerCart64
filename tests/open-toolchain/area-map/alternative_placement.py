"""Try one bounded simulated-annealing placement on the compact LZW input.

The invocation derives from route.py and changes only the documented placer.
It retains strict timing, legality, device, pin and hard-block diagnostic gates.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


EXPECTED = {
    'executable': 'c6fac50f2c98a7f94aadaffa29793900e8d1e5965b3905b8097274f749e9e607',
    'physical': '83ebf876c086953404991ff1643d88b21fa2c023c0ced9606872f45e07134037',
    'lpf': 'cea5c416f963c8302b33af7c2a02ba60a951b60cc0628f486da3351320b3369e',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['executable', 'physical', 'lpf', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() or out.is_relative_to(Path(__file__).resolve().parents[2]):
        parser.error('fresh output outside tests required')
    inputs = {'executable': args.executable, 'physical': args.physical,
              'lpf': args.lpf}
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest()
              for name, path in inputs.items()}
    if hashes != EXPECTED:
        parser.error('alternative-placement input hash mismatch')
    help_text = subprocess.check_output([str(args.executable), '--help'],
                                        text=True, stderr=subprocess.STDOUT)
    if not re.search(r'available:\s+sa,\s*heap', help_text):
        parser.error('pinned nextpnr does not advertise the sa placer')
    out.mkdir(parents=True)
    command = [str(args.executable), '--device', 'LCMXO2-7000HC-6TG144C',
               '--json', str(args.physical), '--lpf', str(args.lpf),
               '--oddr-diagnostic', '--efb-routing-diagnostic',
               '--fifo-routing-diagnostic', '--freq', '100', '--placer', 'sa',
               '--write', str(out / 'routed.json')]
    with (out / 'route.log').open('x') as log:
        try:
            code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                  timeout=120).returncode
        except subprocess.TimeoutExpired:
            code = 124
    text = (out / 'route.log').read_text()
    route_started = bool(re.search(r'^Info: Routing(?: globals|\.\.)', text,
                                   re.MULTILINE))
    initial_progress = re.findall(r'initial placement placed [^\n]*', text)
    result = {
        'hardware_qualified': False,
        'timing_qualified': False,
        'external_constraints_qualified': False,
        'hard_blocks_qualified': False,
        'exit': code,
        'command': command,
        'timeout_seconds': 120,
        'sha256': {**hashes,
                   'runner': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        'placer_help': 'sa, heap',
        'placement_complete': route_started,
        'initial_placement_last': initial_progress[-1] if initial_progress else None,
        'route_complete': 'Routing complete' in text,
        'netlist_written': (out / 'routed.json').exists(),
        'placement_failures': re.findall(r'failed to place[^\n]*', text),
        'errors': re.findall(r'ERROR:[^\n]*', text),
        'frequency_reports': re.findall(r'Max frequency[^\n]*', text),
    }
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    if code:
        return code if code >= 0 else 128 - code
    return 0 if (result['placement_complete'] and result['route_complete'] and
                 result['netlist_written']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
