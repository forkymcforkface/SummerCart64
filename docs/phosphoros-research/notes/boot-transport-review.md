# Software-only boot transport review

Reviewed 2026-09-07 against SC64 `bde096018db1e23b646fd19b23ccdf1ed8ae5059`.
This note owns the SD/MCU command-path audit; the [boot ledger](../boot-testing.md)
owns acceptance and installed-state statements. No hardware is changed by this
review.

## Findings ranked for further work

| Rank | Candidate | Concrete mechanism and expected scope | Required measurement and safety gates |
|---|---|---|---|
| 1 | One full-duplex DMA transaction for register reads | [fpga_reg_get](../../../sw/controller/src/fpga.c) sends a two-byte header and receives four bytes through separate DMA calls. [hw_spi_tx/hw_spi_rx](../../../sw/controller/src/hw.c) each configure and disable two DMA channels. Receive all six bytes while transmitting the identical header and four zero bytes; discard the first two received bytes. Wire length, clock and CS frame stay identical; one DMA setup replaces two. This is a new candidate, with no quantified boot gain yet. | Actual-source read/CS/byte tests, arbitrary garbage in the two discarded bytes, unchanged 8 MHz RTL phase/gap tests, target build and original-loader comparison; then paired installed boot phases, command latency, SD hashes and error/save/USB checks. Keep separate TX/RX buffers, RX-before-TX enabling, both completion waits and final SPI-busy wait. |
| 2 | Boot-specific reassessment of CFG reply batching | [cfg.c](../../../sw/controller/src/cfg.c) success/error replies still write three adjacent registers separately. Existing helper can preserve DATA_0, DATA_1, DONE ordering while reducing 18 to 14 wire bytes. Already tested and rejected for UI FPS, so this is not a new discovery. | Only revisit if current boot traces show enough command traffic. The [UI ledger](../ui-testing.md#cfg-reply-batching-hardware-experiment) explicitly rejects attributing its incomparable boot samples to the change. A fresh boot A/B is required; do not add the old UI delta to a boot claim. |
| 3 | Streaming extent fallback for heavily fragmented menus | [menu_read](../../../sw/bootloader/src/menu.c) supplies a 128-DWORD map. [CREATE_LINKMAP](../../../sw/bootloader/src/fatfs/ff.c) walks the complete size-bounded chain to determine required map size, then more than 63 extents cause `f_read` fallback and another chain traversal. A private bounded streaming extent consumer could avoid duplicate traversal and retain coalescing on fragmented cards. No benefit expected for the normal fitting/contiguous menu. | First compare metadata reads for 63/64/128 extents with the actual FatFs fixtures. Preserve EOF bounds, invalid/truncated/cyclic chain rejection, LBA32 overflow, 64 MiB limits, errors and read-only ownership. Do not weaken the generic FatFs map contract or introduce persistent extent caches. Hardware experiment only if the user's actual menu exceeds the map capacity or fragmented fixtures show a useful supported-card benefit. |
| 4 | CFG argument read grouping | [cfg_cmd_check](../../../sw/controller/src/cfg.c) reads adjacent DATA_0 and DATA_1 separately. One burst saves two wire bytes and a CS frame per new request. Previously proposed in the [MCU audit](mcu.md), not implemented here. | Read prefetch touches the next CFG_CMD register; its current RTL read is side-effect-free. Verify queued retries, no-pending paths, AUX handling, stable arguments until DONE and back-to-back commands. Do not read arguments every idle loop. |
| 5 | Polled SPI only for very short transfers | The same DMA descriptor cost motivates a short-transfer CPU path in [hw.c](../../../sw/controller/src/hw.c). New, lower-priority proposal; larger scope and more hardware semantics than rank 1. | Review STM32 FIFO/data-width/overrun behavior and mixed DMA/CPU operation before implementation. Measure crossover on the MCU. No clock change. Deferred in favor of the narrower full-duplex experiment. |

## Existing work that should not be repeated blindly

Bounded menu extents, bootloader cursor reuse, c1 compression, SPI byte batching
and SD command/DMA write grouping are installed. CMD17/CMD24, metadata reordering,
MCU O2 and command IRQ polling already lack useful measured boot gains. Remaining
MEM/USB register write grouping mainly benefits USB/save traffic; normal menu
data already goes directly from SD to cart memory. SD long-response read bursts
only affect cold initialization's CSD/CID reads, so their ceiling is small.

Extra CFG servicing previously measured a gain, but its button debounce and
writeback scheduling qualification remains incomplete. Moving or duplicating
services is not interchangeable with reducing the cost of the existing call.
No proposal skips pending save writeback, SD initialization requirements, CRC,
timeouts, CIC, RTC settings, RDRAM initialization or required reboot state.

## Isolated full-duplex experiment

Artifacts are in the PhosphorOS checkout's ignored
`build/software-boot/spi-read/`. `prepare.py` copies the controller source into
that directory, writes a three-file candidate patch and extracts baseline and
candidate register-read functions for `compare.c`. Tracked controller source is
unchanged. The candidate adds `hw_spi_transfer`; no existing helper by that name
exists in this baseline. Its descriptor sequence follows the existing RX/TX
helpers, with memory increment enabled on both separate buffers.

The host test passes 168,608 cases with fatal ASan/UBSan checks. It covers every
8-bit register ID, boundary/random response values,
all 65,536 possible discarded two-byte headers, exact six MOSI bytes, one CS
frame, and two-to-one helper-call reduction. A negative control with an incorrect
header offset compiles and fails its result assertion. It mocks the transfer primitive;
it does **not** simulate STM32 DMA registers or prove electrical behavior.
The RTL test uses current `mcu_top.sv` and `mcu_spi.sv` with six-byte register
reads at 8 MHz, 20 half-nanosecond phase offsets, and zero/500 ns header gaps;
all 40 cases pass with zero mismatches. `host-results.log`, `rtl-results.log`,
`negative-results.log`, and both source manifests preserve the evidence.
It is an ideal-pin simulation, not an MCU DMA or board-skew model.

The register parser issues the read when the address byte finishes; the SPI
engine loads output data on the next rising clock. Eliminating the software
header gap therefore needs an explicit zero-gap RTL check. The two received
header bytes are unspecified and must never contribute to the returned word.
The parser also prefetches the next register after the final data byte in both
baseline and candidate; this experiment does not introduce a new read burst.

### Target builds and stack/DMA review

Clean Cortex-M0+ builds with original GCC 9.2.1 succeed without warnings/errors.
`target-build-gcc9.sh` runs the existing `app.mk` pipeline in the isolated source
copies using `sd2snesfw-dev:arm` and `CXX=arm-none-eabi-gcc`, as the application
contains no C++. Both embed the preserved original loader instead of rebuilding
loader code from the candidate's changed `hw.c`/`fpga.c`.

| Image | Bytes | SHA256 |
|---|---:|---|
| Rebuilt current baseline | 21,712 | `b294d1ca45b9f948f0d135a6fde354cc3cf4b1f41184c74fc41939a86cc717be` |
| Full-duplex candidate | 21,776 | `2ff985dc27e726c2d5c8a64c313b2b4065361f723d7e7fc51ad2c8f961415d8a` |

The baseline exactly matches the earlier installed production artifact. Both
first 4,096 bytes exactly match original loader SHA256
`9a2a42052e3dbf292ff514cd0f61daf9981e8b2cd163a829b2c707c35aeb5bec`.
`target-results-gcc9.json` records these assertions. Initial GCC 13.3 builds also
pass, but produce a different baseline (21,656 bytes); those remain separate
artifacts and are not suitable for attributing a change against installed GCC9
firmware without first replacing/re-measuring the baseline.

The GCC9 disassembly reserves 24 bytes in `fpga_reg_get`, places the six-byte TX
buffer at SP and RX buffer at SP+8, and uses an eight-byte helper frame. Both
buffers remain live until both DMA counts reach zero. The existing DMA defaults
use byte transfers; enabling MINC for both channels writes all received header
and response bytes without TX/RX overlap. RX is armed before TX; the helper
disables both channels at completion; the existing `hw_spi_stop` then waits for
SPI BSY to clear before raising CS. Separate external-function calls and the
existing non-LTO build retain the existing buffer visibility model. This is a
source/disassembly review, not a claim that a host mock validates STM32 DMA.

The reviewer performs no hardware operations. Parent-controlled real-cart
behavior and boot A/B belong in the boot ledger; this report does not independently
assert performance acceptance.

### Existing regression-runner integration

`tests-integration/tests.patch` extends the existing `tests/run.py`, `spi.c`,
`groups.c`, and README in an isolated directory. Cursor and bounded fixtures
remain unchanged. The default requires the actual full-duplex helper definition
and a call from the extracted register-read function; `--spi split` explicitly
tests historical byte/group batching. This prevents removal of the optimization
silently passing a fallback test mode.

The complete normal runner passes both the candidate and unchanged historical
source: 12,571 cursor statuses / 10,868 I/O operations, the full actual-FatFs
bounded/error/64-MiB fixture set, 168,608 SPI cases / 337,216 operations, and
93,248 grouped SD cases. Source manifests and logs are under
`integration-results/` and `integration-historical-results/`. SPI wire traffic
and frame counts remain unchanged by the full-duplex change; the additional
assertion verifies one helper transaction per read. The host transfer primitive
remains mocked, so these results supplement the separate RTL and target checks.

## Parent hardware disposition

The [software-only boot round](../boot-testing.md#software-only-boot-round--2026-09-07) supersedes the candidate-only status above. Logo removal and full-duplex register reads are retained after actual-source checks, N64 comparisons and verified production readback. Packed-logo encoding is superseded and omitted from production.
