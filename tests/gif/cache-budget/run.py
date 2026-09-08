"""Measure cache-size variants derived from the unchanged cached GIF baseline.

Only generated research copies change. All original and fault fixtures run for
every size; synthesis is required. Outputs must be new and outside tests.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def replace(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError(f"Baseline anchor changed: {old}")
    return text.replace(old, new)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--bits', type=int, choices=(7, 8, 9), required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent.parent
    output = args.output.resolve()
    if output.exists() or source.parent in output.parents:
        raise ValueError('Output must be new and outside tests')
    output.mkdir(parents=True)
    result = {'cache_entries': 1 << args.bits, 'status': 'running', 'hardware_qualified': False}

    def run(command, name, timeout=600):
        with (output / (name + '.log')).open('w') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=timeout)

    try:
        hashes = {}
        expected = {
            'gif_lzw_cached.sv': 'b2c0af64cfd5d39d69ffafa5b9822d82496120cbea27b34618486de2a0772443',
            'cached_dictionary.sv': '004fdf346e033e14d60bb9165562ec4d0ccf4dd482260193766d5443f8c588c4',
            'driver.cpp': 'bac4106e51a68f387281db5f759a75a14690a93c96c5fa86c3b4c254205d7b96',
        }
        for name, digest in expected.items():
            data = (source / 'cached' / name).read_bytes()
            hashes[name] = hashlib.sha256(data).hexdigest()
            if hashes[name] != digest:
                raise ValueError(f'Baseline hash changed: {name}')
        result['baseline_hashes'] = hashes
        core = (source / 'cached/gif_lzw_cached.sv').read_text()
        core = replace(core, 'module gif_lzw_cached (', 'module gif_lzw_cached #(parameter CACHE_BITS = 9) (')
        core = replace(core, 'cached_dictionary dictionary (', 'cached_dictionary #(.CACHE_BITS(CACHE_BITS)) dictionary (')
        cache = (source / 'cached/cached_dictionary.sv').read_text()
        cache = replace(cache, 'module cached_dictionary (', 'module cached_dictionary #(parameter CACHE_BITS = 9) (')
        cache = replace(cache, 'logic [23:0]', 'logic [32-CACHE_BITS:0]', 2)
        cache = replace(cache, '[0:511]', '[0:(1<<CACHE_BITS)-1]')
        cache = replace(cache, 'logic [8:0] clear_index', 'logic [CACHE_BITS-1:0] clear_index')
        cache = replace(cache, '[8:0]', '[CACHE_BITS-1:0]', 2)
        cache = replace(cache, 'clear_index == 511', 'clear_index == CACHE_BITS\'((1<<CACHE_BITS)-1)')
        cache = replace(cache, 'entry[23]', 'entry[32-CACHE_BITS]')
        cache = replace(cache, 'entry[22:20]', 'entry[31-CACHE_BITS:20]')
        cache = replace(cache, '[11:9]', '[11:CACHE_BITS]', 2)
        cache = replace(cache, "24'd0", "(33-CACHE_BITS)'(0)")
        (output / 'gif_lzw_cached.sv').write_text(core)
        (output / 'cached_dictionary.sv').write_text(cache)
        run(['python3', str(source / 'fixtures.py'), str(args.original.resolve()), str(output)], 'fixtures')
        run(['verilator', '--version'], 'verilator-version')
        run(['yosys', '-V'], 'yosys-version')
        run(['verilator', '--cc', '--exe', '--build', '-j', '2', '--top-module', 'gif_lzw_cached',
             f'-GCACHE_BITS={args.bits}', '--Mdir', str(output / 'obj'),
             str(output / 'gif_lzw_cached.sv'), str(output / 'cached_dictionary.sv'),
             str(source / 'cached/driver.cpp')], 'compile')
        run([str(output / 'obj/Vgif_lzw_cached'), str(output / 'fixtures.bin')], 'simulation', 900)
        script = (f'read_verilog -sv "{output}/gif_lzw_cached.sv" "{output}/cached_dictionary.sv"; '
                  f'chparam -set CACHE_BITS {args.bits} gif_lzw_cached; '
                  f'synth_lattice -family xo2 -top gif_lzw_cached; stat; write_json "{output}/mapped.json"')
        run(['yosys', '-Q', '-T', '-p', script], 'synthesis')
        cells = json.loads((output / 'mapped.json').read_text())['modules']['gif_lzw_cached']['cells']
        counts = {}
        for cell in cells.values():
            counts[cell['type']] = counts.get(cell['type'], 0) + 1
        result['mapped_cells'] = counts
        result['simulation'] = (output / 'simulation.log').read_text().splitlines()[-1]
        result['generated_hashes'] = {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                                      for name in ('gif_lzw_cached.sv', 'cached_dictionary.sv')}
        result['status'] = 'pass'
    except Exception as exc:
        result['status'] = 'failed'
        result['error'] = str(exc)
        raise
    finally:
        (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
