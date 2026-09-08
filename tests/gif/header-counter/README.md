# Bounded packet-header counter

The transport's `emitted` position only selects header bytes 28 through 31.
This isolated derivative replaces its 27-bit incrementing counter with a
six-bit counter that saturates at 32. Packet bytes, DMA lengths, cancellation
and queue ownership remain unchanged.

## Reproduce

Generate the [bounded decoder](../sc64-bounded/README.md) and
[proven mux](../transport-mux/README.md) first. Use fresh output directories:

```powershell
docker run --rm -v "${PWD}:/repo" --entrypoint python3 sc64-gif-test:local -B /repo/vendor/sc64/tests/gif/header-counter/run.py ORIGINAL.gif /repo/build/sc64-header-counter/repeat-behavior --decoder BOUNDED_DIRECTORY --mux PROVEN_MUX.sv --mode behavior
docker run --rm -v "${PWD}:/repo" sc64-open:diagnostic-lpf /usr/bin/python3 -B /repo/vendor/sc64/tests/gif/header-counter/run.py ORIGINAL.gif /repo/build/sc64-header-counter/repeat-mapping --decoder BOUNDED_DIRECTORY --mux PROVEN_MUX.sv --mode mapping
```

Paths passed to the runner are container paths. Behavior mode needs Python,
Yosys, Verilator 5.032 and a C++ build toolchain. Mapping mode needs Python,
sv2v and Yosys with MachXO2 support. Evidence records versions and input hashes.

## Gates and measured result

Both modes check the one-step inductive relation
`small = min(old_count, 32)`: zero initialization establishes it; arbitrary
clear, push and stall combinations preserve it for bounded packets. Both
header event predicates are equal under that relation. A deliberate saturation
at 31 fails with the required SAT diagnostic. This is a proof of the extracted
counter recurrence, not a whole-pipeline RTL equivalence proof. The existing
compositor emits at most `192 + 1200*64 = 76992` bytes; an unbounded malformed
stream that wraps the old 27-bit counter is outside this claim.

The actual-controller simulation repeats the baseline and candidate for eight
original Final Fight images with identical complete summary output:
16,439,680 cycles and 86,784 packet bytes. All twelve inherited cancel/restart
cases pass, including backpressure and delayed memory responses.

| Paired combined synthesis | LUT4 | CCU2D | FF | DP8KC | Distributed RAM |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline | 2387 | 413 | 1203 | 4 | 16 |
| Saturating header counter | 2348 | 380 | 1182 | 4 | 16 |

The saving is 39 LUT4, 33 carry cells and 21 FF. This run uses one complete
`synth_lattice` invocation; the earlier transport-fit audit checkpoints and
resumes synthesis, so its absolute LUT total differs. Compare the paired
results here, not totals from different pass sequences. No placement or timing
claim follows from this result.

Evidence: `build/sc64-header-counter/{frozen-behavior,frozen-mapping}/`.
Independent review confirms the counter's uses and clear ordering; the runner
rejects a changed use inventory and records fixture/driver hashes. The first attempt
uses the newer diagnostic-image Verilator 5.051, which rejects the unchanged
compositor's task writes as multiple writers. That attempt fails before
simulation. Behavior is rerun with the established 5.032 image; no warning is
suppressed and no compositor source changes are made to bypass the failure.

This is a retained resource-reduction experiment. It changes no production
RTL, firmware image, cart state or PhosphorOS UI code.
