"""Test a512-byte local phrase stack with full-depth external spill.

The input is a passed cache-budget result directory. All generated derivatives
remain in a new output directory; no baseline files or production RTL change.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

from spill_generate import generate
from spill_driver import generate as driver_generate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cache_result', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent.parent
    prior = args.cache_result.resolve()
    output = args.output.resolve()
    if output.exists() or source.parent in output.parents:
        raise ValueError('Output must be new and outside tests')
    previous = json.loads((prior / 'result.json').read_text())
    if previous['status'] != 'pass' or previous['cache_entries'] != 512:
        raise ValueError('Requires a passed512-entry paired baseline')
    for name, digest in previous['generated_hashes'].items():
        if hashlib.sha256((prior / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Input RTL changed')
    output.mkdir(parents=True)
    result = {'status': 'running', 'hardware_qualified': False, 'local_stack_bytes': 512, 'maximum_stack_bytes': 4096}
    def run(command, name, timeout=900):
        with (output / (name + '.log')).open('w') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=timeout)
    try:
        generate(prior, output)
        tree = ast.parse((source / 'fixtures.py').read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'pack')
        scope = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<baseline pack>', 'exec'), scope)
        pack = scope['pack']
        sys.path.insert(0, str(source))
        from gif_reference import decode
        vectors = []
        for depth in (512, 513, 4091):
            raw = pack([4, 0] + list(range(6, depth+5)) + [5], 2)
            expected = bytes(depth*(depth+1)//2)
            indices, _ = decode(raw, 2, len(expected))
            if bytes(indices) != expected:
                raise ValueError('Independent long-phrase reference mismatch')
            vectors.append(struct.pack('<IIIII', 2, len(expected), len(raw), len(expected), 0) + raw + expected)
            if depth == 513:
                fault_raw = raw
        fixtures = (prior / 'fixtures.bin').read_bytes()
        count, originals = struct.unpack_from('<II', fixtures)
        (output / 'fixtures.bin').write_bytes(struct.pack('<II', count+len(vectors), originals) + fixtures[8:] + b''.join(vectors))
        driver_generate(source / 'cached/driver.cpp', output, fault_raw)
        run(['verilator', '--cc', '--exe', '--build', '-j', '2', '--top-module', 'gif_lzw_cached',
             '--Mdir', str(output/'obj'), str(output/'gif_lzw_cached.sv'), str(output/'cached_dictionary.sv'), str(output/'driver.cpp')], 'compile')
        run([str(output/'obj/Vgif_lzw_cached'), str(output/'fixtures.bin')], 'simulation', 1800)
        script = (f'read_verilog -sv "{output}/gif_lzw_cached.sv" "{output}/cached_dictionary.sv"; '
                  f'synth_lattice -family xo2 -top gif_lzw_cached; stat; write_json "{output}/mapped.json"')
        run(['yosys', '-Q', '-T', '-p', script], 'synthesis')
        cells = json.loads((output/'mapped.json').read_text())['modules']['gif_lzw_cached']['cells']
        counts = {}
        for cell in cells.values():
            counts[cell['type']] = counts.get(cell['type'], 0)+1
        digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        result.update(status='pass', mapped_cells=counts,
                      simulation=(output/'simulation.log').read_text().splitlines()[-2:],
                      input_result_sha256=digest(prior/'result.json'),
                      input_fixture_sha256=digest(prior/'fixtures.bin'),
                      source_hashes={str(path.relative_to(source)): digest(path) for path in
                                     [source/'fixtures.py', source/'gif_reference.py', source/'cached/driver.cpp',
                                      *sorted(Path(__file__).parent.glob('*.py'))]},
                      output_hashes={name: digest(output/name) for name in
                                     ['gif_lzw_cached.sv', 'cached_dictionary.sv', 'driver.cpp', 'fixtures.bin', 'mapped.json']},
                      tool_versions={tool: subprocess.check_output([tool, flag], text=True).strip()
                                     for tool, flag in [('verilator', '--version'), ('yosys', '-V')]},
                      long_phrase_depths=[512,513,4091])
    except Exception as exc:
        result.update(status='failed', error=str(exc))
        raise
    finally:
        (output/'result.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
