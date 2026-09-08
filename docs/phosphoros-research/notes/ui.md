# PhosphorOS UI / SC64 integration research

This research note supports the [maintained testing ledger](../ui-testing.md).
The user prioritizes **original GIF files without offline conversion**.
Direct on-device decoding is a primary research goal; a generated cache
may be optional and disposable. Current GIF64 tests describe the existing
baseline rather than a required future asset workflow. Proposed ownership
must follow [the application architecture](../../../../../docs/architecture.md).

Raw artifacts named below are local, ignored files under
`build/sc64-ui-research/`; the repository does not distribute those logs,
binaries, assets or fixtures. Completed results are preserved here and in
the ledger. Hardware/installed-state statements in the ledger take
precedence over the earlier audit snapshot below.

Status: source audit, original-GIF dirty-update models, and current profile
interpretation completed 2026-09-05. No production GIF implementation changed.
The maintained ledger owns hardware A/B and restoration status; historical
measurements below remain separate from this investigation's captures.

## Main finding

The useful target is the actual 16.67 ms NTSC UI frame budget. A 50 Hz PAL display has a 20 ms physical presentation period; preserve OS4 animation cadence rather than claiming 60 distinct presentations on that output. The SC64 firmware cannot execute RDP drawing or write N64 RDRAM as a bus master. It can prepare cart SDRAM and make CPU-initiated PI transfers cheaper, but textures still travel into RDRAM for the RDP.

The current background path first opens `background.gif64`
([bg.c](../../../../../src/rtk/bg.c)); failure falls back to normal GIF decoding.
PDSB frames use CPU LZ4 or raw bytes rather than GIF LZW. To meet the original-GIF
goal, a hardware decoder would instead consume the original stream and publish
composed updates. It need not write a GIF64 file. The later dirty-tile results
show why this is more promising than decoding to a full raw frame every time:
the measured Final Fight asset can use a stable CI8 palette and sparse updates.
A disposable runtime cache remains optional and needs existing owner/invalidation
contracts; it is not itself evidence of a warm-playback FPS gain.

## Current work and hardware boundaries

| Work | Current implementation / source | Implication |
|---|---|---|
| Frame ownership | [src/rgbpiui.c:225](../../../../../src/rgbpiui.c) through `:362`; prep/services before framebuffer acquisition, ordered RTK draw then present | Extend existing owner; no new frame loop or reentrant scheduler |
| Framebuffer slack | [src/rtk/rtk_gpu_n64.c:512](../../../../../src/rtk/rtk_gpu_n64.c) polls streams while `display_try_get` waits | Some transfer latency is already hidden; frame wait alone is not evidence of GPU saturation |
| Presentation | [src/rtk/rtk_gpu_n64.c:545](../../../../../src/rtk/rtk_gpu_n64.c) detach callback and deferred RSP syncpoint retirement | Removing waits or reusing a displayed plane risks tearing/use-after-free |
| Cart -> RDRAM | [src/platform/cart_sc64_n64.c:969](../../../../../src/platform/cart_sc64_n64.c), `:1439` asynchronous whole-record PI DMA, including split-block tickets | Already avoids a main-loop poll between each 16 KiB slice; do not reimplement this old optimization |
| SD -> cart SDRAM | [src/platform/cart_sc64_n64.c:1067](../../../../../src/platform/cart_sc64_n64.c), `:1267` `media_fill` -> `stage_slice` -> synchronous `read` into PI window | Strong integration research target: async SD command ownership could hide MCU/SD wait without changing file format |
| Stream fairness | [src/platform/cart_sc64_n64.c:1475](../../../../../src/platform/cart_sc64_n64.c) direct-record vs generic-stream 4:1 service | Existing audio fairness matters; a throughput-only change can harm mixer deadlines |
| Stream slice | `MEDIA_FILL_SLICE` is 32 KiB; background/music prefetch generic constant is 2 KiB ([src/platform/cart.h:128](../../../../../src/platform/cart.h)) | Do not confuse different consumers' budgets; larger batches may improve throughput while making tail latency worse |
| Decode | [src/rtk/gif64_n64.c:698](../../../../../src/rtk/gif64_n64.c) calls libdragon `decompress_lz4_full_inplace`; delta apply at `:712` | Detailed profiling distinguishes CPU decode from transfer; scalar RLE removal already helped historically |
| Image publication | [src/rtk/rtk_gpu_n64.c:1350](../../../../../src/rtk/rtk_gpu_n64.c) whole-plane cache writeback for CPU writes; TLUT-only variant for DMA-filled planes | Cache traffic may matter; partial dirty-region publication is testable for deltas but must cover every modified cache line |
| Draw | GIF backend keeps recorded `gpu_block_t` per plane; CI8 surface / TLUT path | RDP already performs the textured blit; FPGA is not a replacement GPU |
| Audio | [src/mgr/snd_n64.c:74](../../../../../src/mgr/snd_n64.c) mixer_poll, analysis tap, AI submission | RSP already does mixing; moving decode/mix to cart adds transport and synchronization and competes with GIF traffic |
| Normal GIF fallback | [src/rtk/image_gif.c:14](../../../../../src/rtk/image_gif.c) budgeted LZW + compositor, `:530` existing gifbench phase timer | Benchmark this only when assessing unconverted assets, separate from GIF64 playback |

