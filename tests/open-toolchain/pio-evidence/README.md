# PIO mode/pull decoder counterexample

Research-only interpretation test. It neither modifies the database nor emits
a bitstream. Existing configuration and hardware qualification barriers remain
unchanged. A passing fixture means the decoder defect is reproduced, not that
the existing decoder or a proposed replacement is correct for hardware.

## Reproduction

Run from the PhosphorOS root, using fresh output directories:

```powershell
docker run --rm -v "${PWD}:/repo" sc64-open:7000 /usr/bin/python3 -B /repo/vendor/sc64/tests/open-toolchain/pio-evidence/test.py /repo/build/sc64-pio-evidence/baseline
docker run --rm -v "${PWD}:/repo" sc64-open:7000 /usr/bin/python3 -B /repo/vendor/sc64/tests/open-toolchain/pio-evidence/test.py /repo/build/sc64-pio-evidence/diagnostic --pullmask-diagnostic
```

The baseline creates fresh `LCMXO2-7000HC` configuration through the existing
encoder, independently setting `BIDIR_LVCMOS33` and each of `DOWN`, `NONE`,
`UP`. It covers PIO A/B in `PIC_B0`, `PIC_T0`, `PIC_L2`, `PIC_L2_VREF4`,
and `PIC_R1`: 30 cases. All 10 DOWN cases decode to the same encoded pattern;
all 20 NONE/UP cases decode to a different pattern. Unexpected results fail.
`results.json` records selected names and per-file database hashes.

The optional diagnostic removes bits owned by any PIO PULLMODE field from
BASE_TYPE match scoring in memory, then lists every best matching candidate.
All 30 cases must yield only exact encoded aliases of the requested pattern.
This is a bounded diagnostic proposal, **not a generic decoder fix**. Equal
bit patterns do not establish electrically interchangeable standards: bank
voltage and other settings still matter. No reference bits enter these tests.

Verified outputs are in `build/sc64-pio-evidence/baseline-final/results.json`
and `diagnostic-final/results.json`. Both gates pass; the baseline still has
the expected 20 decoding errors. Earlier `fixture-first`/`fixture-second`
attempts fail on Python binding invocation and are not passing tests.

## Why this happens

