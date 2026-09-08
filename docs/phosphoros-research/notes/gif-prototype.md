# Original GIF FPGA conversion prototype

This follows the user's clarified request: decode the original Final Fight GIF
on the FPGA and choose an output format the N64 can consume. It does not require
an offline GIF64 conversion workflow. The [testing ledger](../sc64-ui-testing.md)
owns the current hardware state and links the earlier research.

## What is actually tested

- Experimental RTL decodes all 1,717 original Final Fight images, not GIF64 input.
- An integrated simulation composes transparency in an external CI8 canvas and
  emits packed changed tiles. An independent receiver checks the result.
- A temporary PhosphorOS diagnostic on the real 4 MiB N64 compares full frames,
  changed tiles and changed row spans, using the original GIF's pixels/palette.
- Two packets emitted by the RTL simulator are also read and rendered by the
  real N64. Their bytes are imported unchanged, independently checked against
  the source, and verified again on the console.

The physical SC64 FPGA still runs its original design. Simulation plus an N64
receiver test does **not** establish physical FPGA decoding, whole-UI FPS or
continuous audio performance. The diagnostic intentionally runs synchronously;
staging, CRC checks and repeated offscreen draws can pause normal service.

Source GIF SHA256:
`d48de154f477e6753b14d5d1a1fa7c5edcefe17c3688e9afbe790907bc7056b7`.
Provenance is recorded in the [FPGA research](fpga.md). The file has a single
256-entry global palette, transparency index 255, full-canvas images and no local
palettes or interlacing. The canvas begins at index 255; that palette entry has
zero alpha and is never painted opaquely. Generic GIF support remains broader
than this tested subset.

## N64 output-format measurements

The same diagnostic ROM and Final Fight theme are used throughout each paired
comparison. Each row is the mean of five repetitions. Times below include PI
transfer plus CPU packet validation/application and cache publication. They
exclude FPGA decoding/composition, initial palette transfer, SD staging, CRC
checks and normal UI work. Offscreen clear/draw/completion adds roughly 3 ms to
each mode and is recorded separately in the raw logs.

| Source frame / changed tiles | Full CI8 | Packed tiles | Row spans | Lowest observed receiver cost |
|---|---:|---:|---:|---|
| 1 / 2 | 15.660 ms | 0.774 ms | 0.843 ms | Tiles; small difference from spans |
| 2 / 0 | 15.642 ms | 0.715 ms | 0.813 ms | Tiles; small difference from spans |
| 423 / 259 | 15.649 ms | 6.713 ms | 8.036 ms | Tiles |
| 621 / 1,054 | 15.641 ms | 24.878 ms | 20.900 ms | Full frame |
| 1030 / 123 | 15.640 ms | 3.558 ms | 2.827 ms | Row spans |
| 1713 / 1,200 | 15.648 ms | 28.112 ms | 23.226 ms | Full frame |

All **90 renders** in this three-format comparison match the independent Pillow
RGBA5551 reference and pass allocation guards. An earlier full/tile comparison
adds 60 passing renders. Order is fixed rather than randomized; these are
diagnostic observations, not statistical confidence intervals or universal
format-selection thresholds.

Full CI8 transfers 76,800 bytes. GPD1 tiles use a 192-byte header/mask prefix and
64 bytes per changed 8x8 tile. GPR1 row spans use a 992-byte prefix and aligned
contiguous pixel spans within each affected row. Span copies reduce CPU scatter
work, but sometimes transfer enough additional bytes to lose to tiles. A dense
tile update loses to a direct full-frame read because it adds substantial CPU
copy work.

The evidence favors selecting an output representation according to update
shape and receiver cost. It does not support always expanding into full frames,
or always sending tiles. The current RTL emitter implements GPD1; full-frame
selection and GPR1 emission are not yet implemented in that emitter. No new
production format is selected by these experiments.

## Actual RTL packet replay on N64

