# Why the LZW-only analytical placement stalls

The source investigation explains the [bounded route timeout](route.md).
The subsequent bounded localization probe changes only the search-budget
divisor. It changes no legality rules, netlist, timing constraints or hardware.

## The 13,910,175 message is a cap, not progress

The pinned source in `sc64-open:diagnostic-lpf` is nextpnr commit
`8dbcee5c3c4415770b6fd06d5ccb2db89545b8ec`. In
`common/place/placer_heap.cc:2176-2182`, the constructor computes:

```text
divisor = setting("placerHeap/cellPlacementTimeout", 8)
cap = max(10000, total_context_cells * total_context_cells / divisor)
```

A nonpositive divisor disables the cap. The candidate's packed JSON contains
**10,549 total cells**, so `10549 * 10549 // 8 = 13,910,175` exactly. The
8,390 cells reported as initially placed by the analytic solver are a
different count; clustered/fixed cells do not all become independent solver
objects. The message is not evidence that any particular cell has already
failed thirteen million attempts, nor an error specific to diagnostic FIFO,
EFB or ODDR support.

The command-line `--placer-heap-cell-placement-timeout` value is passed to
that setting by `common/kernel/command.cc:513-515`. Its value is a **divisor**,
not an attempt count or seconds. For this candidate, 10,000 yields an 11,128
cap; 100,000 reaches the 10,000 floor. Zero removes the cap. This distinction
matters when constructing a bounded diagnostic rather than accidentally
extending an effectively unbounded search.

The actual strict-legalizer error at `placer_heap.cc:1179-1184` names the
cell/type after its counter exceeds the cap. Counter increments occur at
line 1256. The frozen timeout log contains no such error or cell name.

## What the last log does and does not localize

Each main iteration performs connectivity solving, spreading, and strict
legalization before printing its iteration summary (`placer_heap.cc:260-307`).
The timed run stops after the initial four analytic iterations and entry to
the main loop. Its last line therefore does **not** prove that the process
was inside the per-cell legalization loop; solver or spreader time is also
possible. No stack trace or per-stage instrumentation was collected here.

The existing 120-second process limit correctly prevented an indefinite wait.
Raising wall-clock time alone would not explain the cause. A lower attempt
cap can provide a named-cell failure **if** legalization is the slow stage;
absence of that error would motivate a debugger stack sample or narrow
phase-duration instrumentation in a separate tool derivative.

## Actual resource and legality pressure

The candidate pack and nextpnr device inventory report:

| Resource | Used | Available |
|---|---:|---:|
| TRELLIS_COMB | 6,630 | 6,864 |
| TRELLIS_FF | 3,765 | 6,864 |
| DP8KC, including four marked FIFO sites | 25 | 26 |
| TRELLIS_RAMW | 24 | 858 |
| TRELLIS_IO | 101 | 336 |
| EFB | 1 | 1 |

These are chip-wide capacities; the TG144 package and explicit LPF still
restrict usable IO locations. The log confirms 104 constraint-placed cells.
Only 234 combinational BELs remain numerically free. Of the 6,630 COMBs,
96 have mode DPRAM and 48 mode RAMW_BLOCK; the remaining 6,486 have no
explicit special mode. The RAMW-block cost is already in the total and must
not be subtracted again to manufacture spare capacity.

`machxo2/arch_place.cc:35-174` implements real joint restrictions:

- Distributed RAM is limited to the bottom two slices of a logic tile.
- RAMW in slice C excludes ordinary COMBs there and prevents FFs there when
  distributed RAM is present.
- Two FFs sharing a slice must agree on CE net/polarity/constant handling and
  global-reset enable.
- FFs in a tile share clock/reset nets, polarity and asynchronous-reset mode.
  Co-located distributed RAM introduces additional clock/reset polarity rules.
- Wide muxes, M-input use and carry pairing have placement restrictions even
  when the global resource counts fit.

