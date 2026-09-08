# Compact decoder integration probe

Research only. `compact.py` composes the passed compact LZW core with its
unchanged cached dictionary, then invokes the existing raw transport behavior,
paired stock-pin mapping, negative liveness and area-mapping gates. No stock
source, production register API, hardware image or cart is changed.

```powershell
docker run --rm -v D:/Documents/GitHub/phosphor-os:/repo sc64-open:diagnostic-lpf /usr/bin/python3 -B /repo/vendor/sc64/tests/gif/stock-lzw-fit/compact.py /repo/build/sc64-compact-lzw/parent/result.json /repo/build/sc64-open-memory/release-conversion/inputs.json "/repo/build/sc64-ui-research/original-final-fight/Final Fight/images/background.gif" /repo/build/sc64-transport-mcu/frozen/gif_transport_mcu_mux.sv /repo/build/sc64-open-timing-options/nextpnr-machxo2 /repo/build/sc64-stock-lzw-compact/agent
```

The compact result must report a passed candidate and both negative gates.
The copied `candidate.sv` hash must match that result's generated hash; the
copied `cached_dictionary.sv` must match its uniquely identified input hash.
Normal module filenames exist only in the fresh output's `core` directory.
The original compact component suite remains the authority for its bounded
counter/stack behavior; this orchestrator does not replace those tests.

The orchestration owns only composition and ordering:

1. [Raw transport behavior](behavior.py): eight original raw images, four
   error/cancel/restart cases using actual DMA/arbiter/SDRAM RTL.
2. [Paired stock integration](run.py): identical stock physical ports, guarded
   memories, actual disconnected-start/status negatives and diagnostic pack.
3. [Area mapping](../../open-toolchain/area-map/README.md): repeat the passed
   default mapping and compare continuation-stage soft-carry options without
   changing the memory forwarding checkpoint.
4. Existing EFB inactive-tie/PLL metadata preparation and actual pack-only
   measurement of the soft-carry variant, with the established diagnostic
   flags and pins-only LPF.

Commands, source hashes, child result hashes and the prepared physical JSON
hash are recorded in the output `result.json`. Each child retains its own
provenance and failure logs. The run fails on any failed child gate and never
continues from missing output. Diagnostic packing does not request placement,
routing, timing qualification or configuration/bitstream serialization.

All [raw-only architecture limitations](README.md) remain: the N64 must still
compose GIF frames and handle palette/transparency/disposal/timing; fixed
research memory ranges are not production-owned; pulse status is not a usable
MCU/N64 job API. Physical resource capacity alone is not a deployable result.

The measured run at `build/sc64-stock-lzw-compact/agent/result.json` passes all
child gates. Eight raw original images and four error/cancellation/restart cases
match exactly. The default stock mapping repeats, both actual disconnected-RTL
negatives fail as required, and all area variants preserve physical RAM shape
and parameters. The compact soft-carry candidate packs to **6,546 TRELLIS_COMB,
3,734 FF, 25 EBR, 24 RAMW and 101 I/O**. This saves 84 packed logic positions
and 31 FF relative to the noncompact soft-carry candidate (6,630/3,765), leaving
318 of 6,864 aggregate logic positions. Placement and routing are untested here.
Default carry mapping remains over capacity at 7,502 TRELLIS_COMB.

Prepared diagnostic netlist:
`build/sc64-stock-lzw-compact/agent/area/soft-carry/physical.json`, SHA256
`83ebf876c086953404991ff1643d88b21fa2c023c0ced9606872f45e07134037`.
It remains subject to all existing primitive configuration and timing barriers;
the output result explicitly keeps `fit_demonstrated` and hardware qualification
false.
