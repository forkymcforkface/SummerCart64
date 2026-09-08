# Full SC64 open-toolchain integration audit

Read-only source audit, 2026-09-05. Sources: the SC64 `fw/project/lcmxo2/sc64.{ldf,lpf}`, generated vendor wrappers, firmware updater, and the pinned nextpnr/Trellis sources inside `sc64-open:7000` described in [README.md](README.md). No full synthesis, hardware operation or backend change is performed by this audit. Parent and other agents own the EFB/ODDRXE/FIFO8KB implementations.

The three unsupported cells are not the only blockers. A successfully routed diagnostic design must remain non-deployable until constraint coverage, initialization, configuration encoding and programming format have independent gates.

## Priority findings

### P0: LPF coverage is incomplete and sometimes silent

Pinned nextpnr `machxo2/lpf.cc::Arch::apply_lpf`:

- Requires `IOBUF PORT`; the actual `IOBUF ALLPORTS IO_TYPE=LVCMOS33` errors.
- Rejects `SDM_PORT` and `I2C_PORT` in its SYSCONFIG whitelist, although `machxo2/bitstream.cc` already has specific CFG0/CFG1 enum emission for them. Extending the whitelist can reuse that mechanism, but emitted bits still need verification.
- Silently ignores unhandled verbs including `BANK`, `VOLTAGE`, `RVL_ALIAS`, `DEFINE`, `INPUT_SETUP` and `CLOCK_TO_OUT`.
- Warns for unsupported `BLOCK` forms. Recognizing ASYNCPATHS/RESETPATHS does not itself prove equivalent path classification.
- Silently skips LOCATE/IOBUF targets absent from its cell map. A port lost or renamed during elaboration can therefore escape the original pin constraint.

Do not solve this by deleting unsupported lines and reporting a timing pass. Add fail-closed coverage: every original LPF statement maps to an implemented constraint or a separately justified equivalent, every physical port has the exact site/electrical intent, and every clock/exception/group resolves. No unconstrained-pin allowance or timing-allow-fail flag belongs in a cart qualification gate.

Exact timing intent requiring preservation:

| Original constraint | Required meaning to carry through |
|---|---|
| `FREQUENCY NET "clk" 100.000000 MHz` and `RVL_ALIAS "clk" "clk"` | Resolve the synthesized core clock and constrain it to 10 ns. |
| SDRAM bidirectional input group | All `sdram_dq[15:0]`: `INPUT_DELAY 5.4 ns`, `HOLD -2.5 ns`, reference `clk`, `CLK_OFFSET -0.25 X`. Preserve the reference edge/offset semantics, not just the numeric values. |
| SDRAM output group | CS/RAS/CAS/WE, BA[1:0], A[12:0], DQM[1:0]: `OUTPUT_DELAY 1.5 ns`, `MIN 0.8 ns`, reference `clk`, forwarded clock output `sdram_clk`. |
| SDRAM bidirectional output group | DQ[15:0], same 1.5 ns maximum/0.8 ns minimum and forwarded-clock relationship. |
| Path exceptions | ASYNCPATHS, RESETPATHS, JTAGPATHS; FROM button/usb_pwrsav/sd_det; TO mcu_int/n64_irq. Translate narrowly; do not blanket-disable more paths. |
| Electrical/configuration | Six banks at 3.3 V, `VOLTAGE 3.300 V`, per-port LVCMOS33/pulls, all LOCATE entries, `SDM_PORT=DISABLE I2C_PORT=ENABLE`. Preserve configuration-port access as well as normal I/O. |

The LPF writes `"sdram_bidir"INPUT_DELAY` without intervening whitespace. A strict replacement parser must recognize the quoted token boundary or normalize it explicitly with a checked parse; silently dropping that line is not acceptable.

### P0: PLL phase and analog attributes need an end-to-end check

The generated `pll_lattice_generated.v` requests a 50 MHz input, 100 MHz core clock and 100 MHz secondary clock at 270 degrees. Exact parameters include CLKI_DIV=1, CLKFB_DIV=2, output dividers=5, CLKOP CPHASE/FPHASE=4/0 and CLKOS=7/6. `pll.sv` forwards the secondary clock through ODDRXE and OB, and registers reset from PLL LOCK.

