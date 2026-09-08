"""Compare exact-width compositor address expressions without changing state.

All candidates derive from the unchanged research compositor. Mapping and
whole-module equivalence are required; a corrupted address negative control
must fail. Generated sources and proof artifacts stay in a new output tree.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Source anchor changed: '+old)
    return text.replace(old, new)


def derivative(source, variant):
    if 'row' in variant:
        source = replace(source,
            "17'(tile_y) * 17'd2560 + (17'(tile_x) << 3) +\n"
            "        17'(tile_pixel[5:3]) * 17'd320 + 17'(tile_pixel[2:0])",
            "{1'b0, tile_y, tile_pixel[5:3], 8'b0} +\n"
            "        {3'b0, tile_y, tile_pixel[5:3], 6'b0} + {8'b0, tile_x, tile_pixel[2:0]}")
    if 'pixel' in variant:
        source = replace(source,
            "11'(y >> 3) * 11'd40 + 11'(x >> 3)",
            "{(8'(y[7:3]) * 8'd5 + 8'(x[8:6])), x[5:3]}")
    if 'header' in variant:
        source = replace(source,
            "out_byte = 8'(header_word >> ((3 - int'(header_pos[1:0])) * 8));",
            "case (header_pos[1:0])\n"
            "            0: out_byte = header_word[31:24];\n"
            "            1: out_byte = header_word[23:16];\n"
            "            2: out_byte = header_word[15:8];\n"
            "            3: out_byte = header_word[7:0];\n"
            "        endcase")
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    source_path = Path(__file__).resolve().parent.parent/'compositor/gif_ci8_compose.sv'
    if output.exists() or source_path.parent.parent.parent in output.parents:
        raise ValueError('Output must be new and outside tests')
    output.mkdir(parents=True)
    result = {'status': 'running', 'hardware_qualified': False, 'variants': {}}
    def run(script, name, negative=False):
        with (output/(name+'.log')).open('w') as log:
            completed = subprocess.run(['yosys', '-Q', '-T', '-p', script], stdout=log,
                                       stderr=subprocess.STDOUT, timeout=180)
        text = (output/(name+'.log')).read_text()
        if negative:
            if completed.returncode == 0 or 'unproven $equiv cells' not in text:
                raise ValueError('Negative control did not fail at equivalence')
        elif completed.returncode:
            raise ValueError('Yosys failed: '+name)
        return text
    try:
        source = source_path.read_text()
        gold = output/'gold.sv'
        gold.write_text(source.replace('module gif_ci8_compose (', 'module gold ('))
        for variant in ['baseline', 'row', 'pixel', 'header', 'row-header', 'row-pixel', 'row-pixel-header']:
            candidate = derivative(source, variant)
            path = output/(variant+'.sv')
            path.write_text(candidate)
            run(f'read_verilog -sv "{path}"; synth_lattice -family xo2 -top gif_ci8_compose; '
                f'stat; write_json "{output}/{variant}.json"', variant+'-map')
            cells = json.loads((output/(variant+'.json')).read_text())['modules']['gif_ci8_compose']['cells']
            counts = {}
            for cell in cells.values():
                counts[cell['type']] = counts.get(cell['type'], 0)+1
            result['variants'][variant] = counts
            if variant != 'baseline':
                gate = output/(variant+'-gate.sv')
                gate.write_text(candidate.replace('module gif_ci8_compose (', 'module gate ('))
                run(f'read_verilog -sv "{gold}" "{gate}"; proc; memory_map; opt; '
                    'equiv_make gold gate equiv; hierarchy -top equiv; equiv_simple; '
                    'equiv_induct -seq 4; equiv_status -assert', variant+'-equivalence')
        negative = derivative(source, 'row').replace("tile_pixel[5:3], 8'b0", "tile_pixel[5:3], 7'b0, 1'b1")
        negative_path = output/'negative.sv'
        negative_path.write_text(negative.replace('module gif_ci8_compose (', 'module gate ('))
        run(f'read_verilog -sv "{gold}" "{negative_path}"; proc; memory_map; opt; '
            'equiv_make gold gate equiv; hierarchy -top equiv; equiv_simple; '
            'equiv_induct -seq 4; equiv_status -assert', 'negative', True)
        result.update(status='pass', source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
                      runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      generated_hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('*.sv')},
                      yosys=subprocess.check_output(['yosys', '-V'], text=True).strip())
    except Exception as exc:
        result.update(status='failed', error=str(exc))
        raise
    finally:
        (output/'result.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
