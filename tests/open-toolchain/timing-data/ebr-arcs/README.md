# Active 7000 RAM timing-pin coverage

This read-only audit joins the public mapped reference's exported Verilog
wrapper, hard primitive parameters/connections, specify statements and SDF.
It does not import timing, qualify hardware, or equate an SDF pin name with a
physical pin by spelling. Source provenance, NCD identity, reporter commands
and hashes are in [active-7000-evidence.md](../active-7000-evidence.md).
The unmodified Diamond reporter identifies LCMXO2-7000HC, TQFP144, grade 6.
Only source scripts are distributed here; vendor exports remain local.

```sh
python3 -B test.py /path/to/build/sc64-active-7000-evidence
python3 -B audit.py --netlist /path/to/active7000.v \
  --grade6 /path/to/active7000.sdf --minimum /path/to/active7000-min.sdf \
  --inventory-unmatched --output /ignored/output/ebr-arcs.json
```

Both corner inventories pass, with 26 RAM wrappers, 128 IOPATH statements,
830 SETUPHOLD statements and 104 WIDTH statements **per export**. Twenty
negative tests check exact rejection reasons. Default operation without
`--inventory-unmatched` deliberately rejects this reference: two PDP wrappers
have an unresolved RSTA check. The opt-in flag records those two specific
orphans; arbitrary unmatched pins still fail. An inventory pass is not timing
qualification.

The output must be fresh and outside `tests/`; exclusive creation prevents
overwriting an existing report. Its top-level `hardware_qualified` is always
false. Numeric fields must each contain three signed integers, including
values without a colon or consisting only of a minus sign in rejection tests.

| Primitive | Instances | Observed configuration |
|---|---:|---|
| DP8KC | 16 | Width 2 on both ports, NOREG, NORMAL, SYNC reset |
| DP8KC | 8 | Width 9 on both ports, NOREG, NORMAL, SYNC reset |
| PDPW8KC | 2 | Width 18 read/write, NOREG, SYNC reset |

The script rejects unknown width/register/write/reset modes, missing or
duplicate RAM wrappers/cells, unmatched instance paths, changed timescale,
unsupported check forms and SDF/specify coverage differences. It preserves
all signed triples and records wrapper-to-primitive connections, including
explicit reset inversion. It is a bounded exporter-dialect audit, not a
general Verilog/SDF parser. Initialization values are not exported into the
report. Physical site/NCL joins remain separate evidence from this logical
pin audit.

## Concrete association findings

The first DP wrapper's SDF `CLKB -> DOB0` maps directly to primitive CLKB and
DOB0. Its RSTA/RSTB inputs instead pass through explicit inverters. Exported
setup/hold checks are at the wrapper boundary, so blindly applying their
signed values to an uninverted primitive reset is unjustified.

The PDP wrapper exposes DP-style names while instantiating PDPW8KC:

- CLKA/CLKB become CLKW/CLKR.
- DIA0..8 become DI0..8; DIB0..4 become DI9..13.
- DOB0..4 become DO0..4; DOA0..8 become DO9..17.
- ADA4..12 become ADW0..8; ADB4..12 become ADR4..12.
- RSTB passes through an inverter into the only primitive RST input.
- **RSTA has a SETUPHOLD check on CLKA in both SDF and specify, but has no
  primitive connection.** Both PDP instances contain this orphan. It must
  not be guessed to mean RST, discarded silently, or treated as a verified
  primitive timing arc. Its vendor-export rationale remains unresolved.

This is a concrete obstacle to feeding these wrapper arcs into an importer
which assumes cell/port names already describe primitives. The existing
[SPD probe](../probe.py) deliberately does not assign numeric pin/event IDs
or fully decode corners; this audit adds no such assignment.

## Corner scope

Both exported modes have identical logical coverage, but different numerical
values. For the first DP wrapper, CLKB-to-DOB0 is 4248 ps in grade 6 and
1622 ps under `-min`; DIA0 setup/hold is -40/85 versus 2/51 ps. These are
wrapper oracle observations, not a transform formula for SPD slots.
The earlier selected SLICE grade-6 match and minimum mismatch remain bounded
as documented in [the schema probe](../README.md). This reference additionally
has a 319:342:366 ps first-SLICE CLK-Q range rather than another reference's
320:343:367 ps; no universal envelope or scalar is established.

There are no active FIFO8KB, ODDRXE or EFB timing instances here. Other RAM
widths, output registers, write-through modes, asynchronous reset, unused
ports and distinct operating grades/corners remain uncovered. A successful
26-wrapper join cannot qualify those missing modes or 100 MHz board timing.

Local output: `build/sc64-active-7000-evidence/ebr-arcs.json`. No production
RTL, timing database, tool installation, license or cart state changes.

Parent review strengthens numeric-field rejection and output guards. The parent
rerun passes both inventories and all 20 rejection checks, then independently
joins the parent-exported grade-6 Verilog/SDF with the minimum export. Counts
and the two unresolved PDP pins agree. Evidence is
`build/sc64-active-7000-evidence/parent-ebr-arcs.json`.
