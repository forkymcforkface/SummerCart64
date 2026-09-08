# LZW-only stock-pin resource experiment

Research only. This measures a smaller architectural alternative: the FPGA
decodes LZW to a raw CI8 index plane; the N64 must implement GIF composition.
It neither implements theme parity nor produces a deployable bitstream.

```powershell
docker run --rm -v D:/Documents/GitHub/phosphor-os:/repo sc64-open:diagnostic-lpf /usr/bin/python3 -B /repo/vendor/sc64/tests/gif/stock-lzw-fit/run.py /repo/build/sc64-open-memory/release-conversion/inputs.json /repo/build/sc64-bounded/agent-core /repo/build/sc64-transport-mcu/frozen/gif_transport_mcu_mux.sv /repo/build/sc64-open-timing-options/nextpnr-machxo2 /repo/build/sc64-stock-lzw-fit/final
```

`run.py` executes the shared [stock-fit runner](../stock-fit/run.py) with this
directory's generator and gate. `generate.py` first invokes the original
generator, then applies exact checked substitutions to its isolated pipeline.
The stock top/MCU taps, original release manifest, paired guarded RAM mapping,
pin contract comparison, real disconnected-RTL negative gates and diagnostic
packing mechanics remain shared. The wrapper hashes and shared-helper hashes
are recorded separately. No production source is edited.

The CI8 compositor instance is removed. Its canvas requests are tied inactive;
the existing external dictionary adapter remains. The bounded decoder's output
index bytes feed the existing output FIFO directly. Starting a frame launches
a 76,800-byte output DMA; no GPD1 header, dirty mask or packet ACK is produced.
The source/output DMA, two FIFOs, four-client mux and GIF-only cancellation
drain remain. New jobs are rejected during cancel while pending bus requests
continue draining. The MCU memory owner and stock arbiter/SDRAM/USB/SD paths
remain intact. There are no additional physical ports.

The tested paired mapping/packing result is:

| Resource | Stock | LZW-only | Composed stock-fit |
| --- | ---: | ---: | ---: |
| TRELLIS_COMB | 5,674 | 7,631 | 8,863 |
| TRELLIS_FF | 3,023 | 3,783 | 4,288 |
| Physical EBR | 22 | 25 | 26 |
| TRELLIS_RAMW | 8 | 24 | 24 |
| Physical I/O | 101 | 101 | 101 |

Removing composition saves 1,232 packed logic positions, but the raw decoder
still exceeds 6,864 by 767 (11.2%). This candidate does not fit. The three
additional EBRs hold the cached dictionary (two) and 512-byte stack (one).
Both FIFOs remain in sixteen additional distributed RAM blocks. No resources
are double-counted for stock memory arbitration or SDRAM control.
The parent independently reproduces this paired result in
`build/sc64-stock-lzw-fit/parent`.

A separate [area-mapping experiment](../../open-toolchain/area-map/README.md)
uses `-noccu2` on this LZW design. Its saved packed netlist at
`build/sc64-area-map/lzw/soft-carry/packed.json` contains 6,630 TRELLIS_COMB,
3,765 FF, 25 EBR and 101 I/O (234 logic positions below capacity).
That is a different mapping candidate, not the default result above. Aggregate
resource capacity is not placement, routing, timing or equivalence proof.

## Remaining behavior and qualification

The stock-fit [unsafe research address and command limitations](../stock-fit/README.md)
all apply. Generation/ACK/frame metadata and transparency controls become
unused and are optimized away; minimum code size and source length remain
live SPI inputs. A0 still exposes one-cycle completion/retirement pulses that
MCU polling can miss. This is not a supported firmware or N64 submission API.

Only full 320x240 raw image output is represented. Short output, malformed GIF
data or decode error leaves an incomplete fixed-length output DMA until the
caller explicitly cancels and waits for retirement. There is no automatic
error retirement.
The structural gate checks control/status connectivity, real start/status
disconnection rejection, and exact decoded-index/output-byte wire identity.
These checks do not replace cycle-level or original-GIF behavioral tests.

An N64 receiver would still need GIF framing, palette handling, transparency,
rectangle placement, disposal, timing and safe plane ownership. Full index
planes increase PI traffic compared with dirty packets; no N64 cost or frame
rate is measured here. Performance and parity cannot be inferred from savings
in synthesized FPGA logic. Existing diagnostic EFB/ODDR/FIFO barriers remain;
no placement, route, bitstream generation or hardware operation occurs.

## Bounded functional transport test

```powershell
docker run --rm -v D:/Documents/GitHub/phosphor-os:/repo sc64-gif-test:local python3 -B /repo/vendor/sc64/tests/gif/stock-lzw-fit/behavior.py "/repo/build/sc64-ui-research/original-final-fight/Final Fight/images/background.gif" /repo/build/sc64-bounded/agent-core /repo/build/sc64-transport-mcu/frozen/gif_transport_mcu_mux.sv /repo/build/sc64-stock-lzw-fit/behavior-review
```

`behavior.py` applies the same `raw()` transform to the original functional
transport wrapper. It retains actual source/output DMA, stock arbiter/SDRAM
controller and the shared SDRAM command model. The four-client mux is present;
its MCU client is inactive in this probe. Stock N64/USB/SD contention is active
during the eight normal frames. This does not test the new stock SPI job API.

Append `--all-frames` to check every original image through the same transport
and retain the four cancellation cases. The default remains eight images for
the focused gate. Both modes require one successful comparison per selected
image and all four cancellation results before writing the success report;
the report records the selected count and mode. Full-sequence coverage still
does not test palette composition, the SPI job API or physical hardware.

The fresh compact-core run at `build/sc64-gif-qualification/raw-full` passes
all 1,717 original Final Fight frames (131,865,600 bytes) and four cancellation
cases with `--all-frames`. Fixture SHA256 is
`bc41d5ab5ad709a8d9edc4bdb05082186720d534390cf0a563027521b052e5f8`.
The default-eight regression with the normalized synchronous stack also passes;
a copied fixture with one expected output byte changed fails the packet
equality assertion. Evidence is under `build/sc64-gif-qualification/stack-raw`.

The first eight original Final Fight image payloads are decoded independently
with `gif_reference.decode`. All 76,800 stored bytes and the accepted index
stream match each raw plane, including index 255; these are not composited
canvases. The unused output tail retains its sentinel. Four cancellation cases
pass: invalid minimum-code-size error and pending output-DMA request under PI
reservation, each with pulsed and held cancellation. The pending output request
is observed held for 128 cycles before cancellation; PI reservation is then
released to let issued work drain. New starts during abort are rejected, no
writes occur after retirement, and distinct original image 1 restarts exactly.

Results and exact source hashes are in
`build/sc64-stock-lzw-fit/behavior-review/{results.log,result.json}`. Earlier
`behavior`/`behavior-final` runs failed their pressure-setup assertions: blocking
all memory did not guarantee a full FIFO, and blocking after an already-granted
write did not guarantee a pending request. The retained case observes the first
pending output request before reservation instead. This is functional simulation
evidence for eight images and four cancellation cases, not complete decoder,
electrical SDRAM, real MCU SPI, N64 playback or hardware qualification.
The final provenance run includes the reference decoder, fixture, runner and
tool versions. The parent independently repeats all twelve cases in
`build/sc64-stock-lzw-fit/parent-behavior-final`.
The provenance-strengthened repeat at `behavior-provenance` also passes and
records `behavior.py`, the independent `gif_reference.py`, fixture hash and
Verilator/Python versions alongside the RTL and shared harness hashes.
