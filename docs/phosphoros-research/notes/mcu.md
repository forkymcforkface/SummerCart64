# SC64 MCU and UI throughput research

This research note supports the [maintained testing ledger](../sc64-ui-testing.md).
The user prioritizes **original GIF files without offline conversion**.
Direct on-device decoding is a primary research goal; a generated cache
may be optional and disposable. Current GIF64 tests describe the existing
baseline rather than a required future asset workflow. Proposed ownership
must follow [the application architecture](../architecture.md).

Raw artifacts named below are local, ignored files under
`build/sc64-ui-research/`; the repository does not distribute those logs,
binaries, assets or fixtures. Completed results are preserved here and in
the ledger. Hardware/installed-state statements in the ledger take
precedence over the earlier audit snapshot below.

Updated 2026-09-05. Source: vendor/sc64 at
`fdb5cc68634cc1f9fcaf347dae2ad7025f51c422`, current PhosphorOS tree and
its pinned libdragon sources. This agent performed no hardware operations,
firmware updates, or production edits. Parent owns hardware comparisons and
the durable testing ledger.

## Main conclusion

MCU firmware can shorten SD/USB command stalls. It cannot speed a cached UI
frame that only executes N64 CPU/RSP/RDP work. Establish slow-frame attribution
first: 16.7 ms frame intervals are already approximately 60 Hz; source GIFs
with longer frame delays must retain their original cadence.

The current GIF64 backend already uses cart SDRAM caching, bounded stream
windows, prefetch, asynchronous PI DMA, CI8 planes, and RDP blits. Recommending
those as entirely new optimizations would duplicate existing work. The remaining
SD-to-cart phase is synchronous and is a better integration target than adding
another generic cache.

## Current work and completed test

Hardware follow-up rejected CFG reply batching for this UI goal: Final Fight
47.4 to 47.6 FPS and Sunset Drive 29.3 to 29.4 FPS are too small to justify
retaining the change. The five-change production MCU has been restored and
readback verified. The [ledger](../sc64-ui-testing.md) records completed repeat baselines and
final menu/configuration restoration. Production boot/runtime checks pass. The host/build evidence below
describes the tested candidate and remains useful despite its rejection.

Narrow candidate: batch command reply registers using the already installed
`fpga_reg_set_words`. Source change is only two functions in
[sw/controller/src/cfg.c](../../vendor/sc64/sw/controller/src/cfg.c): success and error replies. The three adjacent
registers are DATA_0, DATA_1, CMD; DONE remains the final write.

Artifacts under `cfg-reply/`:

- `candidate.patch`: applies to the current fork; preserves all five installed optimizations.
- `controller/build/app/app.bin`: 21,712 bytes, same size as installed MCU baseline.
- SHA256: `22f35ce0a0eb846bc35e567d1c6e88974ee005307b30773216b87df6fbb250fe`.
- First 4096 loader bytes exactly match baseline; loader SHA256
  `9a2a42052e3dbf292ff514cd0f61daf9981e8b2cd163a829b2c707c35aeb5bec`.
- `host-results.log`: 200,000 actual-source success/error replies, ASan/UBSan,
  `-Wall -Wextra -Werror`; byte values, order, queue clearing, and DONE timing match.
- The actual unchanged `cfg_cmd_check` additionally passes no-pending,
  capture, 1,000 deferred retries retaining arguments, error completion,
  and fresh-command-after-error tests. AUX packet handling is not exercised.
- `arm-build.log`: Cortex-M0+ GCC 9.2 build. The image lacks libstdc++, so
  the C-only application links with `CXX=arm-none-eabi-gcc`; first g++ attempt
  failed at missing libstdc++, and is not counted as a successful build.
- `cfg-generate.py` extracts tested functions from actual source and prepares
  the isolated source copy. `cfg-reply/test.c` checks register effects at each
  completed word, rather than waiting for CS deassertion.

Reply wire traffic falls from 18 to 14 bytes and 3 to 1 CS frames.
At the existing 8 MHz SPI clock that removes exactly 4 microseconds of wire
time per reply, plus unmeasured software/CS overhead. This is not a measured
frame-time gain. A 32 KiB direct-cart read normally sends SECTOR_SET and READ,
so the reply portion alone saves 8 microseconds. Real idle UI could see none.

