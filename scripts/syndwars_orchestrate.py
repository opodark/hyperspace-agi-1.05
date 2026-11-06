#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Decompilazione a blocchi: l'assembly viene diviso ai salti e un modello traduce un blocco per volta.

I registri restano variabili C locali, cosi' ogni blocco si controlla da solo e la funzione
ricomposta si puo' confrontare riga per riga con l'originale. I risultati finiscono in
`data/nightly/syndwars_orchestrated/` e non nel dataset: vanno riletti prima.

Uso:
    .venv/bin/python scripts/syndwars_orchestrate.py do_shockwave_building
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.syndwars_decompile_sovereign import (
    PENDING_PATH,
    SWARS_DIR,
    _find_c_declaration,
    _project_include_dirs,
    check_translation_fidelity,
    collect_target_context,
    load_jsonl,
    replace_function_in_c_file,
    verify_c_file_with_clang,
)

OLLAMA_URL = os.getenv("SWARS_OLLAMA_URL", "http://127.0.0.1:21434").rstrip("/")
BLOCK_MODEL = os.getenv("SWARS_BLOCK_MODEL", "hf.co/mradermacher/Qwen3.5-9B-Coder-GGUF:Q4_K_M")
BLOCK_NUM_CTX = int(os.getenv("SWARS_BLOCK_NUM_CTX", "8192"))
BLOCK_NUM_PREDICT = int(os.getenv("SWARS_BLOCK_NUM_PREDICT", "3000"))
BLOCK_TIMEOUT_S = int(os.getenv("SWARS_BLOCK_TIMEOUT_S", "300"))
OUTPUT_DIR = ROOT / "data" / "nightly" / "syndwars_orchestrated"

WATCALL_REGISTERS = ("eax", "edx", "ebx", "ecx")
CONDITIONAL_JUMP = re.compile(r"^j(?!mp\b)[a-z]{1,4}$")


class UnsupportedFunction(Exception):
    pass


def clean_asm(asm_code: str) -> List[str]:
    """Istruzioni ed etichette della funzione, senza prologo, epilogo e dati dopo l'ultimo `ret`."""
    lines = []
    for raw in asm_code.splitlines():
        line = re.sub(r"/\*.*?\*/|#.*$", "", raw).strip()
        if line and not line.startswith("GLOBAL_FUNC"):
            lines.append(line)

    last_ret = max((i for i, l in enumerate(lines) if l.split()[0] == "ret"), default=len(lines) - 1)
    lines = lines[: last_ret + 1]

    start = 0
    while start < len(lines) and lines[start].split()[0] == "push":
        start += 1
    lines = lines[start:]
    end = len(lines) - 1
    while end > 0 and lines[end - 1].split()[0] == "pop":
        del lines[end - 1]
        end -= 1
    return lines


def fold_high_word_loads(lines: List[str]) -> List[str]:
    """`mov 0x38(%ebx),%eax` + `sar $0x10,%eax` legge il solo short a 0x3a: `movswl 0x3a(%ebx),%eax`."""
    result = list(lines)
    i = 0
    while i < len(result):
        m = re.match(r"mov\s+(0x[0-9a-fA-F]+|\d+)\((%e\w\w)\),%(e\w\w)$", result[i])
        if m:
            register = m.group(3)
            for j in range(i + 1, min(i + 4, len(result))):
                if re.match(rf"sar\s+\$0x10,%{register}$", result[j]):
                    result[i] = f"movswl {hex(int(m.group(1), 0) + 2)}({m.group(2)}),%{register}"
                    del result[j]
                    break
                low = register[1:]
                if re.search(rf"%(?:{register}|{low}|{low[0]}[lh])\b", result[j]) or result[j].endswith(":") or result[j].split()[0].startswith(("j", "call", "ret")):
                    break
        i += 1
    return result


