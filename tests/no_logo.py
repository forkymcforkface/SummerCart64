#!/usr/bin/env python3
"""Verify logo removal preserves actual diagnostic clear/text rendering.

Compile current and v2.20.2 drawing functions and font independently with
ASan/UBSan, then compare full framebuffers for plain and diagnostic text cases.
This host model does not exercise VI hardware or exception entry.
"""
import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess
import zlib

BASELINE = '18041e25472075a166292d1195603bcefe9c9688'
HARNESS = r"""
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "font.h"
typedef uint32_t io32_t;
static uint32_t display_framebuffer[SCREEN_WIDTH * SCREEN_HEIGHT];
static int char_x, char_y;
static void cpu_io_write(io32_t *p, uint32_t v) {
    assert(p >= display_framebuffer);
    assert(p < display_framebuffer + SCREEN_WIDTH * SCREEN_HEIGHT);
    *p = v;
}
"""
MAIN = r"""
int main(int argc, char **argv) {
    assert(argc == 2);
    memset(display_framebuffer, 0xA5, sizeof(display_framebuffer));
    display_clear_background();
    char_x = BORDER_WIDTH;
    char_y = BORDER_HEIGHT;
    if (strcmp(argv[1], "text") == 0)
        display_draw_string("SC64 diagnostic text\n");
    else if (strcmp(argv[1], "errors") == 0)
        display_draw_string("[ Runtime error ]\nMissing menu\n"
                            "[ Watchdog timeout ]\n"
                            "[ Unhandled exception ] @ 0x80000000\n");
    else
        assert(strcmp(argv[1], "plain") == 0);
    for (unsigned i = 0; i < SCREEN_WIDTH * SCREEN_HEIGHT; i++) {
        uint32_t p = display_framebuffer[i];
        for (int shift = 24; shift >= 0; shift -= 8)
            assert(fputc((p >> shift) & 255, stdout) != EOF);
    }
    return 0;
}
"""


def run(command):
    return subprocess.run(command, check=True, capture_output=True, timeout=120).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True,
                        help='bootloader directory under test')
    parser.add_argument('--baseline', type=Path, required=True,
                        help='SC64 Git checkout containing v2.20.2')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if output == source or source in output.parents:
        parser.error('--output must be outside --source')
    output.mkdir(parents=True, exist_ok=True)
    current = (source / 'src/display.c').read_text()
    assert 'display_decompress_background' not in current
    assert 'void display_init (void)' in current
    init = current[current.index('void display_init (void)'):]
    assert 'display_clear_background();' in init
    for path in (source / 'src').glob('*.c'):
        assert 'assets_sc64_logo_' not in path.read_text(), path
    assert 'sc64_logo_640_240_dimmed.png' not in (source / 'Makefile').read_text()
    executables = []
    for name in ['baseline', 'current']:
        folder = output / name
        folder.mkdir(exist_ok=True)
        def read(relative):
            if name == 'current':
                return (source / relative).read_text()
            return run(['git', '-C', str(args.baseline), 'show',
                        BASELINE + ':sw/bootloader/' + relative]).decode()
        text = read('src/display.c')
        defines = '\n'.join(line for line in text.splitlines()
                            if re.match(r'#define (SCREEN_|BORDER_|BACKGROUND_COLOR|TEXT_COLOR|LINE_SPACING)', line))
        start = text.index('static void display_clear_background')
        end = text.index('void display_init', start)
        (folder / 'test.c').write_text(defines + '\n' + HARNESS + text[start:end] + MAIN)
        (folder / 'font.c').write_text(read('src/font.c'))
        (folder / 'font.h').write_text(read('src/font.h'))
        executable = folder / 'test'
        run(shlex.split(os.environ.get('CC', 'gcc')) +
            ['-std=c11', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
             str(folder / 'test.c'), str(folder / 'font.c'), '-o', str(executable)])
        executables.append(executable)
    for case in ['plain', 'text', 'errors']:
        expected, actual = [run([str(executable), case]) for executable in executables]
        assert len(actual) == 640 * 240 * 4 and actual == expected, case
        assert (any(actual) if case != 'plain' else not any(actual)), case
        (output / (case + '.rgba')).write_bytes(actual)
        print('PASS', case, 'crc32=%08X' % zlib.crc32(actual))
    print('PASS no-logo linking inputs and exact baseline diagnostic rendering')


if __name__ == '__main__':
    main()
