# Registered DMA completion predicates

Research-only candidate for `fw/rtl/memory/memory_dma.sv`. Production source,
configuration encoding, cartridge state and firmware are untouched. The
original critical path in the fixed 75.52 MHz diagnostic baseline runs from
`memory_usb_dma_inst.mem_bus_remaining_bytes[20]` through zero/end/stop/start
logic to the counter clock enable (13.24 ns). This experiment tests removing
the wide current-counter comparisons from that path.

`run.py` generates an isolated candidate that registers `last_transfer` and
`almost_last_transfer` alongside every original remaining-byte assignment.
Both predicates use the exact assigned expression, including 27-bit unsigned
subtraction and its wraparound. Assignment ordering remains unchanged, so the
original unaligned-start override still wins. No state, request, ACK, reset,
stop, start, FIFO or byte-swap logic is changed; no extra transfer cycle is
introduced. Six counter assignments and both original predicate anchors are
required before generating a candidate.

## Actual-source equivalence

```powershell
docker run --rm -v "${PWD}:/repo" sc64-open:diagnostic-lpf /usr/bin/python3 -B /repo/vendor/sc64/tests/open-toolchain/memory/dma-flags/run.py /repo/build/sc64-open-release/source /repo/build/sc64-dma-flags/proof-review
```

The runner uses the actual DMA source and all three original interfaces with
a port-only wrapper; sv2v conversion precedes Yosys `equiv_simple -undef`,
`equiv_induct -undef -seq 8` and `equiv_status -assert`. All **313** matched
internal/output equivalence points pass in the simple step; induction has no
remaining points. Inputs remain unconstrained, including dynamic byte swap,
unaligned addressing, transfer lengths, stop/start, FIFO stalls and memory ACK.
The source's undefined startup state remains undefined under `-undef`; this
is not a physical power-up or defined-reset-values proof.

A separate negative control changes the start-length zero predicate to test
one instead. It fails equivalence with two unproven points. A tool error or
timeout is not accepted as this expected negative result. Fresh output
directories are mandatory and must lie outside the tests tree.

Verified logs and identities: `build/sc64-dma-flags/proof-final-strict/`.
`result.json` records source/candidate hashes and proof scope. No bitstream is
written by the proof. Successful RTL equivalence is necessary but does not
establish timing, electrical behavior or FPGA configuration correctness.

## Full-design diagnostic comparison

The local experiment driver `build/sc64-dma-flags/full-ab.py` substitutes only
the proven candidate file in the exact release's previously recorded sv2v
source command. `provenance.json` checks every original manifest input hash,
the proven candidate identity, full conversion, checkpoints, pins-only LPF,
and nextpnr executable. The source is official release
`18041e25472075a166292d1195603bcefe9c9688`.

The existing `memory/full.py` performs the same guarded RAM transform and
checks: eight address implications and six physical forwarding blocks pass.
Both variants resume `synth_lattice` from their mapped-RAM checkpoint with
the same options. Both use the existing frozen EFB preparation, original PLL
metadata, exact same router executable, default seed and placement options,
explicit 100 MHz target, and the same three hard-cell diagnostic flags.
There is no `--timing-allow-fail` and no bitstream output.

The completed pair uses the same diagnostic pipeline:

| Variant | LUT4 | CCU2D | FF | Pre-route | Routed | Exit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Fresh baseline | 4,448 | 402 | 3,023 | 64.49 MHz | 75.52 MHz | 1 |
| Registered predicates | 4,461 | 480 | 3,027 | 66.51 MHz | 78.23 MHz | 1 |

Both complete routing and fail the explicit 100 MHz requirement. The internal
estimate improves 3.59%, from approximately 13.24 ns to 12.78 ns, at the cost
of 13 LUT4, 78 carry cells and four FFs. The candidate critical path moves to
the SD DMA remaining-byte arithmetic. This is a promising source-equivalent
diagnostic candidate, not a hardware-accepted performance change. Resource
growth and a single fixed-seed comparison limit the conclusion. No production
source is changed; integrated hardware acceptance remains required.
Results/logs are in `build/sc64-dma-flags/{baseline,candidate}/`.
All frequencies
remain incomplete internal estimates: missing hard-cell timing and original
external constraints prevent hardware qualification regardless of improvement.

Parent review and reproduction pass: `parent-proof/` proves all 313 points and
rejects the deliberately wrong flag. `parent-route/` independently routes the
same hashed candidate netlist with unchanged executable and LPF, reproducing
78.23 MHz and the required exit 1 at 100 MHz. Inputs are hashed before and after.
The candidate remains isolated research; no production behavior is deployed.
