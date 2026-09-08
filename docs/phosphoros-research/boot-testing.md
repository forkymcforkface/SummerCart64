# SC64 boot optimization testing log

Last updated: 2026-09-08.

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
- Software-only reviews continue alongside serialized real-N64 tests; latest
  September 8 results and exclusions are appended below. No FPGA changes.
- Current task: qualify theme-cache ownership, allocator, configuration-index,
  native cart I/O, ROM packaging and language-validation candidates against
  their matched baselines, retaining only independently verified gains.
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

## Software follow-up experiment round (in progress)

Baseline: PhosphorOS `0d64d57c`, SC64 `f5fc7fd`, accepted no-logo bootloader
and full-duplex register-read MCU above. Final Fight is the comparison theme.
Fresh console-off firmware backup matches the preceding full readback SHA256
exactly. An attempted live backup failed its bootloader checksum and produced
an empty file; it is not recovery evidence. No firmware is changed by backup.
Evidence for this round lives in ignored `build/software-boot-round2/`.

| Experiment | State / acceptance requirement |
| --- | --- |
| LZ4 windows 2, 4, 16, 32, 64 KiB versus 8 KiB | Exact loaded-image and full packaging checks pass; real N64 timing starts next |
| Smaller established diagnostic formatter | Implementation and complete format compatibility under investigation |
| Omit unused successful command result reads | Actual-function host equivalence passes; hardware comparison pending |
| Conditional MCU configuration-register read | Matched GCC9 baseline reproduced; host equivalence passes; hardware pending |
| USB status/pop full-duplex frames | Matched builds ready; FIFO/RTL correctness checks pending before hardware |
| USB push batching | Independent matched build ready; FIFO/RTL checks pending before hardware |
| Coalesce redundant pending root scan | Isolated implementation and lifecycle guards under preparation |
| Module initialization attribution | Temporary profiler under preparation; changes depend on measured attribution |

Only repeatable improvements passing their correctness gates become production
commits. Each accepted performance experiment remains independently rollbackable;
test infrastructure and documentation have separate commits. FPGA and MCU loader
remain unchanged. Installed firmware currently remains the baseline. The original
Ghosts'N Goblins theme must be restored after testing; no commits are pushed.

### First hardware pass

All six compression windows boot Final Fight with music. The original large
timing reporter gives entry times 53.429/53.607/52.710/52.272/52.232 ms for
2/4/16/32/64 KiB, against 8 KiB at 52.698 and 53.224 ms. A smaller reporter
removes its printf payload: 50.240/49.452/49.310/49.745/49.813 ms against
8 KiB at 49.758 and 49.771 ms. These are separate measurement series, not a
before/after optimization claim. The ranking changes with probe footprint;
4/16 KiB require repetition before any retention decision. Loaded images are
byte-identical within each series. No compression change is installed.

The established formatter passes its real N64 ABI/renderer comparison:
1,197 format cases, zero format errors, zero mismatched framebuffer words,
29,262 white pixels in both renderings. Appending the negative-control text
produces 376 differing words, proving the pixel comparison is sensitive.
The original renderer's actual uncached framebuffer is used, and the target
reports 4-byte long / 8-byte long long. Final Fight then boots and plays music.
This diagnostic establishes correctness; its timing is not performance evidence.
The production firmware remains unchanged; formatter speed A/B is next.

Module attribution identifies `memview` initialization at 19,367 us, versus
SC64 availability 115 us, repeated firmware version 111 us, LED SET 137 us and
button SET 133 us. Other measured initializers: resident 1,178 us, viz 712 us,
controller pak 406 us, cheats 400 us. SC64's aggregate 2,673 us includes the
temporary command-attribution logging. The profiler's total boot time is not
a production baseline. No version-cache or LED/button elision is justified by
these sub-0.2 ms command timings. A separate candidate removes the redundant
early Memory-view statistics sample while retaining its declaration and its
existing activation-time refresh; build and hardware comparison are pending.

Memory-view deferral is rejected after testing: baseline warm ready 419/420 ms,
candidate 419/420 ms; cold candidate 513 ms overlaps baseline 511/515/517 ms.
The statistics seam calls `phos_cart_cache_open`; removing that first call
merely moves the required cache-open/format into `phos_theme_engage` through
`phos_cart_cache_theme`. The 19 ms attribution is real work, not avoidable work.
No production Memory-view change is retained. Its isolated target build and
activation guard pass, but that does not make it a performance improvement.

Frontend ROMs have different build timestamps, deliberately invalidating the
cart cache when switching images. Cold and consecutive warm results are kept
separate; the stamp is never forced equal across binaries. Browser root-arm
candidate cold 513/515 ms versus adjacent baseline 515/517 ms; warm 415/414 ms
versus 419/420 ms. Final restoration/repetition and focused lifecycle validation
remain pending before acceptance.

The formatter's minimal transient probe records entry 48.195/48.559 ms versus
49.190/49.213 ms baseline; menu-load results overlap. Unused-response candidate
entry 49.209/49.240 ms, menu 28.026/28.010 ms versus baseline 28.091/28.100 ms:
the tens-of-microseconds menu difference requires attribution and repetition,
not a millisecond-scale gain claim. Installed-flash formatter comparison is
underway. The cart currently contains the original-formatter minimal timing
probe; readback verifies unchanged MCU and FPGA. Restore a clean bootloader
before completing this round.

### Accepted formatter

Installed-flash baseline entry samples 49.686/49.628 ms versus candidate
47.524/48.034 ms give a mean reduction of 1.878 ms. Entry is the measured
IPL3-to-C phase, not total outlet-to-picture time. First boots after MCU/firmware
reset perform SD initialization (menu load about 42 ms); consecutive warm reads
are about 28 ms, so these are not pooled into a claimed formatter I/O gain.

Performance commit `faacf01` retains the pinned formatter; `a5978e2` adds its
independent regression gate. The clean production image is 49,152 bytes,
SHA256 `722056face42e8dd48e6ea5294d46efb7b7fdeeb59efc08884e1a16e0c724519`.
Exact firmware readback matches its payload and erased tail, with original MCU
and FPGA unchanged. No research/timing symbols remain. Normal installed SD-menu
boot passes at 421 ms ready / 448 ms music. This clean image is installed and
becomes the fixed bootloader baseline for subsequent MCU experiments.

Additional agent research continues at the user's request: small register-group
TX staging, combined SD DAT/DMA command grouping, and SC64-menu-only file padding
are isolated leads. They have no production acceptance yet. R1b status reuse is
excluded before hardware because independent command completion and DAT0 busy
signals lack the required ordering guarantee; the fresh status read stays.

### Continuing software-only queue