## Existing measured evidence

[docs/perf_log.md](../benchmarks.md) records real `browse10-nav` runs with music/effects. On 2026-08-25, Final Fight had 341 frames / 10 seconds with PDSA RLE reverse-baseline and 438 with PDSB LZ4 using the same ROM. Direct PDSB record DMA reached 482; later background-copy candidate reached 494. These demonstrate both decode and transport improvements, but the final historical result still misses sustained 60 FPS (p50 19 ms, p99 41 ms). They do not prove today's firmware result.

Do not repeat rejected historical approaches without a new hypothesis: full independent raw frames, oversized lookahead/rings and RLE have multiple poor historical rows. Font TLUT residency alone did not improve the heavy Final Fight case (343 frames before and after in its recorded comparison).

## Host experiment completed: FPGA decoder transport cost

Generated `offload-transport-model.json` using the historical 5.2 MB/s PI read rate documented in [src/platform/cart_sc64_n64.c:626](../../../../../src/platform/cart_sc64_n64.c). This is a arithmetic model, not new hardware throughput. A 320x240 CI8 frame is 76,800 bytes: 14.77 ms of PI transfer. RGBA16 is 153,600 bytes: 29.54 ms. At 60 frame updates/s raw CI8 needs 4.608 MB/s before audio/other PI users; RGBA16 needs 9.216 MB/s.

If the FPGA expands compressed data into cart SDRAM, the N64 must fetch expanded output. For an example 25%-size LZ4 record, current compressed PI transfer is 3.69 ms, versus 14.77 ms raw. The decoder would need to save over 11.08 ms of CPU work in a serialized model merely to break even. Actual overlap and memory contention change the critical path, so measure end-to-end rather than sum stage maxima. On strongly compressed frames, this can make an FPGA decoder slower. On large weakly compressed frames or expensive delta processing it remains a hypothesis, not a rejection of every accelerator.

Parent downloaded the actual card assets read-only. The host diagnostic `analyze-assets.py` inspected every indexed record, and `validate-assets.py` decoded every PDSB frame using host LZ4, requiring exact 76,800-byte output. All 1,862 frames passed. This is format/decode validation, not N64 performance or pixel comparison against original GIF. Results and concatenated-plane SHA256 values are in `asset-record-analysis.json` and `asset-decode-validation.json`.

| Actual card asset | Frames / format | Mean / maximum compressed record | Historical-rate PI model |
|---|---|---|---|
| Final Fight | 1,717 PDSB, all LZ4, 10 ms source delays | 17,880 / 24,703 bytes | 3.44 ms mean compressed vs 14.77 ms raw; expansion adds 11.33 ms |
| Sunset Drive | 145 PDSB, all LZ4, zero source delays resolved by existing cadence model | 54,080 / 55,866 bytes | 10.40 ms mean compressed vs 14.77 ms raw; expansion adds 4.37 ms |

Both files are independent full CI8 frames, so delta application is not their current decode workload. Final Fight is especially unfavorable for expanding frames on the cart unless CPU unpack is unexpectedly expensive. Sunset Drive is substantially more PI-bandwidth intensive. These sizes make an actual PI-timing / overlap benchmark more immediately useful than a generic GIF decoder prototype.

## GIF format and fidelity constraints

[tools/themeconv/themeconv.py:390](../../../../../tools/themeconv/themeconv.py) uses Pillow frame composition (disposal, local/global palettes, transparency, interlace) and converts exact displayed colors to RGBA5551. A shared palette is constructed across the animation; the converter chooses PDS9 for background min source delay >=30 ms, otherwise independent PDSB. A union palette overflow falls back to per-frame PDS2; a composed frame over 256 colors falls back to RGBA16 PDS8. A hardware converter must preserve these cases, not merely decode LZW indices.

