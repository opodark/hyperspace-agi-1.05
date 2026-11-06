# SPDX-License-Identifier: Apache-2.0
from scripts.syndwars_retire import apply, function_regions, plan

SX = """/*----------------------------------------------------------------*/
GLOBAL_FUNC(ASM_dead)
/*----------------------------------------------------------------*/
\t\tcall   ac_other
\t\tret

/*----------------------------------------------------------------*/
GLOBAL_FUNC(ASM_caller)
/*----------------------------------------------------------------*/
\t\tcall   ASM_dead
\t\tret

/*----------------------------------------------------------------*/
GLOBAL_FUNC(ASM_shared)
/*----------------------------------------------------------------*/
\tjump_shared:
\t\tret

/*----------------------------------------------------------------*/
GLOBAL_FUNC(ASM_user)
/*----------------------------------------------------------------*/
\t\tjmp    jump_shared
"""


def files():
    return {"a.sx": SX.split("\n")}


def test_regions_start_at_the_separator():
    regions = function_regions(files()["a.sx"])
    assert set(regions) == {"ASM_dead", "ASM_caller", "ASM_shared", "ASM_user"}
    start, end = regions["ASM_dead"]
    assert files()["a.sx"][start].startswith("/*---")


def test_function_called_by_active_assembly_is_not_retired():
    retire, rejected = plan(files(), ["ASM_dead"])
    assert retire == {} and "ASM_caller" in rejected["ASM_dead"]


def test_function_called_only_by_retired_ones_is_retired():
    retire, rejected = plan(files(), ["ASM_dead", "ASM_caller"])
    assert set(retire) == {"ASM_dead", "ASM_caller"} and rejected == {}


def test_local_label_used_elsewhere_blocks_retirement():
    retire, rejected = plan(files(), ["ASM_shared"])
    assert retire == {} and "jump_shared" in rejected["ASM_shared"]


def test_apply_wraps_each_function_in_if0_and_keeps_balance():
    out = apply(files(), {"ASM_dead": "a.sx", "ASM_caller": "a.sx"})["a.sx"]
    text = "\n".join(out)
    assert text.count("#if 0") == 2 and text.count("#endif") == 2
    assert text.index("#if 0") < text.index("GLOBAL_FUNC(ASM_dead)") < text.index("#endif")
    assert "GLOBAL_FUNC(ASM_shared)" in text.split("#endif")[-1]
