#!/usr/bin/env python3
"""Measure exact consecutive GIF reuse candidates against Pillow composition.

This host research probe does not implement a cache or estimate hardware FPS.
Only identical payload/metadata with retain disposal qualifies; source bytes
still need reading and exact comparison in a runtime implementation.
"""
import argparse
import json
from pathlib import Path
from PIL import Image
from gif_reference import read_gif


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    source_dir = Path(__file__).resolve().parent
    if output == source_dir or source_dir in output.parents:
        raise SystemExit("output must remain outside test sources")
    *_, frames = read_gif(args.source)
    previous_key = previous_pixels = None
    candidates = []
    with Image.open(args.source) as image:
        for index, frame in enumerate(frames):
            key = tuple(frame[name] for name in (
                "x", "y", "w", "h", "interlace", "local", "pal", "bits", "raw", "gce"))
            image.seek(index)
            pixels = image.convert("RGBA").tobytes()
            if frame["gce"][0] in (0, 1) and key == previous_key:
                if pixels != previous_pixels:
                    raise RuntimeError(f"composed pixel mismatch at frame {index}")
                candidates.append(index)
            previous_key, previous_pixels = key, pixels
    result = dict(frames=len(frames), exact_consecutive_reuse=len(candidates),
                  candidate_frames=candidates,
                  max_compressed_payload=max(len(frame["raw"]) for frame in frames))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"PASS frames={len(frames)} identical_retained={len(candidates)} Pillow_RGBA_exact")


if __name__ == "__main__":
    main()
