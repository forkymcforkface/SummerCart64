"""Join a bounded ldbanno RAM wrapper dialect to SDF without importing timing.

Only the observed synchronous, unregistered DP/PDP modes are accepted. The
report retains signed transition triples and explicit wrapper-to-primitive
pin transformations; no SPD corner or physical-site equivalence is inferred.
"""
import argparse
import collections
import hashlib
import json
import pathlib
import re


def require(ok, message):
    if not ok:
        raise ValueError(message)


def modules(text):
    pairs = re.findall(r'\bmodule\s+(\w+)\s*\((.*?)\bendmodule', text, re.S)
    require(len(dict(pairs)) == len(pairs), 'duplicate module')
    return dict(pairs)


def shape(body):
    paths = re.findall(r'\((\w+)\s*=>\s*(\w+)\)\s*=', body)
    checks = re.findall(r'\$setuphold\s*\((posedge|negedge) (\w+), (\w+),', body)
    widths = re.findall(r'\$width\s*\((posedge|negedge) (\w+),', body)
    require(len(paths) == body.count('=>'), 'unrecognized specify path')
    require(len(checks) == body.count('$setuphold'), 'unrecognized specify check')
    require(len(widths) == body.count('$width'), 'unrecognized specify width')
    return paths, checks, widths


def audit(netlist, sdf, inventory_unmatched=False):
    mods = modules(netlist)
    primitive = {}
    for name, body in mods.items():
        found = re.findall(r'\b(DP8KC|PDPW8KC)\s+INST10\s*\(', body)
        if not found:
            continue
        require(len(found) == 1, 'ambiguous primitive')
        params = dict(re.findall(r'defparam INST10\.(\w+)\s*=\s*([^;]+);', body))
        mode = {k: v.strip('"') for k, v in params.items()
                if not k.startswith('INITVAL_')}
        require(mode.get('RESETMODE') == 'SYNC', 'unknown reset mode')
        keys = ['REGMODE_A', 'REGMODE_B'] if found[0] == 'DP8KC' else ['REGMODE']
        require(all(mode.get(k) == 'NOREG' for k in keys), 'unknown register mode')
        if found[0] == 'DP8KC':
            require(all(mode.get('WRITEMODE_' + p) == 'NORMAL' for p in 'AB'),
                    'unknown write mode')
            require(mode.get('DATA_WIDTH_A') == mode.get('DATA_WIDTH_B')
                    and mode.get('DATA_WIDTH_A') in ('2', '9'), 'unknown DP width')
        else:
            require(mode.get('DATA_WIDTH_R') == mode.get('DATA_WIDTH_W') == '18',
                    'unknown PDP width')
        primitive[name] = (found[0], mode)
    wrappers = {}
    for name, body in mods.items():
        children = [(typ, args) for typ, args in re.findall(
            r'\b(\w+)\s+\\\S+\s*\((.*?)\);', body, re.S) if typ in primitive]
        if not children:
            continue
        require(len(children) == 1, 'ambiguous wrapper')
        typ, args = children[0]
        pins = re.findall(r'\.(\w+)\((\w*)\)', args)
        require(len(pins) == args.count('.'), 'unknown connection syntax')
        inverse = dict((out, inp) for inp, out in re.findall(
            r'inverter\s+\w+\(\s*\.I\((\w+)\),\s*\.Z\((\w+)\)\)', body))
        mapping = collections.defaultdict(list)
        for pin, signal in pins:
            inverted = signal in inverse
            signal = inverse.get(signal, signal)
            if signal.endswith('_dly'):
                signal = signal[:-4]
            if signal and signal not in ('GNDI', 'VCCI'):
                mapping[signal].append({'pin': pin, 'inverted': inverted})
        wrappers[name] = (primitive[typ], mapping, shape(body))
    require(len(wrappers) == 26, 'expected 26 RAM wrappers')
    require(re.search(r'\(TIMESCALE\s+1\s*ps\)', sdf), 'unexpected timescale')
    records = []
    seen = set()
    for cell in sdf.split('(CELL\n')[1:]:
        match = re.search(r'\(CELLTYPE "([^"]+)"\)', cell)
        require(match is not None, 'missing cell type')
        name = match[1]
        if name not in wrappers:
            require(not re.search(r'pmi_ram|lm32_monitor_ram', name), 'unmatched RAM cell')
            continue
        require(name not in seen, 'duplicate RAM SDF cell')
        seen.add(name)
        inst = re.search(r'\(INSTANCE ([^\s)]+)\)', cell)
        require(inst is not None, 'missing instance')
        instance = re.sub(r'\\(.)', r'\1', inst[1])
        require(re.search(r'\b' + re.escape(name) + r'\s+\\' + re.escape(instance)
                          + r'\s+\(', netlist), 'unmatched instance path')
        paths = re.findall(r'\(IOPATH (\w+) (\w+) \(([-\d:]+)\)\(([-\d:]+)\)\)', cell)
        checks = re.findall(r'\(SETUPHOLD (\w+) \((posedge|negedge) (\w+)\) '
                            r'\(([-\d:]+)\)\(([-\d:]+)\)\)', cell)
        widths = re.findall(r'\(WIDTH \((posedge|negedge) (\w+)\) \(([-\d:]+)\)\)', cell)
        require(len(paths) == cell.count('(IOPATH'), 'unknown SDF path')
        require(len(checks) == cell.count('(SETUPHOLD'), 'unknown SDF setuphold')
        require(len(widths) == cell.count('(WIDTH'), 'unknown SDF width')
        require(not re.search(r'\((?:COND|RECOVERY|REMOVAL|HOLD|SETUP|PERIOD)\b', cell),
                'unsupported SDF check')
        mode, mapping, expected = wrappers[name]
        actual = ([p[:2] for p in paths], [(p[1], p[2], p[0]) for p in checks],
                  [p[:2] for p in widths])
        require(all(collections.Counter(a) == collections.Counter(b)
                    for a, b in zip(actual, expected)), 'SDF/specify coverage mismatch')
        unresolved = []
        for pin in {p for a in actual[0] for p in a} | {p[0] for p in checks} | {
                p[2] for p in checks} | {p[1] for p in widths}:
            if not mapping[pin] and mode[0] == 'PDPW8KC' and pin == 'RSTA':
                require(inventory_unmatched, 'unmatched PDP wrapper-only RSTA')
                unresolved.append(pin)
            else:
                require(len(mapping[pin]) == 1,
                        'unmatched/ambiguous primitive pin ' + name + ':' + pin)
        for values in ([row[-2:] for row in paths] + [row[-2:] for row in checks]
                       + [row[-1:] for row in widths]):
            for value in values:
                require(re.fullmatch(r'-?\d+:-?\d+:-?\d+', value), 'invalid triple')
        records.append({'cell': name, 'instance': instance, 'primitive': mode[0],
                        'mode': mode[1], 'pin_mapping': dict(mapping),
                        'unresolved_wrapper_pins': unresolved,
                        'iopath': paths, 'setuphold': checks, 'width': widths})
    require(seen == set(wrappers), 'missing RAM SDF cell')
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--netlist', type=pathlib.Path, required=True)
    parser.add_argument('--grade6', type=pathlib.Path, required=True)
    parser.add_argument('--minimum', type=pathlib.Path, required=True)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    parser.add_argument('--inventory-unmatched', action='store_true',
                        help='report known PDP RSTA orphan; never qualifies it')
    args = parser.parse_args()
    target = args.output.resolve()
    tests = pathlib.Path(__file__).resolve().parents[3]
    require(not target.is_relative_to(tests), 'output must be outside tests')
    require(not target.exists(), 'output must be fresh')
    net = args.netlist.read_text()
    reports = {label: audit(net, path.read_text(), args.inventory_unmatched) for label, path in
               [('grade6', args.grade6), ('minimum', args.minimum)]}
    require([r['cell'] for r in reports['grade6']] ==
            [r['cell'] for r in reports['minimum']], 'corner cell mismatch')
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (args.netlist, args.grade6, args.minimum)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        stream.write(json.dumps({'hardware_qualified': False, 'hashes': hashes,
                                'corners': reports}, indent=2)+'\n')
    print(json.dumps({k: {'cells': len(v), **{field: sum(len(r[field]) for r in v)
                     for field in ['iopath', 'setuphold', 'width']}} for k, v in reports.items()}))


if __name__ == '__main__':
    main()
