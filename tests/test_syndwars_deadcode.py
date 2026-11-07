# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import unittest

from scripts.syndwars_deadcode import analyse, filter_tail, reachable, split_blocks, strip_disabled

SEP = "/*----------------------------------------------------------------"


def fn(name, *body, is_global=False):
    head = f"GLOBAL_FUNC({name})" if is_global else f"{name}:"
    return [SEP, head, SEP, *body]


def source(*chunks):
    return "\n".join(line for chunk in chunks for line in chunk)


class DeadCodeTest(unittest.TestCase):
    def test_reachability_follows_calls_and_ignores_unused(self):
        text = source(fn("ASM_used", "\tcall   helper", "\tret", is_global=True), fn("helper", "\tret"), fn("orphan", "\tcall   helper2", "\tret"), fn("helper2", "\tret"))
        result = analyse(text, {"ASM_used"})
        self.assertEqual(result["dead"], ["helper2", "orphan"])
        self.assertIn("#if 0", result["text"])

    def test_fallthrough_keeps_the_next_block(self):
        text = source(fn("start", "\tmov    %eax,%ebx", is_global=True), fn("next_block", "\tret"), fn("other", "\tret"))
        self.assertEqual(analyse(text, {"start"})["dead"], ["other"])

    def test_jump_does_not_fall_through(self):
        text = source(fn("start", "\tjmp    far_away", is_global=True), fn("skipped", "\tret"), fn("far_away", "\tret"))
        self.assertEqual(analyse(text, {"start"})["dead"], ["skipped"])

    def test_data_sections_are_roots(self):
        text = source(fn("alone", "\tret"), [".data", "table:", "\t.long  alone"], [".text"])
        self.assertEqual(analyse(text, set())["dead"], [])

    def test_retired_code_is_not_a_caller(self):
        text = source(["#if 0"], fn("old", "\tcall   helper", "\tret"), ["#endif"], fn("helper", "\tret"))
        self.assertEqual(analyse(text, set())["dead"], ["helper"])

    def test_conditional_code_is_kept(self):
        text = source(["#ifdef NET"], fn("netcode", "\tcall   helper", "\tret"), ["#endif"], fn("helper", "\tret"))
        self.assertEqual(analyse(text, set())["dead"], [])

    def test_else_branch_of_if_zero_counts_as_active(self):
        text = source(["#if 0"], fn("off", "\tret"), ["#else"], fn("on", "\tcall   helper", "\tret"), ["#endif"], fn("helper", "\tret"))
        self.assertEqual(analyse(text, set())["dead"], [])

    def test_a_comment_is_not_a_reference(self):
        text = source(fn("start", "\tret\t/* helper */", is_global=True), fn("helper", "\tret"))
        self.assertEqual(analyse(text, {"start"})["dead"], ["helper"])

    def test_filter_tail_drops_adapters_nobody_uses(self):
        tail = ("/* Collegamento delle bozze */\n\t.text\n\t.global foo__c\nfoo__c:\n\tcall   foo\n\tret\n"
                "\t.global bar__c\nbar__c:\n\tcall   bar\n\tret\n\t.global some_data\n")
        out, kept, dropped = filter_tail(tail, {"foo"})
        self.assertEqual((kept, dropped), (["foo"], ["bar"]))
        self.assertIn("foo__c:", out)
        self.assertNotIn("bar__c:", out)
        self.assertIn(".global some_data", out)

    def test_tail_keeps_its_targets_alive(self):
        text = source(fn("foo", "\tret"), fn("bar", "\tret")) + "\n/* Collegamento delle bozze */\n\t.global foo__c\nfoo__c:\n\tcall   foo\n\tret\n\t.global bar__c\nbar__c:\n\tcall   bar\n\tret\n"
        result = analyse(text, {"foo"})
        self.assertEqual(result["dead"], ["bar"])
        self.assertNotIn("bar__c:", result["text"])
        self.assertIn("foo__c:", result["text"])

    def test_local_label_named_like_a_c_function_is_not_a_root(self):
        text = source(fn("same_name", "\tret"), fn("exported", "\tret", is_global=True))
        self.assertEqual(analyse(text, {"same_name", "exported"})["dead"], ["same_name"])

    def test_empty_root_and_data_do_not_keep_the_next_block(self):
        text = source(["#ifdef X", "# define Y(s) \\", "  s ##:", "#endif"], fn("first", "\tret"), fn("table", "\t.long  0"), fn("after_table", "\tret"), fn("user", "\tmov    table,%eax", "\tret", is_global=True))
        self.assertEqual(analyse(text, {"user"})["dead"], ["after_table", "first"])

    def test_disabled_c_code_is_not_a_reference(self):
        text = "int f(void)\n{\n#if 0\n    asm(\"call ASM_old\");\n#else\n    g();\n#endif\n#ifdef X\n    h();\n#endif\n}"
        kept = strip_disabled(text)
        self.assertNotIn("ASM_old", kept)
        self.assertIn("g();", kept)
        self.assertIn("h();", kept)

    def test_blocks_keep_labels_inside_the_function(self):
        blocks = split_blocks(source(fn("start", "inner:", "\tjmp    inner")).split("\n"))
        self.assertEqual(blocks[0].labels, {"start", "inner"})
        self.assertEqual(reachable(blocks, {"inner"}), {0})


if __name__ == "__main__":
    unittest.main()