PDS9 is four-chain delta data; PDSB supports independent addressable raw/LZ4 records so playback can skip to the wall-clock target. Preserve frame delay resolution, `bg_speed`, loop/transition semantics, offsets, masks and buffer chain dependencies. A one-pass online converter cannot know its union palette fits until it has inspected all frames; prepass, seek/rewrite or per-frame output is needed. Current file readers accept several older versions ([src/rtk/gif64.h](../../../../../src/rtk/gif64.h)). A new FPGA accelerator must negotiate capability/version and retain software fallback on stock SC64, EverDrive and host targets.

Any decompressor needs bounded input/output, invalid-distance and malformed-length detection, cancellation and output ownership; a bad theme file must not overwrite save or firmware memory. N64 cache invalidation, parity alignment, final partial sectors and RDP plane retirement are part of the protocol. The existing assembly LZ4 backend can write eight bytes beyond logical output; allocated planes intentionally include a guard (`rtk_gpu_n64.c:1273`). Do not assume a new decoder has identical boundary behavior.

## Prioritized experiments and remaining work

| Priority | Experiment | Evidence needed / acceptance | Status |
|---|---|---|---|
| 1 | Fresh Final Fight, Sunset Drive and Ghosts'N Goblins control using unchanged browse10-nav | FPS/p50/p99, GIF ticks/frames/drop, underruns; same ROM/assets/theme/config/firmware per A/B | Completed; see maintained ledger |
| 1 | Detailed frame attribution | PHOS_PERF_DETAIL adds GIF_READ/STAGE/UNPACK/APPLY, sound, view, persistence and frame-begin/end; one same-build A/B avoids profiling overhead confound | Completed in separate profile ROM; see measurements below and ledger |
| 1 | Async SD-to-cart producer via existing SC64 command registers, separate submit/poll at backend | Idle CPU time, maximum service slice, concurrent PI reads, cancellation/USB/save command serialization, byte-for-byte content and stock fallback | Source hypothesis; not implemented |
| 1 | PI throughput/timing and simultaneous SD-fill contention benchmark | Several sizes/alignment, SD idle vs active, CRC and guard check; timing only within verified cart specification | Delegate FPGA/hardware agents |
| 2 | Adjust SD command batching/service slice only where detailed trace shows blocking | Three trials each baseline/candidate, both average and tail latency plus audio; no silently changed benchmark epoch | Not started |
| 2 | FPGA LZ4 decode benchmark against CPU+compressed PI | Actual asset record-size distribution, measured unpack cost and expanded-transfer cost; host golden tests before RTL/flash | Transport model completed; full decoder not implemented |
| 2 | RSP LZ4/delta application prototype | Stays within N64 so avoids expanded PI cost; needs audio high-priority/RDP scheduling benchmark and DMA chunk boundaries | Research only; not an SC64 firmware change |
| 2 | Delta dirty-cache publication / RDP copy refinement | Profile APPLY/cache cost; guard and pixel parity checks, same resulting image and retirement | Research only; existing full-frame RDP copy already present |
| 1 | Direct original-GIF decoder with packed dirty updates | Full GIF composition/cadence parity, reference versions, decoder bounds, RTL fit and hardware A/B | Current user-priority proposal; host models completed below, RTL pending |
| Alternate | On-device conversion to disposable GIF64 cache | Cold conversion and warm playback measured separately; no PC dependency | Earlier architecture alternative, superseded as primary direction by direct original-GIF playback; unimplemented |
| 3 | FPGA palette/RLE/delta expansion | Reject simple raw expansion when extra PI bandwidth dominates; consider bounded output spans with explicit destination protocol | Research only |
| 3 | FPGA image scaling / audio offload | Must beat existing RDP/RSP plus command and PI cost; no direct RDRAM access | Low-priority research; no speed claim |

Acceptance should retain actual displayed animation correctness and music, and distinguish UI render FPS from GIF source update rate. Repeating a held GIF frame can make the menu render at 60 without delivering its intended animation cadence. Aggregate 10-second FPS alone hides 40 ms stalls; collect p99 and phase maxima, and count unique presented frames when diagnosing cadence. No claim of FPGA fit, timing closure or universal safety is made by this source audit.