The simulator's packets for frames 3 and 7 are imported unchanged. Frame 3 is
the initial 1,200-tile keyframe, referencing the initial all-255 canvas; frame 7
references frame 3 and updates 150 tiles. Five repetitions of full/tile/span
controls for each case produce **30 more passing N64 renders**, matching the
source goldens. Tile mode consumes actual RTL-produced bytes; span mode is a
host-generated comparison. There are 180 passing offscreen renders across this
round, not 180 frames of real-time FPGA playback.

## RTL correctness and resource checks

The [reference LZW suite](../../vendor/sc64/tests/gif/README.md) passes 1,772
cases: all original images, 55 synthetic/error cases and 200 additional
cancellation checks. It covers code growth, full dictionaries, clear/end codes,
KwKwK, truncation, output limits and input/output stalls. Parent reruns pass;
truncated test-fixture headers also fail loudly. The core maps to 14 DP8KC
blocks, 509 LUT4 and 211 flip-flops under Yosys MachXO2 technology mapping.

The [compositor suite](../../vendor/sc64/tests/gif/compositor/README.md) connects
LZW, external canvas memory, transparency composition and GPD1 output. It passes
all 1,717 images and produces 430 packets / 10,245,568 bytes. The harness emits
every four images and the final remainder to exercise reference retention; this
is not the OS4 playback schedule. Cancellation drains pending memory access;
stale ACKs, memory errors, malformed metadata, guards and backpressure are tested.

Replacing the compositor's large dynamically indexed dirty-bit vector with
synchronous byte RAM reduces its mapping from 6,130 to **630 LUT4**, with
240 flip-flops and one DP8KC block. The output remains identical. Simulated
cycles increase about 3%. This is a resource improvement in the prototype,
not a measured UI speed improvement.

The [cached dictionary variant](../../vendor/sc64/tests/gif/cached/README.md)
also passes all 1,772 fixtures and 200 cancellation checks in an independent
parent rerun, plus four external-memory failure/cancel/restart checks. A
512-entry cache and external 16 KiB dictionary reduce its mapping to **6 DP8KC,
635 LUT4 and 300 flip-flops**. Original-image decoding takes 1,257,856,312
modeled cycles, versus 485,920,630 for the dedicated-memory reference. This
trades memory for latency; neither model establishes cartridge throughput.

The [cached decoder/compositor simulation](../../vendor/sc64/tests/gif/cached-compositor/README.md)
serializes dictionary and canvas requests through one synthetic service. All
1,717 images pass, with the same 430 packets / 10,245,568 bytes; sixteen exported
packets are byte-identical to the dedicated pipeline. It records 1,860,815,157
modeled cycles, 250,163,825 modeled 16-bit beats and 823,752 contended grants.
Its canvas latency differs from the earlier simulation, so cycle totals are
not an isolated cache A/B comparison. Source fetch, output writes, refresh and
normal cartridge competition remain outside this model. Combined cancellation
ownership and real memory arbitration still require implementation.

Yosys mapping does not establish placement or timing closure. An attempted
full-SC64 open-source mapping failed to infer several existing memories properly;
its inflated logic counts are not credible baseline utilization. Do not add the
reference core's dedicated 14-block memory requirement to the production FPGA.

## What prevents a cartridge decoder test

SC64 already owns the required memory machinery:
[`mem_bus`](../../vendor/sc64/fw/rtl/memory/mem_bus.sv),
[`memory_arbiter`](../../vendor/sc64/fw/rtl/memory/memory_arbiter.sv),
[`memory_sdram`](../../vendor/sc64/fw/rtl/memory/memory_sdram.sv) and
[`memory_dma`](../../vendor/sc64/fw/rtl/memory/memory_dma.sv).
The missing bridge means adapting the GIF client's dictionary and canvas
transactions to that existing bus and adding client ownership. It does not
mean replacing SDRAM refresh/timing or building another memory controller.