def split_blocks(lines: List[str], max_instructions: int = 14) -> List[List[str]]:
    """Nuovo blocco a ogni etichetta e dopo ogni salto; `cmp` e `j<cc>` restano insieme."""
    blocks: List[List[str]] = []
    current: List[str] = []
    for line in lines:
        mnemonic = line.split()[0]
        if line.endswith(":") and current:
            blocks.append(current)
            current = []
        current.append(line)
        is_flag_setter = mnemonic.rstrip("bwl") in ("cmp", "test")
        if mnemonic == "jmp" or mnemonic == "ret" or CONDITIONAL_JUMP.match(mnemonic):
            blocks.append(current)
            current = []
        elif len(current) >= max_instructions and not is_flag_setter and mnemonic != "push":
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def parse_signature(stub: str) -> Tuple[str, str, List[Tuple[str, str]]]:
    head = stub.split("{")[0].strip()
    m = re.match(r"(.+?)\b(\w+)\s*\((.*)\)\s*$", head, re.DOTALL)
    if not m:
        raise UnsupportedFunction(f"firma non riconosciuta: {head}")
    params: List[Tuple[str, str]] = []
    for part in m.group(3).split(","):
        part = part.strip()
        if part and part != "void":
            pm = re.match(r"(.*?)(\w+)$", part, re.DOTALL)
            params.append((pm.group(1).strip(), pm.group(2)))
    return m.group(1).strip(), m.group(2), params


def check_supported(lines: List[str], params: List[Tuple[str, str]]) -> None:
    if len(params) > len(WATCALL_REGISTERS):
        raise UnsupportedFunction("argomenti sullo stack non ancora gestiti")
    if any("%esp" in line for line in lines):
        raise UnsupportedFunction("uso diretto dello stack non ancora gestito")


def jump_target(block: List[str]) -> Optional[str]:
    parts = block[-1].split()
    if len(parts) == 2 and (parts[0] == "jmp" or CONDITIONAL_JUMP.match(parts[0])):
        return parts[1]
    return None


def called_names(block: List[str]) -> List[str]:
    names = []
    for line in block:
        m = re.match(r"call\s+(?:ac_|ASM_)?(\w+)", line)
        if m:
            names.append(m.group(1))
    return names


def load_sources(c_rel_path: str) -> List[str]:
    sources = [p.read_text(encoding="utf-8", errors="replace") for d in _project_include_dirs(SWARS_DIR) if d.exists() for p in sorted(d.glob("*.h"))]
    c_path = SWARS_DIR / c_rel_path
    if c_path.exists():
        sources.append(c_path.read_text(encoding="utf-8", errors="replace"))
    return sources


def build_call_expression(name: str, declaration: str) -> Tuple[str, List[str]]:
    """Dal prototipo alla chiamata esatta: i primi 4 argomenti stanno in eax, edx, ebx, ecx."""
    m = re.match(r"(.*?)\b" + re.escape(name) + r"\s*\((.*)\)\s*;?$", declaration, re.DOTALL)
    if not m:
        return "", []
    return_type = m.group(1).replace("extern", "").strip()
    args: List[str] = []
    raw_params = [] if m.group(2).strip() in ("", "void") else [a.strip() for a in m.group(2).split(",")]
    for idx, param in enumerate(raw_params):
        pm = re.match(r"(.*?)(\w+)$", param, re.DOTALL)
        cast = pm.group(1).strip() if pm and pm.group(1).strip() else param
        source = WATCALL_REGISTERS[idx] if idx < len(WATCALL_REGISTERS) else f"PUSHED_{idx - len(WATCALL_REGISTERS) + 1}"
        args.append(f"({cast}){source}")
    call = f"{name}({', '.join(args)})"
    if return_type and return_type != "void":
        call = f"eax = (long){call}"
    return call + ";", args


def mask_jump_hint(block: List[str]) -> str:
    if len(block) < 2 or block[-2].split()[0].rstrip("bwl") != "test" or "$" not in block[-2]:
        return ""
    mask = block[-2].split()[1].split(",")[0].lstrip("$")
    target = block[-1].split()[-1]
    mnemonic = block[-1].split()[0]
    if mnemonic in ("jne", "jnz"):
        return f"The last line of your C must have the form: if ((VALUE & {mask}) != 0) goto {target};\n"
    if mnemonic in ("je", "jz"):
        return f"The last line of your C must have the form: if ((VALUE & {mask}) == 0) goto {target};\n"
    return ""


