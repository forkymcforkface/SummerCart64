# Ordered MachXO2 IOBUF ALLPORTS support

This patch changes only nextpnr's MachXO2 LPF electrical-attribute parser. It
applies to pinned nextpnr commit `8dbcee5c3c4415770b6fd06d5ccb2db89545b8ec` and
requires the original `machxo2/lpf.cc` SHA-256
`8f32c0e24d35d448490d2447168a19f55662094067509d1c88362431cfa9dfa7`.
A changed or already-patched parser is rejected before writing.

`IOBUF ALLPORTS` applies attributes to actual frontend top-level port cells,
including vector bits and bidirectional ports. It does not annotate internal
logic. Statements retain their input order: a later named-port statement or
later ALLPORTS statement overwrites only its listed keys. Named singleton
`port[0]` can resolve to a scalar port, matching LOCATE's existing convention.
Well-formed named ports absent from the synthesized design retain the old
parser's no-effect behavior; source-port coverage belongs to the
[constraint audit](../README.md).

Attributes are validated before target lookup, so a malformed constraint does
not disappear when its target was optimized out. Empty keys/values, extra `=`,
unknown attributes, missing attribute lists, and unsupported values fail.
`IO_TYPE` uses the backend's IO type catalog. The other accepted keys are
PULLMODE, DRIVE, SLEWRATE, CLAMP, OPENDRAIN, and HYSTERESIS, with values present
in the pinned MachXO2 PIO database. Existing downstream direction, IO-type,
voltage-bank and site restrictions still apply.

The old parser's BANK, BANK_VCC, VREF, DIFFDRIVE and TERMINATION keys lack a
consumer in this MachXO2 electrical writer; they now fail instead of appearing
to apply. DIFFRESISTOR has a writer branch, but the pinned MachXO2 tile database
contains no corresponding PIO configuration enum, so it also fails explicitly.
This is a deliberate fail-closed restriction, not an implementation of those
features. Do not broaden these keys without configuration evidence.

## Build and reproduce

Inside an isolated container with the parent diagnostic source checkout at
`/src/nextpnr`, database at `/src/prjtrellis/database`, and SC64 at `/sc64`:

```sh
/usr/bin/python3 /sc64/tests/open-toolchain/constraints/allports/apply.py /src/nextpnr
cmake --build /src/nextpnr/build -j2
/usr/bin/python3 /sc64/tests/open-toolchain/constraints/allports/run.py \
    /out/allports --nextpnr /src/nextpnr/build/nextpnr-machxo2 --sc64 /sc64
```

Use a fresh output directory. The patch is independent of the FIFO/ODDR/EFB
patches because they do not change `lpf.cc`. No shared Dockerfile, production
constraint file, firmware, or hardware is changed by these tools.

## Evidence and limits

The `sc64-oddr-agent` isolated container built the actual patched backend and
passed the runner at ignored `build/sc64-open-allports/final`:

The parent independently applies/builds the patch and repeats the complete
runner at `build/sc64-open-allports/parent`, including the electrical bit
roundtrip. Reapplying the patch rejects the changed source as intended.

- Three positive cases verify ALLPORTS defaults, subsequent per-port overrides,
  reverse ordering, quoted values, vector/scalar handling, preservation of
  DRIVE/SLEWRATE, and exclusion of internal cells.
- Thirteen negatives reject malformed statements, invalid values, unsupported
  keys (including one targeting an absent port), and a missing semicolon.
- A five-pin combinational fixture places/routes and survives ecppack/ecpunpack.
  Every requested PIO enum must either return unchanged or have an exactly
  identical bit-token set in the pinned database. The latter is reported,
  not hidden: LVCMOS33 decodes as LVTTL33 and DOWN as FAILSAFE because those
  names alias identical PIO bits. The report hashes the inspected database.
- The complete original SC64 LPF is passed directly, without removing any
  statement. SHA-256 remains
  `eaf0a7b1b45e7047cce5a478116e36cf74b094f20e48359fc7e02efce0efb662`.
  Parsing advances past ALLPORTS and stops at `SYSCONFIG SDM_PORT`, as expected.

The small electrical fixture's generated bitstream is a diagnostic artifact,
not a programming deliverable. LPF parser acceptance is not electrical or
hardware qualification. Existing unsupported/ignored aliases, bank declarations,
BLOCK paths, SDRAM timing groups, setup/hold and output timing, and SYSCONFIG
remain covered by the fail-closed audit. This patch does not implement them.
The runner explicitly reports `full_lpf_qualified: false` and
`hardware_qualified: false`.
