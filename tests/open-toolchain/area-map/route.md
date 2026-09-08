# Bounded LZW-only placement/routing diagnostic

This is a physical-tool diagnostic for the LZW-only soft-carry integration,
not a bitstream or a deployed decoder. The [area probe](README.md) owns the
mapping comparison. The input is its already prepared physical netlist;
this runner neither changes pin assignments nor prepares new hard-cell
configurations.

```sh
python3 -B route.py \
  --executable /repo/build/sc64-open-timing-options/nextpnr-machxo2 \
  --physical /repo/build/sc64-area-map/lzw/soft-carry/physical.json \
  --lpf /repo/build/sc64-open-memory/parent-full/pins-only-diagnostic.lpf \
  --output /repo/build/sc64-area-route/FRESH_DIRECTORY
```

Run inside `sc64-open:diagnostic-lpf`. The helper verifies the exact inherited
nextpnr executable and diagnostic LPF hashes, fixes the device to
LCMXO2-7000HC-6TG144C, requests **100 MHz**, and retains all three explicit
ODDR/EFB/FIFO diagnostic flags. No timing-allow-fail, clock reduction,
alternative placement heuristic or bitstream output is used. The process
has a 120-second bound; result JSON records the actual tool exit or 124 for
timeout, commands, input hashes, completion state and frequency messages.

The old `lzw/soft-carry/mapped.json` and reviewed
`review-lzw/soft-carry/mapped.json` are byte-identical:
`c189b8c3d89e11c16140b1cee01412570d9ea5ae9410877b3bf43a5800722a35`.
Their independently prepared physical JSONs are also byte-identical:
`1e119761b3652b70b9bea735d6995d52e088666e67232a03d370a891604642ac`.
The existing pack contains 6,630 TRELLIS_COMB, 3,765 FF, 101 IO, 25 DP8KC
and 24 RAMW cells. The FIFO diagnostic packs four FIFO primitives into
marked DP8KC cells; this is not removal of four FIFO memory blocks.

## Observed result

`build/sc64-area-route/lzw/result.json` records **timeout 124 at 120 seconds**.
Packing and four initial analytic iterations complete; the final log line
enters the main analytical placer with 8,390 cells and a reported maximum
of 13,910,175 placement attempts per cell. No completed placement, routing,
frequency estimate or routed JSON is produced. This is an unresolved physical
placement result, not proof of either fit or impossibility.

The helper propagates timeout as CLI exit 124 and other tool failures as
nonzero exits after writing the report. Even tool exit zero fails if routing
did not complete or no routed netlist exists. The original timed run preceded
this exit-propagation correction; focused mocked execution verifies it using
the same real executable/LPF hash prerequisites. No longer or weaker physical
follow-up was attempted.

## Comparison and qualification boundary

The historical [stock diagnostic](../memory/timing-options.md) uses the same
executable SHA256 `c6fac50f2c98a7f94aadaffa29793900e8d1e5965b3905b8097274f749e9e607`,
LPF SHA256 `cea5c416f963c8302b33af7c2a02ba60a951b60cc0628f486da3351320b3369e`,
device, three diagnostic flags and explicit 100 MHz request. Its default
route completed at an internal estimate of 75.52 MHz and exited 1 for timing.
That is a useful tool/control reference, not a paired decoder speed result:
the stock design differs and its timeout allowance was 180 seconds.

Packing below 6,864 combinational resources does not prove placement,
routing or timing closure. Dedicated locations, distributed RAM, FF pairing,
fanout and routing resources still constrain the physical design.
The pins-only LPF is a documented diagnostic subset, not enforcement of all
original external delays/false paths. Known FIFO/EFB/ODDR timing and
configuration gaps remain. Consequently even a tool exit zero would not
qualify a hardware image or establish 100 MHz board operation.

No hardware, production source, license settings or remote repository changes
are part of this experiment. Logs remain under `build/sc64-area-route/`.
