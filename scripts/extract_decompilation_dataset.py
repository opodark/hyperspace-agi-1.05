#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Estrattore del Golden Dataset di Decompilazione (Watcom x86 ASM <-> C Portabile).

Scansiona il repository SyndWarsFX (`/Users/opo/syndwarsfx`) valutando le direttive
del preprocessore `#if 0 / #else / #endif` sia in `src/swars.sx` sia nei file `src/*.c`:
1. **Golden Pairs (`data/syndwars_golden_pairs.jsonl`)**: funzioni già convertite in C
   puro attivo (senza chiamate ASM attive), accoppiate 1:1 con il blocco assembly x86
   originale Watcom per il Fine-Tuning (QLoRA / MLX) e la distillazione CoT.
2. **Pending Targets (`data/syndwars_pending_targets.jsonl`)**: funzioni il cui ramo
   attivo C invoca ancora `ASM_<func>`, ordinate dando priorità a quelle che possiedono
   già una bozza C sotto `#if 0` e poi per lunghezza assembly crescente.

Uso:
    .venv/bin/python scripts/extract_decompilation_dataset.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SWARS_DIR = Path("/Users/opo/syndwarsfx")
DATA_DIR = ROOT / "data"
GOLDEN_OUT = DATA_DIR / "syndwars_golden_pairs.jsonl"
PENDING_OUT = DATA_DIR / "syndwars_pending_targets.jsonl"
SUMMARY_OUT = DATA_DIR / "syndwars_dataset_summary.json"


def split_active_and_disabled_c(block: str) -> Tuple[str, str]:
    """Separa le righe attive da quelle disattivate sotto #if 0 (gestendo #else)."""
    active_lines: List[str] = []
    disabled_lines: List[str] = []
    # Stack di stati booleani: True = ramo attivo, False = ramo disattivato (#if 0)
    stack: List[bool] = [True]

    for line in block.splitlines():
        s = line.strip()
        if s.startswith("#if"):
            if re.match(r"^#if\s+0\b", s):
                stack.append(False)
            else:
                stack.append(stack[-1])
            continue
        elif s.startswith("#else"):
            if len(stack) > 1:
                parent_active = stack[-2]
                stack[-1] = parent_active and (not stack[-1])
            continue
        elif s.startswith("#endif"):
            if len(stack) > 1:
                stack.pop()
            continue

        if stack[-1]:
            active_lines.append(line)
        else:
            disabled_lines.append(line)

    return "\n".join(active_lines), "\n".join(disabled_lines)


def extract_asm_functions(sx_path: Path) -> Dict[str, Dict[str, Any]]:
    """Estrae tutti i blocchi GLOBAL_FUNC(ASM_xxx) da src/swars.sx."""
    lines = sx_path.read_text(encoding="utf-8", errors="replace").splitlines()
    funcs: Dict[str, Dict[str, Any]] = {}

    if0_depth = 0
    i = 0
    n = len(lines)
    func_re = re.compile(r"^GLOBAL_FUNC\s*\(\s*ASM_([A-Za-z0-9_]+)\s*\)")
    end_re = re.compile(
        r"^(GLOBAL_FUNC\s*\(|GLOBAL\s*\(|#if\s+0|#endif|/\*---\s*End|#ifdef)"
    )

    while i < n:
        line = lines[i].strip()
        if re.match(r"^#if\s+0\b", line):
            if0_depth += 1
        elif line.startswith("#if"):
            if if0_depth > 0:
                if0_depth += 1
        elif line.startswith("#endif"):
            if if0_depth > 0:
                if0_depth -= 1

        m = func_re.match(line)
        if m:
            fname = m.group(1)
            start_line = i + 1
            retired = if0_depth > 0
            block_lines = [lines[i]]
            j = i + 1
            while j < n:
                sline = lines[j].strip()
                if j > i + 1 and end_re.match(sline):
                    break
                block_lines.append(lines[j])
                j += 1
            asm_text = "\n".join(block_lines).strip()
            funcs[fname] = {
                "func_name": fname,
                "start_line": start_line,
                "end_line": j,
                "line_count": len(block_lines),
                "retired_in_sx": retired,
                "asm_code": asm_text,
            }
            i = j
            continue
        i += 1

    return funcs


