# Algebraic DMA flag predecode

Isolated follow-up to [registered DMA predicates](../README.md). It uses the
same actual-source wrapper, sv2v conversion, full equivalence points and
negative control by importing the frozen parent runner. No production RTL,
encoder, cart state or previous candidate is changed.

For a 27-bit unsigned counter `n`, the registered predicates become:

| Counter update | Zero flag | At-most-two flag |
| --- | --- | --- |
| `n - 1` | `n == 1` | `n >= 1 && n <= 3` |
| `n - 2` | `n == 2` | `n >= 2 && n <= 4` |

The lower bounds preserve wraparound: a counter smaller than the decrement
wraps to a large 27-bit value, not a last-transfer value. Start-length flags,
the six original counter writes and their priority remain unchanged.
The transform requires exactly three decrement-one and two decrement-two
assignments for each flag. Unsupported source shapes fail before output.

```powershell
docker run --rm -v "${PWD}:/repo" sc64-open:diagnostic-lpf /usr/bin/python3 -B /repo/vendor/sc64/tests/open-toolchain/memory/dma-flags/algebra/run.py /repo/build/sc64-open-release/source /repo/build/sc64-dma-flags/algebra/proof-review
```

The actual DMA equivalence gate passes all 313 matched internal/output points.
The inherited wrong-start-zero control fails with exactly two unproven points
and exit 1. Evidence: `build/sc64-dma-flags/algebra/proof-final/`. Undefined
startup remains source-undefined under `-undef`; this is not a physical reset
or power-up proof. No input restriction or changed transfer cycle is added.

The isolated full-design driver is
`build/sc64-dma-flags/algebra/full-ab.py`. It uses the prior registered
candidate's mapped-RAM checkpoint as the fresh baseline, with the same
guarded mapping, checkpoint resynthesis, diagnostic router executable,
pins-only LPF, default seed, original PLL metadata and explicit 100 MHz.
The original source manifest is unchanged except the proven DMA substitution.
Full results and disposition follow only after completed routes; diagnostic
timing does not qualify an image for hardware.

## Inequality result and final bitfield variation

The inequality form completes routing at **73.52 MHz**, below its fresh
78.23 MHz registered-predicate baseline; pre-route estimates are 62.84 and
66.51 MHz. Both exit 1 for the explicit 100 MHz requirement. This candidate
is rejected. Its mapped 478 carry cells barely reduce the baseline's 480.

`bitfield.py` uses the same actual-DMA proof but spells the ranges as upper-bit
zero plus small low-bit membership:

- decrement one: bits 26:2 are zero and bits 1:0 are nonzero;
- decrement two: bits 26:3 are zero and bits 2:0 equal 2, 3 or 4.

These preserve the same lower bounds and exclude underflow. Start-length
predicates remain unchanged. All 313 actual-source equivalence points and
the strict negative control pass in
`build/sc64-dma-flags/bitfield/proof-final/`. To reproduce, substitute
`bitfield.py` for `run.py` in the command above and use a fresh output path.
Full mapping preserves the same eight address implications and six guarded
RAM blocks. Original manifest and proven candidate hash checks for both
variations are recorded in their `provenance.json` files.

## Completed comparison and disposition

| Variant | LUT4 | CCU2D | FF | Pre-route | Routed | Disposition |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Registered baseline | 4,461 | 480 | 3,027 | 66.51 MHz | 78.23 MHz | Previous candidate |
| Algebraic inequalities | 4,451 | 478 | 3,027 | 62.84 MHz | 73.52 MHz | Rejected |
| Explicit bitfields | 4,503 | 428 | 3,027 | 63.30 MHz | 72.03 MHz | Rejected |

Each candidate has its own freshly rerouted registered baseline, both
reproducing 78.23 MHz. All four routes finish and return exit 1 for the
100 MHz requirement. The bitfield form removes 52 carry cells but adds
42 LUT4 and loses 7.9% of the baseline's estimated maximum frequency.
Reducing comparator carry cells does not improve this routed design.
Hard-cell types and parameters, including RAM INIT contents, match the
registered baseline in both variants; all retain 18 DP8KC, four FIFO8KB
and eight LUT RAM cells. This does not qualify missing hard-cell timing.

Neither follow-up is retained as a performance candidate. These files are
isolated reproductions of rejected experiments; they do not modify the
previous candidate or production source. Evidence is in
`build/sc64-dma-flags/{algebra,bitfield}/{baseline,candidate}/`; no further
variation is attempted in this pass. Parent review and independent proof reruns
pass for both variants in their `parent-proof/` directories; the rejected route
results are inspected against the paired command and provenance records.
