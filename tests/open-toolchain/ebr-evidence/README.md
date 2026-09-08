# EBR mode and site-field evidence

Read-only tests reproduce the EBR.MODE mismatch in an independently published
**7000HC** design with mapped EBRs. At 13 of its 26 EBR sites, F1B35 is the
only unmet token in the pinned database's declared mode pattern. The complete
F1B32..F1B36 field equals the SC64 reference's site sequence at every site.
This establishes a reproducible database-pattern counterexample across
associated artifacts. It does not establish the field's physical function
or authorize a configuration encoder change.

No database, production RTL, license, or hardware changes occur. The probe
never writes a configuration. Earlier boundaries remain in the
[unknown-bit audit](../unknown-bits-audit.md) and
[public EBR audit](../timing-data/public-ebr-audit.md).

## Inputs and normal vendor reporting

The manufacturer publishes
[Forza4Graphical_Slideshow.zip](https://www.artekit.eu/resources/ak-machxo2-7000/Forza4Graphical_Slideshow.zip).
The archive SHA256 is
`ce7398e4bc639059f6ff565d11cf82f25193ad218379249bd9c0acb766776e6c`.
Its BIT SHA256 is
`d83edb0535aa6877e079548a5b3b4eb45e3ec5fea6b2d2761b5a4d4adc345481`.
The associated NCD loads as LCMXO2-7000HC, TQFP144, grade 6. Exporting it
through the installed vendor NCL writer succeeds:

```sh
export FOUNDRY=/usr/local/diamond/3.13/ispfpga
export LD_LIBRARY_PATH=$FOUNDRY/bin/lin64
"$FOUNDRY/userware/unix/bin/lin64/ncd2ncl" source.ncd output.ncl
```

This is the same normal NCL export tool invoked by pinned Trellis's
[diamond.sh](https://github.com/YosysHQ/prjtrellis/blob/3afe7b52b30f4b4417ee98f03016767a502006e3/diamond.sh).
The isolated official image is `ghcr.io/polprzewodnikowy/sc64env:v1.10`,
container `sc64-ngd-agent`. No map or bitgen is invoked. Archive membership,
matching names and reports support association but do not prove that this
NCD generated this BIT. The archive's bitgen report records `RamCfg:Reset`;
that setting alone does not identify the five-bit field.

The previous public CPU artifact is also exported to NCL and its JED
converted using the ordinary file-only deployment tool:

```sh
export LD_LIBRARY_PATH=/usr/local/diamond/3.13/bin/lin64:$FOUNDRY/bin/lin64
/usr/local/diamond/3.13/bin/lin64/ddtcmd -oft -bit -dev LCMXO2-4000HC \
  -if cpu.jed -of cpu.bit
```

Both operations exit 0. The initial deployment-tool launch lacked distro
`libusb-0.1.so.4`; installing Rocky's `libusb` package resolves that loader
prerequisite. The tool reports successful conversion despite a separate
default log-path warning. CPU BIT SHA256 is
`fc429681210d792875b15d30fe9eefc7978a8ed67e2776081a405311634d6fbf`.
The CPU source is the immutable
[STEP example](https://github.com/tocache/STEP-Lattice-MachXO2-FPGA/tree/9e0f3b5fba6f8258c72c1376feb8ae8ee99c86a5/lm8_tutor)
already identified by the public audit. It is a different-density control,
not a replacement for the 7000 evidence.

## Physical results

The pinned Trellis database revision is
`015e0330630d7c238c0e4f2cdd9c8157eb78c54a`; EBR1 `bits.db` SHA256 is
`e78069444eddb5f84e0fb74684a2d559bad366c6f2d36ba11549756d0cd3abb5`.
`probe.py` reads actual CRAM bits and the actual database mode tokens. It
joins an NCL EBR base site at column C to EBR1 at C+1, requiring every
exported EBR site to exist in the decoded device.

| Input | NCL EBR components | Nonzero field values | Mode mismatches |
|---|---:|---|---:|
| Active 7000HC | 24 DP8KC + 2 PDPW8KC | 3..28 across all 26 sites | 13 |
| CPU 4000HC | 6 DP8KC | 6..11 at six occupied sites; four others zero | 2 |

All 15 mismatches consist solely of F1B35 being unset. Every other token
required by the corresponding mode matches. The 7000 fields exactly
equal the SC64 sequence reported in the earlier audit. Unlike the idle
7000HE artifact's all-zero fields, both active designs correlate nonzero
fields with occupied sites. In particular, the 7000 design has **26**, not
24, active EBRs: its two PDPW8KC blocks must be counted alongside DP8KC.

The CPU NCL and exported Verilog independently contain **six DP8KC**
instances. The Verilog has six distinct wrapper modules, each instantiated
once and each containing one DP8KC leaf. The earlier public audit's
one-instance statement is incorrect.

Neither NCL export contains an RID property. WID is present and is not the
observed five-bit field: for example CPU EBR base R11C10 has WID=4 and
field=6, while R11C13 has WID=3 and field=7. No read-ID, initialization,
enable, or address function is assigned to the field here.

## Fuzzer confounding and corrective experiment

Pinned
[041-ebr_config/fuzzer.py](https://github.com/YosysHQ/prjtrellis/blob/3afe7b52b30f4b4417ee98f03016767a502006e3/fuzzers/machxo2/041-ebr_config/fuzzer.py)
fuzzes MODE at 1200HC EBR base R6C17, including EBR1 R6C18. Its NONE
case moves the EBR to R6C10 rather than leaving the same site occupied.
Its ignore list does not exclude F1B35, while a separate RID word fuzzer
is commented out. Thus occupancy and site-dependent bits can enter the
MODE pattern; that procedure alone cannot distinguish their semantics.

The 1200 database's sorted EBR1 columns are 2,5,8,11,15,18,21. The chosen
column18 is ordinal5, which would have field8 if the observed active-site
ordinal-plus-three sequence also held there. That would explain why only
F1B35 leaked into the mode pattern, but **no 1200 vendor bitstream is
tested here**. This remains a hypothesis, not a replacement encoding.

The justified next controlled fixture uses the exact 7000 device and
compares DP8KC/PDPW8KC/FIFO8KB at each fixed site with all other properties
held constant. A separate occupied-versus-empty comparison tracks the
entire five-bit field without calling it MODE. Initialization payload and
the vendor's supported RAM configuration settings must be varied
independently. Removing F1B35 from MODE or inventing an RID word before
those controls would exceed this evidence. These fixtures require a
supported source-to-configuration flow; they are not claimed executed.

## Reproduce and retained artifacts

In a pinned `sc64-open:7000` container, using the two successful NCL exports:

```sh
python3 -B tests/open-toolchain/ebr-evidence/test_probe.py
PYTHONPATH=/usr/local/lib/trellis /usr/bin/python3 \
  tests/open-toolchain/ebr-evidence/probe.py \
  --database /src/prjtrellis/database --bit source.bit --ncl output.ncl \
  --output result.json
```

Run the second command for each artifact pair. The parser test passes its
positive site/WID case and five rejection cases. Both full probes exit 0
and retain every site, mode, WID/RID inventory, unmet mode token and input
hash. A successful probe records mismatch evidence; it is not a successful
configuration qualification test.

Ignored `build/sc64-ebr-evidence/` contains `cpu.bit`, both NCL exports and
`cpu.json`/`active7000.json`. Original active7000 artifacts and archive
provenance remain under `build/sc64-active-7000-evidence/`; CPU source
artifacts remain under `build/sc64-public-ebr-audit/`. Generated vendor
artifacts are not redistributed beside these scripts.
