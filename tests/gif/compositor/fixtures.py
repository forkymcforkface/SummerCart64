"""Validate the narrow CI8 pilot subset and generate original-payload vectors."""
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gif_reference import read_gif, decode

source, output = map(lambda p: Path(p).resolve(), sys.argv[1:3])
if output.is_relative_to(Path(__file__).resolve().parent.parent):
    raise SystemExit("Build directory must be outside the source tests directory")
w, h, bg, palette, frames = read_gif(source)
if (w, h, bg, len(palette)) != (320, 240, 255, 768) or not frames:
    raise SystemExit("Pilot requires 320x240, 256-entry global palette, background index 255")
for i, frame in enumerate(frames):
    disposal, delay, transparent, index = frame['gce']
    if ((frame['x'], frame['y'], frame['w'], frame['h']) != (0, 0, 320, 240)
            or frame['interlace'] or frame['local'] or disposal > 1
            or not transparent or index != 255):
        raise SystemExit(f"Frame {i} is outside the retained global-palette CI8 pilot subset")
output.mkdir(parents=True, exist_ok=True)
with (output / 'fixtures.bin').open('wb') as stream:
    stream.write(struct.pack('<I', len(frames)))
    for frame in frames:
        expected, metrics = decode(frame['raw'], frame['bits'], 76800)
        assert len(expected) == 76800
        stream.write(struct.pack('<5I', frame['bits'], 76800, len(frame['raw']), len(expected), 0))
        stream.write(frame['raw'])
        stream.write(expected)
(output / 'manifest.json').write_text(json.dumps({
    'source': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'frames': len(frames), 'width': w, 'height': h, 'background_index': bg,
    'global_palette_rgb': list(palette), 'transparent_index': 255,
    'packet_cadence': 'Every four original frames, plus final remainder; test cadence only'
}, indent=2) + '\n')
print(f'PASS validated original GIF subset and generated {len(frames)} frame vectors')
