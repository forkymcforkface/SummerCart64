# Public 7000 idle-EBR comparison

This read-only follow-up to the [unknown-bit audit](../unknown-bits-audit.md)
finds that the EBR1 field at F1B32..F1B36 is **zero at every site** in a
public 7000HE programming artifact, whereas the SC64 reference contains
the site sequence 3..28. It is therefore not an unconditional,
always-populated field across these 7000 artifacts. Its function remains
unidentified; no database patch is justified by this comparison.
See the [timing research README](README.md) and
[public oracle provenance](public-oracles.md) for the broader boundaries.

## Inputs and association limits

The public file is `impl1/FPGASDR_impl1.jed` from
[alberto-grl/1bitSDR, commit 3e2e01d](https://github.com/alberto-grl/1bitSDR/blob/3e2e01da0357b38a9badff832c65a185b2fdcaf0/impl1/FPGASDR_impl1.jed).
It is 1,453,943 bytes with SHA256
`151180c052bb43abd2b1a12dacdb9a5e0a6c5f4eb7b5d70fc6e2f27b7f817248`.
Its header names `FPGASDR_impl1.ncd`, `LCMXO2-7000HE-4TQFP144`, and
Diamond 3.11.2.446. The same commit includes that named NCD and a PAR
report. The NCD independently loads as 7000HE in the current reporter;
the PAR utilization lists PIO, SLICE and OSC, with no EBR, consistent with
the exported netlist/SDF lacking EBR instances.

This is a correlated artifact group, **not proved same-build identity**.
Matching names, device and dates do not prove that the checked-in NCD
generated the checked-in JED. A normal `bitgen` invocation on that NCD
exits 99 for unavailable `LSC_BASE`; it produces no comparison bitstream.
The license is not changed and the operation is not retried by another
route. Consequently this is not an active-EBR mapped-site/mode oracle.

The reference comparison uses the previously verified SC64
[release bitstream](../release/README.md). It is 7000HC, while the public
artifact is 7000HE, and their vendor tool versions differ. The site-field
observation is factual across those inputs; family/package/tool effects
are not eliminated.

## Conversion and physical-bit inspection

The normal file-only Diamond Deployment Tool operation succeeds:

```sh
ddtcmd -oft -bit -dev LCMXO2-7000HE \
    -if public-sdr.jed -of public-sdr-converted.bit
ecpunpack public-sdr-converted.bit public-sdr.config
```

Both exit 0. The deployment tool runs in the existing isolated official
SC64 container with its real distro `libusb` dependency. The Trellis
decoder uses the pinned tool/database from the unknown-bit audit.
The converted BIT is 75,589 bytes, SHA256
`323022b4322e288bcbec2bfd658e90a3435bc4d45d934d6e63e40beb7bd69f66`;
the decoded configuration is 1,362,951 bytes, SHA256
`cb9ef00b67494b16c686f8371c07424eaa232fcf4d1a18b6ebfe77f11b9839fc`.

The comparison reads each decoded chip's physical tile CRAM, rather than
inferring unset bits from missing text records:

```python
chip = pytrellis.Bitstream.read_bit(bit_path).deserialise_chip()
for name, tile in chip.tiles.items():
    if tile.info.type == "EBR1":
        value = sum(int(tile.cram.bit(1, 32 + i)) << i for i in range(5))
        print(name, value)
```

| Sites | SC64 field values | Public SDR field values |
|---|---|---|
| R13C2, C5, C8, C11, C14, C17, C22, C25, C28, C31, C34, C37, C40 | 3 through 15 | All 0 |
| R20 at those same columns | 16 through 28 | All 0 |

All 26 site comparisons differ. `sites.json` also preserves each input's
bits referenced by the existing EBR.MODE patterns, including F1B35;
this experiment does not change, reinterpret or qualify those patterns.
F1B32..F1B36 remains distinct from the already defined EBR.WID field at
F1B23..F1B31.

The parent independently repeats the CRAM comparison in a fresh
`sc64-open:7000` container using `PYTHONPATH=/usr/local/lib/trellis` and
`/usr/bin/python3`. `parent-sites.json` equals the agent's complete JSON;
an explicit check verifies all 26 public values are zero and reference
values are nonzero. This repeats the observation without strengthening
the artifact-association or device-variant assumptions above.

## Other artifact and retained evidence

The mapped CPU example in
[tocache/STEP-Lattice-MachXO2-FPGA](https://github.com/tocache/STEP-Lattice-MachXO2-FPGA/tree/9e0f3b5fba6f8258c72c1376feb8ae8ee99c86a5/lm8_tutor)
exports successfully, but the actual loaded device is **LCMXO2-4000HC**.
Its NCL and elaborated wrappers confirm six DP8KC instances, including nonzero
initialization; the [mapped-site check](../ebr-evidence/README.md) records the
count. It is classified
as a different-density lead only; no 4000 configuration comparison or
7000 mode inference is performed.

All downloaded artifacts, converter/report logs, `sites.py`, per-site
JSON, and the file hash manifest remain in ignored
`build/sc64-public-ebr-audit`. No generated artifact is committed beside
this report. The work changes no production source, database, firmware,
license, hardware or persistent cart state.
