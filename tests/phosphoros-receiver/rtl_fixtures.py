#!/usr/bin/env python3
"""Wrap unchanged simulated-RTL GPD1 packets for N64 receiver verification."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

import numpy as np
from PIL import Image
from fixtures import WIDTH, HEIGHT, PIXELS, decode, packets, read_pilot, rgba5551


def generate(source, output, paths):
    frames, palette, background = read_pilot(source)
    imports, needed = [], set()
    for path in paths:
        packet = path.read_bytes()
        magic, generation, frame, ref, dims, flags, count, size = struct.unpack_from(">8I", packet)
        if (magic != 0x47504431 or generation != 1 or dims != ((WIDTH << 16) | HEIGHT)
                or flags != 1 or count > 1200 or size != count * 64
                or len(packet) != 192 + size or packet[182:192] != bytes(10)
                or frame >= len(frames) or (ref != 0xffffffff and ref >= frame)):
            raise ValueError(f"unsupported or malformed packet: {path}")
        needed.add(frame)
        if ref != 0xffffffff:
            needed.add(ref)
        imports.append((path, packet, frame, ref, count))
    if not imports or len(imports) > 32:
        raise ValueError("supply 1..32 original-source RTL packets")
    canvas = np.full((HEIGHT, WIDTH), background, dtype=np.uint8)
    canvases = {0xffffffff: canvas.copy()}
    for index, frame in enumerate(frames):
        raw, _ = decode(frame["raw"], frame["bits"], PIXELS)
        indices = np.frombuffer(raw, dtype=np.uint8).reshape(HEIGHT, WIDTH)
        mask = indices != 255
        canvas[mask] = indices[mask]
        if index in needed:
            canvases[index] = canvas.copy()
        if index == max(needed):
            break
    blob = bytearray(struct.pack(">4I", 0x47534231, len(imports), 528, 0)
                     + palette.astype(">u2").tobytes() + bytes(len(imports) * 64))
    ledger, provenance = [], []
    with Image.open(source) as pillow:
        for case, (path, packet, frame, ref, count) in enumerate(imports):
            base, expected = canvases[ref], canvases[frame]
            result = base.copy()
            consumed = 0
            for tile in range(1200):
                if not packet[32 + tile // 8] & (1 << (tile % 8)):
                    continue
                if consumed + 64 > count * 64:
                    raise ValueError("mask contains more tiles than packet header")
                y, x = divmod(tile, 40)
                pixels = np.frombuffer(packet[192 + consumed:256 + consumed], dtype=np.uint8)
                result[y * 8:y * 8 + 8, x * 8:x * 8 + 8] = pixels.reshape(8, 8)
                consumed += 64
            if consumed != count * 64 or not np.array_equal(result, expected):
                raise ValueError(f"RTL packet does not reproduce source frame {frame}")
            rendered = palette[result].astype(">u2").tobytes()
            pillow.seek(frame)
            if rendered != rgba5551(pillow):
                raise ValueError(f"RTL render differs from Pillow frame {frame}")
            _, span, _, rows, payload = packets(base, expected, frame, ref)
            crc, rgba_crc = zlib.crc32(result.tobytes()), zlib.crc32(rendered)
            offsets = []
            for data in (base.tobytes(), expected.tobytes(), packet, span):
                blob.extend(bytes(-len(blob) % 16))
                offsets.append(len(blob))
                blob.extend(data)
            entry = (frame, ref, offsets[0], offsets[1], offsets[2], len(packet), count,
                     crc, rgba_crc, offsets[3], len(span), rows, payload, 0, 0, 0)
            struct.pack_into(">16I", blob, 528 + case * 64, *entry)
            ledger.append(dict(case=case, frame=frame, reference=ref, tile_count=count,
                               tile_packet_bytes=len(packet), row_count=rows,
                               row_payload_bytes=payload, span_packet_bytes=len(span),
                               full_bytes=PIXELS, ci8_crc32=f"{crc:08x}",
                               rgba5551_crc32=f"{rgba_crc:08x}"))
            provenance.append(dict(case=case, packet_path=str(path),
                                   packet_sha256=hashlib.sha256(packet).hexdigest(),
                                   tile_source="unchanged RTL simulation output",
                                   span_source="host-derived comparison control"))
            print(f"PASS RTL packet case={case} source_frame={frame} reference={ref} tiles={count}")
    struct.pack_into(">I", blob, 12, len(blob))
    output.mkdir(parents=True, exist_ok=True)
    (output / "rtl-receiver-fixture.bin").write_bytes(blob)
    (output / "rtl-receiver-fixture.json").write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    manifest = dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    fixture_sha256=hashlib.sha256(blob).hexdigest(), fixture_bytes=len(blob),
                    packets=provenance, scope="simulated FPGA packet -> real N64 receiver; not board FPGA decode")
    (output / "rtl-receiver-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="original Final Fight background.gif")
    parser.add_argument("output", type=Path, help="ignored output directory")
    parser.add_argument("packets", type=Path, nargs="+", help="actual original-source GPD1 RTL packets")
    args = parser.parse_args()
    generate(args.source, args.output, args.packets)
