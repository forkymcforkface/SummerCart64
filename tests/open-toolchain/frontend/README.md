# Interface and high-impedance frontend regression

`run.py OUTPUT --sv2v /path/to/sv2v` checks two separate frontend requirements:

- An unqualified interface crosses a module boundary alongside a real inout.
  Its enable signal must still control an open-drain output after conversion.
- An unconditional high-Z output must remain Z, never an undefined X value.

The test runs the pinned Slang frontend in default, best-effort and kept
hierarchy modes. All three currently reject the interface/inout fixture. Its
standalone high-Z fixture compiles but produces X; the test explicitly detects
that loss. These results describe unsupported frontend behavior, not accepted
production synthesis. The aggregate regression passes only when it detects
those known failures and the sv2v/native route preserves the actual enable,
zero and high-Z nets.

The opt-in full-manifest probe is:

```sh
python3 tests/open-toolchain/probe.py CHECKOUT OUTPUT --frontend sv2v \
  --sv2v /path/to/sv2v --primitive /path/to/efb-declaration.v \
  --primitive tests/open-toolchain/oddr/oddrxe_decl.v --timeout 600
```

The default remains Slang. The original source manifest and source hashes are
unchanged; conversion goes into the explicit output directory, with a separate
log, tool version and SHA-256. The timeout applies per conversion/synthesis
stage, kills the process group, returns124 and leaves status evidence.

## Root cause and measured limits

Slang's `should_dissolve` preserves any module with an inout port before it
considers hierarchy-mode options. On a preserved boundary it requires an
explicit modport. SC64's n64_top and sd_top have unqualified interfaces and
physical inouts, causing that exact conflict. Forcing hierarchy options does
not solve it. High-Z conversion is a separate synthesis limitation.

The original full manifest converts with sv2v v0.0.13 and completes native
Yosys synth_lattice plus check-assert with no reported connectivity problems.
Its mapped cells include 91014 LUT4, 35845 TRELLIS_FF, 402 CCU2D, 12 DP8KC,
4 FIFO8KB, 8 TRELLIS_DPR16X4, 53 $_TBUF_, one each EFB/EHXPLLJ/ODDRXE and one
TRELLIS_IO. This result cannot fit the 6864-LUT SC64 device. The log explicitly
falls back to flip-flops for DD RAM, both EEPROM banks and the MCU buffer.
This repeats the previously observed sv2v memory-inference limitation; it is
not a new qualified implementation or a physical usage estimate for Diamond.

The final n64_video_sync output remains literal Z. The two CIC RAM blocks have
nonzero initialization with combined population5787 one-bits, matching the
464 source words' bit population. This is a sanity check, not a proof of word
order or initialized behavior; initialization and memory functionality still
need exact equivalence checks. Unknown hard blocks are retained by explicit
primitive declarations, never silently discarded. A synthesis pass is not
place/route, timing, electrical correctness or permission to flash.

Evidence: outer checkout `build/sc64-open/slang-boundary/` contains the full
conversion, synthesis log and JSON; `build/sc64-open/frontend-focused/` contains
the focused tests. These are generated outputs and are not committed.

[Upstream frontend source](https://github.com/povik/yosys-slang/blob/b6e440d6a2586b93c2a43da676c207c8c2a15778/src/slang_frontend.cc)
contains the inout preservation and required-modport rules.

Converter prerequisite:
[official sv2v v0.0.13 Linux release](https://github.com/zachjs/sv2v/releases/download/v0.0.13/sv2v-Linux.zip).
Archive SHA-256:
`552799a1d76cd177b9b4cc63a3e77823a3d2a6eb4ec006569288abeff28e1ff8`.
Extracted `sv2v-Linux/sv2v` SHA-256:
`b80a8ac6212aa72a196d9d6129cda35f16dbfa799ec61848c46321f845b6b635`.
The full probe records the executable path/hash and version. A missing converter
returns127 with an explicit failed-prerequisite status and log. Run
`python3 tests/open-toolchain/frontend/missing_tool.py CHECKOUT OUTPUT`
to check that failure contract independently of synthesis.