def build_block_prompt(block: List[str], context: str, entry: str, calls: Dict[str, str]) -> str:
    call_rules = "".join(f"- Write this call exactly: `{expr}`\n" for name, expr in calls.items() if name in called_names(block) and expr)
    return (
        "Translate this x86 block (AT&T syntax: source first, destination last) into C statements.\n"
        "Rules:\n"
        "- `eax edx ebx ecx esi edi ebp` are existing `long` C variables. Keep using them.\n"
        "- Access memory by casting: `((struct Thing *)ebx)->Flag`. Use only fields in the tables below; "
        "for an offset not listed use `*(short *)(ebx + 0x38)`.\n"
        "- `movswl` reads a signed 16-bit field: `eax = ((struct Thing *)ebx)->Health;` with no shift.\n"
        "- Sub-registers: `ax` is the low 16 bits of eax, `al`/`ah` its low bytes. Preserve the other bits.\n"
        "- `test $mask,x` + `jne L` is `if ((x & mask) != 0) goto L;`; with `je L` it is `if ((x & mask) == 0) goto L;`. "
        "`test %eax,%eax` + `jge L` is `if ((long)(int)eax >= 0) goto L;`. Keep the exact label name.\n"
        "- Assign every result back to its register; do not introduce other variables.\n"
        "- `call ac_foo` becomes `eax = (long)foo(...)` or `foo(...)`: arguments in order eax, edx, ebx, ecx, "
        "then pushed values, cast to the declared parameter types.\n"
        "- A label line stays as `label: ;`. No declarations of registers, no function wrapper, no comments.\n"
        "Reply with only one ```c block.\n\n"
        f"{context}\n\n"
        f"Registers at function entry: {entry}\n"
        f"{call_rules}\n"
        "Translate ONLY these instructions. Block:\n```asm\n" + "\n".join(block) + "\n```\n"
        + mask_jump_hint(block)
    )


def call_model(prompt: str, model: str = BLOCK_MODEL, temperature: float = 0.1) -> Dict[str, Any]:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"num_ctx": BLOCK_NUM_CTX, "num_predict": BLOCK_NUM_PREDICT, "temperature": temperature},
    }).encode("utf-8")
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=BLOCK_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_block_c(content: str) -> str:
    answer = content[content.rfind("</think>") + len("</think>"):] if "</think>" in content else content
    blocks = re.findall(r"```(?:c|C)?\s*\n(.*?)```", answer, flags=re.DOTALL)
    return blocks[-1].strip() if blocks else ""


SUB_REGISTER_READS = {
    **{r[1:]: f"((short){r})" for r in ("eax", "edx", "ebx", "ecx")},
    **{f"{r[1]}l": f"((unsigned char){r})" for r in ("eax", "edx", "ebx", "ecx")},
    **{f"{r[1]}h": f"((unsigned char)({r} >> 8))" for r in ("eax", "edx", "ebx", "ecx")},
}
_SUB_REGISTER_RE = re.compile(r"(?<![\w.>])(" + "|".join(SUB_REGISTER_READS) + r")\b(?!\s*(?:=(?!=)|[-+*/&|^]=|<<=|>>=|\+\+|--))")


def lower_subregister_assignments(c_code: str) -> str:
    """`dx = v;` scrive solo i bit bassi di edx, come fa la CPU; i bit alti restano."""
    def rewrite(m: "re.Match[str]") -> str:
        indent, sub_reg, value = m.group(1), m.group(2), m.group(3)
        if len(sub_reg) == 2 and sub_reg[1] == "x":
            full = f"e{sub_reg}"
            return f"{indent}{full} = ({full} & ~0xFFFFL) | (({value}) & 0xFFFF);"
        full = f"e{sub_reg[0]}x"
        if sub_reg[1] == "l":
            return f"{indent}{full} = ({full} & ~0xFFL) | (({value}) & 0xFF);"
        return f"{indent}{full} = ({full} & ~0xFF00L) | ((({value}) & 0xFF) << 8);"
    return re.sub(r"^(\s*)(ax|bx|cx|dx|[abcd][lh])\s*=(?!=)\s*([^;\n]+);", rewrite, c_code, flags=re.MULTILINE)


