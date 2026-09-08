"""Regenerate the stock EFB wrapper through installed vendor front-end utilities.

The original source is immutable. Generated vendor netlists remain in a new
external output directory; no mapping, configuration emission or flashing runs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def tokens(source):
    result = []
    pattern = (r'"(?:\\.|[^"\\])*"|/\*[\s\S]*?\*/|//[^\n]*|\\[^\s]+'
               r'|[A-Za-z_$][\w$]*|[0-9][\w\x27]*'
               r'|===|!==|<<<|>>>|<=|>=|==|!=|&&|\|\||<<|>>|\*\*|~\^|\^~|~&|~\||[^\s]')
    for token in re.findall(pattern, source):
        if token.startswith(('/*', '//')):
            if 'synthesis' in token:
                result.append(' '.join(token.split()))
        else:
            result.append(token)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sc64', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--foundry', type=Path, default=Path('/usr/local/diamond/3.13/ispfpga'))
    args = parser.parse_args()
    out = args.output.resolve()
    for tests in (Path(__file__).resolve().parents[3], args.sc64.resolve() / 'tests'):
        if out == tests or tests in out.parents:
            parser.error('generated output must be outside tests')
    source = args.sc64 / 'fw/rtl/vendor/lcmxo2/generated/efb_lattice_generated.v'
    original = source.read_bytes()
    out.mkdir(parents=True, exist_ok=False)
    foundry = args.foundry.resolve()
    env = os.environ.copy()
    env.update(FOUNDRY=str(foundry), LD_LIBRARY_PATH=str(foundry / 'bin/lin64'))
    commands = []

    def run(tool, arguments, artifact):
        command = [str(foundry / 'bin/lin64' / tool), *arguments]
        with (out / (tool + '.log')).open('w') as log:
            subprocess.run(command, cwd=out, env=env, stdout=log,
                           stderr=subprocess.STDOUT, timeout=60, check=True)
        if not (out / artifact).is_file() or (out / artifact).stat().st_size == 0:
            raise RuntimeError('missing generated artifact: ' + artifact)
        commands.append(command)

    run('scuba', ['-w', '-n', 'efb_lattice_generated', '-lang', 'verilog',
                 '-synth', 'synplify', '-bus_exp', '7', '-bb', '-type', 'efb',
                 '-arch', 'xo2c00', '-freq', '100', '-ufm', '-ufm_ebr', '2038',
                 '-mem_size', '8', '-ufm_0', '-wb', '-dev', '7000'], 'efb_lattice_generated.v')
    generated = (out / 'efb_lattice_generated.v').read_bytes()
    if tokens(original.decode()) != tokens(generated.decode()):
        raise RuntimeError('generated HDL differs from stock source')
    run('edif2ngd', ['-l', 'MachXO2', '-d', 'LCMXO2-7000HC',
                    'efb_lattice_generated.edn', 'efb.ngo'], 'efb.ngo')
    run('ngdbuild', ['-a', 'MachXO2', '-d', 'LCMXO2-7000HC',
                    'efb.ngo', 'efb.ngd'], 'efb.ngd')
    if 'DRC complete with no errors or warnings' not in (out / 'ngdbuild.log').read_text():
        raise RuntimeError('missing clean DRC completion marker')
    if source.read_bytes() != original:
        raise RuntimeError('original source changed')
    report = {'hdl_token_identity': True, 'token_count': len(tokens(original.decode())),
              'source_sha256': hashlib.sha256(original).hexdigest(),
              'generated_sha256': hashlib.sha256(generated).hexdigest(),
              'commands': commands, 'ngd_drc_clean': True,
              'configuration_equivalence': False, 'hardware_qualified': False}
    (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