RTL source safety review: [fw/rtl/mcu/mcu_top.sv:836](../../vendor/sc64/fw/rtl/mcu/mcu_top.sv) stores DATA_0 and
DATA_1 independently; `:844` handles CMD and DONE after them. Register write
auto-increment already supports the installed SD grouping helper. No clock,
SD command, timeout, updater, loader, or loop scheduling changes.

Hardware A/B and MCU restoration/readback are complete; there is no hardware
acceptance claim. No SD scratch/save qualification was performed because the
candidate was rejected. The comparison is recorded in the maintained ledger.

## Candidate ledger

| Candidate | Source / mechanism | Status and cost | Safety / next test |
|---|---|---|---|
| CFG reply write grouping | [cfg.c:173](../../vendor/sc64/sw/controller/src/cfg.c), `:180`; reuse [fpga.c:49](../../vendor/sc64/sw/controller/src/fpga.c) | Host/ARM tests pass; hardware gain negligible | Rejected for UI goal; production MCU restored |
| CFG argument read grouping | [cfg.c:166](../../vendor/sc64/sw/controller/src/cfg.c); DATA_0/DATA_1 adjacent | New proposal; 12 to 10 wire bytes per capture, one fewer CS | Read burst speculatively reads next CFG_CMD register. RTL `:465` is side-effect-free, but verify pending stability and exact waveforms before implementation |
| Remaining memory/DMA register grouping | [fpga.c:72-115](../../vendor/sc64/sw/controller/src/fpga.c); [usb.c](../../vendor/sc64/sw/controller/src/usb.c) DMA setup | New proposal; MEM_ADDRESS/SCR and USB ADDRESS/LENGTH/SCR have trigger-last ordering | Primarily USB/save/launch traffic, not steady rendering. Test each owner separately; preserve odd-length and FIFO semantics |
| Runtime SD cursor reuse | [libdragon/src/libcart/cart.c:1694-1756](../../libdragon/src/libcart/cart.c) | New runtime opportunity: each 8 KiB RDRAM chunk still sends SECTOR_SET; direct-cart reads also always send it | Bootloader cursor optimization does not modify libcart. All reads/writes/errors/init/direct register commands must invalidate or update one shared cursor; otherwise wrong-LBA risk. Trace first |
| Atomic READ_AT command | current cfg stores one global `sd_card_sector`; libcart uses SET then READ | Firmware + N64 protocol extension could halve request/reply count without cached cursor state | Needs version/capability negotiation, request validation, backward fallback, all callers and USB ownership audited; prototype host protocol first |
| Async SD-to-cart prefetch | `cart_sc64_n64.c:1268` media_fill calls synchronous stage_slice; libcart `__sc_sync` waits | Potentially meaningful frame stall reduction by overlapping SD DMA with N64 rendering | Existing protocol start/poll may suffice without new firmware. Must reserve cart command channel; USB status, sound SD refill, save operations cannot interleave. Resolve FAT extents before asynchronous launch. Owner-held completion/cancellation, never generic frame yielding |
| Larger or adaptive prefetch slices | `MEDIA_FILL_SLICE=32KiB`, gif64 fill32KiB/prefetch80-128KiB | Application experiment, not firmware. Fewer commands can improve throughput but lengthen synchronous frame stalls | Compare p95/p99 and audio underruns, not only MB/s; retain bounded owners |
| Extra cfg servicing | [app.c:39-51](../../vendor/sc64/sw/controller/src/app.c) | Already tested in boot research; about 3.1 ms menu/10 ms frontend improvement then | Still held: 64-iteration rear-button debounce and writeback fairness. Not a new discovery or accepted UI improvement |
| Single-sector CMD17/CMD24 | [sd.c:533-600](../../vendor/sc64/sw/controller/src/sd.c) | Already tested; no useful boot improvement; not retained | Small cached metadata requests are already coalesced into4-sector reads. Only revisit if frame traces show frequent uncached singles |
| Larger SD block count | MCU max256 plus FPGA8-bit count | Already simulated:257 wraps to1; not safe as MCU-only patch | No reason to change for32KiB/64-sector prefetch. Coordinated RTL/MCU only after throughput evidence |
| 16MHz SPI | [hw.c](../../vendor/sc64/sw/controller/src/hw.c) uses64MHz /8 | Previously simulated read corruption; rejected | No clock increase or flash proposed |
| MCU GIF decoder/converter | MCU `app.ld`:8KiB total SRAM,28KiB code; SPI8MHz | Poor fit; no implementation. Standard LZW dictionary alone commonly needs4096 entries plus prefix/suffix storage, and compositing needs a canvas | External-memory dictionary/canvas accesses add SPI bottlenecks. Prefer N64 conversion cache or dedicated FPGA decoder research; MCU is control plane, not pixel engine |
| Generic cart-side file cache | `fatcache_n64.c` already128KiB max metadata cache; cart backend whole-stream/ring/image caches | No new implementation justified | Firmware does not own filenames/FAT policy. New raw-sector cache requires exact write invalidation, memory reservation and USB/reset rules |

