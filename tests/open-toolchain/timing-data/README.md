# Installed exact-device timing schema probes

This research identifies timing records in Diamond 3.13's installed
MachXO2-7000 database. It does **not** import them into nextpnr or qualify
timing. In particular, a supported minimum-delay export disproves the
simple rule that every SDF range is the extrema of the four stored values.
The prior report-tool investigation is in
[timing-research.md](../timing-research.md).

## Reproduce without a licensed compilation

Use a separate container from the official SC64 image
`ghcr.io/polprzewodnikowy/sc64env:v1.10`. Copy these scripts into it and
run Python 3; no additional packages are needed. The installed database
directory is `/usr/local/diamond/3.13/ispfpga/xo2c00a/data`.

Create the two oracle files with the documented `ldbanno` reporter:

```sh
export FOUNDRY=/usr/local/diamond/3.13/ispfpga
export LD_LIBRARY_PATH=$FOUNDRY/bin/lin64
p=/usr/local/diamond/3.13/examples/Board-SWDemo_MachXO2/Demo_MachXO2_Control_SoC/Diamond_project/impl1/control_SoC_demo_impl1
timeout 20 "$FOUNDRY/bin/lin64/ldbanno" -n verilog -neg -sp 6 \
    -o /tmp/grade6.v -d /tmp/grade6.sdf "$p.ncd" "$p.prf"
timeout 20 "$FOUNDRY/bin/lin64/ldbanno" -n verilog -neg -min \
    -o /tmp/min.v -d /tmp/min.sdf "$p.ncd" "$p.prf"
python3 -B test.py
python3 -B probe.py --data "$FOUNDRY/xo2c00a/data" \
    --oracle /tmp/grade6.sdf --minimum-oracle /tmp/min.sdf
```

Both exports exit 0. `-min` and `-sp` are mutually exclusive: combining
them exits 231 with an explicit diagnostic, preserved in the experiment
logs. `-neg` preserves negative setup/hold. No licensing settings are
changed. The output reports hashes, counts and five narrow numerical
cross-checks; it does not reproduce the vendor database. Generated files
and logs remain under ignored `build/sc64-timing-data` in the outer repo.

## Executable results

The synthetic test passes 25 malformed/ambiguous-input rejection checks,
including exact design, timescale, cell and instance scope for both oracles.
The probe rejects any SPD file other than the two exact installed hashes,
any unexpected grade inventory, and any changed recognized-record count.
It is a scanner for an explicitly bounded record subset, not a complete
file parser. Unknown sections are not converted into usable timing.

Both SPD files have eight named grade sections: `M,L,6,5,4,3,2,1`.
Each contains names with big-endian length fields, conditions, and locally
validated records containing four signed big-endian integers. The probe
recognizes 31,112 records per file. It deliberately leaves the four slot
roles and the adjacent numeric port/event identifiers unnamed.

Five positive-edge SLICE facts match the **1200** grade-6 SDF oracle:

| Record | Four stored slots | SDF range, ps |
|---|---|---|
| REG_DEL | 320,355,330,367 | 320:343:367 |
| M_SET | 232,258,202,232 | 202:230:258 |
| M_HLD | -118,-106,-104,-94 | -118:-106:-94 |
| CE_SET | 176,206,185,217 | 176:196:217 |
| CE_HLD | -73,-61,-76,-64 | -76:-68:-61 |

The checks inspect the actual first SLICE's CLK-to-Q and M0/CE setup/hold
statements. Those five selected 7000 records happen to be identical; this
does not establish equivalence of the databases or other cells.

The separate `-min` oracle is a critical counterexample. Its CLK-to-Q is
133:143:154 ps; the `M` section's REG_DEL slots are 131,146,136,151.
Its M setup is 76:88:101 ps, versus stored 75,83,89,99. A scaling or
selection step remains unresolved. Do not infer a multiplier from these
two examples, equate `M` with a complete minimum corner, or populate
production timing from the grade-6 matches alone.
The supplied PRF has no voltage, temperature, derating or process override
line. This rules out an obvious explicit preference override, not an
internal default transformation in the reporter.