def normalize_subregister_reads(c_code: str) -> str:
    """Le letture di `ax`/`al`/`ah` diventano espressioni sul registro; le scritture restano da rifiutare."""
    return _SUB_REGISTER_RE.sub(lambda m: SUB_REGISTER_READS[m.group(1)], lower_subregister_assignments(c_code))


def jump_sense_error(block: List[str], c_code: str) -> Optional[str]:
    if len(block) < 2 or block[-2].split()[0].rstrip("bwl") != "test" or "$" not in block[-2]:
        return None
    mnemonic = block[-1].split()[0]
    negated = bool(re.search(r"==\s*0|if\s*\(\s*!", c_code))
    if mnemonic in ("jne", "jnz") and negated:
        return "`jne` after `test $mask` jumps when the bits ARE set: use `(x & mask) != 0`."
    if mnemonic in ("je", "jz") and not negated:
        return "`je` after `test $mask` jumps when the bits are NOT set: use `(x & mask) == 0`."
    return None


def check_block(block: List[str], c_code: str, calls: Optional[Dict[str, str]] = None) -> Optional[str]:
    if not c_code:
        return "No ```c block in the reply."
    if re.search(r"(?<![\w.>])(?:ax|bx|cx|dx|[abcd][lh])\s*(?:=(?!=)|[-+*/&|^]=)", c_code):
        return "Do not assign to sub-registers: write `eax = (eax & 0xFFFF0000) | (value & 0xFFFF);` and similar."
    if re.search(r"\b(long|int)\s+(eax|edx|ebx|ecx|esi|edi|ebp)\b", c_code):
        return "Do not declare the registers: they already exist."
    if re.search(r"!\s*\(\(struct\s+\w+\s*\*\)\w+\)->[\w.]+\s*&", c_code):
        return "Wrong precedence: write `(x & mask) != 0` or `(x & mask) == 0`, never `!x & mask`."
    if re.search(r"&\s*(?:0x[0-9a-fA-F]+|\d+)\s*(?:!=|==)", c_code):
        return "Wrong precedence: put parentheses around the mask, `(x & mask) != 0`."
    declared = re.search(r"^\s*(?:(?:unsigned|signed|const)\s+)*(?:long|int|short|char|ubyte|ushort|ulong|sbyte|u8|s8|u16|s16|u32|s32)\s+\*?\w+\s*[=;,]", c_code, re.MULTILINE)
    if declared:
        return "Do not declare variables: assign only to the registers eax edx ebx ecx esi edi ebp."
    target = jump_target(block)
    sense = jump_sense_error(block, c_code)
    if sense:
        return sense
    if target and not re.search(rf"\bgoto\s+{re.escape(target)}\s*;", c_code):
        return f"The block must jump with `goto {target};`."
    if block[0].endswith(":") and not re.search(rf"^\s*{re.escape(block[0][:-1])}\s*:", c_code, re.MULTILINE):
        return f"The block must start with the label `{block[0][:-1]}: ;`."
    for name in called_names(block):
        if not re.search(rf"\b{re.escape(name)}\s*\(", c_code):
            return f"The block must call `{name}`."
        expected = (calls or {}).get(name)
        if expected and re.sub(r"\s+", "", expected.replace("PUSHED_", "")) not in re.sub(r"\s+", "", re.sub(r"PUSHED_", "", c_code)) and "PUSHED_" not in expected:
            return f"Write the call exactly as: `{expected}`"
    return None


