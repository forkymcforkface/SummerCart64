# Experimental original-GIF LZW core

This directory is research, excluded from every production FPGA source list.
It consumes original GIF image LZW payload, not a GIF64 file. It is **not yet a
complete GIF parser/compositor or an integrated SC64 accelerator**.

Run from any directory with Python 3, Verilator, g++ and make installed:

```sh
/path/to/sc64/tests/gif/run.sh /path/to/original/background.gif /path/to/build/gif-test
```

Yosys 0.52 is optional and supplies generic statistics plus MachXO2 primitive
mapping through `synth_lattice -family xo2`. The input GIF
is read without modification. Generated binary vectors, manifests, object files
and logs go under the explicit build directory. The Python code generates test
vectors; it is not a proposed end-user conversion requirement. No theme assets
or generated GIF64 files are distributed with this test.

The independent bounded reference parses GIF image sub-blocks and decodes LZW.
Synthetic cases exercise minimum code sizes 2–8, dictionary-width boundaries,
full-table deferred clear, malformed references, output bounds, early end,
truncation and invalid minimum sizes. The RTL harness adds deterministic input
and output stalls, exact output comparison, completion checks, a finite cycle
watchdog and 200 cancellation checks. It counts cycles separately for the
original images and writes source SHA256 and frame metadata to `manifest.json`.

The original Final Fight background from OS4-Themes commit
`2e1576bc44ec0268579028f32c42fc7b9aedc829` has SHA256
`d48de154f477e6753b14d5d1a1fa7c5edcefe17c3688e9afbe790907bc7056b7`.
The isolated development suite passed all 1,717 images (131,865,600 decoded
indices), 55 synthetic/error cases and 200 cancellations under Verilator
5.032. With deterministic stalls the original loop consumed 485,920,630
simulated cycles, maximum 294,186 cycles per image. These are LZW-only simulator
counts, **not board performance**; composition, PI traffic, SDRAM contention and
protocol costs are absent. Re-run this self-contained suite to verify any edit.

The self-contained suite passes with a synchronous stack output. Yosys 0.52
maps the core to 14 DP8KC memory primitives, 509 LUT4, 211 TRELLIS_FF and 127
CCU2D. These are component counts, not a full SC64 fit or place-and-route report.

The prototype requests 14 KiB of dedicated logical dictionary/stack memory.
Together with existing SC64 logical RAM this exceeds total EBR capacity; it
must not be added to the production image as written. Yosys technology mapping
is not MachXO2 placement or timing closure. Reusing an exclusively
leased general buffer and external state are research
options requiring actual integrated resource/timing results. No firmware flash
or hardware-safety claim follows from these tests.

Final Fight uses a global palette and full-canvas transparent images. This
core only decodes indices; interlace addressing, local-palette composition,
disposal, presentation timing, cancellation ownership and N64 output transport
belong to additional stages. A future implementation must preserve those
semantics rather than treating the successful LZW test as complete GIF support.

`cache_probe.cpp` is a separate host-only sensitivity model for an external
prefix/suffix dictionary with a direct-mapped cache. Build with a C++17 compiler
and pass the generated `fixtures.bin` path. It counts actual dictionary reads
and write-allocation policy; it does not implement hardware or estimate cycles.
On the same original Final Fight loop it records 106,643,169 prefix reads and
23,928,675 dictionary writes. A 512-entry write-allocate cache hits 78.95%; a
1,024-entry cache hits 89.64%. These are cache-model results, not a proven FPGA
speedup or resource fit. A possible future layout combines external dictionary
storage, a small on-chip cache and an exclusively leased general-buffer stack.

`repeated_payload.py ORIGINAL.gif OUTPUT.json` checks exact consecutive payload
and metadata equality against Pillow-composed RGBA pixels. It admits reuse only
for disposal 0/1 and records frame indices, not generated animation assets.
Final Fight passes all 1,717 images with **407 identical retained frames**;
maximum compressed image payload is 25,747 bytes. Runtime source reading,
exact comparison, storage, frame identity and presentation timing still have
costs and ownership requirements. This is an unimplemented optimization
candidate, not an accepted decoder speedup. Outputs stay outside this source
directory; Python/Pillow are developer-test dependencies only.
