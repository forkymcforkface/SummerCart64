"""HDL comparison must retain literals and functional synthesis attributes."""
import unittest
from run import tokens


class Tokens(unittest.TestCase):
    def test_regular_comments_and_spacing(self):
        self.assertEqual(tokens('module x; /* date */ endmodule'), tokens('// host\nmodule x; endmodule'))

    def test_synthesis_and_literals_are_semantic(self):
        for a, b in [('/* synthesis MODE=1 */', '/* synthesis MODE=0 */'),
                     ('"a b"', '"ab"'), ('"a//b"', '"a"'),
                     ('parameter X=1;', 'parameter X=0;'),
                     ('wire foo;', 'wirefoo;'), ('a<=b;', 'a< =b;')]:
            self.assertNotEqual(tokens(a), tokens(b))


if __name__ == '__main__':
    unittest.main()