## Updated user priority: original GIF directly, no preconversion

The user explicitly prioritizes unmodified original GIF playback and prefers FPGA on-the-fly decoding. The earlier PDSB comparison remains a performance reference, not the desired asset workflow. A direct decoder does not need to serialize a GIF64 file: it can read the original stream and publish bounded decoded updates from cart SDRAM. Existing GIF64 files may remain an optional compatibility path, but are not a requirement of this proposed pipeline.

### Native GIF implementation and parity

The actual OS4 source was read at [rtk.py](https://raw.githubusercontent.com/forkymcforkface/rgb-pi-frontend/master/rtk.py), `RtkAniGif` lines 1197-1263. It uses Pillow-composed frames, the theme speed override or frame duration (100 ms when absent), advances only when elapsed is greater than duration, resets elapsed, and advances one frame per animation call. Its background constructor uses the original GIF. Hardware work must preserve this observed scheduling and composition, including loop and transition behavior. A zero/10 ms delay does not mean the application must display 100 unique frames/s.

The current C fallback already reads originals (`image_gif.c:327`) and stages theme input to cart SDRAM where possible. `rtk_gifdec_step` performs budgeted LZW then the backend compositor. The N64 loader tries resident predecode, a decoded cart/SD cache, whole-animation cart sealing, then live streaming (`rtk_gpu_n64.c:2552`). Final Fight's 1,717 raw CI8 frames require 131,865,600 bytes before palettes, so whole-animation residency is unsuitable. A new direct hardware path should begin with bounded input/output rings and never require predecoding the entire animation.

The current generic fallback is not a full compatibility oracle: `image_gif.c:301` explicitly marks disposal 3 unsupported. Large N64 canvases may be CI8-only (`rtk_gpu_n64.c:1666`) and palette-union overflow can disable that path without an RGBA canvas. These must be tested against Pillow/OS4 reference output, not inherited silently into a new FPGA decoder.

### Completed original-frame dirty-update experiment

Used the agent-downloaded upstream original `original-final-fight/Final Fight/images/background.gif` (source provenance documented by the FPGA agent). `analyze-original-dirty.py` composited all 1,717 frames with Pillow and compared their RGBA5551 output. `analyze-original-palette.py` independently measured palette union and frame-gap update sizes. Results are retained in `original-dirty-frame-model.json` and `original-palette-gap-model.json`. This is a host transport model, not an FPGA speed or resource result.

The displayed color union is **252 RGBA5551 colors**, with **1-114 colors per
composed frame**. The original source already has a **256-entry global palette
and no local palettes**, so this particular CI8 pilot can preserve source indices
and needs neither dynamic palette assignment nor a prepass. These two palette
counts describe different properties and are consistent. Other GIFs can need
stable dynamic index assignment, a format transition or software fallback.
Replacing a palette entry while an earlier canvas index still uses it corrupts
preserved pixels; per-frame GIF palettes cannot simply replace one global canvas
TLUT.

| Reference gap | Mean changed 8x8-tile CI8 payload | Mean including 150-byte tile mask + full 512-byte TLUT | p99 tile payload |
|---|---:|---:|---:|
| Previous decoded frame | 16,551 B | 17,213 B | 67,456 B |
| Two frames earlier | 18,315 B | 18,977 B | 69,056 B |
| Three frames earlier | 21,715 B | 22,377 B | 69,568 B |
| Four frames earlier | 22,024 B | 22,686 B | 70,144 B |

Initial keyframe is excluded from these averages; worst-case tile payload is 76,800 B at every gap. Row-aligned single-span-per-row updates average 18,906 B across 101 rows; a single bounding rectangle averages 25,494 pixels. Sparse tiles are therefore worth investigating. Packet headers, alignment and completion metadata add a small amount beyond the table. A palette only needs resending when changed, so full 512 bytes every frame is conservative.

The 17,213-byte estimate compares RGBA5551 colors. A pilot comparing original palette indices can conservatively mark additional tiles when different indices map to the same displayed color. This is a color-difference model, not measured pilot traffic.

At the historical PI rate, 17,213 B is approximately 3.31 ms, comparable to current PDSB mean compressed-record transfer (3.44 ms), while potentially removing CPU decompression. This addresses the expanded-full-frame objection: **FPGA LZW + composition + dirty-tile packing is a promising original-GIF design for this asset**. Tail events still require full-frame bandwidth; steady 60 FPS is not established by averages.

### Proposed narrow ownership and protocol

1. The existing RTK GIF owner opens the original asset, owns GIF timing, loop/cancel state and format negotiation. Cart mechanics remain below the existing platform seam. Stock cart/software behavior remains available. Do not introduce another view renderer or a second main-loop scheduler.
2. MCU/control logic validates stream descriptors; the FPGA LZW/compositor works in explicitly allocated cart SDRAM. Decoder input is the original GIF bytes, not an offline transformed asset. Limit dimensions, dictionary indexes, compressed sub-block lengths, output ranges and frame count/sequence arithmetic.
3. The FPGA publishes a complete immutable output packet: generation, source frame, reference-frame identity, format, dimensions, delay/disposal metadata as needed, tile mask and contiguous tile pixels, plus palette changes. The N64 submits one/few large PI transfers for the packed packet. One PI command per tile would surrender the byte savings to per-command overhead.
4. RTK's N64 backend applies updates to an owned RDRAM image plane using the existing GPU image lifecycle. CPU tile placement and cache writeback remain real costs; measure them. Possible implementations compare CPU row copies, RSP scatter and RDP texture composition, without assuming any is free. RDP cannot directly fetch the cart's SDRAM as a normal texture.
5. The consumer acknowledges the exact reference version. Skipping a displayed frame must retain all intervening changes, and every retired/reusable RDRAM plane has its own content version. A packet relative to frame N-1 cannot patch a plane containing N-3. Use per-tile version tracking, conservative dirty accumulation, or retained reference canvases; request a full keyframe when versions cannot be reconciled. Our gap model computes exact differences, while accumulated dirty flags can send more data.
6. Do not modify a plane still used by queued RDP work. Preserve existing retirement fences, at least two working/output buffers as required, and generation-based cancellation before releasing any destination. Theme switching must cancel the FPGA job and observe completion before arena reuse.

For arbitrary GIF compatibility, implement local palettes, transparency, interlacing and disposal 0/1/2/3. Disposal 3 requires preserving/restoring earlier pixels; initial black/background behavior and transparent transition output need OS4 comparison. Full RGBA16 is a necessary fallback when a composed frame cannot fit CI8, but packetized changed RGBA16 tiles can still reduce bytes. The current Final Fight asset only exercises disposal 0, so passing it cannot establish generic GIF safety.

### Fresh profile interpretation

Parent-produced `profile-final-fight.log` reports 475 frames / 10,020 ms (**47.4 FPS**), p50 20 ms, p99 38 ms, 464 GIF frames, 599 ticks, 138 drops, zero underruns. Detailed averages: loop 21.091 ms; background pump 8.495 ms; GIF unpack 7.166 ms (max 7.731); stage 1.440 ms; USB 2.336 ms; sound poll 2.594 ms; view pump 1.413 ms; view draw 1.747 ms. Frame-begin 12.017 ms includes background, mixer and framebuffer wait; do not add nested scopes twice. This validates substantial CPU decode cost for the proposed dirty-output accelerator.

`profile-sunset.log` reports 293 frames / 10,014 ms (**29.3 FPS**), p50 33 ms, p99 63 ms, 293 GIF frames, 591 ticks, 298 drops, zero underruns. Loop average 34.173 ms; GIF unpack 11.404 ms; USB 6.024 ms; browser scan 5.765 ms (max 163.643); view pump 7.082 ms. Sunset has additional browser/transport stalls, so fixing GIF decode alone does not establish 60 FPS there.

USB scope includes a significant potential transport wait: `usb_sc64_n64.c:106` calls libdragon `usb_poll`, which issues `usb_sc64_execute_cmd`; its register reads/writes call `io_read`/`io_write`, both using `dma_wait_and_disable_interrupts` ([libdragon/src/dma.c:516](../../../../../libdragon/src/dma.c)). Outstanding async GIF PI DMA can therefore become CPU waiting attributed to USB. Do not call all 2-6 ms MCU overhead. A bounded defer-USB-while-PI-busy experiment could permit useful CPU work to overlap, but might merely relocate the wait. Preserve command-service responsiveness and measure the whole loop.

Next implementation should be staged: bounded host original-GIF reference decoder -> RTL LZW/compositor simulation with malformed-input fixtures -> resource/timing fit -> packet golden tests including palette overflow/skipped frames -> hardware bytes/cadence/perf. Parent is finishing isolated MCU comparisons and restoration first; no new GIF hardware implementation has been flashed by this audit.
