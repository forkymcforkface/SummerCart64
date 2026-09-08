# Bounded SC64 timing-option experiments

These tests compare open-toolchain implementation options for the unchanged
SC64 v2.20.2 RTL, after the [guarded RAM transform](README.md). They do not
change RTL, memory semantics, firmware, or hardware. All frequencies below are
incomplete internal nextpnr estimates: missing primitive timing arcs and the
unimplemented original LPF external constraints still prevent qualification.

## Synthesis options

The fixed input is the guarded `mapped-ram.json` checkpoint, SHA-256
`572ad1927fe56956dac55e4324259f891ed032bae6bcaec2805a065c07a7aab4`.
A fresh paired baseline is necessary because restarting Yosys from a serialized
checkpoint changes optimizer naming/order and ABC mapping. Its 4,448 LUT4
result is distinct from the earlier full runner's 4,531 LUT4 result.

| Option | LUT4 | CCU2D | FF | PFUMX | L6MUX21 | Verification |
|---|---:|---:|---:|---:|---:|---|
| Paired default | 4,448 | 402 | 3,023 | 0 | 0 | Synthesized and routed |
| `-widelut` | 4,997 | 402 | 3,023 | 1,136 | 161 | Synthesized and routed; rejected |
| `-noccu2` | 4,780 | 0 | 3,005 | 0 | 0 | Synthesis only |
| `-widelut -noccu2` | 5,326 | 0 | 3,005 | 1,117 | 174 | Synthesis only |

All four pass Yosys `check -assert`, retain 18 DP8KC, four FIFO8KB and eight
LUT RAM cells, and preserve every hard-cell parameter, including RAM INITs,
relative to the paired final baseline. The normal `lattice_gsr` pass resolves
pre-map `GSR=AUTO` to `DISABLED` in every case. Parameter equality is not
whole-design equivalence; the 18-FF reduction with `-noccu2` requires separate
review before adoption. Those two variants were not routed or accepted.

`-widelut` completes routing but reports 75.01 MHz versus the paired default's
75.52 MHz. Both explicitly target 100 MHz and exit 1 for timing. Wide-LUT mapping
increases logic/mux use without improving this result, so it is rejected.

`-dff` and retiming were not attempted. `synth_lattice -dff` runs `zinit -all`
and passes registers through ABC9, requiring explicit state/initialization
proof. `-no-rw-check`, timing-error overrides and source behavior changes were
not used. ABC9's default already requests its best possible logic delay;
providing a relaxed `-D` target is not automatically an improvement.

## Placement-only experiment contract

Exactly three additional runs use the same paired baseline netlist, LPF and
executable, changing one setting each:

- `--placer-heap-timingweight 20`, versus default 10;
- `--placer-heap-critexp 3`, versus default 2;
- `--seed 1`, versus the backend's fixed default seed.

The actual binary's help confirms those options/default weights. Every run
uses explicit `--freq 100`, strict timing errors, a 180-second timeout, and the
same default HeAP placer/router1. No `--timing-allow-fail` is used. Route
completion is recorded separately from timing failure. The three input hashes
are checked before and after every invocation. The sweep stops after these
three variants regardless of improvement.

The netlist includes only the existing diagnostic preparations: the frozen
[EFB dedicated-tie preparation](../efb/inactive/README.md), and PLL analog
attributes recovered from the original generated wrapper. The latter preserves
source values rather than inventing them. All three untimed hard-cell diagnostic
flags remain explicit. The LPF here is the existing pins-only diagnostic LPF;
it is not the complete original project LPF and cannot establish external timing.

The earlier parent route's critical internal path crosses the MCU register-read
mux, from address[2] to reg_rdata[10]. It totals 13.82 ns, with 10.46 ns routing
and 3.36 ns logic. That motivated a bounded placement/locality experiment; it
does not establish that a particular heuristic or seed will improve the result.

## Reproduction and evidence

Generated files remain under the PhosphorOS workspace's ignored
`build/sc64-open-timing-options/`. `synthesize.py`, `route.py`, and
`place_sweep.py` record the exact experiment commands; per-case logs, JSON
netlists and results accompany them. No generated candidate is a deployable
firmware image. The copied parent combined backend runs inside the isolated
`sc64-oddr-agent` container.

To repeat one placement invocation with the retained fixed inputs:

```sh
/repo/build/sc64-open-timing-options/nextpnr-machxo2 \
  --device LCMXO2-7000HC-6TG144C \
  --json /repo/build/sc64-open-timing-options/baseline/physical.json \
  --lpf /repo/build/sc64-open-memory/parent-full/pins-only-diagnostic.lpf \
  --oddr-diagnostic --efb-routing-diagnostic --fifo-routing-diagnostic \
  --freq 100 --placer-heap-timingweight 20 --write /out/fresh-result.json
```

Use an external 180-second process timeout as the sweep driver does. Replace
only the final heuristic option to repeat another case. The source checkout,
Yosys version, source-conversion hash and RAM-proof limits are documented in the
[parent RAM report](README.md). These runs were not independently reproduced
at the time this agent report was written; parent verification must be recorded
separately. No physical timing measurement, hardware flashing, source commit or
remote push is part of this experiment.

The parent independently repeats the fixed paired baseline with the recorded
executable and input files: routing completes and exits 1 for the 100 MHz
target, reproducing 64.49 MHz before routing and 75.52 MHz afterward. Evidence:
`build/sc64-open-timing-options/parent-baseline.log` and `parent-baseline.json`.
The individual rejected variants remain agent-run results with reviewed logs.

Fixed placement input SHA-256 values:

| Input | SHA-256 |
|---|---|
| Combined nextpnr executable | `c6fac50f2c98a7f94aadaffa29793900e8d1e5965b3905b8097274f749e9e607` |
| Prepared baseline `physical.json` | `58a84825c2fb62f02c589a8cb261e45b450f005e39bc55544665ae0571c581c8` |
| Pins-only diagnostic LPF | `cea5c416f963c8302b33af7c2a02ba60a951b60cc0628f486da3351320b3369e` |

## Placement results

| Fixed-netlist case | Pre-route estimate | Post-route estimate | Route complete | Exit | Disposition |
|---|---:|---:|---|---:|---|
| Reused paired baseline | 64.49 MHz | 75.52 MHz | Yes | 1 | Reference; fails 100 MHz |
| Timing weight 20 | 65.98 MHz | 64.73 MHz | Yes | 1 | Rejected; worse |
| Criticality exponent 3 | 64.49 MHz | 75.52 MHz | Yes | 1 | No improvement |
| Seed 1 | 63.57 MHz | 71.96 MHz | Yes | 1 | Rejected; worse |

All three cases finish within their 180-second limit (approximately 46.4,
51.9, and 54.9 seconds respectively). No input hash changes. The routed JSON
confirms criticality exponent 3 was applied even though its reported frequency
matches baseline. No timing failure is counted as a timing pass.

No candidate improves the fixed baseline, so none is recommended for adoption.
The sweep ends here as specified; it does not rule out every other seed or
placer configuration. The more fundamental remaining work is complete timing
semantics and constraints, followed by diagnosis of the constrained critical
paths. These limited heuristic experiments do not justify changing functional
RTL or declaring 100 MHz operation safe.
