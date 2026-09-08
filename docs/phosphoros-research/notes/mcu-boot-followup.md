# MCU boot follow-up

Reviewed 2026-09-07 against SummerCart64 `c0eb44106199058d5ba6738dd20a2c2c3f44c5ab`.
The [boot ledger](../boot-testing.md) owns measured performance and installed
state. This follow-up makes no firmware changes and performs no hardware test.
The [transport review](boot-transport-review.md) and [previous MCU audit](mcu.md)
are the prior-work baseline; their rejected experiments are not new findings.

## Fresh candidates

| Candidate | Mechanism and likely scope | Disposition |
|---|---|---|
| Read CFG_SCR only for hardware-backed config queries | `cfg_query` in [cfg.c](../../../sw/controller/src/cfg.c) currently reads the FPGA for every ID. Only IDs 0, 1, 2, 3 and 14 consume that value; the other ten valid IDs use MCU state/getters. Invalid IDs do not need it either. Saves one six-byte register transaction per applicable CONFIG_GET and CONFIG_SET previous-value query. | Narrow candidate with host equivalence proof. Six microseconds of wire time per applicable query at 8 MHz, plus DMA/CS overhead; not a large standalone boot gain. |
| Full-duplex two-byte USB status and pop | [fpga.c](../../../sw/controller/src/fpga.c) still splits command TX and result RX in `fpga_usb_status_get` and `fpga_usb_pop`. The accepted `hw_spi_transfer` can transmit the same command/zero bytes and discard received byte zero. | New application of the accepted primitive. Saves one DMA setup per status/pop, not wire time. Most relevant with USB host traffic or diagnostic output. Needs its own zero-gap RTL and hardware tests. |
| Batch USB push command/data into one TX | `fpga_usb_push` still makes two one-byte TX calls within one CS frame. A two-byte local buffer preserves the command/data sequence with one setup. | Companion USB transport candidate; test separately or explicitly as one coherent USB-byte transport experiment. No claim of a normal unplugged-USB boot benefit. |

The normal menu path in [sc64_get_boot_params](../../../sw/bootloader/src/sc64.c)
queries only boot mode, then supplies fixed auto-CIC/passthrough-TV parameters.
CIC seed and TV queries occur for non-menu boot modes. Therefore three saved
queries must not be attributed to every menu boot. The main loop still runs
each service exactly once in its existing order for these candidates.

## CFG query host proof

Ignored artifacts are under the PhosphorOS checkout's
`build/software-boot/mcu-followup/`: `prepare.py`, `query.c`, executable,
`source-manifest.json`, and `host-results.log`. The script extracts the actual
current `cfg_query` body twice and changes only the candidate's unconditional
SCR read to a conditional read for the five hardware-backed IDs. Both copies
use mocked register and state getters.

GCC `-std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined
-fno-sanitize-recover=all` passes **1,114,112 cases**: 17 IDs, including two
invalid IDs, across 65,536 varied register/state values. Return status, both
argument words and getter-call counts match. Baseline reads exactly once;
candidate reads once for the five hardware IDs and zero otherwise. This is an
actual-function logic proof, not an MCU timing, DMA, or concurrency proof.

[The register RTL](../../../fw/rtl/mcu/mcu_top.sv) assembles CFG_SCR as a read-only
snapshot: its read handler does not clear pending events, acknowledge a
command, or write configuration. The parser's next-register prefetch reaches
CFG_DATA_0, also a side-effect-free read. Removing this unused transaction does
not remove an acknowledgment. Hardware-backed queries still sample live SCR;
there is no shared cached configuration value.

Before retention: clean Cortex-M0+ build with unchanged original loader,
existing transport fixtures, GET/SET previous-value and invalid-ID command
checks, then a fresh paired boot comparison. Reject if the gain is below the
measurement resolution or negative. Preserve this proof even if rejected.

## USB trigger and timing review

The unchanged parser in [mcu_top.sv](../../../fw/rtl/mcu/mcu_top.sv) handles
CMD_USB_STATUS by entering NOP after the command. CMD_USB_READ asserts one RX
FIFO pop on the command byte and enters NOP after the next byte. CMD_USB_WRITE
pushes its one data byte and then enters NOP. Keeping exactly two bytes under
one CS frame preserves the number of pop/push triggers; increasing transfer
length or combining multiple USB commands under one CS does not follow this
contract.

A zero-gap proof for register reads does not cover FIFO data arrival after a
USB pop. Test the actual USB parser/SPI/FIFO path across the existing 8 MHz
phase sweep, with empty/full transitions, alternating status/data frames,
all byte values, arbitrary first-byte garbage and CS boundaries. Confirm no
extra FIFO consumption and byte-for-byte host packet streams. Preserve
RX-before-TX DMA enable, independent buffers, both completion waits and final
SPI-busy wait. Compare boot with and without diagnostic logging separately.
Do not count USB logging acceleration as normal boot acceleration.

## Cross-service safety audit

- Save integrity: do not remove `writeback_process`, shorten its one-second
  timer, skip pending-save waits, or change `cfg_cmd_check`'s reset/lock-release
  condition. CFG query narrowing does not change the save-type setter or its
  writeback-disable transition. USB callbacks and successful packet enqueue
  still determine writeback completion; a transport edit must preserve them.
- Button debounce: [button.c](../../../sw/controller/src/button.c) uses 64
  iterations, not milliseconds. These candidates preserve call count and order,
  but shorter iterations still shorten physical debounce time. Existing
  full-duplex work already has this property; stable press/release and noisy
  input qualification remains necessary. Do not describe unchanged service
  ordering as unchanged wall-clock debounce.
- USB and locks: SD lock ownership is already a cheap local enum comparison;
  there is no slow FPGA read to remove there. USB inactive handling releases
  the USB lock and flushes packets; preserve it. Pending CFG USB commands keep
  captured arguments across retries; neither proposal should recapture them.
- Pending hardware operations: skipping `flashram_process` or `dd_process`
  merely because a configuration says disabled risks leaving an older pending
  operation unfinished across a mode transition. This review does not propose
  such gating. RTC pending joybus writes and CIC region correction remain
  serviced; neither can be reduced to a boot-only delay without qualification.
- Save/card presence: `sd_process` and enabled SD writeback each check insertion.
  Sharing a cached sample would move the observation across USB commands and
  other work. Physical removal and reset semantics make that broader than a
  harmless duplicate-read cleanup; no candidate is proposed here.

## Previously known, not rediscovered

CFG argument grouping, reply grouping, extra CFG servicing, runtime SD cursor
reuse, atomic READ_AT, cold SD metadata reordering and small-transfer polling
are already documented. Reply grouping has a rejected UI result; extra service
still needs scheduling/debounce qualification. A fresh boot trace may justify
revisiting them, but this report supplies no new positive measurement for any.
The accepted full-duplex register read, byte/group batching, bounded extents,
cursor caching, c1 compression and logo removal are the starting point.