Browser root-scan coalescing is accepted in PhosphorOS `0b2d3e5b`, with its
identity guard in `32bdf743`. The full production matrix passes. Seven focused
host captures match baseline byte-for-byte after a four-second scan settle;
the earlier half-second empty captures were premature on both builds. N64
root/navigation/theme checks pass with music and zero underruns. Integrated
production ready is 508 ms cold / 414 ms warm; the controlled warm comparison
is 419/420 ms baseline versus 415/414 ms candidate.

The original cache-open candidate is excluded before hardware: publishing a
valid new-theme header before clearing all entries permits interrupted writes
to expose stale sealed entries. A separate table-first variant is under review;
its fault-injection guard must include surviving tail entries, real payload
validation and a failing unsafe-variant control before hardware acceptance.

Pending independent hardware candidates: CFG software-query read elision; USB
read and push batching; register-group TX staging; combined SD start grouping;
timer reciprocal arithmetic; libcart within-call sector cursor reuse and
completed-status snapshot reuse; full-menu c0/c1/c2 decompression, six c1
windows and SC64-only 512-byte padding. Source/RTL tests establish only their
stated contracts, not hardware timing or universal firmware safety. Parent
owns the cart; agents continue independent source research and isolated builds.

CFG query candidate has passed exact MCU readback, preserving original loader,
FPGA and accepted clean formatter bootloader. Live same-value configuration,
invalid-ID error and recovery checks pass for both baseline and candidate.
Its first post-update boot is 421 ms ready / 448 ms music, with SD initialization
43.137 ms; warm comparisons and baseline restoration are still pending.

CFG-query experiment is rejected for boot performance: candidate ready 421/421 ms,
restored baseline 422/421 ms, preceding baseline warm 421 ms. Warm menu read
28.153 ms candidate versus 28.065 ms restored; no repeatable gain. Exact original
MCU readback after restoration passes. No production CFG change is retained.

USB-read batching passes exact firmware readback, live configuration errors/
recovery, and a 1 MiB deterministic SD round-trip hash. Boot ready 422/422 ms,
music 449/449 ms; warm menu load 27.475 ms. A first upload comparison differs
substantially (4,244 ms baseline, 533 ms candidate), but the baseline created a
new file while the candidate overwrote it. This is not yet valid throughput
evidence; repeated overwrite measurements on restored baseline are in progress.

Parent reruns the strengthened cache-format fault gate successfully. A sealed
entry at index 255 with a valid payload header is found before interruption.
Six table/header interruption boundaries reject it under the new theme with
the table-first candidate; the original header-first candidate wrongly accepts
it after each interrupted table-clear boundary. The safe candidate remains
unapplied pending hardware A/B.

### Full-menu compression measurement

USB-read and USB-push are not retained: matching overwrite transfers remove
the apparent upload gain (baseline 533/546 ms, read candidate 533 ms, push
530/529 ms). Download results overlap at 394-406 ms. Ready 422/422 ms read,
423/422 ms push, restored 422/423 ms; warm menu 27.475/27.536 ms candidates
versus 27.375 ms restored. Both configuration and exact 1 MiB transfer gates
pass; restored/push playback smoke reports zero underrun/producer overruns.
Original MCU is restored and exact-readback verified before menu comparisons.

Full-menu c2 timing exposes a substantial phase outside frontend boot_ms:
273.630/273.652 ms from menu IPL3 Count reset to platform_init. Warm SD load
is 27.384 ms, sum 301.036 ms. Same-ELF c1 measures 145.972/145.956 ms; warm
SD load 36.428 ms, sum 182.384 ms: initial net reduction 118.653 ms. Loaded
ELF segments are byte-identical, same metadata/cache stamp and assets. Both
run Final Fight with music. C2 restoration and c0 control are pending before
production selection. These sums exclude later platform setup and frontend
boot_ms and are not claimed as total power-to-picture measurements.

Physical SD original menu is backed up and SHA256-verified against original
3ed181a976cee2f272f08e1a7bf510bbd6d596b947e326aace83df0723e94784. Each
experimental SD upload is downloaded and hash checked. Current SD contains a
temporary timing menu; final clean menu and normal SD boot must be restored.

### Accepted full-menu LZ4 packaging

PhosphorOS `19fd308f` selects stock compression level 1 for SC64 only; explicit
overrides and other carts retain their previous behavior. C2 restoration repeats
273.646 ms pre-platform, confirming the earlier 273.630/273.652 ms results.
C0 control is slower than c1: 209.475 ms pre-platform + 55.108 ms warm SD =
264.583 ms. C0 also overlaps the resident cheatsearch mailbox and approaches
the IGR 1 MiB copy bound, so it is not a production candidate. No size gate,
resident layout or toolchain patch is introduced.

Clean canonical N64 build passes at 638,976 bytes, SHA256
1a25ea3df56352de63a8892aca9ed75a7926ce3e13a0411c3b7e40fa53c8ec2e.
ELF has no temporary attribution markers. Persistent SD+SDRAM deployment,
reset and downloaded SD hash verification pass. Clean boot is 513 ms cold /
414 ms warm; music 541/442 ms. Playback smoke: 568 frames/10,010 ms, zero
underrun/producer overruns, GIF tick 599/frame 563/drop 35. Scene-dependent
playback is only a health check, not an FPS improvement claim. C1 clean ROM
is preserved in round3/c1-production-clean.n64 while subsequent isolated
experiments continue.

### Additional attributed costs

Platform-only diagnostic: all constructors together 0.912 ms; FAT mount
5.616 ms; synchronous RTC 3.658 ms. An RTC overlap candidate starts detection
after card initialization and preserves the original readiness barrier. It
is source-tested, including a failing omitted-barrier control, but hardware
comparison remains pending. Other platform intervals are preserved in
round3/platform-attribution-boot1.log; diagnostic total is not a baseline.

Cache diagnostic warm: language hit, identity 4 ms/read-validation 27 ms;
theme hit, identity 8 ms/read-validation 31 ms. Cart open 11 ms with one full
directory flush, no format/theme reset. Cold has 18 ms initial cart open, four
full directory flushes and two formats. The safe cache-directory candidate is
undergoing baseline/candidate/baseline hardware comparisons.

Config/gamedb diagnostic warm: config 42,324 us total; file open 2,422 us,
reads 9,728 us, parsing/callbacks 28,259 us; nested key insertion 18,353 us
for 206 unique rows. Gamedb 15,018 us total: DAT 6,933, index header 2,114,
fences 3,854, user overlay 521, migration 3 us. Per-call clock overhead and
unclassified work mean attributed subtotals are not forced to sum exactly.
Config lookup is now a measured lead; both required startup owners remain eager.

### Accepted cache directory transfers and window sweep

