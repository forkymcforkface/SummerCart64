# Stock pulse-register control sets in strict legalization

This note follows the first named failure from the bounded legal-placement
probe in [placement.md](placement.md). It examines the pinned nextpnr source
and the two packed netlists; it does not change placement legality or claim a
completed placement.

## The register is unpaired and consumes a unique tile-wide reset

Both `build/sc64-area-map/lzw/soft-carry/packed.json` and
`build/sc64-stock-lzw-compact/agent/area/soft-carry/packed.json` contain the
same stock-MCU structure for `mcu_top_inst.mem_write_TRELLIS_FF_Q`:

| Property | Noncompact | Compact |
|---|---:|---:|
| Clock | `clk$glb_clk`, bit 46982 | `clk$glb_clk`, bit 46268 |
| Data port | `M`, from `counter[0]` | `M`, from `counter[0]` |
| Reset port | `LSR`, bit 18937 | `LSR`, bit 18779 |
| `SD` / `CEMUX` | `0` / constant `1` | `0` / constant `1` |
| Reset mode | `LSR_OVER_CE`, active high | `LSR_OVER_CE`, active high |
| GSR | disabled | disabled |

There is no cluster or BEL attribute on the register. In the noncompact pack,
all 3,765 FFs use the same clock, but this is the only FF using its LSR net and
complete control signature. The compact pack also has a one-member signature.
The LSR driver is a multi-LUT expression generated for the default-clear plus
conditional-set behavior in `mcu_top.sv`; it is not the top-level `reset`
alone.

This matters because pinned nextpnr commit
`8dbcee5c3c4415770b6fd06d5ccb2db89545b8ec` treats FF clock and LSR as
tile-wide. `machxo2/arch_place.cc:112-159` requires all FFs in a tile to have
identical clock net, LSR net, clock polarity, LSR polarity and asynchronous
mode. Consequently a tile containing `mem_write` cannot contain any other FF
from this pack, although its COMB sites can still be used subject to the other
slice rules. This is a concrete source of packing pressure, not an indication
that the legality predicate is wrong.

The register also misses the packer's LUT/FF binding path for a separate
reason. `machxo2/pack.cc:216-254` pairs an FF only when its `DI` is driven by a
`TRELLIS_COMB.F`; otherwise it renames `DI` to general-routing port `M`, sets
`SD=0`, and leaves the FF unconstrained. Here the synthesized synchronous-reset
primitive has `counter[0]` as its direct data input, so it becomes such an
unpaired `M`-input FF. The LSR expression's final LUT is not its data driver
and cannot be paired by that rule. `arch_place.cc:91-95` adds a local conflict:
an `M`-input FF cannot occupy an LC whose COMB uses its M mux for a wide mux.

The compact integration reduces the whole pack from 6,630 to 6,546 COMBs and
from 3,765 to 3,734 FFs, but it does not alter this stock register or its
one-member control set. Thus compacting the decoder relieves global pressure
without testing this lead directly.

## The compact failure is the same structural pattern

The compact bounded probe next names
`n64_scb.flashram_done_TRELLIS_FF_Q` after 10,001 attempts. This is a
different stock pulse register, but not a different placement mechanism. In
the compact packed JSON it is also unclustered, has `SD=0`, constant-one CE,
`SRMODE=LSR_OVER_CE`, and takes data through `M`. Its data is bit 0 of the
MCU register-write data bus (named `gif_wdata[0]` after net merging), driven
by `mcu_top_inst.reg_wdata_TRELLIS_FF_Q_15`. Its LSR is a generated LUT net,
`n64_scb.flashram_done_TRELLIS_FF_Q_LSR`, and no other FF has that complete
control signature. The old noncompact pack has the same one-member signature.

The RTL has the same default-clear/conditional-load form. At
`mcu_top.sv:722`, `n64_scb.flashram_done` clears on every clock. The
`REG_FLASHRAM_SCR` write at line 856 conditionally replaces that value with
`reg_wdata[0]`. Yosys therefore maps the pulse to a synchronous-reset FF whose
direct data input is not a LUT, producing the same unique tile-wide LSR and
unpaired M-input restrictions as `mem_write`.

This recurrence strengthens the control-set lead while narrowing its claim.
The compact pack contains nine one-member FF signatures with this particular
combination of an M data port, synchronous LSR and constant CE. They include
both named failures, `n64_scb.rtc_done`, and six other registers. Removing
pressure from only `mem_write` can therefore expose the next member of this
family rather than complete placement. It does not show that any legality rule
is excessive.

That sample is now available in
`build/sc64-area-route/compact-stack/stack.log`. At 45 seconds, the exact
default compact process is in `StrictLegaliser::try_place_cell`, called by
`StrictLegaliser::legalise_cell` and `StrictLegaliser::run`
(`placer_heap.cc:1317`, 1251 and 1113). This rules out solve or spread as the
sampled stall phase and makes the currently named compact register the first
remap target. One sample does not establish which compatibility check rejects
each attempted BEL.

## Legal, equivalent next experiment

Test a derived mapping in which only the synchronous reset on
`n64_scb.flashram_done` is unmapped into its D logic before MachXO2 FF
technology mapping. Yosys 0.68 in
`sc64-open:diagnostic-lpf` documents `dffunmap -srst-only` as emulating a
synchronous reset with an input multiplexer while retaining the base FF.
Select only the RTLIL cell driving `n64_scb.flashram_done` and apply that pass
before MachXO2 FF technology mapping. Do not substitute a hand-rewritten RTL
expression without separately proving its priority and reset behavior. The
selected remap should produce a plain DFF driven by a LUT, allowing the
existing packer to set `SD=1`, bind the LUT and FF in one LC, and remove the
unique LSR from that FF. This is a mapping experiment; do not weaken or bypass
`slices_compatible`.

Run it as a fresh derivative of the exact compact input first, with a
sequential-equivalence gate against the original stock MCU over reset and all
command inputs. Then pack with the same pinned executable, device, LPF,
100 MHz request and diagnostic flags. The experiment succeeds only if:

1. equivalence passes;
2. `flashram_done_TRELLIS_FF_Q` has `DI`, `SD=1`, no LSR net, and shares a
   cluster with its driving COMB in packed JSON;
3. total COMB use does not increase unexpectedly; and
4. the unchanged bounded legal-placement probe advances past this failure or
   completes placement.

Applying `dffunmap -srst-only` indiscriminately to all synchronous-reset FFs is
not the controlled first test: at 96.6% COMB utilization it can exchange many
control-set restrictions for enough new mux LUTs to make the design larger.
Targeting one proven member isolates how much pressure this reset/data mapping
creates. If that succeeds, expand the experiment to the nine
counted one-member signatures as a separately measured step rather than
assuming one register represents the whole placement failure.

## Limits

The low placement cap reports the first cell whose search exceeds 10,000
attempts, not a proof that this cell makes the design impossible. A successful
remap would show that this control set impeded the heuristic. A later named
cell or another timeout would identify the next constraint; it would not
justify relaxed legality. Neither packed JSON contains candidate-BEL attempt
history, so no exact count of legal sites is claimed here.

Source inspected inside `sc64-open:diagnostic-lpf`:

- nextpnr commit `8dbcee5c3c4415770b6fd06d5ccb2db89545b8ec`;
- `/src/nextpnr/machxo2/pack.cc`;
- `/src/nextpnr/machxo2/arch_place.cc`;
- `/src/nextpnr/machxo2/arch.cc`; and
- `/opt/oss-cad-suite/share/yosys/lattice/cells_map_trellis.v`.
