# FIFO8KB diagnostic support

This experiment packs the exact SC64 hard FIFO onto the existing MachXO2 EBR
BEL, routes its real ports, and writes existing database configuration fields.
It does not replace the FIFO with logic or claim a timing-qualified FPGA image.
Normal packing fails closed. `--fifo-routing-diagnostic` explicitly enables
unqualified routing; FIFO endpoints have no fabricated setup/hold or clock-to-Q
arcs. The exact FIFO fixture consequently reports **no Fmax**.
The flag is re-established from the current command line after loading JSON;
saved settings cannot authorize a later run. Both the timing and configuration
entry points reject marked FIFO cells without fresh opt-in, including replay
with packing, placement, and routing disabled.

## Reproduce

Use a private container from the [parent image](../README.md), mounting the
SC64 checkout at `/sc64` and an ignored output directory at `/out`. Changes
apply only to that container's source trees:

```sh
python3 -B /sc64/tests/open-toolchain/fifo/apply.py /src/nextpnr
python3 -B /sc64/tests/open-toolchain/fifo/apply_trellis.py /src/prjtrellis
touch /src/nextpnr/machxo2/facade_import.py
PRJTRELLIS_DB=/src/prjtrellis/database cmake --build /src/nextpnr/build -j2
python3 -B /sc64/tests/open-toolchain/fifo/test.py /sc64 /out/fifo
```

The touch forces regeneration because upstream CMake does not depend on the
database files. `PRJTRELLIS_DB` prevents accidentally using the separately
installed, unchanged database. The test requires a new output directory,
preserves logs, and rejects unexpected exits. Generated bitstreams are
diagnostics only and must not be flashed.

The equivalent reviewable changes are [nextpnr.patch](nextpnr.patch),
[trellis-database.patch](trellis-database.patch), and
[trellis-fuzzer.patch](trellis-fuzzer.patch). Apply scripts and patches are
alternatives, not cumulative edits. Pins: nextpnr
`8dbcee5c3c4415770b6fd06d5ccb2db89545b8ec`, Trellis
`3afe7b52b30f4b4417ee98f03016767a502006e3`, database
`015e0330630d7c238c0e4f2cdd9c8157eb78c54a`.

Patch files use zero context. From each corresponding pinned repository root,
use `git apply --unidiff-zero --check /path/to/patch` before
`git apply --unidiff-zero /path/to/patch`. The database patch applies within
the database submodule; the fuzzer patch applies within Project Trellis.

## Mapping and direction correction

The unchanged [SC64 generated FIFO](../../../fw/rtl/vendor/lcmxo2/generated/fifo_8kb_lattice_generated.v)
uses 1024 entries, 9-bit ports carrying eight useful bits, NOREG, independent
clocks, asynchronous reset with synchronous release, and explicit thresholds.
The patch intentionally rejects other widths and registered output mode.
Missing explicit pointer or chip-select parameters also fail rather than
silently assuming values. Pointer fields require exactly fourteen binary
digits and chip-select fields exactly two, each following `0b`.

Existing `libtrellis/src/Bels.cpp:add_bram` defines AE, AF, EF, FF as EBR
outputs. However, the pinned `040-ebr_routing/mk_nets.py` labels all four as
sinks and the EBR0/EBR0_END fixed connections point toward those outputs.
The separate patches reverse exactly eight fixed edges and four fuzzer
labels. Before correction, all 104 flag outputs across 26 EBR BELs have zero
outgoing edges, and the exact FIFO cannot route its Full net. Afterward all
104 have outgoing edges and the same fixture routes successfully. These
fixed edges carry no programmable fuse bits; this is a graph-direction
correction, not proof of physical configuration or timing.