Existing nextpnr has EHXPLLJ packing, clock derivation and bitstream emission: reuse those before inventing a replacement PLL. However, `pack.cc` derives output periods using divider values and `simple_clk_contraint`; this is not proof that the secondary phase reaches external SDRAM timing analysis. Generated analog settings `ICP_CURRENT=9`, `LPF_RESISTOR=72` are synthesis comment attributes; `bitstream.cc` reads attributes and otherwise defaults to zero. Verify that Slang/Yosys retains these attributes in the emitted netlist, then inspect the packed configuration. Losing them while retaining digital divider parameters can falsely look correct. ODDR configuration without timing arcs likewise cannot qualify the forwarded-clock setup/hold paths.

### P0: EFB behavior cannot be recovered by guessing unknown stock bits

SC64's generated EFB enables UFM, with zero initialization, start page 2038, eight pages, DEV_DENSITY `7000L`, WB clock `100.0`, GSR enabled, and disabled timer/SPI/I2C1/I2C2 functional blocks. Dedicated configuration I2C in the LPF is a separate setting. `vendor.sv` exposes Wishbone operations to MCU control, so an empty EFB model or tied-off ACK is not equivalent.

The parent audit finds routing/fuzzer support but no UFM/configuration enums in the pinned MachXO2 tile database. A stock FPGA image can be a reference for readback and roundtrip checks, but one image does not identify which unknown bits implement EFB versus unrelated routing, RAM initialization or configuration. Copying all unknown bits into a newly routed design can preserve stale routing. A rigorous derivation needs documented fuse mapping or controlled reference builds that vary the EFB settings while holding placement/routing constant, followed by attribution and independent checks. No such derivation is established here. Until then, fail-closed diagnostic routing is useful; deployable EFB support is not proved.

### P0: Native bitstream output is not SC64's update payload

`build.sh` passes Diamond's `.jed` into `sw/tools/update.py`. Its `JedecFile` reads continuous configuration fuses, packs their bit order, and stops at `NOTE END CONFIG DATA`; the firmware updater consumes the resulting chunk through its existing programming protocol. Trellis `ecppack` has MachXO2 serialization, but producing its `.bit`/SVF does not produce that JEDEC-derived payload.

Reuse the existing update container/checksum and MCU programming flow. Any open-output adapter must independently verify device ID, exact configuration region, frame/fuse ordering, lengths, CRC/checksums, RAM initialization and configuration/UFM boundaries against a known-good package/readback. Never rename a `.bit` as `.jed`, or treat container checksum success as FPGA equivalence. Preserve the documented programming/recovery interfaces and feature configuration.

### P1: Initialization and design completeness need explicit gates

`n64_cic.sv` loads `../../../sw/cic/build/cic.mem` into its RAM. The current probe uses the correct project working directory and hashes this input; extend verification through inferred memory, INITVALs and final configuration bytes. A nonempty file or successful `$readmemh` is insufficient if packing drops or changes its data. Verify read/write width, byte lanes and collision behavior for inferred RAM, independently of the FIFO8KB replacement work.

The LDF source list, top, exact `LCMXO2-7000HC-6TG144C` part/package/speed grade, all bidirectional I/O enables, reset/startup values and generated parameters must survive elaboration. Reject blackboxes and unresolved cells at each stage; count and inspect expected PLL, EFB, clock I/O, RAM and physical ports after optimization. The existing probe is a synthesis diagnostic only: it hashes the LPF but does not apply it, and explicitly sets hardware qualification false. Retain that honest distinction.

## Acceptance sequence

1. Unit fixtures for each added primitive, including reset, initialization, backpressure and timing/configuration coverage. Functional simulation and routing acceptance are separate results.
2. Full unchanged SC64 elaboration and netlist audit; complete LPF coverage; configuration-bit roundtrip and update-payload comparison. Record all warnings and reject unresolved constraints or unsupported primitives.
3. Full device fit and timing, including generated/forwarded clocks, min/max external paths, reset release and all existing interfaces. An internally reported Fmax cannot substitute for SDRAM I/O timing.
4. Preserve a known-good firmware backup and the applicable recovery route from `docs/00_quick_startup_guide.md` and `docs/06_build_guide.md`. Unchanged MCU/loader alone does not guarantee recovery from a bad FPGA configuration. No recovery was exercised by this audit.
5. Only then test the unchanged functional cart: boot/CIC, CFG, USB, SD, SDRAM guards/data patterns, saves and reset/update behavior. Add GIF integration only after the open baseline is qualified; retain separate measurements and rollback evidence.

These gates identify missing evidence rather than assuming failure of every existing backend feature. The upstream README is older than several implemented PLL/RAM mechanisms; inspect actual pinned code and test results rather than treating its TODO list as the implementation inventory.
