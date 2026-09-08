# Compositor arithmetic comparison

This bounded research experiment rewrites only three combinational expressions
in the existing CI8 compositor. It does not change state, memory contents,
request scheduling, supported frames or packet format. Original source files
remain unchanged; all usable candidate sources and proof/mapping artifacts
are generated into a new output directory.

```powershell
docker run --rm -v "${PWD}:/repo" --entrypoint python3 sc64-gif-test:local -B `
  /repo/vendor/sc64/tests/gif/compact-compose/run.py `
  /repo/build/sc64-compact-compose/repeat
```

The pinned image and Yosys 0.52 provenance are in the
[cache comparison](../cache-budget/README.md). The runner records its own hash,
the unchanged compositor hash, generated source hashes and exact tool version.
Every synthesis/proof command has a 180-second timeout and must succeed; the
negative control must fail specifically at equivalence validation.

## Candidates

- `row` combines tile row and intra-tile row into one eight-bit row, then
  computes `row*320 + column` as shifts and additions. This removes separate
  additions for the tile and intra-tile row contributions.
- `pixel` computes the high eight bits of the dirty-tile index separately from
  its low three column bits.
- `header` expresses the four header-byte choices as explicit slices.

The combinations are tested independently. Each expression preserves its
original bit widths and arithmetic for every value of its input registers,
including values beyond normal canvas coordinates. There is no narrowing
based on an assumed reachable state.

## Verification and results

The complete actual compositor is processed and its dirty memory is lowered
identically on both sides for equivalence. Each candidate proves all 1549
comparison points using `equiv_simple` and induction. Registers, state, reset
behavior and memory structure are unchanged; the proof does not introduce a
clock conversion or external-memory assumption. As usual, this Yosys proof is
digital two-state equivalence, not analog timing or unknown-value simulation.

A negative control adds one to the tile read address. Whole-module equivalence
must reject it. This demonstrates that an incorrect address is observable to
the proof rather than being discarded or treated as an environmental input.
No original-animation performance run is claimed for these expressions; the
gate is complete-module equivalence and paired component mapping.

| Candidate | LUT4 | CCU2D | TRELLIS_FF | DP8KC |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 630 | 80 | 240 | 1 |
| Row | 635 | 73 | 240 | 1 |
| Pixel | 634 | 77 | 240 | 1 |
| Header | 628 | 80 | 240 | 1 |
| Row + header | 633 | 73 | 240 | 1 |
| Row + pixel | 645 | 69 | 240 | 1 |
| Row + pixel + header | 637 | 69 | 240 | 1 |

There is no large logic reduction here. Header-only saves two mapped LUTs;
the address variants exchange additional LUTs for fewer carry cells. These
counts do not establish a packed or placed improvement. All variants retain
the same register and EBR counts. None is promoted into the accelerator or
production source by this experiment.

The parent independently repeats all seven mappings, six equivalence gates
and the negative control in `build/sc64-compact-compose/parent` with identical
counts. The initial round and final seven-way comparison remain in
`build/sc64-compact-compose/agent` and `agent-final`. A Python syntax error in
the initial runner was corrected before any tests ran; it is not counted as a
successful verification attempt. The final `result.json` is the authoritative
completion and provenance record. No FPGA image or hardware operation occurs.
