# Tools that can close the remaining MachXO2 gaps

Research checked 2026-09-05. No hardware access, license alteration, firmware
changes, or production source changes occur in this investigation. The useful
next steps are controlled configuration comparisons and MachXO2-specific SDF
fixtures. Switching synthesis frontends does not supply EFB fuse definitions.

## Verified inventory

| Tool or source | Checked version | Result and useful boundary |
| --- | --- | --- |
| nextpnr MachXO2 | `8dbcee5c3c4415770b6fd06d5ccb2db89545b8ec` | `git ls-remote origin HEAD` equals our pin. Updating upstream main supplies no additional implementation today. |
| Project Trellis | `3afe7b52b30f4b4417ee98f03016767a502006e3`; ecppack `1.4-82-g3afe7b5` | Upstream HEAD also equals our pin. Existing configuration diff and SDF import infrastructure is reusable. |
| Yosys | `0.68+195`, `435977e97-dirty` | Version command passes in the pinned image. Synthesis is already available; hard-cell mapping still belongs to nextpnr/Trellis. |
| Slang / sv2v | See the pinned [frontend experiment](frontend/README.md) | Their elaboration/high-impedance differences must remain independently checked. Neither is a timing or EFB configuration database. No duplicate frontend experiment was run here. |
| Apicula | Current upstream README inspected | Gowin bitstream tools and `synth_gowin`, not an alternative MachXO2 backend. No installation is warranted for this cart. [Primary repository](https://github.com/YosysHQ/apicula). |
| Diamond installed utilities | Official SC64 environment v1.10, Diamond 3.13 | Installing Rocky's real libusb package resolves startup. File-only JEDEC/bitstream conversion passes; see the completed experiment below. The utility identifies itself as Deployment Tool 3.12. |
| Trellis JEDEC fork | `cr1901/prjtrellis`, head `839f9f51f61a09bb7397a122333bc212521543c5` | Concrete unmerged source lead, not a drop-in fix. Its two-commit patch fails `git apply --check` against our current pin at `ecppack.cpp` lines 29/42. |

The isolated inventory container uses `sc64-open:7000`, image SHA-256
`9632531eb216aefc18f12f8de0c005faef60b433df37e11b59bac0a1c8a45d3a`.
Source trees remain unchanged. GitHub's public API returned 16 open Trellis
PRs; #233 was the relevant packaging lead. A bounded first-page search of open
nextpnr PR titles found no FIFO/EFB/MachXO2 replacement. This is not an exhaustive
audit of every fork or unpublished implementation.

## Separate UFM data packaging from EFB configuration

[Trellis PR #233](https://github.com/YosysHQ/prjtrellis/pull/233) adds JEDEC
generation in `libtrellis/tools/ecppack.cpp`. It remains a draft and explicitly
lists UFM initialization, feature fields, and Diamond compatibility as unfinished.
Its proposed `.ufm_init` and `.ufm_start_page` fields are useful design leads,
not implemented capabilities we can rely on. Rebase and test it as a separate
format experiment; do not claim that producing a JED enables EFB.

The [SC64 EFB wrapper](../../fw/rtl/vendor/lcmxo2/generated/efb_lattice_generated.v)
requests eight zero-initialized pages starting at 2038, plus `EFB_UFM=ENABLED`.
This creates at least two independently testable requirements: the initial
flash contents and the mechanism that exposes the Wishbone path. Existing
Trellis `109-efb` fuzzers discover interconnect; inspection confirms they do not
run a parameter-to-configuration-bit sweep. A physical BEL and routable pins
therefore do not settle the second requirement. Conversely, absent EFB enums
do not prove that an additional static EFB enable fuse exists.

A useful next experiment, **proposed, not executed**, is to compare official
reference outputs for the exact same constrained tiny design while changing
only (a) EFB_UFM, (b) UFM_INIT_START_PAGE, (c) page count, and (d) known page
patterns. Decode each configuration, initialization region, feature field,
device ID, and checksum separately. Repeat identical inputs first to identify
nondeterministic output. Preserve unrelated routing and unknown bits as
evidence, never transplant them into a new routed design.

The public [MachXO2 programming/configuration guide](https://www.latticesemi.com/-/media/LatticeSemi/Documents/ApplicationNotes/MO/MachXO2ProgrammingandConfigurationUsageGuide.ashx?document_id=39085)
and [UFM access FAQ](https://www.latticesemi.com/support/answerdatabase/1/4/0/1409)
provide the programming protocol and access interfaces. Those are a basis for
an independent format checker, but do not by themselves identify all EFB
parameter fuse positions. Programmer conversion of an existing valid artifact
can help compare formats; new parameter sweeps still require an implementation
flow capable of generating controlled reference configurations.

The [EFB register reference, Table 16.2](https://www.latticesemi.com/view_document?document_id=46300)
defines CFGCR[WBCE] at address 0x70 as a runtime connection enable, reset to
zero. Command framing sets it before a command and clears it afterward. The
[UFM usage guide, sections 9–10](https://www.latticesemi.com/view_document?document_id=39086)
separates UFM initialization data from configuration storage modes and describes
Wishbone access to configuration flash. Therefore classify parameters into
runtime registers, initialization contents, static configuration, and fabric
routing before searching for fuses. The exact classification of every SC64
EFB parameter remains unverified; do not invent static enable bits.

## Completed file-conversion experiment

An isolated official-image container installs
`libusb-1:0.1.5-12.el8.x86_64` with normal `dnf -y install libusb` from Rocky's
repositories. This is a real compatibility library, not a shim. Its installed
`libusb-0.1.so.4` SHA-256 is
`f31d4153d2a21d5df15fc38576f0d40b3350866942697773a441f3c9d4efd3a6`.
No license setting or hardware access changes. The installed help at
`docs/webhelp/eng/Reference Guides/Command Line/running_the_universal_file_writer_from_the_command_line.htm`
documents the following file-only modes:

```sh
ddtcmd -oft -jed -dev LCMXO2-7000HC -if input.bit -of output.jed
ddtcmd -oft -bit -dev LCMXO2-7000HC -if input.jed -of output.bit
ddtcmd -oft -jed2bin -dev LCMXO2-7000HC -if input.jed -of fuses.bin
ddtcmd -oft -rbt -if input.bit -of output.rbt
```

Here `-dev` selects the file's chip format; no connected device, cable, or
programming operation is selected. Each command runs with a 20-second bound.

| Input and operation | Observed result |
| --- | --- |
| Official raw `.bin` or Trellis `.bit` to JED without `-dev` | Exit 244, unknown device. |
| Official raw `.bin` to JED with exact device | Exit 232, unsupported input file type. |
| Byte-identical official raw renamed `.bit`, exact device | Exit 0, JED generated. No synthesized header is needed by this converter. |
| Trellis diagnostic `.bit` to JED to `.bit` | All exits 0. Independently unpacked complete configurations match after excluding only `.comment` metadata lines. Binary file hashes differ because metadata/compression differ. |
| Official converted JED to raw fuse bytes | Exit 0, 180,160-byte output. |
| Trellis `.bit` to ASCII RBT | Exit 0. |

The official source is the 104,144-byte FPGA chunk from release `18041e2`,
SHA-256 `c4bd900a8727cfeb4906bf27a8795246e3039b3071cc879c19ab0969139bf1ee`.
The resulting JED has QF=1,441,280, an EBR initialization note, END CONFIG DATA
followed by L833024, and separate FEATURE_ROW/USERCODE fields. It has no
EFB-specific metadata section. Raw fuse export begins at `bdb3ffff...`, whereas
the source begins `ffffbdb3ffff...`; these are not interchangeable payloads.
The converter's padding/default initialization does not prove original UFM
contents that were absent from its input.

Logs and generated artifacts remain ignored under
`build/sc64-programmer-research/` in the parent checkout. The official JED
SHA-256 is `dd1c7fe71b94c72bb735466ccd92bfef79f161564a463a4c0e83b61309508b12`;
raw fuse export SHA-256 is
`0ff67841aa50f2479aa39685a7bebd3e507e39a93bef8fa376e665b72f03e530`.
This closes a practical format-inspection prerequisite. It does not qualify
EFB operation, timing, unknown configuration bits, or a new image for flashing.

## Reuse the timing infrastructure instead of inventing delays

Source inspection found a concrete starting point:
[MachXO3 013-iol](https://github.com/YosysHQ/prjtrellis/tree/3afe7b52b30f4b4417ee98f03016767a502006e3/timing/fuzzers/MachXO3/013-iol)
already extracts IOLOGIC SDF cells through `cell_fuzzers.build_and_add`.
MachXO2 has no corresponding 013-iol directory. Its
[014-ebr fixture](https://github.com/YosysHQ/prjtrellis/tree/3afe7b52b30f4b4417ee98f03016767a502006e3/timing/fuzzers/MachXO2/014-ebr)
extracts DP8KC register/write modes, not FIFO8KB. The common
`timing/util/cell_timings.py` imports SDF into the timing database.

**Proposed:** adapt the fixture structure to exact XO2-7000 speed-6 ODDRXE,
FIFO8KB, and EFB Wishbone cases, preserving both clock domains and reset arcs.
Collect setup/hold, clock-to-Q, and relevant recovery/removal constraints from
the reference implementation. Check that every expected arc appears and reject
missing arcs. MachXO3 numbers must not be copied into MachXO2. Vendor simulation
models with functional checks remain useful, but do not replace routed timing.
This work can use the existing Trellis ownership and file format rather than a
parallel timing database.

## Vendor utility and licensing boundary

Lattice's [standalone Programmer FAQ](https://www.latticesemi.com/en/Support/AnswerDatabase/3/9/3/3932)
says it normally requires no license, with a caveat for older/mature devices.
The [Programmer product page](https://www.latticesemi.com/programmer) identifies
Deployment Tool's conversion functions. This makes independent format
inspection promising; it does not establish that Diamond map/PAR/trace can run
without their required license. No such bypass was attempted.

The current [licensing matrix](https://www.latticesemi.com/license) lists
MachXO2 under Diamond's free tier, while
[SC64's official build instructions](https://github.com/Polprzewodnikowy/SummerCart64/blob/main/docs/05_fw_and_sw_info.md)
require a valid annual license for its reference FPGA build. A renewed normal
license remains the direct route to controlled reference outputs; an expired
bundled license is not evidence that a different synthesis frontend can replace
the entire backend.

## Why SC64 recovery must remain part of qualification

The [official site](https://summercart64.dev/) links directly to the
[build guide](https://github.com/Polprzewodnikowy/SummerCart64/blob/main/docs/06_build_guide.md)
and [bill of materials](https://summercart64.dev/bom.html). The GitHub `/wiki`
URL redirects to the repository; the checked-in docs are the usable source.
The guide identifies separate FPGA/MCU programming through the board connector
when the normal path cannot recover. Recovery availability is not evidence that
an incomplete bitstream is safe to install.

The actual [MCU FPGA programmer](../../sw/controller/src/lcmxo2.c) uses the
Wishbone configuration registers and erases CFG and UFM together in its flash
erase operation. Consequently, removing EFB to obtain a successful route can
also remove the firmware's normal FPGA programming path. Keep the unchanged
EFB functionality, zero-initialization contract, feature settings, and complete
programming format in the acceptance gate. No cart experiment follows from
this document alone.
