# Reference unknown-bit coverage audit

Read-only audit of the official v2.20.2 FPGA reference, using pinned Trellis
`3afe7b52b30f4b4417ee98f03016767a502006e3` in `sc64-open:7000`.
Its database revision is
[`015e0330630d7c238c0e4f2cdd9c8157eb78c54a`](https://github.com/YosysHQ/prjtrellis-db/tree/015e0330630d7c238c0e4f2cdd9c8157eb78c54a).
The reference decoded configuration SHA-256 is
`ccd8afe3cad9cb4df5acb963d9b17e8336c9bb6f54dc2440c136a96e4a9bca69`;
its provenance and exact serialization are in [release/README.md](release/README.md).
No database, backend, bitstream or hardware changes occur.

## Unknown means uncovered, not necessarily undefined

[`TileBitDatabase::tile_cram_to_config`](https://github.com/YosysHQ/prjtrellis/blob/3afe7b52b30f4b4417ee98f03016767a502006e3/libtrellis/src/BitDatabase.cpp)
collects coverage from the selected matching muxes, words and enums. It then
emits `unknown:` for each **set** tile bit outside that coverage. Consequently,
a bit can have a database definition yet remain unknown because its complete
enum/mux pattern did not match. Unset unmapped bits are not inventoried.

The reference has **433 records at 433 distinct physical bit coordinates**:
**121 occur in existing definitions for their exact tile type; 312 do not**.
This checks token references, not whether an unmatched field's intended value
has been proved.

| Tile type | Existing definition, uncovered | No same-tile definition |
| --- | ---: | ---: |
| EBR1 | 68 | 52 |
| PIC_B0 | 16 | 0 |
| PIC_L2 | 8 | 0 |
| PIC_L2_VREF4 | 2 | 0 |
| PIC_R1 | 16 | 0 |
| PIC_T0 | 11 | 0 |
| CIB_EBR0 | 0 | 72 |
| CIB_EBR1 | 0 | 60 |
| CIB_EBR2 | 0 | 51 |
| CIB_EBR_DUMMY | 0 | 18 |
| CIB_EBR0_END2_DLL3 | 0 | 2 |
| CIB_PIC_B0 | 0 | 27 |
| CIB_PIC_B_DUMMY | 0 | 27 |
| LLC2 | 0 | 2 |
| CIB_CFG3 | 0 | 1 |

## Concrete EBR mode-pattern issue to investigate

All 68 referenced EBR1 records belong to existing `EBR.MODE` definitions in
`database/MachXO2/tiledata/EBR1/bits.db`. The patterns are:

```text
DP8KC   F0B13 F1B8 F1B20 F1B21 F1B22 F1B35
FIFO8KB F0B13 F1B0 F1B8 F1B20 F1B21 F1B22 F1B35
PDPW8KC F0B13 F1B8 F1B20 F1B21 F1B22 F1B35
```

Every reference tile contributing those 68 records has **F1B35 unset**.
Thus existing mode patterns cannot match there, leaving their other set bits
uncovered. This is a specific decoder/database mismatch candidate; it does not
justify setting F1B35 or deleting it from the database.

The checked-in [041-ebr_config fuzzer](https://github.com/YosysHQ/prjtrellis/blob/3afe7b52b30f4b4417ee98f03016767a502006e3/fuzzers/machxo2/041-ebr_config/fuzzer.py)
targets **LCMXO2-1200HC**, including EBR1 at R6C18, not a 7000 site sweep.
The neighboring MachXO3 EBR1 database repeats F1B35 in these mode patterns;
MachXO3D instead uses F1B34. That disagreement is evidence against assuming
bit positions transfer between variants, not a replacement encoding.

The remaining 52 EBR1 records are exactly F1B32, F1B33, F1B34 and F1B36,
each appearing 13 times. The five-bit field F1B32..F1B36 has values that
increase with reference EBR site position (for example R13C2=3, R13C5=4,
R13C8=5; R20C2=16, R20C5=17). This is a site-correlated observation only;
its function is **not attributed** to address, initialization, or enable
semantics. Controlled exact-7000 site comparisons are the appropriate next
check before any database patch.

## PIO and configuration boundaries

All 53 referenced PIO records occur in `PIO[A-D].BASE_TYPE` definitions,
not EFB fields. For example PIC_B0 F4B38 appears in PIOA input/bidirectional
LVCMOS/LVTTL patterns; F5B38 is its PIOB counterpart. These are partial
pattern overlaps, not proof of the complete intended port mode. Missing
same-tile definitions for CIB records likewise do not establish their
function merely from neighboring tile names.

The nearby CIB_CFG3 record remains **CIB_R1C7 F3B0**, without a same-tile
definition or proven EFB attribution. No new feature-row, PLL, clock or EFB
field identification emerges from this pass. Configuration-port enums,
runtime CFGCR controls and separately programmed feature bytes must remain
distinct, as documented in
[EFB configuration research](efb/inactive/configuration-research.md).

## Evidence and limits

The ignored `build/sc64-unknown-bits-audit/` directory contains
`inventory.py`, `inventory.log` and `inventory.json`. The JSON preserves
every reference tile/bit, its physical coordinate and all exact same-tile
database token matches, plus the observed EBR fields. The script reads the
existing decoded reference and installed database; it performs no encoding.

The next useful experiments are controlled 7000 EBR site/mode comparisons
and PIO base-type comparisons. None of the 433 records should be copied into
a newly routed design on the strength of this audit. Reference replay remains
distinct from source-generated configuration and full-chip qualification.
