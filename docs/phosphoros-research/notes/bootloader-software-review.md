# Bootloader software review, 2026-09-07

This review covers additional boot speed work without FPGA modifications.
The installed c1 compression, bounded menu extents, SD cursor reuse and MCU
SPI batching remain the baseline. Historical results and recovery state are
owned by the [boot ledger](../boot-testing.md), not this candidate list.

## Recommended first experiment: lossless resident logo packing

The [asset converter](../../../sw/bootloader/tools/asset_converter.py) encodes
RGB run lengths as one count byte and three color bytes. The resident logo
contains 153,600 pixels, 366 distinct exact RGB colors and 35,647 runs capped
at 256 pixels: 142,592 loaded bytes. The
[linker script](../../../sw/bootloader/N64.ld) places these bytes in the loaded
RAM image even though [display.c](../../../sw/bootloader/src/display.c) only
draws the image on diagnostic paths. Normal boot does not draw the logo.

An isolated candidate preserves all 366 colors using a resident RGBA palette
and 16-bit tokens: nine palette-index bits and seven repeat-minus-one bits.
Runs split at 128 pixels. It produces 35,872 tokens, a 1,464-byte palette and
a 12-byte header, totaling **73,220 bytes**, saving **69,372 resident bytes**.
The header stores pixel, palette and token counts. There is no quantization,
external asset file, flash lookup, cart transaction or normal-path image decode.
Error, watchdog and exception paths retain the logo in RDRAM. This avoids the
PI/cart-failure hazard of fetching diagnostic graphics after a failure.

The candidate lives only in the ignored PhosphorOS workspace directory
`build/software-boot/logo-candidate/`; the packed candidate is preserved there for research only. The user subsequently
requested removing the decorative logo entirely; packed production edits have
been restored from the owned baseline snapshots. No commit or installed update
is made by this agent.

| Build | Stripped ELF bytes | c1 compressed ELF bytes | Packaged ROM bytes |
|---|---:|---:|---:|
| Clean baseline | 209,732 | 80,512 | 98,304 |
| Clean packed logo | 140,468 | 76,008 | 98,304 |
| Instrumented transient baseline | 234,684 | 96,800 | 114,688 |
| Instrumented transient packed logo | 165,420 | 92,248 | 114,688 |

Compressed-file size alone understates the change: IPL3 materializes about
69 KiB less data. The historical c1 logo-elision probe saved 12.368 ms for
removing the entire logo, but it was a single pair and removed diagnostics.
That is a rough upper comparison, not a guaranteed bound or measured gain for
this candidate. Expect a fraction of that opportunity; only interleaved actual
N64 A/B can decide whether the added format is justified. Packaged ROM size is
unchanged because both variants remain inside the same padding boundary.

### Host checks completed

- The actual candidate C decoder was extracted into a host harness and compiled
  with GCC `-Wall -Wextra -Werror -fsanitize=address,undefined`. All 153,600 RGBA
  output pixels exactly match the source PNG converted to RGB with opaque alpha.
- Bad pixel count, zero/excess palette count, zero/excess token count, a short
  token stream, invalid palette index and final-run overflow return failure;
  a checked framebuffer writer detects any output overrun. Failure falls back
  to the existing plain diagnostic background so error text remains available.
- Generator round trips pass at repeat lengths 1, 127, 128, 129, 255, 256, 257
  and 153,600. Exactly 512 distinct colors is accepted; 513, empty and non-RGB
  input fail loudly. Source colors and repeat semantics remain exact.
- Bounds checks protect framebuffer writes. The decoder trusts the linked asset
  allocation; this is **not** a general decoder safe for arbitrary truncated
  external input. No broader external-image format/API is proposed.
- Four MIPS builds completed. Existing missing-version-metadata preprocessor
  warnings occur in both baselines and candidates; these research builds are
  not presented as a warning-clean release build. Hashes and sizes are recorded
  in the ignored `build-summary.json` beside the build logs.

### Reproduction and hardware gates

