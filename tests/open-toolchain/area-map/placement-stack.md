# Compact placement stack sample

`placement_stack.py` runs the exact pinned executable and compact physical
input from [the alternative placer comparison](alternative-placement.md),
using the default analytical placer. Device, pins, three diagnostic flags and
100 MHz request stay unchanged. GDB interrupts the inferior after 45 seconds
of wall time, prints all thread stacks and kills the inferior. A 90-second
outer limit also terminates the debugger process group on failure.

Run in `sc64-open:diagnostic-lpf` with GDB installed:

```sh
python3 -B placement_stack.py \
  --executable /repo/build/sc64-open-timing-options/nextpnr-machxo2 \
  --physical /repo/build/sc64-stock-lzw-compact/agent/area/soft-carry/physical.json \
  --lpf /repo/build/sc64-open-memory/parent-full/pins-only-diagnostic.lpf \
  --output /repo/build/sc64-area-route/FRESH_STACK
```

The successful collection is `build/sc64-area-route/compact-stack/`, using
GDB 15.1. Its status is `sampled`, never a successful route. The original
executable already includes debugging symbols; no tool rebuild, new legality
rule or modified design is involved. Input hashes and the complete command
are recorded. The script requires an actual SIGINT stop and stack frames;
missing debugger, failed launch or early process exit cannot pass collection.

The sampled main thread is in:

```text
Arch::checkBelAvail
HeAPPlacer::StrictLegaliser::try_place_cell
HeAPPlacer::StrictLegaliser::legalise_cell
HeAPPlacer::StrictLegaliser::run
HeAPPlacer::legalise_placement_strict
HeAPPlacer::place
```

This directly localizes this instant of the default compact attempt to strict
legalization. It is consistent with the [lower-cap failure](compact-placement.md),
but does not establish that the same cell occupies the whole timeout, identify
its name, count legal sites or prove impossibility. Sampling under a debugger
is not a speed comparison. No route, timing qualification, bitstream or cart
test results from this diagnostic.
