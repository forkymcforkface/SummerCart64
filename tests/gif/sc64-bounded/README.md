# Canvas-bounded original-GIF decoder

This experiment derives a 512-byte local stack from the unchanged cached LZW
decoder and uses it in the existing cart transport cancellation wrapper. It
adds no spill port, scratch arena, arbiter client or production RTL change.
The [phrase-bound argument and gate](../phrase-bound/README.md) establish why
the existing 76,800-pixel output domain needs at most 391 emitted phrase bytes
and at most 392 bytes in a valid attempted walk before output-overrun rejection.

The generated decoder rejects output limits above 76,800 at start. Its WALK
guard rejects a stack size of 512 before the literal write or dictionary-read
path leading to PUSH; all physical indices use nine bits. The guard remains
mandatory for corrupt external dictionaries. Larger output jobs must use the
unchanged general decoder or another explicitly supported implementation.
This does not silently truncate larger images.

## Reproduce

Use the pinned `sc64-gif-test:local` image documented in the
[cache comparison](../cache-budget/README.md). From the PhosphorOS root:

```powershell
docker run --rm -v "${PWD}:/repo" --entrypoint python3 sc64-gif-test:local -B `
  /repo/vendor/sc64/tests/gif/sc64-bounded/run.py `
  "/repo/build/sc64-ui-research/original-final-fight/Final Fight/images/background.gif" `
  /repo/build/sc64-bounded/core-repeat --mode core
```

Run again with a different output path and `--mode transport` for the paired
eight-frame actual-controller smoke and twelve cancellation cases. All output
directories must be new and outside tests. Source and generated artifact
hashes, tool versions, results and command logs are recorded. Tests, builds
and synthesis have finite timeouts. `--focused` is core-only: it keeps the
first original frame, all four added boundary cases and the cancellation and
memory-fault checks. It is explicitly labelled in the manifest and cannot
substitute for the complete original-animation run.

Transport mode optionally accepts `--mux GENERATED_MUX.sv`. Only the candidate
uses that selector; the paired reference keeps its original decoder and mux.
The supplied file hash is recorded. This tests the separate selector change
after the bounded decoder alone already matches the baseline. Both normal
outputs must match exactly, including counters. The cancellation wrapper,
scratch adapter, source/output DMA, arbiter and SDRAM controller remain the
existing source files.

## Checks and observed results

The initial full core suite passes 1776 fixtures: all 1717 original frames,
the reference malformed-input cases, a tight 391-byte phrase, a valid 392-byte
phrase rejected at the lower output limit, and immediate rejection of limits
76,801 and 0xffffffff. It also passes 200 cancellations, four reference memory
error/cancel/restart cases and an injected self-referential dictionary chain.
The valid 392-byte stream is independently decoded at its complete 77,028-byte
size before it becomes an overrun fixture. Original performance remains
exactly 1,257,856,312 modeled cycles, with 22,448,934 dictionary reads and
23,928,675 writes; the full runner asserts the cycle count.

The strengthened corruption gate requires termination within 4096 clocks of
the first poisoned dictionary read. It passes in 2559 clocks. A separate
negative control retains the physical 512-byte stack but changes its guard to
4096; this fails specifically at that gate. Reproduce it against a passed
focused result:

```sh
python3 -B tests/gif/sc64-bounded/guard_negative.py FOCUSED_RESULT NEW_OUTPUT
```

Component mapping with Yosys 0.52 produces **3 DP8KC, 656 LUT4, 300 TRELLIS_FF
and 142 CCU2D**. The unchanged cached decoder uses six EBRs. This bounded path
also avoids the larger spill decoder and all additional memory ownership.

Fresh actual-controller baseline and bounded candidate runs match exactly:
eight original Final Fight frames take 16,439,680 modeled clocks, read 148,670
compressed bytes in 74,338 source words, and emit two packets totaling 86,784
bytes. Output writes and DMA readback each use 43,392 words. All twelve pulse
and held cancellation cases pass, with 510–517 modeled clocks before retirement
and exact decode/packet/readback after restarting at generation 2.

The separate explicit-priority mux candidate also reproduces those normal
results and all twelve cancellations. Its equivalence and resource evidence
belong to that experiment; this runner only checks the transport behavior.

Agent logs are in `build/sc64-bounded/agent-core`, `focused`, `agent-transport`
and `agent-mux`. These are disposable workspace outputs, not golden fixtures.

## Remaining limits

The three-block decoder plus the compositor's one block meets the four spare
EBR count arithmetically. Full accelerator and stock-device fit, timing and
runtime resource admission require separate checks. This model includes actual
memory RTL and command-level SDRAM validation, but memory-chip timing, peer
request engines and FIFO storage are simulation models. No board performance,
100 MHz closure or firmware safety claim follows. Runtime source parsing, SD
staging and production lifecycle integration remain outside this experiment.
