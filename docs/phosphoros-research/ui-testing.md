# SC64 UI performance investigation

Last updated: 2026-09-06. Target: approximately 60 FPS at normal NTSC refresh,
with animation cadence preserved, music playing, and zero audio underruns.

This log extends the [boot investigation](boot-testing.md) into steady-state
UI performance. Update current work before each experiment and record its
result, safety limits, and disposition afterward. Host simulation is not a
hardware pass. Keep unsuccessful and unimplemented ideas visible.

The user's priority is **normal GIF assets without offline conversion**.
Investigate direct GIF decoding/composition on the console or cartridge;
GIF64 measurements establish the current performance baseline, not a required
future authoring workflow. The clarified playback requirement permits bounded
temporary RAM buffers, not a saved converted file or whole-animation cache.

Detailed findings and source links: [MCU and SD](notes/mcu.md),
[FPGA and direct GIF](notes/fpga.md),
[N64 rendering and asset transport](notes/ui.md).
The maintained [gap tracker](gaps.md) records upstream ownership, current
evidence and the next closure test for toolchain and original-GIF support.

## Current work

The user pauses GIF timing experiments and requests the
[broader practical improvement review](#practical-sc64-and-phosphoros-review--2026-09-06).
That review is the current direction; the chronological experiments below
retain their historical results. Best completed GIF timing is 86.790 MHz,
below the unchanged 100 MHz requirement. No experimental FPGA image is flashed.

### Rejected early synchronous-reset remap

The maintained [gap tracker](gaps.md) now owns the cross-project gap index.
The [selected-register experiment](../../tests/open-toolchain/area-map/reset-unmap.md)
tests early `dffunmap -srst-only` on `n64_scb.flashram_done`. A fresh paired
baseline reproduces 6,347 LUT4/3,734 FF; the isolated candidate uses 6,353 LUT4
and the same FF count and RAM shapes. Diagnostic packing gives 6,552 COMB,
3,734 FF, 25 EBR, 24 RAMW and 101 I/O. The register still uses general `M`
data, `SD=0` and a unique LSR: later synthesis reconstructs the reset. Reject
the variant; no placement or hardware test follows the failed structural gate.
Parent repeat: `build/sc64-reset-unmap/parent-final/result.json`, with the same
counts and explicit `placement_performed=false`. Focused scope checks also
reject an unrelated-cell mutation and a net merge across stable net identities.

Parent review catches selection assertions that do not apply a selection and
adds a separate before/after scope check plus an unrelated-cell negative.
Induction and reset-polarity negatives remain supplemental evidence, not a
startup or complete transition proof. The direct next-state gate is still
required before accepting a later-stage remap. Failed setup stages are listed
in the experiment report; removed early retries have no claimed retained logs.

Next: test the source-reviewed HeAP control-set search hint, preserving device
legality and the existing 100 MHz diagnostic constraints. It remains untested.

### Compact placement failure localization

The [compact localization](../../tests/open-toolchain/area-map/compact-placement.md)
repeats the stricter search with the smaller physical input. Agent and parent
both reproduce exit 125 on `n64_scb.flashram_done_TRELLIS_FF_Q` after 10,001
attempts. Parent evidence: `build/sc64-area-route/parent-compact-localize/`.
No routed netlist or frequency report is produced.

The [debugger sample](../../tests/open-toolchain/area-map/placement-stack.md)
uses the original executable's symbols and unchanged default-placement inputs.
At 45 seconds, the process is in `StrictLegaliser::try_place_cell`, reached
through `legalise_cell` and `legalise_placement_strict`. Evidence:
`build/sc64-area-route/compact-stack/`. This localizes the sampled phase to
legalization, not solving or spreading; it does not identify every rejected
site or prove placement impossible.

The [control-set review](../../tests/open-toolchain/area-map/control-sets.md)
finds the same pattern in both named stock registers: an unpaired FF using a
general data input and a unique tile-wide synchronous reset. Nine compact FFs
have this one-member signature pattern. Next: prove and test a targeted
synchronous-reset-to-data-mux mapping on `flashram_done`, then measure packing
and placement under unchanged legality. This remains a proposed experiment,
not a production RTL fix or hardware-qualified result.

### Compact integration and placement diagnosis

The [compact integration](../../tests/gif/stock-lzw-fit/compact.md)
passes agent and parent repeats of raw byte/cancellation, paired stock mapping,
disconnected-start/status negatives and guarded area mapping. Actual diagnostic
packing gives **6,546 COMB, 3,734 FF, 25 EBR, 24 RAMW and 101 I/O**, leaving
318 aggregate logic positions. Parent evidence is
`build/sc64-stock-lzw-compact/parent/result.json`. The compact default placement
still times out at 120 seconds with no route, frequency or output netlist
(`build/sc64-area-route/compact/result.json`).

The [placement diagnosis](../../tests/open-toolchain/area-map/placement.md)
finds that the printed attempt number is a cap, not progress. A stricter search
budget on the preceding noncompact candidate fails after 10,001 attempts on
stock MCU register `mcu_top_inst.mem_write_TRELLIS_FF_Q`; parent reproduces exit
125 in `build/sc64-area-route/parent-localize/result.json`. Its distinct reset
control set is a packing lead, not evidence that legality rules are incorrect.

The [arithmetic equivalence gate](../../tests/open-toolchain/area-map/equivalence.md)
extracts 132 ALUs with 58 distinct shapes from the hash-checked passed checkpoint.
Default and soft-carry mappings prove equal across all 2,322 output bits for
arbitrary inputs; an altered LUT fails the negative control. Parent repeat passes
at `build/sc64-area-equivalence/parent-provenance/result.json`. This proves those
operator mappings, not the surrounding fabric, 18-register difference, startup
or hard-block wiring.

The bounded [alternative placer](../../tests/open-toolchain/area-map/alternative-placement.md)
also times out after 120 seconds with no completed placement, route or output
netlist (`build/sc64-area-route/sol-sa/result.json`). The Sol agent uses the exact
same compact physical input, pins, diagnostics and 100 MHz request as the default
placer run. Neither search proves the design impossible to place. Next: inspect
control-set/site pressure and localize placement phases before changing RTL or
backend rules. No cart, firmware, SD or production changes occur in these probes.

### Smaller datapath and mapping options

The [LZW-only stock probe](../../tests/gif/stock-lzw-fit/README.md)
removes FPGA composition/dirty packets and writes a full raw index plane. Parent
paired mapping and packing reproduces 7,631 COMB, 3,783 FF, 25 EBR and 101 I/O:
1,232 fewer COMB than the composed design, but still 767 over capacity under
default mapping. Its actual-DMA/arbiter/SDRAM simulation passes eight original
raw index planes and four error/cancel/restart cases. Parent repeats the final
provenance run, including blocked output DMA, distinct restart and no late
writes. MCU traffic is inactive in this specific raw test; the earlier MCU
arbitration suite remains a separate gate. This does not implement N64 composition.

The [compact decoder](../../tests/gif/compact-lzw/README.md) narrows
the output counters, bit reservoir, stack depth and clear/stop registers under
explicit active-state bounds. Parent repeats all 1,776 fixtures, 200 cancels,
four dictionary-fault cases and corrupt-dictionary guard; original cycles and
memory traffic are unchanged. Component mapping falls from 656 to 587 LUT4,
300 to 254 FF and 142 to 113 carry cells, still three EBR. Local SAT/invariant
checks pass. Actual RTL negatives reject a 16-bit counter on frame 0 and an
18-bit reservoir on original frame 4. Initial implicit-width warnings fail;
explicit extensions resolve them without suppression. This smaller decoder
is combined with stock soft-carry mapping in the subsequent compact probe above.

The [mapping comparison](../../tests/open-toolchain/area-map/README.md)
repeats the exact guarded checkpoint and changes only the logic continuation.
Default mapping reproduces all counts. Soft carry reduces the full composed
design from 8,342 to 7,434 prepack units, still too large. For LZW-only it reduces
7,202 to 6,575 prepack units. Actual diagnostic packing produces **6,630 COMB,
3,765 FF, 25 EBR, 24 RAMW and 101 I/O**, leaving 234 logic positions and one EBR.
This is the first tested stock-integrated variant below the arithmetic resource
limits. Comparator-only flags have no effect at this continuation stage; coarse
mapping was not rerun, so this does not reject that option generally.

Independent review adds final RAM shape/parameter comparison and direct converted
source/Yosys executable hashes; final repeated mappings are identical to the
packed input. These checks are not whole-design memory wiring or mapped-netlist
equivalence. Diagnostic EFB/PLL preparation and ODDR/EFB/FIFO flags remain.
The 100 MHz diagnostic placement/route attempt times out at 120 seconds in the
analytical placer: no completed placement, routing, frequency or routed netlist.
Packing compatibility is not physical fit or timing closure.

The [MCU/N64 split review](../../tests/gif/mcu-split/README.md) rejects
expanded MCU pixel transport for 60 full images/s through the existing 8 MHz
SPI link: 76,800 bytes alone need at least 76.8 ms. Conventional LZW dictionaries
also exceed the MCU's 8 KiB total RAM. These are interface/storage bounds, not
measured MCU decode time. Existing N64 full-plane receiver measurements use a
contiguous backend read, not 1,200 tile scatters; their approximately 15.6 ms
cost is not a physical PI floor. Direct asynchronous DMA, transparency/history
composition and overlap with the normal frame/audio loop still need real A/B
tests. No 60 FPS conclusion follows from this area experiment.

Next: resolve physical placement and complete timing/configuration coverage, and
implement safe job/arena ownership and N64 raw-plane composition before cart
acceptance. No production RTL, N64 ROM, SD assets, firmware or cart state changes
this pass. Commits remain local.

### Stock integration and remaining logic budget

In progress: preserve the original MCU CFG memory client alongside the GIF
clients and replace research observation interfaces with an explicit stock-top
integration probe. Parent review identifies two retirement requirements:
unrelated MCU traffic must not prevent GIF retirement, and pending GIF requests
must continue receiving grants during cancellation. Closing mux admission at
cancel would strand ungranted DMA/adapter requests. An actual-arbiter test is
checking whether inter-grant gaps preserve USB/SD progress; downstream fairness
does not follow from fair rotation inside the four-client mux.

The [header-counter experiment](../../tests/gif/header-counter/README.md)
passes the bounded recurrence proof, deliberate wrong-saturation rejection,
eight-image actual-controller comparison and twelve cancellation/restart cases.
Saturating a six-bit header position at 32 replaces a 27-bit whole-packet count,
saving 39 LUT4, 33 carry cells and 21 FF in paired combined synthesis. Original
output and 16,439,680 simulated cycles are unchanged. Independent agent review
confirms the clear ordering and 76,992-byte packet bound. Parent adds a strict
counter-use inventory and missing fixture/driver provenance, then repeats both
gates. The newer diagnostic-image Verilator rejects unchanged compositor task
writes; that first attempt is failed, and the established 5.032 image is used
without warning suppression. Mapping remains in the diagnostic image.

All six [compositor arithmetic candidates](../../tests/gif/compact-compose/README.md)
prove equivalent at 1,549 points each, and an incorrect address is rejected.
Parent independently repeats the gates and seven mappings. Header slicing
saves only two LUTs (630 to 628); row/index variants trade extra LUTs for fewer
carry cells, with unchanged registers and memory. No substantial packed fit
gain is established and none is promoted. All alternatives and counts remain
in the report instead of changing production arithmetic.

The [four-client MCU mux](../../tests/gif/transport-mcu/README.md)
passes the parent's independent warning-clean repeat: 512 MCU writes and reads,
three saturated GIF peers, delayed/held ACKs, pending-request cancellation,
1,000 stalled MCU clocks with independent GIF retirement, restart and wrong-ACK
negative control. Two explicit width conversions in the extracted stock memory
slice pass SAT equivalence. The MCU SPI parser is not part of that functional
test. Added mux cost is 76 LUT4 and three FF; all source/tool hashes are recorded.

The [actual-arbiter matrix](../../tests/gif/transport-fairness/README.md)
passes agent and parent runs of 54 cases with exactly 3,000 grants each. Delays
0/3/17, PI windows, three CFG configurations and three USB/SD workloads exercise
ACK ownership, data, reservation gating and actual CFG-low selection edges.
The four-client mux permits USB/SD progress through its gaps. Continuous USB
starves SD even with CFG disabled; that is existing fixed priority, not an
observed GIF-specific regression. Finite maximum waits are not liveness proofs.

The [stock-pin integration skeleton](../../tests/gif/stock-fit/README.md)
now gives actual combined packing evidence. Parent repeats paired guarded
mapping, identical top-port checks, structural job/status connectivity, two
actual disconnected-RTL negatives and pack-only diagnostics. The stock-to-GIF
comparison is 5,674 to 8,863 COMB cells, 3,023 to 4,288 FF, 22 to 26 EBR and
101 to 101 physical I/O. The candidate exceeds 6,864 logic positions by 1,999
(29.1%): **fit rejected**. It retains the original header counter; the separate
counter saving does not close this gap. The 26-block RAM budget is fully used.

Review replaces an insufficient broad status-reachability negative with actual
RTL disconnection and exact decoder-busy/status-wire identity. An initial pack
attempt without pin-constrained ODDR is rejected; the repeat uses the existing
pins-only diagnostic LPF. EFB/ODDR/FIFO diagnostic limitations remain. All 56
frozen release inputs match the conversion manifest in the parent audit.

The synthesis skeleton keeps stock MCU, USB, SD, N64 and memory owners and uses
SPI register taps to retain job logic without extra GPIO. It is not a command
API: status pulses can be missed, parameters are not atomically captured, source
length/arena ownership is unfinished, and fixed addresses conflict with ROM
use. Next work needs a substantially smaller complete datapath or a different
division of decoding/composition work, then safe job/arena ownership, complete
configuration and timing validation, and finally cart tests. No placement,
routing, bitstream, firmware update or hardware programming occurs this pass.

### Bounded transport integration pass

Current work uses a stronger image-size bound to avoid adding spill ownership.
The existing compositor accepts 320 by 240 images and the decoder has a
76,800-index output limit. An LZW phrase can exceed the maximum previously
emitted phrase by at most one byte; induction gives emitted bytes >=M(M+1)/2.
Thus accepted phrases have length at most 391, and a pre-overrun walk at most
392. A guarded 512-byte stack suffices for this entire explicitly bounded
image class. Larger images remain outside this accelerator's current contract;
no truncation or general-GIF support is inferred.

The parent [phrase-bound gate](../../tests/gif/phrase-bound/README.md)
checks 8,390,656 abstract transitions plus tight accept/overrun vectors for all
seven legal minimum code sizes. The first vector attempt was one code short;
the reference rejected the expected length, the generator was corrected, and
the completed gate passes. The bound derives from the inspected decoder;
it is not claimed as a complete RTL proof.

The [bounded decoder](../../tests/gif/sc64-bounded/README.md) passes
the parent full run: 1,776 fixtures, all 1,717 original images, 200 cancellation
cases, four memory-fault/restart cases and a corrupt-dictionary watchdog.
Original decoding remains exactly 1,257,856,312 simulated cycles. Mapping uses
three DP8KC, 656 LUT4, 300 FF and 142 carry cells. The parent repeats the
negative watchdog test and observes the required semantic rejection. Its first
invocation names a nonexistent focused-results directory and fails before
testing; the corrected invocation passes.

The [explicit-priority mux](../../tests/gif/transport-mux/README.md)
passes parent equivalence, all 32 selector combinations, actual-cast simulation
and deliberate wrong-priority rejection. Standalone mapping falls from 7,526
to 162 LUT4 and from 3,792 to zero carry cells. Combined with the bounded core,
the actual SC64 RTL transport simulation reproduces all eight baseline frames
and 12 cancel/restart cases exactly: 16,439,680 cycles and 86,784 packet bytes.
These are model results, not measured UI FPS.

The [combined resource audit](../../tests/gif/transport-fit/README.md)
maps the bounded pipeline plus simpler mux to 2,381 LUT4, 413 carry cells,
1,203 FF, four DP8KC and 16 distributed RAMs. Parent synthesis with physical
DQ wiring reproduces 2,343 LUT4; actual packing reproduces 3,521 COMB cells,
four DP8KC and 739 observation I/O cells. Packing succeeds but the runner
intentionally reports unqualified status (exit 3); no placement or routing is
performed. The observation interface exceeds available I/O sites.

Four added EBRs fit the stock arithmetic budget exactly. Logic remains a
problem: the rough combined prepack estimate is 8,251 versus 6,864 available
units, not an exact integrated fit or lower bound. The research mux also
omits the original MCU CFG client. Next work must preserve that client,
remove research-only observation interfaces through actual integration, and
measure complete logic, placement and timing. Independent configuration-bit
and timing-coverage gaps remain. Production sources, cart state and SD assets
remain unchanged; no FPGA image is qualified or programmed.

Parent evidence: `build/sc64-bounded/{parent-core,parent-transport,parent-negative}`,
`build/sc64-transport-mux/parent`, and
`build/sc64-transport-fit/{parent-physical,parent-pack}`.

### Behavioral build target and memory-fit experiment

The user accepts an independently generated FPGA implementation without a
byte-identical release image. Acceptance still requires behavior preservation,
complete configuration and timing checks, resource fit, recovery compatibility
and real-cart validation. Reference-derived byte equality is only an artifact
reconstruction check, not the source-build acceptance criterion.

Completed this pass: bounded local phrase stack with external spill, registered
DMA completion flags, and two rejected algebraic follow-ups. Baselines and
production sources remain unchanged. None is programmed.
The [cache-size comparison](../../tests/gif/cache-budget/README.md)
rejects 128/256-entry caches: all sizes still use six EBRs, while original
cycles increase from 1,257,856,312 to 1,368,813,574 and 1,510,948,941.
All 1,772 fixtures and cancellation/fault gates pass; the parent independently
repeats the 256-entry run and obtains an identical result manifest.

The [RAM timing-pin audit](../../tests/open-toolchain/timing-data/ebr-arcs/README.md)
joins 26 blocks per corner, with 128 propagation, 830 setup/hold and 104 pulse
width records. Two PDP wrapper-only reset pins remain unresolved. Strict mode
rejects them; an explicit inventory mode records them without qualification.
Parent review fixes malformed numeric-field acceptance and output guards;
all 20 rejection checks and the independent parent-export join pass.
The parent independently profiles every original Final Fight image through
`tests/gif/gif_reference.py`: 1,717 images, maximum phrase 391 bytes; 142 images
exceed 256 bytes and none exceeds 512. Source SHA-256 matches the established
original. This supports testing a 512-byte local stack, but does not permit
truncating longer phrases in other GIFs. Evidence:
`build/sc64-gif-stack-profile/{profile.py,results.json,run.log}`.

### Stack spill and DMA timing results

The [spill-stack experiment](../../tests/gif/cache-budget/spill.md)
reduces the isolated decoder from six DP8KC blocks to three by keeping 512
phrase bytes local and spilling longer phrases through an explicit byte-memory
port. A separate local RAM read register enables block-RAM inference. Final
mapping with Yosys 0.52 is three DP8KC, 749 LUT4, 332 FF and 155 carry cells.
Parent mapping with the current Yosys 0.68+195 also uses three DP8KC, with
764 LUT4 and the same FF/carry counts. Adding the existing one-block compositor
matches the four spare blocks arithmetically; this is not integrated fit.

Agent and parent full runs pass 1,775 fixtures, including all 1,717 original
images, three long-phrase vectors through length 4,091, the inherited 200
cancellations/four memory-fault cases and eight new spill error/cancel/restart
cases. The latter include acknowledgement delayed beyond cache retirement and
acknowledgement simultaneous with cancellation. Original Final Fight has zero
spill accesses and exactly the paired 1,257,856,312 cycles; this preserves the
modeled baseline, not a measured UI speedup.

Four additional varied-byte phrases exercise depths 513/1025/2046 at minimum
code size 2 and depth 1920 at size 8. They pass 4,601,407 exact bytes; deliberate
address alias, byte corruption and two-bit truncation each fail at comparison.
The parent independently constructs the size-2 expected streams, repeats the
full varied suite, and verifies all mutation failures. Zero-only long phrases
were insufficient to establish data-order coverage. See the report for rejected
setup attempts and generated evidence under `build/sc64-cache-budget/`.

The [registered DMA flags](../../tests/open-toolchain/memory/dma-flags/README.md)
pass 313 actual-source equivalence points and the strict negative control.
Parent proof and route repeats pass their stated gates. Diagnostic timing
improves from the freshly reproduced 75.52 MHz baseline to 78.23 MHz, at a cost
of 13 LUT4, 78 carry cells and four FFs. It remains an isolated promising
candidate: both routes fail the explicit 100 MHz target.
[Algebraic inequalities and explicit bitfields](../../tests/open-toolchain/memory/dma-flags/algebra/README.md)
pass equivalence but route at 73.52 and 72.03 MHz versus independently repeated
78.23 MHz baselines. Both are rejected. Parent proof reruns pass, and paired
arguments, strict route failures and unchanged hard-cell/INIT parameters are
independently checked.

Next: connect spill storage through the existing scratch-memory owner with a
bounded arena and coordinated retirement, verify the combined transport and
full resource fit, then continue configuration and timing coverage toward a
safe independent FPGA image. The new block-RAM count does not resolve shared
bus ownership, extra transport resources, encoding gaps or timing closure.
All work remains local; no cart firmware, SD assets or production ROM changes.

### Active evidence-to-implementation pass

Completed the [project documentation audit](notes/documentation-audit.md):
66 root, 61 SC64, 32 supplemental and seven generated historical documents.
Technical scope and exclusions are recorded in that report. Protocol corrections
cover the IDENTIFIER button-interrupt side effect, CIC bit range and command links.

New [exact 7000HC active-RAM evidence](../../tests/open-toolchain/timing-data/active-7000-evidence.md)
provides 26 active EBRs and successful unmodified vendor timing exports. Parent
repeats the export and EBR probe. The mode/site conflict is reproduced; it does
not yet justify a fuse encoder correction. The
[source-aware PIO gate](../../tests/open-toolchain/pio-evidence/README.md)
passes 51 original ports and rejects 204 bit mutations plus a direction mutation.
Parent review and independent rerun pass after separating checker and test imports.

[Hardware evidence](../../tests/open-toolchain/constraints/hardware-evidence.md)
confirms the actual SDRAM part and original LPF inputs. The inherited Micron
symbol URL is not the fitted part's timing authority.
[Three additional route probes](../../tests/open-toolchain/memory/timing-options3.md)
yield no improvement over the fixed 75.52 MHz diagnostic baseline: router2
completes at 41.81 MHz and fails 100 MHz; timing-driven rip-up times out after
180 seconds; simulated annealing fails relative-chain legalization. Retain no
performance candidate. Existing hard-cell and external-timing barriers remain.

Focused fixtures, local documentation links and repository lint pass. Commits
remain local; no cart operation is part of this file-only pass. Next work needs
controlled EBR/configuration comparisons, complete hard-cell timing, resource
fit and production ownership, as detailed in the audit. Historical entries
below describe their original experiment dates, not current pending status.

### Continued toolchain investigation

Completed: exact 7000 timing database probes against vendor report oracles,
pinned OpenSTA synthetic fixtures, and no-carry/ABC comparisons with the fixed
timing baseline. New commits remain local. Existing firmware and the real cart
remain unchanged. Public reference-design searches and supported timing-export
library-resolution probes are recorded below.

Follow-up: two public 7000HE NCDs export successfully. Their five checked
grade-6 arcs match the installed 7000 data; minimum-delay discrepancies remain.
The parent repeats the SDR design's grade-6 export. Neither design supplies
the missing hard-block oracle. The latest SC64 extra archive and current
workflow publish no NCD/SDF intermediate. Six normal NGD timing-export probes
all fail with the same missing-MACO-model error, including FIFO and ODDR
controls whose preceding netlist conversions pass.

The clean OpenSTA Docker build requires explicit Flex development headers.
After adding them, the image builds and independently passes all 13 fixtures;
its executable hash matches the original engine. Lint passes. Evidence:
`build/sc64-opensta/docker-build-final.log`, `fresh-image/`, `final-lint.log`.

The parent repeats the reference configuration coverage audit: 433 distinct
set bits remain unexplained, but 121 already occur in same-tile database
definitions and remain uncovered by the selected decode; 312 have no same-tile
definition. Of the 121, 68 involve EBR complete-mode-pattern mismatches and 53
involve PIO overlapping-pattern selection. The source-requested PIO patterns
match in full; the greedy decoder selects a different overlapping pattern. This exposes
a concrete 7000 EBR site/mode question, not a proven replacement encoding.
Evidence: `build/sc64-unknown-bits-audit/parent-final.log`.
The public 7000 SDR JED converts and decodes, but its association with the
NCD is correlated metadata rather than a proven same-build pair. Its mapped
design contains no active EBR, so it cannot qualify active RAM mode encoding.
Nevertheless, the parent independently repeats a useful counterexample:
F1B32..36 is zero at all 26 sites in that configuration, versus nonzero
site-correlated values in SC64. It is not an unconditional device constant.
Normal bitgen of the public NCD stops at its license check. A further public
CPU NCD proves to be 4000HC, not 7000, and is not substituted for this evidence.
The official 7000 demo download also requires sign-in in the current browser.
Evidence: `build/sc64-public-ebr-audit/parent-sites.json`.
Remaining: a controlled exact-7000 active-EBR site/mode oracle, hard-block
timing and minimum-corner mapping, full external constraints, and complete
configuration/programming qualification. No bits are transplanted or emitted
to hardware on the strength of these observations.

The parent independently passes all 13 OpenSTA fixture cases, including signed
I/O delays, 270-degree generated-clock phase and missing-annotation rejection.
The pinned engine crashes on a malformed SDF instance; the bounded fixture
runner rejects that mismatch before annotation. Synthetic timing validates
the workflow, not MachXO2 models. Evidence: `build/sc64-opensta/parent/`.

The database probe identifies FIFO, DDR and EFB records in the exact 7000 SPD.
Five 1200 grade-6 numerical checks match vendor SDF, but a minimum-delay export
disproves a direct extrema conversion. The parent regenerates both reports and
passes the bounded probe plus 25 rejection checks. All 34 installed example
NCDs are inventoried by actual loaded part: none is 7000; 31 export and three
stop at their IP license requirement. Evidence: `build/sc64-timing-data/`.

No-carry reaches 69.82 MHz; explicit ABC control 64.14 MHz; removing its final
area-recovery pass reaches 74.19 MHz. Every route completes but fails strict
100 MHz, and none beats the prior 75.52 MHz baseline. A conditional fabric
proof passes 3,333 points, but the initialized base case times out: complete
equivalence is unproven. These are rejected experiments, not production
changes. Agent logs are retained without a parent route rerun in
`build/sc64-open-timing-options2/`.

The exact stock SCUBA EFB command succeeds in the official environment and
produces Verilog/EDIF. `edif2ngd -l MachXO2` and `ngdbuild -a MachXO2` also
succeed for the actual 7000 target, with zero NGD DRC warnings/errors. The help
example's `LATTICE-XO2C` library spelling fails and is not the working invocation.
Normal `map -p LCMXO2-7000HC -s 6 -t TQFP144` stops at the LSC_BASE license check.
`ngd2ltm` is another available timing-model converter, but the direct EFB NGD
probe fails because its expected MACO cell model is absent. No licensed check
is modified. Evidence: `build/sc64-efb-compiler/`.

### Official release reproduction follow-up

Target: official SC64 v2.20.2, source commit
`18041e25472075a166292d1195603bcefe9c9688`, verified against the upstream
release/API on 2026-09-05. Firmware archive SHA-256:
`1616417c883d710f313a139a7ac29228a1b9870d8c2f22b4c864c05266408659`.
The isolated checkout is `build/sc64-open-release/source`; earlier diagnostic
fork checkouts are not silently substituted for this source baseline.

Completed: CPU/CIC source rebuild, exact reference-package reconstruction,
collision-preserving RAM mapping proofs/model checks, full-design routing
diagnostics, and the two missing electrical/configuration parser extensions.
Remaining: an independent FPGA source rebuild with complete primitive timing,
external constraints, configuration/feature ownership, and programming safety
qualified. Internal timing still misses 100 MHz; no new firmware is flashed.
Compare whole-container identity separately from component identity because
upstream packaging embeds build host/time metadata. Replaying release bytes
is a format roundtrip, never a claim to have compiled those bytes from RTL.
No new firmware image is approved for hardware by these investigations.

CPU/CIC build from the exact release completes using the unchanged upstream
`./build.sh bootloader controller cic` and its original GNU compilers from
SC64 environment v1.10. MCU (21,648 bytes), bootloader (65,536 bytes), and
primer (3,420 bytes) match their official chunks byte-for-byte; all three
SHA-256s match. CIC builds to 1,856 bytes and remains a separate FPGA
initialization input. Evidence: `build/sc64-open-release/cpu-build.log`,
`cpu-comparison.json`, and the durable shared-parser `cpu-gate.json`.

The parent independently repeats the official FPGA configuration roundtrip:
all 433 unknown-bit records survive and decoded configurations match exactly.
The stock repacker emits 104,128 command bytes versus the official 104,144.
The checked reference serializer reproduces all 104,144 bytes exactly from
freshly repacked configuration. Combining this with the three source-rebuilt
CPU binaries and explicit reference metadata through the upstream packer
reproduces the entire 195,040-byte package, including its SHA-256 above.
Evidence: `build/sc64-open-release/parent-serialized.bin` and
`reconstructed/`; the serializer never reads the original FPGA payload.
The FPGA source compiler is not involved in this reference replay, so an
independent all-source build remains unfinished. A separate file-only
Lattice Deployment Tool test succeeds after installing its genuine libusb
dependency; conversions cover official payload to JEDEC and Trellis BIT to
JEDEC and back. No Diamond build license is bypassed.

The parent repeats the guarded memory experiment successfully: 91,014 LUT4 /
35,845 FF becomes 4,531 LUT4 / 3,023 FF, with 18 DP8KC and four FIFO8KB blocks.
Generic equivalence, arbitrary collision outputs, negative controls, eight
original address implications and six physical CE/mode checks pass. The
physical losing port is disabled on cross-port write collisions; logical read
enable holds and port-B write priority are preserved. This is not whole-design
post-mapping equivalence or hardware qualification. Evidence:
`build/sc64-open-memory/parent-focused/` and `parent-full/`.
The separate mapped 512x16 physical fixture also passes 6,000 cycles against
Lattice's DP8KC simulation model, covering both-write priority and cross-port
read/write collisions. Evidence: `build/sc64-open-memory/parent-physical/`.
The original LPF still fails at `IOBUF ALLPORTS`; a separate pin/electrical-only
placement/routing diagnostic investigates remaining physical-tool gaps without
claiming the omitted timing/configuration constraints are satisfied.
That diagnostic completes placement with all original pin assignments, then
routing fails on ground-net arc 5. A same-run pre-route sink inventory identifies
the endpoint as `vendor_inst.efb_lattice_generated_inst.EFBInst_0.I2C1SDAI`.
The disabled hard-peripheral input's physical handling needs evidence before
any connection is removed. Logs: `parent-full/pins-route.log`, `place.log`,
and `ground-route.log`. No bitstream is emitted.
The guarded dedicated-input experiment resolves that connectivity failure:
24 exact placeholder ties on dedicated pad/PLL paths are excluded, while every
other cell, parameter and connection is preserved. The parent passes 32 mutation
rejections and repeats minimal routing and mandatory emission/replay barriers.
Full routing now completes at an explicit 100 MHz request, but exits 1 because
the post-route estimate is 72.36 MHz (pre-route 66.00). This is a failed timing
result, not a 100 MHz pass. Evidence: `parent-full/route-100-repeat.log`,
`routed-100.json`, and `build/sc64-efb-inactive/parent-minimal/`.
The first `route-100.log` launched before its input existed; it is an ordering
failure and is superseded by the completed repeat.

The parent also verifies actual `IOBUF ALLPORTS` support: three ordered override
cases, 13 negative cases, and five-pin electrical pack/unpack pass. The original
LPF is unchanged and initially advances to `SYSCONFIG SDM_PORT`. The next patch
adds both stock SYSCONFIG keys using their existing encoder/database bits:
nine positive cases, seven negatives, and four routed exact-bit pack/unpack
cases pass independently. The full original LPF now parses without deleting
statements; this is parser acceptance only. Existing SDRAM delays and other ignored
constraints remain unqualified. Evidence: `build/sc64-open-allports/parent/`.
SYSCONFIG evidence: `build/sc64-open-sysconfig/parent-final/`; the first parent
attempt exposed and fixed a fixture path that incorrectly depended on the old
release checkout containing new test tooling.
SDC inspection also rules out merely translating LPF to SDC: this nextpnr's
generic reader lacks input/output delays, and its `set_false_path` handler
explicitly warns that it does nothing. Full external timing is still a backend
implementation requirement, not a syntax conversion.

Vendor timing tools provide a further verified lead: the parent repeats
`iotiming` and `ldbanno` on an installed 1200HC example, both exit 0 without
changing licensing. Exact 7000 SPD/TLD data exists, but its schema/corner
mapping is not established; no 1200 timing is substituted. Creating a new
7000 NCD via `ncl2ncd` remains license gated. Details:
[timing investigation](../../tests/open-toolchain/timing-research.md).

A bounded mapping/placement comparison finds no accepted clock improvement:
paired default 75.52 MHz, wide-LUT 75.01, placement weight 20 at 64.73,
criticality exponent 3 at 75.52, and seed 1 at 71.96. Every routed case fails
the explicit 100 MHz target. The parent independently reproduces the paired
75.52 MHz baseline. Two no-carry variants receive synthesis checks only and
remain unaccepted; retiming is not attempted because it requires additional
state/initialization proofs. Full results and fixed hashes:
[timing options](../../tests/open-toolchain/memory/timing-options.md).

OpenSTA is a possible existing engine for the missing external SDC semantics,
but needs a matching packed netlist, characterized Liberty cells and complete
annotation. Parent SDF export confirms seven hard-cell instances have no timing
arcs; another analyzer cannot recover absent characterization. No OpenSTA
installation or qualified flow is claimed. See
[external STA](../../tests/open-toolchain/constraints/external-sta.md).

The EFB configuration question is narrower than a missing enum list implies.
Stock packaging discards separate post-configuration UFM data; zero initialization
is consistent with the existing erase-to-zero path. Extra static EFB enable
fuses remain unproved, not assumed. Board SN/pin 70 carries SDRAM_A5, so disabled
configuration SPI and the primer's SPI_OFF feature setting must be preserved.
Normal updates preserve the feature region. Details:
[configuration and board evidence](../../tests/open-toolchain/efb/inactive/configuration-research.md).

The clean combined tool image includes both parser extensions and excludes
generated Python caches: `sc64-open:diagnostic-lpf`, image ID
`sha256:15cb73a02b74c4adf32c87d01537fec490dc83dafe02d3720076fca1c3ea4df4`.
Fresh-container EFB barriers, FIFO roundtrip/negative checks, ODDR/PLL
roundtrip/negative checks and SYSCONFIG exact-bit fixtures pass independently.
Evidence: `build/sc64-open-release/image-*` and
`diagnostic-lpf-clean-build.log`. Root lint and 40 local documentation links
pass. Automatic approval review rejects deletion of generated Python cache
directories; they remain untracked and excluded from commits and Docker context.
Per the latest user instruction, commits after the already-pushed `6199a54`
remain local until the overall work is complete.

### License-free FPGA toolchain

Backend implementation follow-up adds isolated, rollbackable diagnostics;
none is enabled for production firmware. Three agents developed/reviewed the
separate paths, followed by parent review and independent checks.

| Experiment | Result | Safety / disposition |
|---|---|---|
| EFB declaration and physical routing | All 109 port directions match the 7000 routing graph; minimal Wishbone routing reaches `X3/Y1/EFB`. | Keep routing diagnostic only. EFB/UFM configuration bits and timing remain unmapped; bitstream emission always errors. |
| Original generated EFB wrapper | Synthesizes; routing fails at a constant-connected inactive peripheral arc. | Unresolved. No speculative removal of peripheral connections. |
| ODDRXE output register | Data fixture and unchanged SC64 PLL/ODDR/OB circuit synthesize, route, pack and unpack. Original pin3/pin61 and active clock connectivity are checked. | Keep diagnostic only. No characterized timing or proven physical clock polarity. |
| PLL analog settings | Source `ICP_CURRENT=9` and `LPF_RESISTOR=72` survive explicit metadata preservation and roundtrip. | Missing/conflicting attributes, enabled WB/reset, and nonzero unused WB pins reject. Metadata input/output aliases reject before writes. |
| FIFO8KB | Exact SC64 9-bit/NOREG wrapper routes; pack/unpack/repack is byte-identical. | Keep diagnostic only. FIFO data-pin/configuration mapping needs independent vendor comparison; timing is absent. |
| FIFO flag graph | Eight reversed fixed edges corrected; reachable outputs increase from 0/104 to 104/104. | Separate fuzzer/database patches. Fixed edges carry no programmable fuse bits; direction repair is not hardware qualification. |
| FIFO behavior model | Vendor model passes 1024-byte fill/drain, data/flags, independent clocks, global reset and read-pointer replay. | Validates wrapper/model behavior, not the new physical implementation. Proprietary model remains outside the repository. |
| Diagnostic barriers | Fresh CLI opt-in required even when replaying saved JSON; malformed widths/pointers/chip-select values reject. ODDR negative checks require the intended error and no configuration output. | Keep fail-closed checks. Patch anchor failures leave source files unchanged. |
| Original LPF inventory | 226 statements retained; 14 focused tests pass. Original project returns unresolved qualification, exit 3. | SDRAM timing, electrical/configuration and exception semantics cannot be dropped to obtain a pass. |

Evidence: `build/sc64-open/efb-final/`, `oddr-parent/`,
`oddr-parent-negative.log`, `oddr-guard-parent/`, `constraints-parent.json`,
and `build/sc64-open-fifo/atomic-final/`. The clean combined image builds and
all three parent diagnostic suites pass together, including the ODDR negative
replay checks: `build/sc64-open/combined-{efb,oddr,fifo}/` and
`combined-oddr-negative.log`. Details and exact remaining requirements:
[integration audit](../../tests/open-toolchain/integration-audit.md).

The first clean-image frontend repeat fails because sv2v is absent from the
base image; this is a missing prerequisite, not a test pass. The diagnostic
Dockerfile explicitly installs official sv2v v0.0.13 with archive SHA-256
`552799a1d76cd177b9b4cc63a3e77823a3d2a6eb4ec006569288abeff28e1ff8`.
The corrected image passes the parent interface/high-Z fixtures in
`build/sc64-open/frontend-parent-final/`. Slang rejects the interface/inout
boundary in all three hierarchy modes and converts literal Z to X in the
separate fixture. Native Yosys after sv2v preserves the enable/zero/Z paths.

The full unchanged manifest also synthesizes through sv2v/native Yosys, but
expands DD RAM, both EEPROM banks and the MCU buffer into flip-flops. The
agent result is 91,014 LUT4 and 35,845 TRELLIS_FF, plus 12 DP8KC and 4 FIFO8KB;
it cannot fit SC64. The high-Z output survives. CIC initialization has a
matching one-bit population only, not verified word order. Parent full-design
repeat also passes synthesis/check with 90,904 LUT4 and the same 35,845
flip-flops, 12 DP8KC and 4 FIFO8KB; all four register-mapped memories remain.
The variation in LUT mapping does not change the failed capacity result.
Evidence: `build/sc64-open/full-parent-final/{inputs,status,mapping-summary}.json`
and `synthesis.log`. This diagnostic path does not qualify a firmware image.

Combined image ID:
`sha256:6c1b547003a32e50d26ba99c53e9a45967a70f4fb7226080dadc03048bbf10a1`;
base image ID:
`sha256:9632531eb216aefc18f12f8de0c005faef60b433df37e11b59bac0a1c8a45d3a`.
The missing-converter regression returns 127 with explicit failed status;
the timeout smoke returns 124. Repository lint passes through the Git Bash
entry point. Initial attempts through Windows' WSL `bash` fail on checkout
CRLF parsing before any lint executes; those attempts are not passes.
No cart/SD/firmware operation occurs in this backend round.

The ODDR clock mux also exposes a database ambiguity: requested `CLK` and
`INV` share a bit encoding at the relevant PIC_B0 location. Readback can
canonicalize to `INV`. Existing routing connectivity and roundtrip checks
do not establish physical edge polarity, so the external SDRAM clock remains
unqualified.

The isolated [open-toolchain probes](../../tests/open-toolchain/README.md)
use OSS CAD Suite 2026-09-05 with a verified archive SHA-256, Slang/Yosys,
Project Trellis, and nextpnr. They do not use Diamond or a license file.
The official Diamond baseline fails with an expired-license checkout
(expiry 2025-02-23), recorded in
`build/sc64-gif-hardware/diamond-baseline.log`.

Unmodified open-backend baseline, before the diagnostic patches above:

- The packaged open toolchain runs successfully but omits SC64's
  `LCMXO2-7000HC-6TG144C`. An actual device-selection attempt fails with
  `Unsupported MachXO2 chip type`. A source build explicitly selects 7000.
- The unchanged SC64 manifest, constraints and CIC are hashed before probing.
  Full-source elaboration identifies unknown `EFB` and `ODDRXE` primitives.
  The generated FIFO/PLL parameters are accepted when the existing primitive
  declarations are passed directly to Slang.
- On the packaged 1200 device, an ordinary logic control synthesizes and routes.
  Separate `EFB`, `ODDRXE` and `FIFO8KB` probes synthesize, then fail in
  nextpnr with explicit unsupported-cell diagnostics. They retain the cell
  names; empty diagnostic declarations do not implement those blocks.
- The pinned source build completes with explicit 7000 support. On SC64's exact
  part, the logic control passes synthesis, routing and bitstream generation.
  `EFB`, `ODDRXE` and `FIFO8KB` each fail routing with unsupported-cell errors
  (exit 125). The full capability suite returns failure, not a hardware pass.
  Evidence: `build/sc64-open/7000-image.log`, `cells-7000-native/`, and
  `baseline-native/`. Repository lint passes.
- Remaining: real backend support for the three hard cells, complete pin and
  electrical constraints, timing/PLL/SDRAM-clock validation, configuration/UFM
  and programming-format validation, then the unchanged SC64 hardware gates.
  The GIF design follows those gates. No incomplete design is flashable.
- Disposition: research only. No new cart firmware, physical decoder test,
  or measured UI performance result is claimed.

### Original-byte transport and exact frame reuse

- In progress: cart-RAM source reads and packet writes/readback using the
  existing `memory_dma`, with bounded FIFOs and test-only arbitration ahead
  of the unchanged CFG port. SD file staging remains a separate cost.
- In progress: an exact byte-comparison/replay stage for consecutive retained
  GIF images, with bounded external buffers, metadata/session identity,
  success-only reference commit and cancellation. The 407 host-identified
  candidates are not runtime skip flags or preconverted theme assets.
- The official Diamond environment is installed; its unchanged baseline build
  stops at the expired license described above. Hardware decoder testing follows
  integrated fit/timing and lifecycle verification.
- Installed firmware, production ROM and original user settings are unchanged.

### Reuse SC64 memory infrastructure for original themes

The follow-up targets the existing `mem_bus`, `memory_arbiter`, `memory_sdram`
and `memory_dma` implementations. The missing bridge is a decoder client
adapter and ownership integration, not a replacement SDRAM controller.

- The bounded dictionary/canvas adapter passes 4,096 dictionary round trips,
  byte lanes, bounds, fairness, reconfiguration and cancellation checks,
  including a fresh parent run.
- The strict original-GIF pipeline through unchanged arbiter and SDRAM RTL
  passes all 1,717 images and 430 packets. Sixteen exports match the prior
  pipeline byte-for-byte. Scripted N64, USB and SD peers each complete 335,425
  checked operations; 251,246,900 grants pass priority/reservation checks.
  Mean modeled work is 1,600,351 clocks/image, maximum 2,619,056, excluding
  source fetching and output transfer. This does not establish 60 FPS.
- Existing DMA reuse probe passes sixteen original-GIF RTL output packets and
  64 cases, including parity, stalls, stop/drain and restart. This uses a modeled
  memory responder, so it does not establish SDRAM timing or live playback.
- The [vanilla-theme audit](notes/vanilla-themes.md) identifies direct
  BMP/font paths, GIF compatibility limits, disabled N64 Ogg/MP3 decoders and
  missing OS4 tracker-music admission. Audio still needs its own runtime tests.
- Exact consecutive-payload reuse has 407 candidates in original Final Fight;
  all match Pillow-composed pixels. Runtime comparison/reuse remains unimplemented.
- Physical firmware and original user settings remain as restored below.
  Diamond licensing, integrated fit/timing and hardware playback are still
  outstanding; no new firmware is flashed for these simulations.

### Final Fight FPGA conversion follow-up

The user clarified that the requested test is specifically **FPGA conversion
of original GIFs into an N64-usable format**, using Final Fight. GIF64 is not
required if another output format performs better. Unrelated MCU, USB and SD
experiments are stopped. Three preliminary baseline captures completed before
the clarification (48.5, 49.5, 49.5 FPS, zero underruns). No new MCU firmware or
USB candidate was deployed; the temporary USB source edit is removed.

The [prototype results](notes/gif-prototype.md) record the full
comparison and remaining integration requirements. Reproducible RTL lives in
`vendor/sc64/tests/gif/`; N64 receiver tools live in `vendor/sc64/tests/phosphoros-receiver/`.
Generated logs/fixtures remain under `build/sc64-ui-all/`.

- Reference LZW: 1,772 fixtures, all 1,717 original images and 200 cancellation
  checks pass, including parent reruns. Standalone mapping uses 14 EBR blocks.
- LZW/compositor/packet pipeline: all original images pass with 430 accumulated
  packets. The compositor's RAM dirty map reduces mapping from 6,130 to 630 LUT4
  plus one EBR, with identical packet output.
- Cached external-dictionary LZW passes all 1,772 fixtures and maps to six EBR
  blocks. Its serialized dictionary/canvas simulation passes all 1,717 images
  with identical packets. None of these components is a cartridge image.
- N64: 180 offscreen renders pass source pixel/guard checks. This includes 30
  renders using unchanged packets emitted by the RTL simulator. Full frames,
  tiles and row spans each win for different update shapes; no universal winner
  or 60-FPS playback result is claimed.
- Authoritative SC64 placement/timing is blocked by the missing current Diamond
  license. Current upstream no longer ships one. The real SC64 memory/register
  bridge and lifecycle integration also remain necessary before a board test.

Host-generated reference packets are research fixtures, not a proposed user
conversion step. No new MCU or FPGA firmware was flashed in this follow-up.

Restoration is complete: temporary RTK receiver code is removed, the production
ROM has no Git diff, both owned SD fixture files are removed after hash checks,
and original configuration write/download hashes match. The restored production
Final Fight check boots in 524 ms, starts music at 551 ms, and reports 560 frames
over 10,004 ms with zero audio underruns or producer overruns. This is an idle
restoration check, not the navigation benchmark or a decoder improvement. Original user
theme Ghosts'N Goblins is subsequently restored and boots in 674 ms with music
at 699 ms. Console remains running; the hardware test sessions are closed.

### Previous round

- Production navigation baselines and separate detailed-profile runs complete.
- CFG reply batching hardware comparison complete: no meaningful UI gain.
  Candidate rejected for this goal; original five-change MCU is restored and
  readback verified. Repeat baselines confirm no meaningful candidate gain.
- Original-GIF source, LZW/composition and dirty-tile host analyses complete.
  Next research is a bounded RTL pilot and general GIF fixtures; no decoder
  implementation or synthesis fit has been completed.
- Installed firmware: original five-change production fork MCU restored and
  readback verified; original MCU loader prefix, FPGA and stable N64 bootloader
  remain byte-identical. Original production ROM and user configuration are
  restored; final normal SD boot and runtime verification passed.
- Ghosts'N Goblins and the original user settings are restored. Console is
  running; all testing USB sessions are closed. Original backups remain under
  `build/sc64-ui-research/`.

## Baseline and evidence

PhosphorOS baseline: `88976d49`. SC64 fork: `fdb5cc6` (last code change
`7a5bb99`). Real 4 MiB N64; USB-powered cartridge. The previous Ghosts'N Goblins
idle capture was about 59.8 FPS with zero underruns; it does not establish
performance in animated themes or during navigation.

Use unchanged benchmark scenarios for A/B. Detailed profiling, if needed,
gets its own baseline because instrumentation can change frame cost. Raw logs,
agent reports, temporary builds, and simulations live in the ignored local
directory `build/sc64-ui-research/`; durable results are summarized here.

## Candidate ledger

| Idea | Current evidence | Test / disposition |
|---|---|---|
| Batch MCU CFG reply registers | Host/ARM tests pass; hardware Final Fight 47.4 to 47.6 FPS, Sunset 29.3 to 29.4 FPS, with zero underruns. Restored baselines 47.3 / 29.3 FPS. | Rejected for UI goal: gain too small to establish value; original MCU restored and verified. |
| CFG argument-read and remaining memory/DMA groups | Adjacent registers offer smaller wire savings; CFG read-ahead reaches a side-effect-free command register in current RTL. | Source proposals only; exact burst/trigger tests needed. |
| Runtime SD cursor reuse / atomic READ_AT | Runtime libcart still sends SECTOR_SET for each 8 KiB RDRAM chunk; bootloader cursor optimization does not reach it. | Unimplemented. Shared command/cursor ownership, errors, writes and fallback need tests. |
| Asynchronous SD prefetch | SD-to-cart media fill remains synchronous; subsequent cart-to-RDRAM PI DMA is already asynchronous. | High-value integration hypothesis if SD stalls dominate; requires command-channel ownership and cancellation. |
| SD slice tuning | Larger slices reduce command overhead but can lengthen frame stalls. | Profile before changing existing consumer budgets; no new test yet. |
| Extra MCU cfg service point | Prior boot experiment improved latency; not an accepted runtime change. | Held for rear-button debounce and save-writeback fairness validation. |
| Single-sector commands / larger block counts / faster SPI | Prior tests found no useful CMD17/CMD24 boot gain; 257-sector count wraps; 16 MHz SPI corrupts reads. | Previously rejected or held; no new UI result reverses these findings. |
| Direct normal-GIF FPGA LZW/composition | Independent host decoder/compositor matches Pillow on all 1,717 original Final Fight frames; parent rerun passes. | User-priority research; no RTL decoder or synthesis fit yet. General disposal/local-palette/interlace cases remain pending. |
| Direct-GIF dirty-tile output | Original Final Fight mean consecutive-frame tile payload is 16,551 bytes versus 76,800 full-frame bytes. | Promising host traffic model; skipped-frame references, plane history and hardware execution remain to validate. |
| On-device conversion/cache | Can amortize preparation while accepting original GIF files. | Optional architecture, unimplemented; no new mandatory generated asset workflow. |
| FPGA LZ4 or existing PDS delta acceleration | Current measured assets are independent LZ4 frames; expanding on cart increases PI bytes. | Transport model and actual frame validation complete; no decoder RTL implementation. |
| Palette conversion / fill-copy / scaling / audio offload | Existing RDP/RSP already performs graphics/mixing; cart output must still cross PI. | Source proposals only. Establish unavoidable work and end-to-end gain first. |
| SDRAM arbitration / bursts / PI FIFO | Actual arbiter blocks SD SDRAM work throughout PI reservation; BRAM exception passes simulation. | Existing policy verified, no optimization made. Removing mask or changing bursts needs timing/refresh/abort proof and synthesis. |
| BRAM ping-pong window | BRAM remains accessible during PI SDRAM reservation. | Unimplemented; shared scratch ownership and producer/consumer safety needed. |
| Direct FPGA RDRAM/RDP access or CIC soft-CPU reuse | Cart has no N64 RDRAM bus-master interface; CIC core has authentication duties. | Reject direct access as described; CIC reuse not recommended. |
| N64 RSP LZ4/delta, cache publication, RDP/PI overlap | Profile shows substantial GIF unpack time and nontrivial USB/browser costs. | Source proposals; preserve audio priority, cache-line bounds and displayed-plane retirement. |
| Defer USB polling while PI DMA is busy | USB register accesses wait for outstanding PI DMA; the USB scope can therefore include GIF transfer wait. | New unimplemented scheduling probe; measure entire loop and command responsiveness, since it may only move the wait. |
| Generic MCU pixel engine / extra firmware cache | MCU has 8 KiB SRAM and 8 MHz SPI; Phosphor already owns metadata/cart-stream/image caches. | Pixel routing through MCU is a poor fit; no extra cache without demonstrated misses and exact invalidation. |

## Completed tests

### Real N64 production baselines

Unchanged `browse10-nav`, music and effects on; one 10-second run per theme.
These are observations, not repeated-sample confidence intervals. GIF counters
come from the existing harness and must not be interpreted as distinct physical
presentations without checking their owner semantics.

| Theme | Frames / window | FPS | p50 / p99 / max ms | GIF frames / ticks / drops | Audio underruns |
|---|---|---:|---|---|---:|
| Ghosts'N Goblins | 599 / 10014 ms | 59.8 | 17 / 23 / 36 | 0 / 0 / 0 | 0 |
| Final Fight | 495 / 10007 ms | 49.5 | 20 / 34 / 44 | 484 / 598 / 116 | 0 |
| Sunset Drive | 297 / 10013 ms | 29.7 | 32 / 63 / 100 | 297 / 591 / 294 | 0 |

Ghosts is the scrolling-background control. Both animated themes miss the
approximately 16.67 ms frame budget. Raw evidence: `ghosts-baseline.log`,
`final-fight-baseline.log`, `sunset-baseline.log` under
`build/sc64-ui-research/`. Durable harness rows are in [perf_log.md](benchmarks.md)
and [perf_log.csv](benchmarks.csv), labeled `sc64-ui-production-baseline`.

### Detailed-profile baseline

A separate temporary ROM enables `PHOS_PERF_DETAIL`; do not treat comparison
with production as a firmware effect. Final Fight: 475 frames / 10020 ms, 47.4 FPS,
p50/p99/max 20 / 38 / 50 ms. Sunset Drive: 293 frames / 10014 ms, 29.3 FPS,
p50/p99/max 33 / 63 / 100 ms. Both report zero underruns.

| Scope | Final Fight mean / max ms | Sunset Drive mean / max ms |
|---|---|---|
| Complete loop | 21.091 / 49.709 | 34.173 / 215.245 |
| GIF unpack | 7.166 / 7.731 | 11.404 / 11.743 |
| GIF staging | 1.440 / 6.573 | No samples |
| USB poll | 2.336 / 3.815 | 6.024 / 8.318 |
| Browser scan | 1.002 / 4.918 | 5.765 / 163.643 |
| Frame begin | 12.017 / 21.197 | 14.428 / 26.812 |

Scopes can nest or cover different sample counts; do not add them. Missing
GIF staging samples do not prove all SD/PI traffic is absent. The frame
histogram reports a 100 ms maximum for Sunset while the detailed loop scope
records 215.245 ms; retain both owning measurements rather than discarding the
outlier. Logs: `profile-final-fight.log`, `profile-sunset.log`. Durable harness
labels: `sc64-ui-profile-baseline`.

### Host and RTL evidence

- Actual unchanged memory arbiter: SD SDRAM request stays blocked 100 cycles
  during PI reservation despite no active N64 word request; resumes after
  release. BRAM exception and simultaneous-request N64 priority pass. This
  verifies policy, not SDRAM timing or an accelerated board design.
- Actual card GIF64 files: all 1,717 Final Fight and 145 Sunset Drive PDSB LZ4
  frames decode to exactly 76,800 bytes on host. Mean record sizes 17,880 and
  54,080 bytes. No original-GIF pixel parity claim from this test.
- CFG reply tests/build described above pass. Hardware comparison below is
  complete; no candidate accepted yet.

### Original GIF reference and dirty-update models

The original Final Fight background was obtained from the pinned upstream
theme archive; [the FPGA note](notes/fpga.md) records source URLs,
archive/GIF hashes and exact reproduction commands. The original file remains
unchanged. Research Python/Pillow scripts are test oracles, not an end-user
conversion requirement.

An independent bounded LZW parser/compositor decoded all 1,717 original frames
and matched Pillow RGBA output byte-for-byte. Parent independently reran the
probe successfully, and reran all three existing-arbiter assertions. The GIF
uses one 256-entry global palette, no local palettes/interlace, transparent
pixels and disposal zero. Its authored delays are all 10 ms; their 17.17-second
sum is not a claim that OS4 presents 100 unique frames per second. The owning
OS4 animation policy controls cadence.

The source global palette already permits a CI8 pilot without dynamic palette
assignment or a prepass. The UI agent's separate output-color analysis found
252 distinct RGBA5551 colors; this is compatible with, and distinct from, the
source's 256 palette entries. General local palettes, disposal 2/3, overflow
and malformed-input fixtures remain mandatory before general compatibility.

| Reference-frame gap | Mean changed CI8 tile payload | With 150-byte mask and full 512-byte TLUT | p99 tile payload |
|---|---:|---:|---:|
| 1 | 16,551 bytes | 17,213 bytes | 67,456 bytes |
| 2 | 18,315 bytes | 18,977 bytes | 69,056 bytes |
| 3 | 21,715 bytes | 22,377 bytes | 69,568 bytes |
| 4 | 22,024 bytes | 22,686 bytes | 70,144 bytes |

These models compare composed RGBA5551 output using changed 8Ã—8 tiles; the
initial keyframe is excluded and worst-case tile payload is 76,800 bytes for
every gap. Packet headers/alignment and N64 tile application add work. A
consumer plane containing an older frame cannot safely apply a delta against
the wrong reference; generation, cancellation and retirement contracts are
part of the proposal. No FPGA GIF decoder, fit, timing closure or board speed
result exists yet.

### CFG reply batching hardware experiment

Official MCU update completed, then readback matched candidate SHA256
`22f35ce0a0eb846bc35e567d1c6e88974ee005307b30773216b87df6fbb250fe`.
The original MCU loader prefix, FPGA and stable N64 bootloader were preserved.
Both sides used the same detailed-profile ROM and unchanged navigation harness.

| Theme | Baseline frames / window / FPS | Candidate frames / window / FPS | Baseline / candidate p99 ms |
|---|---|---|---|
| Final Fight | 475 / 10020 ms / 47.4 | 476 / 10005 ms / 47.6 | 38 / 40 |
| Sunset Drive | 293 / 10014 ms / 29.3 | 294 / 10013 ms / 29.4 | 63 / 63 |

All captures report music playing, zero audio underruns and zero producer
overruns. The differences are too small to accept this firmware change for
the UI goal. Original MCU restoration/readback passed. No scratch SD write/read
test was performed because the candidate is rejected, so it does not receive
broader SD/save compatibility acceptance.

Restored-profile baseline repeats: Final Fight 473 frames / 10,002 ms
(47.3 FPS), p99 38 ms, GIF frames/ticks/drops 462/598/138; Sunset Drive
293 frames / 10,016 ms (29.3 FPS), p99 63 ms, GIF counters 293/591/298.
Both have music playing and zero audio/producer overruns. These repeats support
the rejection; they do not constitute a formal statistical significance test.

The production ROM is restored byte-for-byte in the working tree and uploaded
to cart SDRAM before reset to normal SD boot. Original user configuration was
restored to SD and downloaded back byte-identically. Temporary profile build
flags are removed from staging. Final normal SD boot/runtime verification passed.

One attempted capture encountered COM access denied while the preceding boot
session was closing; the rerun succeeded. This is a harness collision, not
evidence of a firmware failure. The initial profile boot took 1190 ms and failed
the existing 1000 ms readiness threshold; a later candidate boot took 474 ms with
music at 503 ms under different warm-asset/state conditions. Neither timing is
an attributable firmware boot improvement. Keep this failed threshold in the
record rather than counting it as a boot pass.

### Final restoration verification

- Full firmware backup SHA256
  `d0614001ee0e7a17cf3cd6e3c95a822053fb4bb9693198362e80830a0ac2cf2f`
  matches the pre-test five-change production fork backup exactly. FPGA unchanged.
- Production `sd/sc64menu.n64` has no Git diff and SHA256
  `3cb54aa0b7f8553868aac5c7b8953fbb12ccec449153b08e41728e2a5019c7ce`.
- Original configuration SD write/download hashes match exactly; Ghosts'N Goblins
  is restored.
- Normal SD production boot: frontend ready 682 ms, music 708 ms.
- Final idle capture: 599 frames / 10,012 ms, approximately 59.8 FPS,
  p50/p99/max 17 ms, zero audio underruns and producer overruns, detail profiling
  off. Logs: `final-boot.log`, `final-runtime.log`.

This completes restoration for the research round. It does not claim the heavy
animated themes have reached 60 FPS; their measured baselines remain above.

## Original-GIF qualification restart — 2026-09-06

The target is on-demand streaming from the original GIF, not a saved converted
asset. The FPGA decodes into temporary bounded RAM, the N64 consumes the output,
and playback reuses the buffers. No converted GIF/GIF64 file or whole-animation
decoded cache is part of this design. PC fixture exports below exist only to
verify bytes and transport behavior.

The installed firmware remains unchanged. Its full backup SHA256 is
`d0614001ee0e7a17cf3cd6e3c95a822053fb4bb9693198362e80830a0ac2cf2f`.
Evidence for this round is under ignored `build/sc64-gif-qualification/`.
Temporary private tooling is outside the tracked project.

| Fresh check | Result | Scope and limitation |
|---|---|---|
| Real N64 Final Fight, unchanged `browse10-nav` | 486 frames / 10,013 ms, 48.5 FPS; p50/p99 20/36 ms | Installed production `.gif64` playback baseline, not FPGA original-GIF playback. Boot 564 ms, music 592 ms; zero audio underruns/producer overruns. |
| Compact LZW decoder | Pass: 1,776 fixtures, including all 1,717 original frames and 131,865,600 decoded bytes | 200 cancellation cases, four memory-error/restart cases and corrupt-chain guard pass; both deliberately undersized variants fail as expected. Simulation only. |
| Compact local proof | Pass | Local arithmetic/transitions, not whole sequential equivalence. |
| Raw transport | Pass: all 1,717 original frames and four pulse/held cancellation/error/restart cases | Exact 131,865,600 output bytes, intact tail guards and no late writes after retirement. New `--all-frames` gate committed in vendor `a3108cc`. |
| Actual SC64 arbiter fairness | Pass: all 54 scenarios | Finite workload coverage, not arbitrary-load latency proof. |
| Complete raw source, original Diamond constraints | Rejected at mapping | 28/26 EBRs, 9,064/7,209 registers, 5,731/3,432 slices and 9,408/6,864 LUT4. No routed candidate or hardware qualification. |

The failed fit expands the decoder's 512-byte stack into registers; retiming
adds 1,292 registers. Cache and transport FIFO inference succeeds. A paired
stock report uses all 26 EBRs, so fixing stack inference alone cannot resolve
the memory shortage. The next experiments normalize the stack's synchronous
ports and investigate stock memory packing while preserving read/write
collision semantics and initialization. Each requires behavioral/proof gates
before another complete fit.

The installed firmware's self-test passes all 44 SDRAM patterns, including
both 60-second retention checks. USB read/write measures 12.54/16.72 MiB/s;
the read-only SD test measures 6.05 MiB/s. No candidate firmware is flashed.
Original Ghosts'N Goblins configuration is restored with byte-identical SD
readback; normal boot passes at 680 ms with music at 706 ms. These restoration
times are not a comparable Final Fight performance measurement.

The commit inventory includes 28 GIF-path commits and 12 related qualification
commits; historical results are not fresh rerun passes. The maintained
[per-commit coverage](notes/gif-commit-coverage.md) records fresh
evidence for every executable GIF-history branch and distinguishes the two
documentation-only commits. Open-toolchain-only experiments are outside this
direct Diamond round. Additional fresh checks:

| Experiment | Fresh result | Limitation |
|---|---|---|
| Reference LZW | Pass: 1,772 fixtures, all 1,717 originals, 200 cancellations | Component model. |
| CI8 compositor / GPD1 | Pass: 1,717 frames, 430 packets, 10,245,568 packet bytes; fault suite passes | First attempt stops at frame 896 and is incomplete; separate full rerun supplies the accepted evidence and 16 DMA fixtures. |
| Runtime exact reuse | Pass: 407 hits across all 1,717 images, 80 cancellation offsets | Standalone model, not integrated playback. |
| Output DMA | Pass: 64 cases using the 16 fresh original packets | Delayed memory-bus model. |
| Scratch bus adapter | Pass: 4,096 dictionary entries, six lane cases, seven invalid configurations, 65 cancel offsets | No physical memory. |
| Three-client mux | Pass: equivalence/induction, exhaustive 32-state selector, negative controls and synthesis | Historical architecture prerequisite. |
| Four-client MCU mux | Pass: saturation, cancellation/drain, restart and held-ACK gates; bad ACK routing rejected | Component synthesis 238 LUT4 / 57 FF. |
| Legacy transport abort | Pass: eight normal images and all 12 abort/restart cases | Finite actual-controller simulation. |
| Bounded transport | Pass: identical reference/candidate normal logs and all 12 aborts | Uses freshly verified three-client mux. |
| Phrase bound | Pass: 8,390,656 abstract transitions, all seven minimum sizes; invalid jump rejected | Mathematical/local bound, not whole hardware equivalence. |
| Normalized stack | Pass: all 1,776 decoder fixtures with identical cycles/bytes, write-control SAT and negative control | Default-eight raw transport and deliberate output-byte corruption detection also pass. |
| Cached decoder / compositor | Pass: all 1,717 originals; decoder 1,772 fixtures, compositor 430 packets | Same historical counts; serialized memory model. |
| Actual-controller integration / full transport | Pass: all 1,717 frames and 430 packets each | Full transport checks 5,122,784 output writes and equal DMA readbacks, plus concurrent N64/USB/SD service. |
| Compositor arithmetic / header | Pass: six 1,549-point proofs and negative; header exact eight-frame/12-abort behavior | Area variants remain rejected or absent from raw output. |
| Dictionary sizes / external spill | Pass: all three 1,772-fixture size suites; 1,775 spill fixtures and varied-value mutations | Smaller dictionaries still use six EBRs and increase cycles; spill remains unselected. |
| Historical transport / composed stock fit | Synthesis/structural/negative gates pass | Composed stock candidate still exceeds capacity at 8,644 packed logic cells versus 6,864; no hardware acceptance. |

Further fit experiments remain rejected:

| Candidate | Registers | Slices / 3,432 | LUT4 / 6,864 | EBR / 26 |
|---|---:|---:|---:|---:|
| Normalized distributed stack | 3,907 | 3,629 | 6,738 | 28 |
| Normalized block stack + guarded DD source inference | 3,975 | 3,504 | 6,517 | 29 |
| Explicit DD primitives + block stack + distributed FlashRAM | 3,800 | 3,491 | 6,518 | 26 |
| Same RTL, clean vendor area strategy | 3,729 | 3,467 | 6,512 | 26 |
| Pipelining only, original synthesis target | 3,739 | 3,489 | 6,517 | 26 |
| 16-byte queues, area strategy | 3,705 | 3,444 | 6,476 | 26 |

The DD source passes local collision equivalence and 6,000 full-width model
cycles, but does not save RAM blocks in Diamond. Explicit DD primitives
validated against the installed vendor model and a distributed mapping hint
for the 128-byte FlashRAM buffer meet the RAM-block limit; logic remains 59
slices over capacity. The parent repeats the 6,000 vendor-model cycles and
forwarding-negative gate successfully. An area-option attempt reused generated
project paths and did not apply the option; it is not accepted evidence. A
clean-source build applies the option and remains 35 slices over capacity.
The installed tool implements area mode by lowering its synthesis target to
1 MHz; original LPF timing constraints remain unchanged, and no timing pass
is claimed. A clean 100 MHz pipelining-only experiment is next; smaller
temporary stream queues also require full backpressure/cancellation checks.
The CIC two-block shortcut is rejected: the vendor model exposes different
read-during-write behavior.

The 16-byte queues pass a paired full 1,717-frame/four-abort run against the
64-byte baseline. Modeled phase cycles rise from 2,007,513,771 to 2,027,547,849
(0.99795%); this trades a small modeled throughput cost for area. Source-index
aliasing is rejected by the byte-order gate. This is temporary stream storage,
not a persisted converted asset or a measured UI speedup.

Complete mapped/routed candidates still fail the original 100 MHz requirement:

| Candidate | Mapping | Routed maximum | Disposition |
|---|---|---:|---|
| 16-byte queues + resource sharing + area strategy | 3,431 slices, 26 EBR | 75.177 MHz | Reject timing. |
| Same RTL, 100 MHz synthesis target | 3,431 slices, 26 EBR | 82.686 MHz | Reject timing; read-address to MCU read-data path is critical. |
| Single-write-port dictionary | 3,431 slices, 26 EBR | 74.305 MHz | Reject as improvement. Full 1,776 core fixtures and eight-frame/four-abort transport pass, but whole-module proof attempts remain incomplete; local write-control proof alone is not whole-module equivalence. |
| Banked MCU read selection | Complete mapping and routing | 84.767 MHz | Reject timing. All 40 source-derived read arms and 256 addresses match; full source elaboration and a compilable wrong-bank negative pass their gates. No command-latency change. |

Reports are preserved in `build/sc64-gif-qualification/diamond-reports/`.
The best candidate is not hardware-qualified. No experimental firmware is
flashed, and the original configuration and normal production boot remain
restored. Next work is timing closure of the MCU read path and production job
ownership/original-GIF streaming integration, not saving a converted file.

## GIF timing closure follow-up — 2026-09-06

The complete stock Diamond build passes 102.891 MHz; the best integrated GIF
candidate remains at 84.767 MHz. The original 100 MHz clock and external timing
constraints remain the acceptance requirement. No timing-failing candidate is
to be flashed.

Inspection of the banked-MCU candidate's actual routed report moves the worst
path to decoder `next_code` through code-width logic: 11.664 ns, 13 logic levels,
against 9.867 ns available. A separate N64 PI address-decode path takes
11.412 ns. Current experiments simplify these paths without changing observable
transaction latency, and separately compare Synplify pipelining-only against
its retiming setting. Tests and complete routes must finish before claiming
an improvement; all isolated candidates and reports remain under
`build/sc64-gif-qualification/`.

| Experiment | Complete routed maximum | Result |
|---|---:|---|
| Synplify pipelining-only; MAP retiming retained | 79.033 MHz | Rejected; slower than baseline. |
| Equivalent next-code width-growth threshold | 85.785 MHz | Improvement, still fails 100 MHz. Full 1,776 decoder fixtures and eight raw frames/four aborts preserve all baseline cycles and output. |
| PI range predicates replaced with exact bit comparisons | 84.717 MHz | Rejected as an improvement against 84.767 MHz; proof does not establish speed. |
| Per-bit code mask, independently from width-growth rewrite | 86.790 MHz | Best completed GIF route; still fails 100 MHz. Full core and focused transport tests preserve output/cycles. |
| Shared mask, resource sharing disabled | No route | Mapping fails at 3,491/3,432 slices, 26/26 EBR; no timing result. |
| Registered code mask | Interrupted | Parent stops the owned Diamond container during routing when the user scales back scope. No completed frequency or qualification result. |

The width-growth change moves the worst path to retimed width through
`stack_size[9]`: 11.525 ns and 14 logic levels. Parent reruns of actual-SV SAT
prove the threshold and independent per-bit mask identities. The mask-only
variant also passes the full decoder and focused raw-transport suites.
PI predicate simplification passes the parent's 2,097,152 address/feature
comparisons. A separate actual-SV MCU read-transition proof establishes all
64 next-state read/debug bits, with a compilable wrong-bank negative failing.
Its symbolic arm values rely on the unchanged-body source gate.

The registered mask passes 1,776 core fixtures, eight raw frames/four aborts,
and 67 actual-source invariant fixtures; an incorrect growth bit fails the
invariant. A remaining-byte counter separately passes the full core and
focused transport tests. Its combined shared-mask variant passes the full
core only; combined queue16 and SAT gates are not started before the pause.
These functional results do not supply the interrupted physical timing result.
Report directories use the
corresponding `raw-*` names under `diamond-reports/`. An initial shared-mask
staging attempt fails because Python 3.6 lacks `copytree(dirs_exist_ok=...)`;
the corrected clean staging directory is separate, and no failed staging is
counted as a build or timing result.

## Practical SC64 and PhosphorOS review — 2026-09-06

The user scales back accelerator work to examine smaller improvements across
the existing system. No further GIF timing builds or hardware operations are
started. The parent stops `sc64-gif-diamond-fit`; its files remain available.
Other unrelated containers and the console are untouched. Research fixtures
are temporary developer evidence, not a change to the original-GIF-only
playback requirement.

This review checks the maintained boot/UI/gap ledgers, FPGA/MCU/UI and theme
research, the prior [documentation inventory](notes/documentation-audit.md),
SC64 protocol/memory documentation, and the owning source paths below. It
also checks the official [SC64 site](https://summercart64.dev/),
[command/interrupt contract](https://github.com/Polprzewodnikowy/SummerCart64/blob/main/docs/01_memory_map.md)
and [MachXO2 documentation index](https://www.latticesemi.com/Products/FPGAandCPLD/MachXO2).
Historical research pages contain superseded pending statements; completed
measurements in this ledger control their disposition. This is a targeted
technical review, not a new every-line audit of every historical artifact.

### Ranked opportunities

| Priority / change | Owner and useful effect | Evidence, limits and smallest next check |
|---|---|---|
| 1. Overlap SD-to-cart filling with useful N64 work | Existing `media_fill`/`stage_slice` in `src/platform/cart_sc64_n64.c`; likely no FPGA change. Potentially fewer theme/music/video refill stalls. | The producer still calls synchronous `read`; cart-to-RDRAM DMA is already async. SC64 already has submit/status/optional completion IRQ. Trace SD wait first, then one owner-held submit/poll job with exclusive command/sector/byte-swap state. Publish bytes only after successful completion; drain before theme close, launch, or arena reuse. Hardware benefit remains unmeasured. |
| 2. Preserve PI DMA overlap when servicing USB | Existing frame service order and `src/platform/usb_sc64_n64.c`; no new FPGA engine. Potential reduction in CPU waiting. | Historical profiles attribute 2.336 ms on Final Fight and 6.024 ms on Sunset to USB scope, but libdragon register access can wait for pending PI DMA. These are not proven USB overhead savings. A bounded defer-while-PI-busy A/B must improve whole-loop/p99 time and retain command latency, halt/reset and audio service. |
| 3. Target the measured N64 decode/render cost | Existing RTK GIF/GPU owners and established RSP/RDP seams. Helps cached themes where MCU changes cannot. | Historical Final Fight unpack average is 7.166 ms. Separate decode, publication/cache maintenance and RDP wait before changing any algorithm. Existing CI8, async DMA, caches and prefetch are already present. Consider narrow CPU/RSP work only after attribution; preserve source animation cadence and image parity. |
| 4. Batch remaining MCU DMA setup writes | `vendor/sc64/sw/controller/src/{fpga,usb}.c`, using existing `fpga_reg_set_words`. Small command savings for USB/loading paths; no FPGA change. | Adjacent address/length/trigger sequences can reduce three SPI frames/18 wire bytes to one/14. At 8 MHz this saves four microseconds of wire time per three-register group, not milliseconds per UI frame. Review each register's side effects and trigger-last order; test odd lengths, abort/flush and byte hashes. Reply batching already showed negligible UI gains and stays rejected. |
| 5. Runtime sequential-read cursor or negotiated READ_AT | Runtime libcart and SC64 command owner, separate from the optimized bootloader. Potentially fewer commands while loading/streaming. | Boot cursor gains do not automatically apply to runtime. Trace repeated SECTOR_SET first. A shared cursor needs invalidation on writes/errors/USB/direct commands; READ_AT instead requires capability negotiation and stock fallback. Select one mechanism from evidence, not both preemptively. |
| 6. Fair service among non-N64 memory clients | `vendor/sc64/fw/rtl/memory/memory_arbiter.sv`. Most concrete small FPGA behavior lead: avoid USB starving SD under mixed traffic. | The actual-arbiter 54-case matrix shows zero SD grants during sustained USB, even without CFG traffic. This is synthetic arbitration evidence, not a demonstrated normal-UI freeze. Preserve N64 priority and the entire existing PI reservation. Check real overlap, then prove stable requests/ACK ownership and bounded progress among eligible clients; compare SD latency, USB throughput, saves/DD and reset behavior. |
| 7. Small diagnostic bus counters | Optional research FPGA instrumentation at existing arbiter/controller boundaries. Better attribution, not a direct speedup. | Per-owner granted words, wait cycles and peak waits can distinguish PI exclusion, arbitration and SDRAM service cost. Budget resource/timing impact and take coherent snapshots. Add only if software traces cannot resolve a specific bottleneck; do not retain temporary profiling code in production by default. |
| 8. Bounded cart-local copy/fill | Optional small FPGA engine under explicit cart memory ownership. Could avoid N64 round trips for substantial cart-resident copies. | No current workload measurement establishes enough copy volume to justify it. Profile first; define overlap, bounds, completion, cancellation and reset semantics before any implementation. The FPGA does not directly write N64 RDRAM or command its RDP. |

### Boundaries and rejected shortcuts

The five measured boot/MCU optimizations in
[`vendor/sc64/docs/phosphoros.md`](../phosphoros.md) are already
retained; they are not new runtime improvements. Their incremental timings
must not be added as independent savings. Broader card/game/save qualification
would make that existing series more useful upstream without inventing new
features; no pushes are authorized.

SDRAM bursts, deeper PI prefetch and permitting SDRAM work during an active PI
reservation are larger compatibility projects. The existing controller uses
single-word requests and a small PI FIFO. Changing a mode bit or dropping the
reservation is insufficient: refresh, row changes, aborts, mapping boundaries,
FIFO headroom and PI deadlines must all remain correct. Defer until traces
show a controller throughput limit.

Do not repeat 16 MHz SPI, MCU-only larger SD counts, removing CRC/timeouts/save
barriers, or commandeering CIC resources. Existing tests already reject or
exclude these shortcuts. Explicit DD RAM packing can free resources but is
not a demonstrated UI speedup. PI predicate cleanup fails to improve the
completed GIF A/B; banked MCU reads have only candidate-context timing evidence,
not a stock-system throughput result. Proof alone does not justify keeping an
optimization.

### Recommended next bounded experiment

Use the unchanged owning performance harness on Final Fight, with the same
ROM/assets/settings and a saved baseline. Attribute SD completion wait, PI
busy time, decode work and render wait without double-counting nested scopes.
Then select one software overlap experiment (SD producer or USB service),
whichever dominates. Compare repeated whole-loop median/p99, unique GIF frames
at the required source cadence, audio underruns and control latency. Add Sunset
for streaming pressure and Ghosts'N Goblins as a light-theme regression only
after a clear benefit. FPGA fairness is the first separate RTL experiment if
mixed USB/SD traces demonstrate its relevance. No numerical FPS gain is promised.

## Remaining work

### SD/USB overlap experiments — 2026-09-06

The user authorizes testing asynchronous SD-to-cart prefetch and bounded USB
poll deferral separately. Artifacts are in `build/sc64-overlap/`; the original
card configuration is preserved there, and the Final Fight configuration is
uploaded only with console power off and verified by readback. No firmware
update is part of these tests. `build.sh n64` synchronizes libdragon from
`cbc66918f` to `5e8bd05cbc1f3f2383d156a6a0939f634bcffd9b`, so the baseline ROM
is rebuilt before comparing candidates. Existing 4 MiB production hardware
and the unchanged `browse10-nav` harness are used.

| Candidate | Status / result |
|---|---|
| Fresh baseline | First-after-boot captures: 48.6/48.7 FPS, p50 20/20 ms, p99 38/36 ms, GIF frames 475/477. Same-boot repeats: 53.2/49.4 FPS, p99 31/32 ms. |
| USB polling deferral | Retained as `6a39cafd`: first-after-boot 50.2/50.5 FPS, p50 19/19 ms, p99 32/35 ms, GIF frames 491/493. Same-boot repeats 51.0/51.2 FPS, p99 31/31 ms. Small repeated boot-sequence gain; the warm-repeat ranges overlap, so no uniform 3–4% steady-state guarantee. All captures retain BGM, zero underruns and zero producer overflow. |
| Async SD producer | Rejected for insufficient demonstrated benefit. First-after-boot 49.0/48.8 FPS, p50 20/20 ms, p99 38/37 ms, GIF frames 480/480. Warm repeats 52.2/52.8 FPS, p99 31/32 ms, GIF frames 512/524. All captures retain BGM and zero underruns/producer overflow. The baseline warm range overlaps, and fresh-boot gains are only 0.4/0.1 FPS. |

The USB guard polls normally when PI is idle, defers while hardware DMA/I/O
is active, and forces an attempt after 50 ms at the next frame call. Software
input pumping remains unconditional. The interval bounds deliberate deferral,
not the duration of libdragon's subsequent PI wait. Fifty live pings during
animated Final Fight all reply within 70.720 ms against a 150 ms bound.
Boundary/wrap source checks, N64 build and lint pass. The fresh baseline ROM,
USB-only ROM, every capture, and latency samples are retained under the ignored
artifact directory. A warm-repeat improvement must not be inferred from the
first-versus-second capture alone: the third baseline drops back to 49.4 FPS.

The rejected async implementation starts one cluster-bounded SD-to-cart read,
then publishes its bytes only after completion. Source review catches and
corrects PI timing snapshot nesting, the physical cart address, sticky error
retry, final sub-sector completion, and cross-owner error propagation. Async
byteswap is excluded; the existing synchronous path handles that mode. The
actual-source GCC harness passes and the linked N64 disassembly confirms
libcart, direct cart commands and libdragon USB call the serialization wrapper.
The wrapper retains libcart's unbounded hardware completion wait and therefore
expands which callers can block; stuck-card/error recovery is not hardware
qualified. FAT extent discovery can still block on synchronous metadata reads.

All four deterministic SD fixtures are uploaded with the console off and
verified by full SHA-256 readback. The first runtime probe reports FAIL without
a useful diagnostic; occupied theme/audio stream slots are a suspected setup
cause, not a proven diagnosis. A diagnostic boot-time rerun, before theme and
audio stream acquisition, passes all four cases: 511, 513, 2 MiB + 513 and
128 KiB + 513 bytes. It checks every returned byte, logical cluster and 1 MiB
stream boundaries, and drain/close/reopen after observing a job owned by the
specific test stream. This does not establish physical FAT fragmentation,
command BUSY at observation time, error injection, or audio performance during
the tight correctness loop. The temporary boot probe includes the accepted USB
guard; every async performance ROM explicitly disables that guard.

The rejected code and all temporary probe hooks are removed. The exact tested
patch, ROM hashes, complete logs and host/real-cart fixtures remain ignored in
`build/sc64-overlap/`. SD fixtures are removed; the original card configuration
is restored byte-for-byte. The accepted USB-only menu is written to SD and
read back byte-for-byte, uploaded to SDRAM, then reset to normal SD-menu boot.
Normal SD-menu boot reaches the original Ghosts'N Goblins theme in 686 ms
and starts its music in 711 ms. The final production source builds and lint
passes; the SD deliverable remains the exact hardware-qualified `6a39cafd`
artifact. No firmware/FPGA update or push occurs in this round.

1. Finish fresh verification of the remaining GIF experiments. Keep historical,
   superseded and rejected variants distinct from the selected candidate.
2. Separate PI wait, decode and cache work and explain USB/browser
   stalls before selecting asynchronous transport or a decode accelerator.
3. Repeat promising candidates on the N64; retain only measured improvements.
4. Resolve FPGA resource use and obtain original-constraint timing closure.
   Replace fixed research memory windows and pulse status with bounded job
   ownership, atomic submission, sticky completion/error and safe cancellation.
   Add incremental original-GIF parsing and an N64 palette/disposal-aware raw
   consumer before UI A/B; retain software fallback. Simulation and theoretical
   bandwidth are not measured UI improvements.
5. Restore and verify temporary state after every subsequent hardware round.

## Frame-time follow-up, 2026-09-08

The user parks boot work at approximately 335 ms warm application readiness
and prioritizes Final Fight background/frame time. Accepted software baseline
is root e6b69f79, ROM 5b5d5b1cfa407f80df06daa459767e3986b0984e4f407e13800d7bf9a5c0bf1b,
with accepted ff00d9ed MCU and unchanged FPGA. The production menu is uploaded
to SD and downloaded with this exact hash, then uploaded to SDRAM and reset.
No new firmware change belongs to this frame-time round.

The unchanged browse10-nav baseline measures 51.3 FPS, p50 19/p99 34 ms,
GIF frame501/tick599/drop100, zero audio underruns and producer overruns.
Idle display rate does not establish navigation frame time or GIF timeline
delivery. Standard PERF_DRAW includes frame start, background pumping and
framebuffer wait; it is not isolated rendering CPU time.

An existing PHOS_PERF_DETAIL build, ROM763538bc4fcecf4b7e7c4ec70993c421e4f14cdb2d9e2106280211d4e9202450,
has independently verified packed ELF loadable bytes and equivalent runtime
source. Its valid browse10 capture measures 51.0 FPS, p50 19/p99 30 ms,
GIF498/tick599/drop101 with zero audio/producer faults. Per-call averages are
GIF unpack7126 us (498 calls, max7859), GIF stage1278 us (511, max5670),
sound_poll3525 us (510, max7402), browser_scan1057 us (510, max6768), and
view_draw1572 us (510, max3689). Scopes have different call counts and nesting;
do not add these averages as a disjoint frame breakdown. Sound polling needs
narrower attribution before assigning its whole cost to optional prefetch.

Evidence is E:/phosphor-boot-round3/hardware/fps-detail-browse10-v2.log.
The first fps-detail-browse10.log used incorrect positional arguments and
selected a fallback rectangle theme; its --theme benchmark row is invalid and
excluded. Corrected capture restores Final Fight. Profiler builds are temporary
and never replace the clean production SD image.

The immutable installed PDSB asset is 30711105 bytes, SHA256
aca12fcc49b4e9bc92cdcb8668dd1074e91d9b0bebc100ecfd42499f7d0e62b0,
with1717 320x240 CI8 frames. The following candidates are under qualification:

| Candidate | Evidence and current status |
| --- | --- |
| Direct PDSB record transfer across a 1 MiB stream boundary | Only29/1717 records cross; max record24703 bytes. Parent actual-owner and precise-negative reruns pass, including final-ticket publication and modeled plane-age guards. Matched clean ROM hardware ABAB is running; no gain claimed. |
| Complete-input private LZ4 playback decoder | Parent independently repeats all1717 actual records against bounded reference and assembled stock/candidate MIPS code, with exact decoded bytes. Dynamic instruction count falls9.19%; this is not cycle/performance evidence. Caller readiness, private symbol integration and hardware comparison remain pending. |
| Next-song prefetch/frame scheduling | Source review ongoing; no candidate retained. Current mixer/RSP ordering, source completion and audio refill priority remain protected. |

All generated proofs and matched artifacts remain under E:/phosphor-boot-round3.
