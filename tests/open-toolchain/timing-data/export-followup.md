# NGD timing export follow-up

Six `ngd2ltm` probes with the installed official SC64 toolchain fail with
exit 11 and `Can not find cell model MACO in cell model file.` None creates
an `.ltm` or `.spd` file. These tests provide no EFB, FIFO, or ODDRXE timing
arcs for the open backend.

The isolated container is `sc64-ngd-agent`, using
`ghcr.io/polprzewodnikowy/sc64env:v1.10`. The executable identifies itself
as Diamond 3.13.0.56.2. No licensing settings, production sources, or
hardware are changed. Generated vendor files and all logs remain in the
outer repository's ignored `build/sc64-timing-export-followup/` directory.

## Supported interface and tested cases

The installed executable's help advertises only:

```text
ngd2ltm [-odir <output_dir>] [-bin] [-p <rptfile>] <ngdfile>
```

It accepts `.ngd` or `.ngo`; `-bin` requests SPD instead of LTM. No
library-selection option is advertised. The normal vendor environment is:

```sh
export FOUNDRY=/usr/local/diamond/3.13/ispfpga
export LD_LIBRARY_PATH=$FOUNDRY/bin/lin64
```

Each export uses the following command shape, with its own output folder:

```sh
"$FOUNDRY/bin/lin64/ngd2ltm" -odir "$out" -p "$out/report.n2t" "$input"
```

| Case | Input or variation | Exit | Timing files |
|---|---|---:|---:|
| `ngd` | Existing successful SCUBA EFB NGD | 11 | 0 |
| `ngo` | Corresponding EFB NGO | 11 | 0 |
| `binary` | EFB NGD, additional `-bin` | 11 | 0 |
| `library_cwd` | EFB NGD, cwd `$FOUNDRY/xo2c00/data` | 11 | 0 |
| `fifo-control` | Stock FIFO SCUBA command, successful NGD build | 11 | 0 |
| `oddr-lattice-control` | ODDRXE leaf, successful NGD build | 11 | 0 |

Every row has the same MACO diagnostic. The EFB inputs come from ignored
`build/sc64-efb-compiler/reproduced-final/efb.ngd` and `efb.ngo`, generated
by the existing [SCUBA investigation](../efb/scuba/README.md). Their SHA-256
values are respectively:

```text
90f1d56bd09ea324b3698f6aef7a244925355de7b4a737c9ea8439d3fe601e47
cfc675f99c1f2fb58cfeee7d3a7b42193fae7de7cdc314a68139a0efca294550
```

## Independent primitive controls

The FIFO control uses the command recorded in SC64's generated
`fw/rtl/vendor/lcmxo2/generated/fifo_8kb_lattice_generated.v`:

```sh
"$FOUNDRY/bin/lin64/scuba" -w -n fifo -lang verilog -synth synplify \
  -bus_exp 7 -bb -arch xo2c00 -type ebfifo -depth 1024 -width 8 \
  -rwidth 8 -no_enable -pe 1 -pf 1023
"$FOUNDRY/bin/lin64/edif2ngd" -l MachXO2 -d LCMXO2-7000HC fifo.edn input.ngo
"$FOUNDRY/bin/lin64/ngdbuild" -a MachXO2 -d LCMXO2-7000HC input.ngo input.ngd
```

All three steps exit 0. The generated wrapper is not independently
token-compared against the committed wrapper in this test.

The ODDRXE control matches the SC64 leaf's `D0=1`, `D1=0`, `RST=0`, with
an external SCLK and output Q. It does not include the full PLL/OB chain.
Installed Yosys 0.68+195 (`435977e97-dirty`) generates its EDIF using:

```sh
yosys -Q -T -p 'read_verilog oddr.v; hierarchy -check -top oddr_probe; \
  hilomap -hicell VHI Z -locell VLO Z; write_edif -nogndvcc oddr-lattice.edn'
```

The same `edif2ngd` and `ngdbuild` options above both exit 0 on this EDIF.
An initial EDIF using generic GND/VCC passed `edif2ngd` but failed
`ngdbuild` with exit 2 because those two cells were unexpanded. That
setup failure remains in `oddr-control/ngdbuild.log`; it is not counted
as one of the six export failures. `write_edif` help documents using
`hilomap` with `-nogndvcc` to supply technology-specific constants.

## Installed library evidence and limits

The installed MachXO2 library files exist at:

```text
/usr/local/diamond/3.13/ispfpga/xo2c00/data/xo2clib.ngl
  SHA256 d98da03193c25c53c712ecbfed8e8308a68652e9f708f11c1db1f2a5cbc70f16
/usr/local/diamond/3.13/ispfpga/xo2c00/data/xo2clib.ttl
  SHA256 ebce80a7b2c22d4ccc35a925ae009689a91cd1ef0aad8b4aa5bd3a5e95d6890e
```

A filename search under Diamond 3.13 found no `.cml` or `.ltm` files.
The installed `ispfpga/maco/` directory exists, containing generator and
model sources with PCS/sysbus names. A strings scan of `xo2clib.ngl`
finds FIFO8KB and ODDRXE names but no exact MACO line. This scan does not
decode the library schema or establish which internal model file the
exporter expects. Running from the installed XO2 data directory does not
resolve the failure. No internal loader modification or undocumented
licensing workaround is attempted.

## Evidence ledger

The ignored output directory contains `help.log`, the four-case runner
`probe.py` and `results.json`, FIFO/initial-ODDR runner `controls.py` and
`controls.json`, and corrected ODDR runner `oddr_control.py` with
`oddr-lattice-controls.json`. Each JSON records exact executable arguments
and exit status; case folders retain vendor logs and reports. `oddr.v`,
both EDIF variants, and Yosys logs retain the control inputs.

The six failures leave timing extraction unresolved. Successful EDIF/NGD
conversion is not successful timing export, and these results do not
qualify any open-toolchain timing estimate or FPGA hardware change.