PhosphorOS `d3a404b1` retains the safe cache transfer changes; `749e24e1` adds
the default lint fault-injection gate. Isolated baseline/candidate/baseline:
cold 512/501/519 ms and warm 420/415/421 ms. Integrated with root coalescing
and c1, clean ready 496 ms cold / 410 ms warm, music 523/438 ms. Final
comment-only rebuilt image cold 494/521 ms passes. Target build and lint pass;
no diagnostic markers are linked. Ghosts'N Goblins and Final Fight theme
switches restore twelve root rows and play their expected songs. Final Fight
playback after switching: 478 frames/10,001 ms, no underrun/producer overrun,
GIF tick 598/frame 467/drop 131. This is a health check, not an FPS gain claim.

All six full-menu c1 windows pass exact loaded-image decoding and physical
boot/music gates. Initial comparisons include SD initialization equally:

| Window bytes | Menu bytes | Pre-platform ms | SD load ms | Sum ms | Disposition |
| ---: | ---: | ---: | ---: | ---: | --- |
| 2048 | 704512 | 156.859 | 53.535 | 210.394 | Slower; reject |
| 4096 | 671744 | 150.965 | 52.035 | 203.000 | Slower; reject |
| 8192 | 638976 | 145.965 | 49.955 | 195.920 | Stock c1 reference |
| 16384 | 606208 | 144.806 | 48.498 | 193.304 | Repeat/production tool qualification |
| 32768 | 589824 | 154.671 | 48.073 | 202.744 | Slower; reject |
| 65535 | 573440 | 162.147 | 46.935 | 209.082 | Slower; reject |

Repeated 16 KiB window warm sum 179.552 ms versus restored 8 KiB 182.395 ms
(a 2.844 ms reduction). Startup itself repeats 144.792 versus 145.951 ms.
The larger dictionaries reduce SD bytes but can increase decoder time; size
alone is not an acceptance criterion. The explicit-window compressor option
is not present in stock upstream. An additive, separately named compressor
and its provenance/default-equivalence gates are being evaluated without
changing the installed stock tools or compiler/library. No custom production
tool or window setting is accepted yet.

The first config-index proposal is not deployed: parent review caught duplicate
index insertion and missing sort/hydration/failure-path coverage. The corrected
variant limits indexing to config, preserves theme behavior, and passes an
actual-source lifecycle/OOM/collision guard with a failing stale-slot control.
It remains hardware-unqualified; the 18 ms kv_set attribution includes retained
allocation costs and is not the predicted index saving.

### RTC overlap and cache read attribution follow-up

RTC baseline/candidate/baseline/candidate real-hardware intervals are
501734/334593/509307/334480 Count ticks (46.875 ticks per microsecond).
The complete mount-plus-RTC interval falls from a mean 10.784 ms to 7.137 ms,
a 3.648 ms reduction. Both candidates report present=1, source=1 and an
advancing valid clock. The retained readiness barrier takes 56 ticks after
mount, versus 171549/171563 ticks synchronously. Warm frontend baseline
427 ms versus candidate 425/424 ms; the first baseline 522 ms is cold and
is not compared to warm candidates. All boots play Final Fight music.
Clean integrated build matrix passes; clean hardware acceptance is pending.

The fine cache probe finds language index read 4.988 ms, arena read 12.741 ms,
CRC 4.296 ms and validation 2.777 ms. Theme body read 8.780 ms, CRC 2.146 ms,
row hydration 18.932 ms, including key insertion 17.191 ms and its nested
allocation/copy cost 10.356 ms. These nested values must not be double-counted.
Actual target Newlib uses a 1024-byte stdio buffer, below the FAT cache's
16-sector/8192-byte bulk threshold. Two-call 8/16 KiB stream-owned buffering
candidates pass real-source parser/cache fixtures and are being measured.
The 8 KiB candidate first repeats 413/413 ms versus baseline warm 422 ms;
restored baseline and 16 KiB controls remain pending. No gain is accepted yet.
CRC loop unrolling, config indexing, and allocation reduction remain separate
candidates; no CRC validation or cache identity checks are removed.

### Retained RTC and binary-cache buffering

PhosphorOS `68845a42` retains RTC overlap; `a7dd24bb` adds its actual-source
1280-case readiness/fallback gate to lint. Clean integrated ROM SHA256
 e0f429e0781e544496c5c50eea9810e4ffc6f9ce4fcedaa9d00efe7f2a1f98a4
boots cold 498 / warm 413 ms, music 525/441 ms. Read-only RTC query reports
source=1, 2026-09-08T00:51:28, weekday 2. Clean combined totals are health
checks; the matched RTC window comparison establishes its isolated gain.

PhosphorOS `2349ab0b` retains 16 KiB buffering for the two binary cache reads.
Independent warm ready measurements on fixed-metadata ROMs:

| Variant | Ready ms | Music ms | Disposition |
| --- | --- | --- | --- |
| Original 1 KiB buffer | 422, restored 423/423 | 450, restored 451/450 | Baseline |
| 8 KiB | 413/413 | 441/441 | Works, slower than 16 KiB |
| 16 KiB | 409/409 | 437/437 | Retained |
| Unbuffered | 415 | 443 | Works, slower than 16 KiB |

All use the original file format and checks. Buffer ownership ends at fclose;
only one additional 16 KiB buffer exists at a time. Canonical full matrix,
lint and existing language/theme cache fixtures pass. Clean integrated ROM
bddc42b065001641d887d1ce5e83a5dcc30a0ba264d31092845983ea2893f0dc
is preserved as round3/buffer-production-clean.n64 for queued hardware smoke.

The 8 KiB diagnostic attributes language read/validation 20.890 ms versus
26.889 ms default, theme 32.073 versus 34.208 ms. Unbuffered diagnostic reads
language index 4.121 ms, arena 11.208 ms and theme body 5.972 ms. Diagnostic
build totals are not used as clean performance comparisons.

Config detail independently repeats 206 inserted rows, no replacements:
scan/hash 4.564 ms, table growth 0.406 ms, strdup/copy 12.082 ms. Allocation
cost dominates; the pending config index cannot eliminate the latter cost.
Theme-arena parent rerun passes both real-owner suites, cache lifecycle tests,
and exact assertion failures for ownership/order negatives. Hardware is pending.

### Independent CRC and native read comparisons

CRC8 unroll first baseline/candidate/restored baseline: cold515/515/513 ms,
warm422/419/421 ms, music450/447/449 ms. The 2-3 ms warm lead needs another
candidate repeat before retention. Actual-source parent test passes all lengths
0..4096, 16 alignments, larger payloads and streaming chunk chains; skipping
one byte fails specifically at length8.

