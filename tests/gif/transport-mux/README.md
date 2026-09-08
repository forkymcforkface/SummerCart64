# Three-owner transport mux selector experiment

The actual [abort transport mux](../sc64-transport-abort/gif_transport_mux.sv)
uses a signed integer modulo expression to select among three clients.
`run.py` generates an isolated derivative replacing only that combinational
selector with explicit priorities. It never edits the source mux, arbitration
state machine, request/ACK gap, registered payload, or four fatal checks.

```sh
python3 -B run.py /fresh/ignored/output/directory
```

Requires Python 3, Verilator, a C++ compiler, make, and Yosys with
`synth_lattice -family xo2`. The verified
container is `sc64-gif-test:local`, Yosys 0.52, commit
`fee39a3284c90249e1d9684cf6944ffbbcbb8f90`. Each tool invocation has a
180-second timeout. The output directory must not exist and must be outside
the vendored tests tree. Generated source, netlists and logs stay there.

The selector orders are 0/1/2, 1/2/0 and 2/0/1. State value 3 explicitly
retains the original modulo behavior, order 0/1/2. No request produces
`found=0,choice=0`, as in the baseline.

## Verification and scope

- The complete source mux is flattened to the fixed `mem_bus` port schema.
  The same four simulation fatal statements are omitted from both formal
  and synthesis copies; they remain in the usable derivative. Integer cast
  `int'(next_owner)` becomes its explicit signed 32-bit zero extension for
  this Yosys frontend. The actual mem_bus field widths/order and both modport
  directions are checked before flattening. Other logic remains unchanged.
- `equiv_simple` plus one-step successful induction proves all 108 matched
  equivalence points, including registered payload/state and observable
  outputs. Inputs have no traffic assumptions.
- An additional combinational SAT proof extracts the selector directly from
  both actual sources. All 32 combinations of two-bit `next_owner` and three
  request bits are covered, including state 3. No reset/reachability assumption
  hides that value.
- A priority mutation changes the state-0/3 first request test from scratch
  to source. Both full-mux and selector proofs fail with exact exit 1. Their
  logs remain as negative controls.
- Verilator independently executes all 32 selector inputs using the original
  SystemVerilog integer cast, its lowered form and the candidate. This checks
  the cast lowering against an actual SV frontend. Negative formal runs must
  include the expected unproven-equivalence/SAT-proof-failure diagnostic;
  a generic tool error with exit 1 cannot pass.

Paired standalone synthesis in this flow:

| Actual mux | LUT4 | CCU2D | Flip-flops |
|---|---:|---:|---:|
| Original selector | 7,526 | 3,792 | 54 |
| Explicit priorities | 162 | 0 | 54 |

These are paired results for this exact frontend/lowering flow. They are not
interchangeable with another pipeline's 4,919-LUT baseline. Combined synthesis,
unchanged original-GIF transport pixels/cycles, and cancellation are separate
integration gates owned by the coordinating agents. No Fmax, placed fit or
hardware safety result follows from these counts alone.

Reviewed local result: `build/sc64-transport-mux/reviewed/result.json`.
Baseline SHA256: `4ecdf0ff524240467f9edd37db48bd5bdfac45d4b8abe3de272370e7a378a0fd`.
Generated candidate SHA256:
`2e6e19e0fdce50d8b06470ee4344e30afedddfa043f7ea16cc380c9003c2303a`.
The report explicitly records `hardware_qualified: false`.