def extract_c_function_blocks(c_path: Path) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """Estrae gli include e i blocchi di funzione da un file .c valutando i rami #if 0."""
    text = c_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    includes = [ln.strip() for ln in lines if ln.strip().startswith("#include")]

    c_funcs: Dict[str, Dict[str, Any]] = {}
    n = len(lines)
    i = 0
    file_if0_depth = 0

    sig_re = re.compile(
        r"^(?:static\s+|inline\s+)*(?:struct\s+\w+\s*\*?\s*|[A-Za-z_][A-Za-z0-9_]*\s+\*?\s*)+"
        r"([A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*$"
    )

    while i < n:
        ln = lines[i]
        s = ln.strip()
        if re.match(r"^#if\s+0\b", s):
            file_if0_depth += 1
            i += 1
            continue
        elif s.startswith("#if"):
            if file_if0_depth > 0:
                file_if0_depth += 1
            i += 1
            continue
        elif s.startswith("#endif"):
            if file_if0_depth > 0:
                file_if0_depth -= 1
            i += 1
            continue

        if (
            file_if0_depth == 0
            and ln
            and not ln[0].isspace()
            and not ln.startswith("#")
            and not ln.startswith("//")
            and not ln.startswith("/*")
        ):
            m = sig_re.match(ln)
            if m:
                fname = m.group(1)
                if fname not in ("if", "while", "for", "switch", "return", "sizeof"):
                    k = i
                    found_brace = False
                    while k < min(i + 5, n):
                        if "{" in lines[k]:
                            found_brace = True
                            break
                        if ";" in lines[k]:
                            break
                        k += 1
                    if found_brace:
                        start_idx = i
                        end_idx = k
                        while end_idx < n:
                            if lines[end_idx].startswith("}"):
                                break
                            end_idx += 1
                        block = "\n".join(lines[start_idx : min(end_idx + 1, n)])
                        active_code, disabled_code = split_active_and_disabled_c(block)

                        # Verifica se il ramo ATTIVO chiama ASM_
                        calls_asm_actively = bool(
                            re.search(r"\bcall\s+ASM_" + re.escape(fname) + r"\b", active_code)
                            or re.search(r"\bASM_" + re.escape(fname) + r"\b", active_code)
                        )
                        # Verifica se nel ramo disattivato (#if 0) c'è una bozza C sostanziosa (non un semplice call ASM)
                        disabled_non_asm = re.sub(r'asm\s+volatile\s*\([^)]*\)\s*;', '', disabled_code)
                        has_c_draft = len(disabled_non_asm.strip()) > 35

                        c_funcs[fname] = {
                            "func_name": fname,
                            "c_file": f"src/{c_path.name}",
                            "start_line": start_idx + 1,
                            "end_line": end_idx + 1,
                            "calls_asm": calls_asm_actively,
                            "has_if0_draft": has_c_draft and calls_asm_actively,
                            "c_code": block,
                            "clean_active_c": active_code,
                            "disabled_c_draft": disabled_code.strip() if has_c_draft else "",
                            "includes": includes,
                        }
                        i = end_idx + 1
                        continue
        i += 1

    return includes, c_funcs


def build_datasets(swars_dir: Path) -> Dict[str, Any]:
    sx_path = swars_dir / "src" / "swars.sx"
    src_dir = swars_dir / "src"
    if not sx_path.exists():
        raise FileNotFoundError(f"File non trovato: {sx_path}")

    asm_funcs = extract_asm_functions(sx_path)

    all_c_funcs: Dict[str, Dict[str, Any]] = {}
    for c_file in sorted(src_dir.glob("*.c")):
        _, c_map = extract_c_function_blocks(c_file)
        for fname, info in c_map.items():
            if fname not in all_c_funcs or (not info["calls_asm"] and all_c_funcs[fname]["calls_asm"]):
                all_c_funcs[fname] = info

    golden_pairs: List[Dict[str, Any]] = []
    pending_targets: List[Dict[str, Any]] = []

    for fname, asm_info in sorted(asm_funcs.items()):
        c_info = all_c_funcs.get(fname)
        if c_info and not c_info["calls_asm"]:
            golden_pairs.append({
                "func_name": fname,
                "c_file": c_info["c_file"],
                "c_start_line": c_info["start_line"],
                "asm_start_line": asm_info["start_line"],
                "asm_line_count": asm_info["line_count"],
                "retired_in_sx": asm_info["retired_in_sx"],
                "includes": c_info["includes"],
                "asm_code": asm_info["asm_code"],
                "c_code": c_info["clean_active_c"],
                "instruction": (
                    f"Decompile the following 32-bit Watcom x86 assembly function `ASM_{fname}` "
                    f"from Syndicate Wars (`{c_info['c_file']}`) into clean, portable C code "
                    f"preserving exact struct offsets, register calling conventions (__watcall: "
                    f"eax, edx, ebx, ecx), and fixed-point arithmetic."
                ),
            })
        elif c_info and c_info["calls_asm"] and not asm_info["retired_in_sx"]:
            pending_targets.append({
                "func_name": fname,
                "c_file": c_info["c_file"],
                "c_start_line": c_info["start_line"],
                "c_end_line": c_info["end_line"],
                "asm_start_line": asm_info["start_line"],
                "asm_end_line": asm_info["end_line"],
                "asm_line_count": asm_info["line_count"],
                "has_if0_draft": c_info["has_if0_draft"],
                "c_draft": c_info["disabled_c_draft"],
                "includes": c_info["includes"],
                "asm_code": asm_info["asm_code"],
                "current_c_stub": c_info["c_code"],
            })

    pending_targets.sort(key=lambda x: (not x["has_if0_draft"], x["asm_line_count"], x["func_name"]))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(GOLDEN_OUT, "w", encoding="utf-8") as f:
        for item in golden_pairs:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    with open(PENDING_OUT, "w", encoding="utf-8") as f:
        for item in pending_targets:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    by_file: Dict[str, int] = {}
    drafts_count = 0
    for item in pending_targets:
        by_file[item["c_file"]] = by_file.get(item["c_file"], 0) + 1
        if item["has_if0_draft"]:
            drafts_count += 1

    summary = {
        "total_asm_global_funcs_in_sx": len(asm_funcs),
        "golden_verified_pairs_count": len(golden_pairs),
        "pending_c_targets_count": len(pending_targets),
        "pending_with_c_draft_count": drafts_count,
        "pending_by_file": dict(sorted(by_file.items(), key=lambda kv: -kv[1])),
        "golden_dataset_path": str(GOLDEN_OUT),
        "pending_targets_path": str(PENDING_OUT),
    }
    SUMMARY_OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Estrae il Golden Dataset ASM<->C da SyndWarsFX")
    parser.add_argument("--swars-dir", type=Path, default=DEFAULT_SWARS_DIR)
    args = parser.parse_args()

    summary = build_datasets(args.swars_dir)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
