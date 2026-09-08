# Four-client CFG mux and stock arbiter progress

The four-client mux's request gap does let lower-priority clients reach the
actual stock `memory_arbiter`. It does not change the stock USB-over-SD
priority. Continuous USB traffic can still starve SD; the same behavior occurs
with CFG disabled entirely.

This test instantiates the frozen generated `gif_transport_mcu_mux`, the
unchanged stock arbiter and actual interface declarations. A bounded delayed
`mem_bus` responder replaces the SDRAM controller and chip. This isolates
arbitration and does not measure actual SDRAM or board timing. All requests
are reads of distinct fixed SDRAM words, held until acknowledgement.

```powershell
docker run --rm -v "${PWD}:/repo" --entrypoint python3 sc64-gif-test:local -B `
  /repo/vendor/sc64/tests/gif/transport-fairness/run.py `
  /repo/build/sc64-transport-mcu/frozen/gif_transport_mcu_mux.sv `
  /repo/build/sc64-transport-fairness/repeat
```

The output path must be new. The runner records all source hashes, tool version
and per-case observations. Build and simulation timeouts are 120 seconds each.
The complete matrix contains 54 cases, each required to finish exactly 3000
memory grants within 100,000 clocks. A partial run is an error.

## Matrix and checks

Response delays are 0, 3 and 17 countdown clocks. These are responder settings,
not end-to-end transaction durations. Each setting runs with PI reservations
disabled and with 32-clock windows every 257 clocks. N64 requests during those
windows remain pending through ACK. The test checks that new requests chosen
inside a reserved window belong to N64; already-issued transactions may finish
after a reservation begins.

Three CFG configurations are compared:

- Continuous stock CFG requests, without the four-client mux. This is the
  starvation negative control for USB and SD.
- Continuous scratch, source, packet and MCU requests through the actual
  four-client mux, with `gif_admit` held high throughout.
- CFG disabled, to expose the stock USB/SD priority without CFG interference.

USB/SD workloads are continuous simultaneous requests, paired simultaneous
single requests followed by a 19-count cooldown after both finish, and
continuous SD with USB disabled. In paired mode each side receives exactly the
same offered work; a request remains pending until completed. Continuous USB
is intentionally different from the paired workload and has no SD fairness
expectation.

The scoreboard checks stable memory requests, exactly one ACK owner, matching
address and read data, PI reservation priority, and at most one grant of
difference between the four continuously pending mux clients. Every USB/SD
selection must occur with CFG request low at the arbiter's selection edge;
the number of those observed gaps must equal completed USB/SD grants. This
directly checks the gap's role rather than merely inferring it from totals.

## Results

All 54 cases pass. One representative setting, delay 17 with PI windows,
produces the following counts after 3000 total grants:

| CFG mode / load | Scratch | Source | Packet | MCU/CFG | USB | SD | N64 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Continuous stock CFG / paired USB+SD | 0 | 0 | 0 | 2628 | 0 | 0 | 372 |
| Four-client mux / continuous USB+SD | 333 | 333 | 333 | 332 | 1297 | 0 | 372 |
| Four-client mux / paired USB+SD | 333 | 333 | 333 | 332 | 649 | 648 | 372 |
| Four-client mux / SD only | 333 | 333 | 333 | 332 | 0 | 1297 | 372 |
| CFG disabled / continuous USB+SD | 0 | 0 | 0 | 0 | 2628 | 0 | 372 |
| CFG disabled / paired USB+SD | 0 | 0 | 0 | 0 | 1200 | 1200 | 600 |

In the four-client paired case, longest observed pending intervals are 190
clocks for each CFG client, 76 for USB and 114 for SD. Continuous SD behind
continuous USB waits for the entire 57,000-clock observation without a grant.
Those finite measurements are not proven upper bounds or an infinite-trace
liveness guarantee. The disabled CFG clients' synthetic pending counters are
irrelevant and must not be interpreted as measured active-client starvation.

The actual stock priority is N64, then CFG, then USB, then SD. The mux releases
CFG between grants, creating lower-priority opportunities. SD needs USB to
release its request in one of those opportunities. No guarantee applies under
unbounded PI reservation, an unresponsive memory target or indefinitely
asserted higher-priority traffic.

Agent results are in `build/sc64-transport-fairness/frozen/result.json`; earlier
rounds remain under `agent` and `final`. The parent independently repeats the
complete strengthened matrix in `build/sc64-transport-fairness/parent-final`.
These are generated observations, not committed golden files. No mux policy,
stock RTL, firmware image or hardware state changes in this experiment.
