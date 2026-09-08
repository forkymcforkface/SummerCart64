# SC64 FPGA acceleration investigation

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

**Current direction:** the user prioritizes playback of original GIF files without preconversion, preferably decoded by FPGA. The concrete direct-GIF proposal and original Final Fight tests below supersede the earlier suggestion to prioritize a GIF64-only accelerator. Exact GIF64 output is not a requirement for direct playback.

Updated 2026-09-05. Scope: current `vendor/sc64` RTL and PhosphorOS GIF64 converter/runtime. No firmware or production source changed; no board access performed by this agent.

## Findings

An FPGA GIF decoder is technically possible, but this FPGA cannot directly render into N64 RDRAM or submit RDP/RSP commands. The cartridge is a peripheral on the PI bus: [fw/rtl/top.sv](../../vendor/sc64/fw/rtl/top.sv) exposes cartridge PI address/data/strobes, SI and CIC, not the N64 RDRAM bus. The N64 still has to initiate PI transfer of completed pixels into RDRAM and render them. An accelerator therefore helps only if saved CPU work exceeds its command, memory-contention and transfer costs. It cannot by itself guarantee 60 FPS; the target frame budget is approximately 16.67 ms at 60 Hz.

The main immediate hardware constraint is **SDRAM reservation**. [memory_arbiter.sv](../../vendor/sc64/fw/rtl/memory/memory_arbiter.sv) masks MCU/config, USB DMA and SD DMA SDRAM requests for the entire `pi_sdram_active` interval. [n64_pi.sv](../../vendor/sc64/fw/rtl/n64/n64_pi.sv) sets that reservation when decoding a cartridge SDRAM operation and clears it on end/reset. It is not merely per-word priority. A decoder added as another SDRAM master cannot run freely while PI fetches a previous frame under this policy. Background SDRAM work should initially obey the same mask. Removing it requires proving PI service deadlines, FIFO behavior, row conflicts and refresh timing across cartridge consumers.

[memory_sdram.sv](../../vendor/sc64/fw/rtl/memory/memory_sdram.sv) uses a 100 MHz, 16-bit SDRAM interface but programs **burst length one**. The request interface carries one 16-bit word and one acknowledgement. The raw 200 MB/s pin-rate arithmetic is not application throughput: controller handshakes, row activation, refresh, arbitration and PI protocol all reduce it. Existing SD/USB peak claims (~23.8 MiB/s, project README) also are not measured PI throughput or a promise for simultaneous traffic.

## FPGA capacity