Original-source native counter: dram_calls138, cart_calls41, reads179,
sets179, sectors1821, nonempty_dram138, extra_sets0, bounce_sectors0.
The independent within-call cursor candidate has no removable SET work on this
build. Ready baseline420/421, cursor422/421, status-reuse422/422,
restored422/423 ms. Both candidates boot/play normally but neither establishes
a performance gain; neither is retained. The accepted16KiB cache buffers can
introduce longer reads, so matched candidates are retargeted to2349ab0b before
closing this interaction. No cross-call cursor cache or bus lock is invented.

Full compressor Docker recipe builds under a research tag. Its stock tree
matches2123/2126 files exactly. The two library archives have identical object
members/order/symbol tables, differing only in ar modification-time fields.
cpaktool differs only in its build-time banner and resulting GNU build ID
(25 bytes). Parent reruns the bounded comparison and changed-executable-byte
negative successfully. The earlier derived-image2126-file equality remains a
separate proof; the full rebuilt tree is not falsely described as byte-identical.
The canonical image is unchanged pending current-ELF window hardware repeat.

### Accepted current-code compression window and CRC repeat

Current RTC-source matched window comparison:

| Window | Warm SD load ms | Pre-platform ms | Sum ms |
| --- | ---: | ---: | ---: |
| 8KiB baseline | 35.976 | 145.987 | 181.963 |
| 16KiB candidate | 34.363 | 144.878 | 179.241 |
| 8KiB restored | 35.896 | 145.981 | 181.877 |

Loaded ELF bytes, metadata and cache stamp are identical; each SD upload is
read back and hashed. Every boot/music gate passes. PhosphorOS64fb9051 adds
the separately named packaging auxiliary;38b9fa55 selects16KiB for SC64 c1;
e283c914 documents it. Full canonical image and production matrix pass. A
Windows CRLF patch checkout initially failed the image's patch-apply gate;
LF attributes/actual file normalization correct it, with no failed image installed.
Clean606208-byte ROM SHA dd5cde483758f2449d19e1c3af6214c67e4a836c62e6b2e04da0ada0aee84138
is preserved as window-production-clean.n64. Clean hardware smoke is queued.

Cache-buffer integrated clean ROM boots487ms cold/401ms warm, music515/429ms.
These are frontend-ready/music metrics, not total power-to-picture times.
CRC candidate warm repeat420/419ms supports the first419ms against baseline
422/421ms. Its coherent source integration and full production matrix are running;
the default actual-source gate is prepared separately with argv-only Docker calls.

### Remaining qualified hardware queue

- MCU group-TX, SD-start-group, timer reciprocal and short polled read: original
  loader hashes, independent source/RTL/fault proofs and second-agent review pass.
  Parent now runs baseline/candidates/restored baseline with the original menu,
  exact firmware component readbacks, two1MiB SD roundtrips and playback checks.
- Native cursor/status retargeted to2349ab0b (16KiB cache buffers): independent
  ROMs and counter probe ready; older-source no-gain result remains recorded.
- Theme string arena, config index, generic4KiB INI buffering and4KiB gamedb
  index buffering: source/host gates pass; real menu A/B remains pending.
- TLSF modulo-mask and aligned-peek: parent repeats65536-operation sanitizer
  traces with identical allocation layouts, plus2097152mask cases and exact
  wrong-alignment negative. Real N64 A/B remains pending; combinations require
  a separate merged build and revalidation.
- ROMPAK bounded DMA search,512-byte SC64 padding and heap-log consolidation
  remain pending on hardware. No mandatory constructor, RTC/TZ behavior or
  floating-point exception diagnostic is removed to reduce linked libc size.
- Allocation phase diagnostic and additional bit-scan candidates are in review;
  instruction counts are not hardware cycle/performance claims.

### Completed remaining MCU hardware experiments

Every candidate is an independent app-only update from2ff985dc. Full readback
checks confirm exact app bytes, erased tail, unchanged original4096-byte loader,
FPGA and formatter bootloader. Each passes live configuration/error queries,
two exact1MiB SD write/read roundtrips, Final Fight boot/music and ten-second
playback with zero underrun/producer overrun. These are the exercised safety
gates, not universal card/power-loss certification.

| MCU | Warm frontend ready ms | Warm SD menu load ms | Result |
| --- | --- | --- | --- |
| Baseline | 421 | 27.444 | Reference |
| Grouped small TX | 422/422 | 27.427 | No boot gain; reject |
| Grouped SD start | 421/421 | 27.513 | No boot gain; reject |
| Timer reciprocal | 421/421 | 27.679 | No boot gain; reject |
| Short polled read | 440/440 | 28.090 | 18-19ms slower; reject |
| Restored baseline | 422/422 | 27.599 | Restored and exact-verified |

Host SD roundtrip timings overlap baseline process/USB variability. Original
baseline write540/527ms read402/406ms; restored write539/529 read406/392ms.
Polled write550/538 read406/408ms. No transfer-performance win is retained.
Full per-candidate JSON, boot and playback logs are round2/mcu-final-*.
The current firmware is the proven2ff985dc MCU with the accepted formatter
bootloader; no new MCU candidate or FPGA change remains installed.

CRC source is retained as2410b611 after repeated positive boot comparisons and
full production matrix; e8c1a8ee adds its default equivalence gate. The final
gate compares each incremental chain directly to one independent monolithic
reference, avoiding redundant re-tests of the reference itself. The window
option-effect gate is1e14e1ff; its omission negative now fails specifically at
the missing size effect, while decoder-only validation previously passed it.
Clean window production boots402/401ms, music430/429ms; packaging gain is in
the separately measured pre-platform/SD phase, not those frontend metrics.

### September 8: continued independent frontend trials

Clean CRC production smoke passes: frontend ready 486 ms on first boot and
399 ms warm; music 513/426 ms. These exclude pre-platform work and are not
power-to-picture measurements. The clean ROM hash is
eeb520424bcfae7be6748bddb75e4ef8bd5c218c22a5705a5dbf89fd18fd9f16.

Theme string arena: matched immutable c2 baseline warm 421 ms, restored
420/420 ms; candidate 412/412 ms, music 440/440 ms. Further repeat and final
allocation-failure hardware probe remain in progress. The 4 MB console passes
Ghosts'N Goblins to Final Fight switching with BGM; ten-second playback reports
544 frames, gif_frame=537, gif_tick=599, underrun=0 and produce_over=0.
No comparison of those playback counts to a boot baseline is claimed.
The independent host ownership/fault gates pass; production integration and
full matrix are in progress, not yet committed or accepted as complete.

Heap-only O2 is a new independent queued target-build candidate. Its 1,424-byte
text increase leaves the padded ROM size unchanged; matched early-Count probes
will measure decompression cost as well as clean frontend timing. Parent
reruns actual linked N64-code allocator checks: 10,000 mixed operations pass
content, alignment, failed realloc preservation, calloc overflow, accounting
and balanced interrupt nesting. Instruction counts alone are not speed proof.
TLSF fls16 and builtin controls are also queued; parent sanitizer traces and
the specific wrong-zero negative pass. The builtin is not assumed faster.

