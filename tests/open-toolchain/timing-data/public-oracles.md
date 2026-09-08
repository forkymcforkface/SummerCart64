# Public mapped 7000 timing oracles

Checked 2026-09-05. Two public author repositories provide real mapped
MachXO2-7000HE NCDs. The official Diamond 3.13 reporter accepts both
without a new compilation or license modification. Neither examined
design supplies the missing EFB/FIFO/ODDR hard-block timing oracle.

## Verified SDR artifact

Source: [alberto-grl/1bitSDR](https://github.com/alberto-grl/1bitSDR/tree/3e2e01da0357b38a9badff832c65a185b2fdcaf0),
commit `3e2e01da0357b38a9badff832c65a185b2fdcaf0`.

Download `impl1/FPGASDR_impl1.ncd`, its adjacent `.prf`, and `FPGASDR.ldf`
from that commit. The NCD is 4,696,533 bytes, SHA256
`7abfced1b9a8d34dac34190676993e1fda2eacb1089728aa7f064d4e0e577e90`.
The 1,890-byte PRF hashes to
`dbd47675ea8d1181801c1967666ce916c6df379e63e7bdb12e4a60f3b2aa98f3`.

The LDF names `LCMXO2-7000HE-4TG144C`; importantly, the reporter itself
loads **LCMXO2-7000HE, TQFP144**. This is HE, not SC64's HC part, and the
following explicit grade override is a timing experiment, not the
original design's grade-4 performance result.

Inside the official `ghcr.io/polprzewodnikowy/sc64env:v1.10` image:

```sh
export FOUNDRY=/usr/local/diamond/3.13/ispfpga
export LD_LIBRARY_PATH=$FOUNDRY/bin/lin64
timeout 20 "$FOUNDRY/bin/lin64/ldbanno" -n verilog -neg -sp 6 \
    -o /tmp/sdr.v -d /tmp/sdr.sdf /tmp/sdr.ncd /tmp/sdr.prf
timeout 20 "$FOUNDRY/bin/lin64/ldbanno" -n verilog -neg -min \
    -o /tmp/sdr-min.v -d /tmp/sdr-min.sdf /tmp/sdr.ncd /tmp/sdr.prf
```

Both commands exit 0, reporting performance `6` and `M` respectively.
They preserve the negative setup/hold values. No source synthesis,
placement/routing, hardware operation or unknown executable is involved.

The scoped comparisons against the exact installed `xo2c7000.spd` are:

| SDF cell and pin | Grade-6 SDF, ps | Minimum SDF, ps | Direct M-slot extrema match? |
|---|---|---|---|
| PWM1_SLICE_0, CLK to Q0 | 320:343:367 | 133:143:154 | No |
| uart_rx1_SLICE_14, CE setup to rising CLK | 176:196:217 | 71:79:88 | No |
| uart_rx1_SLICE_14, CE hold to rising CLK | -76:-68:-61 | -30:-27:-24 | Yes |
| SinCos1_SLICE_133, M1 setup to rising CLK | 202:230:258 | 76:88:101 | No |
| SinCos1_SLICE_133, M1 hold to rising CLK | -118:-106:-94 | -42:-30:-19 | Yes |

These are the first matching cells for each pin class; the very first
SLICE does not contain all five checks. The CLK-to-Q rise and fall ranges
are identical in the reported cell. All five grade-6 ranges match the
corresponding stored four-slot envelope. The M-section mismatch on three
positive checks reproduces the installed 1200 observation on an actual
7000. It does not identify the transformation: no scalar, slew correction,
interconnect correction or corner rule is inferred from these samples.

The full generated Verilog and both complete SDFs are preserved in ignored
`build/sc64-timing-public/sdr-export.{v,sdf}` and `sdr-min.{v,sdf}`, so
cell configuration and every transition range remain available for later
comparisons. `compare.json` records the selected cell, four raw slots,
calculated envelope and actual range for each check; `compare.py` is the
ignored experiment driver. `manifest.json` records file hashes, including
the timestamped exports. Their hashes identify this run, not a guarantee
that a later timestamped export has identical bytes.

## Other concrete searches

The [itxs/Lattice-LCMXO2-FPGA](https://github.com/itxs/Lattice-LCMXO2-FPGA/tree/7645ecc46ac35173e93ba8bb0494afe0aad32f3e)
SPI design's `spi_slave/default_impl/spi_slave_default_impl.ncd` also
exports at grade 6 with exit 0 and loads **LCMXO2-7000HE**. Its 42,988-byte
NCD hashes to
`cbb9a0e369d3cecb207db9380d9969ea8d5eaf49f4d123f1888f9f4a8d0671a3`.
Its adjacent PRF hashes to
`1692b05473df21fa6daa7ec1bad80ea0f5d7b15b62031ba5dd98d00e98fba658`.
The SPI title does not make it a hard EFB oracle: exported SDF has none of
the searched EFB/Wishbone, FIFO, ODDR or IOLOGIC indicators.

The public [xjordanx/lattice_efb](https://github.com/xjordanx/lattice_efb/tree/2e147a2107b43d67db92ee6294fa4b24331f5268)
tree contains no NCD/SDF/LTM/NCL artifact. A bounded GitHub API inventory
examined 22 repository trees, recording immutable tree SHAs and truncation
flags under the ignored output directory. This is not an exhaustive search
of all public history or releases.

The official [MachXO2 Breakout Board page](https://www.latticesemi.com/products/developmentboardsandkits/machxo2breakoutboard)
links its 7000HE demo as document 50476, version 1.0, 23.1 KB. Requesting
that document currently redirects to account sign-in; the downloaded
39,979-byte response is HTML, not a ZIP. It was identified and rejected as
an archive. No archive-content or mapped-design claim is made for it, and
no authenticated download requirement was bypassed.

## Public timing tooling

The pinned [Trellis MachXO2 EBR fuzzer](https://github.com/YosysHQ/prjtrellis/blob/3afe7b52b30f4b4417ee98f03016767a502006e3/timing/fuzzers/MachXO2/014-ebr/fuzzer.py)
explicitly builds density 7000 DP8KC register/write-mode fixtures.
Its [cell_fuzzers.py](https://github.com/YosysHQ/prjtrellis/blob/3afe7b52b30f4b4417ee98f03016767a502006e3/timing/util/cell_fuzzers.py)
selects HE grades 4/5/6 and ZE grades 1/2/3, calls `build_design` with
backannotation, then feeds SDF to the cell database importer. This is a
concrete future fixture workflow, not an installed-SPD parser or a route
around the unavailable licensed compilation step. The examined MachXO2
timing tree has basic-cell, I/O, EBR and routing fuzzers; it does not supply
a dedicated EFB/FIFO/ODDR timing fixture oracle.

## Official SC64 publication check

The [latest public release, v2.20.2](https://github.com/Polprzewodnikowy/SummerCart64/releases/tag/v2.20.2),
has six assets: four platform deployer packages, the firmware binary,
and `sc64-extra-v2.20.2.zip`. The already downloaded extra archive was
independently inventoried: SHA256
`8d99aa1cb2287d363eaeaa7a911dc47f3c968448db0c8c7d00b1026e1a79f48b`.
It contains 27 members and no NCD, SDF, NCL, PRF, JED or BIT file. Its
`fpga_max_frequency.txt` contains `102.891 MHz`; that scalar is not a
primitive/path timing oracle.

The [current build workflow](https://github.com/Polprzewodnikowy/SummerCart64/blob/a1e7996d2cbece686820a5c785029c68514f17b0/.github/workflows/build.yml),
pinned to `a1e7996d2cbece686820a5c785029c68514f17b0`, uploads only the
extra ZIP and firmware binary from the firmware job, for both CI
artifacts and releases. Separate jobs upload deployer packages and the
website. There is no declared intermediate NCD/SDF artifact. The workflow
uses its own normal licensed build; no secret values were accessed.
`sc64-latest-release.json`, `sc64-build.yml` and
`sc64-extra-inventory.json` preserve the read-only evidence under the
ignored research output. No claim is made about inaccessible historical
CI artifacts, and no broad CI-run scan was performed.

These public files improve the exact-density evidence, while leaving
hard-block pin/mode mapping and minimum-delay transformation unresolved.
The existing timing and bitstream barriers remain unchanged.
