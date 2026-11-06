# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import random
import unittest

import pytest

pytest.importorskip("unicorn")
pytest.importorskip("elftools")

from scripts.syndwars_verify import Callee, called_functions, choose_args, fill_page, make_mutants, narrow_value, parse_declaration, stub_return


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

    def test_parse_declaration_handles_unnamed_and_pointer_parameters(self):
        self.assertEqual(parse_declaration("extern short calc(struct Thing *p, short, ubyte b);"), ("short", ["void *", "short", "ubyte"]))
        self.assertEqual(parse_declaration("void f(void);"), ("void", []))
        self.assertEqual(parse_declaration("void g(void (*cb)(int, int), int n);"), ("void", ["void *", "int"]))

    def test_parse_declaration_refuses_what_a_stub_cannot_read(self):
        self.assertIsNone(parse_declaration("int log(const char *f, ...);"))
        self.assertIsNone(parse_declaration("void f(struct Coord p);"))
        self.assertIsNone(parse_declaration(""))

    def test_narrow_value_follows_the_c_type(self):
        self.assertEqual(narrow_value("short", 0x18000), 0xFFFF8000)
        self.assertEqual(narrow_value("ubyte", 0x1FF), 0xFF)
        self.assertEqual(narrow_value("struct Thing *", 0x12345678), 0x12345678)

    def test_stub_return_is_repeatable_and_fits_the_type(self):
        callee = Callee("f", "short", [], 0)
        self.assertEqual(stub_return(callee, 3, 9), stub_return(callee, 3, 9))
        for sequence in range(100):
            value = stub_return(callee, sequence, 1)
            self.assertTrue(value <= 0x7FFF or value >= 0xFFFF8000)

    def test_called_functions_strip_prefix_and_recursion(self):
        target = {"func_name": "me", "asm_code": "call ac_foo\n call ASM_bar\n call baz\n call ASM_me\n call *%eax\n"}
        self.assertEqual(called_functions(target), {"foo": "ac_foo", "bar": "ASM_bar", "baz": "baz"})

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