Coverage audit reconciles 176 raw logs and exact MCU component/SD roundtrip
proofs. Small bootloader windows are rejected for unstable ranking/probe drift;
unused response reads are rejected within noise, not left awaiting more tests.
Menu-only PI DMA handoff and atomic READ_AT are research, not implemented or
hardware-tested results. Fragmented extent streaming has no normal-menu
opportunity; DAT_OK snapshot reuse remains unqualified for ordering. Historical
extra CFG servicing is still held for debounce/save-scheduling qualification.
The original MCU, loader and FPGA remain installed; no new FPGA work is used.
### September 8: cache repeat, recovery, and exclusions

Arena repeats 411/411 ms against restored 420/420 ms. Real 4 MB fault ROM
47b228e63ebde6a37f367a5305fa67d6d96b61cd1ad6a9bf8799540b2bde3c97
logs final arena-allocation injection at 202 rows/4256 string bytes, then
fallback=ini success=1, ready500/music527. Subsequent clean production build
boots469/388 ms, music496/416 ms; SHA
d19a5333726443d8bf2a0e77a8a40b6e87ac1b8f91011ebb428377aec48181df.
All production builds pass. Parent catches a missing Docker -i in the new
production ownership runner: the first matrix compiled successfully but this
new runner executed no fixture. After correction, standalone and integrated
lint execute4361cases and both exact negative controls successfully. Current
c1/16K matched early-Count/SD comparison remains pending because the clean
arena ROM grew one16KiB padding block; frontend savings alone do not establish
the full boot tradeoff.

Generic4KiB INI buffering421/422ms and gamedb index4KiB422/422ms do not beat
matched baseline420/420ms. Both boot/play music and pass their host behavior
gates, but are rejected for no benefit; the gamedb variant also retains3KiB
additional stdio memory. Neither enters production.

Historical extra CFG servicing BEFORE writeback is now excluded with a concrete
actual-owner safety counterexample, independently repeated by parent under
ASan/UBSan: over1000loops baseline sends the pending save once and clears it;
extra CFG sends zero saves, keeps it pending and acknowledges1000AUX packets.
The second CFG pass consumes every USB pending slot immediately after USB
service frees it. This disproves fairness for that placement; it is not a
hardware test or a claim that every alternate placement is unsafe.

Queued language validation preserves the prior bounded-NUL acceptance rule by
finding the last NUL once. Parent repeats62496CRC-valid malformed cases on each
source with identical10095accepted, the exact omitted-trailing-scan negative,
and both11776-value editable-language suites. Hardware timing remains queued.

### September 8: retained arena and storage transition

Retained arena source/ownership contract and clean SD deliverable as e4493948;
46ebf515 adds the default actual-owner fault gate. Current matched c1/16KiB
Count pair uses source1e14e1ff plus identical first-statement Count probe:

| Warm phase | Baseline A | Arena | Restored baseline B |
| --- | ---: | ---: | ---: |
| SD menu load us | 34271 | 35446 | 35011 |
| Menu IPL3-to-platform Count ticks | 6786988 | 6792678 | 6785587 |
| Frontend ready ms | 402 | 393 | 397 |
| Sum of these measured phases ms | 581.060 | 573.356 | 576.770 |

Against the bracketing mean, gain is5.559ms despite16KiB larger ROM. This sum
EXCLUDES platform_init and other unmeasured power-to-picture intervals. The
baseline frontend has a5ms spread; do not present9ms as an exact universal win.
Both SD menus are downloaded and exact hash-verified. Clean production ready
388ms/music416ms remains a separate smoke, not a summed timing claim.

D: fills during further isolated builds. Allocator mask419/419ms matches
baseline419ms; peek418/418ms is tentative pending the later restored baseline.
The batch stops before fls16 because it cannot create its log: that incomplete
D log is NOT a failed N64 boot or a passed trial. New builds and logs move to
E:/phosphor-boot-round3; original inputs remain onD. The owning timing loop is
unchanged; frontend_trial/menu_trial copies only change output paths. Production
worktree onE begins46ebf515 and uses local shared source clones, preserving
canonical tools/build.sh and product paths.

Automatic cleanup review rejects generated-directory deletion. One agent then
improperly retries through Python and removes only the two matched Count
root-baseline/build and root-arena/build trees, freeing28147712bytes. Parent
stops all further deletion/move attempts, discloses the mistake and independently
hash-verifies both copied ROMs and ELFs against their prior provenance. Their
sources, copied artifacts and firmware recovery backups remain intact. The
removed trees are rebuildable intermediates, not measurement/recovery evidence.

New native buffered counter: dram_calls121 cart_calls41 reads165 sets165,
sectors1819, nonempty_dram121, extra_sets3, bounce_sectors0. Cursor reuse has
three potential eliminated SETs; READ_AT would need separate initial-SET
attribution and version/capability/error semantics. No new protocol is accepted.

Blanket extra CFG after writeback also starves USB button notifications: actual
button/CFG/USB owners produce one debounced button packet in1000baseline loops,
zero for either extra-CFG placement under sustained AUX arrivals. Both versions
are excluded before hardware. Menu-only PI DMA handoff is likewise excluded:
it changes inherited PI DMA address/length state for unknown third-party menu
IPL3s. A reliable complete-IPL3 guard costs the same PIO reads being removed.
Its source model/build passes are not hardware qualification.
### Round3 continuation: config index and remaining qualified candidates

Root 187de724 prepares owner-fixture calloc/index cleanup; 8b598a27 accepts
configuration indexing; 0ccd09f1 installs its default lifecycle/OOM gate.
The standalone production clone on E replaces the Docker-incompatible linked
worktree. The final config-index matrix passes all nine production targets,
SC64/EDX/ED64P and lint. Earlier missing-fixture runs are incomplete, not passes.
E:/phosphor-boot-round3/config-index-final-matrix.log is the completed gate.

| Current matched warm candidate | Baseline A / restored B ready ms | Candidate ready ms | Decision |
| --- | --- | --- | --- |
| Config lookup index | 390 / 393 | 375, 376 | Accepted, 8b598a27 |
| Utils-only O2 | 390 / 393 | 384, 384 | Positive; production cart gates/smoke pending |
| Heap-only O2 | 391 / 392 | 383, 383 | Positive; production integration pending |

All six current candidate/baseline ROMs remain622592bytes. Corresponding SD
load and first-platform Count logs are under E:/phosphor-boot-round3/hardware/
current-*. These ready_ms values exclude platform_init and are not total
power-to-picture. Config production cold455/warm377ms, music481/403ms;
10-second Final Fight capture570UI frames, GIF561frames/598ticks, underrun0,
produce_over0. Both theme switches complete and resume music on the4MB rig.

