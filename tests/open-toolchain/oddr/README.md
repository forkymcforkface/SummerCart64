# ODDRXE diagnostic backend support

This patch adds explicit, untimed research support for MachXO2 ODDRXE output
registers. It uses existing Trellis IOLOGIC BELs and routing, emits the existing
fuzzed output-DDR configuration fields, and preserves the SC64 clock topology.
It does **not** make a hardware-qualified FPGA image. Normal use fails closed;
`--oddr-diagnostic` is an explicit opt-in for these investigations.

## Reproduce

Inside a private `sc64-open:7000` container with the checkout mounted at `/sc64`:

```sh
/usr/bin/python3 /sc64/tests/open-toolchain/oddr/apply.py /src/nextpnr
cmake --build /src/nextpnr/build -j 4
/usr/bin/python3 /sc64/tests/open-toolchain/oddr/probe.py /sc64 /out/oddr
/usr/bin/python3 /sc64/tests/open-toolchain/oddr/negative.py /out/oddr
```

`apply.py` expects the pinned source layout from the owning toolchain README.
Each replacement checks its unique anchor and fails on drift. It changes only
`machxo2/{main.cc,pack.cc,arch.cc,bitstream.cc}`. The patch does not change firmware,
RTL, the Trellis database, the device pinout or any proprietary library. Do not
apply it repeatedly to the same source tree. Output directories must be unused.
The declaration `oddrxe_decl.v` preserves an unknown primitive during synthesis;
it is not a functional replacement or timing model.

Tested base image ID:
`sha256:9632531eb216aefc18f12f8de0c005faef60b433df37e11b59bac0a1c8a45d3a`.
Nextpnr is `8dbcee5c3c4415770b6fd06d5ccb2db89545b8ec`, Trellis is
`3afe7b52b30f4b4417ee98f03016767a502006e3`. The private build remains in container
`sc64-oddr-agent`; generated evidence is under `build/sc64-open-oddr/` in the
outer PhosphorOS checkout.

## Implemented boundary

A primitive must drive exactly one explicitly pin-constrained output PIO. The
packer selects its adjacent IOLOGIC BEL, maps D0/D1 to OPOS/ONEG, SCLK to CLK,
RST to LSR, and Q through IOLDO into the original output buffer. No LUT clock
substitute or combinational clock bypass is inserted. The pin61 SC64 instance
maps to `X30/Y27/BIOLOGICA`, beside `PIOA`.

The configuration writer enables IOLOGIC MODE=IDDR_ODDR, output clock/reset
muxes, GSR and PIO DATAMUX_ODDR=IOLDO. Existing database routing carries the
clock and data to those actual BEL pins. Timing classification deliberately
marks data endpoints/startpoints as untimed; it supplies no invented register
setup, hold or clock-to-output arcs. Both primitive packing and previously
packed IOLOGIC use require the explicit diagnostic setting.

The unchanged generated SC64 PLL wrapper also exposes constant-low Wishbone
inputs that have only fixed EFB-to-PLL connectivity in Trellis. Fabric GND
cannot route to them. For this diagnostic, the packer disconnects only these
unused inputs when PLL_USE_WB and PLLRST_ENA are both DISABLED; every connected
input must be constant zero. An enabled bus/reset or nonzero/dynamic input is
rejected. PLL parameters and active clock paths remain unchanged.

## Source metadata preservation

Native Yosys `read_verilog` drops the generated wrapper's `synthesis` comment
attributes ICP_CURRENT and LPF_RESISTOR. The upstream writer otherwise silently
uses zero. Diagnostic PLL configuration now rejects either missing attribute.

`preserve_pll_metadata.py WRAPPER INPUT.json OUTPUT.json MANIFEST.json` reads
these two exact decimal source attributes, verifies uniqueness/ranges and one
expected PLL instance, rejects conflicts, then adds their numeric equivalents
to a separate diagnostic JSON. It records wrapper/input hashes and copied
values. No source file or analog value is changed. The probe also hashes the
original PLL wrapper, generated PLL and project LPF. Full-design tooling must
perform this preservation explicitly; adding a primitive declaration is not
sufficient.

## Evidence and unresolved constraints

Both the data-driven primitive and unmodified SC64 PLL/ODDR/OB wrapper pass
synthesis, diagnostic place/route, ecppack and ecpunpack. Normal mode rejects
both with exit125. The SC64 test additionally verifies routed connectivity:
CLKOS directly supplies the IOLOGIC clock, D0=1 and D1=0 retain their respective
pins, RST remains zero and the original output buffer takes IOLDO. Original
100 MHz divider/phase settings and source-derived analog values survive
bitstream roundtrip checks. Input pin3 and output pin61 follow the SC64 LPF;
other diagnostic outputs may be placed automatically.

Negative cases reject active PLL Wishbone, nonzero unused WB input, enabled
PLL reset, either missing analog attribute and an unconstrained output. Reloading a routed JSON also requires fresh
command-line opt-in, despite its saved settings. These
checks are fail-closed errors, not warning-only substitutions.

There is a database ambiguity: in PIC_B0, IOLOGICA.CLKOMUX values CLK and INV
both encode F3B27. The writer requests CLK but ecpunpack canonicalizes it to
INV. The probe reports the intended enum and accepts only that known alias
on readback; it does not claim this proves physical clock polarity. The actual
routing connects the original positive clock net through the database clock
wires, but hardware/reference-tool confirmation of polarity remains required.

The MachXO2 speed6 timing database contains no IOLOGIC/ODDR timing arcs. PLL
jitter, analog setup, actual DDR edge behavior, timing closure and board
operation remain unvalidated. The diagnostics are neither production firmware
nor permission to flash them. Earlier preliminary outputs before source analog
metadata preservation are not authoritative PLL configurations.

Primary evidence:

- [Trellis MachXO2 IOLOGIC BEL definitions](https://github.com/YosysHQ/prjtrellis/blob/3afe7b52b30f4b4417ee98f03016767a502006e3/libtrellis/src/Bels.cpp)
- [Trellis MachXO2 DDR configuration fuzzer](https://github.com/YosysHQ/prjtrellis/blob/3afe7b52b30f4b4417ee98f03016767a502006e3/fuzzers/machxo2/061-basic_ddr/fuzzer.py)
- [Lattice high-speed interface guide, ODDRXE and forwarded-clock examples](https://www.latticesemi.com/-/media/LatticeSemi/Documents/ApplicationNotes/IK2/FPGA-TN-02153-1-9-Implementing-High-Speed-Interfaces-with-MachXO2-Devices.ashx?document_id=39084)

The installed Diamond3.13 ODDRXE model was inspected read-only to check port
order, GSR default and reset semantics. No proprietary model text is distributed
here, no licensed operation is bypassed, and that inspection is not bitstream
validation.
