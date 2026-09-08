"""Synthesize the actual transport-abort research pipeline without board output.

Top-level observation ports remain exposed. Simulation-only fatal checks are
removed explicitly and inventoried; functional control logic is preserved.
Stock arbiter/SDRAM controller and added DMA channels are counted separately.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--decoder', type=Path)
    parser.add_argument('--mux', type=Path)
    parser.add_argument('--stock', action='store_true')
    parser.add_argument('--physical-dq', action='store_true')
    args = parser.parse_args()
    if args.stock and (args.decoder or args.mux):
        parser.error('stock reference has no GIF overrides')
    here = Path(__file__).resolve().parent
    tests = here.parents[1]
    root = here.parents[2]
    out = args.output.resolve()
    if out.exists() or out == tests or tests in out.parents:
        parser.error('output must be fresh and outside tests')
    out.mkdir(parents=True)
    gif = here.parent
    rtl = root / 'fw/rtl'
    source = gif / 'sc64-transport-abort/gif_transport_abort_pipeline.sv'
    wrapper = source.read_text()
    if args.stock:
        from stock import wrapper as stock_wrapper
        wrapper = stock_wrapper()
    if args.physical_dq:
        if args.stock:
            raise ValueError('physical DQ probe supports the full transport wrapper only')
        substitutions = [('    input logic chip_drive,\n', ''),
                         ('    input logic [15:0] chip_data,\n', ''),
                         ('    output logic [15:0] chip_dq,', '    inout wire [15:0] chip_dq,'),
                         ('    wire [15:0] dq;\n', ''),
                         ("    assign dq=chip_drive?chip_data:16'hzzzz;\n", ''),
                         ('    assign chip_dq=dq;\n', ''),
                         ('.sdram_dq(dq)', '.sdram_dq(chip_dq)')]
        for old, new in substitutions:
            if wrapper.count(old) != 1:
                raise ValueError('unexpected physical DQ wrapper anchor')
            wrapper = wrapper.replace(old, new)
    checks = re.findall(r'\$fatal\([^;]+\);', wrapper)
    if len(checks) != (0 if args.stock else 6):
        raise ValueError('unexpected simulation fatal checks')
    wrapper = re.sub(r'\$fatal\([^;]+\);', 'begin end', wrapper)
    generated = out / 'pipeline.sv'
    generated.write_text(wrapper)
    mux_source = args.mux.resolve() if args.mux else gif/'sc64-transport-abort/gif_transport_mux.sv'
    mux_text = mux_source.read_text()
    mux_checks = re.findall(r'\$fatal\([^;]+\);', mux_text)
    if len(mux_checks) != 4:
        raise ValueError('unexpected mux simulation checks')
    mux_file = out/'gif_transport_mux.sv'
    mux_file.write_text(re.sub(r'\$fatal\([^;]+\);', 'begin end', mux_text))
    decoder = args.decoder.resolve() if args.decoder else gif / 'cached'
    files = [rtl/'memory/mem_bus.sv', rtl/'memory/dma_scb.sv', rtl/'fifo/fifo_bus.sv',
        rtl/'n64/n64_scb.sv', rtl/'memory/memory_dma.sv', rtl/'memory/memory_arbiter.sv',
        rtl/'memory/memory_sdram.sv', gif/'sc64-bus/gif_sc64_bus.sv',
        decoder/'gif_lzw_cached.sv', decoder/'cached_dictionary.sv',
        gif/'compositor/gif_ci8_compose.sv', mux_file, generated]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    with (out/'converted.v').open('w') as target, (out/'conversion.log').open('w') as log:
        subprocess.run(['sv2v','--top=gif_transport_abort_pipeline',*map(str,files)],stdout=target,stderr=log,check=True,timeout=120)
    script = f'''read_verilog {out}/converted.v
synth_lattice -family xo2 -top gif_transport_abort_pipeline -run begin:map_ram
select gif_transport_abort_pipeline
write_json -selected {out}/memories.json
select -clear
synth_lattice -family xo2 -top gif_transport_abort_pipeline -run map_ram:
check -assert
stat
write_json {out}/mapped.json
'''
    (out/'synth.ys').write_text(script)
    with (out/'synthesis.log').open('w') as log:
        subprocess.run(['yosys','-Q','-T','-s',str(out/'synth.ys')],stdout=log,stderr=log,check=True,timeout=600)
    top = 'gif_transport_abort_pipeline'
    cells = json.loads((out/'mapped.json').read_text())['modules'][top]['cells']
    supported = {'LUT4','CCU2D','TRELLIS_FF','DP8KC','PDPW8KC','TRELLIS_DPR16X4',
                 '$_TBUF_','$scopeinfo','VHI','VLO','PFUMX','L6MUX21'}
    unsupported = sorted({c['type'] for c in cells.values()} - supported)
    if unsupported:
        raise ValueError('unreviewed mapped cell types: '+str(unsupported))
    raw = json.loads((out/'memories.json').read_text())['modules'][top]['cells']
    memories = {name:cell['parameters'] for name,cell in raw.items() if cell['type']=='$mem_v2'}
    owners = {owner:dict(Counter(c['type'] for n,c in cells.items() if n.startswith(owner+'.'))) for owner in
              ['decoder','compositor','adapter','mux','source_dma','output_dma','arbiter','controller']}
    result = {'synthesis_passed':True,'hardware_qualified':False,'bitstream_generated':False,
       'stock_only':args.stock,'physical_dq':args.physical_dq,'spill_bus_adapter_included':False,
       'cell_counts':dict(Counter(c['type'] for c in cells.values())),
       'unsupported_mapped_cell_types':unsupported,
       'owner_cells':owners,'inferred_memories':memories,'source_hashes':hashes,
       'simulation_only_checks_removed':{'pipeline':checks,'mux':mux_checks},
       'original_pipeline_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
       'original_mux_sha256':hashlib.sha256(mux_source.read_bytes()).hexdigest(),
       'top_ports':json.loads((out/'mapped.json').read_text())['modules'][top]['ports'],
       'physical_ram_cells':{name:{'type':c['type'],'parameters':c['parameters']} for name,c in cells.items() if c['type'] in {'DP8KC','PDPW8KC','TRELLIS_DPR16X4'}},
       'versions':{tool:subprocess.check_output([tool,flag],text=True).strip() for tool,flag in [('sv2v','--version'),('yosys','-V')]}}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['cell_counts']))


if __name__ == '__main__':
    main()
