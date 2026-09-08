# PhosphorOS history migration

The unpublished series after `3e43f9096d4bbcd0f633e97651bc60516d20622d` contained 58 commits. This migration removes 55 research commits from PhosphorOS and preserves three production changes. Research document and receiver-tool history is imported into this SummerCart64 repository; existing firmware commits remain here. Original hashes below identify historical measurements and are not rewritten in the ledgers.

## Preserved production changes

| Original PhosphorOS commit | Replayed commit |
| --- | --- |
| `57799b9de04a1ddd8980432dea6f9dfc96ebb25d` | `1c3ff78f28e4d14ecf4af1f77bb1da7625d5df97` |
| `88976d497694db870dff428e1126d7d85bf8e972` | `fe89cc0177110e60c39d3e84d682169791451553` |
| `6a39cafd08e02c4df41924548e06b80278e1c84a` | `aef1f60cbdc1dca84445e73ba6e8d487df64eb67` |

## Removed PhosphorOS research commits

| Original commit | Subject | Imported document/tool commit |
| --- | --- | --- |
| `ab74e88eed0945c02c6a57caa5c99d7445b4cbd5` | docs: maintain SC64 boot optimization test ledger | `4dfaea11cab50a2ea53e5d12b770c05cf4a20c86` |
| `d25fe66f2e9f504fb28a7a44bb6c11c74b86ce65` | docs: record SC64 UI and original GIF acceleration experiments | `da6dc28a498dd9b9cf376e336398a034b9e53e9f` |
| `929f44d5e9e3833f763fe7e5a672cd2f7d9d222a` | test: track experimental SC64 GIF decoder reference suite | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `d363c1fbf6e57394312babb1f8e3fe5ca519f407` | test: track SC64 GIF composition prototype | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `dd8bb0f7eb9fc268ce3d76e3726bb12e511c1e6a` | test: track experimental SC64 cached GIF decoder | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `ded1c59b36ede39b5742b3f5771d500edb68bfd9` | test: retain source-checked SC64 GIF receiver diagnostics | `f5448905d8f90e44d43e138484a9332793503ddc` |
| `9c10db90d7c3452af1702cf779e9b350301a32e6` | test: track SC64 GIF shared-memory simulation | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `b0a126defc5750e532127a328513fca996e925e6` | docs: record original GIF FPGA prototype and N64 receiver results | `d97d7e12d2967c9bf8637ca5cf932f40906af03d` |
| `25995ca830abdf07cc2c1496dae78ae22c173e0f` | test: track SC64 GIF output DMA reuse probe | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `2513948be5503b830e2ac2de1e6b7edd64fd74c3` | test: track bounded SC64 GIF memory client | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `75714bc85d596de7b7e0a262f355fc9c11a91d58` | test: track source GIF repeated-frame probe | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `c078bd771b39e43645e9718173d243232c7577a9` | test: track original GIF SC64 controller integration | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `27cff6bb2f9b3fffc4e7120b2aa0c68a5b72116d` | docs: audit original OS4 theme conversion requirements | `d48b4c65920e0b78ae8765f1a5188765239090f0` |
| `fac6a9d283a31e53746817c73dfab4413a73d313` | docs: record GIF memory controller integration results | `f8b845bc61b07bc2f2adfce2643a79063236d29a` |
| `5aa66407a5da19a73415f3393e14c005c08f3350` | test: track exact runtime GIF reuse prototype | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `df0dbee7f5d3f3b783538a6cde1e7e10fe489da5` | test: track reproducible GIF reuse timing baseline | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `4249845b764580b0360d216176c92fcf8e94b07e` | test: track license-free SC64 FPGA toolchain probes | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `26f7a2b26d1720f1edd990468d789fbf2d4ed831` | docs: record open SC64 toolchain results and hardware blockers | `0570501f80788ced4777c5dd34f498b3ea7f917c` |
| `9c68161ec1e5fc107d38870497de2ff876c072c5` | test: track guarded open SC64 backend diagnostics | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `ad14bae6d1bea11bf784db570edd2368d0484fd4` | docs: record open FPGA backend tests and qualification blockers | `07217e17d8e1eb1d49f1bd7ab9221c9b2d3f11ae` |
| `af3b8ac35a0b86fab5455b04b90fba8dd35df4d6` | Track SC64 reference reconstruction and proved memory tooling | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `424a8e77b591ce691462ad2953b118619b80e9d9` | Record exact reference identity and source-toolchain qualification gaps | `e12daab0f6e73abea184a2b7fdbdfea192a7a82c` |
| `f0f014ac04ecfa6ebc58a4743d26e4e3f24632ca` | Track verified SC64 routing and configuration tooling | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `68d8fb5b1f5aad3b2acd06d3da297a7f61ecd695` | Record routed timing failures and remaining FPGA qualification work | `d737bb2d9572d0fca971652e81d22f21f2778867` |
| `1536bff2e2c318a33c5fe4a98b4f861d37608a1c` | Update SC64 research tools for timing and constraint validation | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `40b9475ea1e8779d899e11f40afd8a30006c2f78` | Record further SC64 timing experiments and independent checks | `37f58a3b3f5a67671b03778f6b6c4bdbf2650b2d` |
| `42a85f5f22cc873a22305f22a79e7d8bc78d2b9b` | Update SC64 research for reproducible STA and configuration audits | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `1a914a149bdaba830442da99f61fcaba280864f9` | Record public FPGA oracle searches and configuration audit | `2bce37f1649f72b8924610de885a79b0cc4b88be` |
| `4fa3146fef9de5ff103661e414a94eca152cb138` | Update SC64 public configuration comparison evidence | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `7716e3801271f6108f1f3173022553e3403cc5bf` | Record public EBR counterexample and remaining qualification gaps | `8f08273864d124dbf655708de6e2037ddec2ed06` |
| `e332c507f6f0384a312b6579b9cba0423c62b50c` | build: advance SC64 evidence and source-pattern verification | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `14580b5a4633a00d723f2a8c607290541671a131` | docs: consolidate project audit and current FPGA test results | `c9900cc34d3864b94069de57520048da07bd62ae` |
| `e1e50ab4d4551ecd74e329c43a1bb29fa8ee032f` | build: track verified SC64 RAM and DMA experiments | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `82da14eb5133479c8960a8b0131443932a03b879` | docs: record behavior target and FPGA memory-fit results | `3dafdf02f8bda4c6b04c3ca8fe16a1f1546804dc` |
| `bc22cb811cfa6d1b84552a0bd84e6dce3980a89e` | test: pin verified bounded SC64 GIF transport experiments | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `918ff4c9c39694d7b60c82d7d896e0384e2958f8` | docs: record bounded GIF transport results and remaining fit limits | `0276ba1285e5f11621a860c764c46217c73cd8a1` |
| `982d598775b90e2a064658a04fca9ed6fa587912` | test: pin MCU-safe GIF arbitration and stock resource audits | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `b1f9282fd5eb2ce74b9e7817d94c2f74990357c6` | docs: record stock GIF integration resource rejection | `dcef32f0f7246372f932e19a05c18b228ded923d` |
| `9f25c8473d4bd1378ff9e92d47d612b1883148c1` | test: pin smaller raw GIF accelerator experiments | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `7fb369afe573ad943e586b855d267640d0923084` | docs: record resource-compatible raw GIF design and placement limit | `6d5eb8ecc268c6b2d88f5a2a0bb537d54355e9b8` |
| `b9b0e3afcc6d293da6ef3fe177e04095fc5f7b10` | test: track compact SC64 integration and placement probes | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `d39811766250a92c45bc72f74516f42279d2b647` | docs: record compact integration proof and placement results | `23b4e125336c235176cb8d417a8b48c18fd0c5ee` |
| `88e3a67a0c7d46982b3a3087bade3211f8bdb8b4` | test: track SC64 placement localization diagnostics | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `b875d9eb51d836ae3d3e902d413c52d78cd41955` | docs: record SC64 control set investigation results | `44b0ff36374af8bc89b6f0afe515f3b3b3adb938` |
| `6533f5bff3c15a7272a3bad11273ec22f43d5d49` | docs: maintain SC64 open toolchain and GIF gap tracker | `84deeb32a3a0389f13be985a20b41412ec3b5800` |
| `57e7026a7bbd3a0117c6bb64a5dab6ea7add124c` | docs: track untested control set placement alternative | `213f25d936b9d52057b7a453405cb8dbf5db2bdd` |
| `d0398f9fdba09f47369c3783ee2af206fc3d62a5` | test: track reviewed SC64 reset mapping probe | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `dfaedaf72bfc11501e156a4e43166adcdeab2f7a` | docs: record reset mapping rejection and next placement gap | `d4b16e894f3ae7bc4a5bdf6216d2e96c313ea0a4` |
| `74b771da5d2f825917e48d413656e203b3207f9c` | docs(sc64): record GIF qualification baseline and first fit failure | `87012fd3814e8ff1c243dd99d6f704487ef8a5fd` |
| `91ed6bed6e823a78c2c4ac28464a7991d2bd28d6` | test(sc64): retain complete original GIF transport gate | Firmware pointer or benchmark record; preserved in this repository and benchmark extracts |
| `59330bc15480d3b22836f927348ed1e5c9d30dc7` | docs(sc64): track streaming-only GIF qualification and memory trials | `b466b461372beef0d8e39ce1da7f452cd02de134` |
| `8aa8cb2511de612184bf1d2f9cd5349ccdbe146a` | docs(sc64): record complete GIF replay and routed timing results | `2e9047054c828c7a81cb2a7aa4b6b6bf426e61db` |
| `a0bc25c9a85ea4369bae3d01536ca06f7db63887` | docs: prioritize practical SC64 integration improvements | `4781b7006a6a037ecef9702d5f1be3e7572c0c9d` |
| `924a7d6e51194f37583bbf5334927b44191aa643` | docs: record SC64 SD and USB overlap hardware comparisons | `9d3bdce46dd31560286f43b5c3d7d09368dab2fc` |
| `21f60f872bd5c03fd623ebfc35f071d77a6e2556` | docs: record rejected SDRAM dispatch bypass timing experiment | `fa0d6cedb43435ad5828f3d708081cd8196e7c15` |

