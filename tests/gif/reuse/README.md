# Exact compressed-payload reuse pilot

This standalone research stage compares incoming original GIF compressed bytes
at runtime. It does not accept a precomputed skip flag or use hashes. A hit
requires equal lengths, all 192 metadata bits, session epoch, and every payload
byte, following a successfully committed previous frame with disposal 0 or 1.
There are no production source-list or hardware changes.

```sh
sh tests/gif/reuse/run.sh ORIGINAL.gif /path/to/build/reuse
```

Python only creates test stimuli from the original GIF. It emits bytes and
metadata, never reuse decisions. The C++ driver independently checks expected
equality while the RTL performs the actual comparison through delayed mem_bus
reads. Python, Verilator, g++ and make are required.

## Ownership and interfaces

The caller supplies a non-overlapping, exclusively reserved SDRAM arena and an
even buffer_base. Configuration validates two adjacent 25748-byte scratch banks
inside that arena and below 64 MiB. The maximum payload is 25747 bytes, the
observed Final Fight pilot bound. Zero-length and larger payloads fail loudly;
a production owner needs a fallback for other assets. No payload is kept in EBR.

Start latches length, metadata, epoch and disposal. Metadata is an exact packed
192-bit value, not a digest: the owner must include rectangle, canvas geometry,
LZW minimum, interlace/local-palette state, GCE fields, background and an exact
palette-identity epoch as appropriate. Palette identity must change whenever
palette content changes, without hash-only equality or epoch reuse in a live
session. A separate session epoch prevents reuse across owners/themes. The
stimulus generator verifies one unchanged global palette and packs all actual
Final Fight frame metadata; it does not implement a general runtime GIF parser.

Each accepted byte is stored in the current external bank. While equality
remains possible, the prior committed bank is read and compared byte for byte.
The first mismatch disables further comparison reads but continues storing.
After all declared bytes arrive, result_valid stays asserted. A miss waits for
replay_start and replays the stored payload through a stalled ready/valid output
stream. After the final output byte, commit_valid/commit_success accepts the
new prior identity only when both decoding and composition have succeeded.
Failure invalidates reuse. Unsupported disposal values always miss and replay;
they are never eligible for a later hit.

A hit waits directly for commit_valid. Its owner must still update frame ID,
presentation timing and packet/reference bookkeeping; it must preserve dirty
changes accumulated since the last published packet. This module does not
implement those downstream ownership steps. The owner must commit reuse only
after they succeed. Neither result_hit nor out_last is meaningful without its
corresponding valid signal.

Pulse cancel to drain any issued bus beat and invalidate identity/configuration.
An already-issued write can commit; scratch contents are discarded, not rolled
back. Wait for cancelled and idle before reconfiguration. Reset requires the
whole bus owner to reset together. An incomplete input stream requires explicit
owner cancellation; the RTL does not invent a timeout policy.

## Cost and limitations

This correctness baseline uses one masked word write per incoming byte, one
word read per compared byte, and one word read per replayed byte. It deliberately
accounts for all of these transfers. Packed-word buffering can reduce this
traffic in a separate measured experiment. Reuse cannot be called a performance
win until comparison/staging/replay costs and downstream work are measured
together against the unchanged actual-controller baseline.

The responder checks stable requests, exact scratch bounds and guards, stalls
ACK and sometimes holds ACK high. Tests cover last-byte/size differences, all
192 metadata bits, epoch, disposal, failed commits, cancellation and length
bounds. These are digital mechanics tests with synthetic memory timing, not
actual SC64 arbitration, FPGA fit, timing closure or board playback. The original
GIF framing and downstream decode/compose integration remain separate owners.

Recorded baseline: all 1717 original Final Fight payloads pass, with 407 exact
runtime hits. The run includes 33507709 incoming-byte writes and 33645069
comparison/replay reads, taking 437670572 cycles with a fresh Rig for the
original-frame phase. This boundary makes paired variants start from identical
timing state. The preliminary reused-Rig parent run took 437670720 cycles;
its preflight-dependent stall phase is not the matched A/B baseline. Neither
count is a hardware timing measurement.
The strengthened focused suite additionally passes cancellation in miss replay
before issue, during an issued read, with output stalled, before commit, and
in hit RESULT; opposite-pattern restart is verified. Five invalid arena classes
cover misalignment, undersized range, address overflow, SDRAM limit and empty
range. These extra tests do not change the frozen RTL or original-frame counts.
