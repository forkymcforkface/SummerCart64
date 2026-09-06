"""Focused LPF fixtures: real manifest inventory and fail-closed mutations.

No generated fixtures or toolchain are needed. Test success means the guard
rejects unsupported qualification, not that the FPGA constraints are applied.
"""

import json
from pathlib import Path
import subprocess
import sys
import unittest

from audit import audit, tokens, top_inventory

ROOT = Path(__file__).resolve().parents[3]
LPF = ROOT / 'fw/project/lcmxo2/sc64.lpf'
TOP = ROOT / 'fw/rtl/top.sv'


class Constraints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lpf, cls.top = LPF.read_text(), TOP.read_text()

    def reject(self, text):
        result = audit(text, self.top)
        self.assertFalse(result['inventory_valid'])
        self.assertFalse(result['qualified'])
        return result

    def test_original_inventory(self):
        result = audit(self.lpf, self.top)
        self.assertTrue(result['inventory_valid'], result['errors'])
        self.assertFalse(result['qualified'])
        self.assertEqual(result['ports']['sdram_clk']['site'], '61')
        self.assertEqual(result['ports']['inclk']['site'], '3')
        self.assertEqual(result['ports']['n64_nmi']['electrical']['PULLMODE'], 'DOWN')
        self.assertEqual(len(result['groups']['sdram_bidir']), 16)
        self.assertEqual(len(result['groups']['sdram_output']), 21)
        self.assertEqual(len(result['statements']), self.lpf.count(';'))

    def test_quoted_adjacency(self):
        self.assertEqual(tokens('GROUP "sdram_bidir"INPUT_DELAY 5.4 ns;'),
                         ['GROUP', 'sdram_bidir', 'INPUT_DELAY', '5.4', 'ns', ';'])

    def test_comments_and_quotes(self):
        self.assertEqual(tokens('# pre\n A "quoted#name"; // post\n /* x */ B;'),
                         ['A', 'quoted#name', ';', 'B', ';'])

    def test_truncated_syntax(self):
        for text in ['IOBUF "unterminated', 'BANK 0 VCCIO 3.3 V']:
            with self.assertRaises(ValueError):
                audit(text, self.top)

    def test_unknown_verb(self):
        self.reject(self.lpf + '\nIGNORED_BY_BACKEND yes;')

    def test_unknown_port(self):
        self.reject(self.lpf.replace('COMP "button"', 'COMP "typo"'))

    def test_duplicate_site(self):
        self.reject(self.lpf.replace('COMP "inclk" SITE "3"', 'COMP "inclk" SITE "1"'))

    def test_missing_locate(self):
        self.reject(self.lpf.replace('LOCATE COMP "button" SITE "1" ;', ''))

    def test_missing_electrical(self):
        self.reject(self.lpf.replace('IOBUF PORT "button" PULLMODE=UP IO_TYPE=LVCMOS33 ;', ''))

    def test_duplicate_electrical(self):
        self.reject(self.lpf + '\nIOBUF PORT "button" PULLMODE=DOWN;')

    def test_group_and_clock_resolution(self):
        self.reject(self.lpf.replace('INPUT_SETUP GROUP "sdram_bidir"', 'INPUT_SETUP GROUP "typo"'))
        self.reject(self.lpf.replace('CLKNET "clk"', 'CLKNET "typo"'))

    def test_missing_timing(self):
        self.reject('\n'.join(line for line in self.lpf.splitlines() if not line.startswith('INPUT_SETUP')))

    def test_top_parser_rejects_unknown_grammar(self):
        with self.assertRaises(ValueError):
            top_inventory('module top(input [WIDTH-1:0] bus); endmodule')

    def test_cli_never_qualifies_original(self):
        run = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('audit.py')), str(LPF), str(TOP)],
                             capture_output=True, text=True, check=False)
        self.assertEqual(run.returncode, 3)
        self.assertTrue(json.loads(run.stdout)['inventory_valid'])
        self.assertFalse(json.loads(run.stdout)['qualified'])


if __name__ == '__main__':
    unittest.main()
