# Original-GIF pipeline through actual SC64 memory controllers

This experimental harness connects cached LZW and CI8 composition through the
[scratch adapter](../sc64-bus/gif_sc64_bus.sv), unchanged production
[memory arbiter](../../../fw/rtl/memory/memory_arbiter.sv) and
[SDRAM controller](../../../fw/rtl/memory/memory_sdram.sv). No production source
list changes, bitstream, hardware installation or device timing result are involved.

```sh
sh /path/to/tests/gif/sc64-integration/run.sh ORIGINAL.gif /path/to/build/sc64-integration
```

Python, Verilator, g++ and make are required. The explicit build directory holds
fixtures, logs, per-image `frame-cycles.csv`, and the first sixteen actual GPD1
packets. The original-GIF subset, packet format and reference rules follow the
[compositor test](../compositor/README.md). Python generates reference vectors
only; users are not required to convert original GIFs offline.

## Memory and competing clients

The adapter occupies the existing CFG port **exclusively for this test**. Real
CFG traffic is absent. A production integration needs an owned upstream mux or
another arbiter client; it cannot silently replace CFG. N64, USB and SD remain
the actual three other arbiter inputs. Every 8,192 clocks each scripted client
submits a word operation, alternating writes and checked reads. PI SDRAM
reservation holds for 24 clocks per period. Each new arbiter grant is checked
against N64 > CFG > USB > SD priority and PI reservation gating; an already
issued request can finish during reservation.

Scratch dictionary bytes occupy `[0,16384)`, with canvas bytes at
`[0x10000,0x10000+76800)`. Three peer words are at `0x1000000`, `0x2000000`, and
`0x3000000`, exercising other SDRAM banks and row changes. Every physical read
and write is asserted to remain inside those exact ranges. This is a test-owned
scratch layout, not production allocation or whole-file staging.

## SDRAM data model and its limits

The C++ chip model consumes real controller command/address/DQM/DQ pins. It
tracks four active banks and row addresses, precharge, refresh, mode-register
selection, CL2 burst-one reads, and masked 16-bit writes. No returned pixel is
fabricated from a mem_bus ACK: all reads come from memory previously written
through physical DQ. Composition is checked against independent original indices.

The generated [PLL configuration](../../../fw/rtl/vendor/lcmxo2/generated/pll_lattice_generated.v)
explicitly specifies 100 MHz and a 270-degree SDRAM clock phase. The idealized
model therefore supplies CL2 read data for one controller sampling edge three
cycles after the registered READ command: command clock plus 7.5 ns, two SDRAM
cycles, then the next controller edge at 30 ns. It drops read drive on the next
cycle and rejects simultaneous read drive and WRITE. This preserves the intended
digital sampling relationship; it does not model analog propagation, setup/hold,
PLL jitter, device speed grade, signal integrity or timing closure. Bank/mode
legality is checked, but this is not a complete vendor SDRAM timing/retention model.

The full-run watchdog is 20 billion clocks; each image and packet phase is also
bounded. The per-image ledger includes its optional accumulated packet output.
The test emits every four original images plus the final remainder only to test
reference lifetime, not to redefine OS4 animation timing.

## Scope of measurements

Controller clocks include actual refresh/row switching and the scripted peer
traffic. Compressed source bytes still arrive from a host ready/valid feeder;
SD file reads, source staging/streaming and MCU framing are **not** measured.
Packets are captured directly by the host, so output-buffer RAM writes, N64 PI
DMA, receiver placement/cache publication and RDP work are also excluded.
The complete original file is never allocated in the production scratch arena.

Adapter bounds/cancellation have their own standalone suite. This full-frame
test does not establish combined decoder/compositor cancellation ownership,
production address allocation, or integration with real SD/USB DMA engines.
It tests those peers' mem_bus requests, not their whole firmware stacks.

The first permissive probe held read data until a write and is preliminary only.
The authoritative run uses the single-cycle read drive and exact range checks
described above. No hardware FPS or safe deployable FPGA image is claimed.

A negative phase control changes the read-drive sampling edge from cycle +3 to
+2 in an isolated copy. It fails the peer readback equality assertion before
eight original images complete. This detects the incorrect sampling phase in
the digital harness; it is not a measurement of physical timing margin.

## Completed strict original Final Fight run

All **1,717 original images pass**, with **430 packets / 10,245,568 bytes**.
Every packet and canvas matches its independent original-image reference; all
sixteen exported packets additionally match the dedicated-dictionary pipeline
byte-for-byte. The per-image ledger totals **2,747,802,158 controller cycles**;
maximum image plus optional packet is **2,619,056 cycles**.

Each competing N64/USB/SD client completes **335,425** checked operations.
There are **251,246,900** checked arbiter grants and **8,050,200** reserved
controller cycles. Original-loop SDRAM traffic comprises **187,429,612 reads**
and **63,740,488 writes**, including dictionary, canvas and peer traffic.
The whole model run, including initialization, observes **3,514,311 refreshes**
and **68,513,205 activations**. Initialization is excluded from original-loop
cycle/read/write totals. No setup or source preparation time is included.

These results establish functional conversion through the existing digital
memory controllers under the declared traffic pattern. They do not establish
end-to-end UI frame rate or the performance of a board-installed accelerator.
