# Exact old-data RAM forwarding experiment

This diagnostic netlist transform repairs the four SC64 memories that Yosys
otherwise expands into flip-flops: DD RAM, both EEPROM byte arrays, and the MCU
memory buffer. It changes no production RTL, build list, firmware, or hardware.
The source remains the original SC64 source manifest, converted by the opt-in
sv2v frontend in [the existing probe](../probe.py).

## Why the memories do not infer

Each affected memory has two synchronous old-data read ports and two ordered
write ports. Port B wins simultaneous same-address writes. MCU read outputs
also hold when their individual read enables are false. Yosys's XO2
`lattice/brams_8kc.txt` describes same-port `READBEFOREWRITE`, but cannot provide
the original cross-port old-data read directly. A 512x16 reproducer maps to
flip-flops with exact semantics and two DP8KC with `-no-rw-check`.
**Disabling read/write checks is not the proposed repair:** it weakens behavior
that the source defines.

[Lattice's MachXO2 Memory Usage Guide](https://www.latticesemi.com/view_document?document_id=39082),
Appendix A.5, describes the unknown read result possible on same-address
cross-port read/write access. The experiment avoids that physical collision:

1. Suppress port A's write when port B writes the same address.
2. Disable the losing physical port's clock enable on a write collision.
3. Keep the winning physical port enabled, including when its original logical
   read enable is false, and obtain its defined same-port old-data result.
4. Forward that old-data result to the losing logical reader. Register the
   selection at the original read edge; do not add a cycle of read latency.
5. Preserve each original logical read enable with an output hold path.

The raw memory marks cross-port collision data unspecified only after adding
these guards. Both readers may remain active for same-address read-only access.
Physical DP8KC CE connections and `READBEFOREWRITE` parameters are checked after
memory mapping, before LUT synthesis obscures the logic.

`forward.py` accepts only the matched two-port, shared positive-edge clock,
full-word write, zero-offset power-of-two memory shape. It requires port B
priority, no read resets, unknown initial read outputs, and no wide ports.
Before rewriting any write address, `address_proof.py` extracts the original
combinational cones and runs SAT with undefined-value tracking to prove that
each enabled write address equals its corresponding read address. Unsupported
logic in a cone becomes an unconstrained input, making the proof conservative.
A failed implication stops the transform. Memory contents/initialization remain
in the original memory cell.

## Reproduce

Use the pinned diagnostic image from the parent toolchain README, with this
SC64 checkout at `/sc64` and a fresh ignored output directory at `/out`:

```sh
/usr/bin/python3 /sc64/tests/open-toolchain/memory/run.py /out/memory-focused

# First use ../probe.py --frontend sv2v with the actual project/primitive
# manifest. Feed that probe's converted.v to this separate experiment.
/usr/bin/python3 /sc64/tests/open-toolchain/memory/full.py \
    /out/source-probe/converted.v /sc64/fw/project/lcmxo2 /out/memory-full
```

`run.py` proves a 4x3-bit generic memory including both write collisions and
independent read enables. A stronger copy replaces losing raw read data with
independent `$anyseq` values. Both prove all 18 output/state equivalence points.
A deliberately removed forwarding path fails three output points; a deliberately
wrong enabled write address also fails. A separate 512x16 fixture must map to
exactly two DP8KC and pass physical CE/mode assertions. The tiny proof fixture
itself can remain a logical memory because block RAM is not economical for it.

`full.py` hashes the supplied conversion, proves all eight original address
implications, applies only the four named SC64 transformations, checks all six
new DP8KC physical CE/mode pairs, completes synthesis, and runs `check -assert`.
It writes `result.json` on success or failure. Preserve the source probe's
manifest alongside these results: a hash of converted Verilog alone does not
establish source provenance. These experiments do not emit a bitstream.

## Recorded results

Yosys 0.68+195 (`435977e97-dirty`), sv2v v0.0.13, exact official SC64 v2.20.2
source commit `18041e25472075a166292d1195603bcefe9c9688`, with its built CIC image.
Conversion SHA-256:
`f155a8c75b8b02fb908a5c274efe0ea3e5e2c309ba8bf9a0408d1a4aae73a82d`.

| Mapping | LUT4 | TRELLIS_FF | DP8KC | FIFO8KB | CCU2D |
|---|---:|---:|---:|---:|---:|
| Original native-Yosys inference | 91,014 | 35,845 | 12 | 4 | 402 |
| Guarded forwarding, final checkpointed runner | 4,531 | 3,023 | 18 | 4 | 402 |

Both full syntheses pass connectivity checking. The final runner's intermediate
RAM checkpoint changes ABC's mapping relative to an earlier single-pass
experiment (4,442 LUT4); use the reproducible checkpointed result above.
Generated evidence is under the workspace's ignored
`build/sc64-open-memory/`: `guarded-focused-final`, `release-conversion` (source
hash manifest), and `release-ce-final` (full results and mapped RAM).

This removes the known register expansion, but does **not** prove placed fit,
100 MHz timing closure, bitstream correctness, or real-cart safety. Generic
memory equivalence plus original address implications is not a whole-design
post-LUT equivalence proof. Device timing, initialization packing, all other
primitive/constraint toolchain gaps, and hardware qualification still apply.
The physical baseline uses 18 RAM plus four FIFO blocks, leaving only four of
26 EBRs; adding the experimental seven-EBR cached GIF decoder/compositor still
requires a separate memory-sharing or resource-reduction design.

## Independent vendor-model comparison

`physical.py` exports the focused runner's mapped 512x16 fixture and compares it
against the original source using a caller-supplied installed Lattice DP8KC
simulation model. It initializes every address, then checks 6,000 cycles across
all read/write collision modes. The parent run passes; model SHA-256 is
`97d08937610d1ca8c4701e4090f5f81a27578a335825db2c1b688e9b9d9dee45`.
Evidence: `build/sc64-open-memory/parent-physical/`. The model is not distributed
with this repository. Logical read-enable holds remain covered by the separate
generic formal fixture; this physical fixture has both logical reads enabled.

```sh
python3 -B tests/open-toolchain/memory/physical.py /out/memory-focused \
    /installed/diamond/cae_library/simulation/verilog/machxo2/DP8KC.v \
    /out/memory-physical
```

This is a functional model comparison, not a timing simulation or cart test.

## Parent physical diagnostic

The parent independently repeats both runners in the combined diagnostic image
at `build/sc64-open-memory/parent-focused` and `parent-full`, obtaining the same
counts and checks. After preserving the original PLL analog metadata with
`../oddr/preserve_pll_metadata.py`, nextpnr rejects the unchanged release LPF at
`IOBUF ALLPORTS`. This remains a failed original-constraint build.

A separate diagnostic LPF containing only original `LOCATE COMP` and `IOBUF
PORT` statements retains all original package pin assignments and explicit
per-port electrical statements. With the existing EFB/ODDR/FIFO routing opt-ins,
the full design completes placement. Total physical LUT use, including carries
and distributed RAM, is 5,383/6,864 (78%). The pre-route estimate is 57.32 MHz,
failing the requested 100 MHz; missing hard-cell timing and omitted constraints
prevent treating this as a qualified frequency.

Routing fails on `$PACKER_GND_NET` arc 5. A same-run pre-route user inventory
identifies `vendor_inst.efb_lattice_generated_inst.EFBInst_0.I2C1SDAI` as that
endpoint. No connection is removed and no FPGA configuration is emitted.
Evidence: `parent-full/{route,pins-route,place,ground-route}.log`,
`physical.json`, `pll-metadata.json`, and `pins-only-diagnostic.lpf`.
This test establishes a concrete next routing defect, not successful routing
or satisfaction of the original SDRAM and configuration constraints.
