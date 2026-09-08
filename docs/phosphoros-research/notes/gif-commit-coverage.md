# GIF commit coverage

Fresh reconciliation on 2026-09-06 for the vendor history through
`279d00ae5467c3a7797a23efc304fe2a55c9c055`. `PASS` means a fresh ignored
host/RTL result under ignored `build/sc64-gif-qualification/` only; it does not mean Diamond fit, timing, configuration, or
cart hardware qualification. The original input remains
`background.gif` SHA-256 `d48de154f477e6753b14d5d1a1fa7c5edcefe17c3688e9afbe790907bc7056b7`.

| Commit | Coverage and exact fresh evidence/disposition |
| --- | --- |
| `1a81179d192739aab30532adf3e4f4cfc18c9ea2` | PASS reference LZW: 1772 fixtures, 1717 originals, 200 cancellations; `legacy-reference/results.log`. |
| `2b3771874b5741cc157692464a443f653c516f8a` | PASS compositor/GPD1: 1717 frames, 430 packets and fault gates; `legacy-compositor-full/results.log`, `faults.log`. |
| `c8718491c347db059a156a5b059f69f290787d3f` | PASS cached dictionary: 1772 fixtures, 1717 originals, 200 cancellations and four memory fault/restarts; `legacy-cached/results.log`. |
| `9f69a7e1c6976334ea4d503c38cb03b9e58fd311` | PASS cached compositor: 1717 frames, 430 packets under serialized service; `legacy-cached-compose/results.log`. |
| `131cf169997a69ad9143b0ba9278478b01449871` | PASS existing DMA output: fresh 16 exports and 64 output cases; `legacy-dma-output/results.log`. |
| `84eb97c1061ac4fbac8247a98af43c14052350db` | PASS SC64 scratch adapter: dictionary4096, six canvas lanes, seven invalid configurations and 65 cancellation offsets; `bus/results.log`. |
| `26cbbdf78bb5f9d5e8b35d3abadccf4d989f88f4` | PASS host reuse discovery: 1717 frames, 407 retained exact RGBA payload/metadata matches; `legacy-repeated.json`. |
| `d9d6de7610b94b96cf03875373e246e50a558139` | PASS actual-controller cached integration: 1717 frames and 430 packets; `legacy-integration/results.log`. |
| `a661f4b5b89eb49d5aec1e66befd9cca92e8b723` | PASS runtime exact reuse: 1717 frames, 407 hits and 80 cancellation offsets; `legacy-reuse/results.log`. |
| `bf48bfa0b192faa6f1113589a791bc47b9cdf7d4` | COVERED by the fresh normalized original-phase reuse run above; no separate executable behavior remains. |
| `1954e6adb8cce8461129fd18ceb0fbcc26556ca0` | PASS cache-width comparison for 128/256/512 entries, each with 1772 fixtures, 1717 originals and fault/cancel gates; `cache7/result.json`, `cache8/result.json`, `cache9/result.json`. Smaller caches remain rejected. |
| `6b5f596e9858be517d81e5a3852568ec733c3e82` | PASS external spill and varied-spill negative gates; `spill/result.json`, `spill-varied/result.json`, summarized in `rejected-branches-review.md`. The spill architecture remains unselected. |
| `6bcf9b44ac99f06b78437202e79a9f8c7de9728a` | PASS phrase bound: 8390656 abstract transitions, maximum emitted391/walk392 and invalid jump rejection; `phrase-bound.log`. |
| `95a1f657e22c8475d16fe271ace41b075d00a1a6` | PASS full source/output DMA and readback transport: 1717 frames, 430 packets, 3208827902 cycles; `legacy-transport/results.log`. |
| `5129e8e6f725fb0add87e3e3114bb2f49d9a587c` | PASS coordinated transport abort: eight normal frames plus all 12 pulsed/held phase cases; `legacy-abort/{normal-results,results}.log`, `transport-history-review.md`. |
| `77a1692cb760dd28cb579ab69bdfc5b04db5512a` | PASS three-client mux equivalence/SAT/negative gates; `mux3/result.json`, `transport-history-review.md`. Superseded by four-client MCU mux for the selected source. |
| `47d393227375bfcd9d8027b29616fdeb6a297d68` | PASS bounded transport: eight matched normal frames plus all 12 abort cases using fresh mux3; `bounded-transport/result.json`. The bounded core itself is also covered by the compact run. |
| `3d1a9615492300b3f97de3b0caa9c094e9c92292` | PASS diagnostic transport mapping with physical-DQ wrapper: 2316 LUT4,384 CCU2D,1172 FF,4 DP8KC and16 DPR16X4; `legacy-transport-fit/result.json`. It is a synthesis audit, not board fit or timing. |
| `3afbbbffa680d6ee37c4257df83a0928d33f316c` | PASS header recurrence/saturation negative plus eight-frame/12-abort behavior; `header-behavior/result.json`, `rejected-branches-review.md`. Removed from raw output candidate. |
| `38b16fcc6e81d70d1f182fc9b36c4189512fd374` | PASS seven compositor arithmetic variants, six 1549-point equivalence checks and negative control; `proof-compose/result.json`, `rejected-branches-review.md`. Rejected for insignificant area gain. |
| `ee2f76ad0b70a4a034e32d617f6387adeb7d4c07` | PASS four-client MCU mux: stock512 and stalled/held-ACK/fairness cases plus incorrect-ACK negative; `mux4-run.log`. |
| `11af30dfb09b23c56199ac9283b4f6f8baa96702` | PASS actual-arbiter fairness: 54 cases with each required client completing3000 grants; `transport-fairness/result.json`. |
| `e5f166942787be072a001bbd4a0a4d6847a7e037` | PASS structural/liveness gate and both deliberate disconnected-RTL negatives; pack-only candidate is REJECTED at8644 TRELLIS_COMB versus6864 available, with26 EBR; `legacy-stock-fit/result.json`, `liveness.log`, `start/status/liveness.log`. |
| `5bc0dd8cc6fb6c651d2050b429d61d573c0cf384` | Documentation-only downstream-progress interpretation; no runner to rerun. |
| `0f3ca5dfb247ea82c9c165162e90aaba08e8f28a` | PASS compact bounded LZW: 1776 fixtures, 1717 originals, cancellation/fault/corrupt-dictionary gates and both negative variants; `compact-lzw/result.json`. |
| `be4a1aa9c405ca50e1b34ac7abd2c43ff8dcbc73` | PASS raw stock behavior through actual controller: 1717 raw frames plus four cancellation cases; `raw-full/result.json`, `raw-full/results.log`. |
| `2f56289c97f9a83be5caa6a5aab1dcfcb9945ac0` | Documentation-only MCU/N64 split analysis; no runner to rerun. Its API/consumer requirements remain open. |
| `468c8908bee75db573756070c8695cb495f227aa` | PASS compact raw stock integration: the `raw-full` manifest hashes compact core `fb9f244e`, dictionary and mux4, then records 1717 frames plus four cancellation cases. |

## Remaining scope

Every executable one of the 28 `tests/gif` commits now has fresh evidence.
`5bc0dd8` and `2f56289` are documentation-only commits. The transport-fit
and stock-fit outcomes are fresh rejected diagnostics, not Diamond fit,
timing, configuration, or hardware evidence.

The 12 open-toolchain-related experiments listed in `commit-inventory.md`
(`2ed3d8a`, `5855849`, `1af35a6`, `5a86733`, `875471e`, `b4e776f`,
`6f85918`, `3939923`, `12a6d18`, `79e54b4`, `50652f2`, `279d00a`) were not
rerun. They are open-tool mapping, placement, debugger, reset, or
control-set diagnostics, not inputs or qualification evidence for the direct
original-Diamond build. The untracked `reuse-packed` experiment is likewise
outside the 28-commit inventory and unselected.

Fresh queue16 paired evidence is supplementary, not a counted inventory
commit: both 64-byte baseline and 16-byte candidate complete1717 raw frames
and four cancellation cases. `queue16/final-result.json` records
2007513771 versus2027547849 cycles (+0.99795%) and a source-alias negative
failure; it is a resource/throughput tradeoff, not a speed or hardware claim.
