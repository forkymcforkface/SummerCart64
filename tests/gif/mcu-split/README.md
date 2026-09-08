# Original-GIF work split: MCU, FPGA and N64

The viable direction remains bounded container parsing/control on an existing
software owner, FPGA LZW plus external-canvas composition/dirty output, and
N64 packet application/rendering. Moving **all LZW expansion onto the stock
MCU** introduces both a RAM deficit and a demonstrated architectural wire
limit; no MCU timing measurement in this research establishes a benefit.
FPGA LZW-only with N64 composition is a possible simplification experiment.
Existing full-plane diagnostic costs motivate measuring a direct-DMA path;
they do not establish its minimum cost or rule out a faster implementation.
No offline asset conversion is required by either proposed split.

## Actual stock MCU limits

[ST's STM32G030F6 specification](https://www.st.com/en/microcontrollers-microprocessors/stm32g030f6.html)
identifies a Cortex-M0+ at up to 64 MHz, 8 KiB SRAM and 32 KiB flash. The
[actual linker script](../../../sw/controller/app.ld) reserves 4 KiB loader,
28 KiB application flash and **8 KiB total RAM**, not 8 KiB free for GIF.
[hw.c](../../../sw/controller/src/hw.c) configures 64 MHz and the current
8 MHz SPI1 link to the FPGA. These are source/specification facts, not new
hardware measurements.

[app.c](../../../sw/controller/src/app.c) cooperatively services button, CFG,
CIC, DD, FlashRAM, ISV, LED, RTC, SD, USB and writeback. A large synchronous
decode in that loop would delay those services. A safe software decoder
would need bounded work, cancellation and exclusive memory ownership, plus
measured service latency. Existing CFG reply batching already failed to
produce a meaningful UI gain; it is not an untested decoder optimization.

The MCU's FPGA memory controller has a 512-word buffer and moves payload over
SPI; this buffer is FPGA storage, not additional MCU-addressable SRAM.
See [the actual-source controller experiment](../transport-mcu/README.md).
SD-to-cart DMA avoids carrying pixel payload through the MCU today.

## Existing original-Final-Fight evidence and arithmetic

No new host timing benchmark is needed to repeat the existing independent
[LZW/cache measurements](../README.md) and [reference decoder](../gif_reference.py).
The source has 1,717 full 320x240 images and expands to 131,865,600 index bytes
over the loop. The existing model counts 106,643,169 actual prefix reads and
23,928,675 dictionary writes. The older 107,929,728 prefix-walk figure includes
1,286,559 KwKwK append steps, so it is a different counter, not a disagreement.
No one should label these operation counts MCU cycles.

| Quantity | Consequence for this split |
|---|---|
| Conventional 4,096-entry prefix16/suffix8 dictionary | 12 KiB before a phrase stack, I/O buffers or firmware state |
| Packed prefix12/suffix8 dictionary | 10 KiB; still larger than total MCU RAM |
| General 4,096-byte phrase stack | Adds 4 KiB; observed Final Fight maximum 391 is not a generic safe bound |
| Full CI8 output per image | 76,800 bytes |
| Full CI8 at 60 images/s | 4.608 MB/s |
| 8 MHz SPI raw byte ceiling | 1 MB/s before commands/CS/software overhead |
| Full index output over that SPI link | At least 76.8 ms/image from output bytes alone |
| 64 MHz at 60 images/s | About 1,066,667 CPU clocks/image total, including all existing services |

Thus MCU LZW followed by FPGA composition cannot deliver 60 full expanded
images/s through the existing pixel-byte interface, even with a hypothetical
zero-cost decoder. This is a throughput bound for **that interface**, not a
claim that every encoded/phrase/token protocol must send full index bytes.
Sending compressed phrases or another encoded representation would require
the FPGA to expand them and is a different split requiring its own design.

An external dictionary does not remove the MCU link cost. A naive uncached
16-bit prefix read for each counted prefix lookup alone carries 213,286,338
bytes over the link across the loop, before suffixes, writes, pixels or
protocol overhead. The existing 512-entry write-allocate cache's 78.95% hit
rate is a host sensitivity result, not measured MCU cache behavior or a
free source of RAM. No CPU-clock estimate is inferred from it.

The source file itself is 33,675,601 bytes and the maximum compressed image
payload is 25,747 bytes. The MCU cannot keep either in its 8 KiB RAM. A parser
can operate incrementally across sub-blocks and skip pixel payload while
issuing bounded DMA descriptors; a design that reads the entire compressed
stream into MCU RAM or transfers it through MCU SPI adds a separate cost.
The existing bounded source-DMA experiments are preferable mechanics to reuse.

## FPGA LZW-only versus N64 composition

The real N64 [receiver comparisons](../../../docs/phosphoros-research/notes/gif-prototype.md)
already measure PI transfer plus packet application/cache publication:

| Original source case | Full CI8 | Changed tiles | Row spans |
|---|---:|---:|---:|
| Frame 423, 259 tiles | 15.649 ms | 6.713 ms | 8.036 ms |
| Frame 1030, 123 tiles | 15.640 ms | 3.558 ms | 2.827 ms |
| Frame 1713, 1,200 tiles | 15.648 ms | 28.112 ms | 23.226 ms |

The [actual receiver](../../phosphoros-receiver/receiver.inc)
distinguishes these paths explicitly: `kind == 0` reads `PX` contiguous bytes
directly into `plane` with `phos_cart_cache_read`. Packet validation, tile
scatter/row copies and cache writeback are inside `if (kind)` and are skipped
for full-plane mode. Thus the table's full-plane cost is **not** a 1,200-tile
GPD1 scatter cost. The counters separately time `pi_us` around the backend
cache read, `apply_us` around the conditional application and `rdp_us` around
offscreen rendering. `pi_us` is a backend-call duration, not necessarily pure
wire time or the fastest possible direct DMA.

These are five-repeat diagnostic observations on the N64; approximately
3 ms of offscreen clear/draw/completion is separate. FPGA decode/compose,
SD staging, palette setup and normal UI work are excluded. The full-plane
measurement is not a transparency/disposal compositor benchmark.

LZW-only output would still transfer a full index stream for these full-canvas
source images, then require the N64 to preserve transparent pixels, apply
disposal/palette policy, maintain history and publish GPU data. The measured
15.6 ms backend read is not a physical PI floor and must not be extrapolated
into an impossibility result. A contiguous cart output could DMA directly
into a destination without GPD1 unpacking; whether that destination can be
the final image depends on opacity, retained canvas/disposal and GPU lifetime.
Transparent index streams may need a separate plane and a composition pass.
Those costs and useful DMA/CPU/RDP overlap remain unmeasured here.

This split may reduce FPGA area and deserves a focused test if fit is the
binding limit. A useful A/B would use identical decoded streams, source
cadence and retained canvases, compare the existing cache-read path with
explicit contiguous asynchronous PI DMA, measure N64 composition and cache
publication separately, and include the whole frame/audio loop. No 60 FPS
acceptance or rejection follows from the older synchronous receiver alone.

FPGA composition retains the prior canvas in cart memory and sends sparse
updates, explaining why the measured sparse receiver cases are promising.
Dense updates need a full-plane option; always sending tiles is not justified
by the data. Removing composition also removes the producer that presently
determines dirty output, so its transport savings cannot be credited to an
LZW-only prototype without replacing that work elsewhere.

## Bounded recommendation and remaining work

1. Keep bulk compressed input, dictionary traffic and expanded pixels off
   the MCU SPI payload path. MCU container/control work is plausible, but
   N64-owned incremental parsing also fits the existing RTK owner and avoids
   adding a second file/parser lifecycle. Neither parser is qualified here.
2. Continue the smaller FPGA LZW/cache/stack and compositor experiments with
   proper external-memory ownership, existing MCU access and retirement.
   Preserve original GIF durations; 60 UI FPS is not 60 decoded images/s for
   every authored asset.
3. Treat FPGA LZW-only/N64 composition as a measured fallback experiment if
   resource fit requires it, with no inherited sparse-update performance claim.

This note adds no MCU decoder, host timing estimate, production firmware,
hardware operation or commit. General palettes, interlacing and disposal 2/3
remain broader than the original Final Fight pilot. Physical fit/timing and
end-to-end behavior remain separate gates.
