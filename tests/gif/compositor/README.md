# Experimental original-GIF composition and N64 packet output

This simulation connects the [LZW core](../gif_lzw.sv) to a CI8 compositor and
GPD1 packet emitter. It is excluded from production FPGA source lists. It does
not implement an SC64 memory bridge, physical accelerator, or runtime GIF parser.
The [independent reference](../gif_reference.py) supplies original compressed
image bytes and expected indices; no GIF64 asset is an input or prerequisite.

Run with Python 3, Verilator, g++ and make:

```sh
sh /path/to/tests/gif/compositor/run.sh ORIGINAL.gif /path/to/build/compositor
```

The explicit output directory must be outside the source tests directory.
Fixtures, manifest, objects, logs and the first sixteen actual emitted packets
(`original-0003.gpd`, `original-0007.gpd`, etc.) go there. Python only prepares
test vectors; this is not an end-user conversion requirement. The runner runs
fault probes and then every original frame. For a shorter diagnostic after
building, invoke `obj/Vgif_pipeline fixtures.bin OUTPUT_DIRECTORY FRAME_COUNT`;
zero selects the fault probes. A successful short run is not the full gate.

## Supported subset and ownership

The generator fails before simulation unless the original has a 320x240 canvas,
256-entry global palette, background index 255, full-canvas images, disposal 0/1,
no interlace or local palettes, and transparency index 255 in every image.
Final Fight satisfies these restrictions. Generic GIF disposal, palette changes,
subrectangles and changing alpha interpretation need further implementation or
explicit software fallback.

The compositor retains an **external** 76,800-byte CI8 canvas. Transparent input
is a no-op; differing opaque indices write the canvas and mark an 8x8 tile.
The canvas is not an on-chip array. The N64 owns a separate 512-byte RGBA5551 TLUT;
for this subset index 255 is transparent and the other entries are opaque.

Dirty bits accumulate across submitted images until a matching generation/frame
acknowledgement. While emitting or waiting for ACK the canvas cannot change.
Wrong ACKs flag an error and leave the packet pending. Correct ACK clears the
150-byte dirty map sequentially before `busy` falls. The first packet marks all
tiles; later packets reference the last acknowledged image. Changed-back pixels
can conservatively remain marked. Every four images plus the final remainder are
emitted by the harness solely to test reference retention, not OS4 timing policy.

An external memory request remains stable until acknowledgement. Cancellation
drains a pending transaction before invalidating the session. Memory errors
invalidate the session and stop requests. An indefinitely unresponsive bus needs
owner-level reset; this prototype does not claim safe completion without one.
The wrapper cancels composition on LZW decode failure. A new session clears the
canvas to its background index.

## GPD1 wire format

The fixed prefix is 192 bytes: eight big-endian 32-bit header words followed by
a 160-byte mask region. Header words are magic `0x47504431`, generation, frame,
reference frame, dimensions `0x014000f0`, flags `1` (CI8), tile count, and payload
bytes (`tile_count*64`). The mask contains 150 bytes then ten zero padding bytes;
tile index is `tile_y*40+tile_x`, least significant bit first within each byte.
Each marked tile contributes 64 row-major bytes, in row-major tile order.
The packet length is 16-byte aligned. TLUT bytes are supplied out of band.

Exported packets use generation 1 and zero-based original image numbers.
The packet for image 3 references `0xffffffff` (initial all-255 canvas); image 7
references image 3. Synthetic preflight packets are never exported with these
names. A receiver must validate generation/reference before applying a packet.

## Verified results and remaining limits

The complete original Final Fight run passes all **1,717 images**, comparing
actual RTL LZW indices, external-memory composition, emitted packet bytes and
an independent receiver canvas. There are **430 original packets / 10,245,568
bytes**, excluding synthetic preflights. The synthetic memory model counts
142,028,608 reads and 15,379,999 writes; the run takes 880,954,077 cycles with a
maximum image plus optional output of 1,152,026 cycles.

The harness injects input/output stalls and variable memory acknowledgement
latency, and checks stable requests/output, memory bounds and canaries. Separate
probes cover cancellation during a memory request, five invalid metadata classes
before writes, full initial and empty packets, wrong-generation/wrong-frame ACKs,
correct subsequent ACK, and memory-error shutdown.

Yosys 0.52 MachXO2 mapping of the compositor alone reports **630 LUT4, 240 FF,
80 CCU2D and 1 DP8KC**. An earlier wide dirty-vector implementation needed 6,130
LUT4 and 1,431 FF; synchronous byte RAM reduces that cost while increasing modeled
cycles about 3%. This is generic primitive mapping, not Diamond placement/timing.
The parent LZW core separately requires 14 DP8KC, so the combined design does not
have a demonstrated fit alongside SC64. These are synthetic cycles, not measured
board throughput or proof of 60 FPS.

Still required: bounded runtime source framing, supported generic GIF semantics,
shared cart-memory arbitration and safe address ownership, packet publication,
integrated device fit/timing, and actual FPGA-to-N64 performance measurement.
The separate N64 receiver benchmark can consume these exact simulated packets;
that validates packet compatibility, not execution of this RTL on the cartridge.
