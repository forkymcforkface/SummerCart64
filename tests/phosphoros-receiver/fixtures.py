#!/usr/bin/env python3
"""Generate research receiver packets from an original GIF, never a runtime asset."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "vendor/sc64/tests/gif"))
from gif_reference import decode, read_gif

DEFAULT_FRAMES = (1, 2, 423, 621, 1030, 1713)
WIDTH, HEIGHT = 320, 240
PIXELS = WIDTH * HEIGHT


def packets(previous, current, frame, reference=None):
    """Build index-difference packets against exactly the preceding source frame."""
    changed = (current != previous).reshape(30, 8, 40, 8).any(axis=(1, 3))
    mask, tiles = bytearray(160), bytearray()
    for tile, active in enumerate(changed.reshape(-1)):
        if active:
            mask[tile // 8] |= 1 << (tile % 8)
            y, x = divmod(tile, 40)
            tiles.extend(current[y * 8:y * 8 + 8, x * 8:x * 8 + 8].tobytes())
    tile_count = int(changed.sum())
    reference = frame - 1 if reference is None else reference
    header = (1, frame, reference & 0xffffffff, (WIDTH << 16) | HEIGHT)
    tile_packet = (struct.pack(">8I", 0x47504431, *header, 1, tile_count, len(tiles))
                   + mask + tiles)
    descriptors, pixels = bytearray(), bytearray()
    rows = 0
    for y in range(HEIGHT):
        indices = np.flatnonzero(previous[y] != current[y])
        x = count = 0
        if len(indices):
            x = int(indices[0]) & ~7
            end = (int(indices[-1]) + 8) & ~7
            count = end - x
            pixels.extend(current[y, x:end].tobytes())
            rows += 1
        descriptors.extend(struct.pack(">HH", x, count))
    span_packet = bytearray(struct.pack(">8I", 0x47505231, *header, 2, rows,
                                        len(pixels)) + descriptors + pixels)
    span_packet.extend(bytes(-len(span_packet) % 16))
    return tile_packet, span_packet, tile_count, rows, len(pixels)


def rgba5551(image):
    """Match the N64 palette precision, including the source alpha bit."""
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint16)
    colors = (((rgba[:, :, 0] >> 3) << 11) | ((rgba[:, :, 1] >> 3) << 6)
              | ((rgba[:, :, 2] >> 3) << 1) | (rgba[:, :, 3] >= 128))
    return colors.astype(">u2").tobytes()


def read_pilot(source):
    """Read and validate the source-format subset supported by the RTL pilot."""
    width, height, background, global_palette, frames = read_gif(source)
    if (width, height, background, len(global_palette)) != (320, 240, 255, 768):
        raise ValueError("pilot requires 320x240, 256-entry global palette, background255")
    for frame in frames:
        if ((frame["x"], frame["y"], frame["w"], frame["h"]) != (0, 0, 320, 240)
                or frame["local"] or frame["interlace"]
                or frame["gce"][0] != 0 or frame["gce"][2:] != (True, 255)):
            raise ValueError("pilot requires full frames, disposal0, global palette, transparency255")
    palette = np.frombuffer(global_palette, dtype=np.uint8).reshape(-1, 3).astype(np.uint16)
    palette = (((palette[:, 0] >> 3) << 11) | ((palette[:, 1] >> 3) << 6)
               | ((palette[:, 2] >> 3) << 1) | 1)
    palette[255] &= np.uint16(0xfffe)
    return frames, palette, background


def generate(source, output, selected):
    frames, palette, background = read_pilot(source)
    if not selected or len(selected) > 32 or min(selected) < 1 or max(selected) >= len(frames):
        raise ValueError("select 1..32 frames within 1..frame_count-1")
    count = len(selected)
    blob = bytearray(struct.pack(">4I", 0x47534231, count, 528, 0)
                     + palette.astype(">u2").tobytes() + bytes(count * 64))
    canvas = np.full((HEIGHT, WIDTH), background, dtype=np.uint8)
    ledger = []
    with Image.open(source) as reference:
        for index, frame in enumerate(frames):
            previous = canvas.copy() if index in selected else None
            raw, _ = decode(frame["raw"], frame["bits"], PIXELS)
            indices = np.frombuffer(raw, dtype=np.uint8).reshape(HEIGHT, WIDTH)
            mask = indices != 255
            canvas[mask] = indices[mask]
            if index not in selected:
                continue
            tile, span, tile_count, rows, payload = packets(previous, canvas, index)
            full = canvas.tobytes()
            rendered = palette[canvas].astype(">u2").tobytes()
            reference.seek(index)
            if rendered != rgba5551(reference):
                raise ValueError(f"Pillow source render mismatch at frame {index}")
            crc, rgba_crc = zlib.crc32(full), zlib.crc32(rendered)
            offsets = []
            for data in (previous.tobytes(), full, tile, span):
                blob.extend(bytes(-len(blob) % 16))
                offsets.append(len(blob))
                blob.extend(data)
            case = len(ledger)
            entry = (index, index - 1, offsets[0], offsets[1], offsets[2], len(tile),
                     tile_count, crc, rgba_crc, offsets[3], len(span), rows, payload, 0, 0, 0)
            struct.pack_into(">16I", blob, 528 + case * 64, *entry)
            ledger.append(dict(case=case, frame=index, reference=index - 1,
                               tile_count=tile_count, tile_packet_bytes=len(tile),
                               row_count=rows, row_payload_bytes=payload,
                               span_packet_bytes=len(span), full_bytes=PIXELS,
                               ci8_crc32=f"{crc:08x}", rgba5551_crc32=f"{rgba_crc:08x}"))
            print(f"PASS source golden case={case} frame={index}", flush=True)
            if index == max(selected):
                break
    if len(ledger) != count:
        raise ValueError("missing selected frame")
    struct.pack_into(">I", blob, 12, len(blob))
    output.mkdir(parents=True, exist_ok=True)
    (output / "gif-span-fixture.bin").write_bytes(blob)
    (output / "gif-span-fixture.json").write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    manifest = dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    fixture_sha256=hashlib.sha256(blob).hexdigest(), fixture_bytes=len(blob),
                    selected_frames=selected, reference="vendor/sc64/tests/gif/gif_reference.py",
                    purpose="research receiver fixture, not end-user conversion")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="original Final Fight background.gif")
    parser.add_argument("output", type=Path, help="ignored output directory, normally under build/")
    parser.add_argument("--frames", default=",".join(map(str, DEFAULT_FRAMES)))
    parser.add_argument("--check-against", type=Path, help="require byte-identical existing fixture")
    args = parser.parse_args()
    selected = sorted(set(map(int, args.frames.split(","))))
    result = generate(args.source, args.output, selected)
    if args.check_against and (args.output / "gif-span-fixture.bin").read_bytes() != args.check_against.read_bytes():
        raise SystemExit("FAIL fixture differs from supplied baseline")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
