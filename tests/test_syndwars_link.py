# SPDX-License-Identifier: Apache-2.0
from scripts.syndwars_link import (adapter, asm_only_callees, assembly_target, build_link_pack, parameter_count,
                                   prototype_from_drafts, undefined_symbols)

LOG = """x.o: in function `a':
x.c:(.text+0x1): undefined reference to `VNAV_goto'
y.c:(.text+0x2): undefined reference to `data_1770f5'
z.c:(.text+0x3): undefined reference to `VNAV_goto'
"""

SX = """GLOBAL_FUNC(ASM_find_target)
find_target:
\t\tret
VNAV_goto:\t/* 0x1 */
\t\tret $0x8
data_1770f5:
\t\t.byte 0
"""


def test_undefined_symbols_without_repeats():
    assert undefined_symbols(LOG) == ["VNAV_goto", "data_1770f5"]


def test_parameter_count():
    assert parameter_count("int f(void);") == 0
    assert parameter_count("int f();") == 0
    assert parameter_count("int f(int a1, int (*cb)(int, int), int a3);") == 3


def test_adapter_without_stack_arguments_loads_only_given_registers():
    text = adapter("f", "f", 2)
    assert "mov    20(%esp),%eax" in text and "mov    24(%esp),%edx" in text
    assert "%ebx" not in text.split("call")[0].split("mov    %esp,%ebp")[1]
    assert "pushl" not in text


def test_adapter_with_stack_arguments_repushes_in_order():
    text = adapter("g", "g", 6)  # quattro registri e due argomenti sullo stack
    assert text.count("pushl  40(%esp)") == 2  # 16 + 4*6
    assert "mov    28(%esp),%eax" in text  # 20 + 8 di argomenti ripetuti
    assert text.index("call   g") > text.index("mov    40(%esp),%ecx")
    assert "mov    %ebp,%esp" in text.split("call   g")[1]


def test_link_pack_separates_functions_data_and_unresolved():
    header, asm, unresolved = build_link_pack(
        ["VNAV_goto", "data_1770f5", "mancante", "senza_target"], [SX],
        ["void x(){ VNAV_goto(1,2); mancante(); }"],
        {"VNAV_goto": "int VNAV_goto(int a1, int a2);", "senza_target": "int senza_target(int a);"})
    assert "#define VNAV_goto VNAV_goto__c" in header
    assert "VNAV_goto__c:" in asm and "\t.global data_1770f5" in asm
    assert unresolved["senza_target"] == ["mancante", "senza_target"] or "senza_target" in unresolved["senza_target"]


def test_assembly_target_prefers_local_label_then_asm_prefix():
    assert assembly_target("VNAV_goto", [SX]) == "VNAV_goto"
    assert assembly_target("set_dist_volume", [SX, "GLOBAL_FUNC(ASM_set_dist_volume)\n"]) == "ASM_set_dist_volume"
    assert assembly_target("nulla", [SX]) is None


def test_asm_only_callee_without_c_definition_is_found():
    sx = "GLOBAL_FUNC(rotate_obj)\nGLOBAL_FUNC(gia_in_c)\nGLOBAL_FUNC(solo_asm2)\n"
    c = "static inline void rotate_obj(int a)\n{\n}\nvoid gia_in_c(int a)\n{\n}\n"
    draft = "void rotate_obj(int a, int b);\nvoid f(void){ rotate_obj(1,2); gia_in_c(3); if (x) CONCAT11(1,2); }"
    assert asm_only_callees([draft], [sx], [c]) == ["rotate_obj"]
    assert prototype_from_drafts("rotate_obj", [draft]) == "void rotate_obj(int a, int b);"
    assert parameter_count(prototype_from_drafts("rotate_obj", [draft])) == 2


def test_extend_adds_only_new_symbols():
    from scripts.syndwars_link import extend_link_pack
    header = "#ifndef G\n#define G\n#define old old__c\n#endif\n"
    sx = "new_fn:\n\tret\nold:\n\tret\ndata_1:\n\t.long 0\n/* Collegamento delle bozze */\n\t.global old__c\nold__c:\n\tcall   old\n\tret\n"
    out_header, out_sx, unresolved = extend_link_pack(header, sx, ["old", "new_fn", "data_1"], [sx], ["int new_fn();"], {"new_fn": "int new_fn(int a);", "old": "int old(int a);"})
    assert out_header.count("#define old old__c") == 1 and "#define new_fn new_fn__c\n#endif" in out_header
    assert out_sx.count("old__c:") == 1 and "new_fn__c:" in out_sx and "\t.global data_1" in out_sx
    assert not any(unresolved.values())
