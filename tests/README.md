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
python3 tests/run.py --output build/host-tests --suite mcu --mcu byte
python3 tests/run.py --output build/host-tests --suite mcu --mcu combined
```

The default requires combined MCU batching. `--mcu byte` permits the interim
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
- SPI bytes: 103,072 cases / 206,144 actual-function operations check single-register
  read/write bytes, CS boundaries, returned values and reduced helper calls.
- Register groups: 93,248 cases compare separately routed actual stock/current
  SD-command and DMA functions. Check busy/error responses, return values,
  byte swapping, trigger-last order, frame/byte savings, optimized read-header
  calls, address patterns, 1 to 256 blocks and zero-count no-op.

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

The function extractor accepts the current straightforward C definitions and
fails if expected names disappear. SD type/enum changes require explicit test
adaptation. Source snapshots are regenerated and hashed on every run. Retained
logs describe that snapshot only; rerun after edits. Compression selection
requires a separate target build and N64 timing check.
