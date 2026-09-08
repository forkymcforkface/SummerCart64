"""Check the 51 SC64 inout pads against source intent without emitting bits.

This gate checks existing pattern consistency only. Other pads, electrical
standards, routing, timing and physical qualification remain outside its scope.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, '/usr/local/lib/trellis')
import pytrellis

spec = importlib.util.spec_from_file_location('constraint_audit', Path(__file__).resolve().parents[1] / 'constraints/audit.py')
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)
SUPPORTED = ({f'{base}[{i}]' for base, count in [('flash_dq', 4), ('n64_pi_ad', 16),
             ('sdram_dq', 16), ('usb_miosi', 8), ('sd_dat', 4)] for i in range(count)}
             | {'sd_cmd', 'n64_cic_dq', 'n64_si_dq'})


def enum_options(text):
    result = {}
    current = None
    for line in text.splitlines():
        if line.startswith('.config_enum '):
            current = line.split()[1]
            result[current] = {}
        elif not line or line.startswith('.') or line.startswith('#'):
            current = None
        elif current:
            words = line.split()
            result[current][words[0]] = set(words[1:]) - {'-'}
    return result


def coordinates(token):
    match = re.fullmatch(r'!?F(\d+)B(\d+)', token)
    if not match:
        raise ValueError('unsupported bit token ' + token)
    return tuple(map(int, match.groups()))


def mismatches(cram, pattern):
    return sorted(token for token in pattern if bool(cram.bit(*coordinates(token))) == token.startswith('!'))


def check(chip, lpf, top, database):
    inventory = audit_module.audit(lpf, top)
    if not inventory['inventory_valid']:
        raise ValueError('invalid source inventory: ' + '; '.join(inventory['errors']))
    if chip.info.name not in {'LCMXO2-7000', 'LCMXO2-7000HC'}:
        raise ValueError('unsupported device ' + chip.info.name)
    ports = inventory['ports']
    if {name for name, port in ports.items() if port['direction'] == 'inout'} != SUPPORTED:
        raise ValueError('unsupported or changed SC64 inout directions')
    package = json.loads((database / 'MachXO2/LCMXO2-7000/iodb.json').read_text())
    pins = package['packages']['TQFP144']
    metadata = {(m['row'], m['col'], m['pio']): m for m in package['pio_metadata']}
    rows, errors = [], []
    for name in sorted(SUPPORTED):
        port = ports[name]
        attrs = port['electrical']
        if attrs.get('IO_TYPE') != 'LVCMOS33' or attrs.get('PULLMODE') not in {'UP', 'DOWN', 'NONE'}:
            raise ValueError('unsupported electrical intent for ' + name)
        pin = pins[port['site']]
        location = (pin['row'], pin['col'], pin['pio'])
        if inventory['banks_v'].get(str(metadata[location]['bank'])) != '3.3':
            raise ValueError('unsupported bank voltage')
        tiles = [t for _, t in chip.tiles.items() if t.info.type.startswith('PIC_')
                 and (t.info.get_row_col().first, t.info.get_row_col().second) == location[:2]]
        if len(tiles) != 1:
            raise ValueError('ambiguous physical pad tile ' + name)
        tile = tiles[0]
        path = database / 'MachXO2/tiledata' / tile.info.type / 'bits.db'
        enums = enum_options(path.read_text())
        key = 'PIO' + pin['pio']
        base = enums[key + '.BASE_TYPE']
        expected = base['BIDIR_LVCMOS33']
        pull = enums[key + '.PULLMODE'][attrs['PULLMODE']]
        bad_base, bad_pull = mismatches(tile.cram, expected), mismatches(tile.cram, pull)
        matched = sorted(value for value, bits in base.items() if not mismatches(tile.cram, bits))
        aliases = sorted(value for value, bits in base.items() if bits == expected)
        db = pytrellis.get_tile_bitdata(pytrellis.TileLocator('MachXO2', chip.info.name, tile.info.type))
        decoded = {e.name: e.value for e in db.tile_cram_to_config(tile.cram).cenums}.get(key + '.BASE_TYPE', 'NONE')
        row = {'port': name, 'site': port['site'], 'tile': tile.info.name, 'pio': pin['pio'],
               'bank': metadata[location]['bank'], 'pull': attrs['PULLMODE'],
               'receiver_pattern': sorted(expected), 'pull_pattern': sorted(pull),
               'base_mismatches': bad_base, 'pull_mismatches': bad_pull,
               'decoded': decoded, 'matched_candidates': matched, 'encoded_aliases': aliases,
               'standard_status': 'ambiguous_database_patterns',
               'database_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        rows.append(row)
        if bad_base or bad_pull:
            errors.append(name + ': source pattern mismatch')
    return {'source_pattern_gate_passed': not errors, 'hardware_qualified': False,
            'scope': '51 source-declared SC64 inouts only; no electrical standard identification',
            'errors': errors, 'ports': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bit', type=Path)
    parser.add_argument('lpf', type=Path)
    parser.add_argument('top', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--database', type=Path, default=Path('/src/prjtrellis/database'))
    args = parser.parse_args()
    tests = Path(__file__).resolve().parents[2]
    if args.output.resolve() == tests or tests in args.output.resolve().parents:
        parser.error('output must be outside tests')
    try:
        pytrellis.load_database(str(args.database))
        chip = pytrellis.Bitstream.read_bit(str(args.bit)).deserialise_chip()
        report = check(chip, args.lpf.read_text(), args.top.read_text(), args.database)
        report['input_sha256'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.bit, args.lpf, args.top)}
    except (ValueError, KeyError, OSError, RuntimeError) as exc:
        report = {'source_pattern_gate_passed': False, 'hardware_qualified': False, 'errors': [str(exc)]}
    with args.output.open('x') as output:
        output.write(json.dumps(report, indent=2) + '\n')
    return 0 if report['source_pattern_gate_passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
