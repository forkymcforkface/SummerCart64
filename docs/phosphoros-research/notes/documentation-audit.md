# Project documentation audit for SC64 GIF acceleration

Reviewed 2026-09-06. The project documentation contains important integration
constraints, but no missing MachXO2 configuration specification or complete
timing model that makes an independent FPGA build ready to program.
This report supplements the [testing ledger](../ui-testing.md); it does
not replace the application architecture or subsystem contracts.

## Coverage

| Inventory | Files | Scope |
| --- | ---: | --- |
| Root project | 66 | 65 tracked Markdown/text/HTML candidates plus the existing untracked GIF hardware-path note |
| SC64 vendor repository | 61 | 58 tracked candidates plus three existing experimental GIF READMEs |
| Supplemental | 32 | Local skills, CLAUDE.md, Neon64, Sodium64 and nested bass documentation |
| Generated historical research | 7 | Boot A/B notes, timing options and the earlier FPGA/MCU/UI research reports |

All candidate text was loaded and searched. Relevant technical passages were
reviewed in context; this is not every-line validation of large historical
ledgers, assembler instruction tables or application JavaScript. The generated
interactive BOM's visible controls and data declaration were inspected, not
its compressed PCB geometry. No PDF or RST appeared in the tracked inventories.
Generated dependency trees, private rig configuration and recursively linked
external documentation are outside this local audit. Two Sodium skill-linked
runbooks are absent and cannot be counted as read.

Per-file paths, SHA-256 snapshots, classifications and reading limits remain
in `build/sc64-docs-audit/{root,sc64,supplemental,generated-research}.json`, with
companion findings files. These are audit-time snapshots, not hashes of later
documentation corrections. The seven generated notes contain no substantive
result missing from maintained reports; several pending-work statements are
superseded by subsequent tests.

## Findings that affect implementation

- Original Final Fight is 33,675,601 bytes, exceeding the 23.75 MiB asset arena.
  Input needs bounded streaming windows. Existing memory clients, DD overlap
  and global SD byte-swap/session state rule out treating cart SDRAM or DMA as
  unowned scratch space.
- Cancellation must finish before the first ROM staging write, theme-cache
  rewind and explicit cache reset. Console reset can leave USB-powered cart
  SDRAM and FPGA state alive. A final launch-handoff barrier alone is too late.
- The guarded SC64 design uses 22 of 26 EBRs. The cached GIF prototype requires
  seven, leaving a deficit of at least three before additional buffers.
- Final Fight's palette/disposal subset does not qualify arbitrary GIFs.
  Local palettes, interlacing, transparency, disposal 2/3 and fallback still
  need coverage. Original audio support is a separate raw-theme requirement.
- Receiver-only timing excludes source SD transfer and decoding. UI FPS and
  GIF progress are separate metrics. Existing GIF64 paths already use cache,
  prefetch, asynchronous PI DMA and CI8 rendering.
- Neon64 provides useful N64-side examples of producer publication, RSP tile
  conversion and DMA/RDP completion ordering. These are design references,
  not demonstrated GIF acceleration on this cart.

The owning evidence is in [FPGA research](fpga.md), [UI transport research](ui.md),
[vanilla theme gaps](vanilla-themes.md), the testing ledger and the vendor
[GIF experiments](../../../tests/gif/README.md).

## Verified corrections and remaining documentation drift

The SC64 protocol documents now explain the IDENTIFIER register's unlocked
upper-halfword write side effect: it clears the button interrupt while the
identifier value remains read-only. This is checked against `n64_cfg.sv`.
The USB guide's unused CIC argument range is corrected from `[32:25]` to
`[31:25]`; three broken USB-command links point to the existing N64 command
table. No protocol or RTL behavior changes.

The theme guide's universal approximately 40 FPS ceiling is contradicted by
the later Final Fight baseline: 47.3 UI FPS and 462 GIF frames in 10,002 ms.
Treat older measurements as workload-specific. Historical plans also retain
superseded claims about build exit codes, absent GIF RTL, runtime reuse,
missing bridges and uninstalled tools. These do not describe current research
status or prove production integration. CLAUDE.md conflicts with current
AGENTS/architecture guidance on outputs, module registration and fonts; the
current authority remains AGENTS and the owning contracts.

The old LZW estimate of 107,929,728 prefix-walk steps includes 1,286,559 KwKwK
append steps. The RTL's 106,643,169 actual prefix reads is a different counter,
not an inconsistent decode result. Preserve that distinction in comparisons.

## Evidence advanced during this audit

- The board and actual ISSI SDRAM part support the original LPF's documented
  timing inputs; an inherited Micron symbol link is not the fitted part's
  datasheet. See the vendor hardware evidence report.
- A public exact-device 7000HC design supplies 26 active EBRs and supported
  vendor NCD/NCL/SDF exports. It supplies new comparison evidence, not FIFO,
  ODDR or EFB timing coverage or a proven source-to-bitstream recipe.
- The new source-aware PIO gate passes 51 original inouts and rejects all
  204 checked-bit mutations plus a direction mutation. It reports database
  ambiguity without changing configuration or guessing an electrical mode.
- Exact-device EBR comparison reproduces the F1B35 mode-pattern conflict.
  Site/occupancy confounding remains; no encoder patch is justified yet.
- Router2 finishes at 41.81 MHz versus the fixed 75.52 MHz diagnostic baseline.
  Timing-driven rip-up times out at 180 seconds; simulated annealing fails
  relative-chain legalization. None supplies a retained improvement or a
  qualified 100 MHz implementation.

Remaining work is controlled EBR/configuration evidence, complete hard-cell
and external timing coverage, resource fit and production transport ownership.
The reference-derived byte-identical release reconstruction does not establish
an independently compiled FPGA image. No cart programming or hardware
performance claim follows from this documentation and host-tool pass.
