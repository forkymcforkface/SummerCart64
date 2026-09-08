# Experimental cart source and packet transport

This extends the [actual-controller test](../sc64-integration/README.md) with
the unchanged [memory DMA](../../../fw/rtl/memory/memory_dma.sv): compressed
frame bytes are read from cart SDRAM into a small FIFO, decoded/composed, then
GPD1 bytes are written to a bounded cart output window and independently read
back through DMA. It is excluded from production FPGA source lists.

```sh
sh /path/to/tests/gif/sc64-transport/run.sh ORIGINAL.gif /path/to/build/sc64-transport
```

The same original-GIF subset and every-four-images packet cadence apply. All
original images are decoded; no host-selected reuse bit or skipped image is
injected. Python prepares reference vectors only. Generated fixtures, logs,
packets and the per-image ledger stay under the explicit build directory.

## Ownership and transport

A test-only round-robin mux shares the CFG input between the scratch adapter,
source DMA and packet DMA. Each grant latches one complete mem_bus request and
holds ownership through ACK. A low request/ACK gap separates grants, including
DMA clients that keep request asserted for their next word. Assertions enforce
request/data stability while owned. The unchanged downstream arbiter preserves
N64/CFG/USB/SD priority and PI reservation gating. As in the earlier test, real
CFG operations are excluded; production integration needs an explicit owner.

The source window is `[0x30000,0x38000)`: at most one 32 KiB compressed image
payload is staged by the test fixture. The whole original GIF is never placed
into a fixed arena. **Preloading this window is test setup, not measured SD
staging.** Actual source reads pass through memory_dma, the mux, arbiter and
SDRAM controller/DQ model. The DMA FIFO feeds LZW with backpressure, and the
harness requires consumption of exactly every supplied compressed byte.

Source and packet transport each use a 64-byte FIFO. The packet path retains
the first 32 header bytes, derives the exact GPD1 length, checks the bounded
payload, and starts FIFO-to-memory DMA into `[0x40000,0x40000+76992)`.
The packet remains unpublished until DMA, its outstanding bus request and the
FIFO have retired. Before acknowledging the reference frame, the harness uses
the source DMA in readback mode to compare every stored output byte against
the emitted packet. It does not validate output by peeking at the host array.

The scratch dictionary/canvas ranges and three competing peer words are
unchanged. All physical reads/writes are checked against exact scratch,
source, output and peer ranges. FIFO bounds, empty reads, early source/output
reuse and invalid payload sizes fail loudly.

## Measurement epoch and limitations

This is a new transport epoch, not an apples-to-apples speed comparison with
the earlier 2,747,802,158-cycle controller-only run. It adds a mux, source RAM
reads, output writes, FIFO backpressure and independent output readback. Future
reuse/optimization comparisons must retain this same transport path, source
feeder and packet cadence.

The per-image ledger includes `readback_cycles` separately. `cycles` includes
decode/composition, optional packet writes and readback validation. Source byte
counts, physical source reads, output writes and readback reads are reported.
Readback replaces a future consumer for verification; it is not an N64 renderer
or a measurement of its PI/cache/RDP costs.

The original file parser, SD read/staging, real firmware clients, publication
protocol and combined cancellation/recovery remain outside this harness.
Cancellation is not qualified by the full-frame run. The same idealized CL2,
270-degree phase, single-cycle DQ model and digital-only limitations from the
controller test apply. No board image, integrated placement/timing, physical
FPS or hardware safety claim is made.

The current cancellation gap is concrete: stopping the DMAs does not flush
queued source/output bytes, so output busy can remain asserted and source
restart can be rejected after cancellation. A future combined owner must first
drain decoder/cache, compositor, scratch adapter, both DMAs and the mux, then
flush queues and publish retirement. Clearing queues before issued bus work
retires would violate ownership. This throughput prototype is not ready for
first-cart deployment or cancellation-safe production use.

## Completed original Final Fight transport baseline

All **1,717 original images pass**, producing the unchanged **430 packets /
10,245,568 bytes**. All emitted bytes pass actual DMA readback, and all sixteen
exported packets match the earlier dedicated-dictionary output byte-for-byte.

- 33,507,709 compressed payload bytes are consumed through 16,754,277 physical
  source word reads, including the correct handling of odd payload lengths.
- Output performs 5,122,784 word writes and 5,122,784 independent DMA word reads.
- Total original-loop cost is 3,208,827,902 controller clocks, including
  41,635,041 clocks of readback validation; maximum image including optional
  packet transport/readback is 3,622,537 clocks.
- Each N64/USB/SD peer completes 391,702 checked operations. The harness checks
  278,415,576 arbiter grants and observes 9,400,848 PI-reserved clocks.
- Original-loop physical SDRAM totals are 209,391,090 reads and 68,947,686
  writes, including scratch, source, output and competing peer traffic.
- The whole model run including initialization observes 4,103,958 refreshes
  and 97,178,097 activations. Initialization is excluded from loop totals.

The ledger reconciles all 1,717 image rows with these totals. This is a measured
simulation transport baseline for future A/B experiments, not proof of 60 FPS
or a tested physical cartridge implementation.
