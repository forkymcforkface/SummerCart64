# Targeted synchronous-reset unmapping experiment

This bounded experiment follows the `n64_scb.flashram_done` control-set lead
from [control-sets.md](control-sets.md). It changes only the single `$sdff`
that drives that named net in the exact passed compact soft-carry checkpoint.
The mapping uses Yosys `dffunmap -srst-only` before the `map_ffram:`
continuation. It does not edit production RTL or weaken MachXO2 legality.

Run it once in the pinned diagnostic container:

```powershell
docker run --rm -v "${PWD}:/repo" sc64-open:diagnostic-lpf /usr/bin/python3 -B `
  /repo/vendor/sc64/tests/open-toolchain/area-map/reset_unmap.py `
  --checkpoint /repo/build/sc64-stock-lzw-compact/agent/area/soft-carry/forward.json `
  --area-result /repo/build/sc64-stock-lzw-compact/agent/area/result.json `
  --project /repo/build/sc64-open-release/source/fw/project/lcmxo2 `
  --executable /repo/build/sc64-open-timing-options/nextpnr-machxo2 `
  --lpf /repo/build/sc64-open-memory/parent-full/pins-only-diagnostic.lpf `
  --output /repo/build/sc64-reset-unmap/FRESH_OUTPUT
```

The runner rejects any checkpoint, passed area result, pinned nextpnr, or LPF
hash change before creating output. It also requires one current `$sdff`
driver with the expected one-bit active-high, zero-valued synchronous reset.
The isolated original cell and actual `dffunmap` result pass a local induction
check and a negative reset-polarity mutation. This is supplemental evidence,
not an initialized-base proof. The current checkpoint has no Q initialization
constraint; unchanged attributes do not establish a chosen power-up value.

An explicit selection precedes the selection-count assertion: Yosys assertions
do not modify the selected objects. A separate before/after snapshot requires
exactly one DFF and mux to replace the selected cell, with every unrelated cell,
existing net/initialization, module port, clock and Q identity unchanged.
Net names establish a bijection between JSON bit IDs; merges and new constant
ties fail. An unrelated-cell mutation must fail this gate. The scope snapshot is a separate
run so diagnostic JSON serialization cannot perturb the paired mapping flow.

The script continues the existing `-noccu2` mapping, checks RAM
shape and parameters against the paired compact baseline, runs the established
diagnostic EFB and PLL preparation, and invokes the pinned nextpnr packer with
the same LPF and ODDR/EFB/FIFO diagnostic flags. The packed target fails the
required LUT-fed `SD=1`/no-LSR shape. The runner returns nonzero and records the
rejection; it contains no placement or routing step. An unexpected improvement
also fails pending a separately reviewed experiment and stronger proof gates.

## Executed outcome

The isolated selection maps to 6,353 LUT4 and 3,734 FF, compared with the
fresh paired baseline's 6,347 LUT4 and 3,734 FF. RAM shapes and parameters are
unchanged, and the six-LUT increase remains within device capacity. The pack
rejects the intended local outcome: later optimization reconstructs the
synchronous reset, so `n64_scb.flashram_done_TRELLIS_FF_Q` still has `SD=0`,
an `M` data input, and an LSR connection. The runner stops fail-loud at that
gate and performs no placement. Evidence is under
`build/sc64-reset-unmap/agent`; setup failures are retained in separately
named sibling directories.

The parent repeats the final rejection at `build/sc64-reset-unmap/parent-final/`,
including the scope gate and unrelated-cell negative. A first scope comparison
at `parent/` rejects JSON bit renumbering before the bijection is implemented.
Focused checks against the final snapshots pass both unrelated-cell and net-merge
negatives (`build/sc64-reset-scope-check.py`). No failed setup is a placement
measurement. The runner's nonzero result is the expected rejection, not a pass.

Diagnostic packing gives 6,552 COMB versus the accepted compact pack's 6,546,
with 3,734 FF, 25 EBR, 24 RAMW and 101 I/O. No production change is retained.

The isolated induction and negative reset-polarity check support the local
`dffunmap` transformation, but the stronger extracted-next-state SAT gate is
still pending. No whole-design equivalence or placement improvement is
claimed from this rejected mapping.

The named retained setup attempts cover missing synthesis stages/libraries,
wrong project working directory, JSON library serialization, a baseline
mismatch, an overcapacity split-stage mapping, accidental broad selection and
an overly strict area gate. Early retries before that preservation procedure
were removed and have no retained logs; they are not claimed as independently
reviewable experiments.
