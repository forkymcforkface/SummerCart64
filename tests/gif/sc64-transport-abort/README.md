# Experimental transport cancellation owner

This separate variant adds coordinated retirement to the
[cart transport experiment](../sc64-transport/README.md). It does not change
the frozen throughput baseline or production FPGA sources.

```sh
sh /path/to/tests/gif/sc64-transport-abort/run.sh ORIGINAL.gif /path/to/build/sc64-abort
```

The runner uses the same original-GIF fixtures and actual DMA/arbiter/SDRAM
model. Generated vectors, logs and the normal-path smoke driver remain in the
explicit build directory. It runs cancellation cases on the first original
image and up to eight normal images; this is not a new all-image performance run.

## Ownership and retirement

An external cancel request produces exactly one component pulse. A request
latch rearms only after cancel goes low, so a held request cannot repeatedly
restart dictionary clearing. An `aborting` latch blocks source/verify/frame
starts, configuration/session admission, packet emission/ACK and pixel input.
The existing DMA stop latches stop each DMA after its issued work completes.

The owner waits for decoder/cache, compositor, scratch adapter, both DMA busy
states, mux idle with ACK low, and every local bus request to retire. Only then
does it flush queued source/output bytes, invalidate local packet metadata and
pulse `retired`. It never forces an issued mem_bus request low or flushes FIFO
data before its DMA client retires. A new session requires explicit scratch
configuration and canvas initialization. The old partial scratch/output data
is discarded logically, not atomically rolled back.

Decoder errors do **not** automatically initiate the combined abort. The caller
must explicitly request cancellation; the test covers error-to-cancel recovery.
An indefinitely unresponsive physical memory bus still requires a separate
system recovery policy. This wrapper does not prove that policy or board safety.

## Verified cases

Twelve cases cover pulse and held cancel requests during:

- source DMA memory access;
- the second dictionary word;
- a stalled packet FIFO;
- an active packet DMA write;
- output DMA readback;
- an invalid LZW minimum-size error followed by explicit cancellation.

Each case attempts frame/verify/emit starts during abort and requires bounded
retirement, empty local queues, no later writes during 64 idle clocks, and exact
decode/packet write/DMA readback after restarting with generation 2. Observed
drain intervals are 510–517 clocks in this idealized model, including dictionary
cache clearing. Real bus stalls can extend them; these are not hardware bounds.

The eight-image normal smoke reproduces the transport baseline exactly:
16,439,680 clocks, 148,670 source bytes, 74,338 source word reads, two packets
totaling 86,784 bytes, and 43,392 output writes plus 43,392 DMA readback reads.
Normal-path correctness is also checked against original pixels; matching this
smoke does not substitute for a full qualified board implementation.

Source SD staging, runtime GIF parsing, production arena ownership, real peer
engines, timing closure and FPGA deployment remain outside this experiment.
