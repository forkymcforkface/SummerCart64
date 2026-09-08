"""Compare mapped RAM against source using an independently installed DP8KC model.

The proprietary model is a caller-supplied input and is never copied into the
repository. This checks functional collisions, not device timing or hardware.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('focused', type=Path, help='successful run.py output')
    parser.add_argument('model', type=Path, help='installed vendor DP8KC.v')
    parser.add_argument('output', type=Path, help='new ignored output directory')
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    out = args.output.resolve()
    mapped = args.focused.resolve() / 'large-mapped.json'
    if any(c.isspace() or c in '\";\\' for p in (mapped, out) for c in str(p)):
        parser.error('use simple POSIX mapped/output paths')
    if here.parent.parent == out or here.parent.parent in out.parents:
        parser.error('output must be outside tests')
    model = args.model.resolve()
    model_hash = hashlib.sha256(model.read_bytes()).hexdigest()
    out.mkdir(parents=True, exist_ok=False)

    def run(name, command):
        with (out / (name + '.log')).open('w') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                           timeout=120, check=True)

    script = out / 'export.ys'
    script.write_text(f'read_json {mapped}\nrename dual_old gate\nselect gate\nwrite_verilog -selected {out}/gate.v\n')
    run('export', ['yosys', '-Q', '-T', '-s', str(script)])
    run('compile', ['iverilog', '-g2012', '-o', str(out / 'physical.vvp'),
                    str(here / 'physical_tb.v'), str(out / 'gate.v'),
                    str(here / 'dual_old.v'), str(model)])
    run('model', ['vvp', str(out / 'physical.vvp')])
    if 'PASS physical DP8KC collision comparison cycles=6000' not in (out / 'model.log').read_text():
        raise RuntimeError('missing physical comparison completion marker')
    result = {'functional_model_comparison': True, 'cycles': 6000,
              'mapped_sha256': hashlib.sha256(mapped.read_bytes()).hexdigest(),
              'model_sha256': model_hash, 'hardware_qualified': False}
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
