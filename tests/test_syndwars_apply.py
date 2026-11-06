# SPDX-License-Identifier: Apache-2.0
import pytest

from scripts.syndwars_apply import add_includes, choose, replace_stub, split_compat

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
