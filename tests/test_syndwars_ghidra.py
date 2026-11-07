# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import unittest

from scripts.syndwars_ghidra import (
    apply_known_fields,
    apply_names,
    cast_call_arguments,
    clean_ghidra_c,
    fake_external_section,
    join_statements,
    _clean_declaration,
    cast_pointer_locals,
    declare_missing_globals,
    expand_ghidra_pieces,
    keep_unsigned_parameters,
    asm_call_targets,
    drop_debug_sprintf,
    make_compilable_draft,
    parse_inferred_signatures,
    parse_local_symbols,
    stack_args_from_assembly,
    list_local_names,
    parse_names_reply,
    parse_ghidra_output,
    resolve_data_addresses,
    rewrite_named_globals,
)

FIELDS = {"Thing": [
    (12, 4, "ulong", "Flag"), (40, 2, "short", "Timer1"), (58, 2, "short", "Health"), (68, 4, "u32", "Flag2"),
    (84, 2, "ushort", "U.UObject.Other"), (84, 2, "ushort", "U.UPerson.ComCur"),
]}
PARAMS = [("struct Thing *", "p_person")]


class GhidraPipelineTest(unittest.TestCase):
    def test_clean_removes_stack_noise_prefixes_and_types(self):
        code = clean_ghidra_c(
            "  puVar5 = &uStackY_20;\n  ac_plant_mine(p);\n  *(undefined2 *)(p + 1) = _frame;\n"
        )
        self.assertNotIn("puVar5", code)
        self.assertIn("plant_mine(p);", code)
        self.assertIn("*(short *)(p + 1) = frame;", code)

    def test_clean_restores_argument_passed_on_stack(self):
        code = clean_ghidra_c(
            "  puVar5 = &uStackY_20;\n"
            "  *(uint *)((int)puVar5 + 0xc) = (uint)*(byte *)(p + 0x9e);\n"
            "  puVar9 = (undefined1 *)((int)puVar5 + 8);\n"
            "  iVar3 = ac_create_item(1,2,3,0x3ec,\n"
            "                         *(undefined4 *)((int)puVar5 + 0xc));\n"
        )
        self.assertNotIn("puVar", code)
        self.assertIn("0x3ec,", code)
        self.assertIn("(u32)*(ubyte *)(p + 0x9e)", code)

    def test_clean_keeps_real_pointers_named_puvar(self):
        code = clean_ghidra_c("  puVar2 = table;\n  *puVar2 = 1;\n")
        self.assertIn("*puVar2 = 1;", code)

    def test_clean_does_not_treat_real_results_as_stack_noise(self):
        code = clean_ghidra_c("  puVar5 = &uStackY_20;\n  iVar3 = compute(puVar5);\n  iVar4 = iVar3 + 1;\n")
        self.assertIn("iVar4 = iVar3 + 1;", code)

    def test_named_globals_use_address_and_ghidra_width(self):
        self.assertEqual(rewrite_named_globals("x = _frame;", {"_frame": 4}), "x = (*(int *)&frame);")
        self.assertEqual(rewrite_named_globals("x = (int)head;", {"head": 2}), "x = (int)(*(short *)&head);")
        self.assertEqual(rewrite_named_globals("x = (uint)head;", {"head": 2}), "x = (uint)(*(ushort *)&head);")
        self.assertEqual(rewrite_named_globals("x = (&tbl)[i];", {"tbl": 4}), "x = ((int *)&tbl)[i];")
        self.assertEqual(rewrite_named_globals("p = &people_frames;", {"people_frames": 2}), "p = ((long)&people_frames);")
        self.assertEqual(rewrite_named_globals("x = (&follow_dist)[i];", {"follow_dist": 1}), "x = ((ubyte *)&follow_dist)[i];")

    def test_call_arguments_are_cast_to_pointer_parameters(self):
        decl = "void foo(struct M33 *p_mat, int n);"
        self.assertEqual(cast_call_arguments("foo(iVar1 + 4, g(1, 2));", "foo", decl), "foo((struct M33 *)(iVar1 + 4), g(1, 2));")

    def test_unsigned_ghidra_parameter_stays_unsigned_in_the_body(self):
        body = "{\n  if (x < 3) p->x = x;\n}"
        self.assertEqual(
            keep_unsigned_parameters("u32 f(u32 x, int y)", body, [("int", "x"), ("int", "y")]),
            "{\n  u32 x_u = (u32)x;\n  if (x_u < 3) p->x = x_u;\n}",
        )
        self.assertEqual(keep_unsigned_parameters("void f(int x)", body, [("int", "x")]), body)
        self.assertEqual(keep_unsigned_parameters("void f(u32 x)", body, [("ushort", "x")]), body)

    def test_stack_args_come_from_the_first_ret(self):
        source = "ASM_x:\\n".replace("\\n", "\n") + "  nop\n  ret $0x8\nGLOBAL_FUNC(ASM_y)\n  ret\n"
        self.assertEqual(stack_args_from_assembly("ASM_x", source), 2)
        self.assertEqual(stack_args_from_assembly("ASM_y", source), 0)
        self.assertIsNone(stack_args_from_assembly("ASM_z", source))

    def test_inferred_signatures_use_c_names(self):
        text = "//@@@INFER ac_foo 2 value\n//@@@INFER bar 0 void\n//@@@ ASM_f\nvoid f(void) {}\n"
        self.assertEqual(parse_inferred_signatures(text), {"foo": "int foo(int a1, int a2);", "bar": "void bar(void);"})

    def test_pieces_become_address_accesses(self):
        self.assertEqual(expand_ghidra_pieces("x = y._2_2_;"), "x = (*(ushort *)((long)&y + 2));")
        self.assertEqual(expand_ghidra_pieces("(*(int *)&d)._3_1_ = 1;"), "(*(ubyte *)((long)&(*(int *)&d) + 3)) = 1;")
        self.assertEqual(expand_ghidra_pieces("x = y._1_3_;"), "x = ((*(u32 *)((long)&y + 1)) & 0xFFFFFF);")

    def test_missing_globals_only_when_used_by_address(self):
        message = "use of undeclared identifier 'data_1'\nuse of undeclared identifier 'bVar2'"
        code = "void f(void)\n{ (*(int *)&data_1) = bVar2; }"
        self.assertEqual(declare_missing_globals(code, message, "void f(void)"), "extern int data_1;\n" + code)

    def test_inferred_call_is_declared_without_prototype(self):
        target = {"current_c_stub": "void f(void)\n{\n}", "asm_code": "call foo\n"}
        code = make_compilable_draft(target, "void f(void)\n{\n  foo(p);\n}", [], {"foo": "int foo(int a1);"})
        self.assertIn("int foo();", code)
        self.assertNotIn("int foo(int a1);", code)

    def test_debug_sprintf_is_dropped_only_when_nobody_reads_the_buffer(self):
        unused = "{\n  char local_c0[64];\n  sprintf((char *)(local_c0), (const char *)(x), 1);\n  g();\n}"
        self.assertEqual(drop_debug_sprintf(unused), "{\n  char local_c0[64];\n  g();\n}")
        used = "{\n  char local_c0[64];\n  sprintf((char *)(local_c0), (const char *)(x), 1);\n  g(local_c0);\n}"
        self.assertEqual(drop_debug_sprintf(used), used)

    def test_asm_call_targets_include_tail_calls_only(self):
        code = "func_a:\n\tcall   helper\n\tjmp    other_fn\n\tjmp    inner\ninner:\n\tret\t/* jmp commented */"
        self.assertEqual(asm_call_targets(code), ["helper", "other_fn"])

    def test_stub_with_inferred_signature_is_declared_without_prototype(self):
        target = {"current_c_stub": "void f(void)\n{\n}", "asm_code": "call foo\n"}
        code = make_compilable_draft(target, "void f(void)\n{\n  foo(&x);\n}", ["int foo(int a1)\n{\n    return 0;\n}\n"])
        self.assertIn("int foo();", code)

    def test_inferred_int_parameter_that_ghidra_sees_as_pointer(self):
        target = {"current_c_stub": "void f(int a1)\n{\n}", "asm_code": ""}
        body = make_compilable_draft(target, "void f(ubyte *a1)\n{\n  *a1 = a1[2];\n}", [])
        self.assertIn("void f(int a1)", body)
        self.assertEqual(body.count("((ubyte *)a1)"), 2)

    def test_pointer_locals_get_their_cast(self):
        body = "{\n  ubyte *p;\n  p = (long)&x + 1;\n}"
        self.assertEqual(cast_pointer_locals(body), "{\n  ubyte *p;\n  p = (ubyte *)((long)&x + 1);\n}")

    def test_internal_data_resolves_to_nearest_local_symbol(self):
        local = {"tbl": 0x6c000, "other": 0x6d000}
        self.assertEqual(resolve_data_addresses("x = DAT_0006ca84;", {}, {"DAT_0006ca84": 2}, local), "x = (*(ushort *)((long)&tbl + 0xa84));")
        self.assertEqual(resolve_data_addresses("x = ram0x0006c004;", {}, {"_DAT_0006c004": 4}, local), "x = (*(int *)((long)&tbl + 0x4));")
        self.assertEqual(resolve_data_addresses("x = DAT_00001000;", {}, {}, local), "x = DAT_00001000;")

    def test_array_field_is_not_read_as_a_number(self):
        fields = {"Thing": [(0x70, 4, "short[2]", "Timer")]}
        self.assertEqual(apply_known_fields("x = *(int *)(p + 0x70);", [("struct Thing *", "p")], fields), "x = *(int *)(p + 0x70);")

    def test_typed_pointer_after_a_cast_is_rewritten(self):
        target = {"current_c_stub": "void f(struct M *p)\n{\n}", "asm_code": ""}
        body = make_compilable_draft(target, "void f(ushort *p)\n{\n  *p = (ubyte)p[6];\n}", [])
        self.assertIn("*((ushort *)p) = (ubyte)((ushort *)p)[6];", body)

    def test_comma_assignment_to_pointer_local_gets_its_cast(self):
        body = "{\n  ushort *p;\n  while (p = x + 1, y < p) {\n  }\n}"
        self.assertIn("while (p = (ushort *)(x + 1), y < p)", cast_pointer_locals(body))

    def test_local_symbols_ignore_ghidra_names(self):
        self.assertEqual(parse_local_symbols("//@@@LOCAL tbl 5\n//@@@LOCAL DAT_1 6\n"), {"tbl": 5})

    def test_absolute_address_returns_to_its_symbol(self):
        symbols = {"text": 0x100000}
        self.assertEqual(resolve_data_addresses("*(byte *)(x + 0x100005) = 0;", symbols, {}), "*(byte *)(x + (int)((long)&text + 0x5)) = 0;")
        self.assertEqual(resolve_data_addresses("y = x & 0x100005;", symbols, {}), "y = x & 0x100005;")

    def test_address_plus_index_keeps_the_element_scale(self):
        self.assertEqual(rewrite_named_globals("x = *(byte *)(&tbl + n);", {"tbl": 4}), "x = *(byte *)(((int *)&tbl) + n);")
        self.assertEqual(rewrite_named_globals("x = (int)&tbl + n;", {"tbl": 4}), "x = (int)((long)&tbl) + n;")

    def test_wide_access_to_a_named_global(self):
        decompiled, _ = parse_ghidra_output("//@@@ ASM_f\n//@@@WIDE _head 4\nvoid f(void) {}\n")
        self.assertEqual(decompiled["f"]["global_sizes"], {"_head": 4})
        self.assertEqual(rewrite_named_globals("x = _head;", {"_head": 4}), "x = (*(int *)&head);")

    def test_typed_pointer_parameter_is_not_a_byte_offset(self):
        code = "void f(short *p_person)\n{\n  x = *(short *)(p_person + 0x28);\n}"
        self.assertEqual(apply_known_fields(code, PARAMS, FIELDS), code)

    def test_ghidra_piece_of_a_global(self):
        code = "void f(void)\n{ x = y_2 + (*(ushort *)&y); }"
        repaired = declare_missing_globals(code, "undeclared identifier 'y_2'", "void f(void)")
        self.assertIn("(*(ushort *)((long)&y + 2))", repaired)

    def test_declaration_drops_comments_and_inline(self):
        self.assertEqual(_clean_declaration("static inline void f(int a) // TODO\n;"), "void f(int a);")

    def test_typed_ghidra_pointer_keeps_its_scale(self):
        target = {"current_c_stub": "void f(struct M *p)\n{\n}", "asm_code": ""}
        body = make_compilable_draft(target, "void f(int *p)\n{\n  x = p[1];\n  y = *p;\n}", [])
        self.assertIn("x = ((int *)p)[1];", body)
        self.assertIn("y = *((int *)p);", body)

    def test_untyped_ghidra_pointer_stays_in_bytes(self):
        target = {"current_c_stub": "void f(struct M *p)\n{\n}", "asm_code": ""}
        body = make_compilable_draft(target, "void f(int p)\n{\n  x = (p - y) / 8;\n  z = p;\n}", [])
        self.assertIn("x = ((long)p - y) / 8;", body)
        self.assertIn("z = (long)p;", body)

    def test_resolve_data_addresses_maps_symbol_offset_and_width(self):
        symbols = {"players": 0x100000, "ingame": 0x110000}
        self.assertEqual(resolve_data_addresses("x = _DAT_001000ce;", symbols, {"_DAT_001000ce": 2}), "x = (*(ushort *)((long)&players + 0xce));")
        self.assertEqual(resolve_data_addresses("x = DAT_00110001;", symbols, {}), "x = (*(ubyte *)((long)&ingame + 0x1));")
        self.assertEqual(resolve_data_addresses("x = (&DAT_001000ce)[i];", symbols, {"DAT_001000ce": 4}), "x = ((int *)((long)&players + 0xce))[i];")
        self.assertEqual(resolve_data_addresses("x = (int)DAT_001000ce;", symbols, {"DAT_001000ce": 2}), "x = (int)(*(short *)((long)&players + 0xce));")
        self.assertEqual(resolve_data_addresses("p = &DAT_00110000;", symbols, {}), "p = ((long)&ingame);")

    def test_fake_section_leaves_called_symbols_external(self):
        text = fake_external_section(["things", "ac_foo", "bar"], ["bar"])
        self.assertIn(".global things", text)
        self.assertNotIn("ac_foo", text)
        self.assertNotIn(".global bar", text)

    def test_parse_output_separates_symbols_globals_and_code(self):
        decompiled, symbols = parse_ghidra_output("//@@@SYM things 4096\n//@@@ ASM_f\n//@@@GLOBAL _DAT_1 2\nvoid f(void) {}\n")
        self.assertEqual(symbols, {"things": 4096})
        self.assertEqual(decompiled["f"], {"code": "void f(void) {}", "global_sizes": {"_DAT_1": 2}})

    def test_join_statements_keeps_open_parentheses_together(self):
        self.assertEqual(join_statements("  a = f(1,\n     2);\n  b;"), ["  a = f(1, 2);", "  b;"])

    def test_clean_joins_call_split_across_lines(self):
        self.assertIn("collapse_building(1)", clean_ghidra_c("ac_collapse_building\n      (1);"))

    def test_field_read_keeps_the_sign_seen_in_the_assembly(self):
        self.assertEqual(apply_known_fields("x = *(ushort *)(p_person + 0x28);", PARAMS, FIELDS), "x = ((ushort)p_person->Timer1);")
        self.assertEqual(apply_known_fields("*(ushort *)(p_person + 0x28) = 1;", PARAMS, FIELDS), "p_person->Timer1 = 1;")
        self.assertEqual(apply_known_fields("x = *(ushort *)(p_person + 0x28) == 1;", PARAMS, FIELDS), "x = ((ushort)p_person->Timer1) == 1;")

    def test_pointer_field_arithmetic_stays_in_bytes(self):
        fields = {"Thing": [(0x74, 4, "struct Thing *", "PTarget")]}
        params = [("struct Thing *", "p")]
        self.assertEqual(apply_known_fields("x = *(int *)(p + 0x74) + 10;", params, fields), "x = ((long)p->PTarget) + 10;")
        self.assertEqual(apply_known_fields("*(int *)(p + 0x74) = 0;", params, fields), "p->PTarget = 0;")

    def test_fields_exact_high_word_and_byte_slice(self):
        self.assertEqual(apply_known_fields("*(short *)(p_person + 0x28)", PARAMS, FIELDS), "p_person->Timer1")
        self.assertEqual(apply_known_fields("*(int *)(p_person + 0x38) >> 0x10", PARAMS, FIELDS), "p_person->Health")
        self.assertEqual(apply_known_fields("*(ubyte *)(p_person + 0x46)", PARAMS, FIELDS), "(((ubyte *)&p_person->Flag2)[2])")

    def test_fields_prefer_person_union_member(self):
        self.assertEqual(apply_known_fields("*(ushort *)(p_person + 0x54)", PARAMS, FIELDS), "p_person->U.UPerson.ComCur")

    def test_fields_leave_untyped_pointers_to_the_model(self):
        self.assertEqual(apply_known_fields("*(short *)(iVar3 + 0x28)", PARAMS, FIELDS), "*(short *)(iVar3 + 0x28)")

    def test_names_reply_keeps_only_valid_new_identifiers(self):
        code = "int iVar1; int iVar2; int uVar3; int taken; goto x;"
        reply = '<think>x</think>{"iVar1": "tile_x", "iVar2": "taken", "uVar3": "goto", "ghost": "y"}'
        self.assertEqual(parse_names_reply(reply, ["iVar1", "iVar2", "uVar3"], code), {"iVar1": "tile_x"})
        self.assertEqual(parse_names_reply("nessun json", ["iVar1"], code), {})

    def test_names_reply_rejects_duplicates(self):
        self.assertEqual(parse_names_reply('{"iVar1": "a_b", "iVar2": "a_b"}', ["iVar1", "iVar2"], ""), {"iVar1": "a_b"})

    def test_apply_names_leaves_fields_and_longer_words_alone(self):
        self.assertEqual(apply_names("iVar1 = p->iVar1 + iVar10 + q.iVar1;", {"iVar1": "n"}), "n = p->iVar1 + iVar10 + q.iVar1;")

    def test_list_local_names_in_order_of_appearance(self):
        self.assertEqual(list_local_names("int uVar2; iVar1 = uVar2; unaff_EDI = iVar1;"), ["uVar2", "iVar1", "unaff_EDI"])


if __name__ == "__main__":
    unittest.main()


def test_mixed_16bit_equality_uses_the_same_sign_on_both_sides():
    from scripts.syndwars_ghidra import fix_mixed_16bit_equality as fix

    assert fix("if ((short)tngno != (*(ushort *)&head)) {") == "if ((short)tngno != (*(short *)&head)) {"
    assert fix("(*(ushort *)&head) == (short)x") == "(*(short *)&head) == (short)x"
    assert fix("y = (u32)(*(ushort *)&head);") == "y = (u32)(*(ushort *)&head);"