The selected part is LCMXO2-7000HC-6TG144C ([fw/project/lcmxo2/sc64.ldf](../../vendor/sc64/fw/project/lcmxo2/sc64.ldf); PCB names the same family/package). The manufacturer lists 6,864 LUTs, 26 EBR blocks and 240 kbits advertised EBR capacity. These are **total**, not free resources. [Lattice product brief](https://www.latticesemi.com/-/media/LatticeSemi/Documents/ProductBrochures/AM/XO2_Product_Brief_10312024.ashx?document_id=44918).

Visible logical RAM consumers already include:

| RTL allocation | Payload |
|---|---:|
| General buffer, [memory_bram.sv](../../vendor/sc64/fw/rtl/memory/memory_bram.sv) | 8,192 bytes |
| EEPROM | 2,048 bytes |
| DD | 1,024 bytes |
| FlashRAM page | 128 bytes |
| MCU `mem_buffer` | 1,024 bytes |
| CIC soft-core program/data RAM | 2,048 bytes |
| SD RX/TX and USB RX/TX FIFOs | 4 × 1,024 bytes |
| PI FIFO | Four 16-bit words |

The large named logical arrays total 18,560 bytes, excluding small registers and soft-core register storage. This is a logical accounting, **not** a synthesis allocation report: port organization, width and mapping can waste EBR capacity or use LUT RAM. No current place-and-route utilization report was located in the inspected paths, so there is no support for claiming a particular amount of free logic/RAM. A matched Diamond build and timing report is a prerequisite to an actual accelerator proposal. The existing build rejects a design that fails its required clock frequency.

## Can normal GIF become GIF64 on the fly?

Yes in principle, but this is a new decoder/compositor/cache subsystem rather than a small firmware optimization. GIF LZW emits palette indices; complete playback additionally needs sub-block parsing, variable 3–12-bit codes, clear/end codes, dictionary edge cases, local/global palettes, transparency, interlace, partial rectangles, disposal/background restoration and timing/loop semantics. These operations must match the current software decoder's output. A conventional 4,096-entry prefix/suffix dictionary alone is about 10 KiB tightly packed (12-bit prefix + 8-bit suffix); a 4 KiB expansion stack is a common additional choice, not a theoretical lower bound. That already exceeds plausible unused EBR without an exact fit report. External SDRAM storage is possible but adds dependent dictionary reads and contention.

At 320×240 a CI8 canvas is 76,800 bytes and an RGBA16 canvas is 153,600 bytes: neither fits inside the whole chip's EBR, even before SC64's existing duties. Disposal method 3 can need restoration storage as well. SDRAM-backed composition is therefore necessary for general backgrounds. A streaming scanline design alone cannot handle every disposal/composition case without external state.

Current [tools/themeconv/themeconv.py](../../tools/themeconv/themeconv.py) does more than LZW decode: it obtains composed frames, optionally resizes, maps RGBA5551 colors, chooses a shared palette across frames when possible, writes delays/indexes, and selects PDS9 four-chain deltas or PDSB independent raw/LZ4 frames based on cadence. It falls back through per-frame palettes to PDS8 RGBA16. An exact shared-palette output cannot be finalized from the first frame alone; later colors may force a different representation. Practical on-device conversion could use a scan/pass or a deliberately simpler compatible representation and persistent cache. It would not require creating the most compact current PDS9/PDSB encoding to display an ordinary GIF.

Distinguish two goals: converting once on the console removes the PC conversion requirement, but mostly changes preparation/loading; decoding every loop shifts CPU cost each frame and needs sustained throughput. Predecoding to cart SDRAM once is likely easier to bound than repeatedly decoding arbitrary GIF during animation. Existing Phosphor runtime already stages GIF64 in cart SDRAM and transfers frames through `phos_cart_gif64_staged`; that part should be reused, not duplicated.

## Candidate ledger

| Candidate | Finding/result | Current state | Next test and risk |
|---|---|---|---|
| Full GIF LZW/composition in FPGA | Independent original Final Fight host decoder matches all 1,717 Pillow frames; substantial RAM/protocol work remains | Host reference and resource audit complete; no RTL implementation | Bounded differential RTL fixtures, malformed inputs and resource/timing fit next. High complexity; parser bounds/disposal parity essential. |
| On-console conversion once to cart/SD cache | Removes offline preparation in principle; can amortize decode over loops | Architecture option, not implemented | Incremental C prototype using existing owner first; verify invalidation and RAM tiers before RTL. Must not stall UI or silently change asset semantics. |
| PDSB LZ4 decompression in FPGA | Narrower than GIF and preserves existing format. LZ4 permits offsets up to 65,535, so general history exceeds free EBR | Source audit; no prototype | Benchmark CPU LZ4 time separately, then use cart SDRAM history or an explicit bounded-history codec. Test overlapping copies, truncation, output bounds. |
| PDS9 tile/delta application in cart SDRAM | Small control engine plausible; can reduce N64 delta patch work, but output still crosses PI | Source audit; no prototype | Compare sparse tile update traffic versus full decoded-frame PI transfer. Preserve four-chain dependencies and frame skipping. |
| Palette conversion / byte swapping | Very small streaming logic plausible | Feasibility calculation only | N64 RDP already consumes CI8/TLUT; expanding to RGBA16 doubles pixel traffic. Only useful for a measured unavoidable conversion. |
| Cart-local fill/copy/blit engine | Can initialize/copy SDRAM without CPU PIO; existing DMA is FIFO-to-memory, not a general memory-to-memory blitter | Source audit | Measure current copy volume. Define overlapping-copy semantics, bounds, cancel, completion and ownership. Do not export a general unsafe arbitrary-memory writer to core. |
| SDRAM bursts and PI prefetch FIFO | Single-word controller and four-word PI FIFO make this a plausible throughput experiment | Source audit only | Simulate actual controller + SDRAM timing model, random row/refresh/abort/unaligned sequences; synthesize timing; then compare board PI throughput. High compatibility impact. |
| Allow SD/decoder between PI words | Current arbiter intentionally blocks it for whole PI operation | Actual RTL reservation test PASS | Must prove sufficient PI FIFO headroom and worst-case SDRAM service time; simply removing mask is not safe. |
| BRAM ping-pong output window | Existing arbiter permits BRAM accesses while PI SDRAM reservation is active | Actual RTL exception test PASS | Small windows avoid SDRAM exclusion but require more PI transactions. Need true dual-port producer/consumer design or controlled arbiter use, not commandeering shared 8 KiB buffer. |
| Direct RDP/RSP/RDRAM accelerator access | Not provided by physical cart interface/RTL | Rejected as described | Use N64 PI DMA and existing RDP/RSP facilities; FPGA cannot initiate arbitrary N64 bus-master DMA. |
| Reuse CIC SERV soft CPU for graphics | Existing SERV instance owns CIC protocol and limited RAM | Source audit, not recommended | Sharing disrupts cartridge authentication/timing; a second soft core consumes resources and is not an obvious speedup over VR4300. |
| Faster FPGA/SPI clock | Prior SPI test rejected 16 MHz due to read corruption; no new evidence changes that | Not retested here | Do not include as an assumed free gain. Any clock change needs CDC and timing closure plus board validation. |

## Tests performed in this investigation

1. **Actual unmodified [memory_arbiter.sv](../../vendor/sc64/fw/rtl/memory/memory_arbiter.sv) under Verilator 5.032**, driven by `arbiter_probe.sv`: held a pending SD SDRAM write for 100 cycles with PI active but no N64 word request; verified it stayed blocked and resumed when reservation cleared. Verified BRAM request is allowed during PI SDRAM reservation. Verified N64 wins simultaneous SDRAM requests. **All three assertions passed**, `arbiter-results.log`. Downstream memory acknowledgements are testbench inputs; this proves the arbiter policy, not SDRAM timing or physical board behavior.
2. Source allocation and transfer-size accounting: 320×240×60 CI8 output is **4.395 MiB/s**, RGBA16 **8.789 MiB/s**, before palette/commands. At a illustrative PI rate of 10 MiB/s those full frames cost 7.32 / 14.65 ms; at 20 MiB/s they cost 3.66 / 7.32 ms. These rates are illustrative, **not measurements**. Decode/composition memory traffic is additional. An accelerator which adds a full-frame copy can lose despite fast logic.
3. Attempted local `sd/phosphor/themes/*/background.gif64` inventory found zero staged files. `asset-budget.json` is an empty inventory, **not a successful playback benchmark**. Parent hardware captures are needed to identify active format, cadence, bytes and real frame cost.

Reproduce the RTL probe inside a container with Verilator/g++/make:

```sh
cd build/sc64-ui-research
verilator --binary -j 4 --timing -Wno-fatal --top-module arbiter_probe --Mdir arbiter_obj arbiter_probe.sv ../../vendor/sc64/fw/rtl/memory/memory_arbiter.sv ../../vendor/sc64/fw/rtl/memory/mem_bus.sv ../../vendor/sc64/fw/rtl/n64/n64_scb.sv
arbiter_obj/Varbiter_probe
```

## What to test next

Obtain frame CPU/render/RDP wait/PI/SD/decode timings from the unchanged production rig. Select a workload that actually misses its frame deadline; an animation encoded at 20/30 FPS should not itself be interpreted as UI failure to run at 60 FPS. Prioritize the smallest measured bottleneck: transfer overlap/staging first when I/O-bound, existing RDP/RSP paths when rendering/CPU-bound, then a bounded decompression or delta engine only if decompression remains dominant. Every proposed FPGA image needs baseline utilization, timing closure, protocol simulation, bounded cancellation and memory isolation before board deployment. No accelerator implementation or physical validation is claimed by this document.

## Original Final Fight investigation: direct GIF, no preconversion

Source is the original theme archive in [OS4-Themes at pinned commit 2e1576bc44ec0268579028f32c42fc7b9aedc829](https://github.com/forkymcforkface/OS4-Themes/tree/2e1576bc44ec0268579028f32c42fc7b9aedc829). Downloaded `data/themes/Final Fight - Theme by elreypescador.7z` under this ignored research directory, SHA256 `69140d90f162187e21920af4684e962a1ebd71cbf62d856bbf4c857fb9c1d658`. Original `Final Fight/images/background.gif` is 33,675,601 bytes, SHA256 `d48de154f477e6753b14d5d1a1fa7c5edcefe17c3688e9afbe790907bc7056b7`. Original theme sets `[bg] type=ani_gif`, `speed=default`.

### New completed test

`gif_probe.py` parses the original bytes and independently decodes every LZW image with output bounds, valid dictionary references and explicit end-code checks. It composites transparent indices over the persistent global-palette canvas and compares every resulting RGBA frame with Pillow 12.2.0. **All 1,717 frames matched byte-for-byte.** This is a software feasibility/reference test, not FPGA implementation or timing validation. Raw output metrics and provenance are in `final-fight-gif-probe.json`; host run took 19.57 seconds, which is not a prediction of N64/FPGA speed.

| Original property | Measured result |
|---|---:|
| Dimensions / raw image rectangles | 320×240; every image covers full canvas |
| Frame count / source delay | 1,717 / every frame 10 ms |
| Sum of authored frame delays | 17.17 seconds; not measured OS4 loop duration |
| Global palette | 256 entries |
| Local palette / interlaced images | 0 / 0 |
| Transparency | All 1,717 frames |
| Disposal | All zero (unspecified/retain for tested decoder behavior) |
| Compressed image sub-block payload | 33,507,709 bytes |
| Decoded palette indices | 131,865,600 bytes |
| LZW codes / clear codes | 23,944,786 / 7,197 |
| KwKwK special cases | 1,286,559 |
| Maximum dictionary occupancy / phrase length | 4,096 / 391 |
| Conventional dependent prefix walk steps | 107,929,728 |

This confirms a **guarded global-palette CI8 pilot is sufficient for this actual original file**. It does not justify pretending local palettes, interlace or disposal 2/3 are supported. The production original-GIF decoder currently documents disposal 3 as unsupported in [src/rtk/image_gif.c](../../src/rtk/image_gif.c); a new full-support engine must test that separately rather than inheriting the gap unnoticed.

The file authors a 100 frames/s cadence, above 60 Hz display rate. This is not automatically OS4 playback cadence: OS4 timing policy, including its strict elapsed-time comparison and frame-loop behavior, must remain authoritative. If the selected existing playback policy skips presentations to track authored time, the direct decoder must still process intermediate transparent frames to maintain the composed canvas. Skipping compressed image blocks blindly changes the picture. The source averages ~1.95 MB/s compressed input and 7.68 MB/s decoded indices at its native cadence; those figures exclude dictionary/composition traffic.

The UI agent's independent original-frame comparison (`original-dirty-frame-model.json`) found a mean 16,551 bytes of changed 8×8 CI8 tiles per consecutive image (median 7,872, p99 67,456, maximum 76,800). This explains why dirty tile output is worth prototyping. Those figures **do not** establish traffic per 60 Hz presentation: accumulated differences across skipped images and destination-buffer history still need measurement.

### Concrete implementation recommendation

1. **Add a bounded hardware GIF LZW core in isolated research RTL.** Input is original GIF compressed sub-block bytes, minimum code size and exact output pixel limit. Output is index bytes with backpressure. Start with an explicit prefix/suffix dictionary plus stack, or evaluate the current C decoder's output-offset/length dictionary alternative. Do not allocate an unbounded phrase buffer. Differentially test against the reference for clear codes at all positions, growth boundaries, full-dictionary deferred clear, KwKwK, malformed code, truncation, maximum phrase, blocked output and cancellation. The GIF89a specification explicitly permits a full dictionary to remain unchanged until a later clear code. [GIF89a specification](https://www.w3.org/Graphics/GIF/spec-gif89a.txt).
2. **Map state onto real SC64 memory resources, then synthesize before choosing a board test.** A 4,096×20-bit prefix/suffix table logically needs 10 KiB; practical 32-bit SDRAM slots use 16 KiB. Put the dictionary in cart SDRAM initially if free EBR cannot fit it, keeping a small phrase stack/FIFO on-chip if possible. A 4 KiB stack handles general bounded expansion; the observed 391-byte maximum is not a safe universal allocation. Reusing existing 8 KiB buffer or CIC/save RAM is prohibited without explicit ownership/exclusivity. Obtain actual EBR/LUT placement and 100 MHz timing closure.
3. **Stage the original GIF in the existing cart asset arena, not a converted file.** For this file that costs ~32.1 MiB of cart SDRAM plus bounded decode scratch/canvas. Existing arena capacity and competing assets must be checked; if it does not fit, stream original compressed windows from SD. A frame descriptor cursor can be parsed on the N64 incrementally initially, with the MCU issuing a bounded accelerator job. Moving all GIF framing into FPGA is optional and can follow after LZW/composition proves valuable. The MCU must never relay pixel bytes over SPI; use memory descriptors and completion status.
4. **Compose inside cart SDRAM with dirty tracking.** For the measured Final Fight subset, retain one CI8 canvas, treat transparent indices as no-op, and compare written values before marking an 8×8 tile dirty. A 40×30 dirty bitmap is only 150 bytes. Process every due original image, then pack final changed tiles into a contiguous output region. A packed list avoids hundreds of separate PI commands. Include output generation, tile count and output byte limit; never let a malformed file write outside its allocated arena ranges.
5. **Transfer only the needed presentation update to N64 memory.** After the job completes, N64 initiates PI DMA of the packed descriptors/pixels, then applies tiles to an RDP-safe destination through the existing backend. This still has CPU tile-copy and RDP synchronization costs, which must be measured. Preserve separate destination histories: dirty state since the last displayed generation cannot simply be cleared when one of multiple framebuffer/texture planes is updated. An acknowledgement/generation contract or full resynchronization keyframe is needed. Keep a valid previously displayed frame while the next decode is incomplete.
6. **Extend to general GIF semantics without changing the original files.** Interlace is a row-address sequence (passes beginning 0,4,2,1 with increments 8,8,4,2). Apply previous frame disposal before next composition; disposal 2 restores the specified background rectangle, disposal 3 snapshots/restores affected pixels. Preserve alpha when required by the owning background/transition contract. For local palettes, retain composed colors independently of the new palette: an RGBA16 canvas is the simplest robust mode, while a CI8 mode is safe only when the palette mapping remains valid. Resizing, if required for non-native dimensions, belongs in a separately tested stage matching existing behavior. No global-palette scan or GIF64 encoder is required for a direct RGBA16 path.
7. **Version and confine the protocol.** Capability query; submit bounded source/canvas/scratch/output ranges; pump/query completed generation and error; cancel/drain before theme release or game launch. The FPGA returns deterministic errors for unsupported pilot features, so the ordinary GIF software path remains available during staged development. Release the accelerator before save/ROM reuse. Reset during a job must not leave a DMA or stale response targeting recycled cart memory.

### Feasibility limits and tests still required

A naïve external prefix dictionary is bandwidth-heavy. The observed 107.9M prefix steps at four bytes per SDRAM entry imply ~25.1 MB/s dictionary-read payload at source cadence, before dictionary writes, compressed input, canvas reads/writes, output packing, refresh or PI reservation. Prefix traversal is dependent, so latency matters as much as aggregate bandwidth. This is an **algorithmic traffic estimate**, not a measured hardware throughput. The existing SDRAM controller's single-word acknowledgements may make this design too slow; alternatives include an on-chip dictionary where fit permits, a dictionary cache, or output-offset/length copying from a decoded index plane. That alternative also has memory traffic and a larger table; it needs a cycle model rather than an assumption of improvement.

A pilot that tracks the file's authored 10 ms timeline would need 100 source images/s while sharing memory with PI output and normal UI/audio traffic. An OS4-parity policy may advance differently; establish that source behavior before choosing the production deadline target. Dirty output helps the PI side, but does not eliminate source decode/composition. Full-frame raw output remains a poor default based on the parent's measured transfer profile. As of this update, there is **no GIF RTL implementation, no synthesis fit, no decoded-GIF FPGA cycle benchmark and no board performance claim**. The next concrete test is the differential LZW RTL core plus actual-controller memory service simulation; flash only after those and timing closure pass. Retaining original GIFs is compatible with this staged plan throughout.

At the 100 MHz clock specified by the current RTL/build constraints, a 10 ms source interval contains 1,000,000 cycles. The measured average is ~62,859 dependent prefix steps and ~13,945 codes per image, plus 76,800 emitted indices. Even granting unrealistically cheap one-cycle code handling and one-cycle pixel output leaves ~14.47 cycles per dependent prefix step for everything else. A 32-bit dictionary entry needs two transfers through the present 16-bit memory interface, before dictionary writes and composition. If PI reservations consumed an illustrative 3 ms of that interval, the remainder falls to ~9.69 cycles per step. These are budget sensitivities, **not simulated utilization or predictions**; stalls, maximum-frame work and memory access patterns determine feasibility. A new core should report worst-frame cycles and sustained loop backlog under the selected OS4-parity timing policy (17.17 seconds is only the sum of authored delays), not merely average decoder speed.

Reproduce the completed original-GIF probe from the PhosphorOS repository root:

```powershell
python build/sc64-ui-research/gif_probe.py
```

It requires Python with Pillow and NumPy only for research/reference comparison; neither is a proposed end-user asset preparation requirement. It reads [build/sc64-ui-research/original-final-fight/Final Fight/images/background.gif](<../../build/sc64-ui-research/original-final-fight/Final Fight/images/background.gif>), leaves that original unchanged, and writes [build/sc64-ui-research/final-fight-gif-probe.json](../../build/sc64-ui-research/final-fight-gif-probe.json). `gif-probe.log` is captured stdout. Archive/original hashes above allow independently downloaded input verification. The dirty-tile model is independently reproducible with the UI agent's [build/sc64-ui-research/analyze-original-dirty.py](../../build/sc64-ui-research/analyze-original-dirty.py); consult its accompanying JSON for exact source/destination interval assumptions.
