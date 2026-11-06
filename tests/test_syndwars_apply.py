# SPDX-License-Identifier: Apache-2.0
import pytest

from scripts.syndwars_apply import add_includes, choose, forward_structs, reconcile_declarations, redirect_asm_calls, remove_adapter, replace_stub, split_compat, wrapper_line

CODE = """#ifndef GHIDRA_COMPAT_H
#define GHIDRA_COMPAT_H
#ifndef bool
#define bool _Bool
#endif
typedef int int4;
#endif
void other(int a);
void f(void) { other(1); }
"""


def test_split_compat_handles_nested_conditionals():
    block, rest = split_compat(CODE)
    assert block.count("#endif") == 2 and "typedef int int4;" in block
    assert rest.strip().startswith("void other") and "GHIDRA" not in rest


def test_split_compat_without_block_returns_code():
    assert split_compat("void f(void) {}") == ("", "void f(void) {}")


def test_choose_takes_agree_and_manual_minus_excluded():
    results = [{"func": "a", "verdict": "agree"}, {"func": "b", "verdict": "mismatch"},
               {"func": "c", "verdict": "unsupported_calls"}, {"func": "d", "verdict": "agree"}]
    assert choose(results, ["c"], ["d"]) == ["a", "c"]


def test_replace_stub_requires_the_stub():
    assert replace_stub("x STUB y STUB", "STUB", "NEW") == "x NEW y STUB"
    with pytest.raises(KeyError):
        replace_stub("nothing", "STUB", "NEW")


def test_add_includes_is_idempotent():
    once = add_includes("int a;\n")
    assert once.startswith('#include "drafts_link.h"') and add_includes(once) == once


def test_wrapper_line_from_inferred_signature():
    assert wrapper_line("int tank_los(int a1, int a2, int a3, int a4);") == "tank_los\t\t\tW\ti\tiiii"
    assert wrapper_line("void f(void);") == "f\t\t\tW\tv"
    assert wrapper_line("") is None


def test_redirect_calls_and_jumps_but_not_the_tail():
    sx = "foo:\n\tret\n\tcall   foo\n\tjmp    foo\n\tcall   foo2\n/* Collegamento delle bozze */\nfoo__c:\n\tcall   foo\n"
    text, count, others = redirect_asm_calls(sx, "foo")
    assert count == 2 and others == []
    assert "\tcall   ac_foo\n\tjmp    ac_foo\n\tcall   foo2\n" in text
    assert text.endswith("foo__c:\n\tcall   foo\n")


def test_address_of_a_function_cannot_be_redirected():
    _text, _count, others = redirect_asm_calls("foo:\n\tmov    $foo,%eax\n", "foo")
    assert others == ["mov    $foo,%eax"]


def test_remove_adapter_leaves_the_others():
    tail = "\t.global foo__c\nfoo__c:\n\tcall   foo\n\tret\n\t.global bar__c\nbar__c:\n\tcall   bar\n\tret\n"
    assert remove_adapter(tail, "foo") == "\t.global bar__c\nbar__c:\n\tcall   bar\n\tret\n"


def test_reconcile_removes_only_conflicting_empty_declarations():
    text = "ubyte next(struct Thing *p);\nint next();\nint other();\nint other(int a);\n"
    assert reconcile_declarations(text) == "ubyte next(struct Thing *p);\nint other();\nint other(int a);\n"


def test_forward_structs_lists_each_struct_once():
    assert forward_structs(["void f(struct Path *p);", "void g(struct Path *p, struct Thing *t);"]) == "struct Path;\nstruct Thing;\n"
