# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import unittest

from scripts.syndwars_orchestrate import (
    UnsupportedFunction,
    assemble_function,
    build_call_expression,
    check_block,
    check_supported,
    clean_asm,
    extract_block_c,
    fold_high_word_loads,
    normalize_subregister_reads,
    parse_signature,
    split_blocks,
)

ASM = """GLOBAL_FUNC(ASM_f)	/* 0x1 */
/*----*/
		push   %esi
		testb  $0x2,0xc(%ebx)
		jne    jump_1
		mov    0x38(%ebx),%eax
		call   ac_collapse_building
	jump_1:
		pop    %esi
		ret

vtable_1:
		.long   func_1
"""


class OrchestrateTest(unittest.TestCase):
    def test_clean_asm_drops_prologue_epilogue_and_trailing_data(self):
        self.assertEqual(clean_asm(ASM), [
            "testb  $0x2,0xc(%ebx)", "jne    jump_1", "mov    0x38(%ebx),%eax",
            "call   ac_collapse_building", "jump_1:", "ret",
        ])

    def test_split_blocks_breaks_at_labels_and_jumps(self):
        self.assertEqual(split_blocks(clean_asm(ASM)), [
            ["testb  $0x2,0xc(%ebx)", "jne    jump_1"],
            ["mov    0x38(%ebx),%eax", "call   ac_collapse_building"],
            ["jump_1:", "ret"],
        ])

    def test_split_blocks_keeps_compare_with_jump_at_size_limit(self):
        lines = ["mov %eax,%ebx", "cmp $1,%eax", "je x"]
        self.assertEqual(split_blocks(lines, max_instructions=2), [lines])

    def test_check_block_requires_goto_call_and_label(self):
        self.assertIn("goto jump_1", check_block(["jne jump_1"], "if (eax) return;"))
        self.assertIn("collapse_building", check_block(["call ac_collapse_building"], "eax = 1;"))
        self.assertIn("label", check_block(["jump_1:", "ret"], "return;"))
        self.assertIsNone(check_block(["jne jump_1"], "if (eax) goto jump_1;"))

    def test_check_block_rejects_register_declarations(self):
        self.assertIn("declare", check_block(["mov %eax,%ebx"], "long ebx = eax;"))

    def test_call_expression_uses_watcall_order_and_casts(self):
        call, _ = build_call_expression("collapse_building", "void collapse_building(short x, short y, short z, struct Thing *p_building);")
        self.assertEqual(call, "collapse_building((short)eax, (short)edx, (short)ebx, (struct Thing *)ecx);")
        call, _ = build_call_expression("calc", "short calc(struct Thing *p);")
        self.assertEqual(call, "eax = (long)calc((struct Thing *)eax);")

    def test_check_block_rejects_invented_call_arguments(self):
        calls = {"foo": "foo((short)eax);"}
        self.assertIn("exactly", check_block(["call ac_foo"], "foo(bx);", calls))
        self.assertIsNone(check_block(["call ac_foo"], "foo((short)eax);", calls))

    def test_check_block_rejects_inverted_mask_jump(self):
        block = ["testb $0x2,0xc(%ebx)", "jne L"]
        self.assertIn("precedence", check_block(block, "if (!((struct Thing *)ebx)->Flag & 0x2) goto L;"))
        self.assertIn("ARE set", check_block(block, "if ((((struct Thing *)ebx)->Flag & 0x2) == 0) goto L;"))
        self.assertIsNone(check_block(block, "if ((((struct Thing *)ebx)->Flag & 0x2) != 0) goto L;"))

    def test_fold_high_word_load_across_unrelated_instruction(self):
        self.assertEqual(
            fold_high_word_loads(["mov    0x38(%ebx),%eax", "sar    $0x4,%edx", "sar    $0x10,%eax", "sub    %edx,%eax"]),
            ["movswl 0x3a(%ebx),%eax", "sar    $0x4,%edx", "sub    %edx,%eax"],
        )

    def test_fold_stops_when_register_is_used(self):
        lines = ["mov    0x38(%ebx),%eax", "mov    %eax,%edx", "sar    $0x10,%eax"]
        self.assertEqual(fold_high_word_loads(lines), lines)

    def test_check_block_rejects_mask_precedence_and_new_variables(self):
        self.assertIn("parentheses", check_block(["mov %eax,%ebx"], "if (x & 0x2 != 0) eax = 1;"))
        self.assertIn("declare", check_block(["mov %eax,%ebx"], "long health = 1;"))

    def test_subregister_reads_become_register_expressions(self):
        self.assertEqual(normalize_subregister_reads("p->Health = (short)ax;"), "p->Health = (short)((short)eax);")
        self.assertEqual(normalize_subregister_reads("edx = dl + ah;"), "edx = ((unsigned char)edx) + ((unsigned char)(eax >> 8));")
        self.assertEqual(normalize_subregister_reads("p->ax = 1; al = 2;"), "p->ax = 1; al = 2;")

    def test_subregister_assignments_keep_high_bits(self):
        self.assertEqual(normalize_subregister_reads("dx = 5;"), "edx = (edx & ~0xFFFFL) | ((5) & 0xFFFF);")
        self.assertEqual(normalize_subregister_reads("cl = ax;"), "ecx = (ecx & ~0xFFL) | ((((short)eax)) & 0xFF);")
        self.assertEqual(normalize_subregister_reads("ah = 1;"), "eax = (eax & ~0xFF00L) | (((1) & 0xFF) << 8);")

    def test_check_block_rejects_subregister_writes(self):
        self.assertIn("sub-registers", check_block(["mov %ebx,%eax"], "al = 2;"))

    def test_extract_block_uses_answer_after_think(self):
        text = "<think>```c\nbozza;\n```</think>\n```c\neax = 1;\n```"
        self.assertEqual(extract_block_c(text), "eax = 1;")

    def test_parse_signature(self):
        self.assertEqual(
            parse_signature("void f(int a, struct Thing *p_t)\n{\n}"),
            ("void", "f", [("int", "a"), ("struct Thing *", "p_t")]),
        )

    def test_check_supported_refuses_stack_use(self):
        with self.assertRaises(UnsupportedFunction):
            check_supported(["mov 0x4(%esp),%eax"], [])
        with self.assertRaises(UnsupportedFunction):
            check_supported([], [("int", n) for n in "abcde"])

    def test_assemble_initialises_only_used_registers(self):
        code = assemble_function("int f(int a, int b)\n{\n}", ["eax = eax + 1;"])
        self.assertIn("long eax = 0;", code)
        self.assertIn("eax = (long)a;", code)
        self.assertNotIn("edx", code)
        self.assertIn("return (int)eax;", code)


if __name__ == "__main__":
    unittest.main()
