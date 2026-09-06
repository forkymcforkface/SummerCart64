"""Replay original FPGA payload through Trellis; this is never an RTL build.

SC64 stores a headerless compressed configuration command stream. The inspection
wrapper supplies only metadata framing and the known device ID before the
original CRC reset. No original payload bytes are modified or removed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from compare import differences


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('payload',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();raw=args.payload.read_bytes();out=args.output.resolve()
    tests=Path(__file__).resolve().parents[2]
    if out==tests or tests in out.parents:
        parser.error('output must be outside tests')
    if raw[:10]!=bytes.fromhex('ffffbdb3ffff3b000000'):
        parser.error('expected SC64 preamble followed by CRC reset')
    out.mkdir(parents=True,exist_ok=False)
    wrapped=bytes.fromhex('ff00')+raw[:6]+bytes.fromhex('e2000000012bd043')+raw[6:]
    (out/'identified.bit').write_bytes(wrapped)
    commands=[['ecpunpack','identified.bit','original.config'],
              ['ecppack','--compress','original.config','repacked.bit'],
              ['ecpunpack','repacked.bit','repacked.config']]
    for index,command in enumerate(commands):
        with (out/f'{index}.log').open('w') as log:
            subprocess.run(command,cwd=out,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
    original=(out/'original.config').read_bytes();repacked=(out/'repacked.config').read_bytes()
    bit=(out/'repacked.bit').read_bytes();preamble=bytes.fromhex('ffffbdb3')
    start=bit.find(preamble)
    if start<0:raise ValueError('repacked preamble missing')
    commands=bit[start:]
    tile='';unknown={}
    for line in original.decode().splitlines():
        if line.startswith('.tile '):tile=line[6:]
        if line.startswith('unknown:'):unknown.setdefault(tile,[]).append(line[9:])
    report={'source_rebuilt':False,'original_payload_sha256':hashlib.sha256(raw).hexdigest(),
            'decoded_config_identical':original==repacked,
            'decoded_config_sha256':hashlib.sha256(original).hexdigest(),
            'unknown_bit_records':sum(line.startswith(b'unknown:') for line in original.splitlines()),
            'unknown_bits_by_tile':unknown,
            'command_bytes_identical':raw==commands,'original_command_bytes':len(raw),
            'repacked_command_bytes':len(commands),
            'command_differing_intervals':differences(raw,commands)}
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in {'command_differing_intervals','unknown_bits_by_tile'}},indent=2))
    return 0 if original==repacked else 1


if __name__=='__main__':raise SystemExit(main())
