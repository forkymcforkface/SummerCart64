"""Verify the bounded decoder and unchanged SC64 transport ownership.

Each mode uses a new ignored output directory. Core mode runs original and
boundary/fault fixtures plus mapping. Transport mode compares the unchanged
abort wrapper against its baseline with actual DMA/arbiter/SDRAM models.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

from generate import generate, replace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--mode', choices=['core', 'transport'], required=True)
    parser.add_argument('--focused', action='store_true')
    parser.add_argument('--mux', type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent.parent
    output = args.output.resolve()
    if output.exists() or source.parent in output.parents:
        raise ValueError('Output must be new and outside tests')
    output.mkdir(parents=True)
    if args.focused and args.mode != 'core':
        raise ValueError('Focused mode is core-only')
    if args.mux and args.mode != 'transport':
        raise ValueError('Mux option is transport-only')
    result = {'status': 'running', 'mode': args.mode, 'focused': args.focused, 'hardware_qualified': False}
    def run(command, name, timeout=900):
        with (output/(name+'.log')).open('w') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=timeout)
    try:
        result['source_hashes'] = generate(source, output)
        if args.mode == 'core':
            run([sys.executable, '-B', str(source/'fixtures.py'), str(args.original), str(output)], 'fixtures')
            node = next(n for n in ast.parse((source/'fixtures.py').read_text()).body
                        if isinstance(n, ast.FunctionDef) and n.name == 'pack')
            scope = {}
            exec(compile(ast.Module(body=[node], type_ignores=[]), '<reference pack>', 'exec'), scope)
            pack = scope['pack']
            sys.path.insert(0, str(source))
            from gif_reference import decode
            records = []
            for depth, limit, error in [(391, 76636, 0), (392, 76800, 1)]:
                raw = pack([4, 0]+list(range(6, depth+5))+[5], 2)
                complete, stats = decode(raw, 2, depth*(depth+1)//2)
                assert complete == bytes(len(complete)) and stats['max_phrase'] == depth
                expected = bytes(76636)
                records.append(struct.pack('<IIIII', 2, limit, len(raw), len(expected), error)+raw+expected)
            for limit in [76801, 0xffffffff]:
                records.append(struct.pack('<IIIII', 2, limit, 0, 0, 1))
            path = output/'fixtures.bin'
            data = path.read_bytes()
            count, originals = struct.unpack_from('<II', data)
            if args.focused:
                _, _, raw_size, expected_size, _ = struct.unpack_from('<IIIII', data, 8)
                data = data[:28+raw_size+expected_size]
                count = originals = 1
            path.write_bytes(struct.pack('<II', count+len(records), originals)+data[8:]+b''.join(records))
            driver = (source/'cached/driver.cpp').read_text()
            driver = replace(driver, 'bool inject_error=false,read_error=false;',
                             'bool inject_error=false,read_error=false,corrupt_dictionary=false;unsigned corrupt_reads=0;uint64_t corrupt_clock=0;')
            driver = replace(driver, 'd.memory_ack=1;d.memory_rdata=dictionary[key];',
                             'd.memory_ack=1;d.memory_rdata=dictionary[key];\n                if(corrupt_dictionary&&!wr){d.memory_rdata=(key<<8)|0x5a;if(!corrupt_reads)corrupt_clock=clock_count;corrupt_reads++;}')
            driver = replace(driver, 'mode<4', 'mode<5')
            driver = replace(driver, 'mode==3?', 'mode>=3?', 3)
            driver = replace(driver, 'inject_error=mode==0;read_error=mode==3;',
                             'inject_error=mode==0;read_error=mode==3;corrupt_dictionary=mode==4;')
            driver = replace(driver, '(mode==0||mode==3)', '(mode==0||mode>=3)')
            marker = '    std::cout<<"PASS fixtures="'
            driver = replace(driver, marker, '    if(!corrupt_reads)throw std::runtime_error("corrupt dictionary not exercised");\n'
                             '    if(clock_count-corrupt_clock>4096)throw std::runtime_error("corrupt guard exceeds512-stack bound");\n'
                             '    std::cout<<"Corrupt guard cycles="<<(clock_count-corrupt_clock)<<"\\n";\n'+
                             ('' if args.focused else '    if(originals!=1717||total!=1257856312ull)throw std::runtime_error("original baseline changed");\n')+marker)
            driver = driver.replace('memory_error_cancel_restart=4', 'memory_error_cancel_restart=4 corrupt_dictionary_guard=1')
            (output/'driver.cpp').write_text(driver)
            run(['verilator', '--cc', '--exe', '--build', '-j', '2', '--top-module', 'gif_lzw_cached',
                 '--Mdir', str(output/'obj'), str(output/'gif_lzw_cached.sv'), str(output/'cached_dictionary.sv'), str(output/'driver.cpp')], 'compile')
            run([str(output/'obj/Vgif_lzw_cached'), str(output/'fixtures.bin')], 'simulation')
            script = (f'read_verilog -sv "{output}/gif_lzw_cached.sv" "{output}/cached_dictionary.sv"; '
                      f'synth_lattice -family xo2 -top gif_lzw_cached; stat; write_json "{output}/mapped.json"')
            run(['yosys', '-Q', '-T', '-p', script], 'synthesis')
            cells = json.loads((output/'mapped.json').read_text())['modules']['gif_lzw_cached']['cells']
            counts = {}
            for cell in cells.values():
                counts[cell['type']] = counts.get(cell['type'], 0)+1
            result.update(mapped_cells=counts, simulation=(output/'simulation.log').read_text().splitlines()[-1])
        else:
            run([sys.executable, '-B', str(source/'compositor/fixtures.py'), str(args.original), str(output)], 'fixtures')
            rtl = source.parent.parent/'fw/rtl'
            actual = [rtl/p for p in ['memory/mem_bus.sv', 'memory/dma_scb.sv', 'fifo/fifo_bus.sv',
                      'n64/n64_scb.sv', 'memory/memory_dma.sv', 'memory/memory_arbiter.sv', 'memory/memory_sdram.sv']]
            shared = [source/p for p in ['sc64-bus/gif_sc64_bus.sv', 'compositor/gif_ci8_compose.sv',
                      'sc64-transport-abort/gif_transport_mux.sv', 'sc64-transport-abort/gif_transport_abort_pipeline.sv']]
            normal = (source/'sc64-transport/driver.cpp').read_text().replace('Vgif_transport_pipeline', 'Vgif_transport_abort_pipeline')
            (output/'normal.cpp').write_text(normal)
            def build(directory, decoder, driver, name):
                chosen = [args.mux.resolve() if args.mux and decoder == output and p.name == 'gif_transport_mux.sv' else p for p in shared]
                run(['verilator', '--cc', '--exe', '--build', '-j', '2', '--top-module', 'gif_transport_abort_pipeline',
                     '--Mdir', str(directory), *map(str, actual+chosen), str(decoder/'gif_lzw_cached.sv'),
                     str(decoder/'cached_dictionary.sv'), str(driver)], name+'-compile')
            summaries = {}
            for name, decoder in [('baseline', source/'cached'), ('bounded', output)]:
                destination = output/name
                destination.mkdir()
                build(destination/'obj', decoder, output/'normal.cpp', name)
                run([str(destination/'obj/Vgif_transport_abort_pipeline'), str(output/'fixtures.bin'), str(destination), '8'], name)
                summaries[name] = (output/(name+'.log')).read_text()
            if summaries['baseline'] != summaries['bounded']:
                raise ValueError('Normal transport baseline differs')
            build(output/'abort-obj', output, source/'sc64-transport-abort/driver.cpp', 'abort')
            run([str(output/'abort-obj/Vgif_transport_abort_pipeline'), str(output/'fixtures.bin'), str(output)], 'abort')
            result.update(normal=summaries['bounded'], cancellation=(output/'abort.log').read_text())
            result['source_hashes'].update({str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                           for p in actual+shared+[source/'sc64-transport/driver.cpp', source/'sc64-transport-abort/driver.cpp']})
            if args.mux:
                result['source_hashes'][str(args.mux.resolve())] = hashlib.sha256(args.mux.read_bytes()).hexdigest()
        result['source_hashes'].update({str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                                       for p in [source/'fixtures.py', source/'gif_reference.py', source/'cached/driver.cpp', source/'compositor/fixtures.py']})
        result.update(status='pass', original_sha256=hashlib.sha256(args.original.read_bytes()).hexdigest(),
                      generated_hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                        for p in output.iterdir() if p.suffix in ['.sv', '.cpp', '.bin']},
                      runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      tool_versions={tool: subprocess.check_output([tool, flag], text=True).strip()
                                     for tool, flag in [('verilator', '--version'), ('yosys', '-V')]})
    except Exception as exc:
        result.update(status='failed', error=str(exc))
        raise
    finally:
        (output/'result.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