## Imported document history

This includes the research portions of mixed production/document commits.

| Original commit | SummerCart64 document commit |
| --- | --- |
| `14580b5a4633a00d723f2a8c607290541671a131` | `c9900cc34d3864b94069de57520048da07bd62ae` |
| `1a914a149bdaba830442da99f61fcaba280864f9` | `2bce37f1649f72b8924610de885a79b0cc4b88be` |
| `21f60f872bd5c03fd623ebfc35f071d77a6e2556` | `fa0d6cedb43435ad5828f3d708081cd8196e7c15` |
| `26f7a2b26d1720f1edd990468d789fbf2d4ed831` | `0570501f80788ced4777c5dd34f498b3ea7f917c` |
| `27cff6bb2f9b3fffc4e7120b2aa0c68a5b72116d` | `d48b4c65920e0b78ae8765f1a5188765239090f0` |
| `40b9475ea1e8779d899e11f40afd8a30006c2f78` | `37f58a3b3f5a67671b03778f6b6c4bdbf2650b2d` |
| `424a8e77b591ce691462ad2953b118619b80e9d9` | `e12daab0f6e73abea184a2b7fdbdfea192a7a82c` |
| `57799b9de04a1ddd8980432dea6f9dfc96ebb25d` | `1cd19d17043056794de62777c0e9f1b56fd6410d` |
| `57e7026a7bbd3a0117c6bb64a5dab6ea7add124c` | `213f25d936b9d52057b7a453405cb8dbf5db2bdd` |
| `59330bc15480d3b22836f927348ed1e5c9d30dc7` | `b466b461372beef0d8e39ce1da7f452cd02de134` |
| `6533f5bff3c15a7272a3bad11273ec22f43d5d49` | `84deeb32a3a0389f13be985a20b41412ec3b5800` |
| `68d8fb5b1f5aad3b2acd06d3da297a7f61ecd695` | `d737bb2d9572d0fca971652e81d22f21f2778867` |
| `74b771da5d2f825917e48d413656e203b3207f9c` | `87012fd3814e8ff1c243dd99d6f704487ef8a5fd` |
| `7716e3801271f6108f1f3173022553e3403cc5bf` | `8f08273864d124dbf655708de6e2037ddec2ed06` |
| `7fb369afe573ad943e586b855d267640d0923084` | `6d5eb8ecc268c6b2d88f5a2a0bb537d54355e9b8` |
| `82da14eb5133479c8960a8b0131443932a03b879` | `3dafdf02f8bda4c6b04c3ca8fe16a1f1546804dc` |
| `88976d497694db870dff428e1126d7d85bf8e972` | `806852335e5457431ba10e001b1cf4184dc83a87` |
| `8aa8cb2511de612184bf1d2f9cd5349ccdbe146a` | `2e9047054c828c7a81cb2a7aa4b6b6bf426e61db` |
| `918ff4c9c39694d7b60c82d7d896e0384e2958f8` | `0276ba1285e5f11621a860c764c46217c73cd8a1` |
| `924a7d6e51194f37583bbf5334927b44191aa643` | `9d3bdce46dd31560286f43b5c3d7d09368dab2fc` |
| `a0bc25c9a85ea4369bae3d01536ca06f7db63887` | `4781b7006a6a037ecef9702d5f1be3e7572c0c9d` |
| `ab74e88eed0945c02c6a57caa5c99d7445b4cbd5` | `4dfaea11cab50a2ea53e5d12b770c05cf4a20c86` |
| `ad14bae6d1bea11bf784db570edd2368d0484fd4` | `07217e17d8e1eb1d49f1bd7ab9221c9b2d3f11ae` |
| `b0a126defc5750e532127a328513fca996e925e6` | `d97d7e12d2967c9bf8637ca5cf932f40906af03d` |
| `b1f9282fd5eb2ce74b9e7817d94c2f74990357c6` | `dcef32f0f7246372f932e19a05c18b228ded923d` |
| `b875d9eb51d836ae3d3e902d413c52d78cd41955` | `44b0ff36374af8bc89b6f0afe515f3b3b3adb938` |
| `d25fe66f2e9f504fb28a7a44bb6c11c74b86ce65` | `da6dc28a498dd9b9cf376e336398a034b9e53e9f` |
| `d39811766250a92c45bc72f74516f42279d2b647` | `23b4e125336c235176cb8d417a8b48c18fd0c5ee` |
| `ded1c59b36ede39b5742b3f5771d500edb68bfd9` | `f5448905d8f90e44d43e138484a9332793503ddc` |
| `dfaedaf72bfc11501e156a4e43166adcdeab2f7a` | `d4b16e894f3ae7bc4a5bdf6216d2e96c313ea0a4` |
| `fac6a9d283a31e53746817c73dfab4413a73d313` | `f8b845bc61b07bc2f2adfce2643a79063236d29a` |
