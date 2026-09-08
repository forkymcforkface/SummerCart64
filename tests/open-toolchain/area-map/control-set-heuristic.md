# MachXO2 HeAP control-set heuristic

This is a source-level feasibility note for the pinned nextpnr commit
`8dbcee5c3c4415770b6fd06d5ccb2db89545b8ec` in
`sc64-oddr-agent`. It proposes only a legalisation-search hint. It does not
change `slices_compatible`, packing, routing, timing, configuration, or the
meaning of a successful placement.

## Existing HeAP support

`common/place/placer_heap.h` already has the required optional interface:

- `ff_bel_bucket` selects the FF BEL bucket.
- `ff_control_set_groups` maps FF BEL z positions to a shared-control group.
- `get_cell_control_set(Context *, const CellInfo *)` returns an `int32_t`
  identity, or `-1` to opt a cell out.
- `ctrl_set_max_radius` bounds the nearby compatible-group search at each
  legalisation iteration.

HeAP keeps one identity per configured group and first tries nearby occupied
groups with the same identity. It still calls the architecture's normal
`isBelLocationValid` check before accepting a candidate. Thus the hook may
reduce failed random legalisation attempts; it cannot relax a MachXO2 rule or
turn an invalid placement into a valid one. `placerHeap/noCtrlSet` already
disables this optional path.

The pinned ECP5, Nexus and iCE40 `Arch::place` methods instantiate
`PlacerHeapCfg` but do not configure these fields. They provide no family
implementation to copy. The in-tree Xilinx Himbaechel implementation is the
working example: it assigns an FF bucket, groups FF z positions by the
hardware control-set scope, and returns a pre-indexed control-set identity.

## MachXO2 control-set boundary

MachXO2 uses eight `TRELLIS_FF` BELs per logic tile: z positions
`(i << Arch::lc_idx_shift) | Arch::BEL_FF`, for `i` from 0 through 7.
`machxo2/arch_place.cc::slices_compatible` requires every FF in that tile to
share `ffInfo.clk_sig`, `ffInfo.lsr_sig`, `FF_CLKINV`, `FF_LSRINV`, and
`FF_ASYNC`. It separately checks per-two-LC slice properties: GSR enable,
CE constant/inversion and CE net, plus LUT/RAM/M-input restrictions. The
existing validity function must remain the authority for both levels.

Accordingly, the one HeAP group should cover all eight FF z positions and its
identity should contain exactly the five tile-wide comparison fields. Do not
put CE or GSR into this identity: they are slice-local and the generic HeAP
API represents only one shared grouping level. Do not use a truncated hash;
the API requires equal return values only for the same identity. Allocate a
stable dense `int32_t` ID from the full tuple instead.

The safe shape in `machxo2/arch.cc::Arch::place`, after the existing FF
cell-group setup, is conceptually:

```c++
cfg.ff_bel_bucket = id_TRELLIS_FF;
cfg.ff_control_set_groups.resize(1);
for (int i = 0; i < 8; ++i)
    cfg.ff_control_set_groups[0].push_back((i << Arch::lc_idx_shift) | Arch::BEL_FF);
cfg.ctrl_set_max_radius = {18, 15, 12, 9, 6, 3};
cfg.get_cell_control_set = [&](Context *, const CellInfo *ci) -> int32_t {
    if (ci->type != id_TRELLIS_FF)
        return -1;
    return ids.at(std::make_tuple(ci->ffInfo.clk_sig.index, ci->ffInfo.lsr_sig.index,
                                  ci->ffInfo.flags & (ArchCellInfo::FF_CLKINV |
                                                      ArchCellInfo::FF_LSRINV |
                                                      ArchCellInfo::FF_ASYNC)));
};
```

Here `ids` is a complete precomputed map from the tuple to dense IDs before
calling `placer_heap`; the call is synchronous, so a local map captured by
reference lives for every callback. A small owning helper captured by value is
equally valid. `assignArchInfo()` already fills the `ffInfo` fields during
packing, so the callback must be installed only in the post-pack placement
path. A callback that reads raw ports or parameters risks differing from the
actual legality predicate.

This is deliberately a placement preference. A unique-LSR pulse FF such as
`flashram_done` has no peer with its identity, so no compatible occupied tile
will be preferred for that FF. The possible benefit is indirect: placing the
large common control-set population together leaves whole tiles available for
rare sets, reducing futile candidates. It may also make no improvement or
worsen a near-capacity search; neither outcome changes the selected-reset
mapping experiment or proves a legality defect.

## Required experiment if implemented

Keep the compact netlist, device, LPF, diagnostic flags, random seed,
legalisation cap and 100 MHz request unchanged. Compare baseline with this
heuristic and with `placerHeap/noCtrlSet` explicitly enabled. Record the first
named failure, attempts, placement completion, routed netlist and routing
result. Check every completed placement with the existing architecture
legality checks and retain the normal configuration/timing rejection gates.
Only a repeated improvement under those identical conditions justifies an
upstream candidate; it is not a firmware fix or a hardware qualification.