def assemble_function(stub: str, block_codes: List[str], declarations: Optional[List[str]] = None) -> str:
    return_type, name, params = parse_signature(stub)
    signature = stub.split("{")[0].strip()
    used = [r for r in ("eax", "edx", "ebx", "ecx", "esi", "edi", "ebp") if any(re.search(rf"\b{r}\b", c) for c in block_codes)]
    body = [f"    long {r} = 0;" for r in used]
    for register, (_type, param) in zip(WATCALL_REGISTERS, params):
        if register in used:
            body.append(f"    {register} = (long){param};")
    body.extend(block_codes)
    if return_type != "void":
        body.append(f"    return ({return_type})eax;")
    prefix = "".join(d + "\n" for d in (declarations or []))
    return prefix + signature + "\n{\n" + "\n".join(body) + "\n}"


def translate_function(target: Dict[str, Any], model: str = BLOCK_MODEL, retries: int = 4) -> Dict[str, Any]:
    stub = target["current_c_stub"]
    _rt, _name, params = parse_signature(stub)
    lines = fold_high_word_loads(clean_asm(target["asm_code"]))
    check_supported(lines, params)
    blocks = split_blocks(lines)
    context = collect_target_context(SWARS_DIR, target)
    entry = ", ".join(f"{r}={p[1]}" for r, p in zip(WATCALL_REGISTERS, params)) or "(no arguments)"
    sources = load_sources(target["c_file"])
    names = list(dict.fromkeys(n for b in blocks for n in called_names(b)))
    found = {n: _find_c_declaration(n, sources) for n in names}
    calls = {n: build_call_expression(n, d)[0] for n, d in found.items() if d}
    declarations = [d for d in found.values() if d]

    report: List[Dict[str, Any]] = []
    codes: List[str] = []
    for idx, block in enumerate(blocks):
        if block == ["ret"]:
            continue
        prompt = build_block_prompt(block, context, entry, calls)
        code, error = "", "not attempted"
        for attempt in range(retries + 1):
            data = call_model(prompt, model, temperature=min(0.7, 0.1 + 0.2 * attempt))
            content = data.get("message", {}).get("content", "")
            code = normalize_subregister_reads(extract_block_c(content))
            error = check_block(block, code, calls)
            print(f"[BLOCCO {idx + 1}/{len(blocks)}] tentativo {attempt + 1}: {error or 'ok'} ({data.get('eval_count')} token)", flush=True)
            report.append({"block": idx, "attempt": attempt + 1, "asm": block, "c": code, "error": error,
                           "eval_count": data.get("eval_count"), "raw": content})
            if not error:
                break
            prompt += f"\nYour previous reply was rejected: {error}\nPrevious reply:\n{content[-1500:]}\n"
        if error:
            return {"status": "block_failed", "block": idx, "error": error, "report": report}
        codes.append(code)

    function_c = assemble_function(stub, codes, declarations)
    fidelity = check_translation_fidelity(target["asm_code"], function_c, target["asm_line_count"])
    original = (SWARS_DIR / target["c_file"]).read_text(encoding="utf-8", errors="replace")
    patched = replace_function_in_c_file(original, stub, function_c)
    clang_ok, diagnostics = verify_c_file_with_clang(SWARS_DIR, target["c_file"], patched) if patched else (False, "stub not found")
    return {"status": "assembled", "clang_ok": clang_ok, "diagnostics": diagnostics[:1500], "fidelity": fidelity,
            "function_c": function_c, "report": report}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("functions", nargs="+")
    parser.add_argument("--model", default=BLOCK_MODEL)
    args = parser.parse_args()
    targets = {t["func_name"]: t for t in load_jsonl(PENDING_PATH)}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in args.functions:
        print(f"=== {name} ({args.model})", flush=True)
        (OUTPUT_DIR / f"{name}.c").unlink(missing_ok=True)
        try:
            result = translate_function(targets[name], args.model)
        except (UnsupportedFunction, urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"RISULTATO {name}: errore {exc}", flush=True)
            continue
        (OUTPUT_DIR / f"{name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        if result["status"] == "assembled":
            (OUTPUT_DIR / f"{name}.c").write_text(result["function_c"] + "\n", encoding="utf-8")
        print(f"RISULTATO {name}: {result['status']} clang_ok={result.get('clang_ok')} "
              f"fidelity={result.get('fidelity')} {result.get('error', '')}", flush=True)
        if result.get("diagnostics"):
            print(result["diagnostics"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
