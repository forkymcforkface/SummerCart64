# Official release reference and byte identity

On 2026-09-05 the GitHub latest-release API and [official release page](https://github.com/Polprzewodnikowy/SummerCart64/releases/tag/v2.20.2) identify **v2.20.2**, published 2024-11-18T22:00:09Z, source commit **18041e25472075a166292d1195603bcefe9c9688**. The current PhosphorOS fork or current upstream main is not that release source.

Official downloaded references, kept only in ignored `build/sc64-open-release-agent/` of the parent checkout:

| Asset | Bytes | SHA-256 |
|---|---:|---|
| `sc64-firmware-v2.20.2.bin` | 195040 | `1616417c883d710f313a139a7ac29228a1b9870d8c2f22b4c864c05266408659` |
| `sc64-extra-v2.20.2.zip` | 2703402 | `8d99aa1cb2287d363eaeaa7a911dc47f3c968448db0c8c7d00b1026e1a79f48b` |

The extra archive includes firmware, primer script, frequency report, documentation and hardware assets; it does not include the FPGA JEDEC/netlist/placement database. The exact public download URLs are the release's `releases/download/v2.20.2/` paths with those filenames. `release.json` preserves API metadata. No hardware reference was downloaded from the user's cart.

## Validated component identities

All update chunk CRCs, lengths and zero padding pass inspection.

| ID / component | File payload interval, end exclusive | Bytes | SHA-256 |
|---|---|---:|---|
| 1 / update info | [32,214) | 182 | `c5043c4f1a41a7cbf64cb8af7f9edb4400508673eca5e0535fb78e5124bfae14` |
| 2 / MCU | [240,21888) | 21648 | `0244c900e88b3c6fb9b692203ed05dd28a2f2ebecc8599c870c5cdad97c872c8` |
| 3 / FPGA | [21904,126048) | 104144 | `c4bd900a8727cfeb4906bf27a8795246e3039b3071cc879c19ab0969139bf1ee` |
| 4 / bootloader | [126064,191600) | 65536 | `fce0ced2daac4a54955dd2fe0f53ff12ac5fccc0d38732ffbc4252c5e21f6615` |
| 5 / primer | [191616,195036) | 3420 | `d59d0af385bb387fad2e9406dd8575852f6d1fcf8f2979413de6f0e2dbe98336` |

The info text records builder `fv-az1776-431`, creation `2024-11-18 22:10:49`, frequency `102.891 MHz`, version/tag `v2.20.2`, branch `HEAD`, the source commit above and message `[SC64] v2.20.2 release`.

## What has and has not been reproduced

Direct `ecpunpack` rejects the extracted payload's missing `.BIT` metadata framing. Adding an empty `FF00` metadata prefix alone then fails because the stream lacks an explicit device-identification command. The payload itself starts with the valid `FFFFBDB3FFFF` preamble and a CRC reset: it is a headerless compressed configuration command stream, not an unrelated raw CRAM matrix.

Release `sw/tools/update.py::JedecFile` reads continuous JEDEC configuration fuses, MSB first in each byte, stopping at `NOTE END CONFIG DATA`. `lcmxo2.c::vendor_update` programs them as 16-byte nonvolatile flash pages. The 104144-byte component is 6509 pages. The unfinished [Trellis JEDEC PR 233](https://github.com/YosysHQ/prjtrellis/pull/233), head `839f9f51f61a09bb7397a122333bc212521543c5`, supplied the useful observation that JEDEC can carry the serialized command stream with its metadata removed; that patch was inspected, not applied.

`roundtrip.py` preserves every original payload byte and inserts an empty metadata prefix plus the documented VERIFY_ID command for `LCMXO2-7000HC` (`0x012bd043`) **before the original CRC reset**. Trellis then decodes the original stream successfully, including CRC checking and 770 compressed configuration frames. `ecppack --compress` followed by `ecpunpack` produces a byte-identical decoded text configuration: SHA-256 `ccd8afe3cad9cb4df5acb963d9b17e8336c9bb6f54dc2440c136a96e4a9bca69`. Its 433 unknown-bit records survive. The repacked command stream is **104128 bytes versus 104144**, and is not byte-identical; exact differing intervals are recorded in the generated results. Changed command framing/control sequences are not automatically safe programming equivalents.

This is successful **reference replay at decoded configuration level**, not compilation from RTL or exact firmware reproduction. A single reference image cannot identify unknown EFB bits safely by itself. Do not transplant unknown records into a newly routed design or use a copied FPGA component to claim an open-toolchain source rebuild.

The 433 unknown records group as follows: EBR1 120, CIB_EBR0 72, CIB_EBR1 60, CIB_EBR2 51, CIB_PIC_B_DUMMY 27, CIB_PIC_B0 27, CIB_EBR_DUMMY 18, PIC_B0 16, PIC_R1 16, PIC_T0 11, PIC_L2 8, LLC2 2, PIC_L2_VREF4 2, CIB_EBR0_END2_DLL3 2 and CIB_CFG3 1. The nearby CFG record is `CIB_R1C7:CIB_CFG3 F3B0`; there are no reported unknowns in CFG0/CFG1/CFG2 or the decoded PLL tile. CFG1 explicitly decodes `SYSCONFIG.I2C_PORT ENABLE`. PLL phase/divider and analog 9/72 attributes decode as expected. These counts do **not** establish that any unknown is an EFB enable fuse: hard-IP behavior may use fixed routing and runtime CFGCR control, and absent set-bit records cannot prove that no configuration is needed. The parent owns the EFB implementation investigation.

The release packaging script also embeds `platform.node()` and current UTC time. Its build wrapper includes frequency and Git metadata. Thus even matching rebuilt MCU/bootloader/primer/FPGA payloads does not automatically reproduce the entire container; metadata must be reported separately and deliberately reproduced, never silently excluded from a byte-for-byte claim. Different synthesis/place/route tools can produce functionally equivalent but different FPGA bytes. Exact matching must be measured, not inferred from equivalence or a matching source revision.

## Reproduce inspection and comparison

From an SC64 checkout:

```sh
python3 -B tests/open-toolchain/release/test_release.py
python3 -B tests/open-toolchain/release/release_update.py ORIGINAL.bin /path/to/build/reference-chunks
python3 -B tests/open-toolchain/release/compare.py ORIGINAL.bin CANDIDATE.bin
python3 -B tests/open-toolchain/release/roundtrip.py /path/to/chunk-3.bin /path/to/build/roundtrip
```

Inspection validates before creating its new output directory and extracts each chunk with a manifest. Comparison validates both containers and reports every differing byte interval, both whole-file and relative to each payload; exit 0 means byte identity and exit 1 means differences. Missing components remain explicit. These tools do not compile, normalize metadata, package replacement firmware or flash hardware. Generated references/reports stay outside `tests/`.

The roundtrip command needs the pinned Trellis `ecpunpack`/`ecppack` executables. Exit 0 means decoded configuration identity only; `source_rebuilt` and `command_bytes_identical` remain explicit. No candidate FPGA source rebuild exists in this audit, so no candidate-source-vs-release differing regions are claimed. Seven in-memory tests also include a single-byte CPU mismatch with its exact interval.

## Parent-verified CPU source rebuild

The parent rebuilt official source `18041e25472075a166292d1195603bcefe9c9688` with image `ghcr.io/polprzewodnikowy/sc64env@sha256:7d8621a136c7a8ba142b60c85f166d04f0fee7e7f461366ae885b2059a240cd2` and the release Git metadata:

```sh
GIT_BRANCH=HEAD GIT_TAG=v2.20.2 \
GIT_SHA=18041e25472075a166292d1195603bcefe9c9688 \
GIT_MESSAGE='[SC64] v2.20.2 release' ./build.sh bootloader controller cic
python3 -B tests/open-toolchain/release/cpu.py /path/to/built/source ORIGINAL.bin
```

MCU, bootloader and primer are each **byte-identical** to their official chunks above; the compiled CIC image is 1856 bytes and feeds FPGA synthesis rather than a separate update chunk. The parent retains build logs and `build/sc64-open-release/cpu-comparison.json`. `cpu.py` validates the release through the shared chunk reader and reports mismatches without implying an FPGA source rebuild.

## Exact reference command serialization

`serialize_reference.py` takes the **fresh `ecppack --compress` result**, not the original release payload. It validates the pinned 7000HC command profile and all input CRCs, walks all 770 compressed frames structurally, retains their generated bytes and EBR data, then serializes the observed release command profile. It recalculates the affected CRC rather than copying it from the original. The generated output is **104144 bytes, SHA-256 `c4bd900a8727cfeb4906bf27a8795246e3039b3071cc879c19ab0969139bf1ee`**, byte-identical to the official FPGA chunk. This is exact **decoded-reference serialization**, still not FPGA RTL compilation. All 433 unknown configuration records originate from the reference and must not be transplanted into new routes.

```sh
python3 -B tests/open-toolchain/release/test_serialize_reference.py
python3 -B tests/open-toolchain/release/serialize_reference.py \
    /path/to/roundtrip/repacked.bit /path/to/build/serialized-reference.bin
```

The output path must be new and outside `tests/`. Five focused fixtures check a known CRC vector, exact synthetic serialization with two different usercodes, corruption of each CRC region, wrong device, truncation, trailing bytes and out-of-range EBR addresses with valid CRCs. The helper has no original-payload argument. A separate comparison against the extracted release establishes identity; successful serialization alone makes no identity claim.

The precise difference from default Trellis serialization is:

| Region | Official release profile | Default Trellis profile | Official size minus default |
| --- | --- | --- | ---: |
| Before frame data | Dictionary before INIT; no VERIFY_ID or early CTRL0 | VERIFY_ID, CTRL0=40000000, four dummy bytes; dictionary after INIT | -20 |
| After USERCODE | CTRL0=C0000000 and eight dummy bytes | Absent | +16 |
| Four EBR blocks | `B2 10 00 80`, no CRC; four dummy bytes between blocks | `B2 D0 00 80`, two CRC bytes per block | +4 |
| Finalization | Four dummy bytes before DONE, sixteen after | No dummy before DONE, four after | +16 |
| Total | 104144 bytes | 104128 bytes | +16 |

The compressed command plus frame body is 99382 bytes and already identical. The dictionary is `09 03 30 28 50 05 48 ff` in wire order. EBR addresses are `0x1800`, `0x2000`, `0x2800`, `0x3000`; contents and order already match. The first frame CRC changes because the preceding command sequence changes; USERCODE CRC remains `2aa7` for zero USERCODE, and EBR CRCs are omitted by the observed profile.

The owning implementation is [Trellis `Bitstream.cpp` at 3afe7b5](https://github.com/YosysHQ/prjtrellis/blob/3afe7b52b30f4b4417ee98f03016767a502006e3/libtrellis/src/Bitstream.cpp): `write_compressed_frames` chooses the eight most frequent nonzero, non-one-hot bytes using a `(count, byte)` priority queue, resolves ties by byte value, and writes dictionary entries in reverse order. Zero, one-hot, dictionary and literal encodings use 1, 6, 6 and 10 bits respectively. Each frame aligns to a byte; MachXO2 frames retain forward order. CRC polynomial is `0x8005`, initial value zero, with sixteen final zero bits; dummy command bytes do not update CRC. The helper reuses those generated compressed bytes instead of introducing another compressor.

The pinned `ecppack` CLI exposes compression, usercode, idcode, frequency, SPI mode, background mode and multiboot options, but no options for this command order, EBR CRC policy or padding. The separate serializer supplies that narrow observed profile without modifying Trellis or the existing `roundtrip.py`. Neither reference identity nor this profile qualifies a newly synthesized design, a different release/device, or programming hardware.

## Whole-package reference reconstruction

The parent independently repeats the roundtrip and exact serialization, then
combines the serialized FPGA bytes with the three independently rebuilt CPU
binaries using the original source's `sw/tools/update.py` packer. Reference
build metadata is retained explicitly. All **195040 bytes** match the original
release, SHA-256
`1616417c883d710f313a139a7ac29228a1b9870d8c2f22b4c864c05266408659`.

```sh
python3 -B tests/open-toolchain/release/test_reconstruct.py
python3 -B tests/open-toolchain/release/reconstruct.py \
    /path/to/built/release/source ORIGINAL.bin \
    /path/to/build/serialized-reference.bin /path/to/build/reconstructed
```

`reconstruct.py` rejects CPU, FPGA and final package mismatches before creating
its output directory. Six tests exercise those gates with the actual upstream
packer. Its report describes byte equality; retain the CPU build logs and
serializer inputs separately to establish how those supplied bytes arose.
The FPGA configuration and metadata originate from the reference. Therefore
this is an exact reference reconstruction, **not an independent all-source
FPGA rebuild**. It does not qualify new FPGA logic or establish timing safety.
