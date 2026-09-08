# What SC64 actually programs for EFB/UFM

Checked 2026-09-06, without hardware access or changing any emission barrier.
The evidence narrows the question: stock SC64 does not program the separate
post-configuration JEDEC UFM image, and its requested zero initialization is
consistent with the erase operation it already performs. This does **not** yet
prove that changing EFB_UFM or UFM_INIT parameters leaves all configuration
bits unchanged. No extra static EFB enable fuse has been identified either.

## Actual update data path

[JedecFile in stock update.py](../../../../sw/tools/update.py) reads continuous
QF/L data MSB-first. On `NOTE END CONFIG DATA`, it fixes the accepted length at
the current position and ignores subsequent L fields. Feature fields are not
part of the returned FPGA bytes. EBR initialization *before* that marker remains
included; discarding subsequent UFM data does not discard every initialization
record in a JEDEC file.

An actual-source parser probe uses the vendor-converted official release JED
from `build/sc64-programmer-research/official-renamed.jed`. Flipping one data bit
after END CONFIG produces exactly the same parsed bytes; flipping a data bit
before it changes them. The returned configuration is 104,128 bytes, SHA-256
`961f9a9d23e2bbf650d5188dd767f568f6aa660cd9aa2b97d76cb8ff00fcae24`.
This is the converted artifact, not the original 104,144-byte release payload;
conversion changes framing/padding. The probe tests parser ownership, not
parameter compilation or byte equality with the release package. Results and
mutated fixtures remain ignored in `build/sc64-efb-config-research/`.

[vendor_update](../../../../sw/controller/src/lcmxo2.c) resets the configuration
address, erases CFG and UFM together, and writes/reads back exactly the supplied
number of 16-byte pages. It does not subsequently select or write the UFM
initialization region. It also does not erase the feature region: that mask is
separate. The official FPGA chunk has 6,509 pages, below the device's 9,211
configuration-page capacity. Therefore this release's write does not require
overflow into the UFM region.

The exact [generated EFB wrapper](../../../../fw/rtl/vendor/lcmxo2/generated/efb_lattice_generated.v)
requests eight all-zero UFM pages beginning at page 2038, with no initialization
file. The [EFB usage guide](https://www.latticesemi.com/view_document?document_id=39086)
defines erased flash bits as zero and describes the UFM initialization pages.
Thus erasing UFM is consistent with those particular zero contents. This is a
source/protocol inference, not a new physical UFM readback. Nonzero initialization
would not be provided by the current post-marker-discarding update path.

## Runtime controls are not automatically static fuses

The [register reference, CFGCR Table 16.2](https://www.latticesemi.com/view_document?document_id=46300)
defines WBCE as a runtime Wishbone connection enable. The actual MCU code sets
CFGCR[WBCE] around configuration commands and clears it afterward.
[vendor.sv](../../../../fw/rtl/vendor/lcmxo2/vendor.sv) provides the real
Wishbone request/acknowledgement path; its UFM interrupt wire is not consumed.
Source inspection found no separate application UFM-storage client in the
controller firmware. That does not make the EFB unnecessary: the same path
programs and verifies the FPGA configuration itself.

Parameter categories must stay separate:

| Item | Established | Still unproved |
| --- | --- | --- |
| UFM_INIT_FILE/ALL_ZEROS/PAGES/START_PAGE | Describe initialization intent; post-marker initialization bytes are excluded by SC64 packaging. | Whether varying these attributes also changes any pre-marker compiler metadata, configuration mode, or static bits. |
| EFB_UFM | Enabled in the wrapper; Wishbone is used by the working stock programmer. | Whether this exact mode requires static fields beyond existing routing, defaults, and runtime registers. |
| CFGCR[WBCE] | Runtime register written by MCU software. | It is not evidence of a separate configuration fuse. |
| SYSCONFIG and feature bits | Concrete configuration-port ownership settings exist and must be preserved. | They must not be conflated with an unidentified EFB enable field. |

The decoded official reference
`build/sc64-open-release-agent/durable-roundtrip-final/original.config` contains
`SYSCONFIG.I2C_PORT ENABLE` in PT5:CFG1. No SPI/SDM enum is explicitly printed;
default omission alone proves neither enabled nor disabled state. Its unknown
bit ledger has a nearby CIB_CFG3 F3B0 record, but no established attribution of
that record to EFB. The 433 total unknown records cannot all be labeled EFB.
Absence of a named EFB enum is likewise insufficient proof that new fuses are
required. A controlled equivalent-design comparison is still needed before
calling the existing emitter complete or incomplete for this exact function.

## Dedicated SN is an SDRAM address pin on this board

This is the material electrical fact: the
[schematic](../../../../hw/pcb/sc64v2.kicad_sch) names package pin 70
`PB38A/SN`. The [PCB](../../../../hw/pcb/sc64v2.kicad_pcb) assigns that pad to
`SDRAM_A5`, and the [stock LPF](../../../../fw/project/lcmxo2/sc64.lpf) places
`sdram_a[5]` at site 70 with PULLMODE=NONE. The pad toggles as an address output;
it is not an externally held-high configuration select. Consequently the
generated `.UFMSN(scuba_vhi)` cannot mean a fabric-routed physical constant on
that pad in the functioning board design.

Initial setup supplies another part of the contract:
[primer.py](../../../../sw/tools/primer.py) invokes CMD_INIT_FEATBITS after
program/verify. The MCU implementation requests bytes `{0x02, 0x20}`, named
`FEATBITS_0_SPI_OFF` and `FEATBITS_1_PROGRAMN_OFF`, and verifies them. Normal
vendor_update preserves those feature bits. The LPF explicitly disables
SDM_PORT and enables I2C_PORT.

The [programming guide, sections 6.6 and 7.1](https://www.latticesemi.com/view_document?document_id=39085)
describes EFB/Wishbone access and says both master and slave SPI ports must be
disabled to free their pins as GPIO. Therefore acceptance must preserve the
configuration/feature settings that disconnect configuration SPI from pin 70;
requiring an external pull-up would contradict this board. This source analysis
does not read or certify the current cart's feature bytes.

## Narrowed next check

Use controlled reference configurations differing only in EFB_UFM and the
initialization attributes, with identical routes and disabled user peripherals.
Compare decoded configuration, EBR data, post-marker UFM, and feature fields
independently. If all changes are confined to discarded initialization data,
that can close the initialization-emission question for the stock zero case.
It cannot independently close timing, oscillator requirements, configuration
port ownership, or the remaining unknown-bit mappings. The bitstream barrier
stays in place while those contracts remain unproved.
