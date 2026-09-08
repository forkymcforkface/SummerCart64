# Compact widths for the bounded LZW decoder

This derivative reduces active-state datapath widths in the
[canvas-bounded decoder](../sc64-bounded/README.md). It retains the same ports,
memory ownership, state transitions, rejection of output limits above 76,800,
stack guard and cancellation behavior. The passed bounded reference and all
canonical RTL remain unchanged.

## Reproduce

Generate a passed full bounded-core result first, then use the pinned
`sc64-gif-test:local` image from the
[cache experiment](../cache-budget/README.md):

```powershell
docker run --rm -v "${PWD}:/repo" --entrypoint python3 sc64-gif-test:local -B `
  /repo/vendor/sc64/tests/gif/compact-lzw/run.py `
  /repo/build/sc64-bounded/parent-core `
  /repo/build/sc64-compact-lzw/repeat
docker run --rm -v "${PWD}:/repo" --entrypoint python3 sc64-gif-test:local -B `
  /repo/vendor/sc64/tests/gif/compact-lzw/check.py `
  /repo/build/sc64-compact-lzw/repeat-proof
```

Output directories must be new and outside tests. The full runner validates
the passed reference artifact hashes and records its source, driver, fixture,
generated RTL and tool provenance. Every command has a finite timeout. A
failed build, missing negative-control rejection or partial simulation is not
a pass. The generated usable decoder is `candidate.sv`; its dictionary module
is the unchanged `cached_dictionary.sv` from the supplied bounded result.

## Width invariants

- `emitted` and `limit` use 17 bits instead of 32. Valid starts enforce
  `limit <= 76800`. Phrase output begins only after checking its length against
  the remaining space, so accepted output maintains `emitted <= limit`.
- The reservoir uses 19 bits instead of 24. During a valid job the code width
  is 3–12. A fill occurs only with `available < width`, hence at most eleven
  bits precede the incoming byte and at most nineteen follow it. A consuming
  shift cannot create higher set bits. Start clears the reservoir. Its
  twelve-bit code mask is computed at the width of the observed result.
- `stack_size` uses 10 bits instead of 13. The existing guard stops a walk at
  512 before another write; increments cannot exceed 512 and output decrements
  a positive size. Physical stack addresses and storage remain unchanged.
- `clear_code` and `stop_code` use nine bits. Legal minimum sizes 2–8 produce
  values at most 257. Explicit extensions preserve comparisons against
  twelve-bit codes. `next_code` retains thirteen bits to represent 4096.

Invalid starts still report an error immediately. Narrowed internal values
after such a rejected start are not used for decoding; a valid new start
reinitializes them. These arguments assume the original lifecycle and guards,
not arbitrary injected internal register corruption.

`check.py` enumerates the available-bit and stack-size transitions and checks
legal clear/stop values. SAT gates prove the narrowed reservoir operations and
mask, and output-count arithmetic under the stated active-state bounds.
Eighteen-bit reservoir and sixteen-bit counter controls fail. These are local
invariant and combinational proofs, **not whole-decoder sequential equivalence**.
The full malformed-input and cancellation suite supplies independent RTL
behavior coverage.

## Paired mapping and behavior

All rows use Yosys 0.52 and the same complete component synthesis invocation.

| Cumulative candidate | LUT4 | FF | CCU2D | DP8KC |
| --- | ---: | ---: | ---: | ---: |
| Passed bounded baseline | 656 | 300 | 142 | 3 |
| Output counters | 626 | 270 | 120 | 3 |
| Plus reservoir and mask | 602 | 265 | 120 | 3 |
| Plus stack counter | 593 | 262 | 116 | 3 |
| Plus clear/stop values | 587 | 254 | 113 | 3 |

The final derivative saves **69 LUT4, 46 FF and 29 carry cells**, with unchanged
EBR count. It passes all 1776 fixtures, including all 1717 original Final Fight
frames, bounded-output cases and reference malformed streams. It also passes
200 cancellations, four dictionary error/cancel/restart cases and the corrupt
dictionary guard, which terminates in the same 2559 clocks.

Original-animation results remain exactly 1,257,856,312 modeled cycles,
22,448,934 dictionary reads and 23,928,675 writes. This is an area reduction,
not a measured execution-speed improvement. Deliberately narrowing the counter
to sixteen bits fails completion on original frame zero. An eighteen-bit
reservoir fails the byte comparator on original frame four at byte 73,201;
the actual source animation therefore exercises the nineteenth reservoir bit.

The first compile rejected implicit width expansions after narrowing the
clear/stop registers. Explicit extensions resolve those warnings; none is
suppressed. That failed setup remains in `build/sc64-compact-lzw/agent`.
The successful full run is `build/sc64-compact-lzw/final`, and the independent
local gates are in `build/sc64-compact-lzw/proof-final`.
The parent independently repeats the complete run and local gates in
`build/sc64-compact-lzw/parent` and `parent-check`, with identical outcomes.

Full accelerator integration, combined stock resource fit, routing and timing
remain separate gates. No physical FPGA, production firmware or PhosphorOS
behavior changes in this experiment.