Run each converter with local Python/Pillow first, because the existing N64
compiler image does not contain Pillow. For example, from the PhosphorOS root:

```powershell
python build/software-boot/logo-candidate/packed/tools/asset_converter.py build/software-boot/logo-candidate/packed/assets/sc64_logo_640_240_dimmed.png build/software-boot/logo-candidate/packed/build/sc64_logo_640_240_dimmed.asset --compress
```

The isolated research Makefiles use the existing bootloader build; they do not
replace PhosphorOS's production build entry point. Build command, with the
PhosphorOS directory mounted at `/work`:

```sh
docker run --rm --entrypoint bash -v D:/Documents/GitHub/phosphor-os:/work -w /work/build/software-boot/logo-candidate n64menu-dev:libdragon -lc 'make -C packed -j4 all'
```

Use `baseline`, `packed`, `baseline-probe` and `packed-probe` respectively.
The probe copies share the existing historical `logo-probe/src/main.c` USB
reporter, entry Count capture in `init`, and `BENCH_TRANSIENT` menu override.
Startup assembly is unchanged. Clean builds contain none of that probe code.
The existing `build/sc64-boot-ab/run.sh` accepts either probe through
`SCBOOT_ROM=../software-boot/logo-candidate/VARIANT/build/bootloader.bin`.
Only the parent hardware owner runs that harness.

Before retaining: interleave baseline/candidate/baseline on identical SD/theme
state, separate IPL3-to-entry from menu and frontend times, verify boot/music,
and capture the actual diagnostic screen for exact comparison. Explicitly
exercise ordinary runtime error, watchdog and exception entry; the host pixel
check cannot establish N64 endian, cache or video behavior. No FPGA/MCU change
is needed. Installed-flash acceptance remains distinct from transient ROM A/B.

## Other opportunities and disposition

| Candidate | Evidence and expected opportunity | Required gate / disposition |
|---|---|---|
| Menu-only PI DMA staging of IPL3 | The [handoff](../../../sw/bootloader/src/boot.c) still reads 1,008 cartridge words through individual `pi_io_read` calls. Historical staging saved about 2 ms. | Previously tested generically, unqualified for retail/64DD. A new narrow fast path only for the loaded menu can leave retail/64DD untouched; carry an explicit menu distinction because ROM and menu both use the ROM device. Preserve PI interrupt clear and other observable register state. Compare all 4,032 bytes and representative menu IPL3s, NMI/cold starts, and retail/64DD fallback. Do not reuse SP DMA. |
| Further resident logo compression with an error-path decoder | A second small lossless codec could reduce eagerly expanded asset bytes further, while keeping the entire compressed payload resident. | New, unmeasured. Additional codec code and exception-stack use may consume the gain. Prefer the simpler packed palette candidate first; adding an inflater solely for branding is not justified without evidence. |
| Stream bounded allocation runs instead of building a whole extent table first | [menu_read](../../../sw/bootloader/src/menu.c) currently completes `CREATE_LINKMAP` before data transfer and falls back after its fixed 128-word table fills. Very fragmented menus repeat some allocation work on fallback. | New, conditional opportunity; the existing ordinary-menu data phase is already about 28 ms and most data-transfer work cannot disappear. A streaming walker must retain size-bounded corruption behavior, read-only scope, 64 MiB/LBA limits and error reporting. Run actual FatFs FAT32/exFAT fixtures with 63/64/many extents and corrupt chains before any hardware test. Not prioritized for the normal contiguous menu. |
| Read-only FatFs / strip built-in test suite | Diagnostic test code uses writes, formatting and broad FatFs functions. Removing them could shrink startup payload. | Not recommended: it removes cart diagnostics and write tests. Linker already uses function/data section garbage collection. No safe removal inferred from normal-boot non-use. |
| Faster bootloader compiler/compression settings | c1 wins; c0, O2 and LTO already measured in the ledger. | Do not relabel rejected trials as new gains. O2 slowed entry; LTO saved less than 1 ms. Revisit only after a materially different payload and separate A/B. |
| Skip test button/status query, SD initialization, writeback wait or VI reset work | [init](../../../sw/bootloader/src/init.c), [main](../../../sw/bootloader/src/main.c) and the ledger expose their dependencies. | Preserve diagnostic entry, SD ownership, save durability and reset compatibility. Menu already bypasses CIC auto-detection and uses NMI; skip proposals duplicate existing behavior or remove required boundaries. |