Physical aliases WE/RE/ORE to CEA/CEB/OCEB, CLKW/CLKR to CLKA/CLKB, and
RST/RPRST to RSTA/RSTB agree with factual primitive alias records in the
installed Diamond 3.13 `ispfpga/xo2c00/data/xo2c00.bfd`. Data-port splitting
uses the existing nextpnr PDP mapping (low output half DOB, high half DOA);
that FIFO-specific physical mapping still needs an independent vendor-route
comparison. FULLI and EMPTYI use CS2. The
[MachXO2 datasheet, Tables 2.5–2.6](https://www.latticesemi.com/view_document?document_id=38834)
identifies them as flow-control inputs, FF/AFF as write-clock outputs, and
EF/AEF as read-clock outputs. Global reset resets both pointers; read-pointer
reset permits replay. No proprietary library code is included here.

## Results and limits

On 2026-09-05 the focused suite passes synthesis, default rejection, unsupported
width rejection, missing-pointer rejection, exact FIFO diagnostic placement
and routing, and pack/unpack/repack byte equality. This checks the existing
database's internal consistency; it does not establish vendor equivalence.
Split configuration words can print differently across tiles after unpacking;
the roundtrip assertion compares complete bitstreams.
The hardened suite additionally checks invalid binary fields, absent and short
chip-select fields, saved-JSON timing/configuration rejection, and successful
replay with fresh opt-in. Every nextpnr rejection must exit exactly 125 with
its expected diagnostic. A deliberately invalid final fuzzer file verifies
that all Trellis anchors are validated before any database file is modified.
The analogous nextpnr test removes the final bitstream anchor and verifies
that all four source files remain byte-identical. Both applicators stage their
edits in memory until every anchor validates.

The independent [model_test.v](model_test.v) also passes against the installed
Diamond FIFO model and the unchanged SC64 wrapper: 1024-byte fill/drain with
exact data checks, full/almost-full/empty flags, independent clocks, global
reset, and 32-byte read-pointer replay. It does not simulate the newly packed
routing, analog timing, metastability, or every reset-release phase.
Run it **inside** an existing licensed-software installation without copying
its proprietary models into the repository:

```sh
iverilog -g2012 -s model_test \
  -y /usr/local/diamond/3.13/cae_library/simulation/verilog/machxo2 \
  -o /out/model.vvp /sc64/tests/open-toolchain/fifo/model_test.v \
  /sc64/fw/rtl/vendor/lcmxo2/generated/fifo_8kb_lattice_generated.v
vvp /out/model.vvp
```

The model test uses open-source Icarus, not Diamond compilation or a license
bypass. Tested model SHA-256:
`3258c22e56cd85f541223d3c97f22bc75e6046d5f75ec6ba2d76c75e862e8b7c`.
SC64 wrapper SHA-256:
`a4ec6d29ae9b9b8834453dec8551aeeb286c152980e8f4b769babe675cce3e49`.

MachXO2 FIFO timing arcs are absent from the pinned open database. Installed
vendor timing files expose arc names but no imported qualified timing model.
Physical mapping/configuration comparison, timing characterization, full
SC64 route integration, and actual-board verification remain required.
No production source list, firmware, device settings, or hardware is changed.

## Evidence

Ignored run directory in the PhosphorOS parent checkout:
`build/sc64-open-fifo/atomic-final/`; preliminary before/after direction logs:
`build/sc64-open-fifo/exact/`. The diagnostic bitstream roundtrip SHA-256 is
`7d75dffdfcf1070caf6c2e6556ac4899be173ebf5f3ef187493f7487c978f9ad`.
Open image ID:
`9632531eb216aefc18f12f8de0c005faef60b433df37e11b59bac0a1c8a45d3a`;
official `ghcr.io/polprzewodnikowy/sc64env:v1.10` image ID:
`7d8621a136c7a8ba142b60c85f166d04f0fee7e7f461366ae885b2059a240cd2`.

| Database file | Pinned SHA-256 | Corrected SHA-256 |
| --- | --- | --- |
| EBR0/bits.db | `9ad1993ab917a01b39f812f831a4ac2804fdb784f9cb5e4dd8e7337bdd1e6770` | `b7bfc9f057918a80a657f52daaee6a66d74cff38ab7d052d6f1e9149f2c93a5c` |
| EBR0_END/bits.db | `3198b13102f798f09e392e7a5cf3b9ce562bc66bae4d087f6ce336cee7a02d95` | `dfe8e94f70118186f83674f721058841b2462022b92460a27eb321a5a423c257` |