Pinned Trellis is `3afe7b52b30f4b4417ee98f03016767a502006e3`, with database
`015e0330630d7c238c0e4f2cdd9c8157eb78c54a`.
[`EnumSettingBits::get_value`](https://github.com/YosysHQ/prjtrellis/blob/3afe7b52b30f4b4417ee98f03016767a502006e3/libtrellis/src/BitDatabase.cpp)
accepts matching partial patterns and selects the one with most specified
bits. Independent pull bits can therefore make an unrelated mode win.
For example, the pinned `MachXO2/tiledata/PIC_B0/bits.db` contains:

```text
PIOA.BASE_TYPE BIDIR_LVCMOS33: F0B6 F4B38
PIOA.BASE_TYPE OUTPUT_LVCMOS33: F0B6
PIOA.BASE_TYPE OUTPUT_MIPI: F0B6 F4B24 F5B24
PIOA.PULLMODE NONE: !F4B16 F4B24
PIOB.PULLMODE NONE: !F5B16 F5B24
```

Setting both pulls to NONE allows the three-bit output pattern to outrank
the two-bit bidirectional pattern; its receiver bit remains uncovered.
This explains a decoder ambiguity without establishing a new fuse encoding.

The source [051-pio_attrs fuzzer](https://github.com/YosysHQ/prjtrellis/blob/3afe7b52b30f4b4417ee98f03016767a502006e3/fuzzers/machxo2/051-pio_attrs/fuzzer.py)
sets PULLMODE=DOWN while fuzzing most base types, but omits that override for
MIPI and names ending in D. Different pull defaults are a plausible source
of the overlap; that causal explanation is an inference. Top/bottom fixtures
target 7000HC FPBGA484; left/right target 1200HC TQFP144. The
[069-copy_pio_data fuzzer](https://github.com/YosysHQ/prjtrellis/blob/3afe7b52b30f4b4417ee98f03016767a502006e3/fuzzers/machxo2/069-copy_pio_data/fuzzer.py)
copies left/right definitions to the variants involved here. These are not
independent vendor-generated 7000HC TQFP144 controls for every tested site.

The official [MachXO2 sysIO guide, FPGA-TN-02158-2.4](https://www.latticesemi.com/view_document?document_id=39083)
section 9.1.4 describes pull selection independently per I/O, with DOWN the
default for LVCMOS/LVTTL/PCI and NONE for other standards. Section 9.1.13
requires bank VCCIO to select valid I/O types and drive strengths. These
documented defaults support investigating field overlap; they do not provide
the missing fuse truth table.

## Exact reference and physical pins

The [reference audit](../unknown-bits-audit.md) identifies 53 uncovered bits
that occur in PIO.BASE_TYPE definitions. Their decoded configuration hash is
`ccd8afe3cad9cb4df5acb963d9b17e8336c9bb6f54dc2440c136a96e4a9bca69`.
Source and LPF are official release commit
`18041e25472075a166292d1195603bcefe9c9688`, `fw/rtl/top.sv` and
`fw/project/lcmxo2/sc64.lpf`.

All 53 map to bonded TQFP144 pins in the exact 7000 `iodb.json`:

| Group | Pins/records | Source evidence |
| --- | ---: | --- |
| N64 PI AD | 16 | top-level inout and LPF LOCATE/IOBUF |
| SDRAM DQ | 16 | top-level inout and LPF LOCATE/IOBUF |
| USB MIOSI | 8 | top-level inout and LPF LOCATE/IOBUF |
| Flash DQ | 4 | top-level inout and LPF LOCATE/IOBUF |
| SD CMD/DAT | 5 | top-level inout and LPF LOCATE/IOBUF |
| N64 CIC DQ / SI DQ | 2 | top-level inout and LPF LOCATE/IOBUF |
| Dedicated I2C SDA/SCL | 2 | package pins 125/126, board nets I2C_SDA/I2C_SCL |

All 51 top-level ports request LVCMOS33; their full BIDIR_LVCMOS33 database
patterns match the reference. The longest-pattern decoder instead selects
OUTPUT_MIPI (26 ports) or OUTPUT_SSTL25_I (25 ports). This is not an exact-pattern alias.
The remaining two pins have no top-level LOCATE: pins 125/126 are bank 0
PT22D/SDA and PT22C/SCL, consistent with the enabled dedicated I2C port.
That correspondence does not independently prove what each unknown fuse does.

Bank counts are 0:11, 1:16, 2:16, 3:2, 4:8. The original LPF specifies all
six banks at 3.3 V. Physical net inspection uses
`hw/pcb/sc64v2.kicad_pcb`, selecting the footprint by its
`LCMXO2-7000HC-6TG144x` device value rather than assuming reference numbering
matches the schematic: pins 44/45 are N64_AD11/N64_AD4; 125/126 are
I2C_SDA/I2C_SCL. No SDRAM timing is inferred from a symbol's datasheet link.
Detailed read-only records and extraction are in ignored
`build/sc64-pio-evidence/{inspect.py,inventory.json,board.py,board.json}`.

## Next safe implementation boundary

Where source LPF and port direction are known, report the decoded mode as
ambiguous when its complete bit pattern differs from the requested source
pattern even though the source pattern also matches. Preserve the original
bits and list candidates; do not silently substitute an electrical mode.
The optional test demonstrates one narrow way to produce candidates.

A database/encoder correction needs controlled vendor-generated exact-device
fixtures spanning input/output/bidirectional direction, legal standards,
pull modes, and sites, plus unchanged-bit comparisons. This pass establishes
a synthetic counterexample and reference/source consistency, not that wider
matrix. It removes no hardware, timing, or bitstream qualification gate.

## Source-aware physical-pattern gate

`check.py` reuses `constraints/audit.py` for the original LPF and ANSI top
declarations. Its explicit supported set is the 51 inouts above. A changed
direction, extra inout, unsupported standard/pull, invalid source inventory,
or nonunique pad mapping fails. Package mapping resolves each LOCATE to a
physical tile and PIO using the exact 7000 TQFP144 database. It checks every
positive/negative bit in the existing `BIDIR_LVCMOS33` pattern and the
independent requested PULLMODE pattern. Every output row includes mismatches,
matched candidates, identical encoded aliases and the greedy decoded name.
The standard remains reported as ambiguous; no electrical identity is guessed.

The gate intentionally excludes other pads, dedicated I2C, routing, drive,
slew, and timing. A zero exit status means this narrow source-pattern check
passes. `hardware_qualified` remains false. The identified BIT is the
reference wrapper produced by [release roundtrip tooling](../release/README.md),
not a source-generated implementation.

```powershell
docker run --rm -v "${PWD}:/repo" sc64-open:7000 /usr/bin/python3 -B /repo/vendor/sc64/tests/open-toolchain/pio-evidence/check.py /repo/build/sc64-open-release-agent/durable-roundtrip-final/identified.bit /repo/build/sc64-open-release/source/fw/project/lcmxo2/sc64.lpf /repo/build/sc64-open-release/source/fw/rtl/top.sv /repo/build/sc64-pio-evidence/source-check.json
docker run --rm -v "${PWD}:/repo" sc64-open:7000 /usr/bin/python3 -B /repo/vendor/sc64/tests/open-toolchain/pio-evidence/test.py /repo/build/sc64-pio-evidence/source-fixtures --source-reference /repo/build/sc64-open-release-agent/durable-roundtrip-final/identified.bit /repo/build/sc64-open-release/source/fw/project/lcmxo2/sc64.lpf /repo/build/sc64-open-release/source/fw/rtl/top.sv
```

The extended fixture first checks the unchanged reference. It then flips
each checked receiver/base and pull bit separately in memory, requires a
failed gate, and restores the bit. A separate source mutation changes
flash DQ from inout to output and must fail the supported-direction check.
Mutations never produce bitstream files or change the reference input.
The verified `source-aware-final/results.json` records 51 positive ports,
204 rejected bit mutations, and the rejected direction mutation. The standalone
CLI also passes in `source-aware-check.json`. The initial `source-aware` run
rejects Trellis's canonical device name before any fixture completes; the
checker explicitly accepts its `LCMXO2-7000` name and `LCMXO2-7000HC` alias.

Parent review separates the checker from its fixture driver. The independent
rerun after that change passes all 51 ports, 204 bit mutations and the direction
mutation in `build/sc64-pio-evidence/parent-source-final/`. The original
30-case counterexample fixture passes in the same invocation.
