#!/usr/bin/env python3
"""Inventory SC64 LPF intent; never translate or qualify missing backend semantics.

The deliberately narrow grammar matches the checked-in SC64 project. Unknown
syntax fails closed. JSON preserves every statement and exact port settings;
source parsing is not a substitute for post-route pin/timing verification.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re


def tokens(text):
    pattern = r'(?P<comment>(?s:/\*.*?\*/)|//[^\n]*|\#[^\n]*)|"(?P<quoted>[^"\n]*)"|(?P<word>[^\s";]+)|(?P<semi>;)'
    result, position = [], 0
    for match in re.finditer(pattern, text):
        if text[position:match.start()].strip():
            raise ValueError("unrecognized LPF token")
        position = match.end()
        if match['comment']:
            continue
        result.append(match['quoted'] if match['quoted'] is not None else match['word'] or ";")
    if text[position:].strip():
        raise ValueError("unterminated LPF token")
    return result


def top_inventory(text):
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    match = re.search(r'\bmodule\s+top\s*\((.*?)\)\s*;', text, re.S)
    if not match:
        raise ValueError("expected nonparameterized ANSI module top")
    ports = {}
    for declaration in match[1].split(','):
        item = re.fullmatch(r'\s*(input|output|inout)\s+(?:logic\s+|wire\s+)?(?:\[(\d+):(\d+)\]\s*)?(\w+)\s*', declaration)
        if not item:
            raise ValueError("unsupported top declaration: " + declaration.strip())
        names = [item[4]] if item[2] is None else [f'{item[4]}[{n}]' for n in range(min(int(item[2]), int(item[3])), max(int(item[2]), int(item[3])) + 1)]
        for name in names:
            if name in ports:
                raise ValueError("duplicate port " + name)
            ports[name] = item[1]
    nets = set(ports) | set(re.findall(r'\b(?:logic|wire)\s+(\w+)\s*;', text))
    return ports, nets


def audit(lpf, top):
    ports, nets = top_inventory(top)
    stream = tokens(lpf)
    if stream and stream[-1] != ';':
        raise ValueError("unterminated LPF statement")
    statements, current = [], []
    for token in stream:
        if token == ';':
            if not current:
                raise ValueError("empty LPF statement")
            statements.append(current)
            current = []
        else:
            current.append(token)
    errors, records, groups, clocks, aliases = [], [], {}, {}, {}
    pinmap, electrical, banks, sysconfig = {}, {}, {}, {}
    explicit_iobuf = set()
    refs = []

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def assignments(values):
        result = {}
        require(bool(values), 'missing attributes')
        for value in values:
            require(bool(re.fullmatch(r'\w+=[\w.]+', value)), 'invalid attribute ' + value)
            key, setting = value.split('=')
            require(key not in result, 'duplicate attribute ' + key)
            result[key] = setting
        return result

    for index, words in enumerate(statements):
        verb = words[0]
        record = {'index': index + 1, 'tokens': words, 'backend_status': 'unresolved'}
        records.append(record)
        try:
            if verb == 'LOCATE':
                require(len(words) == 5 and words[1] == 'COMP' and words[3] == 'SITE', 'LOCATE grammar')
                name, site = words[2], words[4]
                require(name in ports, 'unknown LOCATE port ' + name)
                require(site.isdecimal() and 1 <= int(site) <= 144, 'invalid TG144 site')
                require(name not in pinmap and int(site) not in map(int, pinmap.values()), 'duplicate port/site')
                pinmap[name] = site
                record['backend_status'] = 'implemented_parse_requires_postroute_verification'
            elif verb == 'IOBUF':
                allports = words[1] == 'ALLPORTS'
                require(allports or (len(words) >= 4 and words[1] == 'PORT' and words[2] in ports), 'IOBUF target')
                attrs = assignments(words[2:] if allports else words[3:])
                require(set(attrs) <= {'IO_TYPE', 'PULLMODE', 'DRIVE', 'SLEWRATE', 'OPENDRAIN'}, 'unreviewed IOBUF attribute')
                target = '*' if allports else words[2]
                require(target not in explicit_iobuf, 'duplicate IOBUF target')
                explicit_iobuf.add(target)
                for name in ports if allports else [words[2]]:
                    electrical.setdefault(name, {}).update(attrs)
                record['backend_status'] = 'parser_rejects_ALLPORTS' if allports else 'implemented_parse_requires_bit_verification'
            elif verb == 'DEFINE':
                require(len(words) >= 5 and words[1:3] == ['PORT', 'GROUP'], 'group grammar')
                require(words[3] not in groups, 'duplicate group')
                require(len(set(words[4:])) == len(words[4:]) and all(n in ports for n in words[4:]), 'invalid group members')
                groups[words[3]] = words[4:]
                record['backend_status'] = 'silently_ignored_by_pinned_parser'
            elif verb == 'FREQUENCY':
                require(len(words) == 5 and words[1] in {'NET', 'PORT'} and words[4] == 'MHz', 'frequency grammar')
                require(float(words[3]) > 0 and words[2] in (ports if words[1] == 'PORT' else nets), 'unknown clock or invalid frequency')
                require(words[2] not in clocks, 'duplicate clock')
                clocks[words[2]] = words[3]
                record['backend_status'] = 'implemented_parse_requires_clock_resolution'
            elif verb == 'RVL_ALIAS':
                require(len(words) == 3 and words[1] in nets and words[2] in nets, 'unknown alias net')
                require(words[1] not in aliases, 'duplicate alias')
                aliases[words[1]] = words[2]
                record['backend_status'] = 'silently_ignored_by_pinned_parser'
            elif verb == 'BANK':
                require(len(words) == 5 and words[2] == 'VCCIO' and words[4] == 'V' and words[1] in map(str, range(6)), 'bank grammar')
                require(words[1] not in banks and words[3] == '3.3', 'unreviewed or duplicate bank voltage')
                banks[words[1]] = words[3]
                record['backend_status'] = 'silently_ignored_by_pinned_parser'
            elif verb == 'VOLTAGE':
                require(len(words) == 3 and words[1:] == ['3.300', 'V'], 'unreviewed voltage')
                record['backend_status'] = 'silently_ignored_by_pinned_parser'
            elif verb == 'SYSCONFIG':
                attrs = assignments(words[1:])
                require(not set(attrs) & set(sysconfig), 'duplicate SYSCONFIG')
                require(set(attrs) <= {'SDM_PORT', 'I2C_PORT'}, 'unreviewed SYSCONFIG key')
                sysconfig.update(attrs)
                record['backend_status'] = 'parser_rejects_keys_emitter_support_requires_verification'
            elif verb == 'BLOCK':
                require(words[1:] in [['ASYNCPATHS'], ['RESETPATHS'], ['JTAGPATHS']] or (len(words) == 5 and words[1] == 'PATH' and words[2] in {'FROM', 'TO'} and words[3] == 'PORT' and words[4] in ports), 'BLOCK grammar/target')
                record['backend_status'] = 'exception_semantics_unverified_or_parser_warning'
            elif verb in {'INPUT_SETUP', 'CLOCK_TO_OUT'}:
                require(len(words) == 14 and words[1] == 'GROUP', 'timing grammar')
                if verb == 'INPUT_SETUP':
                    require(words[3] == 'INPUT_DELAY' and words[5:7] == ['ns', 'HOLD'] and words[8:10] == ['ns', 'CLKNET'] and words[11] == 'CLK_OFFSET', 'input timing grammar')
                    require(words[13] == 'X', 'input offset unit')
                    float(words[12])
                else:
                    require(words[3] == 'OUTPUT_DELAY' and words[5:7] == ['ns', 'MIN'] and words[8:10] == ['ns', 'CLKNET'] and words[11:13] == ['CLKOUT', 'PORT'], 'output timing grammar')
                    require(ports.get(words[13]) == 'output', 'unknown output clock port')
                float(words[4])
                float(words[7])
                refs.append((index + 1, words[2], words[10]))
                record['backend_status'] = 'silently_ignored_by_pinned_parser'
            else:
                raise ValueError('unknown verb ' + verb)
        except (ValueError, IndexError) as exc:
            errors.append(f'statement {index + 1}: {exc}')
    for index, group, clock in refs:
        if group not in groups or clock not in clocks:
            errors.append(f'statement {index}: unresolved timing group/clock')
    if set(banks) != set(map(str, range(6))):
        errors.append('missing bank voltage declaration')
    if sysconfig != {'SDM_PORT': 'DISABLE', 'I2C_PORT': 'ENABLE'}:
        errors.append('missing or changed SC64 configuration-port settings')
    if clocks.get('clk') != '100.000000':
        errors.append('missing or changed SC64 core clock')
    if len(refs) != 3:
        errors.append('expected three SC64 SDRAM timing statements')
    for name in ports:
        if name not in pinmap:
            errors.append('missing LOCATE ' + name)
        if 'IO_TYPE' not in electrical.get(name, {}):
            errors.append('missing IO_TYPE ' + name)
        if name not in explicit_iobuf or 'PULLMODE' not in electrical.get(name, {}):
            errors.append('missing explicit SC64 electrical declaration ' + name)
    return {'inventory_valid': not errors, 'qualified': False, 'errors': errors,
            'qualification_blockers': ['Backend timing/configuration/electrical equivalence is unresolved; inventory is not implementation.'],
            'statements': records, 'ports': {n: {'direction': ports[n], 'site': pinmap.get(n), 'electrical': electrical.get(n, {})} for n in ports},
            'groups': groups, 'clocks_mhz': clocks, 'aliases': aliases, 'banks_v': banks, 'sysconfig': sysconfig}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lpf', type=Path)
    parser.add_argument('top', type=Path)
    args = parser.parse_args()
    try:
        report = audit(args.lpf.read_text(), args.top.read_text())
        report['sha256'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.lpf, args.top)}
    except (ValueError, OSError) as exc:
        report = {'inventory_valid': False, 'qualified': False, 'errors': [str(exc)]}
    print(json.dumps(report, indent=2))
    return 2 if not report['inventory_valid'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
