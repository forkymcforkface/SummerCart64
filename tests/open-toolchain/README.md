# Open MachXO2 toolchain investigation

Research-only build and capability probes for the unchanged SC64 FPGA design.
These tools do not upload, flash, package firmware, or substitute missing hard
cells. The production Diamond build remains the reference.

## Reproduce

From the SC64 repository:

```sh
docker build -t sc64-open:7000 tests/open-toolchain
```

The image pins OSS CAD Suite 2026-09-05 by SHA-256, nextpnr
`8dbcee5c3c4415770b6fd06d5ccb2db89545b8ec`, and Project Trellis
`3afe7b52b30f4b4417ee98f03016767a502006e3` (including its pinned database
submodule). It builds nextpnr with `MACHXO2_DEVICES=7000`: the distributed
suite defaults to 1200 and 6900, omitting SC64's `LCMXO2-7000HC-6TG144C`.
No Lattice software or license file is used. Ubuntu dependency packages are
resolved at image-build time; record the resulting image ID with run evidence.

Mount the checkout at a simple POSIX path, with its existing CIC build at
`sw/cic/build/cic.mem`, and choose an unused output directory:

```sh
docker run --rm -v "$PWD:/sc64" -v "$PWD/build/open:/out" sc64-open:7000 \
  /usr/bin/python3 /sc64/tests/open-toolchain/probe.py /sc64 /out/baseline
docker run --rm -v "$PWD:/sc64" -v "$PWD/build/open:/out" sc64-open:7000 \
  /usr/bin/python3 /sc64/tests/open-toolchain/capabilities.py \
  LCMXO2-7000HC-6TG144C /out/cells
```

Use system Python for the driver: `tabbypy3` injects the suite's Python 3.11
environment, which conflicts with the source-built nextpnr's Python 3.12.
The capability probe selects `/usr/local/bin/nextpnr-machxo2` explicitly;
`--nextpnr` selects a different binary for comparisons.

The full probe reads the existing `.ldf` source list and hashes every source,
the project constraints, and CIC contents. Slang processes SystemVerilog
interfaces and the original generated wrappers; Yosys uses `synth_lattice
-family xo2`. Unknown modules remain errors. Logs and JSON statuses survive a
failed run. A zero synthesis exit alone never means hardware qualification.

Capability probes first build a small logic design, then preserve each hard
cell in a minimal netlist and ask nextpnr to place and route it. EFB and ODDRXE
declarations are diagnostic blackboxes, not implementations. The probes allow
unconstrained pins only because their outputs are never used on a cart.
The suite returns nonzero if any cell fails; do not interpret that as an
accepted SC64 build.

## Findings, 2026-09-05

The pinned suite runs Yosys `0.68+195` and nextpnr
`0.11.1-19-g8dbcee5c` without a Diamond license.

- The prebuilt nextpnr rejects SC64's part with `Unsupported MachXO2 chip
  type`; building the 7000 database is necessary.
- On the packaged 1200 device, the logic control synthesizes and routes.
  All three hard-cell probes synthesize but nextpnr rejects `EFB`, `ODDRXE`,
  and `FIFO8KB` as unsupported cell types.
- The unchanged SC64 source fails Slang elaboration on unknown `EFB` and
  `ODDRXE`. Supplying Yosys's primitive declarations directly to Slang resolves
  the generated FIFO/PLL `defparam` handling; it does not add missing backend
  support.
- The source-built 7000 variant accepts `LCMXO2-7000HC-6TG144C`. On that exact
  device, the logic control synthesizes, routes, and produces a diagnostic
  bitstream. Each of the same three hard-cell probes synthesizes but fails
  routing with an explicit unsupported-cell error (exit 125). The aggregate
  capability test correctly returns failure. No test image is flashed.

## Diagnostic backend experiments

The baseline image above remains unchanged. Optional, separately guarded
backend patches live under [EFB](efb/README.md), [ODDRXE](oddr/README.md), and
[FIFO8KB](fifo/README.md). Each directory owns its focused reproduction and
negative checks. They add research capabilities, not a qualified SC64 build.

Build their combined image from the same context after the pinned base:

```sh
docker build -f tests/open-toolchain/Dockerfile.diagnostic \
  -t sc64-open:diagnostic tests/open-toolchain
docker image inspect sc64-open:7000 sc64-open:diagnostic --format '{{.Id}}'
```

This build verifies clean source pins, applies all three patches, corrects
the FIFO flag routing graph, installs the corrected database, and regenerates
the 7000 nextpnr database. It also installs checksum-pinned sv2v v0.0.13 for the
optional [interface/high-Z frontend experiment](frontend/README.md). Record
both image IDs with the test logs. The default
command still rejects unqualified primitives; explicit flags permit only the
documented diagnostics. EFB bitstream emission always fails.

The [constraint inventory](constraints/README.md) preserves every original LPF
statement and returns exit 3 for the current SC64 project: valid inventory,
unresolved qualification. The [integration audit](integration-audit.md) records
the additional timing, configuration, initialization and programming-format
work. Neither a routed fixture nor a pack/unpack roundtrip establishes physical
equivalence to the vendor toolchain.

The full-source probe accepts repeated `--primitive declaration.v` arguments
and records their hashes separately from original source hashes. Declarations
only preserve hard cells for elaboration; they do not implement those cells.

## Remaining work

The [release reference tools](release/README.md) reproduce the current release
package byte-for-byte using source-rebuilt CPU components and explicitly
reference-derived FPGA configuration/metadata. This is not an all-source FPGA
build. The [guarded RAM inference experiment](memory/README.md) removes the
full-design register expansion and passes formal/model checks; placement
completes under diagnostic constraints, but EFB routing and timing remain
unqualified. [Alternative tool research](research-tools.md) records verified
file-conversion capabilities and remaining configuration evidence requirements.

1. Qualify packing, routing, configuration bits, and timing for EFB (including
   UFM access), ODDRXE (the external SDRAM clock), and FIFO8KB. Adding empty
   declarations does not supply any of this behavior.
2. Preserve the entire SC64 pin/electrical configuration, clock constraints,
   PLL phase and clock output behavior, reset behavior, CIC initialization,
   and internal flash/configuration requirements.
3. Build and check the full unchanged SC64 image, including its programming
   format and recovery behavior, before adding GIF RTL or testing hardware.

Upstream references:

- [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build)
- [nextpnr device selection](https://github.com/YosysHQ/nextpnr/blob/8dbcee5c3c4415770b6fd06d5ccb2db89545b8ec/machxo2/CMakeLists.txt)
- [nextpnr MachXO2 backend](https://github.com/YosysHQ/nextpnr/tree/8dbcee5c3c4415770b6fd06d5ccb2db89545b8ec/machxo2)
