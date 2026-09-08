"""Inspect official SC64 update chunks with strict bounds, CRC and padding checks.

Extraction and byte comparison are reference inspection, never compilation.
All output belongs in an explicit directory outside the checked-in tests.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib


def inspect(data):
    if data[:16] != b'SC64 Update v2.0':
        raise ValueError('invalid update token')
    chunks=[];offset=16;seen=set()
    while offset<len(data):
        if offset+16>len(data):
            raise ValueError('truncated header')
        ident,span,crc,length=struct.unpack_from('<4I',data,offset)
        end=offset+8+span
        if ident not in range(1,6) or ident in seen or span<8 or end>len(data) or end%16 or length>span-8:
            raise ValueError('invalid chunk span/id')
        payload=data[offset+16:offset+16+length]
        if zlib.crc32(payload)!=crc or any(data[offset+16+length:end]):
            raise ValueError('CRC or padding mismatch')
        chunks.append({'id':ident,'offset':offset,'payload_offset':offset+16,'length':length,
                       'end':end,'crc32':f'{crc:08x}','sha256':hashlib.sha256(payload).hexdigest()})
        seen.add(ident);offset=end
    return chunks


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('firmware',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();out=args.output.resolve()
    tests=Path(__file__).resolve().parents[2]
    if out==tests or tests in out.parents:
        parser.error('output must be outside tests')
    data=args.firmware.read_bytes();chunks=inspect(data)
    out.mkdir(parents=True,exist_ok=False)
    for chunk in chunks:
        payload=data[chunk['payload_offset']:chunk['payload_offset']+chunk['length']]
        (out/f"chunk-{chunk['id']}.bin").write_bytes(payload)
        if chunk['id']==1:
            chunk['text']=payload.decode('utf-8')
    report={'file_sha256':hashlib.sha256(data).hexdigest(),'length':len(data),'chunks':chunks,
            'source_rebuilt':False}
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