## Workload path and limits

[src/platform/libcart_sc64_n64.c](../../src/platform/libcart_sc64_n64.c) includes the pinned libdragon libcart
through `libcart_profile.inc`; it does not reuse SC64 bootloader disk code.
Thus compression/cursor/bounded menu loading improve boot but cannot directly
improve already running UI frames. Installed SPI byte/register grouping does
apply to runtime MCU command traffic.

[libdragon/src/libcart/cart.c:1694](../../libdragon/src/libcart/cart.c) splits RDRAM SD reads into at most16
sectors (8KiB) because it uses the fixed SC_BUFFER_REG buffer, then PI DMA.
Unaligned destinations add sector-sized bounce copies. Raising this count
without proving scratch capacity is unsafe. `sc_card_rd_cart:1732` writes
directly into cart memory and avoids that RDRAM staging loop. Existing
`fatcache_n64.c:65` already selects the direct-cart path for PI destinations.

[src/rtk/gif64_n64.c:63-66](../../src/rtk/gif64_n64.c) and `:970+` use asynchronous cart-to-RDRAM DMA,
but `media_fill` synchronously completes SD reads before declaring bytes ready.
The MCU itself waits synchronously in `sd_read_sectors`/`sd_sync`; the FPGA
already performs SD DMA. Rewriting MCU as a scheduler is unnecessary merely
to let the N64 execute independent CPU/RSP/RDP work during that wait.

Data-path bound: raw320x240 CI8 frames are76,800 bytes, or4.608 MB/s at60
frames/s; RGBA16 doubles this to9.216 MB/s. At8MHz SPI the absolute serial
payload ceiling is1 MB/s before command overhead. Routing pixel payload
through the MCU is therefore incompatible with that target. Existing SD and
PI data paths avoid routing pixels through the MCU. FPGA GIF decoding may
reduce N64 decode work, but still needs canvas/disposal/palette state and
cart-to-RDRAM transfers; FPGA feasibility belongs to the parallel RTL audit.

## Suggested next hardware sequence

1. Record baseline representative heavy theme: frame work versus VI wait,
   GIF decode/copy, SD/cart transfers, RDP cost and audio underruns. Keep
   background animation cadence separate from UI redraw rate.
2. A/B CFG replies with firmware-only change and unchanged frontend/assets.
   Reject if effect is noise; do not retain code solely because synthetic
   wire byte counts improve.
3. Measure a diagnostic with all current GIF frames resident in cart cache
   versus streamed, then compare SD-read time and PI-DMA time separately.
4. If SD stalls dominate, prototype asynchronous direct-cart transfer under
   existing media owner, with command-channel arbitration. If cached decode
   or rendering dominates, prioritize N64/RSP/RDP work instead of more MCU
   micro-optimizations.

This report lists proposals honestly: only CFG reply grouping was newly
implemented/tested by this agent. Existing boot tests are cited history;
asynchronous prefetch, READ_AT, runtime cursor caching and pixel offload
remain unimplemented research items.