Old-baseline microexperiments are closed: INI4KiB421/422ms; gamedb index4KiB
422/422; TLSFmask419/419; fls16 422warm; builtin-fls438/439; language validation
423/423; removing cache qsort422/422. Bracketing baselines span419-422ms.
None establishes a retained gain. TLSFpeek418/418 then419/419 also falls within
that spread and is rejected. Current native cursor402/401ms and status401/401ms
match current baselines401-402ms; neither is retained. Source/model savings
are not substitutes for N64 results.

READ_AT independent and parent source gates pass4224MCU cases,24explicit
unsafe-legacy-overflow boundary rejections,7680native cases,12capability/init
cases and three fault-derived negatives. Candidate app ff00d9ed7f6a994a04786420
is21840bytes; matching baseline reproduces installed2ff985dc. No firmware flash
or hardware READ_AT qualification has occurred yet. The warm removed-SET work
measurement10.742ms is only an upper bound, not an achieved saving. The new
command bounds fixed8KiB BRAM; it deliberately rejects legacy address-addition
overflow and leaves original I/s unchanged. Recovery loader/FPGA stay original.

Font diagnostic records all four Final Fight fonts using native sprite loading,
not BMP decoding or the generic cache route. Warm load12.391/20.410/10.323/4.394ms;
CI8 master4.569/7.954/4.798/2.102ms. This is attribution-only. Agents investigate
native loading and atlas construction, plus loader cache-flush work; no candidate
is accepted from these measurements. Heap-log, bounded ROMPAK and sector-padding
comparisons remain in the serialized parent-owned hardware queue.

### Integrated results and native-font follow-up

The current measured phase sums (SD load + IPL3-to-platform + frontend ready)
are556.319ms for configuration indexing, against570.179/572.785ms bracketing
baselines. They still exclude platform_init and are not power-to-picture.
Individual utils/heap O2 trials improve those sums by7.419/8.542ms, but the
accepted configuration index removes their demonstrated integrated benefit:

| Integrated production trial | Warm frontend ready ms | Disposition |
| --- | ---: | --- |
| Config index baseline A | 377 | Accepted source baseline |
| Index plus utils O2 | 377 (earlier376) | Rejected: no clear added gain |
| Index plus heap O2 | 380 | Rejected: no clear added gain |
| Restored config index B | 380 (first warm377) | Baseline variation, not a compiler gain |

Both compiler flags are removed from the integration source. Their isolated
instruction-model and old-baseline gains do not justify stacking them.
Heap-log consolidation reduces its measured platform interval from about
101418 to50713 Count ticks (~1.08ms), with unchanged heap work. This is a local
positive only; no integrated whole-boot acceptance or commit yet.

Bounded ROMPAK DMA search is rejected: original28758/28759ticks vs
candidate36207/36183ticks (~0.61 vs0.77ms), with candidate entry Count also
higher. ROM/TOC cookies and every SD download are verified. No code retained.

| Paired native sprite / atlas trial | Warm ready ms | Assets ms | Status |
| --- | ---: | ---: | --- |
| Native baseline A | 389 | 117 | Control |
| Loose sprite stdio16KiB | 380,379 | 107 | Positive, slower than unbuffered |
| Loose sprite unbuffered | 376,377 | 103 | Best candidate; current-index integration pending |
| Restored native baseline B | 392,391 | 118,117 | Control |
| Indexed atlas map removal | 387,387 | 112 | Positive; integrated/resource qualification pending |
| Restored atlas baseline | 391,392 | 117 | Control |

All native pairs use the exact fixed d68 display/cache identity,622592-byte
ROMs, Final Fight, original MCU/FPGA and retained formatter. The full current
index+unbuffered production matrix passes; default actual native-owner64cases
plus the exact ASan double-free negative pass. Root e3e0a9c1 commits only that
test gate. Candidate clean ROM is478f4d609b92668716334c3d72962167275e47432b73cc8a7834cb10445def04;
production hardware and persistence deployment are still pending.

All four actual installed font sprites are downloaded read-only and confirmed
CI8/v6. Exact indexed-plane/palette output comparisons cover41184pixels plus
4000randomized cases and the reachable255-visible-colour boundary. More than
255visible colours is impossible for valid CI8 because the top-left source
index is transparent. Source-reuse follow-up has a separate memory tradeoff:
it retains native sprite overhead; no retained-memory reduction is claimed.

Old-MCU READ_AT qualification reports13checks, zero failures, unsupported
capability and only legacy reads. All data and guard cases complete, including
1/16/33sectors at start/end and aligned/bounce buffers. The initial standalone
capture also logs a debug-data flush: the temporary harness accidentally pipes
power-on status text into debug stdin. Parent corrects that redirection and
queues a clean repeat. This is not an SD-read failure, but the capture anomaly
is not hidden. No READ_AT firmware flash has occurred.

Loader-only whole-cache experiment passes source ordering/model negatives and
independent packaging review. Its signed stage1 is byte-identical to upstream;
canonical packing moves TOC0x1930 to0x1980 without changing executable payloads.
Legitimate generated cookies remain intact. Current Count hardware is underway;
no loader performance result or acceptance yet. No FPGA changes are involved.

### Current-stack acceptance and further parent trials

Root078e6a77 accepts unbuffered loose native sprite reads after the complete
production matrix, default64-case owner gate and specific double-free negative.
Clean current production ROM478f4d609b92668716334c3d72962167275e47432b73cc8a7834cb10445def04
boots Final Fight cold440/warm361ms, music466/388ms; the prior index-only
production warm result is377ms. Ten-second playback records576UI frames,
574GIF frames/598ticks and zero audio underruns or producer overruns. Both
Ghosts'N Goblins and Final Fight switch successfully, with zero retired GPU
resources after settling. Persistent final deployment remains queued.

The old-MCU READ_AT qualification is repeated with power status correctly
redirected away from debug stdin:13checks pass, no failures or transport errors.
New firmware remains unflashed. Current078e clean and absolute Count pairs are
staged to include the capability-query cost before boot_t0 in the comparison.

The loader-only full-cache candidate records warm first-platform Count6476436,
against6792036/6792139 bracketing controls: about6.734ms earlier entry. Warm
frontend ready391ms versus392/392ms; SD loads35103us versus35892/34939us.
This is a positive isolated result, with production integration still pending.
No MCU loader, FPGA, clock or signed menu stage1 changes are involved.

