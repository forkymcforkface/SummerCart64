# Additional no-carry and ABC timing probes

This bounded follow-up uses unchanged SC64 source and the existing guarded RAM
checkpoint. It adds no production RTL, changes no read/write semantics, and
programs no hardware. The [first timing report](timing-options.md) owns the
paired baseline, exact checkpoint/executable/LPF hashes, and earlier rejected
wide-LUT and placement experiments.

## Actual implementation results

| Candidate | LUT4 | FF | CCU2D | Pre-route | Post-route | Route complete | Exit |
|---|---:|---:|---:|---:|---:|---|---:|
| Previous paired baseline | 4,448 | 3,023 | 402 | 64.49 MHz | 75.52 MHz | Yes | 1 |
| `-noccu2` | 4,780 | 3,005 | 0 | 60.36 MHz | 69.82 MHz | Yes | 1 |
| Explicit ABC script control | 4,458 | 3,023 | 402 | 67.38 MHz | 64.14 MHz | Yes | 1 |
| Same ABC script without final `&mfs` | 4,509 | 3,023 | 402 | 60.83 MHz | 74.19 MHz | Yes | 1 |

Every route uses explicit `--freq 100`, strict timing failure, the same copied
combined nextpnr executable, pins-only diagnostic LPF, and existing PLL/EFB
preparation. All three diagnostic hard-cell flags remain explicit. Every job
has a 180-second bound; none uses `--timing-allow-fail`. Exit 1 is the actual
100 MHz timing failure, not a successful timing result.

No-carry reduces physical carry use but worsens the route estimate and is
rejected. Omitting ABC's final area-recovery pass improves its explicit-script
control but remains below the previous 75.52 MHz baseline. It is not recommended
for adoption. A small change in mapping order/script entry can produce a
different placement and route: the explicit-script control must not be silently
substituted for the earlier baseline.

The ABC control follows the actual `help abc9_exe` default:

```text
&scorr; &sweep; &dc2; &dch -f -r; &ps; &if {W} {D} {R} -v; &mfs
```

Both final ABC variants use `abc9 -W 300 -maxlut 4 -script <file>`, after the
normal `map_ffram`/gate/FF passes and before normal `map_cells`/checks. The only
script change removes the final `&mfs`. A preliminary `-maxlut 5` probe admitted
PFUMX cells, so it was not used for the LUT4-only timing comparison. Those two
preliminary mappings were synthesis-only, with 4,543/4,595 LUT4 and 811/820
PFUMX respectively; they were not routed or accepted.

All final mappings pass `check -assert`. No-carry and both final ABC variants
preserve the paired baseline's hard-cell parameters, including all DP8KC INIT
contents, FIFO, PLL, EFB and ODDRXE parameters. Parameter identity does not prove
surrounding logic equivalence or timing. `-no-rw-check`, register retiming,
`-dff`, weakened resets, and modified initialization were not used.

## No-carry sequential proof investigation

The 18-FF difference was investigated rather than assumed harmless. The proof
compares the final default and no-carry mapped fabric using the pinned Yosys
LUT/carry/FF functional models. Unchanged RAM, FIFO, PLL, EFB, ODDRXE and IO
primitives become explicit boundaries: each primitive output is a shared
arbitrary input, and each primitive input is an observable comparison output.
Tristate data/enable controls are compared digitally; pad electrical behavior
is not modeled. Primitive parameters are checked separately. This is a
compositional fabric experiment, not a substitute hard-cell implementation.

The first broad attempt retained generated internal signal names and timed out
at 180 seconds. A second attempt retained original-source signal names, hid
implementation-generated LUT/FF/carry names, and used `equiv_struct`,
`equiv_simple -seq 2`, and `equiv_induct -seq 4`. It proves all **3,333** remaining
equivalence points; 42 require induction, whose induction step closes at one
cycle. No unknown-cell-ignore option is used.

This result is deliberately conditional. `help equiv_induct` documents a weak
contract: the circuits do not diverge once their observable equivalence points
have been synchronized for the required preceding cycles. It does not by itself
prove startup synchronization. A separate initialized four-cycle SAT miter,
with shared defined external inputs and the primitive-model initial values,
expands to approximately 13.3 million variables/35.5 million clauses and times
out at 180 seconds. **The initialized base case is unproven.** Therefore the
conditional result is not accepted as a complete safety/equivalence proof.

### Clock, reset and initialization scope

The mapped-cell audit finds one FF clock in each candidate: every FF uses the
original `clk` net with `CLKMUX=CLK`. All 3,023 default and 3,005 no-carry FFs use
`SRMODE=LSR_OVER_CE` and `LSRMODE=LSR`; none has an inverted clock or asynchronous
FF reset mode. REGSET populations are:

| Model initialization | Default | No-carry |
|---|---:|---:|
| RESET | 2,964 | 2,946 |
| SET | 59 | 59 |

Yosys SAT time steps therefore model this single synchronous fabric clock.
Neither `clk2fflogic` nor `async2sync` is used. The proof does not establish
relative hard-cell clock phases, FIFO/RAM cross-clock behavior, synchronizer
metastability, external bus setup/hold, power-up/GSR electrical behavior, or
CDC safety. Primitive-model initialization is not a physical startup
qualification. The functional model source `lattice/common_sim.vh` SHA-256 is
`3d55fcb1b659f9a99e081d0e8cd3e0a74fb8d659644103db9ad10b04a64ce75d`.

## Artifacts and disposition

All generated evidence remains in the PhosphorOS workspace's ignored
`build/sc64-open-timing-options2/`: `route.py`, `route-results.json`,
`abc.py`, `abc_route.py`, `abc-route-results.json`, all per-case logs/commands,
`equiv_prepare.py`, `equiv_source.py`, `equiv-source.log`, `initial.ys`,
`initial.log`, `clock-audit.json`, and `proof-summary.json`. Initial failed
frontend attempts are diagnostic setup failures, not proof results.

The prepared no-carry netlist SHA-256 is
`8abb0aef61bf950e16efb3a882425e7176e188cd580a806058d8e32101437e13`.
Its route report records the unchanged executable and LPF hashes. Scripts and
logs preserve the exact commands; each Yosys/SAT/nextpnr process has an explicit
180-second bound. These results had no independent parent rerun when this agent
report was written; any later verification belongs in a separate record.

No candidate exceeds the existing paired baseline, and all fail 100 MHz even
under incomplete internal timing models. None is recommended for production.
A future proof effort could partition the initialized miter into smaller cones,
but that was not run here. Complete primitive timing/constraint semantics and
physical qualification remain necessary before treating any reported frequency
as safe device operation. No commit, remote push or hardware operation is part
of these experiments.
