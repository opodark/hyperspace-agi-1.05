# SPDX-License-Identifier: Apache-2.0
import pytest

from scripts.syndwars_cleanup import PROMPT, describe_failure, readability, split_draft, visible_declarations

DRAFT = """#ifndef GHIDRA_COMPAT_H
#define X 1
#endif
void other(int a);
extern int word_1;
void target(struct Thing *p_thing, short x)
{
  int iVar1;
  iVar1 = *(int *)((long)p_thing + 4);
  other(iVar1);
}
"""


def test_split_draft_separates_prefix_and_function():
    prefix, code = split_draft(DRAFT, "target")
    assert code.startswith("void target(") and code.endswith("}")
    assert "void other(int a);" in prefix and "iVar1" not in prefix


def test_split_draft_does_not_match_a_prototype():
    with pytest.raises(ValueError):
        split_draft("void target(int a);\n", "target")


def test_visible_declarations_skip_the_compat_block():
    prefix, _ = split_draft(DRAFT, "target")
    declarations = visible_declarations(prefix)
    assert "GHIDRA_COMPAT" not in declarations and "extern int word_1;" in declarations


def test_readability_counts_ghidra_leftovers():
    _, code = split_draft(DRAFT, "target")
    measure = readability(code)
    assert measure["nomi_ghidra"] == 3 and measure["cast_deref"] == 1 and measure["goto"] == 0


def test_prompt_formats_without_stray_braces():
    assert "CODE" in PROMPT.format(declarations="D", code="CODE", feedback="")


def test_failure_description_uses_first_mismatch():
    text = describe_failure({"verdict": "mismatch", "disagreed": 2, "mismatches": [{"args": ["0x1"], "return": ["0", "1"]}]})
    assert "0x1" in text and "2 test cases" in text
