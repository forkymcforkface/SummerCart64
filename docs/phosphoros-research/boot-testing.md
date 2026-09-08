# SC64 boot optimization testing log

Last updated: 2026-09-07.

Steady-state UI and direct original-GIF research continues in the
[SC64 UI testing ledger](ui-testing.md). That round rejected an additional
MCU reply-batching experiment and restored this five-change production fork;
its final firmware backup matches its pre-test backup byte-for-byte.

This is the maintained record for the SC64 bootloader, MCU, and FPGA
optimization investigation. It records completed experiments, measurements,
current work, and outstanding tests. Earlier PhosphorOS frontend optimization
work is outside this investigation; frontend timings below measure the impact
of these SC64 experiments.

## Maintenance during testing

Before starting an experiment, update the current-work section with the
candidate, source revision, baseline, and intended test. After each result,
record the measurement, evidence location, safety findings, and disposition
before moving to another candidate. Record failed and inconclusive runs as
such. Update the installed firmware and restoration state after every flash.
Keep rejected experiments in the history and move completed backlog items to
the appropriate results table. Update this document in each related testing
or implementation commit.

Raw logs, firmware backups, binaries, patches, and fixtures currently live in
`build/sc64-boot-ab/`, an ignored local directory. Artifact names below are
relative to that directory. They are not distributed by Git; the measurements
and decisions in this document are the durable record. Do not delete firmware
backups as routine build cleanup.

## Current work

