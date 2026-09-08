# Preserve the stock MCU memory client

This isolated derivative adds the original MCU memory controller alongside
scratch, source and packet clients at the upstream side of the stock CFG
memory-arbiter port. It does not change production RTL or the existing
three-client experiment. The four priorities rotate explicitly; no integer
modulo divider is synthesized.

```sh
sh run.sh /fresh/ignored/output/directory
```

Requires Python 3, Verilator and Yosys with MachXO2 synthesis. Verified with
`sc64-gif-test:local` (Verilator 5.032, Yosys 0.52). Generation refuses existing
output directories and directories within the vendored tests tree. Logs,
generated HDL, executables and netlists remain in the output directory.
After every gate succeeds, `result.json` records hashes of the six local
runner/harness sources, imported three-client generator and baseline, actual
MCU/interface sources, generated mux/slice, tool versions and gate statuses.
It is created exclusively; an existing manifest is not overwritten.

## Exact ownership boundary

The source [MCU controller](../../../fw/rtl/mcu/mcu_top.sv) owns a 512-word
buffer and issues one acknowledged 16-bit memory beat at a time. Length is
the last word index, not a byte count. `mem_stop_pending` waits for a beat's
acknowledgement before stopping. The generator extracts its actual memory
controller declarations/always blocks, changing declarations that become
test inputs/outputs and making two existing width conversions explicit:
32-bit `mem_address` assignment to the 27-bit bus becomes `[26:0]`, and its
increment literal becomes `27'd2` instead of `2'd2`. A combinational SAT
proof checks both old/new expressions for all 32-bit addresses and 27-bit
bus values, including overflow. No Verilator warning suppression is used.
The test drives those controls directly.
It does **not** simulate MCU firmware, SPI framing or register decoding.

`gif_transport_mcu_mux` has the same scratch/source/packet/memory interfaces,
plus a `mcu` memory client and `gif_admit` input. Admission affects only new
GIF grants. Active grants always drain; MCU requests are never cancelled,
reset or forced low by GIF cancellation. A grant retains its payload until
ACK, followed by a request-low/ACK-low gap before the next grant.

**`gif_admit` is a scheduling gate, not a cancel/aborting input.** Integration
must keep it high while any GIF producer has a pending request to drain,
including a request not yet granted. The job owner stops new work but holds
existing requests until their ACKs; admission can close only after retirement.
Directly wiring `!aborting` here would deadlock queued DMA/scratch requests.

`idle` still means the entire mux is idle. `gif_idle` instead requires all
three GIF request lines low and no active GIF grant or held GIF ACK. It may
be true while an unrelated MCU transaction is active or stalled. The final
GIF abort owner must use this separate retirement condition together with
its decoder/compositor/adapter/DMA drain and queue-flush conditions; waiting
for global CFG idle would allow continuous MCU traffic to prevent retirement.
This directory does not modify or claim to validate that complete owner.

## Executed checks

Local frozen logs: `build/sc64-transport-mcu/provenance-final/`. The parent
independently repeats every gate in `build/sc64-transport-mcu/parent-final/`.

- A stock 512-word write under three continuously requesting GIF peers
  returns exactly 512 ACKs to each client. All 2,048 grants match the exact
  repeating scratch/source/packet/MCU order, and all stored words match.
- Cancellation is modeled while MCU owns the live grant and all three GIF
  requests are pending. Admission remains high; each GIF request stays high
  until its own ACK, then stops generating work. All three drain exactly once
  before GIF idle becomes true. Only then does scheduling admission close.
  All 512 MCU read words and ACK ownership remain correct.
- The MCU transaction is deliberately stalled for 1,000 cycles: global idle
  remains false, while GIF idle is true. After memory service resumes the
  MCU completes. No request is forcibly withdrawn to manufacture retirement.
- Restarted GIF clients make fair progress. An active GIF request and its
  three-cycle held ACK both keep GIF idle false until fully drained.
- Memory ACK latency varies from 2 to 12 cycles and ACK remains asserted for
  three cycles. The scoreboard checks stable payload, one-hot ACK ownership,
  read data and full write masks. A 200,000-cycle watchdog bounds each run.
- A negative derivative routes the MCU ACK to owner 2. Compilation must
  succeed; execution must terminate with SIGABRT and the exact ACK-mask
  assertion. A generic tool failure cannot count as the negative pass.

Paired standalone synthesis, same flow and explicit-selector baseline:

| Mux | LUT4 | Flip-flops | Carry cells |
|---|---:|---:|---:|
| Three clients | 162 | 54 | 0 |
| Four clients plus GIF admission/idle | 238 | 57 | 0 |

The comparison omits only simulation fatal checks from both synthesis
copies. It measures mux cost, not the stock MCU buffer or whole FPGA.

## Remaining integration limits

The host memory service is a delayed mem_bus model, not the actual arbiter
or SDRAM chip model. The [stock arbiter](../../../fw/rtl/memory/memory_arbiter.sv)
retains N64 PI-active gating and orders CFG ahead of USB and SD. Downstream
starvation is an unmeasured risk, not a demonstrated result: this mux's
request-low/ACK-low gap may let the stock arbiter grant USB or SD. Four-way
fairness inside this mux does not establish downstream fairness. Combined
arbitration/backpressure tests must determine whether the gaps suffice and
whether an explicit bounded GIF-service policy is needed.

The subsequent [actual-arbiter matrix](../transport-fairness/README.md) observes
USB/SD progress through CFG gaps under finite paired workloads. Continuous USB
still starves SD with CFG disabled, identifying the existing stock priority.
Those observations do not establish unbounded fairness or board timing.

An indefinitely stalled **GIF** memory transaction correctly prevents GIF
retirement; no mux can safely flush that destination without downstream
completion or a proven reset contract. An indefinitely stalled MCU may
allow GIF ownership retirement but still blocks useful shared-memory work.
The bounded 1,000-cycle stall test is not proof the whole system recovers
from an unresponsive memory controller.

This experiment has no N64 command/register mapping, complete job owner,
integrated source SD transport, placement, timing qualification or hardware
test. `synth-result.json` explicitly sets `hardware_qualified` to false.
