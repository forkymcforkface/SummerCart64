# Cached LZW plus compositor, serialized external-memory model

Experimental sources only; excluded from production FPGA builds. Run with the
same Python/Verilator/g++/make environment as the parent tests:

```sh
sh /path/to/tests/gif/cached-compositor/run.sh ORIGINAL.gif /path/to/build/cached-compositor
```

The runner uses the [compositor fixtures](../compositor/fixtures.py),
[cached LZW](../cached/gif_lzw_cached.sv) and
[external-canvas compositor](../compositor/gif_ci8_compose.sv). Generated files
stay in the explicit build directory. Supported GIF semantics, exported GPD1
packets and generation/reference rules match the [compositor test](../compositor/README.md).

This bounded research test substitutes the cached dictionary core into the
original-GIF compositor pipeline. There is one outstanding memory service across
dictionary and canvas requests. When both request, the next grant alternates.
The selected request and write data must remain stable until acknowledgement.

Dictionary entries contain 20 useful bits in modeled 32-bit slots and cost two
16-bit beats. Canvas byte accesses cost one modeled 16-bit byte-lane beat; no
packed adjacent reads or read/modify/write penalties are modeled. Each grant
waits `cycles%3 + (dictionary ? 4 : 2)` countdown cycles, then acknowledges.
This is an explicit synthetic latency/accounting model, not the actual SC64
16-bit SDRAM controller. Dictionary and canvas never complete in parallel.
It omits refresh, PI and MCU competition, packet writes into cart RAM and source
compressed-byte fetch traffic; host ready-valid injection supplies source bytes.

The actual cached RTL, compositor RTL, original compressed payloads, independent
LZW/CI8 references and GPD1 receiver checks are used. The packet cadence and
supported original-GIF subset are unchanged from the compositor experiment.

The wrapper exposes decoder and compositor status separately. It does not own a
production combined cancel/retirement protocol or safe cart address allocation.
Fault probes exercise the inherited canvas cases; the cached core's standalone
suite owns its dictionary fault/cancel cases. No combined dictionary-pending
cancellation claim is made by this full-frame run.

The cached core maps separately to 6 DP8KC and compositor to 1 DP8KC. Seven total
blocks are a component estimate, not integrated SC64 fit or timing closure.
Hardware conversion, host parsing cost, consumer timing and 60 FPS remain
unmeasured by this simulation.

## Complete original Final Fight results

All **1,717 original images pass**, producing the same **430 packets and
10,245,568 bytes** as the dedicated-dictionary pipeline. All sixteen exported
packets additionally compare byte-for-byte with that pipeline. Full-run canvases
and every packet are independently checked against original decoded indices.

- 1,860,815,157 modeled cycles; maximum image plus optional packet 1,937,164.
- Canvas: 142,028,608 reads and 15,379,999 writes.
- Dictionary: 22,448,934 reads and 23,928,675 writes.
- 250,163,825 modeled 16-bit beats; 823,752 grants encounter both requesters.
- Inherited cancellation, invalid metadata, initial/empty packet, stale ACK and
  canvas-memory-error probes pass separately.

The dedicated-dictionary result used a different, faster canvas latency model;
its 880,954,077 cycles are not an isolated cache A/B comparison. This run proves
correctness with serialized external traffic, not an accepted speed improvement.
Both models omit essential real cartridge traffic and cannot predict UI FPS.
