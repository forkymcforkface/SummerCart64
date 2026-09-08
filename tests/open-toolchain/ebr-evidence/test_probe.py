"""Exercise rejection and site association in the read-only EBR probe."""

import unittest

from probe import ncl_sites


FIXTURE = '''design top {
   comp memory
   {
      logical {
         cellmodel-name EBR;
         program "MODE:DP8KC " "DP8KC:::WID=0b0000000011";
      }
      site EBR_R13C1;
   }
}'''


class ProbeTest(unittest.TestCase):
    def test_site_and_word(self):
        result = ncl_sites(FIXTURE)
        self.assertEqual(list(result), ["EBR_R13C2:EBR1"])
        self.assertEqual(result["EBR_R13C2:EBR1"]["wid"], ["0000000011"])
        self.assertEqual(result["EBR_R13C2:EBR1"]["rid"], [])

    def test_rejections(self):
        cases = ["", FIXTURE + FIXTURE,
                 FIXTURE.replace("site EBR_R13C1;", ""),
                 FIXTURE.replace("MODE:DP8KC", "MODE:UNKNOWN"),
                 FIXTURE.replace("site EBR_R13C1;",
                                 "site EBR_R13C1; site EBR_R20C1;")]
        for text in cases:
            with self.subTest(text=text), self.assertRaises(ValueError):
                ncl_sites(text)


if __name__ == "__main__":
    unittest.main()
