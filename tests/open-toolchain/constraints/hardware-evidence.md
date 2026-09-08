# Board documents and external SDRAM timing evidence

Checked 2026-09-06 against the original SC64 v2.20.2 source. The
[SummerCart site](https://summercart64.dev/) links the
[interactive board BOM](https://summercart64.dev/sc64v2_bom.html) and
[build guide](https://github.com/Polprzewodnikowy/SummerCart64/blob/18041e25472075a166292d1195603bcefe9c9688/docs/06_build_guide.md).
The latter locates the KiCad board/schematic and identifies the release extra
archive as the manufacturing-file distribution. These are useful physical
requirements, not an FPGA bit-encoding specification.

## Exact parts, rather than inherited symbol names

`hw/pcb/sc64v2.kicad_sch` declares the FPGA as
`LCMXO2-7000HC-6TG144x` and SDRAM as `IS42S16320F-7TL`.
The SDRAM instance inherits a `Memory_RAM:MT48LC16M16A2TG` library symbol and
still carries a Micron 256 Mb datasheet URL. That inherited URL is not evidence
for the actual ISSI part's timings. This audit does not identify the markings
on a particular physical cart or change the schematic.

## Manufacturer timing cross-check

The ISSI family datasheet, revision B dated 2015-11-13, printed page 17,
contains the relevant **-7** column. A
[distributor-hosted copy of the manufacturer's PDF](https://www.integrated-circuit.com/pdf/531/980/1.pdf)
retains that table; the distributor's cover names a -6BL ordering code, so the
family table's -7 column is the evidence used here.

| SDRAM specification | -7 value | Original SC64 LPF value |
| --- | ---: | --- |
| Clock-to-data maximum | 5.4 ns | `INPUT_DELAY 5.400000 ns` |
| Output data hold minimum | 2.5 ns | `HOLD -2.500000 ns` |
| Input data/address/command setup | 1.5 ns | `OUTPUT_DELAY 1.500000 ns` |
| Input data/address/command hold | 0.8 ns | `MIN 0.800000 ns` |

These magnitudes agree with `fw/project/lcmxo2/sc64.lpf` lines 259-261.
The datasheet values depend on its stated loading, reference voltage and edge
conditions. Numerical agreement does not characterize board trace skew or
prove the loaded FPGA meets setup and hold. The negative LPF hold value must
retain its language-specific meaning; this table is not an SDC translation.

## What this resolves and what remains

The external SDRAM requirements have direct component-document support. They
must survive the open-toolchain handoff, including the LPF's quarter-cycle
clock offset and its explicit `sdram_clk` output reference. The
[external timing plan](external-sta.md) and [synthetic fixtures](sta/README.md)
cover that boundary's remaining work.

Board schematics cannot supply undocumented tile encodings or missing internal
FIFO/EFB/ODDR timing arcs. Those require the separate mapped-reference and
database investigations. No constraint is relaxed and no hardware operation
is performed by this document check.
