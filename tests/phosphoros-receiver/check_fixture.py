#!/usr/bin/env python3
"""Verify combined receiver packet reconstruction and source render CRC metadata."""
import argparse
from pathlib import Path
import struct
import zlib

PIXELS = 320 * 240


def check(path):
    blob = path.read_bytes()
    magic, count, table, size = struct.unpack_from(">4I", blob)
    assert magic == 0x47534231 and 0 < count <= 32 and table == 528 and size == len(blob)
    palette = struct.unpack_from(">256H", blob, 16)
    assert palette[255] == 0
    for case in range(count):
        entry = struct.unpack_from(">16I", blob, table + case * 64)
        frame, ref, base, full, tile_off, tile_size, tiles, crc, rgba, span_off, span_size, rows, payload, *_ = entry
        expected = blob[full:full + PIXELS]
        assert len(expected) == PIXELS and zlib.crc32(expected) == crc
        for kind, offset, length in ((1, tile_off, tile_size), (2, span_off, span_size)):
            packet = blob[offset:offset + length]
            magic = 0x47504431 if kind == 1 else 0x47505231
            assert struct.unpack_from(">8I", packet) == (magic, 1, frame, ref, (320 << 16) | 240,
                                                          kind, tiles if kind == 1 else rows,
                                                          tiles * 64 if kind == 1 else payload)
            plane = bytearray(blob[base:base + PIXELS])
            consumed = 0
            if kind == 1:
                assert packet[182:192] == bytes(10)
                for tile in range(1200):
                    if not packet[32 + tile // 8] & (1 << (tile % 8)):
                        continue
                    y, x = divmod(tile, 40)
                    for row in range(8):
                        dest = (y * 8 + row) * 320 + x * 8
                        plane[dest:dest + 8] = packet[192 + consumed:200 + consumed]
                        consumed += 8
                assert consumed == tiles * 64 and length == 192 + consumed
            else:
                nonempty = 0
                for y in range(240):
                    x, n = struct.unpack_from(">HH", packet, 32 + y * 4)
                    if not n:
                        assert x == 0
                        continue
                    assert not (x | n) & 7 and x + n <= 320 and consumed + n <= payload
                    plane[y * 320 + x:y * 320 + x + n] = packet[992 + consumed:992 + consumed + n]
                    consumed += n
                    nonempty += 1
                assert nonempty == rows and consumed == payload and length == (992 + payload + 15) & ~15
            assert bytes(plane) == expected
            rendered = b"".join(struct.pack(">H", palette[index]) for index in plane)
            assert zlib.crc32(rendered) == rgba
        print(f"PASS case={case} frame={frame} full/tiles/spans exact CI8 and render CRC")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    check(parser.parse_args().fixture)
