# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import unittest

from scripts.syndwars_local_targets import add_global_alias, find_local_function, find_wrapper, make_target, nearest_c_file, stub_from_declaration

SEP = "/*----------------------------------------------------------------"


class LocalTargetsTest(unittest.TestCase):
    def setUp(self):
        self.lines = ["before", SEP, "tank_los:\t/* 0x05F8B4 */", SEP, "\tpush   %ebx", "\tret", SEP, "other:", SEP, "\tret"]

    def test_finds_the_block_of_a_local_function(self):
        self.assertEqual(find_local_function(self.lines, "tank_los"), (2, 6))

    def test_ignores_inner_labels(self):
        lines = ["\tjump_1:", "tank_los:", "\tret"]
        self.assertIsNone(find_local_function(lines, "tank_los"))
        self.assertIsNone(find_local_function(lines, "jump_1"))

    def test_alias_sits_at_the_same_address(self):
        self.assertTrue(add_global_alias(self.lines, "tank_los"))
        self.assertEqual(self.lines[2:4], ["GLOBAL_FUNC(ASM_tank_los)", "tank_los:\t/* 0x05F8B4 */"])
        self.assertFalse(add_global_alias(self.lines, "missing"))

    def test_global_labels_count_as_local_functions(self):
        lines = [SEP, "GLOBAL_FUNC(swoosh_veh)\t/* 0x1 */", SEP, "\tret"]
        self.assertEqual(find_local_function(lines, "swoosh_veh"), (1, 4))

    def test_wrapper_gives_text_and_typed_signature(self):
        c = "int a;\nstatic inline __attribute__((always_inline)) void swoosh_veh(struct Thing *p_vehicle)\n{\n    asm volatile (\"call swoosh_veh\");\n}\nint b;\n"
        text, signature = find_wrapper(c, "swoosh_veh")
        self.assertEqual(signature, "void swoosh_veh(struct Thing *p_vehicle)")
        self.assertTrue(text.endswith("}\n"))
        self.assertIsNone(find_wrapper(c, "other"))

    def test_stub_follows_the_signature(self):
        self.assertEqual(stub_from_declaration("int f(int a1);"), "int f(int a1)\n{\n    return 0;\n}")
        self.assertEqual(stub_from_declaration("void g(int a1);"), "void g(int a1)\n{\n}")

    def test_nearest_file_skips_other_local_targets(self):
        known = [{"asm_start_line": 100, "c_file": "a.c"}, {"asm_start_line": 900, "c_file": "b.c"},
                 {"asm_start_line": 880, "c_file": "c.c", "local": True}]
        self.assertEqual(nearest_c_file(850, known), "b.c")
        self.assertIsNone(nearest_c_file(1, []))

    def test_target_has_the_alias_in_its_code(self):
        target = make_target("tank_los", "int tank_los(int a1);", self.lines, "src/people.c", (2, 6), ["#include \"x.h\""])
        self.assertTrue(target["asm_code"].startswith("GLOBAL_FUNC(ASM_tank_los)\n"))
        self.assertEqual(target["asm_line_count"], 4)
        self.assertTrue(target["local"])


if __name__ == "__main__":
    unittest.main()
