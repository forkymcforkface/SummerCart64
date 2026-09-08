# Boot decompression follow-up, 2026-09-07

This is source research and an isolated host compression experiment after the
accepted no-logo bootloader. There is no production edit, firmware package,
commit or hardware access in this review. The [boot ledger](../boot-testing.md)
owns actual installed status; the [earlier review](bootloader-software-review.md)
owns the initial candidate list. Paths starting with `libdragon/` or `build/`
refer to the enclosing PhosphorOS checkout.

## Findings to test next

| Rank | Candidate | Expected gain | Safety and acceptance gate |
|---|---|---|---|
| 1 | Tune the existing c1 LZ4 match window for the no-logo payload | Unknown; probably small. 4 KiB reduces token count but adds 1,208 input bytes; 16 KiB saves 880 input bytes but accesses history beyond the CPU's 8 KiB data cache. Either might win; size alone cannot choose. | Build-time encoding change only: retain the current decoder, IPL3 and in-place safety margin. Exact host round trips pass. Real N64 interleaved timing, loaded-image hashes, diagnostics and installed-flash acceptance remain required. |
| 2 | Reduce resident diagnostic formatter dependencies while preserving every diagnostic | Potentially several KiB less loaded/decompressed code; boot-time saving unmeasured. The current ELF contains a 4,616-byte `_svfiprintf_r` plus allocator routines. Their entire size is not a removable-byte estimate because FatFs also needs allocation. | Medium implementation risk, low hardware/protocol risk. First prove a smaller established formatter implementation exists in the toolchain and supports the complete current format inventory. Prefer that over a new handwritten printf parser. Preserve the existing bounded 256-byte result, signed/unsigned widths, `long`, hex, padding and truncation. Differential host output and N64 exception/watchdog/test-screen checks required. Do not remove diagnostics to get the size reduction. |
| 3 | Stop reading unused command result words on successful bootloader commands | Small, likely microseconds rather than another multi-millisecond win. `sc64_execute_cmd` unconditionally performs both DATA reads after every command, including SD reads and setters whose callers ignore both. | Requires explicit command response ownership; always preserve the error DATA0 read, completion polling and diagnostic commands. Confirm register read side effects in current protocol/RTL, then trace equivalence and time whole boots. A broad MCU transport audit may supersede this small bootloader-side candidate. |

None is an accepted performance improvement. The narrow menu-only IPL3 DMA
staging candidate remains more promising than these micro-optimizations, but it
is already documented in the earlier review and is not a new finding here.

## c1 window probe: exact results

The probe uses the clean no-logo artifact from
`build/software-boot/logo-candidate/no-logo/build/bootloader.elf.stripped`.
It has two nonempty load segments: 392-byte exception vectors and 61,056 bytes
of code/read-only data/initialized data. The 614,400-byte framebuffer is a
zero-file-size `NOLOAD` segment; two 131,072-byte test buffers are BSS, not
resident compressed assets. Removing those declarations does not remove that
many bytes from the loaded ELF.

The actual checked-out libdragon compressor at
`4142ebea3cdcded9551ba9ee199fb91331b91867` is used: maximum HC level 12,
`LZ4_favorDecompressionSpeed(1)`, varying only `lz4_distance_max`. The 8 KiB
result is **byte-identical** to the existing compressed bootloader code segment,
so the sweep is anchored to the real baseline encoding rather than a different
host codec. All 12 segment/window pairs decode exactly through
`LZ4_decompress_safe` and match the source byte-for-byte.

| Match window | Main segment compressed bytes | Difference from 8 KiB | Match tokens | Literal bytes | Bytes copied from history farther than 8 KiB |
|---|---:|---:|---:|---:|---:|
| 2 KiB | 45,701 | +2,547 | 4,212 | 32,425 | 0 |
| 4 KiB | 44,362 | +1,208 | 4,600 | 30,017 | 0 |
| 8 KiB, current | 43,154 | 0 | 4,920 | 27,929 | 0 |
| 16 KiB | 42,274 | -880 | 5,173 | 26,353 | 3,638 |
| 32 KiB | 41,720 | -1,434 | 5,323 | 25,385 | 5,727 |
| 65,535 bytes, format maximum | 41,659 | -1,495 | 5,339 | 25,281 | 6,015 |

The exception-vector segment remains 20 compressed bytes throughout. Compressed
input-size reduction is only about 2.0% at 16 KiB or 3.5% at the format maximum
for the main segment, not the entire boot. More distant matches can increase
cache misses and more tokens add decoder control work, so larger windows can
be slower. Smaller windows provide the opposite tradeoff. No N64 cycle estimate
or speed claim is inferred from these counts. The main segment has only 7-10
matches with offsets below eight bytes across the sweep; optimizing that special
copy loop is unlikely to pay for a new MIPS decoder path on this payload.

Ignored reproducible probe artifacts are under
`build/software-boot/decompression-review/`: `window.c`, `window`, extracted
`segment*.bin`, encoded `segment*-w*.lz4`, `segments.json`, and
`window-results.json`. Host compilation uses GCC and the existing
`libdragon/tools/common/lz4_compress.c`; it does not replace an installed
compressor or generate a flashable firmware image. These are ordinary host
round-trip checks, not sanitizer or hardware qualification.

To advance the two most informative candidates, generate isolated 4 KiB and
16 KiB c1 ELF packages with the existing compressor's full margin/offset logic.
Do not hand-patch compressed payload lengths without also recomputing in-place
placement and preserving the decoder's eight-byte output overrun allowance.
Verify loaded segments against the baseline, then compare baseline/candidate/
baseline on the parent-owned hardware harness with identical metadata and
separate entry/menu/frontend counters. Only keep a repeatable measured win.

## Checks that rule out attractive but redundant changes

- `libdragon/boot/loader.c` already starts PI DMA and calls the decompressor
  while it runs. The LZ4 assembly already waits for the arriving DMA position.
  Adding a second "overlapped decompression" pipeline duplicates this behavior.
- `libdragon/tools/common/assetcomp.c` already asks for decompression speed at
  the highest LZ4 HC level. Simply enabling that option changes nothing.
- `libdragon/src/compress/lz4_dec_fast.S` already copies literals and ordinary
  matches eight bytes at a time. Replacing it with C or proposing ordinary word
  copies is not an established optimization.
- `libdragon/boot/loader.c` does not separately clear each ELF BSS/framebuffer;
  stage 1 already clears RDRAM with RSP DMA. Removing the global clear requires
  restoring ELF zero-initialization, loader scratch and reset invariants. It is
  not a safe shortcut justified by the fact that the framebuffer is diagnostic.
- The current linker already uses section garbage collection. The linked
  diagnostic font is only 768 bytes; it is not another logo-sized opportunity.
- `display_vprintf` already uses integer-only `vsniprintf`, so merely replacing
  floating-point printf is a no-op. A smaller formatter needs actual size and
  exact-output evidence, not an assumption that floats are currently linked.
- c0/c1 changes, O2/LTO, raw SP DMA handoff, skipped save waits, shorter timeouts,
  and new persistent menu caches are not proposed again. The first two simply
  repeat earlier tuning; the others either lack safety evidence or violate the
  current scope.

Useful source owners within SummerCart64 are
[bootloader command transport](../../../sw/bootloader/src/sc64.c),
[diagnostic display](../../../sw/bootloader/src/display.c),
[ELF linker layout](../../../sw/bootloader/N64.ld), and
[bootloader build](../../../sw/bootloader/Makefile).
