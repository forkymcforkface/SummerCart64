# SC64 open-toolchain and original-GIF gaps

Updated: 2026-09-06. This is the maintained gap index for a license-free SC64
FPGA build and original OS4 GIF playback. The [testing log](ui-testing.md)
owns individual experiments and measurements; linked subsystem reports own
reproduction details. Update this index whenever evidence changes a gap's
status, next test or upstream destination.

The current accelerator is **not hardware-qualified**. Open-toolchain diagnostic
packing fits its aggregate resources, but placement remains unresolved.
Configuration and external timing gaps still block an open-built cart image.
Separate Diamond qualification is testing the complete source with original
constraints; candidates now map and route, but the best reaches only
86.790 MHz against the required 100 MHz after simplifying the decoder's
code mask. On the user's request, timing experiments are paused in favor of
the [broader practical improvement review](ui-testing.md#practical-sc64-and-phosphoros-review--2026-09-06).
No experimental FPGA image is flashed.
Functional equivalence is acceptable; byte-for-byte identity to the release is
not a requirement. No upstream pushes are authorized yet.

Playback requirement: retain only the original GIF on SD. Decode incrementally
on the FPGA and stream frame output to the N64 for rendering. Compressed-input,
dictionary and decoded-output buffers are temporary bounded RAM reused during
playback; do not persist a converted GIF/GIF64 file or build a whole-animation
decoded cache. PC-generated fixtures are verification artifacts only.

## Status vocabulary

- **Verified locally:** the specifically stated fixture or correction passes;
  this does not qualify the complete device or make a patch merged upstream.
- **Partial:** useful implementation/evidence exists, with explicit missing gates.
- **Open:** the required capability or evidence is still missing.
- **Testing:** an experiment is running; it is not an accepted improvement.

Upstream destinations below identify who owns a possible fix, not a promise
that maintainers will accept it. Toolchain support does not establish a defect
in SC64's working Diamond-built firmware or a measured firmware speedup.

## Build and hardware-support gaps

| ID / gap | Status and evidence | Owner / benefit | Next closure test |
| --- | --- | --- | --- |
| G01: exact 7000 device absent from tested prebuilt package | **Verified locally:** rebuilding the database accepts `LCMXO2-7000HC-6TG144C`; a simple logic fixture routes. [Probe](../../tests/open-toolchain/README.md) | Toolchain packaging; lets the tools target SC64's actual part | Preserve exact device/package/speed-grade selection in a reproducible build; full SC64 qualification stays separate |
| G02: SystemVerilog and primitive elaboration | **Partial:** source-manifest conversion preserves the real wrappers; declarations allow elaboration but do not implement hard cells. [Frontend](../../tests/open-toolchain/frontend/README.md) | Frontend/build integration; accepts original SC64 sources | Continue port, parameter, initialization and source-hash checks through final netlist |
| G03: FIFO flag routing edges reversed | **Verified locally:** correcting eight fixed graph edges and four fuzzer labels gives all 104 flag outputs outgoing connections; the exact FIFO fixture routes. [Evidence/patches](../../tests/open-toolchain/fifo/README.md) | Project Trellis/database; makes Full/Empty flag routing possible | Independent physical/reference confirmation and upstream review; no timing claim from graph correction |
| G04: FIFO8KB backend support | **Partial:** exact SC64 mode packs/routes and passes bitstream roundtrip plus negative guards. Physical aliases/data splitting and timing need independent validation. [FIFO](../../tests/open-toolchain/fifo/README.md) | nextpnr/Trellis; preserves hardware FIFOs instead of expanding them into logic | Verify physical mapping against a reference and supply characterized timing arcs |
| G05: ODDRXE output support | **Partial:** original SDRAM clock topology and existing configuration fields survive diagnostic route/roundtrip. [ODDR](../../tests/open-toolchain/oddr/README.md) | nextpnr; represents the actual DDR output register | Qualify clock-to-output/setup/hold, reset, phase and board-level SDRAM timing |
| G06: EFB and UFM support | **Open configuration, partial routing:** minimal routing works, but the unchanged wrapper's constant-ground connection to a dedicated input fails routing; research integration uses unqualified inactive-input handling. Configuration emission remains rejected. [EFB](../../tests/open-toolchain/efb/README.md), [full route](../../tests/open-toolchain/memory/README.md) | nextpnr/Trellis; implements embedded block/internal flash access | Validate dedicated inactive-input handling and full stock integration routing; establish EFB/UFM fields and initialization boundaries; qualify timing and active access behavior |
| G07: lost PLL analog metadata | **Verified local preservation:** original `ICP_CURRENT` and `LPF_RESISTOR` values are copied with provenance; missing/conflicting values fail. [Metadata](../../tests/open-toolchain/oddr/README.md) | Frontend/nextpnr integration; prevents silent replacement by defaults | Integrate preservation into the qualified build and validate the complete clock/phase path |
| G08: LPF electrical/configuration parsing | **Verified scoped parser fixes:** ordered `IOBUF ALLPORTS`, `SDM_PORT` and `I2C_PORT` fixtures pass; unsupported attributes fail. [ALLPORTS](../../tests/open-toolchain/constraints/allports/README.md), [SYSCONFIG](../../tests/open-toolchain/constraints/sysconfig/README.md) | nextpnr; honors more of SC64's original constraints and exposes unsupported ones | Review parser patches upstream; retain bank/site/configuration checks and do not equate parsing with timing support |
| G09: external timing and exceptions | **Open:** original SDRAM delays, forwarded-clock phase, min/max checks and path exceptions are not fully implemented/qualified. [Inventory](../../tests/open-toolchain/constraints/README.md), [integration audit](../../tests/open-toolchain/integration-audit.md) | Timing backend/tool integration; checks real board requirements | Resolve every original constraint to verified semantics and use characterized MachXO2 delays; synthetic STA tests are insufficient |
| G10: exact RAM inference | **Partial:** a diagnostic transform addresses Yosys's mapping limitation, preserving ordered writes, old-data collisions and read-enable holds in focused proofs; four memories infer into EBR rather than massive FF arrays. No production RTL changes. [RAM](../../tests/open-toolchain/memory/README.md) | Yosys mapping; a portable SC64 RTL workaround is an alternative requiring separate acceptance | Preserve full initialization/wiring and qualify physical/timing/cart behavior; do not use `-no-rw-check` as a substitute |
| G11: soft-carry whole-design equivalence | **Partial:** all 132 ALUs/58 shapes/2,322 output bits pass a combinational mapping proof. Surrounding fabric, startup and the 18-register difference remain unproved. [Proof](../../tests/open-toolchain/area-map/equivalence.md) | Verification/mapping flow; validates the area-saving choice | Establish sequential initialized equivalence and final hard-block boundary correspondence |
| G12: compact accelerator placement | **Open; early reset remap rejected:** 6,546 COMB/3,734 FF/25 EBR packs, but both placers time out. Stricter search names `flashram_done`; a debugger sample confirms strict legalization. Early unmapping reconstructs the same reset and adds six COMB. [Control sets](../../tests/open-toolchain/area-map/control-sets.md), [rejected test](../../tests/open-toolchain/area-map/reset-unmap.md) | Mapping/SC64 RTL only if proven beneficial; reduces placement pressure | Test existing HeAP control-set search support without changing legality; a later-stage remap remains an alternative needing direct next-state proof and scope gates |
| G13: complete configuration encoding | **Open:** reference audit finds 433 uncovered set-bit records: 121 in existing definitions and 312 without same-tile definitions. Their functions are not all attributed. [Audit](../../tests/open-toolchain/unknown-bits-audit.md) | Trellis/device database; supports trustworthy all-source configuration | Resolve relevant device/site fields with independent references; never transplant unknown stock bits into new routing |
| G14: update payload and initialization | **Partial reference reproduction:** release packaging can be reproduced using reference-derived FPGA data; that is not an all-source build. [Release](../../tests/open-toolchain/release/README.md) | SC64 build adapter/tests; uses existing updater safely | Verify open configuration serialization, fuse/frame ordering, CIC/RAM initialization and UFM boundaries against the updater contract |
| G15: open-built stock cart baseline | **Open:** no complete open-built SC64 image has passed all configuration/timing gates and real-cart acceptance. [Acceptance sequence](../../tests/open-toolchain/integration-audit.md) | SC64 integration/verification | Qualify unchanged stock behavior first: boot/CIC, USB, SD, SDRAM, saves, reset and update/recovery |

## Original-GIF integration gaps

| ID / gap | Status and evidence | Owner / benefit | Next closure test |
| --- | --- | --- | --- |
| G16: bounded raw GIF decoder | **Verified simulation/component scope:** compact core passes 1,776 fixtures, cancellation and corruption tests, retaining original Final Fight cycles/traffic. [Decoder](../../tests/gif/compact-lzw/README.md) | Proposed SC64 FPGA feature; accepts original compressed image data | Close G11/G12 and transport/system gates before claiming on-cart decoding |
| G17: production job and memory ownership | **Open:** research DMA/mux/cancellation probes pass, but fixed arenas, pulse status and parameter publication are not a production API. [Raw transport](../../tests/gif/stock-lzw-fit/README.md) | SC64 FPGA/MCU plus N64 client; reliable submission, completion and cancellation | Define owned nonconflicting arenas, validated/atomic job parameters, persistent completion/error state and teardown; test concurrent stock traffic |
| G18: N64 raw-plane composition and presentation | **Open:** the smaller FPGA design outputs indices; N64 integration must preserve palettes, transparency, disposal and original timing. [Split review](../../tests/gif/mcu-split/README.md) | Phosphor RTK/backend; presents original GIFs without PC conversion | Implement through existing owners and prove frame-byte/behavior parity with the original Final Fight theme |
| G19: end-to-end UI performance | **Open:** decoder simulation and resource counts do not measure UI FPS. The earlier contiguous PI read is not a proven hardware throughput floor. [Testing log](ui-testing.md) | Phosphor/SC64 integration; responsive UI with uninterrupted audio | After stock cart qualification, measure original Final Fight using the unchanged hardware harness, with real frame cadence, input and audio checks |
| G20: generic original-GIF compatibility | **Open:** Final Fight exercises a global palette, full-canvas frames and disposal 0/1; that fixture cannot qualify all OS4 GIFs. [GIF scope](../../tests/gif/README.md) | Phosphor decoder/composition plus SC64 feature contract; supports vanilla theme assets beyond one example | Verify local palettes, interlace addressing, image rectangles, transparency/background, disposal 2/3 and timing against actual OS4 behavior; retain Final Fight as the required performance workload |
| G21: complete Diamond accelerator fit | **Paused:** complete mapping/routing reaches 86.790 MHz and fails the original 100 MHz requirement. All 1,717 original frames pass raw transport simulation; installed firmware passes 44 SDRAM patterns. [Fresh ledger](ui-testing.md#gif-timing-closure-follow-up--2026-09-06) | SC64 RTL/mapping; establish a complete original-constraint implementation | Resume only as a separate accelerator project; close timing and G17/G18 before hardware UI comparison. Current priority is the broader practical review. |

## Current experiment and disposition

The SDRAM idle-dispatch bypass is **rejected before flashing**. It saves about
one clock per raw word in simulation, but actual DMA fresh-case totals improve
only 0.807%. Full Diamond implementation reaches 88.191 MHz with 453 setup
violations against the original 100 MHz requirement. The critical path crosses
request selection and the SDRAM row comparison. Production hardware is unchanged;
see the [memory-wait experiment](boot-testing.md#sdram-dispatch-wait-experiment--2026-09-07).
No boot-time gain is established by this failed timing candidate.

The practical SD/USB overlap round uses unchanged SC64 firmware and Final
Fight on the real 4 MiB N64. USB polling deferral is retained as `6a39cafd`
with a modest repeated first-after-boot gain (48.6/48.7 to 50.2/50.5 FPS) and
50 live pings within 70.720 ms. Async SD-to-cart prefetch is rejected: its
49.0/48.8 FPS first-after-boot results do not justify the added command
serialization and lifecycle complexity. Warm ranges overlap the baseline.
See the [complete measurements](ui-testing.md#sdusb-overlap-experiments--2026-09-06).
These results do not close any original-GIF accelerator or FPGA timing gap.

The prior accelerator round prioritized G21 and fresh replay of GIF commits. The full
transport gate is retained in vendor commit `a3108cc`; the normalized stack
passes the complete decoder suite and write-control equivalence, but resource
and timing acceptance remain separate. A narrow two-block CIC packing idea
is rejected because the installed primitive model does not preserve old-data
reads during byte writes. No experimental accelerator is installed on the cart.
Temporary private tooling is outside the tracked repository.

The open-toolchain experiments below retain their historical disposition;
they are not newly completed qualification results.

The latest G12 experiment explicitly selects the synchronous-reset cell driving
`n64_scb.flashram_done` before the normal FF mapping continuation. The final
pack reconstructs its `SD=0`/general data/LSR structure and grows to 6,552 COMB.
Agent and parent reproduce the rejection before placement; parent evidence is
`build/sc64-reset-unmap/parent-final/result.json`. Local induction evidence is
supplemental; a direct extracted-next-state proof remains required before any
future remap is accepted. Parent review adds an unrelated-cell mutation gate
to catch accidental broad selection. No production RTL change is retained.

A second, source-reviewed lead is the existing HeAP
[control-set search hook](../../tests/open-toolchain/area-map/control-set-heuristic.md).
MachXO2 does not configure it. A hook matching the exact tile-wide control
fields could prefer compatible locations while retaining all legality checks.
It is not implemented or measured and is the next placement experiment.

The strongest small tool-upstream review candidates are G03 and the scoped G08
parser fixes. G07's preservation/error checks are also useful, with the final
integration owner to be decided. G04/G05/G06 remain diagnostic support. SC64
upstream candidates are a qualified build/test path and, if needed, separately
accepted portable RTL inference workarounds. The existing RAM limitation is
in the open mapping flow, not a demonstrated SC64 firmware defect. The GIF
accelerator is a separate feature proposal.

## Firmware address-bound validation follow-up (2026-09-08)

Actual-source host testing finds that cfg_translate_address in
sw/controller/src/cfg.c can accept an oversized range after unsigned32-bit
address+length wrap. The fixed BRAM address0x1FFE0000 with SD count0x7fffff
passes the existing count guard but wraps its byte-range endpoint. Current
libcart does not send this request: its DRAM reads are bounded to16sectors.
No malformed legacy transfer is sent to the cart during testing.

This is a separate upstream correctness candidate: use checked addition or
subtraction bounds after validating each mapped start address, with tests for
all aliases, zero lengths, exact endpoints and wraparound. It is not yet fixed
or hardware-qualified here. The private READ_AT experiment independently bounds
its fixed8KiB buffer and intentionally rejects these malformed requests; it
leaves legacy commands unchanged. Source evidence and independent review live
under E:/phosphor-boot-round3/read-at-atomic/legacy-translation-gap.md and
E:/phosphor-boot-round3/gap-review/read-at-final-qualification-review.md.

## Software boot follow-up status (2026-09-08)

The private READ_AT integration is accepted in vendor19c7387/root57ce0a31 after
real-cart protocol/error cases, unchanged-component readback and current-menu
344ms warm boot versus357ms old-firmware fallback. Its default actual-source
MCU gate is vendor7e37906. This does not fix the independent legacy oversized
address translation gap above; no malformed legacy operation is tested on cart.

Current measured follow-ups: sound reload34ms (scan10ms, FX15.5ms, playlist8.5ms),
initial directory opens25ms and systems.dat first load6.5ms. Counters overlap.
Agents investigate narrow improvements with first-input sounds, original data
semantics, error propagation and resource ownership preserved. Config key
formatting (root841682c7) and startup log consolidation (rootff917700) pass
current-stack acceptance; their permanent gates are e71014c4 and0391f0e1.
Lazy directory advance and decoder microchanges
have no convincing reproducible gain so far; they are not production changes.
No FPGA or clock modification belongs to this software round.

Systems-file buffering, parser string copying, within-block cache copy batching,
cart-version caching, path joining, direct cartfs DMA and smaller 1KiB/512B cache
geometry fail their hardware performance comparisons and are excluded. Removing
theme-key hashes fails the existing owner mutation test before hardware.

The virtual wav64 guard change passes isolated sound comparisons. Its first
clean production artifact also contained uncommitted filename copying; that
artifact and the later contaminated controls require the correction documented
in boot-testing.md. The exact-root replacement is independently verified against
its packed ELF and is undergoing hardware checks. Directory name copying still
needs its final uncontaminated comparison. Avoiding the browser build discarded
before theme engagement saves about 5–6 ms in initial tests but requires the
remaining context-aware lifecycle gates and full current-source build matrix.

CFG argument-pair reads are undergoing an MCU-only hardware comparison with
exact original recovery-loader/FPGA/formatter readback. Manager attribution puts
language initialization at about 22.4 ms and game-database initialization at
13.7 ms. A narrower database I/O probe is ready; these measurements are not yet
new optimizations. Native controller initialization has no arbitrary wait that
can be removed while preserving its first-ready-input contract.

The subsequent exact-root artifact correction passes hardware verification.
Uncontaminated filename copying and CFG argument-pair MCU reads fail to show a
repeatable gain and are rejected; accepted ff00d9ed MCU firmware is restored.
Browser deferral is accepted in root e6b69f79 after the full matrix, 39 host
contexts, 42 N64 cases, standard browse10 and repeated theme lifecycle checks.
Warm Final Fight readiness is 335 ms versus matched 339–342 ms controls.
Binary-index unbuffered reads and three CRC slicing-by-four forms remain
hardware trials. Config arena reuse has no narrow safe implementation without
additional I/O, excessive allocation or a new ownership mechanism; it is not a
qualified candidate. See boot-testing.md for the evidence and test boundaries.


## Frame-time follow-up status (2026-09-08)

The PDSB complete-input decoder is accepted in root 89bacff4, with default gate
root ccf570af and documentation root f9dc5119. Clean Final Fight browse10-nav ABBA
improves 51.4/51.4 to 52.3/52.0 FPS; all 42 N64 view cases and audio checks pass.
The final integrated ROM is byte-identical to the qualified candidate,
SHA256 2f38fc013bc18cb92629d28115a40cfa86c2497f0d2b7ef9ba12b03d3e30fe1a.
The existing N64 GIF owner generates a pinned private specialization; stock
SDK/PDS9 behavior remains intact. Actual-record, assembled-MIPS, caller-readiness,
negative-control, cart-build and lint evidence is indexed in ui-testing.md.

Independent sound-prefetch ABBA improves 50.6/50.6 to 53.5/53.9 FPS, p99 35/35 to
35/34 ms, with zero audio faults. It is accepted on main in a8dd082f with gate
75d875d7. Full matrix, combined cart builds/lint, real N64 boot and navigation
pass. Combined browse10 measures 54.2 FPS; a supplemental 893-game SNES navigation
check measures 56.4 FPS, both without audio/producer faults. These are operational
checks, not an additional matched gain claim. SD readback matches the combined
ROM e9ef4991657b737aabe9dfa45f439e6fc8c32fe6f1c2188511eefe09f388a0e0.
Continuous-input natural song advance remains additional coverage to capture;
the root navigation observation does not establish that transition. The PDSB boundary
transfer experiment is rejected after its matched comparison.

The broader frame audit has reviewed manager/main-loop hooks, decoder readiness,
GPU submission/state, text/list reuse and image/sprite ownership; it is not a
completed whole-codebase audit. Pager recording is accepted in main e0e120e8,
with permanent gate 94f28ca6: matched SNES893 runs improve 58.259/58.759 to
59.141/59.394 FPS and p99 31/31 to 30/30 ms. Full matrix, 39 host views with
valid-context closures, 42 N64 views and repeated active-list theme changes pass.
SD readback matches 8b681bdebf71de55481e2c3efd42623b4fac2a9147367754302ebb9768421251.
Two-descriptor glyph rotation is rejected: matched runs give 58.477/58.853 FPS
baseline versus 58.054/58.130 candidate, with no residual render-time gain.
Consecutive identical-glyph reuse is excluded for
low frequency in surveyed labels. An active-viz sound-tap threshold early exit
passes 20,588 modeled ring-state cases but has no N64 timing or ordinary Final
Fight benefit claim. Cache-tail publication is proof-only,
including unresolved qualification of the complete publication contract. These
are separate from already rejected boot micro-optimizations and do not reopen
those experiments. Mixed-atlas source rejection and private LZ4 wide-copy v2
have isolated correctness gates and queued ROMs, but no hardware acceptance.
The naive wide-copy v1 is rejected for increased modeled instruction count.
PDSB next-block lookahead is being qualified separately against the newly
accepted main baseline. See ui-testing.md for exact artifacts and results.
