# SPDX-License-Identifier: Apache-2.0
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gaia_bench as g  # noqa: E402


class GaiaBenchTests(unittest.TestCase):
    def test_extract_final(self):
        self.assertEqual(g.extract_final("ragiono...\nFINAL ANSWER: 42."), "42")
        self.assertEqual(g.extract_final("FINAL ANSWER: a\nFINAL ANSWER: b"), "b")
        self.assertIsNone(g.extract_final("niente"))
        self.assertEqual(g.extract_final("FINAL ANSWER: 1386</think>FINAL ANSWER: 1386"), "1386")

    def test_match_numbers_lists_strings(self):
        self.assertTrue(g.match("1,000", "1000"))
        self.assertTrue(g.match("$12.50", "12.5"))
        self.assertTrue(g.match("a, b ,c", "a,b,c"))
        self.assertFalse(g.match("a,b", "a,b,c"))
        self.assertTrue(g.match("The Cat", "the cat"))
        self.assertFalse(g.match(None, "x"))
        self.assertFalse(g.match("12", "13"))

    def test_run_python_isolated(self):
        self.assertEqual(g.run_python("print(2+2)").strip(), "4")

    def test_fetch_rejects_non_http(self):
        self.assertIn("errore", g.fetch_url("file:///etc/passwd"))


if __name__ == "__main__":
    unittest.main()
