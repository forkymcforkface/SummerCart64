# Public 7000HC reference with active block RAM

The [Artekit AK-MACHXO2-7000 manufacturer page](https://www.artekit.eu/products/devboards/ak-machxo2-7000/)
provides a public VGA demo archive containing a routed **LCMXO2-7000HC,
TQFP144, grade-6** Mico32 design with all 26 EBRs active. Unmodified
Diamond 3.13 backannotation succeeds for grade 6 and minimum timing.
This supplies an exact-device active-RAM reference missing from the
[earlier public examples](public-oracles.md).

## Artifact provenance

Download [Forza4Graphical_Slideshow.zip](https://www.artekit.eu/resources/ak-machxo2-7000/Forza4Graphical_Slideshow.zip).
The inspected archive is 26,170,694 bytes, SHA256
`ce7398e4bc639059f6ff565d11cf82f25193ad218379249bd9c0acb766776e6c`.
This hash pins the inspected bytes; the manufacturer's URL itself is
mutable. A normal browser user-agent request succeeds without account
credentials. A default Python request returned HTTP 403; no authenticated
download requirement was bypassed.

The archive's routed design directory is:

```text
Forza 4 Graphical + Slideshow/vga_demo/tftsurfer_demo_v003_versione_EAS_TFTSURFER_demo_OSC_DELL_CLKOP/par_d12/tftsurfer/
```

It contains `tftsurfer_tftsurfer.ncd`, `.prf`, `.jed`, `.bit`, `.bgn`,
`.par`, `.pad` and `.twr`, plus mapped/intermediate NCD variants.
Only the final named NCD is used for the timing exports. The full
member paths, byte counts and individual hashes are retained in ignored
`build/sc64-active-7000-evidence/archives.json`.

The adjacent original BIT hashes to
`d83edb0535aa6877e079548a5b3b4eb45e3ec5fea6b2d2761b5a4d4adc345481`;
the JED hashes to
`f4a36c4d707f549bcd7a363bfcd778fd6a0b190d97088caf4080b82e38221a62`.
The original Diamond 2.2 BGN log explicitly names this NCD/PRF and
`RamCfg:Reset`, and reports pre-loadable EBRs with GSR disabled. This is
useful association evidence, but not a proof that every adjacent file
belongs to the identical build. Independent configuration/initialization
comparison must precede a same-build claim or a database patch.

## Verified exports and coverage

Using the original NCD and PRF, renamed only for convenient local paths,
inside `ghcr.io/polprzewodnikowy/sc64env:v1.10`:

```sh
export FOUNDRY=/usr/local/diamond/3.13/ispfpga
export LD_LIBRARY_PATH=$FOUNDRY/bin/lin64
timeout 30 "$FOUNDRY/bin/lin64/ldbanno" -n verilog -neg -sp 6 \
    -o /tmp/active7000.v -d /tmp/active7000.sdf \
    /tmp/active7000.ncd /tmp/active7000.prf
timeout 30 "$FOUNDRY/bin/lin64/ldbanno" -n verilog -neg -min \
    -o /tmp/active7000-min.v -d /tmp/active7000-min.sdf \
    /tmp/active7000.ncd /tmp/active7000.prf
```

Both commands exit 0; both logs independently identify 7000HC rather
than relying on the archive or project name. The generated Verilog
contains **24 DP8KC and two PDPW8KC primitive instances**. The DP8KC
models use NOREG/NORMAL on both ports: sixteen are width 2 and eight
are width 9. The SDF contains 22 main-memory cells plus four debug-ROM
cells. An extraction check asserts all 26 are present in both exports
and retains their complete pin-specific delay, setup/hold and width
records in `timing-summary.json`.

No literal FIFO8KB, ODDRXE or EFB primitive instance is found in this
export. Thus this artifact supplies RAM evidence; it does not close
those other hard-block timing gaps.

For the first main-memory SDF cell, whose name ends
`p1732326e_1_3_0`, selected reports are:

| Pin relationship | Grade 6, ps | Minimum mode, ps |
|---|---:|---:|
| CLKB to DOB0, both output transitions | 4248 | 1622 |
| DIA0 setup / hold to rising CLKA | -40 / 85 | 2 / 51 |
| ADA3 setup / hold to rising CLKA | -19 / 74 | 4 / 52 |
| ADB3 setup / hold to rising CLKB | -107 / 153 | -22 / 72 |
| CEB setup / hold to rising CLKB | 186 / -23 | 87 / 4 |
| CLKA and CLKB high/low pulse width | 2735 | 1332 |

Each value in this table is a degenerate SDF min:typ:max triple with
three identical entries. The full SDF preserves the original triples.
These are observed configured-cell results, not universally applicable
DP8KC constants. Some outer logical memory cells expose CLKB-to-DOA
paths; their wrapper-to-primitive pin association must be preserved.
No numeric SPD pin-index, transition-slot or minimum-corner mapping is
inferred merely from this export.

There is also a useful grade-6 context counterexample outside RAM: this
export's first SLICE CLK-to-Q range is 319:342:366 ps, whereas the
previously selected public SDR/1200 SLICE cases were 320:343:367 ps.
The voltage and temperature header triples remain 1.26:1.20:1.14 V and
-40:25:85 degrees C. Thus matching five earlier grade-6 envelopes did
not establish a universal direct-envelope rule. Cell mode, transition
and wrapper context must be joined exactly before attributing this
one-picosecond difference or importing timing data.

## Scope and retained evidence

The bounded search checked 28 additional GitHub tree candidates without
repeating the prior 22 repositories, and three manufacturer archives.
The tutorial ZIP contains a nested source tutorial; the Ethernet ZIP
contains a nested demo JED, but no mapped timing artifact. The VGA ZIP
is the concrete active-RAM result. Its unrelated 960,000-byte `.bit`
bitmap images are not FPGA bitstreams and are not treated as such.

Ignored `build/sc64-active-7000-evidence` retains the downloaded archives,
safe flat extraction, per-member provenance, original build reports,
complete grade-6/minimum Verilog and SDF, report logs, and the executable
timing-summary check. No unknown executable from an archive is run.
No vendor data is added beside this report. This work changes no license,
production RTL, database, firmware or hardware, and does not qualify a
new cart image. Follow-up physical-bit comparison remains separate from
this [timing-data investigation](README.md).
