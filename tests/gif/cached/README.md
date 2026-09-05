# Experimental cached-dictionary GIF decoder

This separate variant keeps the verified reference decoder unchanged. It adds
a 512-entry direct-mapped write-allocate cache over an external 4,096-entry GIF
prefix/suffix dictionary. Entries contain 12 prefix bits and 8 suffix bits;
the external owner can store them in 32-bit slots, requiring 16 KiB. The full
4,096-byte expansion stack remains on-chip. No live SC64 buffer or save memory
is borrowed, and there is no production source-list or firmware integration.

```sh
/path/to/sc64/tests/gif/cached/run.sh /path/to/original/background.gif /path/to/build/cached-gif-test
```

Requirements and generated-fixture policy match the parent directory. Tests
consume original GIF payload without creating a GIF64 file. Generated outputs
and source assets remain outside this directory.

The external interface holds `memory_valid`, key, direction and data stable
until `memory_ack`. Reads return `memory_rdata`; either direction can return
`memory_error`. These are dictionary-entry transactions, **not** an existing
SC64 bus protocol or a measured SDRAM service time. An actual 16-bit memory
bridge would need bounded word transfers, arbitration and arena ownership.

Cache tags clear in 512 cycles at image start/GIF clear. Writes allocate and
write through; failed transactions invalidate the affected line. Input EOF,
invalid codes, output bounds and memory errors fail the current job. Cancel
drains an outstanding external request, invalidates the cache and only then
releases busy. Global reset assumes the external bridge is reset with the
decoder; use cancel, not reset, to release a live memory owner safely.

The isolated full suite passed 1,772 fixtures: all 1,717 original Final Fight
images, 131,865,600 exact decoded indices, 55 synthetic/error vectors, 200
cancellations and explicit external read/write failure, active-request cancel
and successful restart checks. The final driver varies cancellation positions
through initialization and active decoding. Memory simulation uses a 3–10
cycle delay based on key plus 40-cycle holds every 1,000 cycles; requests must
remain stable until acknowledged. This is a chosen stress model, not board
timing or an actual SC64 memory-arbiter simulation.

The original images consume 1,257,856,312 simulated cycles, maximum 809,783 per
image, versus the reference's 485,920,630 / 294,186 with dedicated dictionary
RAM. The cache reduces RAM consumption at a latency cost. Original dictionary
traffic is 22,448,934 external reads and 23,928,675 writes, matching the earlier
512-entry cache model. Fault and synthetic test traffic is reported separately.

Yosys 0.52 MachXO2 technology mapping yields **6 DP8KC, 635 LUT4, 300 FF and
132 CCU2D**, compared with 14 DP8KC for the dedicated reference. Adding the
current RAM-based compositor requires another EBR. These counts make a smaller
memory layout plausible; they do not establish that the combined SC64 design
fits or meets timing. Integrated vendor-tool synthesis/place-and-route and
hardware testing are still required. This variant has not been flashed.

The next experiment is the cached decoder plus compositor sharing a modeled
memory bus, followed by the real SC64 memory bridge. Standalone LZW cycles omit
canvas composition, packed output, PI transfer, RDP work and normal cart traffic.
