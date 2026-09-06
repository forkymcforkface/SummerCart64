"""Generate original payload/metadata stimuli, never precomputed reuse decisions."""
import pathlib
import struct
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from gif_reference import read_gif
source, output = map(pathlib.Path, sys.argv[1:])
assert output.resolve() != pathlib.Path(__file__).resolve().parents[1]
assert pathlib.Path(__file__).resolve().parents[1] not in output.resolve().parents
output.mkdir(parents=True, exist_ok=True)
w, h, bg, palette, frames = read_gif(source)
with (output / 'payloads.bin').open('wb') as f:
    f.write(struct.pack('<I', len(frames)))
    for frame in frames:
        disposal, delay, transparent, index = frame['gce']
        assert frame['pal'] == palette and not frame['local']
        meta = struct.pack('<HHHHHHBBBBII', frame['x'], frame['y'], frame['w'], frame['h'], w, h,
                           frame['bits'], int(frame['interlace']), int(transparent), index, delay, bg)
        assert len(meta) == 24
        f.write(struct.pack('<III', len(frame['raw']), 1, disposal))
        f.write(meta)
        f.write(frame['raw'])
