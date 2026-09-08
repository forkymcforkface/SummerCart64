# SC64 original-GIF receiver research

This directory is **research tooling**, excluded from production builds. It
measures the N64 half of an original-GIF FPGA decoder: fetching decoded pixels
from cart SDRAM, applying updates and drawing with the RDP. The proposed user
workflow consumes the original GIF directly. Host-generated packets here are
test fixtures, not a required end-user conversion step.

The FPGA implementation and bounded reference decoder live in
[`vendor/sc64/tests/gif`](../../../vendor/sc64/tests/gif/README.md). The maintained
results live in [SC64 UI testing](../../../docs/sc64-ui-testing.md). This directory
owns no USB protocol implementation; it uses the existing `usb_send.py` CLI over
`sc64usb.py`.

## Reproduce the fixture

Install the developer dependencies `numpy` and `pillow`. From the repository
root, supply the upstream original Final Fight GIF and an ignored output path:

```sh
python tools/verify/sc64-gif/fixtures.py \
  "/path/to/Final Fight/images/background.gif" \
  build/n64-sc64/test/sc64-gif
python tools/verify/sc64-gif/check_fixture.py \
  build/n64-sc64/test/sc64-gif/gif-span-fixture.bin
```

The generator imports the vendored `gif_reference.read_gif` and `decode`
functions, composes exact source indexes, and independently checks each selected
frame against Pillow RGBA5551 output. It fails outside the current pilot:
320×240 full frames, one 256-entry global palette, background/transparency index
255, disposal 0 and no interlacing. Index 255 is never painted opaquely, so its
TLUT alpha is 0; other entries have alpha 1.

Default source frames are 1, 2, 423, 621, 1030 and 1713. `--frames` accepts another
comma-separated list within the source. `--check-against FILE` additionally
requires byte-identical output to an existing fixture. Outputs are the combined
binary, case metadata and a source/output SHA-256 manifest. Do not commit these
generated files or the original GIF.

The tested upstream original has SHA-256
`d48de154f477e6753b14d5d1a1fa7c5edcefe17c3688e9afbe790907bc7056b7`.
The default combined fixture is 1,275,088 bytes with SHA-256
`2881f8a879a18d26f2c8c6c6769d1a07a8b03435ef306a95493c45ce5067d425`.

## Install and remove the diagnostic

Use an isolated checkout with the normal toolchain/dependencies. `receiver.inc`
is a temporary insertion into `src/rtk/rtk_gpu_n64.c`; production makefiles never
include it. The injector requires exactly one clean `gpu_init` definition and
refuses duplicate receiver hooks.

To generate a reviewable patch without changing source:

```sh
python tools/verify/sc64-gif/inject.py \
  src/rtk/rtk_gpu_n64.c build/n64-sc64/test/sc64-gif/injection
```

To explicitly install it, preserve an exact source backup and build:

```sh
python tools/verify/sc64-gif/inject.py \
  src/rtk/rtk_gpu_n64.c build/n64-sc64/test/sc64-gif/injection --apply
tools/build.sh n64
```

The N64 build stages its ROM under the normal product paths. Deploy only that
isolated diagnostic build using the repository's `sc64` skill procedure; the
parent hardware operator must own COM6. With the console off, check that the
owned fixture destination is absent or already this test's file, then deploy
`gif-span-fixture.bin` to `sd:/phosphor/data/gif-span-fixture.bin` (the configured
`path_data` directory if different). This test does not alter the theme's GIF.

After boot, run each case through the existing command transport:

```sh
python tools/verify/usb_send.py COM6 "gifspanbench 0" 20
python tools/verify/usb_send.py COM6 "gifspanbench 1" 20
python tools/verify/usb_send.py COM6 "gifspanbench 2" 20
python tools/verify/usb_send.py COM6 "gifspanbench 3" 20
python tools/verify/usb_send.py COM6 "gifspanbench 4" 20
python tools/verify/usb_send.py COM6 "gifspanbench 5" 20
```

Require `[gifspan] PASS case=N repeats=5` for every case and no failure lines.
Keep capture logs under the ignored output directory. Each case runs five
full/tiles/spans comparisons, checks allocation guards and exact CI8 CRC, clears
an offscreen render target, and requires its RDP result to match the independent
Pillow RGBA5551 golden. No screenshot is captured.

Remove the hook before any production build:

```sh
python tools/verify/sc64-gif/inject.py \
  src/rtk/rtk_gpu_n64.c build/n64-sc64/test/sc64-gif/injection --remove
tools/build.sh n64
```

