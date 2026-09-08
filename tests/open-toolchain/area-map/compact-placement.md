# Compact LZW placement localization

`placement_probe.py --compact` selects only the compact physical input with
SHA-256 `83ebf876c086953404991ff1643d88b21fa2c023c0ced9606872f45e07134037`.
Without the flag, the probe retains the baseline physical-input hash. Both
paths retain the executable and LPF hash checks before creating output.

The compact run used `sc64-open:diagnostic-lpf` with the exact existing device,
pins-only LPF, 100 MHz request, ODDR/EFB/FIFO diagnostic flags, divisor
`100000`, and 120-second process limit:

```sh
docker run --rm -v "$PWD:/repo" sc64-open:diagnostic-lpf \
  /usr/bin/python3 -B /repo/vendor/sc64/tests/open-toolchain/area-map/placement_probe.py \
  --compact \
  --executable /repo/build/sc64-open-timing-options/nextpnr-machxo2 \
  --physical /repo/build/sc64-stock-lzw-compact/agent/area/soft-carry/physical.json \
  --lpf /repo/build/sc64-open-memory/parent-full/pins-only-diagnostic.lpf \
  --output /repo/build/sc64-area-route/compact-localize
```

The tool exited 125 before the wall-clock limit. It reported the following
strict placement failure:

```text
Unable to find legal placement for cell 'n64_scb.flashram_done_TRELLIS_FF_Q'
of type 'TRELLIS_FF' after 10001 attempts
```

No route completed, no routed netlist was written, and no frequency report was
produced. The run evidence is in
`build/sc64-area-route/compact-localize/{probe.log,result.json}`. This names
the first strict-legalizer failure under the bounded compact search; it does
not establish timing, hard-block, functional, bitstream, or hardware
qualification.
