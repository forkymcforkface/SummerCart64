# Database-backed MachXO2 SYSCONFIG parser entries

This patch adds `SDM_PORT` and `I2C_PORT` to nextpnr's MachXO2 LPF parser.
The pinned `machxo2/bitstream.cc` already sends those settings to CFG0 and
CFG1 respectively. The existing Trellis database and encoder supply all bits;
this patch neither introduces configuration bits nor copies reference bits.

The patch layers after [ALLPORTS](../allports/README.md), requiring
`machxo2/lpf.cc` SHA-256
`38da7963795c7e1ad44633c1e302904046dc467c1e4a8a698d91f17cc19ee827`.
Changed input or repeated application fails before writing. All replacement
anchors must be unique before the staged result is written. The underlying
nextpnr revision is `8dbcee5c3c4415770b6fd06d5ccb2db89545b8ec`.

Accepted values match the pinned database:

| Key | Value | Existing database bits |
| --- | --- | --- |
| SDM_PORT | DISABLE, INITN, PROGRAMN | No set bits |
| SDM_PORT | DONE, PROGRAMN_DONE, PROGRAMN_DONE_INITN | CFG0 F5B4 |
| I2C_PORT | DISABLE | No set bits |
| I2C_PORT | ENABLE | CFG1 F5B38 |

The SDM names in each row alias the same database encoding. Accepting them
does not independently validate each named hardware behavior. The stock
SC64 values are `SDM_PORT=DISABLE I2C_PORT=ENABLE`. Optional quoted values
are normalized for these two keys, invalid values fail, and statement order
continues to control overrides. Malformed SYSCONFIG key/value assignments
with an empty side or additional equals sign fail before settings are stored.
Other pre-existing SYSCONFIG key semantics are not broadened or qualified.

## Isolated reproduction

Start a separate container from `sc64-open:diagnostic`, with the SC64 tree
mounted at `/sc64` and a fresh ignored output directory at `/out`. Do not
change another experiment's running container.

```sh
python3 -B /sc64/tests/open-toolchain/constraints/allports/apply.py /src/nextpnr
python3 -B /sc64/tests/open-toolchain/constraints/sysconfig/apply.py /src/nextpnr
cmake --build /src/nextpnr/build -j2
/usr/bin/python3 -B /sc64/tests/open-toolchain/constraints/sysconfig/test.py \
    /out/results --nextpnr /src/nextpnr/build/nextpnr-machxo2 --sc64 /sc64
```

The test requires Yosys, ecppack/ecpunpack, and the installed pytrellis module
at `/usr/local/lib/trellis`. It reuses ALLPORTS's small combinational fixture,
not SC64 firmware. Each output directory must be new and outside `tests/`.

## Verified results and limits

The isolated `sc64-sysconfig-agent` container builds the actual patched
nextpnr backend. Evidence is ignored under PhosphorOS
`build/sc64-open-sysconfig/`: `build.log`, and `first/` with per-command
logs, generated artifacts and `results.json`.

The parent independently applies/builds the patch and passes the entire runner
at `build/sc64-open-sysconfig/parent-final`, using the detached official release
checkout for the original LPF. The first parent attempt exposed a fixture-path
bug: new test fixtures do not exist in an old release checkout. The runner now
finds its fixture relative to its own source file; `--sc64` selects only the
project being inspected. The failed attempt remains under `parent/`.

- Nine parser positives cover every database value, quotes and later
  overrides. Seven negatives cover invalid values, case, empty assignments,
  extra equals, quoted empty values and unknown keys. Negative cases require
  the expected `ERROR:` diagnostic, nonzero exit and no output design.
- Four fully placed/routed fixtures cover both physical states of each
  setting. ecppack and ecpunpack both succeed. Independent pytrellis
  deserialization checks the exact CFG0 F5B4 and CFG1 F5B38 states; comparing
  the complete CFG0/CFG1 tiles against the disabled baseline rejects changes
  to any other bit in those tiles.
- The runner verifies the complete allowed-value/bit-token tables and
  records both database hashes. CFG0 is
  `d9c51a470a8ef8505443c5773d2fa2e45657e41c6dde0c0ca8e98d54f076dfc0`;
  CFG1 is
  `9247cb71ec05b97565b831583974325be0d42f24142f12544b9e818b75d946a1`.
- The original SC64 LPF is passed directly to the parser with the tiny
  fixture, without deleting any statement. It now parses and retains the
  two requested settings. Its SHA-256 remains
  `eaf0a7b1b45e7047cce5a478116e36cf74b094f20e48359fc7e02efce0efb662`.
  This parser-only test does not claim that tiny-fixture ports correspond to
  SC64 ports or that the full SC64 design places/routes successfully.

The report remains **UNQUALIFIED**: `full_lpf_qualified: false` and
`hardware_qualified: false`. Aliases, bank declarations, BLOCK paths, and
external setup/hold/output timing retain unresolved semantics under the
[constraint audit](../README.md). The original parser log retains warnings;
the report includes their warning lines. This patch does not qualify EFB/UFM,
SPI feature rows, timing, recovery behavior, or any generated FPGA image for
programming. No hardware or production firmware changes are made.