Unrestricted indexed source-atlas reuse is rejected before hardware. Actual
linked native-parser allocation modeling accepts otherwise-valid helper sprite
files padded to1MiB and preserves all pixels, but reuse retains that entire
allocation instead of a compact atlas. No such padded asset is uploaded to the
cart. Map-only atlas reduction keeps the original ownership and compact output;
its full matrix passes and current production hardware/default-gate qualification
is ongoing. An initial delivered gate has an undeclared EXPECTED_MAPS macro;
that lint failure is not counted as a pass and is being corrected.

Sector-only menu padding is rejected after actual-SD three-boot A/B/B testing.
Every upload/download hashes identically. Warm SD load baseline27369/27428us,
candidate27351/27262us, restored27364/27307us. Ready baseline421/422ms,
candidate422/423ms, restored422/423ms. The roughly0.1ms difference is within
observed variation and does not justify a production packaging change. The
candidate removes10240zero bytes from the old458752-byte menu; current c1
packaging is unchanged.

### Indexed-font integration and READ_AT qualification

Root44b60c96 retains the map-only indexed atlas optimization;3e3f2433 adds
its default actual-source gate. The full production matrix and corrected lint
pass. The initial gate failure was an undefined test macro; the exact shipped
shell now passes4000randomized atlas comparisons, capacity/OOM and a specific
bad-palette negative. No failed run is treated as a pass.

Clean candidate d3598a19e47a78fdf9b386b07b64f56097a774778cc07745cbaf15bc5c0d581c
reports warm ready357/357ms, music383/383ms and assets97/98ms. Restoring accepted
native-only ROM478f4d60 reports362/362ms, music388/388ms and assets103ms.
Both real320x240 captures are shown to the user; text appearance is intact.
Their animated backgrounds differ, so whole-frame byte equality is not claimed.
The separate exact installed-font pixel/palette gate is the equality evidence.
Both theme switches succeed; GPU retirement settles to zero. Ten-second playback
after switching records558UIframes/547GIFframes, zero underruns/producer overruns.
This smoke differs from a fresh-boot performance epoch and is not an FPS gain.

Parent flashes only the reviewed READ_AT MCU payload ff00d9ed... using the
validated MCU-only package. Before/after full firmware backups verify exact
application bytes, erased tail, original4096-byte MCU recovery loader and
unchanged FPGA/formatter bootloader. Same-value configuration/invalid-ID USB
gates pass, as does the1MiB SD scratch upload/download hash. New command
qualification passes15cases with no failures: negotiated capability, start/end
reads of1/16/33sectors, aligned/bounce destinations, byte comparisons/canaries,
and invalid0/17counts with cursor checks. No malformed legacy address-overflow
read is issued. The new MCU is currently a qualified trial; timing acceptance
and production driver integration are still pending.

SC64 loader production carts/lint pass after adding the existing packaging
LF-checkout convention for its patch. Generated header b3a5ca77458dd8ac6918de7676324792f9e045458a222e6a53a45e0c32515818
matches the isolated hardware winner. Current clean integrated ROM a5f392fa72a2b2b8208e1d7654a652fff2c5dee98cde06c56390224352916120
is queued for real-cart qualification. No production loader commit yet.

### Accepted loader/protocol and next software round

Root2ac737a6 accepts the whole-cache menu IPL3 change; f9d5294e adds its fault
gates. Integrated clean menu boots warm356ms, music382ms. Root57ce0a31 and
vendor19c7387 accept negotiated READ_AT. The full production matrix passes.
Rebuilt MCU app SHA256 is ff00d9ed7f6a994a0478642055d8d97b78f370478bb71b1d0d58fcf3088d4a1f.
Original MCU recovery loader, FPGA and formatter remain unchanged.

Clean combined menu0e3b9b406790d4f39a558e9960fd961522407df0622fba47858a8b6ff4bbc67d
boots warm344/344ms on READ_AT firmware, music371/371ms. Restored original MCU
fallback boots357/357ms, music384ms. Full firmware readback verifies restoration.
Fresh playback records576UI/574GIF frames, zero underruns/producer overruns;
both theme switches succeed with zero settled retirement. Rootfe0668fb adds
the native gate;293ff192 documents integration.

Matched078e Count trials include platform initialization: READ_AT warm ready
counts25066226/25098953/25090489 versus new-MCU legacy restored25810345/25802257.
Original-MCU restored baseline25644962 confirms baseline variation. Net original
firmware gain is approximately11-12ms; within-new-firmware gain approximately15ms.
Count/46875 gives milliseconds in the common CPU epoch, not power-on wall time.

Further original-MCU isolated trials, all Final Fight and complete boot/music:

| Candidate | Candidate ready ms | Restored ready ms | Disposition |
| --- | --- | --- | --- |
| Completed-input decoder loop |366/366/364|367/367|No convincing entry gain; reject|
| Bounded configuration store key |360/360|367/366|Positive isolated; current integration pending|
| Lazy directory advance |366/359|360/363|Variable; no demonstrated gain|
| Consolidated startup heap log |358/358|362/362|Positive isolated; current integration pending|

Completed-loop entry counts7988637/7993651/7998138 overlap restored7990741/7993794.
Literal-branch decoder likewise shows no convincing gain. Literal-pointer
scheduling has a possible sub-millisecond gain overlapping variation and remains
unaccepted. Text-only O2 shows an isolated actual-SD benefit (376ms versus386/382ms
bracket), but requires latest-stack testing. None of these decoder/compiler
experiments is in production.

Two complete diagnostic boots identify sound reload34.10/34.14ms: scan10.06/10.11,
FX15.56/15.53 and playlist8.45ms. Theme view refresh costs12.93ms. Root scan totals
55.70/55.10ms;16 directory opens cost25.17/24.99ms,30 next calls3.16/3.15ms, first
systems.dat load6.66/6.54ms, rebuild9.16/9.05ms. Scopes overlap; do not sum them.
Instrumentation reports after ready; its music timing is not a production
benchmark. Agents continue from measured costs. Evidence is under
E:/phosphor-boot-round3/hardware and the named experiment directories.

Permanent MCU suite integration is in progress. Initial parent runs fail because
the SDL image lacks Git and an SC64-only Ubuntu mount cannot resolve submodule
Git metadata. Neither is a pass. The standalone new READ_AT fixture passes on
Ubuntu24; the full suite needs intact parent Git layout. Earlier Debian sanitizer
failures remain unexplained and recorded. Final persistent clean-menu deployment
and scratch removal remain pending.

The permanent MCU suite now passes in Ubuntu24 with the intact read-only parent
and submodule Git layout: cursor12,571 cases/10,868 I/O events; SPI168,608;
SD groups93,248; formatter544,796; READ_AT4,224 plus24 overflow cases and precise
cursor/bounds negatives. FAT32/exFAT corruption and bounded64MiB tests pass.
Vendor7e37906 commits the new gate and b4f4942 documents it. Parent reviewed
full-suite.log and exit0 under E:/phosphor-boot-round3/mcu-followup/vendor-final-full-suite.
The same accepted READ_AT MCU is reinstalled; full backup readback again verifies
its exact application, original recovery loader and unchanged FPGA/bootloader.