## Parent transient hardware observations

The parent measured two interleaved actual N64 pairs: baseline IPL3-to-entry
65,806 / 64,792 microseconds versus packed 61,397 / 60,458 microseconds,
saving 4,409 / 4,334 microseconds. Menu loads were 28,080 / 28,243 versus
28,538 / 27,928 microseconds, consistent with variation rather than a menu-read
improvement. These are transient ROM results, not installed-flash or outlet-to-
picture timing. The parent also passed the actual N64 diagnostic framebuffer check: CRC32
`DAFE56B3` (decimal 3,674,101,427) over 614,400 RGBA bytes exactly matches
the source, and PhosphorOS boots afterward. Explicit watchdog/exception
entry and installed-flash acceptance remain separate from this logo check.

The reusable packed-logo regression is retained only as ignored
`build/software-boot/logo-candidate/packed-test_logo.py`. It was withdrawn from
the vendor tests directory when the user selected complete logo removal.
It imports the production converter and extracts the actual C decoder; it does
not maintain a second production function body. Python/Pillow and host GCC with
ASan/UBSan are required. Invalid fixtures, missing dependencies, extraction
changes, compiler failures and subprocess timeouts fail the run.

No hardware was accessed by this research agent. No firmware change, flash or
commit is performed by this document. The parent records hardware outcomes and
retention decisions in the maintained boot ledger.

## User-selected follow-up: remove decorative logo

The user prefers omitting the image entirely. Ignored `no-logo` and
`no-logo-probe` copies remove the linked logo entry from `ASSET_FILES`, the
background decompressor, and asset references. `display_init(void)` always
clears the existing framebuffer. All error, watchdog, exception and test-suite
callers retain their existing diagnostic text, VI configuration and control flow.
The source PNG and converter can remain available in the repository; neither
is linked into the no-logo bootloader. This is a deliberate visual change
requested by the user, not an accidental loss of diagnostic capability.

`no-logo.patch` records the minimal production diff. The clean candidate builds
with `-Werror` and all four normal version metadata macros supplied from the
current vendor revision (marked dirty). `no-logo-diagnostic` and
`baseline-plain-diagnostic` both draw a plain background and identical
`SC64 diagnostic text` before reporting `text_crc` over the actual framebuffer.
The parent can compare those CRCs on N64 and confirm normal boot afterward.
Transient timing and installed qualification are pending in this review.

The no-logo host regression `test_no_logo.py` is staged only in the ignored
candidate directory. It independently compiles actual current and v2.20.2
clear/text functions with their real fonts under ASan/UBSan and compares every
framebuffer byte. Three cases pass: plain `C656B350`, diagnostic text `E6E7751D`,
and runtime/watchdog/exception text `4F0BD25F`. It additionally rejects linked
logo build inputs/references and loss of unconditional background clearing.
These source/input gates complement actual rendering; they do not substitute
for a final ELF symbol audit, which also finds no logo/decompressor symbol.

The warning-clean no-logo candidate ROM is 65,536 bytes with SHA256
`77de9d05095e9479a7b1ec2b3aed8c0410b8b77085b94390beec262227492620` at
`build/software-boot/logo-candidate/no-logo/build/bootloader.bin`. Its version
metadata labels the pre-integration vendor revision as dirty; the final release
must rebuild after the parent commits the accepted source.

## Parent hardware disposition

The [software-only boot round](../boot-testing.md#software-only-boot-round--2026-09-07) supersedes the candidate-only status above. Logo removal and full-duplex register reads are retained after actual-source checks, N64 comparisons and verified production readback. Packed-logo encoding is superseded and omitted from production.
