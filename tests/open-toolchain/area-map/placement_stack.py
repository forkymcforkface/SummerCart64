"""Sample the pinned compact placement under GDB without changing the tool.

The inferior stops after 45 seconds, emits all thread stacks, and is killed.
Successful collection is a diagnostic result, never a completed route.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from alternative_placement import EXPECTED


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['executable', 'physical', 'lpf', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() or out.is_relative_to(Path(__file__).resolve().parents[2]):
        parser.error('fresh output outside tests required')
    hashes = {name: hashlib.sha256(getattr(args, name).read_bytes()).hexdigest()
              for name in EXPECTED}
    if hashes != EXPECTED:
        parser.error('pinned placement input hash mismatch')
    out.mkdir(parents=True)
    pidfile = out / 'inferior.pid'
    commands = ['set pagination off', 'set confirm off', 'set debuginfod enabled off',
                'start',
                f'python open({str(pidfile)!r}, "w").write(str(gdb.selected_inferior().pid))',
                'continue', 'thread apply all bt 20', 'kill', 'quit']
    command = ['gdb', '--batch']
    for item in commands:
        command.extend(['-ex', item])
    command.extend(['--args', str(args.executable), '--device', 'LCMXO2-7000HC-6TG144C',
                    '--json', str(args.physical), '--lpf', str(args.lpf),
                    '--oddr-diagnostic', '--efb-routing-diagnostic',
                    '--fifo-routing-diagnostic', '--freq', '100'])
    result = {'status': 'failed', 'hardware_qualified': False, 'route_complete': False,
              'sample_seconds': 45, 'wall_limit_seconds': 90, 'command': command,
              'sha256': hashes, 'signal_sent': False}
    started = time.monotonic()
    try:
        with (out / 'stack.log').open('x') as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            try:
                while process.poll() is None:
                    elapsed = time.monotonic() - started
                    if elapsed >= 90:
                        raise TimeoutError('debugger exceeded wall limit')
                    if elapsed >= 45 and pidfile.exists() and not result['signal_sent']:
                        os.kill(int(pidfile.read_text()), signal.SIGINT)
                        result['signal_sent'] = True
                    time.sleep(0.1)
                result['exit'] = process.returncode
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        text = (out / 'stack.log').read_text()
        if (result['exit'] != 0 or not result['signal_sent'] or
                'received signal SIGINT' not in text or '#0 ' not in text):
            raise ValueError('no successful interrupted stack sample')
        result['status'] = 'sampled'
    except Exception as exc:
        result['error'] = str(exc)
        raise
    finally:
        result['elapsed_seconds'] = time.monotonic() - started
        result['runner_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
