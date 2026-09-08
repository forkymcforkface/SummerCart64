# Arithmetic mapping equivalence gate

The default and `-noccu2` mappings pass a concrete combinational gate covering
every `$alu` parameter/port shape in the guarded LZW-only stock checkpoint.
This does **not** establish whole-design equivalence. The area's
`functional_equivalence_proven` flag remains false, as does hardware
qualification.

```powershell
docker run --rm -v "${PWD}:/repo" sc64-open:diagnostic-lpf /usr/bin/python3 -B `
  /repo/vendor/sc64/tests/open-toolchain/area-map/equivalence.py `
  /repo/build/sc64-area-map/review-lzw `
  /repo/build/sc64-area-equivalence/repeat
```

The input must be a passed [area comparison](README.md). Its recorded Yosys
executable hash must match the current executable. The output directory must
be new and outside tests. Each tool command has a 180-second timeout. Generated
operator bundles, mapped JSON, flattened circuits, proof scripts, logs and
hashes remain in that output directory.

The local `baseline/forward.json` must match the unique `forward.json` hash in
the passed area result's source provenance before extraction, and must remain
unchanged through completion. Missing or ambiguous provenance is an error.
The positive proof also requires the explicit SAT success diagnostic, not
merely a zero process exit. A whitespace-only alteration to a copied checkpoint
is rejected before proof execution; this confirms the provenance guard checks
the supplied bytes even when they still describe valid JSON.

## Exactly what is proved

The actual guarded `baseline/forward.json` contains 132 `$alu` instances with
58 distinct parameter/port shapes. These include unsigned widths from one to
32 bits and a signed 27-bit A / 30-bit B / 31-bit result configuration. The
runner records the original instance names for every shape.

One copy of each shape becomes an isolated `$alu` with independent input
ports for A, B, CI and BI, and observable X, Y and CO outputs. No constant
operand, surrounding reachability or relationship between carry-in and
operand inversion is assumed. Both mappings synthesize this same bundle using
the installed `synth_lattice -family xo2`, with only `-noccu2` differing.

The mapped bundle is required to contain only LUT4 and CCU2D cells, plus
nonfunctional source annotations. The installed Yosys MachXO2 functional
models lower those actual mapped cells. A direct combinational SAT miter proves
all **2322 output bits** equal for every input combination. There are no clocks,
state, assumed synchronization cycles or initialized-base-case shortcuts in
this proof.

The default isolated bundle maps to 1198 LUT4 plus 393 CCU2D; the soft bundle
uses 2706 LUT4. These counts are for fully exposed operator outputs with
unconstrained inputs, not the stock netlist. They must not be used to infer
whole-design area savings or regressions.

A negative control complements the INIT of the soft bundle's
`op0_CO_LUT4_Z`. The same direct SAT miter produces a mismatch and the required
failure diagnostic. Unknown-cell ignoring, undefined-value waivers and
black-box output assumptions are not used by this combinational gate.

## Preserved failures and model scope

The installed `cells_sim_xo2.v` recursively includes FF/IO declarations already
present through `common_sim.vh`. Reading it without its supported `NO_INCLUDES`
macro fails with a duplicate module declaration. The final gate uses that
macro; the needed LUT4 and CCU2D functional models remain included. No used
model is replaced by a black box.

An initial equivalence attempt matched generated internal net names across
the two different mappings. Those are not valid common boundaries and yield
many unproven points. Removing non-port naming metadata leaves two unproven
points in `equiv_simple`, both in the signed shape. A direct SAT miter proves
the entire bundle, including those two points, without relying on internal
name matching. The final runner uses this direct proof. These intermediate
failures are retained rather than presented as counterexamples to mapping
correctness.

The provenance-strengthened final run is `build/sc64-area-equivalence/provenance`;
the checkpoint rejection is recorded in `build/sc64-area-equivalence/tamper.log`.
The preceding successful run is `build/sc64-area-equivalence/frozen`. Earlier
attempts remain under `agent`, `final`, `final2`, `ports` and `direct`. The
manifest hashes the checkpoint, area result, runner, exact Yosys executable,
XO2 model entry point, common and carry models, and mapping support files.

## What remains unproved

The extracted gate does not include the surrounding Boolean optimization,
constant-driven arithmetic cones, multiply-accumulate cells, register
elimination, reset/startup behavior or final netlist wiring. In particular it
does not explain or prove safe the 18-register difference between the full
default and soft-carry mappings.

RAM, FIFO, PLL, EFB, ODDRXE, I/O and tristate cells stay outside this operator
test. They are not deleted from or modified in the stock candidate, and this
gate does not waive their parameter, wiring, timing or physical configuration
requirements. A whole-fabric compositional proof would still need to compare
each hard-block input, share only corresponding output boundaries, validate
their identity, and establish the sequential initialized base case. The
[earlier conditional fabric investigation](../memory/timing-options2.md)
shows why a closed induction step alone is insufficient.

The result supports arithmetic-operator mapping correctness using the pinned
functional models. It is not authorization for a bitstream or hardware change.
