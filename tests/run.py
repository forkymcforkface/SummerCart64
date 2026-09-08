#!/usr/bin/env python3
"""Compile Linux host regression fixtures from the current SC64 source tree."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

BASELINE = '18041e25472075a166292d1195603bcefe9c9688'
TESTS = Path(__file__).resolve().parent


def function(text, name):
    match = re.search(r'^(?:static\s+)?\w+\s+' + re.escape(name) + r'\s*\([^;]*?\)\s*\{', text, re.M)
    if not match:
        raise RuntimeError('Missing actual-source function: ' + name)
    end = text.index('{', match.start()) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[match.start():end] + '\n'


def original_diagnostics(text, *warnings):
    directives = ['#pragma GCC diagnostic push']
    directives += ['#pragma GCC diagnostic warning "-W' + warning + '"' for warning in warnings]
    return '\n'.join(directives) + '\n' + text + '#pragma GCC diagnostic pop\n'


def rename(text, names):
    for old, new in names.items():
        text = re.sub(r'\b' + re.escape(old) + r'\b', new, text)
    return text


class Suite:
    def __init__(self, args, name):
        self.args = args
        self.out = args.output / name
        self.out.mkdir(parents=True, exist_ok=True)
        self.hashes = {}
        self.log = self.out / 'results.log'
        self.log.write_text('')

    def source(self, name, original=False):
        if original:
            text = subprocess.check_output(['git', '-c', 'safe.directory=' + str(self.args.source), '-C', str(self.args.source), 'show', BASELINE + ':' + name], text=True)
        else:
            text = (self.args.source / name).read_text()
        self.hashes[('baseline/' if original else 'candidate/') + name] = hashlib.sha256(text.encode()).hexdigest()
        return text

    def write(self, name, text):
        (self.out / name).write_text(text)

    def command(self, command):
        result = subprocess.run(command, cwd=self.out, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        with self.log.open('a') as log:
            log.write('$ ' + shlex.join(command) + '\n' + result.stdout)
        if result.returncode:
            print(result.stdout, file=sys.stderr)
            result.check_returncode()
        return result.stdout

    def test(self, name, extras=(), defines=()):
        shutil.copyfile(TESTS / (name + '.c'), self.out / (name + '.c'))
        flags = ['-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer']
        self.command(shlex.split(os.environ.get('CC', 'gcc')) + flags + list(defines) + [name + '.c'] + list(extras) + ['-o', name])
        output = self.command([str(self.out / name)])
        if 'PASS' not in output:
            raise RuntimeError('Missing fixture completion output: ' + name)
        print(output, end='')

    def finish(self):
        self.write('sources.json', json.dumps({'baseline': BASELINE, 'source_hashes': self.hashes}, indent=2) + '\n')


def cursor(args):
    suite = Suite(args, 'cursor')
    path = 'sw/bootloader/src/sc64.c'
    current = suite.source(path)
    original = suite.source(path, True)
    declarations = []
    for name in ['sector_known', 'sector_next']:
        match = re.search(r'^static\s+\w+\s+' + name + r'\s*(?:=[^;]+)?;', current, re.M)
        if not match:
            raise RuntimeError('Missing cursor state: ' + name)
        declarations.append(match[0])
    suite.write('cursor-state.inc', '\n'.join(declarations) + '\n')
    names = ['sc64_sd_card_init', 'sc64_sd_card_deinit', 'sc64_sd_card_get_status', 'sc64_sd_card_get_info', 'sc64_sd_set_byte_swap', 'sc64_sd_sector_set', 'sc64_sd_read_sectors', 'sc64_sd_write_sectors']
    text = ''
    for prefix, source in [('baseline', original), ('candidate', current)]:
        mapping = {n: prefix + '_' + n for n in names}
        text += ''.join(rename(function(source, n), mapping) for n in names)
    # Dispatch occurs in the harness; neither implementation receives a test branch.
    for n in names:
        if n == 'sc64_sd_sector_set':
            continue
        signature = function(current, n).split('{')[0].strip()
        parameters = signature[signature.index('(') + 1:signature.rindex(')')].strip()
        arguments = [] if parameters == 'void' else [re.findall(r'\w+', p)[-1] for p in parameters.split(',')]
        call = '(' + ', '.join(arguments) + ')'
        text += signature + ' { return sc64_sector_cache_test ? candidate_' + n + call + ' : baseline_' + n + call + '; }\n'
    suite.write('snapshot.inc', original_diagnostics(text, 'pointer-to-int-cast'))
    suite.test('cursor')
    suite.finish()


def bounded(args):
    suite = Suite(args, 'bounded')
    prefix = 'sw/bootloader/src/'
    helper = function(suite.source(prefix + 'menu.c'), 'menu_read')
    for name in ['ff.c', 'ff.h', 'ffconf.h', 'ffunicode.c', 'diskio.h']:
        suite.write(name, suite.source(prefix + 'fatfs/' + name))
    config = (suite.out / 'ffconf.h').read_text()
    required = {'FFCONF_DEF':80286, 'FF_USE_FASTSEEK':1, 'FF_FS_READONLY':0, 'FF_USE_MKFS':1, 'FF_LBA64':0, 'FF_FS_EXFAT':1, 'FF_MIN_SS':512, 'FF_MAX_SS':512}
    for key, value in required.items():
        match = re.search(r'^#define\s+' + key + r'\s+(\d+)', config, re.M)
        if not match or int(match[1]) != value:
            raise RuntimeError('Required actual config ' + key + '=' + str(value))
    suite.write('menu_snapshot.inc', original_diagnostics(helper, 'int-to-pointer-cast'))
    suite.test('bounded', ['ff.c', 'ffunicode.c'])
    suite.finish()


def mcu(args):
    suite = Suite(args, 'mcu')
    prefix = 'sw/controller/src/'
    baseline = {n: suite.source(prefix + n, True) for n in ['fpga.c', 'sd.c', 'fpga.h', 'sd.h']}
    candidate = {n: suite.source(prefix + n) for n in baseline}
    for header in ['fpga.h', 'sd.h']:
        pattern = r'typedef\s+enum\s*\{.*?\}\s*\w+\s*;'
        if re.findall(pattern, baseline[header], re.S) != re.findall(pattern, candidate[header], re.S):
            raise RuntimeError('Enum definitions changed: ' + header)
        suite.write(header, candidate[header])
    grouping = bool(re.search(r'\bvoid\s+fpga_reg_set_words\s*\(', candidate['fpga.c']))
    if args.mcu == 'combined' and not grouping:
        raise RuntimeError('Combined fixture required but fpga_reg_set_words is absent')
    def types(source):
        value = source['sd.c'].split('static struct process p;')[0]
        if value == source['sd.c']:
            raise RuntimeError('Missing SD process declaration')
        return re.sub(r'^#include.*\n', '', value, flags=re.M)
    if types(baseline) != types(candidate):
        raise RuntimeError('SD declarations changed; fixture requires adaptation')
    suite.write('types.inc', types(candidate) + 'static struct process p;\n')
    for label, source in [('baseline', baseline), ('candidate', candidate)]:
        mapping = {'fpga_reg_get':label + '_get', 'fpga_reg_set':label + '_set'}
        text = ''.join(rename(function(source['fpga.c'], n), mapping) for n in mapping)
        suite.write(label + '.inc', original_diagnostics(text, 'incompatible-pointer-types') if label == 'baseline' else text)
    duplex = args.spi == 'duplex'
    if duplex:
        helper = suite.source(prefix + 'hw.c')
        function(helper, 'hw_spi_transfer')
        if 'hw_spi_transfer' not in function(candidate['fpga.c'], 'fpga_reg_get'):
            raise RuntimeError('Full-duplex register-read implementation is required')
    defines = ['-DEXPECT_WRITE_TX=1', '-DEXPECT_READ_TX=1', '-DEXPECT_DUPLEX=' + str(int(duplex))]
    suite.test('spi', defines=defines)
    if grouping:
        text = (suite.out / 'baseline.inc').read_text() + (suite.out / 'candidate.inc').read_text()
        text += function(candidate['fpga.c'], 'fpga_reg_set_words')
        for label, source in [('baseline', baseline), ('candidate', candidate)]:
            for n in ['sd_cmd', 'sd_dma_start_write', 'sd_dma_start_read']:
                mapping = {'fpga_reg_get':label + '_get', 'fpga_reg_set':label + '_set', n:label + '_' + n}
                text += rename(function(source['sd.c'], n), mapping)
        suite.write('functions.inc', text)
        suite.test('groups', defines=defines)
    suite.finish()


def formatter(args):
    subprocess.run([sys.executable, str(TESTS / 'formatter.py'),
                    '--source', str(args.source / 'sw/bootloader'),
                    '--output', str(args.output / 'formatter')],
                   check=True, timeout=120)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=TESTS.parent, help='SC64 checkout; defaults to parent of tests/')
    parser.add_argument('--suite', choices=['all', 'cursor', 'bounded', 'mcu', 'formatter'], default='all')
    parser.add_argument('--mcu', choices=['byte', 'combined'], default='combined')
    parser.add_argument('--spi', choices=['split', 'duplex'], default='duplex', help='Expected candidate register-read transport; split tests historical batching')
    args = parser.parse_args()
    args.source = args.source.resolve()
    args.output = args.output.resolve()
    if args.output == TESTS or TESTS in args.output.parents:
        raise RuntimeError('Generated output must be outside tests/')
    for name, operation in [('cursor', cursor), ('bounded', bounded), ('mcu', mcu), ('formatter', formatter)]:
        if args.suite in ['all', name]:
            operation(args)
    print('PASS selected SC64 host regression suites; no hardware tested')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('FAIL SC64 regression: ' + str(exc), file=sys.stderr)
        sys.exit(1)
