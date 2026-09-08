# External STA handoff from nextpnr

Research checked 2026-09-06. OpenSTA is a plausible existing engine for SDC
input/output delays and path exceptions, potentially avoiding new general timing
analysis machinery in the MachXO2 backend. It is **not** currently a turnkey
replacement for the missing cell timing models. No OpenSTA binary was installed,
built, or executed during this bounded investigation.

## What was actually checked

Neither `sta`, `opensta`, nor `openroad` is on the host PATH or in the
`sc64-open:diagnostic` image. `icebox_stat` is present but is an iCE40 statistics
utility, not a substitute static timing engine.

The pinned nextpnr
[SDF exporter](https://github.com/YosysHQ/nextpnr/blob/8dbcee5c3c4415770b6fd06d5ccb2db89545b8ec/common/kernel/sdf.cc)
emits SDF 3.0 cell IOPATHs, register setup/hold checks, and per-driver-to-user
INTERCONNECT delays. It uses backend timing queries, skips disconnected ports,
and derives typical values by averaging min/max values. Its source explicitly
marks min/max routing delay modeling as unfinished. Clock constraints themselves
are not an SDC export.

A file-only replay of the already routed guarded SC64 design produced a
7,857,263-byte SDF, exit 0, with fresh diagnostic flags and
`--no-pack --no-place --no-route --sdf`. No bitstream output was requested.
Evidence: `build/sc64-external-sta/{routed.sdf,export.log,sdf-counts.json}` in
the parent checkout. This reuses the earlier default-12-MHz placement/routing;
it does not retest a 100-MHz implementation.

The export contains normal FF/logic/RAM arcs, but the EFB, all four FIFO8KB
instances (packed as DP8KC), the ODDR-mapped BIOLOGIC, and the PLL each contain
**zero IOPATH/setup-hold checks**. Aggregate DP8KC counts must not hide the four
empty FIFO instances. Top-level IO timing is not solved by an empty TRELLIS_IO
cell either. An external analyzer cannot reconstruct missing delays from these
empty records.

The parent repeats SDF export from its explicit-100-MHz routed design (which
failed timing), then independently inventories the seven hard-cell instances:
one EFB, four FIFO, one ODDR/BIOLOGIC and one PLL. Each has zero exported
IOPATH/setup/hold/recovery/removal arcs. Evidence:
`build/sc64-open-memory/parent-full/{parent-routed.sdf,parent-sdf-missing-arcs.json,sdf-export.log}`.
The export is 7,857,263 bytes; successful serialization is not a timing pass.

## OpenSTA inputs and version caveat

[OpenSTA's primary repository](https://github.com/parallaxsw/OpenSTA) and the
[OpenROAD-maintained copy](https://github.com/The-OpenROAD-Project/OpenSTA)
describe structural Verilog, Liberty, SDC, and SDF inputs. The documented flow
links the Verilog instances to Liberty cells before annotating SDF. SDF supplies
delays; Liberty still supplies cell connectivity, polarity, sequential behavior,
and timing-arc/check topology. Blackbox declarations alone are insufficient.

The inspected OpenROAD source pin is
`a9a3f30ca97dc13f9ef911cae1a82c42c67379e1`. Its
[command reference](https://github.com/The-OpenROAD-Project/OpenSTA/blob/a9a3f30ca97dc13f9ef911cae1a82c42c67379e1/doc/OpenSTA.fodt)
documents read_sdf, read_sdc, annotation reports, generated clocks, and min/max
path checks. It uses SDF min/max values and ignores typical values. It does not
support SDF PORT statements or INSTANCE wildcards. Pin this implementation and
test it rather than treating every OpenSTA build as interchangeable.

One concrete documentation discrepancy matters: that reference labels generated
clock `-edge_shift` unsupported, whereas the same pin's
[Sdc.tcl](https://github.com/The-OpenROAD-Project/OpenSTA/blob/a9a3f30ca97dc13f9ef911cae1a82c42c67379e1/sdc/Sdc.tcl)
parses floating edge shifts and passes them to generated-clock construction.
The same source accepts signed floating input/output delays. Thus phase and
negative external hold constraints are plausible, but need executable fixtures
against the chosen binary. Do not clamp negative hold requirements to zero.
The [SDF reader](https://github.com/The-OpenROAD-Project/OpenSTA/blob/a9a3f30ca97dc13f9ef911cae1a82c42c67379e1/sdf/SdfReader.cc)
separates SETUPHOLD annotation into setup and hold timing roles; corresponding
Liberty arcs must exist for meaningful analysis.

## Proposed handoff, not a completed flow

1. Export routed JSON and SDF together from the same nextpnr design. Preserve
   instance names, escaped identifiers, ports, directions, parameters, and
   constants. Supply an equivalent structural Verilog representation; resynthesizing
   the original RTL can change names and topology and invalidate annotation.
2. Build a characterized Liberty view of the **packed** MachXO2 cells. Parameter
   variants sharing names such as TRELLIS_COMB or DP8KC require an explicit,
   consistent specialization strategy across netlist and SDF. Encode actual
   FF polarity, CE/reset behavior, RAM clocks, and conditional paths. Do not
   give uncharacterized FIFO/EFB/ODDR cells zero-delay placeholder libraries.
3. Translate the owning LPF constraints to a reviewed SDC file. Preserve each
   source statement and endpoint mapping. Explicitly model input arrivals,
   output setup/hold, asynchronous exceptions, and generated clock relationships.
   Do not blanket-exclude all paths involving EFB or the external SDRAM clock.
4. Annotate existing route delays once. Do not combine annotated net delays
   with a second independently estimated interconnect delay calculation. Check
   annotation coverage and every unmatched cell/pin/arc before reading slack.

The intended Tcl shape is below; the named Liberty, netlist, and SDC artifacts
do **not** exist yet and this block is not a qualified runnable SC64 script:

```tcl
read_liberty machxo2_packed_characterized.lib
read_verilog sc64_routed_structural.v
link_design top
read_sdc sc64_reviewed.sdc
read_sdf sc64_routed.sdf
report_units
check_setup
report_annotated_delay
report_annotated_check
report_checks -path_delay min_max
report_checks -unconstrained
```

For the 270-degree SDRAM clock, preserve PLL phase and the ODDR output clock
relationship, including falling-edge behavior and output delay. Declaring an
unrelated clock with the same frequency can sever the intended relationship;
annotating data arcs does not create the missing clock waveform. Validate
generated-clock edge shifts and propagated-clock treatment with explicit
launch/capture-edge expectations before applying them to the full design.

## Acceptance gates before using an external timing result

The [executable synthetic fixtures](sta/README.md) now exercise the analytical
and rejection cases below with pinned OpenSTA. All 13 fixture cases pass the
parent rerun; their invented cell models do not satisfy the full-chip handoff.

Run small fixtures with analytically known setup and hold slack: signed minimum
output delay, both clock edges, 270-degree phase, nonzero clock insertion, and a
false path that removes exactly one selected path. Deliberately remove a Liberty
arc, misspell an SDF instance, and omit an I/O constraint; each must fail the
wrapper's coverage gate instead of yielding an apparent timing pass. Preserve
separate minimum and maximum delay corners. Current nextpnr routing estimates
still need credible minimum-delay characterization for hold signoff.

External STA can therefore close the **constraint evaluation** gap after a
netlist/Liberty/SDF handoff is validated. It cannot close missing hard-cell arcs,
electrical loading assumptions, configuration equivalence, or FPGA programming
format gaps merely by accepting an SDF file. No backend emission barrier changes.
