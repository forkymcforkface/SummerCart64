"""Reconstruct an exact release reference with explicit component provenance.

The upstream SC64 packer combines built CPU files, separately reserialized
reference FPGA data, and reference metadata. This is not an all-source FPGA
rebuild; matching bytes establish only the stated reconstruction.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from cpu import compare_cpu, COMPONENTS
from release_update import inspect


def reconstruct(root, reference, fpga):
    chunks = {chunk['id']: chunk for chunk in inspect(reference)}
    if set(chunks) != set(range(1, 6)):
        raise ValueError('expected a complete five-component reference')
    cpu = compare_cpu(root, reference)
    if not all(item['identical'] for item in cpu.values()):
        raise ValueError('CPU binaries differ from the reference')
    chunk = chunks[3]
    if fpga != reference[chunk['payload_offset']:chunk['payload_offset'] + chunk['length']]:
        raise ValueError('serialized FPGA differs from the reference')
    packer = root / 'sw/tools/update.py'
    spec = importlib.util.spec_from_file_location('sc64_reference_packer', packer)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    update = module.SC64UpdateData()
    update.create_update_data()
    chunk = chunks[1]
    update.add_update_info(reference[chunk['payload_offset']:chunk['payload_offset'] + chunk['length']])
    update.add_mcu_data((root / COMPONENTS['mcu'][1]).read_bytes())
    update.add_fpga_data(fpga)
    update.add_bootloader_data((root / COMPONENTS['bootloader'][1]).read_bytes())
    update.add_primer_data((root / COMPONENTS['primer'][1]).read_bytes())
    result = update.get_update_data()
    if result != reference:
        raise ValueError('upstream packaging differs from the reference')
    report = {
        'byte_identical': True, 'bytes': len(result),
        'sha256': hashlib.sha256(result).hexdigest(),
        'upstream_packer_sha256': hashlib.sha256(packer.read_bytes()).hexdigest(),
        'cpu_components': cpu,
        'fpga_origin': 'supplied bytes; reference equality checked, serializer provenance retained separately',
        'metadata_origin': 'release reference',
        'all_components_rebuilt_from_source': False,
    }
    return result, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('reference', type=Path)
    parser.add_argument('serialized_fpga', type=Path)
    parser.add_argument('output', type=Path, help='new reference artifact directory')
    args = parser.parse_args()
    out = args.output.resolve()
    tests = Path(__file__).resolve().parents[2]
    if out == tests or tests in out.parents:
        parser.error('output must be outside tests')
    result, report = reconstruct(args.root, args.reference.read_bytes(), args.serialized_fpga.read_bytes())
    out.mkdir(parents=True, exist_ok=False)
    (out / 'reconstructed-reference.bin').write_bytes(result)
    (out / 'provenance.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
