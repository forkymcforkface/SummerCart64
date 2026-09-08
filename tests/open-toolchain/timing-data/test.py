"""Synthetic rejection tests; no vendor database fixture is redistributed."""

import pathlib
import struct
import sys
import zlib

sys.dont_write_bytecode = True
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import probe


def rejects(function, *args):
    try:
        function(*args)
    except (ValueError, zlib.error):
        return
    raise AssertionError("malformed input accepted")


compressed = zlib.compress(b"fixture_ASS\0")
wrapped = b" _$COMP\0\x32\0" + struct.pack(">I", len(compressed)) + compressed
assert probe.tld_probe(wrapped)["decoded_bytes"] == 12
for bad in (b"", b"wrong", wrapped[:10], wrapped[:-1], wrapped + b"x",
            wrapped[:10] + struct.pack(">I", 0),
            wrapped[:10] + struct.pack(">I", len(compressed) + 1) + compressed + b"x"):
    rejects(probe.tld_probe, bad)
large = zlib.compress(b"x" * 8193)
rejects(probe.tld_probe, wrapped[:10] + struct.pack(">I", len(large)) + large)
rejects(probe.spd_records, b"", "xo2c7000")
rejects(probe.spd_records, b"", "unknown")
rejects(probe.selected, [], "REG_DEL")
rows = [{"grade": "6", "name": "REG_DEL", "condition": "CLKMUX:CLK:::CLK=#SIG",
         "slots": value} for value in ([1, 2, 3, 4], [1, 2, 3, 5])]
rejects(probe.selected, rows, "REG_DEL")

oracle = r'''(DELAYFILE
 (DESIGN "control_soc_demo") (TIMESCALE 1ps)
 (CELL (CELLTYPE "adc_wb_inst_adc_inst_SSD_ADC_SLICE_0")
  (INSTANCE adc_wb_inst\/adc_inst\/SSD_ADC\/SLICE_0)
  (DELAY (ABSOLUTE (IOPATH CLK Q0 (133:143:154) (133:143:154))))
 )
)'''
probe.minimum_oracle_check(oracle)
assert '(IOPATH CLK Q0 (133:143:154)' in probe.oracle_cell(oracle)
wrong_cell = '(CELL (CELLTYPE "other") (INSTANCE other) (DELAY (ABSOLUTE (IOPATH CLK Q0 (133:143:154)))))'
bad_oracles = [
    oracle.replace('control_soc_demo', 'other_design'),
    oracle.replace('(DESIGN "control_soc_demo")', ''),
    oracle.replace('(TIMESCALE 1ps)', '(TIMESCALE 1ns)'),
    oracle.replace('(TIMESCALE 1ps)', ''),
    oracle.replace('(TIMESCALE 1ps)', '(TIMESCALE 1ps) (TIMESCALE 1ns)'),
    oracle.replace('adc_wb_inst_adc_inst_SSD_ADC_SLICE_0', 'other'),
    oracle.replace('adc_wb_inst\/adc_inst\/SSD_ADC\/SLICE_0', 'other'),
    oracle + oracle,
    oracle[:-1] + probe.oracle_cell(oracle) + ')',
    oracle.replace('133:143:154', '1:2:3'),
    oracle.replace('133:143:154', '1:2:3')[:-1] + wrong_cell + ')',
    oracle.replace('133:143:154', '1:2:3') + '(IOPATH CLK Q0 (133:143:154))',
    oracle[:oracle.index('  (DELAY')],
]
for bad in bad_oracles:
    rejects(probe.minimum_oracle_check, bad)
print("PASS: synthetic wrapper/oracle positives + 25 rejection checks")
