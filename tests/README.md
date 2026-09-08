# SC64 optimization host regressions

Run from an SC64 checkout on little-endian Linux with Python 3.9+, Git and GCC
(including AddressSanitizer and UndefinedBehaviorSanitizer runtimes):

```sh
python3 tests/run.py --output build/host-tests
```

`CC` selects a local compiler command, for example `CC='ccache gcc'`. The
runner invokes it directly without a shell. No cross compiler, Docker,
PhosphorOS checkout, downloaded dependency or hardware is required. The
checkout must contain Git object 18041e25472075a166292d1195603bcefe9c9688,
the original v2.20.2 baseline; an archive or shallow clone missing it fails.

All generated C extracts, headers, binaries, source-hash manifests and logs
are placed beneath the required `--output` directory. Output inside tests/
is rejected. Sources default to the parent of this tests/ directory; an
explicit `--source /path/to/sc64` supports testing another checkout. No test
copies of production function bodies are checked in.

Individual suites and intermediate MCU state:

```sh
python3 tests/run.py --output build/host-tests --suite cursor
python3 tests/run.py --output build/host-tests --suite bounded
python3 tests/run.py --output build/host-tests --suite mcu --mcu byte --spi split
python3 tests/run.py --output build/host-tests --suite mcu --mcu combined
python3 tests/run.py --output build/host-tests --suite formatter
```

The default requires combined MCU batching and full-duplex register reads.
`--spi split` tests the historical split header/read implementation; a missing
full-duplex call or helper fails the default run. `--mcu byte` permits the interim
byte-only implementation; if a grouping helper exists it is always tested.
A missing required helper, config mismatch, extraction error, compile error,
sanitizer finding, assertion, timeout or nonzero process exit fails the run.
Each command has a 120-second timeout; do not treat partial PASS lines as a
successful overall exit. Compile diagnostics are retained in suite results.log.

## Coverage

- Cursor: stock and current SD functions are independently extracted; a harness
  dispatcher selects them without adding branches to either implementation.
  Compare 12,571 statuses and 10,868 mocked I/O operations, with exact SET counts,
  partial read failures, retry, write/init/deinit invalidation, lock loss and
  sector wraparound. A small command-protocol model supplies the environment.
- Bounded menu: current menu_read and actual R0.15 FatFs source/config run on a
  RAM disk. FAT32/exFAT, contiguous/fragmented files, 63/64 extents, partial EOF,
  cluster sizes, every read-error position, corrupt/truncated/cyclic chains,
  writable map scope, empty/invalid-start files, unused bad successors,
  exact 64 MiB and oversized input are covered. LBA32 boundary guards use a
  synthetic in-memory database offset and a callback recording the last legal
  sector; they do not require a 2 TiB disk image.
- SPI bytes: 168,608 cases / 337,216 actual-function operations check single-register
  read/write bytes, CS boundaries, returned values and reduced helper calls.
  All 65,536 possible two-byte header replies are discarded correctly by the
  actual full-duplex register-read function; all six MOSI bytes match baseline.
- Register groups: 93,248 cases compare separately routed actual stock/current
  SD-command and DMA functions. Check busy/error responses, return values,
  byte swapping, trigger-last order, frame/byte savings, optimized read-header
  calls, address patterns, 1 to 256 blocks and zero-count no-op.
- Diagnostic formatter: current call-site inventory, pinned-header provenance,
  bounded display wrapper, and 544,796 sanitized formatting comparisons. New
  or unsupported format tokens and unchecked dynamic formats fail explicitly.
  The formatter is vendored; tests do not download an implementation.

`tests/formatter.py --source sw/bootloader --output build/formatter-test
--n64-probe build/formatter-probe` additionally generates an isolated N64 ABI
and framebuffer diagnostic source tree. The destination must not exist and
must be outside the source tree. Build it with the normal bootloader toolchain
and explicit version metadata. The generator never deploys or flashes it.
On hardware require 1,197 cases, zero format/framebuffer errors, equal positive
white-pixel counts, a positive negative-control mismatch count, and successful
menu/audio boot afterward. The actual framebuffer accessor prevents an empty
or unrelated memory range from passing. Host checks alone do not establish
the target newlib ABI; the existing plain-renderer gate remains separate.

FatFs configuration is unchanged: revision 80286, FASTSEEK 1, READONLY 0, MKFS 1,
LBA64=0, EXFAT 1 and 512-byte sectors are required. The harness supplies disk
callbacks/get_fattime and maps 64 MiB at cart address 0x10000000. A failure to
create that mapping is a test failure. Production diskio.c is not executed.

