#!/usr/bin/env python3
"""Gate current bootloader diagnostic formats and actual formatter wrapper.

Host differential checks do not replace target-newlib ABI checks. --n64-probe
creates an isolated validation source tree, never flashes or modifies source.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess

TOKENS = re.compile(r'/\*.*?\*/|//[^\n]*|"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[A-Za-z_]\w*|[^\s]', re.S)
SPEC = re.compile(r'%[-+ #0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:hh|ll|[hljztL])?[diuoxXcsp%]')


def inventory(source):
    found = {}
    for path in sorted((source / 'src').glob('*.c')):
        tokens = [m.group() for m in TOKENS.finditer(path.read_text()) if not m.group().startswith(('/*', '//'))]
        for i, token in enumerate(tokens[:-1]):
            if token not in ('display_printf', 'error_display', 'FF_CHECK') or tokens[i+1] != '(':
                continue
            if i and tokens[i-1] in ('void', 'define'):
                continue
            args = [[]]; depth = 0
            for t in tokens[i+2:]:
                if t in ('(', '[', '{'): depth += 1
                if t in (')', ']', '}'):
                    if t == ')' and depth == 0: break
                    depth -= 1
                if t == ',' and depth == 0: args.append([])
                else: args[-1].append(t)
            index = 1 if token == 'FF_CHECK' else 0
            if len(args) <= index: continue
            pieces = [t for t in args[index] if t != '\\']
            extra = [t for t in pieces if not t.startswith('"')]
            if extra and not (path.name == 'menu.c' and token == 'error_display' and extra == ['message']):
                raise ValueError(f'{path}: diagnostic format must be a checked literal, got {pieces!r}')
            literals = [ast.literal_eval(t) for t in pieces if t.startswith('"')]
            if not literals: raise ValueError(f'{path}: missing literal diagnostic format')
            text = ''.join(literals); cursor = 0
            while True:
                cursor = text.find('%', cursor)
                if cursor < 0: break
                match = SPEC.match(text, cursor)
                if not match:
                    raise ValueError(f'{path}: unsupported diagnostic format at {text[cursor:cursor+20]!r}')
                fmt = match.group()
                tested = {'%016lX', '%016llX', '%01d', '%02X', '%02d', '%03d', '%04d', '%08X', '%08lX', '%2d', '%3d', '%c', '%d', '%ld', '%s'}
                if fmt not in tested: raise ValueError(f'{path}: new format {fmt!r} needs a differential fixture')
                found.setdefault(fmt, set()).add(path.name); cursor = match.end()
    if not found: raise ValueError('No diagnostic format calls found')
    return {k: sorted(v) for k, v in sorted(found.items())}


def function(text, name):
    match = re.search(r'void '+name+r'\s*\([^)]*\)\s*\{', text)
    if not match: raise ValueError('Missing function '+name)
    start = match.start(); depth = 1; pos = match.end()
    for m in TOKENS.finditer(text, pos):
        t = m.group()
        if t == '{': depth += 1
        if t == '}':
            depth -= 1
            if not depth: return text[start:m.end()]
    raise ValueError('Unclosed function '+name)


def generate_probe(source, output):
    if output.exists(): raise ValueError('Probe destination must not already exist')
    shutil.copytree(source, output, ignore=shutil.ignore_patterns('build', '.git', '__pycache__'))
    p = output/'src/display.c'; text=p.read_text(); body=function(text,'display_vprintf')
    call='npf_vsnprintf(line, sizeof(line), fmt, args);'
    if body.count(call)!=1: raise ValueError('Formatter wrapper changed; update diagnostic selector')
    updated=body.replace(call,'if (research_original_formatter) vsniprintf(line, sizeof(line), fmt, args);\n    else '+call)
    text='#include <stdio.h>\n'+text.replace(body,'bool research_original_formatter;\n'+updated)
    text+='\nvolatile uint32_t *research_display_pixels(void) { return UNCACHED(&display_framebuffer[0]); }\n'
    p.write_text(text)
    p=output/'src/init.c';text=p.read_text()
    if text.count('uint32_t __entropy;')!=1 or text.count('    sc64_error_t error;')!=1: raise ValueError('init instrumentation anchor changed')
    text=text.replace('uint32_t __entropy;','uint32_t __entropy;\nuint32_t bench_entry_ticks;').replace('    sc64_error_t error;','    bench_entry_ticks = c0_count();\n    sc64_error_t error;');p.write_text(text)
    p=output/'src/main.c';text=p.read_text();body=function(text,'main');updated=body
    for anchor in ('void main (void) {','    boot_params_t boot_params;','            menu_load();'):
        if updated.count(anchor)!=1: raise ValueError('main instrumentation anchor changed: '+anchor)
    updated=updated.replace('void main (void) {','void main (void) {\n    extern uint32_t bench_entry_ticks;\n    uint32_t load_start;\n    research_formatter_diagnostic();\n    bench_report("ipl3_to_entry_us",bench_us(bench_entry_ticks));')
    updated=updated.replace('    boot_params_t boot_params;','    sc64_boot_params.boot_mode = BOOT_MODE_MENU;\n    boot_params_t boot_params;').replace('            menu_load();','            load_start=c0_count();\n            menu_load();\n            bench_report("menu_load_us",bench_us(c0_count()-load_start));')
    fixtures=Path(__file__).parent
    text='#include <stdio.h>\n#include <string.h>\n'+text.replace(body,(fixtures/'formatter_report.inc').read_text()+'\n'+(fixtures/'formatter_n64.inc').read_text()+'\n'+updated);p.write_text(text)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);ap.add_argument('--n64-probe',type=Path);args=ap.parse_args()
    source=args.source.resolve();out=args.output.resolve()
    if out==source or source in out.parents: ap.error('Output must be outside source')
    if args.n64_probe and (args.n64_probe.resolve()==source or source in args.n64_probe.resolve().parents): ap.error('Probe must be outside source')
    result=inventory(source);out.mkdir(parents=True,exist_ok=True);(out/'formats.json').write_text(json.dumps(result,indent=2))
    vendor=source/'src/vendor/nanoprintf';provenance=json.loads((vendor/'provenance.json').read_text())
    if hashlib.sha256((vendor/'nanoprintf.h').read_bytes().replace(b'\r\n', b'\n')).hexdigest()!=provenance['sha256']: raise ValueError('Upstream formatter differs from provenance')
    display=(source/'src/display.c').read_text();wrapper=function(display,'display_vprintf')
    include='#define NANOPRINTF_IMPLEMENTATION\n#include "'+(vendor/'config.h').as_posix()+'"\nstatic char captured[256];\nstatic void display_draw_string(const char *s){strcpy(captured,s);}\n'+wrapper
    text=(Path(__file__).parent/'formatter_host.c').read_text().replace('/*SOURCE_FORMATTER*/',include);(out/'test.c').write_text(text)
    executable=out/'test';command=shlex.split(os.environ.get('CC','gcc'))+['-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(out/'test.c'),'-o',str(executable)]
    subprocess.run(command,check=True,timeout=120);subprocess.run([str(executable)],check=True,timeout=120)
    if args.n64_probe: generate_probe(source,args.n64_probe.resolve())
    print('PASS current-source diagnostic inventory, provenance, wrapper and host formatter; target ABI remains separate')

if __name__=='__main__':main()
