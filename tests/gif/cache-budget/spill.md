# Local phrase stack with external spill

This research derivative keeps the successful 512-entry dictionary cache and
replaces its 4 KiB local phrase stack with 512 local bytes plus an external
byte-memory spill port. It preserves the complete 4096-byte stack bound.
The reference decoder and production RTL remain unchanged. Generated RTL,
fixtures, drivers, logs and mapped netlists belong in the specified build
directory.

## Reproduce

First produce a passed 512-entry result with [run.py](run.py), following the
image and original GIF provenance in [README.md](README.md). Then run:

```powershell
docker run --rm -v "${PWD}:/repo" --entrypoint python3 sc64-gif-test:local `
  /repo/vendor/sc64/tests/gif/cache-budget/run_spill.py `
  /repo/build/sc64-cache-budget/512 `
  /repo/build/sc64-cache-budget/spill-repeat
```

The output directory must be new. The runner verifies the passed input RTL
hashes and records source, fixture, generated driver, generated RTL and mapped
netlist hashes, tool versions and simulation results. It fails on a simulation
or synthesis error. Use the same pinned image as the paired cache comparison.

## Memory and cancellation contract

Local addresses 0–511 use one explicitly requested block RAM. Addresses
512–4095 use the new `stack_*` byte-memory port; the port owner must provide
that complete external region. An accepted request remains valid with stable
address, direction and data until ACK. An error ends the decode with failure.
The dictionary and spill requests never overlap in this implementation; the
test rejects simultaneous requests. Integration still needs an actual arena
and a serialized SC64 bus owner for this port.

Cancellation drains an outstanding spill request and also waits for dictionary
cache cancellation. A sticky completion bit retains the cache's cancellation
pulse if it precedes the spill ACK. Reset retains the reference design's
whole-owner reset assumption; reset is not a substitute for cancellation.

Separate registers hold the local RAM read and external spill read. The output
selects the appropriate register by remaining phrase length. This allows a
synchronous block RAM read without placing external data into its read-register
feedback path. Output acceptance and local prefetch keep the reference cycle
schedule for phrases of at most 512 bytes.

## Verification scope

The suite includes all 1717 original Final Fight images and the reference
malformed-input fixtures, 200 cancellations and four dictionary error/cancel
restart cases. Three added independently decoded, minimum-code-size-2 streams
exercise phrase lengths 512, 513 and 4091, including KwKwK expansion and a full
dictionary. The last stream emits 8,370,186 zero indices. These are synthetic
depth tests, not additional source-animation frames.

Eight spill cases inject read and write errors, cancel pending reads and writes,
hold each cancelled request's ACK more than 700 cycles, and cancel on each
request's ACK edge. Each case checks drain, no subsequent spill request and a
successful fresh decode. Long cancellation explicitly exceeds the cache's
512-entry clearing time. Original-animation zero spill accesses and exactly
1,257,856,312 modeled cycles are assertions, not informational counters.

## Results and limits

The first full derivative passed 1775 fixtures with zero original spill reads
or writes and exactly the paired original cycle count. Its unconstrained
local RAM mapped into distributed storage: 2 DP8KC, 64 TRELLIS_DPR16X4,
961 LUT4, 332 TRELLIS_FF and 155 CCU2D. Its four initial spill fault/cancel
cases passed. That result predates the expanded eight-case cancellation gate.

Putting a block attribute on the shared local/external read register failed
memory mapping. Separating those registers maps the final derivative to
**3 DP8KC, 749 LUT4, 332 TRELLIS_FF and 155 CCU2D**, compared with the paired
reference's 6 DP8KC, 647 LUT4, 300 TRELLIS_FF and 132 CCU2D.
The final full simulation passes all 1775 fixtures and all eight spill cases.
It records zero original spill accesses, 1,257,856,312 original cycles,
22,448,934 original dictionary reads and 23,928,675 original dictionary writes.
The parent independently repeats this full simulation and mapping successfully.

### Varied-byte spill gate

The zero-chain depth tests alone cannot catch every spill-address alias. Run
the additional targeted gate against a passed final spill directory:

```powershell
docker run --rm -v "${PWD}:/repo" --entrypoint python3 sc64-gif-test:local -B `
  /repo/vendor/sc64/tests/gif/cache-budget/varied_spill.py `
  /repo/build/sc64-cache-budget/spill-repeat `
  /repo/build/sc64-cache-budget/varied-repeat
```

It constructs expected bytes directly by extending the previous phrase with a
literal and emitting the newly created dictionary entry. The independent
reference decoder must agree before RTL testing. Three minimum-size-2 frames
reach lengths 513, 1025 and 2046 with xorshift-derived suffixes. A minimum-size-8
frame reaches length 1920; a literal 0–255 prefix followed by xorshift suffixes
ensures every byte value crosses the spill port. The script asserts this
coverage. A pure xorshift trial failed that coverage assertion and is retained
as a failed setup rather than counted as a test pass.

The four-frame gate passes 4,601,407 exact output bytes in 109,128,052 modeled
cycles with 2,301,123 spill reads and the same number of writes. Three deliberate
memory-response mutations fail at the byte comparator:

| Mutation | Detected frame / byte |
| --- | --- |
| Read address XOR 1 | 1 / 132354 |
| Read data XOR 1 | 0 / 131840 |
| Read data truncated to two bits | 3 / 134425 |

These zero-based offsets are within separate synthetic frames. An initial
negative-control gate unnecessarily demanded a mismatch in frame zero and
rejected the correctly failing address mutation in frame one; the final gate
accepts a byte mismatch in any frame. All positive and negative commands have
finite timeouts and their outcomes and hashes are retained in `result.json`.

Agent artifacts are under `build/sc64-cache-budget/spill-run1`, `spill-final`
and `varied-final3`; rejected setup logs remain in `varied-complete` and
`varied-complete2`. The parent full repeat is `parent-spill`. These paths are
workspace outputs, not committed golden fixtures.

The three-block decoder plus the existing one-block compositor reaches the
four-block spare EBR budget. This arithmetic is not an integrated fit result:
additional logic, external stack addressing and shared bus integration still
need verification, placement and timing analysis. The simulation uses bounded
synthetic memory latency and is neither actual SDRAM timing nor a UI benchmark.
No FPGA image is emitted or flashed by this runner. No hardware safety,
100 MHz timing or frame-rate claim follows from these component results.

Parent verification also repeats the varied-byte gate in `parent-varied`, with
identical positive counts and all three mutation failures. An additional mapping
with the current open-toolchain Yosys 0.68+195 retains three DP8KC and no
TRELLIS_DPR16X4, with 764 LUT4, 332 FF and 155 CCU2D. The source RTL hashes are
unchanged before/after that mapping; evidence is `parent-current-yosys`.
Logic counts from different Yosys versions are not an isolated performance A/B.