The current [MachXO2 data sheet](https://www.latticesemi.com/view_document?document_id=38834)
(FPGA-DS-02056-4.7, July 2026, section 3.19) says logic delays are worst-case
over the operating range and the tools can calculate other temperature/voltage
conditions. This supports checking operating-corner transformations; it does
not specify the SPD slot encoding or resolve the minimum-mode discrepancy.

The exact 7000 grade-6 inventory contains:

| Identifiable family | Recognized records | Scope |
|---|---:|---|
| FIFO8KB conditions | 90 | Clock-to-Q, address/data/CE/CS setup and hold, reset/recovery, pulse widths |
| IDDR_ODDR conditions | 286 | Input/output clock paths, DI/DO setup and hold, clock pulse widths |
| EFB conditions | 69 | Enabled peripheral conditions, interrupts, UFM and serial interfaces |
| EFB Wishbone names | Included separately | Eight address and eight data setup/hold pairs; cycle/reset/strobe/write checks; eight clock-to-data records and one clock-to-ACK |

The EFB condition count excludes its unconditional Wishbone records.
These inventories overlap and are not a count of unique physical arcs.
The stored names include WCLKI2WBDAT0_DEL and WCLKI2WBACK0_DEL; repeat
counts alone cannot assign the individual bit indices. Complete pin,
clock polarity, transition, mode and reset semantics still need an oracle.
Neither the original SoC SDF nor a newly exported alternate `DemoImpl`
SoC SDF contains an EFB, FIFO or ODDR timing instance. The alternate export
passes, but provides no missing hard-block oracle.

`inventory.py` additionally enumerates **all 34** installed example NCDs
and runs a reporter subprocess for each, bounded at 20 seconds, at most
two concurrently. It records the actual reporter's loaded device rather
than trusting the directory name. Run it with `--diamond
/usr/local/diamond/3.13 --output /tmp/new-ncd-inventory` (the output must
not exist). Results: 31 exports exit 0; three ECP3 DDR3 examples exit 99
on their IP license requirement, which is left untouched. All 34 still
report their loaded device:

| Actual loaded part | NCD count |
|---|---:|
| LCMXO2-1200HC | 6 |
| LAMXO2280E | 3 |
| LFE2-35E | 7 |
| LFE3-35EA | 9 |
| LFE5U-25F | 3 |
| LFXP2-17E | 3 |
| LIF-MD6000 | 3 |

There is no loaded 7000 NCD in this installed inventory. Every successful
export has zero occurrences of the explicit EFB Wishbone port or
FIFO/ODDR primitive markers tested by the script. These are textual
coverage indicators, not a formal proof that no transformed model could
hide such a function. All six actual XO2 files are variants of the same
1200 SoC project. The ignored `inventory.json`, `inventory.log` and
`ncd-logs.zip` preserve per-file paths, hashes, status and reporter evidence.

## TLD and other approaches

The TLD wrapper is a ten-byte signature followed by big-endian lengths
and independent zlib streams. The probe validates boundaries, decompressor
completion and a maximum 8192-byte decoded chunk. The 7000 file has eight
chunks totaling 60,120 bytes; the 1200 has four totaling 24,789. Readable
strings include assembly names such as PFU_ASS and EBR_ASS and primitive
names such as SLICE/IOLOGIC. The 7000 contains 27 assembly-name strings,
the 1200 contains 29. This is evidence of device structural data, not an
established timing schema. Decoded vendor contents remain inside the
isolated container and are not checked in.

The installed `ngd2ltm -h` documents NGD/NGO-to-ASCII-LTM extraction for
every speed grade, and `-bin` selects SPD output. The parent tested its
exact EFB NGD: it fails on a missing MACO model and produces no usable
timing export. Help alone is not a conversion pass.

The primary [Trellis timing tree](https://github.com/YosysHQ/prjtrellis/tree/main/timing)
and [Oxide timing tree](https://github.com/gatecat/prjoxide/tree/main/timing)
provide timing fuzzer/tool starting points. This investigation has not
identified a published parser for the installed MachXO2 SPD/TLD format;
it does not claim none exists. Reading exported symbols in the installed
`libbaspd.so` only identified generic binary-read routines, not a supported
timing export interface.

The next useful evidence is a mapped/routed hard-block reference with
identified pin arcs, or a documented export of those same primitive
records. Minimum-corner transformations must also be resolved. Until
then, existing FIFO/EFB/ODDR timing and bitstream barriers remain intact.
No synthesis result, 100 MHz claim, hardware change, or license bypass
is implied by these probes.
