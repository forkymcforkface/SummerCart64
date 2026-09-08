# GIF dictionary cache budget experiment

This research derives parameterized copies from the hash-checked
[cached decoder](../cached/README.md), without changing it. It keeps the full
4096-byte local phrase stack and varies only dictionary cache index/tag width
and clearing depth. The original GIF is unchanged; Python prepares developer
fixtures, not end-user converted assets. No production build or hardware changes.

```sh
python3 tests/gif/cache-budget/run.py ORIGINAL.gif /out/cache128 --bits 7
python3 tests/gif/cache-budget/run.py ORIGINAL.gif /out/cache256 --bits 8
python3 tests/gif/cache-budget/run.py ORIGINAL.gif /out/cache512 --bits 9
```

Each output directory must be new and outside tests. Python3, Verilator,
g++, make and Yosys with MachXO2 mapping are required. Synthesis is mandatory;
a missing tool, compile/test failure or timeout fails the run. Generated
source, fixtures, logs, tool versions and result/hash manifests stay under
the supplied output directory. The source hashes reject baseline drift.

## Completed comparison

All three variants pass **1772 fixtures**: 1717 original Final Fight images,
131865600 exact indices, 55 synthetic/error vectors, 200 cancellation probes
and four external-memory error/cancel/restart cases. They run the unchanged
baseline driver with identical deterministic input/output and memory stalls.
The original GIF hash is recorded by the inherited fixture manifest.

| Cache entries | Original cycles | Maximum image cycles | External reads | External writes | DP8KC | LUT4 | FF | CCU2D |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 128 | 1510948941 | 953297 | 54814509 | 23928675 | 6 | 640 | 298 | 131 |
| 256 | 1368813574 | 883119 | 36754073 | 23928675 | 6 | 641 | 299 | 131 |
| 512 | 1257856312 | 809783 | 22448934 | 23928675 | 6 | 647 | 300 | 132 |

Recorded tools: Verilator5.032 and Yosys0.52, git
`fee39a3284c90249e1d9684cf6944ffbbcbb8f90`, in private container
`sc64-cache-budget-agent` from `sc64-gif-test:local`. Evidence is ignored under
`build/sc64-cache-budget/{128,256,512}` in the PhosphorOS workspace.
Image ID is
`sha256:a1641a080444774827c555302ce4f4e28e71ad67e3cb0c33b132405e1dbd8a26`.
From the PhosphorOS root, the exact256-entry invocation is:

```powershell
docker run --rm -v "${PWD}:/repo" --entrypoint python3 sc64-gif-test:local /repo/vendor/sc64/tests/gif/cache-budget/run.py "/repo/build/sc64-ui-research/original-final-fight/Final Fight/images/background.gif" /repo/build/sc64-cache-budget/parent256 --bits 8
```

The paired512 cycle and traffic counts exactly reproduce the earlier baseline.
Its647 LUT mapping differs from the historical635; compare this run's paired
variants rather than attributing that difference to a production code regression.
Parameter elaboration and synthesis ordering can alter logic mapping.

## Disposition

**Reject smaller caches for the memory-budget goal.** Every size still maps to
six EBRs; reducing depth does not reduce the two-block cache allocation, and
miss traffic and latency increase. With the unchanged compositor's one EBR,
all three remain above the stock SC64 budget of four free EBRs.

These are component mapping and LZW-only synthetic-memory counts, not placed
fit, timing closure, actual SDRAM service, UI performance or a hardware pass.
An independent local-stack-plus-external-spill experiment is separate from
this completed cache comparison. It must retain the full valid GIF phrase
depth and test long phrases, errors and cancellation before any fit claim.

The parent independently repeats the full256-entry simulation and synthesis
in `build/sc64-cache-budget/parent256`. Its result manifest matches the agent
run exactly, including all correctness gates, cycle counts and mapped cells.
