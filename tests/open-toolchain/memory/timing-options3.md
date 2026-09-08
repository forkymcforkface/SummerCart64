# Router and simulated-annealing follow-up

Three parent-run experiments use the unchanged netlist, LPF and executable
hashes in [the paired baseline](timing-options.md), whose completed route
reports 75.52 MHz. Each changes one documented option, targets 100 MHz with
strict timing failure, and has a 180-second subprocess bound. No source,
memory semantics, clock rate or hardware is changed.

| Option | Outcome | Post-route estimate | Disposition |
| --- | --- | ---: | --- |
| `--router router2` | Route completes; exit 1 for timing | 41.81 MHz | Reject |
| `--tmg-ripup` | 180-second timeout during routing; exit 124 | None | Incomplete, not an improvement |
| `--placer sa` | Relative-chain legalization fails; exit 125 | None | Reject this invocation |

Router2 reaches iteration 265 with `overused=0 overuse=0 archfail=0` and
then reports timing failure. The initial driver checks router1's literal
`Routing complete` and therefore records a false completion flag for router2.
`reviewed-results.json` corrects that flag from the actual log; the original
result and log are retained. The timing estimate remains a failure.

Simulated annealing runs through iteration 190 and fails when legalizing a
relative chain beginning in `memory_sd_dma_inst.mem_bus_unaligned_start`.
It does not reach routing or produce a usable frequency result. The timeout
does not prove timing-driven rip-up can never finish; it establishes only
that this bounded attempt supplies no accepted result.

The independent input SHA-256s are checked before and after each invocation.
All existing hard-cell diagnostic flags remain explicit and the LPF is the
same pins-only diagnostic file. Consequently even a higher frequency would
not establish complete primitive or external timing qualification.

Ignored evidence lives in `build/sc64-open-timing-options/continued/` in the
parent workspace: per-case command JSON, route logs, original/reviewed results
and any generated diagnostic netlists. `continued.py`, `continued.log` and
the actual executable's `continued-help.log` sit alongside that directory.
The container image is `sc64-open:diagnostic-lpf`; the copied executable is
the pinned combined backend from the paired baseline, not a substituted
image executable. No candidate or bitstream is deployed.