Removal restores the exact backed-up bytes only when both source and backup
still match their recorded hashes. Concurrent edits cause refusal rather than
being overwritten. Keep the backup for review. Restore the normal ROM and
original hardware/theme configuration, remove only the owned SD fixture with the
console off, and verify normal boot/music using the existing hardware workflow.
The source, generated ROM and test SD file must not enter a production commit.

## What the timing means

`pi_us` measures cart-to-RDRAM transfer. `apply_us` includes packet validation,
CPU placement and conservative whole-plane cache publication. `rdp_us` includes
offscreen clear, submission and RDP completion. Palette initialization, SD
staging, reference-plane restoration, CRC calculation, allocation and logging
are outside these stage timings. Those synchronous operations can pause the UI
and audio: this is not an end-to-end decoder, animation-cadence or 60 FPS test.

The fixture provides a prior reference plane outside timing; a running receiver
already owns that plane. Production plane-history/version management still has
a cost and requires separate measurement. Full, tiles and spans produce the
same output, so dense changes can choose full output if scatter costs outweigh
transfer savings. Do not assume dirty output always wins.

## Packet contracts

Both packets start with eight big-endian 32-bit words: magic, generation, frame,
reference frame, `(width << 16) | height`, flags, item count and pixel-payload
bytes. Generation is 1 in these fixtures. The 512-byte global RGBA5551 palette is
supplied once out of band, including transparent index 255.

**GPD1 tiles:** magic `0x47504431`, flags 1, item count 0–1200. The 32-byte header
is followed by a 150-byte mask and 10 zero padding bytes. Tile `y*40+x` uses bit
`tile%8` in byte `tile/8`, least-significant bit first. Packed payload begins at
byte 192: 64 bytes per active 8×8 tile, row-major, increasing tile order. Packet
length is `192 + 64*count`.

**GPR1 row spans:** magic `0x47505231`, flags 2, item count 0–240 nonempty rows.
Following the header are 240 descriptors, each two big-endian 16-bit values
`x,count`. A zero count requires zero x. Nonempty x/count are multiples of eight
and stay within width 320. Payload starts at byte 992 and concatenates the
nonempty spans in row order. Tail padding rounds total length to 16 bytes.

The fixture container is not the FPGA wire format. Its `GSB1` header holds case
count, entry-table offset 528 and total size, followed by the 512-byte TLUT and
64-byte case entries. Each entry holds frame/reference, reference-plane offset,
full-plane offset, tile-packet offset/length/count, CI8 CRC, RGBA5551 CRC,
span-packet offset/length/row count/payload bytes and three reserved words.

A real producer must publish complete immutable packets and retain output slots
until PI completion. The consumer must validate generation/reference identity
before applying updates, accumulate changes across skipped frames, and track
each reusable plane's content version and RDP retirement. Cancellation must
finish before theme/launch memory is reused. These lifecycle properties are not
proven by a synchronous receiver microbenchmark.

## Feed actual RTL output to the N64 receiver

`rtl_fixtures.py` imports emitted GPD1 packets byte-for-byte, verifies their
header/reference identity, applies them to independently decoded original-GIF
canvases, and compares the results to Pillow. It wraps those unchanged bytes in
the same diagnostic container, so the current receiver ROM needs no change.
The full-plane and row-span alternatives are host-generated comparison controls;
only the tile packets come from RTL.

```sh
python tools/verify/sc64-gif/rtl_fixtures.py \
  "/path/to/Final Fight/images/background.gif" \
  build/n64-sc64/test/sc64-gif/rtl \
  /path/to/rtl-output/original-0003.gpd \
  /path/to/rtl-output/original-0007.gpd
python tools/verify/sc64-gif/check_fixture.py \
  build/n64-sc64/test/sc64-gif/rtl/rtl-receiver-fixture.bin
```

For the durable runner, `original-0003.gpd` represents source frame 3 against an
initial index-255 canvas (`reference=0xffffffff`), and packet 0007 represents
frame 7 against frame 3. The durable runner excludes synthetic preflight cases
from its original-image exports. Keep the provenance
manifest, which records input packet paths and hashes. Future runner output
selection must be checked against that runner's source-frame mapping.

With the console off, preserve the existing owned SD fixture and deploy
`rtl-receiver-fixture.bin` under the receiver's fixed SD name
`sd:/phosphor/data/gif-span-fixture.bin`. Run `gifspanbench 0` and
`gifspanbench 1` for this two-case container. Restore or remove only the owned
fixture afterward using the hardware workflow above.

This bridges **RTL simulation output to the real N64 receiver**. It does not
mean the cart FPGA is running the decoder, and it does not measure FPGA clock
fit, live SD arbitration, streaming deadlines or whole-UI performance.
