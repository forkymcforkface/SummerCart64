# Offline vendor timing export investigation

Checked 2026-09-05 using the official SC64 environment image
`ghcr.io/polprzewodnikowy/sc64env:v1.10`. This is file-only research: no
hardware access, license modification, vendor-file redistribution, or new
FPGA source-build qualification. The broader tool inventory remains in
[research-tools.md](research-tools.md).

## Verified report generation

Diamond 3.13 includes a routed MachXO2-1200HC example at:

```text
/usr/local/diamond/3.13/examples/Board-SWDemo_MachXO2/
Demo_MachXO2_Control_SoC/Diamond_project/impl1/control_SoC_demo_impl1.ncd
```

The following commands run successfully against that installed example. Here
`p` denotes its complete path without `.ncd`; `/out` is an ignored output
directory mounted into the container.

```sh
export FOUNDRY=/usr/local/diamond/3.13/ispfpga
export LD_LIBRARY_PATH=$FOUNDRY/bin/lin64
timeout 20 "$FOUNDRY/bin/lin64/iotiming" -v "$p.ncd" "$p.prf" \
    -o /out/vendor-example.ior
timeout 20 "$FOUNDRY/bin/lin64/ldbanno" -n verilog -neg -sp 6 \
    -o /out/vendor-1200.v -d /out/vendor-1200.sdf "$p.ncd" "$p.prf"
```

Both exit 0 without changing license configuration. The I/O report is 7544
bytes and includes grades M, 4, 5 and 6. Its obsolete example preference
produces a warning about `GENERATE_BITSTREAM`; this warning is retained in
the logs rather than silently removed. The backannotation log independently
identifies `LCMXO2-1200HC`, speed 6. The SDF declares:

```text
(VOLTAGE 1.26:1.20:1.14)
(PROCESS "default")
(TEMPERATURE -40:25:85)
(TIMESCALE 1ps)
```

It contains cell `IOPATH` timing triples. These are usable evidence of the
supported export format, not substitute timings for SC64's 7000HC. The
installed documentation says `iotiming` requires a placed-and-routed NCD;
its preference file controls voltage, temperature and DDR-related behavior.
`ldbanno` accepts mapped, at least partially placed/routed NCD, exports
Verilog/VHDL and SDF, and supports `-sp`, `-min` and `-neg`. In particular,
negative setup/hold numbers otherwise default to zero, and minimum-delay
hold verification is a separate export/simulation case.

Primary installed documentation, relative to `/usr/local/diamond/3.13/`:

- `docs/webhelp/eng/Reference Guides/Command Line/Running_I_O_Timing_from_the_Command_Line.htm`
- `docs/webhelp/eng/Reference Guides/Command Line/running_back_annotation_from_the_command_line.htm`

Generated evidence, relative to the PhosphorOS checkout, is ignored under
`build/sc64-open-release-agent/`: `vendor-iotiming.log`,
`vendor-example.ior`, `vendor-1200-ldbanno.log`, `vendor-1200.v`, and
`vendor-1200.sdf`.

The parent independently repeats both commands in a fresh official-image
container: exit 0, actual 1200HC speed 6, same SDF corner/unit declarations.
Evidence: `build/sc64-open-release/parent-timing.log` and `parent-1200.*`.

An earlier probe used the installed directory
`examples/Reveal_debugger/counter_reveal_MACHXO2/impl1/`. Its project file
names 7000HC, but its supplied NCD actually identifies **LFE3-35EA**. Thus
the successful `vendor-7000-ldbanno.log` and `vendor-7000.sdf` artifacts
are ECP3 results despite their historical filenames. They provide no
MachXO2-7000 evidence. Always inspect the loaded device in the tool output.

## Exact 7000 database lead and unresolved schema

The image contains the exact-density files beneath
`/usr/local/diamond/3.13/ispfpga/xo2c00a/data/`:

