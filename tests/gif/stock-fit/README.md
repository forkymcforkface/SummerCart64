# Actual stock-pin GIF resource skeleton

Research only. This integrates the bounded decoder, external CI8 compositor,
source/output DMA and FIFOs into the exact release stock top for synthesis.
It does not implement a usable firmware/N64 command API, reserve memory,
qualify timing, place, route, generate a bitstream or touch a cart.

Run from the repository root with the existing diagnostic image and pinned
release conversion manifest. Outputs must be fresh and outside `tests`:

```powershell
docker run --rm -v D:/Documents/GitHub/phosphor-os:/repo sc64-open:diagnostic-lpf /usr/bin/python3 -B /repo/vendor/sc64/tests/gif/stock-fit/run.py /repo/build/sc64-open-memory/release-conversion/inputs.json /repo/build/sc64-bounded/agent-core /repo/build/sc64-transport-mcu/frozen/gif_transport_mcu_mux.sv /repo/build/sc64-open-timing-options/nextpnr-machxo2 /repo/build/sc64-stock-fit/final
```

The manifest identifies release `18041e25472075a166292d1195603bcefe9c9688`
and the original conversion inputs. The runner reuses the existing guarded
stock RAM mapping pipeline identically for both designs. Generated sources,
removed simulation assertion inventory, source hashes, tool versions,
mapping/packing logs and actual disconnected-RTL negative results are saved.
No assertion is removed from checked-in functional RTL. The baseline uses
the original transport header counter, not the separate saturation experiment.

## Exact integration boundary

Generated copies of `fw/rtl/top.sv` and `fw/rtl/mcu/mcu_top.sv` connect the
existing SPI register write/address/data signals to seven parameter registers
and six one-cycle command bits. The existing register-read case adds A0 status.
The original physical top ports are compared by name, direction and width.
No observation GPIO or simulation SDRAM bus is added.

The original MCU CFG memory client becomes the fourth client of the proven
round-robin mux. Its downstream port feeds the original CFG arbiter input.
The stock N64, USB DMA, SD DMA, flash, BRAM and SDRAM owners remain present;
the two GIF DMAs are additional channels, not replacements. The original
research wrapper's duplicate arbiter and SDRAM controller are removed.

GIF cancellation rejects new jobs but permits pending GIF bus requests to
drain (`gif_admit=1`). Retirement waits for GIF-only `gif_idle` and each GIF
client request/component, never MCU activity or global CFG idleness. MCU
requests are neither cancelled nor reset by a GIF cancel. The stock CFG
priority over USB/SD remains. The separate [actual-arbiter matrix](../transport-fairness/README.md)
observes USB/SD progress during mux gaps under finite paired workloads and
checks PI reservations. This synthesis skeleton does not execute those peers.

## Address audit and limitations

The exact stock `mcu_top.sv` register enumeration ends at `REG_AUX` (39);
both read and write cases compare the full eight-bit `address`. Controller
`sw/controller/src/fpga.c` transmits the full eight-bit register number and
little-endian words. A0..A7 do not alias those registers. Searches over SC64
`fw`, `sw` and `docs` found A0/A4 STM32 ADC offsets, A5 FlashRAM commands,
font/codepage values and separate N64 CFG AUX words; these are different
address spaces. This research allocation is not a published protocol claim.

A0 writes pulse session/frame/emit/ACK/cancel/configure; A1..A7 hold
generation, initial reference, frame, ACK generation, ACK frame, source length,
and minimum-code-size/transparency/index parameters. The rectangle is fixed
320x240, disposal 1, with no interlacing/local palette. Status is live: done
and retired pulses may be missed by MCU polling. There is no sticky response,
atomic parameter snapshot, capability handshake, bounds-checked source-length
submission or firmware/N64 producer. This is a resource skeleton only.

The inherited fixed dictionary/canvas/source/output addresses begin at 0,
0x10000, 0x30000 and 0x40000. They conflict with stock ROM/use and have no
cart-arena allocation or theme/launch retirement ownership. They are unsafe
for deployment. No stock memory allocation policy is bypassed on hardware.

## Gates and interpretation

Structural data reachability excludes clock/reset edges and requires a path
from SPI data to job control, to decoder start, and from decoder status to
the dedicated MCU status input and SPI output. A job-to-output-memory-request
path is also required. Actual regenerated RTL variants tie frame start and
the MCU status input low; both must fail the same gate after synthesis.
This graph overapproximates combinational, control and RAM relationships;
it establishes retained connectivity, not temporal execution or API behavior.
The dedicated decoder-busy wire must also have identical integer net IDs at
both status-vector bit 10 boundaries; memory feedback cannot satisfy this test.

Packing uses existing diagnostic EFB inactive-tie removal and generated PLL
metadata restoration, with the ODDR/EFB/FIFO diagnostic flags. No configuration
output is requested. Successful packing is not physical fit: placement and
timing remain untested and the diagnostic hard-block limitations still apply.
The added memories are four DP8KC blocks (dictionary 2, stack 1, dirty mask 1)
and sixteen distributed RAM blocks (two FIFOs), on top of the stock 22 EBRs
(18 DP8KC plus four FIFO8KB) and eight distributed RAM blocks. All 26 physical
EBRs are consumed. A resource overage remains a rejection even if pack succeeds.

The parent independently repeats the final runner in
`build/sc64-stock-fit/parent/result.json`, including source-conversion and LPF
hash recording, and confirms all 56 frozen release inputs match the manifest.
The paired `build/sc64-stock-fit/review/result.json` run passes both guarded
mapping pipelines, identical physical port checks, the positive structural
gate and both actual disconnected-RTL negatives. Actual packer counts are:

| Resource | Stock | Integrated skeleton |
| --- | ---: | ---: |
| TRELLIS_COMB | 5,674 | 8,863 |
| TRELLIS_FF | 3,023 | 4,288 |
| Physical EBR | 22 | 26 |
| TRELLIS_RAMW | 8 | 24 |
| Physical I/O | 101 | 101 |

The candidate exceeds 6,864 available logic positions by 1,999 (29.1%).
This actual stock-pin integration still cannot fit. The earlier `frozen`
run exposed an insufficient broad status-path check; `final` then correctly
refused packing without a pin-constrained ODDR output. Both failed runs remain
as logs. The `review` run uses the existing pins-only diagnostic LPF and the
strong dedicated status-wire identity check. The runner additionally verifies
the stock conversion hash and records the LPF hash for independent repeats.
