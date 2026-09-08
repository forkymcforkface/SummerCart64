"""Differential varied-byte spill and negative controls using a passed spill build.

The generated harness retains that build's memory latency and stream stalls,
but runs four independent synthetic frames instead of the original/cancel suite.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('passed_spill', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    prior, output = args.passed_spill.resolve(), args.output.resolve()
    source = Path(__file__).resolve().parent.parent
    if output.exists() or source.parent in output.parents:
        raise ValueError('Output must be new and outside tests')
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    passed = json.loads((prior/'result.json').read_text())
    if passed['status'] != 'pass':
        raise ValueError('Requires a passed spill build')
    for name, expected in passed['output_hashes'].items():
        if digest(prior/name) != expected:
            raise ValueError('Passed spill artifact changed: '+name)
    output.mkdir(parents=True)
    result = {'status': 'running', 'hardware_qualified': False}
    try:
        tree = ast.parse((source/'fixtures.py').read_text())
        pack_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'pack')
        scope = {}
        exec(compile(ast.Module(body=[pack_node], type_ignores=[]), '<reference pack>', 'exec'), scope)
        sys.path.insert(0, str(source))
        from gif_reference import decode
        vectors, vector_info = [], []
        for minimum, depth in [(2, 513), (2, 1025), (2, 2046), (8, 1920)]:
            clear = 1 << minimum
            codes, expected, phrase, seed = [clear, 0], bytearray([0]), bytes([0]), 0x12345678
            for index in range(1, depth):
                seed ^= (seed << 13) & 0xffffffff
                seed ^= seed >> 17
                seed ^= (seed << 5) & 0xffffffff
                literal = seed & (clear-1)
                if minimum == 8 and index <= 256:
                    literal = index-1
                phrase += bytes([literal])
                codes.extend([literal, clear+2+2*(index-1)])
                expected.extend(bytes([literal])+phrase)
            raw = scope['pack'](codes+[clear+1], minimum)
            indices, stats = decode(raw, minimum, len(expected))
            if bytes(indices) != expected or stats['max_phrase'] != depth:
                raise ValueError('Independent varied reference mismatch')
            if minimum == 8 and len(set(phrase[:depth-512])) != 256:
                raise ValueError('High-byte spill coverage incomplete')
            vectors.append(struct.pack('<IIIII', minimum, len(expected), len(raw), len(expected), 0)+raw+expected)
            vector_info.append({'minimum': minimum, 'maximum_phrase': depth, 'bytes': len(expected),
                                'expected_sha256': hashlib.sha256(expected).hexdigest()})
        (output/'fixtures.bin').write_bytes(struct.pack('<II', len(vectors), len(vectors))+b''.join(vectors))
        driver = (prior/'driver.cpp').read_text().split('    for(unsigned stop=0;stop<200;stop++) {')[0]
        if driver == (prior/'driver.cpp').read_text():
            raise ValueError('Driver boundary changed')
        target = 'd.stack_rdata=spill[spill_address];'
        if driver.count(target) != 1:
            raise ValueError('Spill reader changed')
        driver = driver.replace(target, '''d.stack_rdata=spill[spill_address ^ ((argc>2&&std::string(argv[2])=="address")?1:0)];
                if(argc>2&&std::string(argv[2])=="data")d.stack_rdata^=1;
                if(argc>2&&std::string(argv[2])=="width")d.stack_rdata&=3;''')
        driver += '''    if(!spill_reads||!spill_writes)throw std::runtime_error("no spill exercised");
    std::cout<<"PASS varied_cases=4 bytes="<<bytes<<" cycles="<<total<<" spill_reads="<<spill_reads<<" spill_writes="<<spill_writes<<"\\n";
}
'''
        (output/'driver.cpp').write_text(driver)
        def run(command, name, negative=False):
            with (output/(name+'.log')).open('w') as log:
                completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=180)
            text = (output/(name+'.log')).read_text()
            if negative:
                if completed.returncode == 0 or 'mismatch frame ' not in text:
                    raise ValueError('Mutation did not fail at byte comparison: '+name)
            elif completed.returncode:
                raise ValueError('Command failed: '+name)
            return {'exit': completed.returncode, 'last_line': text.strip().splitlines()[-1]}
        run(['verilator', '--cc', '--exe', '--build', '-j', '2', '--top-module', 'gif_lzw_cached',
             '--Mdir', str(output/'obj'), str(prior/'gif_lzw_cached.sv'), str(prior/'cached_dictionary.sv'), str(output/'driver.cpp')], 'compile')
        command = [str(output/'obj/Vgif_lzw_cached'), str(output/'fixtures.bin')]
        tests = {'positive': run(command, 'positive')}
        for mutation in ['address', 'data', 'width']:
            tests[mutation] = run(command+[mutation], mutation, True)
        result.update(status='pass', tests=tests, vectors=vector_info,
                      passed_result_sha256=digest(prior/'result.json'),
                      source_hashes={str(p.relative_to(source)): digest(p) for p in
                                     [Path(__file__), source/'fixtures.py', source/'gif_reference.py']},
                      generated_hashes={name: digest(output/name) for name in ['fixtures.bin', 'driver.cpp']})
    except Exception as exc:
        result.update(status='failed', error=str(exc))
        raise
    finally:
        (output/'result.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
