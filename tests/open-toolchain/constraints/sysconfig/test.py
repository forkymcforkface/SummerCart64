"""Exercise the real SYSCONFIG parser and existing CFG0/CFG1 bit encoders.

Artifacts are diagnostic only. The original complete LPF remains immutable;
parser acceptance never qualifies its unsupported timing/electrical semantics.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--nextpnr', required=True)
    parser.add_argument('--sc64', type=Path, required=True)
    parser.add_argument('--database', type=Path, default=Path('/src/prjtrellis/database'))
    args = parser.parse_args()
    out = args.output.resolve()
    tests = Path(__file__).resolve().parents[3]
    if out == tests or tests in out.parents:
        parser.error('output must be outside tests')
    out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, '/usr/local/lib/trellis')
    import pytrellis
    pytrellis.load_database(str(args.database))

    def run(name, command, error=None):
        log = out / (name + '.log')
        with log.open('w') as stream:
            proc = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=120)
        content = log.read_text()
        if error:
            if proc.returncode == 0 or 'ERROR: ' + error not in content:
                raise RuntimeError(f'{name}: wrong failure {proc.returncode}')
        elif proc.returncode:
            raise RuntimeError(f'{name}: exit {proc.returncode}')
        return content

    allowed = {'SDM_PORT': ['DISABLE', 'DONE', 'INITN', 'PROGRAMN', 'PROGRAMN_DONE', 'PROGRAMN_DONE_INITN'],
               'I2C_PORT': ['DISABLE', 'ENABLE']}
    db_report = {}
    for key, values in allowed.items():
        kind = 'CFG0' if key == 'SDM_PORT' else 'CFG1'
        db = args.database / 'MachXO2/tiledata' / kind / 'bits.db'
        lines = db.read_text().splitlines()
        start = lines.index('.config_enum SYSCONFIG.' + key + ' DISABLE') + 1
        choices = {}
        for line in lines[start:]:
            if not line or line.startswith('.'):
                break
            words = line.split()
            choices[words[0]] = words[1:]
        expected = {v: (['F5B38'] if v == 'ENABLE' else ['-']) for v in values}
        if key == 'SDM_PORT':
            expected = {v: (['F5B4'] if 'DONE' in v else ['-']) for v in values}
        if choices != expected:
            raise RuntimeError('pinned database value/bit profile changed: ' + key)
        db_report[key] = {'sha256': hashlib.sha256(db.read_bytes()).hexdigest(), 'choices': choices}

    fixture = Path(__file__).resolve().parent.parent / 'allports/fixture.v'
    run('synth', ['yosys', '-Q', '-T', '-p',
                  f'read_verilog {fixture}; synth_lattice -family xo2 -top allports -json {out}/input.json'])
    base = [args.nextpnr, '--device', 'LCMXO2-7000HC-6TG144C', '--json', str(out / 'input.json')]
    parse_base = base + ['--lpf-allow-unconstrained', '--no-pack', '--no-place', '--no-route']

    def parse_case(name, statement, error=None):
        lpf = out / (name + '.lpf')
        lpf.write_text(statement)
        result = out / (name + '.json')
        run(name, parse_base + ['--lpf', str(lpf), '--write', str(result)], error)
        if error:
            if result.exists():
                raise RuntimeError('failed parse wrote a design')
            return None
        return json.loads(result.read_text())['modules']['top']['settings']

    positives = 0
    for key, values in allowed.items():
        for value in values:
            settings = parse_case(key + '-' + value, f'SYSCONFIG {key}="{value}";')
            if settings.get('arch.sysconfig.' + key) != value:
                raise RuntimeError('parser value changed')
            positives += 1
    settings = parse_case('ordered', 'SYSCONFIG SDM_PORT=DONE I2C_PORT=DISABLE;\n'
                          'SYSCONFIG SDM_PORT=DISABLE I2C_PORT=ENABLE;')
    if any(settings.get('arch.sysconfig.' + k) != v for k, v in
           [('SDM_PORT', 'DISABLE'), ('I2C_PORT', 'ENABLE')]):
        raise RuntimeError('ordered override failed')
    negative = [
        ('sdm-bad', 'SDM_PORT=ENABLE', 'unsupported SYSCONFIG SDM_PORT'),
        ('i2c-bad', 'I2C_PORT=ON', 'unsupported SYSCONFIG I2C_PORT'),
        ('i2c-lower', 'I2C_PORT=enable', 'unsupported SYSCONFIG I2C_PORT'),
        ('empty', 'I2C_PORT=', "expected syntax 'SYSCONFIG"),
        ('double', 'SDM_PORT==DONE', "expected syntax 'SYSCONFIG"),
        ('quoted-empty', 'SDM_PORT=""', 'unsupported SYSCONFIG SDM_PORT'),
        ('unknown', 'SURPRISE=ENABLE', 'unexpected SYSCONFIG key'),
    ]
    for name, value, error in negative:
        parse_case(name, 'SYSCONFIG ' + value + ';', error)

    physical = []
    tile_states = {}
    for sdm, i2c in [('DISABLE', 'DISABLE'), ('DISABLE', 'ENABLE'), ('DONE', 'DISABLE'), ('DONE', 'ENABLE')]:
        name = 'bits-' + sdm + '-' + i2c
        lpf = out / (name + '.lpf')
        lpf.write_text(f'SYSCONFIG SDM_PORT={sdm} I2C_PORT={i2c};\n'
                       'IOBUF ALLPORTS IO_TYPE=LVCMOS33;\n' + '\n'.join(
                           f'LOCATE COMP "{port}" SITE "{site}";'
                           for port, site in [('a', 1), ('b', 2), ('v[0]', 3), ('v[1]', 10), ('d', 11)]))
        cfg, bit, decoded = [out / (name + suffix) for suffix in ('.config', '.bit', '.decoded.config')]
        run(name, base + ['--lpf', str(lpf), '--textcfg', str(cfg)])
        text = cfg.read_text()
        for key, value in [('SDM_PORT', sdm), ('I2C_PORT', i2c)]:
            if 'enum: SYSCONFIG.' + key + ' ' + value not in text:
                raise RuntimeError('existing encoder lost requested enum')
        run(name + '-pack', ['ecppack', str(cfg), str(bit)])
        run(name + '-unpack', ['ecpunpack', str(bit), str(decoded)])
        chip = pytrellis.Bitstream.read_bit(str(bit)).deserialise_chip()
        states = {}
        for tile_name, tile in chip.tiles.items():
            if tile.info.type not in ('CFG0', 'CFG1'):
                continue
            cram = tile.cram
            states[tile.info.type] = {(f, b) for f in range(cram.frames())
                                     for b in range(cram.bits()) if cram.bit(f, b)}
        for kind, coord, expected in [('CFG0', (5, 4), sdm == 'DONE'), ('CFG1', (5, 38), i2c == 'ENABLE')]:
            if (coord in states[kind]) != expected:
                raise RuntimeError('wrong physical configuration bit')
        tile_states[sdm, i2c] = states
        physical.append({'SDM_PORT': sdm, 'I2C_PORT': i2c, 'exact_bits': True})
    reference = tile_states['DISABLE', 'DISABLE']
    for (sdm, i2c), states in tile_states.items():
        for kind, expected in [('CFG0', {(5, 4)} if sdm == 'DONE' else set()),
                               ('CFG1', {(5, 38)} if i2c == 'ENABLE' else set())]:
            if states[kind] ^ reference[kind] != expected:
                raise RuntimeError('unrelated CFG tile bits changed')

    original = args.sc64 / 'fw/project/lcmxo2/sc64.lpf'
    sha = hashlib.sha256(original.read_bytes()).hexdigest()
    log = run('original-full-lpf', parse_base + ['--lpf', str(original), '--write', str(out / 'original.json')])
    if hashlib.sha256(original.read_bytes()).hexdigest() != sha:
        raise RuntimeError('original LPF mutated')
    settings = json.loads((out / 'original.json').read_text())['modules']['top']['settings']
    if settings.get('arch.sysconfig.SDM_PORT') != 'DISABLE' or settings.get('arch.sysconfig.I2C_PORT') != 'ENABLE':
        raise RuntimeError('original LPF settings absent')
    result = {'parser_positive_cases': positives + 1, 'parser_negative_cases': len(negative),
              'physical_cases': physical, 'database': db_report, 'original_lpf_sha256': sha,
              'original_lpf_parser_accepted': True, 'full_lpf_qualified': False,
              'hardware_qualified': False, 'qualification': 'UNQUALIFIED',
              'remaining': ['aliases', 'bank declarations', 'BLOCK paths', 'external setup/hold/output delays'],
              'original_warnings': [line for line in log.splitlines() if 'Warning:' in line]}
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
