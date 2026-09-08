"""Prove the focused corruption test rejects an oversized logical stack guard.

Only a generated negative-control copy changes; it retains 512 physical bytes
but delays the guard until 4096. A byte-correct or merely terminating run is
insufficient: the bounded corruption watchdog must reject this mutation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('focused', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    prior, output = args.focused.resolve(), args.output.resolve()
    source = Path(__file__).resolve().parent.parent
    if output.exists() or source.parent in output.parents:
        raise ValueError('Output must be new and outside tests')
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    passed = json.loads((prior/'result.json').read_text())
    if passed['status'] != 'pass' or passed['mode'] != 'core' or not passed['focused']:
        raise ValueError('Requires a passed focused core result')
    for name, expected in passed['generated_hashes'].items():
        if digest(prior/name) != expected:
            raise ValueError('Passed artifact changed: '+name)
    core = (prior/'gif_lzw_cached.sv').read_text()
    if core.count('stack_size >= 512') != 1:
        raise ValueError('Stack guard anchor changed')
    output.mkdir(parents=True)
    result = {'status': 'running', 'hardware_qualified': False}
    try:
        (output/'gif_lzw_cached.sv').write_text(core.replace('stack_size >= 512', 'stack_size >= 4096'))
        with (output/'compile.log').open('w') as log:
            subprocess.run(['verilator', '--cc', '--exe', '--build', '-j', '2', '--top-module', 'gif_lzw_cached',
                            '--Mdir', str(output/'obj'), str(output/'gif_lzw_cached.sv'),
                            str(prior/'cached_dictionary.sv'), str(prior/'driver.cpp')],
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
        with (output/'simulation.log').open('w') as log:
            completed = subprocess.run([str(output/'obj/Vgif_lzw_cached'), str(prior/'fixtures.bin')],
                                       stdout=log, stderr=subprocess.STDOUT, timeout=60)
        text = (output/'simulation.log').read_text()
        if completed.returncode == 0 or 'corrupt guard exceeds512-stack bound' not in text:
            raise ValueError('Mutation was not rejected by the stack-bound gate')
        result.update(status='pass', rejected_exit=completed.returncode,
                      original_result_sha256=digest(prior/'result.json'),
                      mutated_rtl_sha256=digest(output/'gif_lzw_cached.sv'),
                      runner_sha256=digest(Path(__file__)))
    except Exception as exc:
        result.update(status='failed', error=str(exc))
        raise
    finally:
        (output/'result.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
