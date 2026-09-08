"""Expose PIO mode/pull overlap using only existing database-generated bits.

The optional diagnostic ranks patterns without independently owned pull bits.
It never changes a database, emits a bitstream, or qualifies an I/O standard.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from check import enum_options


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--database', type=Path, default=Path('/src/prjtrellis/database'))
    parser.add_argument('--pullmask-diagnostic', action='store_true')
    parser.add_argument('--source-reference', nargs=3, type=Path, metavar=('BIT', 'LPF', 'TOP'))
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    out = args.output.resolve()
    tests = here.parents[1]
    if out == tests or tests in out.parents:
        parser.error('output must be outside tests')
    out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, '/usr/local/lib/trellis')
    import pytrellis
    pytrellis.load_database(str(args.database))
    report = {'encoding_changed': False, 'hardware_qualified': False,
              'diagnostic_enabled': args.pullmask_diagnostic, 'cases': []}
    for kind in ['PIC_B0', 'PIC_T0', 'PIC_L2', 'PIC_L2_VREF4', 'PIC_R1']:
        path = args.database / 'MachXO2/tiledata' / kind / 'bits.db'
        enums = enum_options(path.read_text())
        pullbits = {token.lstrip('!') for key, options in enums.items() if key.endswith('.PULLMODE')
                    for bits in options.values() for token in bits}
        for pull in ('DOWN', 'NONE', 'UP'):
            chip = pytrellis.Chip('LCMXO2-7000HC')
            tile = next(t for _, t in chip.tiles.items() if t.info.type == kind)
            db = pytrellis.get_tile_bitdata(pytrellis.TileLocator('MachXO2', chip.info.name, kind))
            cfg = pytrellis.TileConfig()
            for pio in ('A', 'B'):
                cfg.add_enum('PIO' + pio + '.BASE_TYPE', 'BIDIR_LVCMOS33')
                cfg.add_enum('PIO' + pio + '.PULLMODE', pull)
            text = '.device LCMXO2-7000HC\n\n.tile ' + tile.info.name + '\n' + cfg.to_string()
            chip = pytrellis.ChipConfig.from_string(text).to_chip()
            tile = chip.tiles[tile.info.name]
            decoded = db.tile_cram_to_config(tile.cram)
            named = {e.name: e.value for e in decoded.cenums}
            for pio in ('A', 'B'):
                key = 'PIO' + pio + '.BASE_TYPE'
                options = enums[key]
                observed = named.get(key, 'NONE')
                requested = options['BIDIR_LVCMOS33']
                equivalent = options[observed] == requested
                matches = []
                if args.pullmask_diagnostic:
                    for name, tokens in options.items():
                        bits = {b for b in tokens if b.lstrip('!') not in pullbits}
                        matched = True
                        for token in bits:
                            f, b = map(int, re.fullmatch(r'!?F(\d+)B(\d+)', token).groups())
                            if bool(tile.cram.bit(f, b)) == token.startswith('!'):
                                matched = False
                        if matched:
                            matches.append((len(bits), name))
                    best = max(size for size, _ in matches)
                    matches = sorted(name for size, name in matches if size == best)
                    if any(options[name] != requested for name in matches):
                        raise RuntimeError('diagnostic contains a nonalias candidate')
                if (pull == 'DOWN') != equivalent:
                    raise RuntimeError('expected independent-pull collision changed')
                report['cases'].append({'tile_type': kind, 'pio': pio, 'pull': pull,
                                        'requested': 'BIDIR_LVCMOS33', 'decoded': observed,
                                        'exact_alias': equivalent, 'diagnostic_candidates': matches,
                                        'database_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    report['expected_baseline_mismatches'] = sum(not c['exact_alias'] for c in report['cases'])
    report['fixture_gate_passed'] = True
    if args.source_reference:
        from check import check, coordinates
        bit, lpf_path, top_path = args.source_reference
        lpf, top = lpf_path.read_text(), top_path.read_text()
        chip = pytrellis.Bitstream.read_bit(str(bit)).deserialise_chip()
        source = check(chip, lpf, top, args.database)
        if not source['source_pattern_gate_passed'] or len(source['ports']) != 51:
            raise RuntimeError('reference source pattern gate failed')
        rejects = []
        for row in source['ports']:
            tile = chip.tiles[row['tile']]
            for category, pattern in [('receiver', row['receiver_pattern']), ('pull', row['pull_pattern'])]:
                for token in pattern:
                    f, b = coordinates(token)
                    original = bool(tile.cram.bit(f, b))
                    tile.cram.set_bit(f, b, not original)
                    result = check(chip, lpf, top, args.database)
                    tile.cram.set_bit(f, b, original)
                    if result['source_pattern_gate_passed']:
                        raise RuntimeError('mutated ' + category + ' accepted')
                    rejects.append({'port': row['port'], 'category': category, 'bit': token})
        wrong_top = re.sub(r'\binout(\s+(?:logic\s+|wire\s+)?(?:\[\d+:\d+\]\s*)?flash_dq\b)', r'output\1', top)
        if wrong_top == top:
            raise RuntimeError('direction fixture did not mutate')
        try:
            check(chip, lpf, wrong_top, args.database)
        except ValueError as exc:
            if str(exc) != 'unsupported or changed SC64 inout directions':
                raise
        else:
            raise RuntimeError('wrong direction accepted')
        report['source_tests'] = {'positive_ports': 51, 'bit_mutations_rejected': rejects,
                                  'wrong_direction_rejected': True}
        (out / 'source-reference.json').write_text(json.dumps(source, indent=2) + '\n')
    (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'cases'}, indent=2))


if __name__ == '__main__':
    main()
