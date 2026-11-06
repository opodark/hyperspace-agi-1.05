# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import random
import unittest

import pytest

pytest.importorskip("unicorn")
pytest.importorskip("elftools")

from scripts.syndwars_verify import choose_args, fill_page, make_mutants


class VerifyHelpersTest(unittest.TestCase):
    def test_fill_page_is_stable_per_seed_and_address(self):
        self.assertEqual(fill_page(1, 0x1000), fill_page(1, 0x1000))
        self.assertNotEqual(fill_page(1, 0x1000), fill_page(2, 0x1000))

    def test_choose_args_extends_like_the_c_type(self):
        rng = random.Random(1)
        for _ in range(200):
            short_value, byte_value, pointer = choose_args([("short", "a"), ("ubyte", "b"), ("struct Thing *", "c")], rng)
            self.assertTrue(short_value <= 0x7FFF or short_value >= 0xFFFF8000)
            self.assertLessEqual(byte_value, 0xFF)
            self.assertGreaterEqual(pointer, 0x40000000)

    def test_mutants_change_one_operator_in_the_body_only(self):
        code = "int f(int a)\n{\n  int b;\n  if (a < 3) return p->x + 1;\n  return a == 2;\n}\n"
        mutants = make_mutants(code, "int f(int a)")
        self.assertTrue(mutants)
        for _description, mutant in mutants:
            self.assertTrue(mutant.startswith("int f(int a)\n{"))
            self.assertIn("p->x", mutant)
            self.assertNotEqual(mutant, code)


if __name__ == "__main__":
    unittest.main()