A simple packed-netlist inventory finds 123 distinct clock/LSR/net-and-mux
signatures and 265 CE/net/mux/GSR signatures among the FFs. This is evidence
of heterogeneous control sets, not a complete tile-packing proof: the grouping
does not encode every backend flag, cluster or available-site constraint.
It does explain why 54% global FF utilization cannot guarantee easy packing
beside 96% COMB utilization.

`isBelLocationValid` at `arch_place.cc:184-191` invokes this compatibility
logic for COMB/FF/RAMW and otherwise returns true. Thus the observed timeout
does not currently implicate a special FIFO/EFB legality predicate. Hard
blocks can still affect fixed placement, cluster geometry, connectivity and
routing; their diagnostic status remains unqualified.

## Narrow next tests, without relaxing legality

1. Keep the same netlist, device, pins, 100 MHz request and diagnostic flags;
   lower the effective per-cell attempt cap using the divisor semantics.
   Preserve the 120-second wall limit and treat named-cell failure or timeout
   as a failure, not successful placement.
2. If a cell is named, inspect its cluster, control set and candidate BELs
   against the exact compatibility predicates. Demonstrate an incorrect rule
   or missing legal site before changing backend legality.
3. If no cell failure appears, collect one bounded process stack sample or
   phase timer around solve/spread/legalize to identify the expensive stage.
   This is a diagnostic tool change, not an optimization or hardware result.
4. A resource-reduced source variant must retain a matched functional test;
   reducing state or removing reset/clock restrictions merely to place would
   invalidate the contract. Other placement heuristics remain independent
   experiments and must not silently replace this baseline.

## Executed failure localization

`placement_probe.py` applies test 1 to the exact hash-checked physical input,
LPF and executable. Its only new argument is
`--placer-heap-cell-placement-timeout 100000`, resulting in the 10,000-attempt
floor. The device, explicit 100 MHz request and three diagnostic flags remain
identical; the wall-clock limit remains 120 seconds. It propagates nonzero
tool failure and records inputs, command and diagnostic in JSON.

```sh
python3 -B placement_probe.py \
  --executable /repo/build/sc64-open-timing-options/nextpnr-machxo2 \
  --physical /repo/build/sc64-area-map/lzw/soft-carry/physical.json \
  --lpf /repo/build/sc64-open-memory/parent-full/pins-only-diagnostic.lpf \
  --output /repo/build/sc64-area-route/FRESH_LOCALIZATION
```

Run in `sc64-open:diagnostic-lpf`. The actual tool returns **125**, reporting:

```text
Unable to find legal placement for cell 'mcu_top_inst.mem_write_TRELLIS_FF_Q'
of type 'TRELLIS_FF' after 10001 attempts
```

The full result is `build/sc64-area-route/localize/result.json`; no route,
frequency estimate or output netlist is produced. This concretely localizes
the first failure under the stricter budget. It does not prove this was the
same stuck cell throughout the earlier default-budget timeout or that a
longer/different legal placement search could not succeed.

The offending packed cell belongs to the stock MCU, not a new hard-block
diagnostic. It uses global clock net 46982, LSR net 18937, `CEMUX=1`,
`GSR=DISABLED`, `LSRMUX=LSR`, `CLKMUX=CLK`, and `SRMODE=LSR_OVER_CE`.
Only one FF shares its complete clock/LSR/CE-and-mux signature in the pack.
The JSON has no explicit BEL/cluster attribute on that cell. This is a
specific control-set packing lead, not evidence that the register may be
removed, reset weakened or device compatibility checks bypassed.

The next useful comparison is a functionally checked compact integration
with the same constraints, or inspection of candidate sites/control groups
for this FF. No such follow-up is claimed by this report.

Source-file SHA256 values inspected inside the tool image:

- `common/place/placer_heap.cc`:
  `a4e839805c917e3925fac6b0eafca50723d16436038c9c2bc039dbad725a17f9`
- `machxo2/arch_place.cc`:
  `27887e6381965bbdf719fd5019646e080b01a5dc8daef30e644df18721eb5b1b`

The executable and physical/LPF hashes remain in the route report. No
completed placement, timing closure, functional proof or hardware safety
claim is added by this source analysis.
