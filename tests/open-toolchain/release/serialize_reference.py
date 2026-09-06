"""Serialize a decoded SC64 reference in its observed release command profile.

Input is freshly generated Trellis --compress output, never the original FPGA
payload. This bounded MachXO2-7000 profile preserves Trellis frame compression
and EBR contents, validates its CRCs, and emits the observed command ordering.
It does not compile RTL, qualify new routes, or provide a programming tool.
"""
import argparse
import hashlib
import json
from pathlib import Path


def crc16(data):
    """Match Trellis BitstreamReadWriter's polynomial and final zero bits."""
    value = 0
    for byte in data + b'\0\0':
        for bit in range(7, -1, -1):
            top = value & 0x8000
            value = ((value << 1) | ((byte >> bit) & 1)) & 0xffff
            if top:
                value ^= 0x8005
    return value.to_bytes(2, 'big')


def serialize(bit):
    """Reject profiles outside the pinned compressed 7000HC serializer."""
    preamble = bytes.fromhex('ffffbdb3')
    start = bit.find(preamble)
    if start < 0:
        raise ValueError('missing preamble')
    data = bit[start:]
    pos = 0

    def take(count):
        nonlocal pos
        result = data[pos:pos + count]
        if len(result) != count:
            raise ValueError('truncated stream')
        pos += count
        return result

    def expect(expected):
        if take(len(expected)) != expected:
            raise ValueError(f'unexpected command at {pos - len(expected)}')

    expect(bytes.fromhex('ffffbdb3ffff3b000000'))
    initial = take(16)
    if initial != bytes.fromhex('e2000000012bd0432200000040000000'):
        raise ValueError('unsupported device/control profile')
    expect(b'\xff' * 4)
    init = take(4)
    if init != bytes.fromhex('46000000'):
        raise ValueError('missing INIT')
    dictionary = take(12)
    if dictionary[:4] != bytes.fromhex('02000000'):
        raise ValueError('missing dictionary')
    frame_start = pos
    expect(bytes.fromhex('b8e00302'))
    for _ in range(770):
        bitpos = pos * 8
        for _ in range(256):
            def read_bit():
                nonlocal bitpos
                if bitpos >= len(data) * 8:
                    raise ValueError('truncated compressed frame')
                value = (data[bitpos // 8] >> (7 - bitpos % 8)) & 1
                bitpos += 1
                return value
            if read_bit():
                literal = read_bit()
                bitpos += 8 if literal else 4
        pos = (bitpos + 7) // 8
    frames = data[frame_start:pos]
    if take(2) != crc16(initial + init + dictionary + frames):
        raise ValueError('frame CRC mismatch')
    expect(b'\xff' * 8)
    usercode = take(8)
    if usercode[:4] != bytes.fromhex('c2800000'):
        raise ValueError('missing USERCODE')
    if take(2) != crc16(usercode):
        raise ValueError('USERCODE CRC mismatch')
    output = bytearray(bytes.fromhex('ffffbdb3ffff3b000000'))
    output += dictionary + init + frames + crc16(dictionary + init + frames)
    output += b'\xff' * 8 + usercode + crc16(usercode)
    output += bytes.fromhex('22000000c0000000') + b'\xff' * 8
    addresses = []
    while data[pos:pos + 4] == bytes.fromhex('f6000000'):
        address = take(8)
        index = int.from_bytes(address[4:], 'big')
        if index >= 26 * 2048 or index % 2048 or (addresses and index <= addresses[-1]):
            raise ValueError('invalid EBR order/address')
        addresses.append(index)
        command = take(4)
        if command != bytes.fromhex('b2d00080'):
            raise ValueError('unsupported EBR profile')
        payload = take(1152)
        if take(2) != crc16(address + command + payload):
            raise ValueError('EBR CRC mismatch')
        if len(addresses) > 1:
            output += b'\xff' * 4
        output += address + bytes.fromhex('b2100080') + payload
    expect(bytes.fromhex('22000000400000005e000000ffffffff'))
    if pos != len(data):
        raise ValueError('unexpected trailing bytes')
    output += bytes.fromhex('2200000040000000') + b'\xff' * 4
    output += bytes.fromhex('5e000000') + b'\xff' * 16
    return bytes(output), {'compressed_command_bytes': len(frames),
                           'ebr_addresses': addresses}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repacked_bit', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    tests = Path(__file__).resolve().parents[2]
    if output == tests or tests in output.parents:
        parser.error('output must be outside tests')
    result, report = serialize(args.repacked_bit.read_bytes())
    with output.open('xb') as stream:
        stream.write(result)
    report.update(source_rebuilt=False, reference_profile_only=True,
                  bytes=len(result), sha256=hashlib.sha256(result).hexdigest())
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