The arbiter has four existing clients and gates non-N64 SDRAM requests during
an active PI reservation. A simulation can exclusively substitute the GIF
adapter for CFG to test the unchanged arbiter, but production integration must
also preserve CFG access. Output DMA can reuse the existing FIFO-to-memory
engine: the [reuse probe](../../vendor/sc64/tests/gif/dma-output/README.md)
passes sixteen original RTL packets with byte-exact memory output, guards,
parity, stalls, stop/drain and restart checks. The bounded FIFO, output-slot
ownership and actual simultaneous producer/consumer integration remain absent.

Double buffering is output ownership above these memory interfaces. Publishing
a completed slot and retiring it after PI transfer are necessary before the
producer can reuse it. The current cart backend already owns theme arenas and
invalidates them at theme changes/launch. A future GIF job must drain before
those owners reuse the memory; fixed addresses in a simulation do not reserve
that space in PhosphorOS.

The [actual-controller simulation](../../vendor/sc64/tests/gif/sc64-integration/README.md)
now passes all 1,717 images through the unchanged arbiter and SDRAM controller
using the adapter. It checks real command/address/DQM/DQ signals against a
digital chip model, with single-cycle CL2 read delivery aligned to the configured
270-degree SDRAM clock phase. Each scripted N64/USB/SD peer completes 335,425
checked word operations. All 251,246,900 grants pass priority and PI-reservation
checks; all sixteen exported packets match the earlier pipeline byte-for-byte.
An independent negative test delivering read data one cycle early fails readback,
confirming that the checks are sensitive to data timing.

The workload totals 2,747,802,158 controller clocks: mean 1,600,351 per image and
maximum 2,619,056 including occasional packet emission. At the modeled 100 MHz,
these correspond to approximately 16.00 ms mean and 26.19 ms maximum; 436 images
exceed 1,666,666 clocks. These are simulation-derived stage costs, not measured
cartridge latency. Source fetching, output RAM writes, PI transfer, RDP work and
normal UI/audio are still excluded. This result therefore does not demonstrate
60 FPS or sufficient end-to-end throughput. Analog timing closure, production
CFG coexistence, complete cancellation ownership and board testing remain open.

The official SC64 tool image provides Diamond 3.13 but no current license.
The pinned fork's license expired on 23 February 2025; current upstream no longer
ships that file and directs builders to obtain a personal annual license.
MachXO2 is supported by the free Diamond license. See the
[official SC64 build instructions](https://github.com/Polprzewodnikowy/SummerCart64/blob/main/docs/05_fw_and_sw_info.md)
and [Lattice licensing](https://www.latticesemi.com/license).

A valid license enables the authoritative baseline/candidate fit and timing
checks. It does not by itself complete the missing SC64 memory/register bridge,
job ownership, reset/cancellation, firmware capability negotiation or broader
GIF compatibility. Those must be integrated and verified before flashing.
No FPGA clock, pin assignment, CIC, save or recovery path is changed here.

## Exact repeated-image candidate

The [payload reuse probe](../../vendor/sc64/tests/gif/repeated_payload.py)
finds 407 consecutive images with byte-identical compressed data and identical
metadata in original Final Fight. For its retain disposal mode, independently
composed Pillow RGBA pixels also match exactly for every candidate. The largest
compressed image payload is 25,747 bytes. An exact runtime comparison might
avoid redundant decoding while preserving frame identity and delay, without
creating converted files. This remains unimplemented: reading/comparing source
bytes, buffering them, output-reference bookkeeping and preserving timing all
have costs. It is not a measured throughput improvement.

## Reproduce and retain evidence

[Receiver research tools](../../tools/verify/sc64-gif/README.md) generate the
reference fixtures, import actual RTL packets, install/remove the temporary
diagnostic with exact source backups, and describe the hardware commands.
Python is a developer test dependency, not a proposed theme preparation step.

Raw artifacts live under `build/sc64-ui-all/`: `receiver-case-*.log`,
`span-case-*.log`, `rtl-receiver-case-*.log`, `receiver-results.json`,
`span-results.json`, the FPGA/compositor build logs and SD hash readbacks.
The production source and ROM are restored after the diagnostics; current
restoration evidence belongs in the maintained ledger.
