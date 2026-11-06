#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Test per l'estrattore del Golden Dataset e il motore di decompilazione SyndWarsFX."""

from __future__ import annotations

import unittest
from scripts.extract_decompilation_dataset import split_active_and_disabled_c
from scripts.syndwars_decompile_sovereign import (
    check_translation_fidelity,
    extract_asm_memory_offsets,
    extract_asm_symbols,
    parse_record_layouts,
    extract_c_function_from_response,
    replace_function_in_c_file,
)


class TestSyndwarsDecompilePipeline(unittest.TestCase):
    def test_split_active_and_disabled_c_with_else(self):
        sample = (
            "void matrix_identity_fill(struct M33 *p_mat)\n"
            "{\n"
            "#if 0\n"
            '    asm volatile ("call ASM_matrix_identity_fill\\n");\n'
            "#else\n"
            "    p_mat->R[0][0] = 0x4000;\n"
            "#endif\n"
            "}"
        )
        active, disabled = split_active_and_disabled_c(sample)
        self.assertIn("p_mat->R[0][0] = 0x4000;", active)
        self.assertNotIn("ASM_matrix_identity_fill", active)
        self.assertIn("ASM_matrix_identity_fill", disabled)

    def test_split_active_and_disabled_c_active_asm_with_draft(self):
        sample = (
            "int alt_at_point(int x, int z)\n"
            "{\n"
            "#if 0\n"
            "    int alt = compute_alt(x, z);\n"
            "    return alt;\n"
            "#endif\n"
            '    asm volatile ("call ASM_alt_at_point\\n");\n'
            "}"
        )
        active, disabled = split_active_and_disabled_c(sample)
        self.assertIn("ASM_alt_at_point", active)
        self.assertIn("compute_alt(x, z)", disabled)

    def test_extract_c_function_from_response(self):
        resp = (
            "<think>\nMapping %eax to p_person.\n</think>\n"
            "```c\n"
            "void person_intel(struct Thing *p_person)\n"
            "{\n"
            "    p_person->State = 0;\n"
            "}\n"
            "```"
        )
        cot, code = extract_c_function_from_response(resp, "person_intel")
        self.assertIn("Mapping %eax", cot)
        self.assertIn("void person_intel", code)
        self.assertIn("p_person->State = 0;", code)

    def test_replace_function_in_c_file(self):
        orig = "int a = 1;\nvoid foo(void)\n{\n    ASM_foo();\n}\nint b = 2;\n"
        stub = "void foo(void)\n{\n    ASM_foo();\n}"
        new_fn = "void foo(void)\n{\n    return;\n}"
        patched = replace_function_in_c_file(orig, stub, new_fn)
        self.assertIsNotNone(patched)
        self.assertIn("return;", patched)
        self.assertNotIn("ASM_foo", patched)

    def test_extract_prefers_final_answer_over_draft_in_reasoning(self):
        resp = (
            "<think>\n```c\nvoid f(void) { /* bozza */ }\n```\n</think>\n\n"
            "```c\nvoid f(void) { g(); }\n```\n"
        )
        self.assertIn("g();", extract_c_function_from_response(resp, "f")[1])

    def test_extract_falls_back_to_reasoning_when_answer_has_no_code(self):
        resp = "<think>\n```c\nvoid f(void) { /* bozza */ }\n```\n</think>\n\nNo code."
        self.assertIn("bozza", extract_c_function_from_response(resp, "f")[1])

    def test_fidelity_rejects_stub_that_compiles(self):
        asm = "\n".join(["mov %eax,%esi"] * 170 + ["jne a", "jge b", "je c"])
        self.assertIn("too short", check_translation_fidelity(asm, "int f(int x)\n{\n    int a = x & 3;\n    return 0;\n}", 173))

    def test_fidelity_rejects_placeholder_comment(self):
        code = "int f(void) {\n  // Placeholder logic: return 0\n  return 0;\n}"
        self.assertIn("placeholder", check_translation_fidelity("mov %eax,%esi\n", code, 5))

    def test_fidelity_requires_asm_calls_in_c(self):
        asm = "call ac_plant_mine\ncall calc_person_speed\n"
        self.assertIn("plant_mine", check_translation_fidelity(asm, "void f(void) { calc_person_speed(0); }", 5))
        self.assertIsNone(check_translation_fidelity(asm, "void f(void) { plant_mine(0); calc_person_speed(0); }", 5))

    def test_fidelity_requires_writes_when_asm_writes(self):
        asm = "mov %ax,0x24(%esi)\nmovw $0x32,0x68(%esi)\n"
        self.assertIn("writes to memory", check_translation_fidelity(asm, "void f(struct T *p) { int a = p->x; }", 5))
        self.assertIsNone(check_translation_fidelity(asm, "void f(struct T *p) { p->x = 1; }", 5))

    def test_asm_offsets_follow_sar_high_word(self):
        offsets = extract_asm_memory_offsets("mov    0x9c(%esi),%edx\nsar    $0x10,%edx\nmov    0xc(%eax),%ebx\n")
        self.assertTrue(offsets[0x9e])
        self.assertNotIn(0x9c, offsets)
        self.assertFalse(offsets[0xc])

    def test_asm_symbols_strip_call_prefixes(self):
        calls, globals_used = extract_asm_symbols("call ac_plant_mine\ncall foo\nmov EXPORT_SYMBOL(frame),%edx\n")
        self.assertEqual(calls, ["plant_mine", "foo"])
        self.assertEqual(globals_used, ["frame"])

    def test_parse_record_layouts_keeps_nested_leaf_paths(self):
        dump = (
            "*** Dumping AST Record Layout\n"
            "         0 | struct T\n"
            "         0 |   short A\n"
            "         2 |   union T::(unnamed at x.h:1:1) U\n"
            "         2 |     struct P P\n"
            "         2 |       ubyte B\n"
            "         3 |       ubyte C\n"
            "           | [sizeof=4, align=1]\n"
        )
        layout = parse_record_layouts(dump)["T"]
        self.assertEqual([(o, s, f) for o, s, _t, f in layout], [(0, 2, "A"), (2, 1, "U.P.B"), (3, 1, "U.P.C")])

    def test_export_marks_how_a_function_was_verified(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest import mock

        from scripts import syndwars_decompile_sovereign as pipeline

        record = {"func_name": "f", "c_file": "src/f.c", "clang_verified": True, "verification": "execution_unicorn",
                  "lfm_approved": False, "asm_code": "ret", "reasoning_cot": "", "verified_c": "void f(void) {}"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cot, golden, sft = root / "cot.jsonl", root / "golden.jsonl", root / "sft.jsonl"
            cot.write_text(json.dumps(record) + "\n", encoding="utf-8")
            golden.write_text("", encoding="utf-8")
            with mock.patch.multiple(pipeline, COT_TRAIN_PATH=cot, GOLDEN_PATH=golden, SFT_EXPORT_PATH=sft):
                pipeline.export_sft_dataset()
            exported = json.loads(sft.read_text(encoding="utf-8"))
        self.assertEqual(exported["verification"], "execution_unicorn")
        self.assertFalse(exported["has_deep_cot"])
        self.assertNotIn("<think>", exported["messages"][2]["content"])


if __name__ == "__main__":
    unittest.main()