- Current installed state and newest measurements: [software-only round](#software-only-boot-round--2026-09-07).
- Follow-up software-only reviews are complete; their unaccepted experiments
  are recorded below. No FPGA changes.
- Current task: maintain this log for subsequent validation and experiments.
- Fork: `vendor/sc64`, branch `phosphoros-boot`, based on v2.20.2
  (`18041e25472075a166292d1195603bcefe9c9688`). The original five changes are consolidated in `1c8f6f9`; historical
  tables retain their original measurement identifiers.
- Installed state: clean production c1/cursor/bounded-read bootloader without
  the diagnostic image, and SPI byte/group/full-duplex MCU. No timing
  instrumentation is installed.
  The original MCU loader prefix and FPGA match the original backup.
- Last Final Fight verification: frontend ready 420 ms; first music 448 ms;
  589 frames in 10.007 seconds, p99/max 31/33 ms, zero audio underruns.
- Original firmware backup retained; owned scratch SD file removed.

## Still to try or validate

These are pending tasks, not completed tests or claimed improvements. Research
branches explicitly rejected below are not automatically on this queue.

| Priority | Pending work | Required comparison or completion evidence |
|---|---|---|
| 1 | Repeat SPI byte batching and extra cfg servicing against an interleaved baseline | More A/B samples under identical SD and theme state; report variation as well as median, keeping boot phases separate. |
| 1 | Validate MCU winners beyond normal boot | Save/writeback, USB transfers, and button press/release/hold behavior; qualify the loop-timing impact before accepting extra cfg servicing. |
| 2 | Broaden SD compatibility and failure coverage | Additional cards, fragmented FAT32/exFAT menus, missing/truncated files, retries, and save durability where affected; host error injection is not physical failure coverage. |
| 2 | Qualify PI DMA handoff | Representative game and 64DD boot compatibility with original handoff state and interrupt behavior preserved; otherwise leave the candidate out. |
| Complete | Diagnostic logo loading | Superseded by user-selected logo removal; plain-background diagnostic text and watchdog/exception handling remain. See the software-only round below. |
| 2 | Measure true cold-cartridge and end-to-end boot | A procedure that removes USB cartridge power and measures consistent start/end events; console mains cycles alone cannot supply these results. |
| Research | Investigate coordinated FPGA/MCU transfer counts and SDRAM pipeline changes | First demonstrate a bottleneck and simulate protocol, arbitration, refresh, CRC, and boundary behavior. No hardware implementation or speed claim yet. |
| Research | Review bounded register-read bursts | Audit side effects from the speculative extra register read before building a narrow MCU candidate. |

## Research round: firmware state before fork integration

The initial research round performed staged bootloader and MCU firmware A/B experiments. The restoration described in this section predates the installed fork documented above. Earlier reports describing only transient tests are superseded. No FPGA update or clock increase was performed. Original MCU and bootloader firmware are restored; the full readback matches the original backup byte-for-byte. Version 2.20.2 alone does not distinguish experimental builds from stock firmware.

## Baselines and measurement scope

The menu extent and cursor experiments use upstream bootloader revision `a1e7996d`. Installed compression tests, MCU builds, and RTL tests use matching v2.20.2 source, tag `18041e25472075a166292d1195603bcefe9c9688`.

The rig is a real 4 MiB N64. The menu is 458,752 bytes, with FNV hash `4e633c50`. Later tests preserve the user's Ghosts'N Goblins theme; its frontend times are not directly comparable with earlier Sunset Drive samples.

IPL3-to-entry timing begins after IPL3 resets Count. Menu loading is a separate phase; the PhosphorOS frontend counter excludes both. These are not outlet-to-picture measurements. USB keeps the cartridge powered, and first/second menu loads have different SD initialization and cache state. Compare corresponding runs separately.

Two official original backups match SHA256 `A18E37FA61F89293E0B71BA3F245BA79164C651238D77A0ED1EF46615E1F412A`. Their chunks contain MCU `0x8000`, FPGA `0x2BFC0`, and bootloader `0x1E0000` bytes. Final readback `stock-final-readback.bin` matches that full SHA256. Restoration used MCU-only and bootloader-only packages, leaving FPGA untouched.

## Bootloader experiments

| Candidate | Evidence | Disposition and limits |
|---|---|---|
| Original extent coalescing | Data read: 38.36 to 21.59 ms | Rejected implementation: `CREATE_LINKMAP` hangs on a cyclic chain. Original host acceptance fixture exits 1. |
| Bounded read-only extent map | Original menu: 44.898-45.264 to 28.117-28.129 ms; eight hashes match. Actual FatFs ASAN/UBSAN fixtures cover cycles, truncation, errors, 63/64 extents, partial EOF, and exact 64 MiB. | Positive candidate. Read-only maps omit unused tail allocation; writable maps are preserved. Integration pending. See `bounded-extents/` and `bounded-menu-run.log`. |
| Standalone cursor reuse | Original menu: 44.868-45.029 to 40.585-40.603 ms; eight hashes match. 12,571 statuses and 10,868 mocked SD operations match baseline. | Positive standalone candidate: `cursor-only.patch`. Combined gains require measurement, not addition. |
| Cursor plus original extent path | `combined-cursor.log`: 28.131-28.151 to 27.976-27.991 ms; hashes match. Repeat in `hardened-run.log` saves about 0.15-0.19 ms. | Little additional benefit. Uses the rejected unbounded extent implementation, not a tested combination with the new bounded map. |
| PI DMA plus CPU IPL3 copy | About 3.00 to 1.01 ms; bytes match and PhosphorOS boots. | Candidate. Missing PI interrupt clear was corrected. Generic retail/64DD compatibility is not fully tested. |
| Additional SP DMA | Further saving of about 0.21 ms | Rejected: downstream IPL3 compatibility with changed SP DMA register state is unverified. |
| Command IRQ versus polling | No useful gain | Rejected. |
| FATFS/FIL alignment | Zero observed bounce copies; current fast-seek offsets are 88/96. | No change needed. |
| Bootloader `-O2` | Transient c2 entry: 88.197 ms versus baseline 85.368-85.607 ms | Slower; rejected. |
| Bootloader LTO | Transient c2 entry: 84.747-84.790 ms | Less than 1 ms saved; insufficient gain. |
| Compression c0 | 245,760 bytes; transient entry 84.681 ms | No useful gain; rejected. |
| Compression c1 | Transient entry: 65.757-66.095 versus 85.368-85.607 ms. Installed flash: c1 65.359-65.804 versus c2 84.253-84.337 ms, three runs each. | Flash-tested saving of about 18.5-19 ms. c1 is 114,688 bytes versus c2 81,920 bytes. See installed-c1/c2 logs. Final packaging pending. |
| Logo elision | Real N64 transient c2: 83.886 to 63.466 ms (20.420 ms saved); c1: 65.224 to 52.856 ms (12.368 ms saved). All four boots/music checks pass. Removes 142,592 loaded asset bytes; probes are 65,536 bytes. | Diagnostic only: removes the error, watchdog, and exception logo. One paired sample per compression mode, not installed flash. A safe deferred-asset implementation remains separate work. See `logo-*-run.log` and `logo-probe/`. |

## MCU hardware observations

These are independent variants, not combined firmware. Menu values are microseconds; frontend and music values are milliseconds. First and second observations remain separate.

Completed rows have update/readback logs, two normal boots, four scratch-file hash matches (511, 512, 513, and 131,584 bytes), and a runtime performance capture. These do not cover power loss or every SD failure mode.

| Variant | Menu first / second | Frontend first / second | Music first / second | Status |
|---|---:|---:|---:|---|
| Baseline | 59,421 / 45,019 | 557 / 556 | 585 / 584 | Complete |
| SPI byte batching | 57,168 / 42,815 | 546 / 542 | 572 / 568 | Complete; observed menu saving about 2.2 ms and frontend saving 11-14 ms |
| Adjacent-register groups | 57,950 / 44,096 | 549 / 553 | 577 / 580 | Complete; smaller gain |
| CMD17 | 59,005 / 44,837 | 556 / 558 | 584 / 586 | Complete; little or no boot gain |
| CMD24 | 59,275 / 45,030 | 555 / 556 | 583 / 583 | Complete; no useful boot gain |
| Metadata ordering | 59,049 / 44,889 | 554 / 556 | 582 / 584 | Complete; no useful gain |
| Extra cfg service | 56,152 / 41,896 | 545 / 546 | 572 / 573 | Complete; second-run menu saving 3.123 ms, frontend saving 10 ms. Debounce and save scheduling remain unqualified. |
| MCU `-O2` | 59,005 / 44,821 | 555 / 556 | 582 / 584 | Complete; rejected: no useful gain and 2,176 additional bytes |

Raw logs are authoritative: `mcu-<variant>-boot-*.log`, performance logs, `sd-<variant>.log`, and update/readback files. `hardware-summary.json` has been regenerated from all completed logs, with assertions for 16 successful boot/music pairs, 32 scratch hashes, and eight complete runtime captures with zero underruns.

Metadata and service each pass four scratch hashes and record 599 frames, p99 17 ms, and zero underruns. O2 also passes four scratch hashes and records 599 frames, p99 17 ms, maximum 18 ms, and zero underruns. These figures come from the completed-run report; consult raw logs for other frame/audio metrics.

## MCU host/build evidence and remaining limits

| Candidate | Evidence | Remaining limits |
|---|---|---|
| SPI byte batching | 103,072 cases / 206,144 actual-function operations under ASAN/UBSAN; bytes, CS framing, and read values match. Helper calls: writes 3 to 1, reads 3 to 2. ARM image 21,680 versus 21,712 bytes. RTL at 8 MHz passes with no inter-byte gaps. | Later hardware tests supersede the initial no-flash README. Button cadence, saves, and USB compatibility remain relevant. |
| Adjacent-register grouping | 93,248 host cases; ARG then CMD and DMA address/length/SCR preserve trigger-last order. RTL phase/trigger checks pass at 8 MHz. ARM image 21,752 bytes. | Do not extend to arbitrary registers with side effects. |
| CMD17 | Actual `sd.c` model covers 1/2/255/256/257 blocks, command/DAT/DMA errors, timeouts, and retries. Successful single-sector commands: 2 to 1. ARM image 21,720 bytes. | Existing CMD12 error handling remains; physical error recovery is unproved. Little boot gain. |
| CMD24 | Same model coverage; ARM image 21,720 bytes. RTL `TX_STATUS` waits for DAT0 high after the token; `sd_sync` also waits for idle DMA. | Scratch readbacks cover successful writes, not interrupted-write durability or malformed responses. |
| Metadata | Actual `sd.c` initialization without high-speed support: 15 to 13 commands, CMD7 count 3 to 1, warm initialization zero. Error/reinitialization checks pass. ARM image 21,720 bytes. | Mock omits supported high-speed CMD6 negotiation. Console cycles do not measure true cold-cartridge behavior. |
| Extra cfg service | 10,000 loop snapshots under ASAN/UBSAN; only cfg is duplicated, other services run once in their original order. Source audit covers queued replies and USB retries. ARM image 21,712 bytes. | Another synchronous command can delay writeback and other services. Button debounce counts 64 iterations, not milliseconds. |
| MCU `-O2` | Same application source; ARM image 23,888 bytes, leaving 8,880 bytes below 32 KiB. Baseline loader prefix is identical. | Hardware A/B shows no useful gain; rejected. Existing upstream signed-shift UB remains. |

All MCU candidates deliberately embed the unchanged original loader. Official MCU updates still erase/program MCU flash; an unchanged loader is not a recovery guarantee. SD mocks have no ASAN findings, but UBSAN reports the existing `R3_BUSY` expression `(1 << 31)` in baseline and variants. Those SD runs are not sanitizer-clean. Host models do not establish electrical or card timing behavior.

## Rejected and research-only branches

| Idea | Evidence and disposition |
|---|---|
| 16 MHz SPI | Twenty RTL phase/gap cases produce 40 corrupt readbacks; 8 MHz passes. Reject as-is; no board clock change. |
| Raise MCU-only block count | Actual eight-bit FPGA field: 257 encodes zero and transfers one block. RTL confirms; reject. |
| Coordinated wider FPGA/MCU count | Research only; not implemented or hardware-tested. Requires protocol compatibility, boundary/CRC/error tests, and a reviewed FPGA image. |
| Raise FIFO threshold or assume 8 KiB | Generated FIFO is 1,024 bytes (8 kilobits). The 512-byte threshold reserves a full sector; RTL boundary tests pass. Preserve it. |
| SDRAM pipeline or bursts | Source shows single-word request/acknowledgment delays. No measured bottleneck or prototype. Requires arbitration, refresh, timing, and memory tests. |
| Higher SD clock | Already negotiates 50 MHz, four-bit mode. Higher clocks are not a generally safe optimization; not attempted. |
| Skip SD initialization or read directly into cart memory | Already implemented upstream. |
| Remove CRC or shorten timeouts | FPGA CRC runs in parallel; shorter timeouts do not speed successful operations. Excluded. |
| Skip pending-save wait | Save-integrity boundary; excluded. |
| Remove CIC, RDRAM, or reboot work | Required for compatibility; menu already uses NMI reset. Excluded. |
| Remove VI line wait | No established cost during blank startup; active-video handoff invariant. No candidate retained. |
| SP DMA for tiny reboot IMEM copy | Same register-state concern as rejected DMEM experiment, with smaller potential saving. Not pursued. |
| Remove RTC/settings initialization | Region and configuration dependencies; no safe removal proposed. |
| Arbitrary register-read bursts | RTL prefetches the next register after the final word; side effects require review. Four SD response words were demonstrated in RTL, not implemented as a new MCU candidate. |

`rtl-tests/REPORT.md` records ideal-pin simulation limits. Speculative hardware redesigns have not all been implemented or tested on the board.

## Research-round disposition and restoration (historical)

The best measured candidates are c1 compression (18.781 ms median installed-flash saving), bounded menu extent reads (about 16.9 ms), standalone cursor caching (about 4.3 ms), and MCU SPI byte batching (2.204 ms menu saving plus 14 ms frontend saving in the second-run comparison). These are separate comparisons, not an additive combined measurement. Earlier cursor plus unbounded extent tests yielded only about 0.16 ms incremental benefit, so their standalone gains must not be added.

The clean bounded patch is `bounded-menu-standalone/bounded-menu.patch`; it excludes instrumentation, cursor caching, and PI changes. Its helper is private to menu loading. The generic map API can still return an incomplete map for a truncated chain; this helper detects remaining unread sectors and fails. The patch does not claim general malformed-fastseek hardening.

Normal boot, SD hashes, and runtime tests passed for the MCU variants. SPI batching and the narrow adjacent-register groups are promising on this rig; broad card/save/game compatibility is not established by those checks. Extra cfg servicing remains on hold for debounce and writeback validation. CMD17, CMD24, metadata reordering, and MCU O2 are rejected for insufficient boot benefit. Logo elision is a diagnostic, not a production change. At the end of that research round, no combined firmware package was left installed; the subsequent fork integration below supersedes that state.

Original MCU and bootloader restored. The full firmware readback SHA256 is `A18E37FA61F89293E0B71BA3F245BA79164C651238D77A0ED1EF46615E1F412A`, identical to both original backups. See `stock-final-verification.log`. The owned scratch SD file was removed with the console off. The normal production ROM was uploaded to SDRAM and the cart reset to SD-menu boot. Final boot passed with the preserved Ghosts'N Goblins theme: frontend 556 ms, first music 583 ms. Final runtime capture passed: 599 frames in 10.012 seconds, p99/max 17 ms, zero audio underruns; see `stock-final-perf.log`.

PhosphorOS production source and the SD menu were not changed by these experiments. Experiment artifacts remain under the ignored build directory; this document is tracked separately.

## Fork implementation round

Artifacts for this round are under `build/sc64-fork/` (local and ignored).

| Change | Result | Fork commit / status |
|---|---|---|
| Cursor caching | Installed menu load 45.009 to 40.788 ms; two boot/music passes each; current-source ASan/UBSan fixtures pass; production ROM builds. | `886d7c1` retained. |
| c1 compression | Installed warm IPL3-to-entry 84.070 to 65.112 ms; byte-identical stripped ELF; production ROM 64 to 96 KiB; two boot/music passes. | `427316e` retained. |
| Bounded menu reads | Installed warm load 40.635 to 28.248 ms with cursor caching; current R0.15 ASan/UBSan fixtures and production builds pass; two boot/music passes. | `86f79cd` retained. |
| SPI byte batching | Warm menu 28.020 to 27.731 ms; frontend 557 to 542 ms; four SD hashes, two boots, zero runtime underruns; actual-source byte/CS fixtures pass. | `1d3cc1e` retained. |
| Adjacent register batching | Warm menu 27.731 to 27.524 ms; frontend effectively unchanged (542/543 ms); four hashes, two boots, zero underruns; 93,248 combined protocol cases pass. | `7a5bb99` retained. |

### Final fork artifacts and checks

The five changes are retained in the fork, with portable actual-source host
regressions in `vendor/sc64/tests/` (test commit `4957ab4`). All four suites
pass with fatal ASan/UBSan checks; baseline target-pointer diagnostics remain
visible, while fixture code uses strict `-Werror`.

Clean production artifacts in `build/sc64-fork/`:

| Artifact | Bytes / SHA256 |
|---|---|
| `final-production/bootloader.bin` | 98,304 bytes; `837b85a751b787097ebad2614f6e79fb2f9fa69d25985177d1f6f1c978024997` |
| `mcu-groups/build/app/app.bin` | 21,712 bytes; `b294d1ca45b9f948f0d135a6fde354cc3cf4b1f41184c74fc41939a86cc717be` |
| `firmware-phosphoros-boot.bin` | MCU and bootloader update only; `b42be18d1d4c4329465967ff73d4dcadc1bbf9722b256c1d8acc7a022b5b078e` |
| `final-readback.bin` | Full installed readback; `d0614001ee0e7a17cf3cd6e3c95a822053fb4bb9693198362e80830a0ac2cf2f` |

`final-verification.log` verifies both installed components, the original MCU
loader prefix, the unchanged FPGA and erased padding. `final-boot.log` and
`final-perf.log` record the successful production boot and audio checks. The
bootloader metadata identifies code commit `7a5bb99`; subsequent fork commits
add tests and documentation only. MCU runtime version remains 2.20.2, so use
hashes and commits to identify this fork.

The final frontend counter is 538 ms versus 556 ms in the preceding restored
stock production run; first music is 565 versus 583 ms. Earlier bootloader
phase comparisons remain separate. No end-to-end cold-power total or broad
hardware-compatibility certification is implied.

## SDRAM dispatch-wait experiment — 2026-09-07

**Rejected before flashing: completed Diamond build fails original timing.**
Production FPGA, MCU, bootloader and menu remain unchanged throughout this
round. The isolated candidate bypasses the SDRAM arbiter's idle dispatch
register cycle, then holds the selected owner and complete payload until ACK
is consumed. N64 > CFG > USB > SD priority, PI reservation, flash/BRAM routing,
SDRAM counters, refresh and burst length retain their original contracts.

| Check | Baseline / candidate result | Meaning |
|---|---|---|
| Sequential SDRAM writes, 4,096 words per client | 12,452–12,453 / 8,306–8,318 clocks | About one dispatch clock saved per word; includes row/refresh overhead. |
| Sequential SDRAM reads, 4,096 words per client | 24,877–24,886 / 20,756–20,766 clocks | About one dispatch clock saved per word. |
| Actual DMA, 44 fresh paired cases | 45,612 / 45,244 clocks, 9,472 writes each | Only 0.807% fewer clocks once FIFO and transfer setup waits are included; not a boot-time measurement. |
| DMA stop/restart, 12 cases | Both pass | Continuous request renewal at ACK, odd/even address/length, masks, FIFO stalls, row crossings and PI reservation windows exercised. Abort phase differences prevent treating restart totals as paired speed evidence. |
| Byte/command-timing model | Both pass 17,926 writes and 16,898 reads | Every read checked; masked writes, row/bank changes, refresh, four-client priority and a higher-priority request arriving during an accepted SD transaction covered. |
| Negative control | Broken candidate SD write mask compiles, then fails the byte guard | Test detects corruption rather than accepting compilation as a pass. |
| Complete FPGA build | 88.191 MHz versus required 100 MHz; 453 setup errors, zero hold errors | Fail. Original LPF and device/speed selection retained. No hardware deployment. |

The actual DMA and SDRAM RTL generate requests and ACKs; no synthetic memory
ACK supplies a claimed speedup. The parent byte/timing probe uses a behavioral
SDRAM model, not an electrical model of board skew/setup/hold or retention.
The DMA probe separately observes physical WRITE command/data/mask outputs and
checks the resulting byte image. It does not test the DMA read direction.

Diamond's worst reported path passes from arbiter request selection through
`sdram_grant_address[13]`, the active-row comparison, and the SDRAM bank output
register. The reported physical path is 11.351 ns. Removing a pipeline stage
saves a transaction clock but makes too much logic run within one 10 ns clock.
The final build script exits with its timing error; generated programming
files are not qualified firmware. No real-cart boot gain is measured or claimed.

Reproduction and full evidence are under ignored `build/sc64-memory-wait/`:
`candidate.patch`, `source-manifest.json`, `simulation-result.json`, both
simulation logs, `dma-test/`, and the complete isolated Diamond project/logs.
The candidate, temporary probes and build outputs do not enter production.
A future attempt needs a different request/row-comparison pipeline that closes
100 MHz, plus full simulation and hardware qualification; reducing the clock,
relaxing constraints, refresh or physical memory timings is not this experiment.

## Software-only boot round — 2026-09-07

The FPGA image is unchanged. The retained bootloader removes the decorative
logo while preserving plain-background error, watchdog, exception and test
text. The MCU retains the original loader and uses one full-duplex DMA transfer
for the same six-byte register-read frame. Research notes:
[bootloader review](notes/bootloader-software-review.md) and
[MCU transport review](notes/boot-transport-review.md).

Measurements use Final Fight on the real 4 MiB N64. Bootloader entry is measured
with identical isolated transient probes; the frontend counter starts after
platform initialization and excludes bootloader/IPL3/menu loading. These are
not outlet-to-picture or cold-cartridge measurements. Do not add independently
measured phases into an asserted end-to-end time.

| Experiment | Baseline | Candidate | Decision |
| --- | --- | --- | --- |
| Lossless packed diagnostic logo | Entry 65.806 / 64.792 ms | 61.397 / 60.458 ms | Positive, superseded by user-selected logo removal; no packed decoder retained. |
| Remove diagnostic image only | Entry 65.806 / 64.792 ms | 52.352 / 53.234 ms | Retained in `701e31d`; mean saving 12.506 ms. ROM 98,304 → 65,536 bytes. |
| Full-duplex register read | Comparable frontend 424–425 ms; music 452–453 ms | 419–420 ms; music 447–448 ms | Retained in `a57d302`; repeated modest 4–6 ms frontend gain; MCU +64 bytes. |
| Initial frontend phase profile | Warm ready 425 ms | Theme ~202 ms, root scan ~62 ms, configuration ~36 ms, language cache ~31 ms | Attribution only; all temporary instrumentation removed. |

The first MCU-candidate sample was 512/539 ms; the earlier instrumented baseline
also had a 520 ms outlier. These are retained in raw logs but are not comparable
warm-cache speedups. Baseline restoration is a full byte-identical firmware
readback. Original and newly synchronized libdragon frontend builds both return
425/453 ms without profiling. The runtime source and staged menu are unchanged.

Validation: actual-source ASan/UBSan clear/text/error framebuffer comparisons
pass; real N64 plain diagnostic text CRC is `E6E7751D`, exactly matching the
baseline renderer. The packed experiment's logo CRC was `DAFE56B3`, also exact.
Clean production bootloader builds with `-Werror` and no timing hooks.
Full cursor, bounded FatFs, SPI and grouped-register regressions pass, including
168,608 SPI cases and 93,248 SD-command/group cases. Forty unchanged-FPGA SPI
simulation cases pass. Four real SD roundtrips (511, 512, 513 and 131,584 bytes)
match exactly. Combined firmware runs Final Fight for 589 frames / 10.007 s,
p99 31 ms, maximum 33 ms, zero audio underruns and ongoing GIF progress;
this is a runtime smoke test, not a claim of a measured UI FPS improvement.
Twenty live pings pass with a maximum 79.000 ms response.

The clean no-logo-only installation boots 425/453 ms; the combined installation
boots 420/448 ms and is left installed. Firmware readback verifies the exact
bootloader and MCU payloads, erased tails, original MCU loader and unchanged
FPGA. No FPGA build or update is part of this round. Save power-loss, additional
physical cards and broad retail/64DD compatibility remain broader qualification,
not claims made by these focused tests.

Local ignored evidence is under `build/software-boot/`: `results.json`, paired
boot logs, `no-logo-parent-test/`, `no-logo-integrated-test/`,
`spi-parent-regressions/`, `combined-perf.log`, `combined-pings.json`, firmware
backups/update packages and exact readbacks. Original firmware recovery backup
is `firmware-before.bin`; no scratch SD file remains. No commits are pushed.

### Current artifacts

| Component | Bytes | SHA256 |
| --- | ---: | --- |
| Bootloader | 65,536 | `146e8831eca512cad7af3ba39ca32d1984e3d9ccc9372d1602d70c674edc0684` |
| MCU | 21,776 | `2ff985dc27e726c2d5c8a64c313b2b4065361f723d7e7fc51ad2c8f961415d8a` |
| Installed full readback | 2,179,072 | `84d593bb6d1e81924a5e1b1b314d2eac5a4060cd41952c1023c73a893cd5fbc1` |

### Remaining software leads

Three follow-up reviews are complete: [compression and loading](notes/boot-decompression-followup.md),
[MCU configuration/USB overhead](notes/mcu-boot-followup.md), and
[redundant frontend root scans](notes/frontend-boot-followup.md).
These are unaccepted leads until bounded correctness and real N64 A/B tests pass.
The earlier generic deferred-logo task is superseded by user-selected image
removal; diagnostic text stays resident.

After verification the original Ghosts'N Goblins theme is restored through the normal theme switch funnel; its music starts successfully. Final Fight remains the performance workload for all comparisons above.
