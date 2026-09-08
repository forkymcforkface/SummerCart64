"""Compare built SC64 CPU components against a validated release container.

This gate checks bytes, not build provenance. The caller retains the source
commit, compiler image and build log separately. FPGA rebuilding is not implied.
"""
import argparse
import hashlib
import json
from pathlib import Path

from compare import differences
from release_update import inspect


COMPONENTS = {
    'mcu': (2, 'sw/controller/build/app/app.bin'),
    'bootloader': (4, 'sw/bootloader/build/bootloader.bin'),
    'primer': (5, 'sw/controller/build/primer/primer.bin'),
}


def compare_cpu(root, release):
    chunks = {chunk['id']: chunk for chunk in inspect(release)}
    result = {}
    for name, (ident, path) in COMPONENTS.items():
        if ident not in chunks:
            raise ValueError('release lacks ' + name)
        chunk = chunks[ident]
        expected = release[chunk['payload_offset']:chunk['payload_offset'] + chunk['length']]
        actual = (root / path).read_bytes()
        result[name] = {
            'identical': actual == expected,
            'bytes': len(actual), 'reference_bytes': len(expected),
            'sha256': hashlib.sha256(actual).hexdigest(),
            'reference_sha256': chunk['sha256'],
            'differing_intervals': differences(expected, actual),
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path, help='checkout containing built CPU binaries')
    parser.add_argument('release', type=Path)
    args = parser.parse_args()
    release = args.release.read_bytes()
    result = compare_cpu(args.root, release)
    print(json.dumps({'release_sha256': hashlib.sha256(release).hexdigest(),
                     'components': result, 'fpga_source_rebuilt': False}, indent=2))
    return 0 if all(item['identical'] for item in result.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