| File | SHA-256 |
| --- | --- |
| `xo2c7000.spd` | `af2d8aa9a00f86171c134b496ad3e6bc44bc256acdbd7b3099de10392ae399c1` |
| `xo2c7000.tld` | `5db2945095e8ea736c86e6ab35fa086d488c0d674cddd55ee47b03224a1913ca` |

The binary SPD visibly contains named delay/check records such as
`GSRREC_HLD`, `CE_SET`, and conditional `MODE:IDDR_ODDR` records. It
identifies hardware data version `Final 34.4`. These observations do not
establish record structure, units, every speed grade, voltage/temperature
scaling, minimum corners, or complete timing-arc coverage. No numeric
values from this binary have been imported into Trellis. The installed
`ispfpga/verilog/data/machxo2/ODDRXE.v` is functional modeling source and
has no `specify` block supplying the missing routed timing data.

The concrete next implementation is a bounded exact-7000 primitive export
fixture with explicit part, grade, operating conditions and arc inventory,
feeding Trellis's existing SDF importer. A direct SPD parser would need an
independently checked schema and matching exported SDF before its numbers
could be used. No complete extractor was established by this investigation.

## NCL conversion remains license gated

Trellis already uses the following conversion and backannotation mechanics
in [diamond.sh at 3afe7b5](https://github.com/YosysHQ/prjtrellis/blob/3afe7b52b30f4b4417ee98f03016767a502006e3/diamond.sh):

```sh
"$FOUNDRY/userware/unix/bin/lin64/ncl2ncd" input.ncl -drc -o par_impl.ncd
"$FOUNDRY/bin/lin64/ldbanno" -n Verilog par_impl.ncd synth_impl.prf
```

A bounded test retargeted Trellis's `fuzzers/machxo2/109-efb/empty.ncl`
device declaration to `LCMXO2-7000HC`, retaining TQFP144 and speed 6.
`ncl2ncd` exits **99**, reporting missing license file and required
`LSC_BASE`. The image's `/flexlm/license.dat` is absent; explicitly trying
the normal Diamond installation license path also reports it absent. No
license bypass or successful NCD generation occurred. Logs are
`empty-7000-ncl2ncd.log` and `empty-7000-configured-license.log` beside
the ignored `empty-7000.ncl` fixture. This does not establish the result
with the parent's separately available expired license.

`ncd2ncl` on the supplied 1200HC example wrote partial output but exceeded
the 20-second bound: exit 124. `vendor-ncd2ncl.log` and `vendor-1200.ncl`
are incomplete evidence, not a conversion pass. Help probes of undocumented
`arcdump`/`incdelay` did not establish a usable reporting interface.

Normal renewed licensing can enable controlled reference fixture creation;
successful report generation alone does not replace synthesis or routing.
The [Lattice licensing matrix](https://www.latticesemi.com/license) lists
MachXO2 in Diamond's free tier. No claim is made that its licensed tools
are open source or that installed data may be redistributed.

## Reference routing is not an all-source rebuild

The official `sc64-extra-v2.20.2.zip` contains no `.ncd`, `.ncl`, `.sdf`,
`.prf`, `.jed` or `.bit` assets. Its provenance and exact reference replay
are recorded in [release/README.md](release/README.md).

Trellis's [ecp_vlog.py](https://github.com/YosysHQ/prjtrellis/blob/3afe7b52b30f4b4417ee98f03016767a502006e3/tools/ecp_vlog.py)
is a concrete connectivity/netlist extraction starting point, but explicitly
generates ECP5 slice and DP16KD memory models. It is not a complete MachXO2
extractor. Extending it requires exact MachXO2 primitive semantics, configured
routing connectivity, initial memory state, and fail-closed treatment of
unhandled configuration, including the reference's 433 unknown records.

An independently extracted reference netlist proved equivalent to RTL could
strengthen confidence in the reference implementation. It would still be
**reference-derived placement/routing**, not a placement/routing result
generated from that RTL. The existing exact serialization reproduces the
official command bytes from decoded reference configuration; it does not
solve nextpnr's route failure or supply missing timing constraints. None of
these file-only results qualifies a new cart image for programming.
