# PhosphorOS boot optimization branch

`phosphoros-boot` is based on upstream v2.20.2,
`18041e25472075a166292d1195603bcefe9c9688`. It retains the upstream license,
protocol, SPI clock, SD block limits, and FPGA image. The original optimization series is consolidated in `1c8f6f9`; the
historical table retains the original measurement identifiers.

## Retained changes and measurements

Measurements use a real 4 MiB N64 and the same 458,752-byte PhosphorOS menu.
Rows show incremental comparisons, not independent savings to add together.
Bootloader timing comes from separate instrumented builds. Production source
has no benchmark hooks.

| Commit | Change | Measured result |
|---|---|---|
| `886d7c1` | Reuse the SD cursor for consecutive reads | Warm menu load: 45.009 to 40.788 ms. |
| `427316e` | Compress the bootloader with c1 | Warm IPL3-to-entry: 84.070 to 65.112 ms; stripped program is identical. |
| `86f79cd` | Read bounded menu allocation extents | Warm menu load with cursor caching: 40.635 to 28.248 ms. |
| `1d3cc1e` | Batch single-register SPI command bytes | With optimized bootloader: menu 28.020 to 27.731 ms; frontend 557 to 542 ms. |
| `7a5bb99` | Group adjacent SD command/DMA registers | Menu 27.731 to 27.524 ms; frontend effectively unchanged at 542/543 ms. |

The two MCU changes together produce a 21,712-byte image, the same size as the
compiler baseline. The final production bootloader is 98,304 bytes. The MCU
comparisons pass four SD-file hashes each, two boot/music checks each, and
10-second runtime captures with zero audio underruns. Final clean production
firmware readback matches the expected images; normal SD boot reaches the
frontend at 538 ms and first music at 565 ms, with zero runtime underruns.

USB powers the cartridge during console mains cycles. These are warm-cartridge
comparisons, not end-to-end cold-power measurements. The frontend counter
excludes the earlier bootloader phases. Broader card, game, save and electrical
compatibility is not established by one rig's successful checks.

## Build and test

Use the upstream toolchain/build procedure. The tested bootloader compiler is
MIPS GCC 14.4.0 with libdragon's compression tools; the MCU compiler is ARM
GCC 9.2.1. Bootloader asset conversion requires Pillow.

From the fork root, with the upstream toolchains configured:

```sh
GIT_BRANCH=phosphoros-boot GIT_TAG=v2.20.2-based \
GIT_SHA="$(git rev-parse HEAD)" GIT_MESSAGE="PhosphorOS boot optimizations" \
    ./build.sh bootloader
python3 tests/run.py --output build/host-tests
```

The [host test instructions](../tests/README.md) describe dependencies,
coverage, retained upstream diagnostics, and individual suites. The runner
extracts current production functions and original v2.20.2 functions at run
time; it does not test checked-in copies of their implementations.

The tested MCU package rebuilds the application while retaining the installed
v2.20.2 loader's first 4 KiB. The original loader prefix and unchanged FPGA are
checked during firmware readback. The general upstream controller build also
rebuilds the loader; that different package requires separate validation.
The runtime version fields remain 2.20.2 for this branch, so identify artifacts
by commit and hash rather than that version string alone.

## Scope and exclusions

The menu helper owns its temporary extent map and detaches it before return.
An oversized map falls back to ordinary FatFs reads. Read-only mapping stops
at the declared file length; writable mapping remains unchanged. A truncated
chain can still yield an incomplete generic map, which the private menu
consumer detects. This is not a general FatFs corruption-hardening claim.

Register grouping is limited to SD ARG followed by CMD, and DMA address/length
followed by SCR. Trigger registers remain last. Neither the FPGA protocol nor
the 8 MHz SPI clock changes.

This branch excludes the unbounded extent implementation, SP DMA handoff,
16 MHz SPI, larger MCU-only transfer counts, logo removal, extra MCU service
calls, single-sector command changes, and compiler experiments that showed no
useful gain. PI DMA handoff and proper deferred-logo loading remain separate
research. No FPGA optimization is included.

## Further software-only improvements

The [2026-09-07 round](phosphoros-research/boot-testing.md#software-only-boot-round--2026-09-07) retains removal of the decorative diagnostic logo (`701e31d`) and full-duplex MCU register reads (`a57d302`). Error text remains available; the FPGA and original MCU loader are unchanged. The detailed ledger records phase-specific measurements, hardware checks, artifact hashes and qualification limits.