ASan/UBSan failures are fatal. Warnings in fixture code are fatal. Generated
source extracts narrowly downgrade
only retained pointer-width and original enum-pointer argument diagnostics to
visible warnings using diagnostic push/pop directives. These exceptions preserve
actual baseline statements and target 32-bit casts;
they are not a claim that upstream sources compile warning-free on a 64-bit
host. Compiler flags target GCC; other CC choices must support them.

## Limits

These are host models, not hardware or full-firmware acceptance. They do not
prove electrical timing, real SD recovery, interrupted-write durability, USB
client compatibility, button cadence, save scheduling, PI alignment or outlet-
to-picture timing. The bounded fixture validates the private menu consumer;
generic CREATE_LINKMAP can still return a short map for a truncated chain,
which menu_read detects through remaining sectors.

The full-duplex SPI fixture mocks DMA transfer, including arbitrary received
header bytes; it does not execute STM32 DMA register accesses or prove board
timing. The actual helper is required and its source hash is recorded.

The function extractor accepts the current straightforward C definitions and
fails if expected names disappear. SD type/enum changes require explicit test
adaptation. Source snapshots are regenerated and hashed on every run. Retained
logs describe that snapshot only; rerun after edits. Compression selection
requires a separate target build and N64 timing check.

## Plain diagnostic display

After bootloader display or packaging changes, run the actual-source framebuffer regression:

```sh
python3 tests/no_logo.py --source sw/bootloader --baseline . --output build/no-logo-test
```

It compares the complete plain, text, and error-message framebuffers against v2.20.2 with ASan/UBSan and rejects linking the decorative logo. Real-console VI and exception entry remain hardware checks.

## Atomic native SD READ_AT

After the READ_AT firmware change, the default suite includes:

```sh
python3 tests/run.py --suite read-at --output build/host-tests
python3 tests/read_at.py --output build/read-at-host
```

This suite requires only the current SC64 checkout, Python 3.9+ and a host GCC
with ASan/UBSan. It does not need the historical baseline Git object, a
PhosphorOS checkout, N64 or ARM compiler, firmware image, or hardware. `CC`
selects the host compiler command. Other suites retain their existing Git
baseline prerequisites. Running before READ_AT is present fails explicitly.

A standalone container run from the SC64 root is:

```sh
docker run --rm -v "$PWD:/work" -w /work ubuntu:24.04 sh -c \
  'apt-get update -qq && apt-get install -y -qq --no-install-recommends python3 gcc libc6-dev libasan8 libubsan1 && python3 tests/read_at.py --output build/read-at-host'
```

Package installation affects only the disposable container. A normal Linux
host can run the Python command directly without Docker or package downloads.
Generated extracts, binaries, result logs and source hashes stay beneath the
explicit output directory; production source and tests/ are rejected outputs.
Every process has a 120-second timeout, sanitizer failures are fatal, warnings
are errors and core dumps are disabled. Missing or partial completion fails.

Current cfg.c supplies address translation, diagnostics, selected dispatch
cases and command/error enums. Current sd.c supplies sd_read_sectors, SD
response/status enums, transfer limit and timeout; sd.h supplies real errors,
lock values and sector size. The mock BRAM capacity is checked against the
actual N64 sc64_buffers_t.BUFFER declaration in sw/bootloader/src/sc64.h, and
its address comes from that header. No production function body or private
protocol-constant snapshot is checked into the fixture.

The oracle compares current legacy I then s with current R over 4,224 cases:
zero/valid/oversized counts, sector wrap, first/second lock loss, initialized
and uninitialized cards, byte swap, byte/block addressing, CMD18 failure,
CRC failure and timeout. It compares all result bytes, cursor, replies, lock
calls, LED activity, starts, aborts and CMD12 completion. Another 24 cases
exercise 32-bit byte-length overflow before any LED/DMA side effect. Diagnostic
capability/unknown-ID/ADC checks preserve cursor, lock and read state.

The legacy oracle comes from the same current source; it is not a claim to
execute historical firmware. Only its I/s cases are selected. Diagnostics
also use the current owner, including an unknown-ID no-side-effect check.
A cursor-assignment mutation must fail the exact differential assertion; a
removed bounds guard must fail the exact overflow-side-effect assertion.
Those errors are generated from current source and their assertion messages
are required, so an unrelated crash is not accepted as a negative-test pass.

The model substitutes lock, SD command/DMA completion, LED, ADC and reply I/O
boundaries. It does not execute the whole controller service loop, the FPGA,
physical SD timing, USB transport or flash/recovery. Existing RTL gates, exact
firmware readback, card roundtrips and playback/hardware qualifications remain
separate requirements before firmware acceptance.
