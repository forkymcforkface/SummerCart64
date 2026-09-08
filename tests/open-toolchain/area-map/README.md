# Logic mapping area probe

This repeats the passed guarded mapping script with logic-mapping options
changed only at `map_ffram:`. It preserves the existing forwarding checkpoint,
memory shape/parameter checks and source conversion. The default repeat must
match every original cell count. This is an area probe, not formal equivalence
or hardware qualification of a different synthesis mapping.

```powershell
docker run --rm -v "${PWD}:/repo" sc64-open:diagnostic-lpf /usr/bin/python3 -B /repo/vendor/sc64/tests/open-toolchain/area-map/run.py /repo/build/sc64-stock-fit/parent/candidate-map /repo/build/sc64-open-release/source/fw/project/lcmxo2 /repo/build/sc64-area-map/repeat
```

The supplied baseline is produced by [stock-fit](../../gif/stock-fit/README.md).
The output directory must be new. Yosys scripts, mapping logs, netlists, hashes
and result counts remain there. No placement, routing or bitstream is produced.

The installed Yosys `help synth_lattice` is the option authority. `-noccu2`
maps arithmetic into soft logic. The `-cmp2softlogic` comparison is only a
continuation-stage probe: it does not rerun coarse optimization before the
guarded checkpoint, so no general claim about that option follows from a
no-change result.

For the complete compositor skeleton, default mapping reproduces 6,588 LUT4,
805 carry cells and 4,288 FF. Soft carry uses 7,290 LUT4, zero carry cells and
4,270 FF. Both retain 22 DP8KC plus four FIFO8KB and 24 distributed RAMs.
MachXO2 prepack accounting falls from 8,342 to 7,434 logic units, still above
6,864. The comparator continuation changes neither result. These are prepack
counts; they must not be substituted for actual packed counts or timing.

Independent review strengthens the final memory shape/parameter comparison and
adds direct converted-source and Yosys executable hashes. These checks do not
prove final memory wiring equivalence. The final repeats are
`build/sc64-area-map/review-composed` and `review-lzw`; earlier `parent` and
`lzw` results remain as evidence of the same counts.

The LZW-only default maps to 7,202 prepack units; soft carry reduces that to
6,575 (6,431 LUT4 plus 24 distributed RAMs, zero carry cells). Actual packing
with the existing EFB/PLL preparation, pins-only LPF and ODDR/EFB/FIFO diagnostic
flags produces **6,630 COMB, 3,765 FF, 25 EBR, 24 RAMW and 101 I/O cells**.
This is below the logic limit of 6,864, leaving 234 positions and one EBR.
The final mapping's netlist is byte-identical to the earlier packed input.
Packing evidence is in `build/sc64-area-map/lzw/soft-carry/pack.log` and
`packed.json`. Physical placement, timing and all hard-block qualification
requirements remain separate; no cart-ready implementation follows from area.

This smaller integration requires N64-side composition, safe raw-plane
publication and job ownership that this probe does not implement. Its area
savings cannot inherit the composed pipeline's sparse-transfer performance.
