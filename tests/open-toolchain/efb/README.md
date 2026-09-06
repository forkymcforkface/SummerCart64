# EFB routing diagnostic

This patch exposes the existing MachXO2 hard EFB BEL/interconnect to a routing
diagnostic. It does **not** implement EFB/UFM configuration or timing. Normal
builds reject EFB; the explicit diagnostic flag still rejects every request to
generate a configuration file. No artifact from this probe is cart firmware.

Apply to the pinned nextpnr checkout from the parent Docker image:

```sh
python3 apply.py /src/nextpnr
cmake --build /src/nextpnr/build -j2
python3 verify.py /sc64 /src/nextpnr/build/nextpnr-machxo2 /out/efb
```

Use `/usr/bin/python3`, not the suite's `tabbypy3` environment. Output must be a
new directory. `apply.py` validates every source anchor before any write.

`declaration.py` derives an interface-only EFB declaration from the existing
SC64 wrapper's explicit parameters and ports. Verification independently checks
all **109 port directions** against the Trellis routing graph for
`LCMXO2-7000HC`. No proprietary simulation model is copied or distributed.

## Measured results

On `LCMXO2-7000HC-6TG144C`:

- Minimal Wishbone input/acknowledgement routing passes at the physical
  `X3/Y1/EFB` BEL with `--efb-routing-diagnostic` and a routed JSON output.
- Normal use fails with the explicit unqualified-configuration/timing error.
- A diagnostic request for `--textcfg` fails before producing the output file.
- The original SC64 generated EFB wrapper synthesizes with its real parameter
  values. Routing it fails on an arc of the constant ground net. Its inactive
  peripheral/dedicated-pin connections still need documented treatment; this
  failure is retained, not solved by dropping connections.
- EFB logic timing is intentionally absent from the diagnostic. A report of
  `No Fmax available` is not a zero-delay or timing pass.

`verify.py` returns success for the declaration/routing/barrier checks and
records the original-wrapper result separately in `results.json`. That overall
diagnostic verification success must not be described as SC64 support.

## Blocking evidence

Pinned Trellis `libtrellis/src/Bels.cpp` and `fuzzers/machxo2/109-efb/`
describe the EFB pins and fabric routing, including the 7000 device. The
MachXO2 tile database has the EFB routing entries but no mapping for SC64's
`EFB_UFM`, UFM initialization region, or other EFB configuration parameters.
The pinned timing database provides no EFB timing model.

An old full-chip bitstream does not identify which unknown bits belong to EFB.
Copying unknown bits into a newly routed design could preserve old routing or
initialization. Configuration support requires documented fuse mappings or
controlled reference designs and independently checked bit differences; the
emission barrier stays in place until that evidence exists.
