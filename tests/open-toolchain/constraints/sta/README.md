# Executable synthetic OpenSTA constraint fixtures

This is a research-only constraint/annotation test, not a MachXO2 timing
library, SC64 SDC translation, or cart qualification. `synthetic.lib` and
`synthetic.sdf` contain deliberately invented analytical values. No vendor
timing files are distributed. `CLOCK_BUFFER` provides connectivity for an
ideal generated clock; it does not model a physical PLL or ODDR.

## Build and reproduce

The verified engine is OpenSTA **3.1.0**, source
`a9a3f30ca97dc13f9ef911cae1a82c42c67379e1`, from the
[OpenROAD-maintained primary repository](https://github.com/The-OpenROAD-Project/OpenSTA/tree/a9a3f30ca97dc13f9ef911cae1a82c42c67379e1).
CUDD is upstream 3.0.0, commit
`f54f533303640afd5dbe47a05ebeabb3066f2a25` from
[cuddorg/cudd](https://github.com/cuddorg/cudd/tree/f54f533303640afd5dbe47a05ebeabb3066f2a25).

The isolated `sc64-opensta-agent` container executes the build steps recorded
in the local Dockerfile, starting from `sc64-open:diagnostic` image ID
`sha256:6c1b547003a32e50d26ba99c53e9a45967a70f4fb7226080dadc03048bbf10a1`.
The actual build uses CMake Release and two jobs. CUDD's checked-in autotools
files request old aclocal 1.14; running ordinary `autoreconf -fi` with the
installed autotools resolves that build prerequisite. OpenSTA also requires
the GTest development package during configuration and the installed CUDD
library. No engine source or licensing code is modified.

From the SC64 checkout, a fresh container can be built and run with:

```sh
docker build -t sc64-opensta:research tests/open-toolchain/constraints/sta
docker run --rm -v "$PWD:/sc64" -v /absolute/ignored/build/sc64-opensta:/out \
    sc64-opensta:research /usr/bin/python3 -B \
    /sc64/tests/open-toolchain/constraints/sta/run.py /out/new-results \
    --sta /src/OpenSTA/build/sta
```

The parent builds the checked-in Dockerfile independently and passes all 13
cases in a fresh container. Explicit `libfl-dev` is required when recommended
packages are disabled; the first clean build fails without its headers.
Evidence: `docker-build.log`, `docker-build-final.log`, and `fresh-image/` under
the ignored output directory below. Image ID:
`sha256:b0112b5754312e234587e300db3778cc4bdcad3c894065ffea96e67aeca80ecf`.
The fresh build's executable hash matches the initial verified engine below.
The initial agent's default CMake build also builds upstream test executables;
it does not run them. The Dockerfile targets `sta` to avoid those unnecessary
extra executables. Repository source revisions are pinned;
the base tag and apt package repositories are not immutable, so this is not a
claim of byte-reproducible compiler binaries.

Logs remain ignored in the parent checkout under `build/sc64-opensta/`:
`install.log`, `clone.log`, `cudd-clone.log`, `cudd-autoreconf.log`,
`cudd-configure.log`, `cudd-build.log`, `configure.log`, and `build.log`.
The verified executable SHA-256 is
`3d3fb657fd3f4cbe225ec6cf6a893516d0a3d96d0c21b9d3658f859b6c51dfdf`.
The runner checks its pinned banner and records the binary hash. Each result
directory must be new and outside `tests/`; every engine log is retained.

## Analytical timing checks

The root clock has a 10 ns period. The generated clock uses
`-edges {1 2 3} -edge_shift {7.5 7.5 7.5}`; the engine reports a 10 ns
period and waveform `{7.5 12.5}`, exactly 270 degrees. This executable
result resolves the documentation/source discrepancy described in
[external-sta.md](../external-sta.md) for this specific pin.

Input arrival limits are max 2 ns, min **-0.5 ns**. Output delay limits are
max 3 ns, min **-1 ns**. The register's setup is 1 ns, hold is 0.25 ns,
and SDF clock-to-Q min/max are 0.5/1 ns. Root and generated clocks are ideal
except in the explicit latency case. Fixture wires carry zero interconnect
delay by construction; cell coverage checks do not claim routed net coverage.

The base case's independently calculated slacks are:

| Check | Calculation, ns | Expected/observed slack, ns |
| --- | --- | ---: |
| Input setup | 7.5 - 1 - 2 | 4.5 |
| Input hold | (10 - 0.5) - (7.5 + 0.25) | 1.75 |
| Output setup | (10 - 3) - (7.5 + 1) | -1.5 |
| Output hold | (7.5 + 0.5) - (0 + 1) | 7.0 |

The output setup violation is intentional: a passing **test** means the engine
matches the analytical result, not that this synthetic circuit meets timing.
Eight positive cases check all four endpoint slacks to 0.0001 ns tolerance:

- Base 270-degree phase and both signed external minima.
- Zero phase: input setup/hold become 7/-0.75 ns; output setup/hold become
  6/-0.5 ns.
- Clamping only input minimum to zero changes input hold to 2.25 ns.
- Clamping only output minimum to zero changes output hold to 8 ns.
- SDF hold annotation of **-0.25 ns** changes input hold to 2.25 ns, preserving
  the negative check instead of silently clamping it.
- One nanosecond generated-clock latency changes input setup/hold to
  5.5/0.75 ns and output setup/hold to -2.5/8 ns.
- Referencing the falling root edge for input arrival changes input
  setup/hold to -0.5/6.75 ns.
- A false path from `d` to `capture/D` removes exactly its setup and hold
  paths; both output checks remain with their original values.

## Missing-model and missing-constraint rejection

Five negative cases must be rejected by the wrapper's coverage gate:

| Deliberate defect | Actual behavior and required rejection |
| --- | --- |
| Missing explicit output minimum | Engine exits 0 and omits the output hold path; the fixture's required I/O constraint inventory rejects it. |
| Missing input delays | Engine exits 0 with warnings; explicit I/O coverage rejects it. |
| Misspelled SDF instance | Fixture instance/type preflight rejects it before invoking the engine. |
| Missing SDF clock-to-Q arc | Engine exits 0 and falls back to Liberty; cell annotation count rejects it. |
| Missing Liberty hold topology | Engine exits 0 with diagnostics and omits input hold; timing-check topology/annotation counts reject it. |

The baseline requires exactly two cell delay arcs and one setup plus one hold
arc, all annotated. It checks generated-clock waveform, engine diagnostics,
explicit min/max I/O declarations and the complete expected endpoint metric
set. A signal-terminated process is always a failure, never an expected
negative-test pass. These counts and the small instance/type preflight are
specific to the checked-in fixture, not a general Verilog/SDF parser or a
full-chip SC64 acceptance wrapper.

The first direct malformed-instance probe exposed a robustness defect in this
OpenSTA pin: the engine terminates with **SIGSEGV (-11)**. The evidence is
`build/sc64-opensta/complete-first/wrong_instance/`; that exploratory run is
**not a passing suite** despite its provisional results file. The final runner
preflights the fixture's SDF instance/type mapping and never feeds that known
malformed input to the engine. The upstream engine is unchanged, and graceful
engine rejection remains unproven.

All thirteen final cases pass their respective analytical or rejection checks.
Evidence is `build/sc64-opensta/final/`, with `results.json` and per-case logs;
`fixture_only: true` and `machxo2_timing_qualified: false` remain explicit.

## Remaining full-chip boundary

This establishes that the selected engine can evaluate phase, signed min
delays, negative SDF hold checks, clock latency and scoped exceptions when
given complete models. It does not supply missing FIFO/EFB/ODDR/PLL timing,
minimum route-delay characterization, electrical loading, or a lossless
nextpnr-to-Verilog/Liberty/SDC handoff. The seven known hard-cell gaps in
[external-sta.md](../external-sta.md) remain. No SC64 constraint statement is
translated or removed, and no backend bitstream-emission barrier is relaxed.