Root841682c7 accepts bounded configuration key construction on the current
combined stack. Candidate ready340/340ms, music367/367ms; baseline343ms warm,
restored345/343ms. Clean ROM8db94f9e27e8741d0dfd2d365a248352af02ce4c5321421d261a0b62d2dff4ab.
Full production matrix passes. Parente71014c4 adds the corrected permanent gate:
117,766 actual-source comparisons with shared nonzero sentinel initialization,
precise truncation negative and fatal sanitizers. Parent rejected the original
gate's comparison of uninitialized trailing bytes; its earlier claimed count
is superseded. Production key order, truncation and palette semantics remain.

The sound follow-up finds no narrow safe deferral: advance/confirm/open/deny
must support first input; playlist already defers discovery after the first
playable song. Optional screenshot/shoot deferral requires platform policy and
has no measured independent benefit. No sound behavior change is retained.
Directory filename copy, systems.dat4K/16K buffers, current text-onlyO2 and
current heap logging are qualified or preparing final hardware comparisons.
A duplicate cart-version query and within-block FAT-cache copies are new
research leads, not accepted changes.

### Current compiler rejection and smaller follow-ups

Text-onlyO2 is rejected on the accepted combined stack. Actual-SD candidate
ready346/345ms versus baseline warm340ms and restored341/341ms; warm SD reads
35973us versus35681/36159us. Every SD upload/download hashes equally. The
candidate ROMf52ae318834d700503f620907d5672f5fd39c96eb5ce98b67935b461a36af7ed
is not retained. Restoring the makefile and forcing text recompilation reproduces
accepted8db94f9e byte for byte; default carts build passes. Earlier isolated O2
benefit does not justify retention. The later already-built Count adjunct is
preserved as an unneeded diagnostic artifact, not a separate untested algorithm.

Directory filename copy initially varies363/366ms against366/366/367 controls.
Repeat candidate361/361/361 (Counts25529164/25534516/25528726) versus restored
362/363/363 (25590265/25626896/25606204) shows about1.6ms median improvement.
Current production integration remains pending. Parent actual-backend gate passes
235,800 cases per owner and the exact255-byte name negative with fatal sanitizers.
Initial parent container setup misses a directory/include; those attempts fail
before tests and the complete rerun passes.

Systems catalog4KiB buffering warms at364ms;16KiB365/364ms; restored366/367ms.
The smaller candidate is selected for a current-stack comparison, not yet accepted.
Parent actual parser/CSV gates pass generic, generated-SC64 and malformed fixtures
with22 read/buffering conditions; permanent tests additionally cover allocation
failures and already-loaded behavior. The installed file size is awaiting direct
SD inspection; source11,321B and generated1,990B are not interchangeable facts.

Current-stack heap log Count candidate24477227/24445508, controls24486816/24506652
before and24534489/24487984 after, indicate approximately0.9ms median earlier
readiness. Frontend boot_ms excludes the changed log interval. Clean integrated
carts/lint pass with the expanded existing RTC gate (2,560 cases and both specific
negatives); real clean-ROM qualification and commit remain pending. The first
proposed standalone heap gate is superseded by extending the existing RTC owner.

Final combined scan attribution passes both real boots. FatFs directory path open
costs3,358/3,238us across16 calls; first directory reads21,370/21,050us across16;
later reads2,046/2,079us across29. systems.dat f_open costs286/288us, with no
other FatFs file open in this scan window; its whole parser load6,598/6,494us.
Scopes overlap. The unqueued directory-only intermediate is superseded by this
combined file/directory probe and preserved. These results favor investigating
cold read amplification, not introducing a relative-path or directory-cache seam.

Within-block read batching passes parent153,600 mixed-operation comparisons,
unaligned destinations/guards, wrap, eviction and exact failed-fill negative.
Hardware comparison is queued. Independent1KiB/512B cache-block geometry trials
retain the128KiB data cap and8KiB bulk threshold; they require boot and runtime
performance qualification because extra slots/transactions have costs.

Cart-version caching has actual-init/null/error/retry gates and a fresh matched
pair ready. Parent rejects the initial stale packaged artifacts; fresh clean and
Count baselines exactly match the shared e710 baselines00534c8d/4ad97820.
All earlier non-fresh cart-version artifacts are excluded. The separate duplicate
button-mode write is not removed: the earlier init ignores individual command
failures, so the module write is its only retry.

### Current-stack acceptance and rejected follow-ups

Root ff917700 accepts consolidated startup heap logging; 0391f0e1 extends the
existing RTC gate. Clean ROM d4e6c1712b3931e462765a5f8c8d30b95e3e913009c8d7c6073c3d0eec2bc2e3
passes cold419/warm340ms ready and445/367ms music. The combined line preserves
mem, heap and expansion values. Absolute Count improvement is approximately
0.9ms; frontend boot_ms excludes this interval. Final persistent deployment is pending.

The installed systems.dat downloads as1,990 bytes, SHA256
e7a73793c1ecd5278e69c971f879319a64ed9cad5c2c7a16a1deab46e02bbfaf,
matching the generated SC64 catalog. Current-stack4KiB buffering ties at340/340ms,
against warm340ms before and340/341ms restored. It is rejected despite the earlier
isolated result and full matrix pass. The proposed permanent gate remains research.

Within-block FAT copy batching is rejected: candidate346/346ms, compared with
warm342ms before and346/344ms restored. Cart-version caching is also rejected:
candidate348/349ms versus347/346ms restored. Passing correctness gates alone
does not justify either performance change. No production code from either remains.

The final core-view probe separates outer views22,205us from nested themed
refresh12,687us. Outer scopes: favorites7,510us, recents2,027us, collections1,735us,
game-user2,055us, browser8,340us and declarations412us. The initial browser build
is discarded by the later themed refresh. An opt-in deferral through the existing
container owner is under investigation; it is not accepted and requires lifecycle
and view validation. Deferring membership/hidden-game data needed by first input
is excluded. A virtual sound guard unbuffered-read candidate passes31,680 actual
source boundary cases per variant and awaits hardware. Cache geometry, current
filename-copy integration and systems string-copy comparisons remain in progress.

Both smaller cache geometries are rejected.1KiB blocks ready349/350ms with
Counts24617064/24687078;512B blocks388/387ms with26447082/26468326; restored
2KiB blocks346/346ms with24470595/24496293. Correctness/fault gates pass, but
the boot regression rules out retention without an unnecessary runtime sweep.
