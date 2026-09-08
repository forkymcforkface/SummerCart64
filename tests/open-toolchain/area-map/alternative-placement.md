# Compact LZW simulated-annealing placement diagnostic

This is one bounded alternative-placement probe of the compact LZW-only
physical input. It produces no bitstream and changes no source, legality,
clock, device, pin or hard-block diagnostic condition. The installed pinned
nextpnr help advertises `--placer` choices `sa, heap`; the command derived from
[`route.py`](route.py) changes only the default heap placer to `--placer sa`.

Run in `sc64-open:diagnostic-lpf` with a fresh output directory:

```sh
python3 -B alternative_placement.py \
  --executable /repo/build/sc64-open-timing-options/nextpnr-machxo2 \
  --physical /repo/build/sc64-stock-lzw-compact/agent/area/soft-carry/physical.json \
  --lpf /repo/build/sc64-open-memory/parent-full/pins-only-diagnostic.lpf \
  --output /repo/build/sc64-area-route/FRESH_DIRECTORY
```

The runner verifies these exact SHA-256 inputs before invoking nextpnr:

- executable: `c6fac50f2c98a7f94aadaffa29793900e8d1e5965b3905b8097274f749e9e607`
- physical JSON: `83ebf876c086953404991ff1643d88b21fa2c023c0ced9606872f45e07134037`
- pins-only LPF: `cea5c416f963c8302b33af7c2a02ba60a951b60cc0628f486da3351320b3369e`

The command fixes `LCMXO2-7000HC-6TG144C`, requests 100 MHz, keeps the
ODDR/EFB/FIFO diagnostic flags, omits `--timing-allow-fail`, and has a
120-second subprocess bound. A timeout returns 124; any other tool failure is
also propagated. Exit zero still requires an unambiguous routing start,
`Routing complete`, and a written routed JSON before the result is accepted.

## Observed result

`build/sc64-area-route/sol-sa/result.json` records **timeout 124 at 120
seconds**. Packing reports 6,546 TRELLIS_COMB, 3,734 TRELLIS_FF, 25 DP8KC,
24 TRELLIS_RAMW and 101 TRELLIS_IO. After placing 104 constrained cells, the
SA flow starts initial placement for 10,330 remaining cells. Its last progress
line is `initial placement placed 9500/10330 cells`. It never prints
`Running simulated annealing placer.`, enters routing, reports frequency, or
writes `routed.json`. The log contains no placement error before the process
bound.

The same compact input under the default analytical placer also times out at
120 seconds with no completed placement, route, frequency report or output
JSON. That run completes four initial analytic iterations and enters the main
analytical placer. The SA and analytical stages are algorithm-specific, so
their progress messages are not a speed comparison. The paired result only
shows that neither placer produces an accepted physical result within its
identical bound; SA supplies no improvement to retain.

The earlier larger stock integration's SA failure at a relative chain is not
reproduced here: this compact attempt times out before SA itself begins. That
difference does not prove the compact input can legalize or route with more
time.

## Qualification boundary

The four FIFO blocks, EFB and ODDRXE remain explicitly unqualified diagnostic
models. The pins-only LPF does not close the original board's external delays
or false paths. Resource fit below 6,864 combinational positions does not prove
placement, routing, timing, primitive configuration, functional correctness,
or hardware safety. No hardware, ROM, SD card, firmware, bitstream or remote
repository is touched by this probe.
