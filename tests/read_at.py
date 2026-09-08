#!/usr/bin/env python3
"""Test current MCU READ_AT against current legacy I/s with real source constants.

Generated owner extracts and artifacts stay in the explicit output directory.
The protocol model supplies only lock, DMA, command, LED and ADC boundaries;
production CFG translation/dispatch/diagnostics and SD reads execute unchanged.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shlex
import subprocess

TESTS = Path(__file__).resolve().parent

def function(source, name):
    matches = list(re.finditer(r'^(?:static\s+)?\w+\s+' + re.escape(name) + r'\s*\([^;]*?\)\s*\{', source, re.M))
    if len(matches) != 1:
        raise RuntimeError('Missing or duplicate actual function: ' + name)
    start = matches[0].start()
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'

def declaration(source, kind, name):
    values = [m[0] for m in re.finditer(r'typedef\s+' + kind + r'\s*\{[^}]*\}\s*\w+\s*;', source, re.S)
              if re.search(r'\}\s*' + name + r'\s*;$', m[0])]
    if len(values) != 1:
        raise RuntimeError('Missing or duplicate actual declaration: ' + name)
    return values[0] + '\n'

def macro(source, name):
    values = re.findall(r'^#define[ \t]+' + name + r'[ \t]+[^\n]+', source, re.M)
    if len(values) != 1:
        raise RuntimeError('Missing or duplicate actual macro: ' + name)
    return values[0] + '\n'

def section(source, first, last):
    if source.count(first) != 1 or source.count(last) != 1:
        raise RuntimeError('Missing or duplicate command boundary: ' + first)
    return source[source.index(first):source.index(last)]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=TESTS.parent)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.source.resolve()
    out = args.output.resolve()
    protected = [TESTS, root / 'tests', root / 'sw']
    if out == root or any(out == path or path in out.parents for path in protected):
        raise RuntimeError('Generated output must be outside production source and tests/')
    out.mkdir(parents=True, exist_ok=True)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    paths = ['sw/controller/src/cfg.c', 'sw/controller/src/sd.c',
             'sw/controller/src/sd.h', 'sw/bootloader/src/sc64.h']
    sources = {name: (root / name).read_text(encoding='utf-8') for name in paths}
    cfg, sd, header, n64 = (sources[name] for name in paths)
    types = ''.join(declaration(cfg, 'enum', name) for name in
                    ['cmd_id_t', 'diagnostic_id_t', 'translate_type_t', 'error_type_t', 'cfg_error_t'])
    types += ''.join(macro(cfg, name) for name in ['DATA_BUFFER_ADDRESS', 'DATA_BUFFER_SIZE'])
    types += ''.join(declaration(sd, 'enum', name) for name in ['rsp_type_t', 'dat_status_t'])
    types += ''.join(macro(sd, name) for name in ['TIMEOUT_DATA_MS', 'DAT_BLOCK_MAX_COUNT'])
    types += declaration(n64, 'struct', 'sc64_buffers_t') + macro(n64, 'SC64_BUFFERS_BASE')
    process = function(cfg, 'cfg_process')
    first = '        case CMD_ID_SD_SECTOR_SET:'
    read_at = '        case CMD_ID_SD_READ_AT:'
    read = '        case CMD_ID_SD_READ:'
    write = '        case CMD_ID_SD_WRITE:'
    selected = section(process, first, write)
    atomic = section(process, read_at, read)
    legacy = selected.replace(atomic, '')
    if selected.count(atomic) != 1:
        raise RuntimeError('READ_AT case extraction changed')
    diagnostic = process[process.index('        case CMD_ID_DIAGNOSTIC_GET:'):]
    prefix = function(cfg, 'cfg_translate_address') + function(cfg, 'cfg_read_diagnostic_data')
    def commands(cases, name):
        return 'static void ' + name + '(unsigned cmd) { switch (cmd) {\n' + cases + diagnostic
    owners = prefix + commands(legacy, 'legacy_command') + commands(selected, 'read_at_command')
    cursor = '            p.sd_card_sector = p.data[0];'
    if atomic.count(cursor) != 1:
        raise RuntimeError('Cursor negative mutation boundary changed')
    wrong_cursor = atomic.replace(cursor, '            (void)p.data[0];')
    bound = '            if (p.data[1] > DATA_BUFFER_SIZE / SD_SECTOR_SIZE && p.data[1] < 0x800000) {\n                return cfg_cmd_reply_error(ERROR_TYPE_SD_CARD, SD_ERROR_INVALID_ADDRESS);\n            }\n'
    if atomic.count(bound) != 1:
        raise RuntimeError('Bounds negative mutation boundary changed')
    variants = {
        'read-at-owner.inc': owners,
        'negative-cursor.inc': prefix + commands(legacy, 'legacy_command') + commands(selected.replace(atomic, wrong_cursor), 'read_at_command'),
        'negative-bound.inc': prefix + commands(legacy, 'legacy_command') + commands(selected.replace(atomic, atomic.replace(bound, '')), 'read_at_command'),
        'read-at-types.inc': types,
        'read-at-sd.inc': re.sub(r'\bp\.', 'sdstate.', function(sd, 'sd_read_sectors')),
        'sd.h': header,
        'read_at.c': (TESTS / 'read_at.c').read_text(encoding='utf-8'),
    }
    for name, text in variants.items():
        with (out / name).open('w', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
    hashes = {name: hashlib.sha256(text.encode('utf-8')).hexdigest() for name, text in sources.items()}
    hashes['tests/read_at.c'] = hashlib.sha256((TESTS / 'read_at.c').read_bytes()).hexdigest()
    hashes['tests/read_at.py'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (out / 'sources.json').write_text(json.dumps(hashes, indent=2) + '\n', encoding='utf-8')
    env = dict(os.environ, ASAN_OPTIONS='halt_on_error=1:detect_leaks=1', UBSAN_OPTIONS='halt_on_error=1')
    log = out / 'results.log'
    log.write_text('', encoding='utf-8')
    def command(argv, negative=None):
        result = subprocess.run(argv, cwd=out, env=env, universal_newlines=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=120)
        with log.open('a', encoding='utf-8') as stream:
            stream.write('$ ' + ' '.join(shlex.quote(arg) for arg in argv) + '\n' + result.stdout)
        if negative:
            if not result.returncode or negative not in result.stdout:
                raise RuntimeError('Missing specific expected failure: ' + negative + '\n' + result.stdout)
        elif result.returncode:
            raise RuntimeError(result.stdout)
        return result.stdout
    flags = ['-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
             '-fno-sanitize-recover=all', '-fno-omit-frame-pointer']
    for variant, extract, negative in [
        ('read-at', 'read-at-owner.inc', None),
        ('negative-cursor', 'negative-cursor.inc', 'Assertion `!memcmp(&a,&b,sizeof(a))'),
        ('negative-bound', 'negative-bound.inc', 'Assertion `status && !starts && !on && !off')]:
        command(shlex.split(os.environ.get('CC', 'cc')) + flags +
                ['-DPHOS_READ_AT_OWNER="' + extract + '"', 'read_at.c', '-o', variant])
        output = command([str(out / variant)], negative)
        if negative:
            print('PASS rejected ' + variant + ' at expected assertion')
        else:
            if 'PASS READ_AT MCU: 4224 legacy differential + 24 overflow cases' not in output:
                raise RuntimeError('Missing complete fixture result')
            print(output, end='')
    print('PASS current-source READ_AT MCU gate; no hardware tested')

if __name__ == '__main__':
    main()
