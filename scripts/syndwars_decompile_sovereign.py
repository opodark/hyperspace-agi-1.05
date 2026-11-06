#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Motore Sovrano di Decompilazione & Distillazione Dataset (Flint 40B + LFM 2.5 24B).

Orchestra giorno e notte sui nodi della Mesh (HP OMEN 16 & ASUS) la traduzione
da assembly Watcom x86 32-bit (`src/swars.sx`) a C portabile nativo per Syndicate Wars,
con verifica deterministica tramite `clang` e generazione simultanea del dataset di
fine-tuning per il modello specialista `hyperspace-watcom-decompiler`.

Pipeline a 4 stadi per ogni funzione:
1. [Worker Primario - Flint 40B MoE (`flint:latest`)]:
   Analizza l'assembly `__watcall` (`%eax, %edx, %ebx, %ecx`), gli header C e 2 esempi
   Golden verificati dello stesso modulo, producendo `<think>` + implementazione C.
2. [Review Gate Contrattuale - Liquid AI LFM 2.5 24B]:
   Verifica vincoli negativi rigidi (zero stub, zero placeholder, corrispondenza
   aritmetica fixed-point e chiamate).
3. [Compiler Gate Deterministico - `clang -fsyntax-only`]:
   Compila il file `.c` completo con la funzione sostituita contro gli header reali di
   `syndwarsfx`. In caso di errore di compilazione, invia il diagnostico esatto di
   `clang` per auto-riparazione (fino a 2 tentativi).
4. [Persistenza Dataset & Staging]:
   Salva il campione verificato in formato SFT/QLoRA/MLX in
   `data/syndwars_decompilation_cot_train.jsonl` e lo stage in
   `data/syndwars_decompiled_staging/`. Con `--apply`, aggiorna il file `.c` e ritira
   il blocco `ASM_` in `src/swars.sx`.

Uso:
    .venv/bin/python scripts/syndwars_decompile_sovereign.py --once
    .venv/bin/python scripts/syndwars_decompile_sovereign.py --batch 10 --apply
    .venv/bin/python scripts/syndwars_decompile_sovereign.py --daemon --interval 15 --apply
    .venv/bin/python scripts/syndwars_decompile_sovereign.py --export-sft
"""

from __future__ import annotations

import argparse
import datetime
import functools
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.omen_allnight_sovereign import execute_omen_prompt, is_thermal_safe
from scripts.extract_decompilation_dataset import build_datasets
from shared.universal_model_parser import UniversalModelParser

SWARS_DIR = Path(os.getenv("SWARS_DIR", "/Users/opo/syndwarsfx"))
DATA_DIR = ROOT / "data"
GOLDEN_PATH = DATA_DIR / "syndwars_golden_pairs.jsonl"
PENDING_PATH = DATA_DIR / "syndwars_pending_targets.jsonl"
COT_TRAIN_PATH = DATA_DIR / "syndwars_decompilation_cot_train.jsonl"
SFT_EXPORT_PATH = DATA_DIR / "syndwars_watcom_decompiler_sft.jsonl"
STAGING_DIR = DATA_DIR / "syndwars_decompiled_staging"
STATE_PATH = DATA_DIR / "nightly" / "syndwars_decompile_state.json"
RAW_RESPONSES_PATH = DATA_DIR / "nightly" / "syndwars_raw_responses.jsonl"
NUM_CTX = int(os.getenv("SWARS_NUM_CTX", "16384"))
NUM_PREDICT = int(os.getenv("SWARS_NUM_PREDICT", "0")) or None
GENERATION_TIMEOUT_S = int(os.getenv("SWARS_TIMEOUT_S", "600"))

WORKER_MODEL = os.getenv("SWARS_WORKER_MODEL", "hf.co/DuoNeural/LFM2.5-8B-A1B-Abliterated-GGUF:Q4_K_M")
EXPERT_MODEL = os.getenv("SWARS_EXPERT_MODEL", "hf.co/Abiray/Qwen3.5-9B-abliterated-GGUF:Q6_K")
REVIEW_MODEL = os.getenv("SWARS_REVIEW_MODEL", WORKER_MODEL)

SYSTEM_PROMPT_DECOMPILER = (
    "You are the HyperSpace Watcom-to-C Decompilation Specialist. "
    "You translate 1996 Bullfrog 32-bit DOS/4GW Watcom x86 assembly (`__watcall` ABI: "
    "first 4 arguments in `%eax`, `%edx`, `%ebx`, `%ecx`; return value in `%eax`) "
    "into 100% clean, portable, compiler-verified C99 code for Syndicate Wars (`syndwarsfx`). "
    "Rules:\n"
    "1. Keep reasoning concise (max 15 lines mapping registers, struct offsets, and conditions).\n"
    "2. Output the complete C function inside a single ```c ... ``` block with the exact original C signature.\n"
    "3. Call helpers by their C name (`call ac_foo` is `foo(...)`), passing arguments as `%eax`, `%edx`, `%ebx`, `%ecx`, then the stack. Add an `extern` declaration only for symbols the context lists as undeclared. No `#include`. NEVER use C++ syntax like `extern \"C\"`.\n"
    "4. Translate x86 test/cmp instructions into standard C bitwise and relational checks (e.g. `testl $imm, 0xc(%eax)` becomes `(p_thing->Flag & imm)`). NEVER emit raw opcode names or pseudo-builtins like `__builtin_testhl`.\n"
    "5. NEVER emit inline assembly (`asm volatile`), `TODO`, placeholder ellipsis (`...`), or empty stubs. Output the complete, fully implemented body.\n"
    "6. NEVER redeclare globals or functions listed in the context. Use them directly.\n"
    "7. Use ONLY the field names in the offset tables. If a flag has no symbolic name in the context, use its numeric hex mask. Translate EVERY branch, call and memory write of the assembly."
)


def _log(tag: str, msg: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [SWARS-{tag}] {msg}", flush=True)


def ensure_bsndconf() -> None:
    """Garantisce che /tmp/bsndconf.h esista per i check sintattici clang di bfsoundlib."""
    p = Path("/tmp/bsndconf.h")
    if not p.exists():
        p.write_text("/* Auto-generated stub for clang syntax check */\n", encoding="utf-8")


def verify_c_file_with_clang(swars_dir: Path, c_rel_path: str, patched_content: str) -> Tuple[bool, str]:
    """Compila il contenuto patchato del file .c con clang -fsyntax-only."""
    ensure_bsndconf()
    c_orig = swars_dir / c_rel_path
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".c", dir=str(c_orig.parent), delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(patched_content)
        tmp_path = Path(tmp.name)

    try:
        cmd = [
            "clang",
            "-target", "x86_64-apple-darwin",
            "-fsyntax-only",
            "-w",
            "-std=gnu99",
            "-include", "string.h",  # Alcuni .c del gioco usano strlen e simili senza includerlo.
            "-DLB_HAVE_STDINT_H=1",
            "-DLBS_PACKAGE=1",
            "-DPACKAGE_NAME=\"syndwarsfx\"",
            "-DPACKAGE_VERSION=\"0.6\"",
            "-DVERSION=\"0.6\"",
            "-Wno-unused-value",
            "-Wno-unused-variable",
            "-Wno-parentheses",
            "-Wno-pointer-sign",
            f"-I{swars_dir / 'src'}",
            f"-I{swars_dir / 'bfariadne/include'}",
            f"-I{swars_dir / 'bflibrary/include'}",
            f"-I{swars_dir / 'bfsoundlib/include'}",
            f"-I{swars_dir / 'bfsmacklib/include'}",
            f"-I{swars_dir / 'swrendersoft/include'}",
            "-I/tmp",
            str(tmp_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        ok = res.returncode == 0
        diag = (res.stderr or res.stdout or "").strip()
        return ok, diag
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def select_few_shot_examples(
    golden_pairs: List[Dict[str, Any]], target_c_file: str, k: int = 2
) -> List[Dict[str, Any]]:
    """Seleziona k esempi Golden verificati preferendo lo stesso file .c e dimensione moderata."""
    same_file = [
        g for g in golden_pairs
        if g["c_file"] == target_c_file and 10 <= g["asm_line_count"] <= 140
    ]
    others = [
        g for g in golden_pairs
        if g["c_file"] != target_c_file and 15 <= g["asm_line_count"] <= 100
    ]
    pool = same_file + others
    return pool[:k]


_TYPE_SIZES = {
    "char": 1, "sbyte": 1, "ubyte": 1, "u8": 1, "s8": 1, "TbBool": 1,
    "short": 2, "ushort": 2, "u16": 2, "s16": 2, "ThingIdx": 2,
    "int": 4, "uint": 4, "long": 4, "ulong": 4, "s32": 4, "u32": 4, "float": 4,
}
_LAYOUT_LINE_RE = re.compile(r"^\s*(\d+)\s\|(\s+)(\S.*)$")


def _leaf_size(type_name: str) -> int:
    if "*" in type_name:
        return 4
    m = re.match(r"(.+?)\[(\d+)\]", type_name)
    if m:
        return _TYPE_SIZES.get(m.group(1).strip(), 1) * int(m.group(2))
    return _TYPE_SIZES.get(type_name.strip(), 4)


def parse_record_layouts(dump: str) -> Dict[str, List[Tuple[int, int, str, str]]]:
    """Da `-fdump-record-layouts` a {struct: [(offset, size, tipo, percorso.campo)]}, solo foglie."""
    layouts: Dict[str, List[Tuple[int, int, str, str]]] = {}
    current: Optional[str] = None
    stack: List[str] = []
    pending: Optional[Tuple[int, int, str, str]] = None
    pending_depth = -1

    def flush() -> None:
        nonlocal pending
        if pending and current:
            layouts[current].append(pending)
        pending = None

    for line in dump.splitlines():
        m = _LAYOUT_LINE_RE.match(line)
        if not m:
            flush()
            if line.startswith("*** Dumping"):
                current = None
            continue
        offset, indent, decl = int(m.group(1)), len(m.group(2)), m.group(3).strip()
        depth = (indent - 1) // 2
        if depth == 0:
            flush()
            root = re.match(r"(?:struct|union)\s+(\w+)$", decl)
            current = root.group(1) if root and root.group(1) not in layouts else None
            if current:
                layouts[current] = []
            stack = []
            continue
        if current is None:
            continue
        if depth > pending_depth:
            pending = None
        else:
            flush()
        del stack[depth - 1:]
        anonymous = decl.endswith(")")
        parts = decl.rsplit(" ", 1)
        name = "" if anonymous or len(parts) < 2 else parts[1]
        type_name = decl if anonymous or len(parts) < 2 else parts[0]
        stack.append(name)
        path = ".".join(p for p in stack if p)
        pending_depth = depth
        pending = (offset, _leaf_size(type_name), type_name, path) if name else None
    flush()
    return layouts


@functools.lru_cache(maxsize=128)
def load_struct_layout(swars_dir: Path, struct: str) -> Tuple[Tuple[int, int, str, str], ...]:
    """Layout a 32 bit (pack(1) come il gioco originale) dagli header reali, tramite clang."""
    ensure_bsndconf()
    definition = re.compile(rf"^struct\s+{re.escape(struct)}\s*(?://[^\n]*)?\s*\{{", re.MULTILINE)
    header = next(
        (p.name for d in _project_include_dirs(swars_dir) if d.exists() for p in sorted(d.glob("*.h"))
         if definition.search(p.read_text(encoding="utf-8", errors="replace"))),
        None,
    )
    if not header:
        return ()
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "time.h").write_text("typedef long time_t;\nstruct tm { int tm_sec; };\n", encoding="utf-8")
        source = Path(tmp) / "layouts.c"
        # clang scarica solo i record usati: il sizeof forza la struct richiesta.
        source.write_text(f'#include "{header}"\nint layout_probe = sizeof(struct {struct});\n', encoding="utf-8")
        cmd = [
            "clang", "-target", "i386-pc-linux-gnu", "-ffreestanding", "-w", "-std=gnu99",
            "-DLB_HAVE_STDINT_H=1", "-Xclang", "-fdump-record-layouts", "-fsyntax-only",
            f"-I{tmp}", "-I/tmp", *[f"-I{d}" for d in _project_include_dirs(swars_dir)], str(source),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return tuple(parse_record_layouts(res.stdout).get(struct, ()))


def _project_include_dirs(swars_dir: Path) -> List[Path]:
    return [
        swars_dir / "src",
        swars_dir / "bfariadne" / "include",
        swars_dir / "bflibrary" / "include",
        swars_dir / "bfsoundlib" / "include",
        swars_dir / "bfsmacklib" / "include",
        swars_dir / "swrendersoft" / "include",
    ]


def extract_asm_memory_offsets(asm_code: str) -> Dict[int, bool]:
    """{offset: letto come word alta} per ogni `disp(%reg)`; `mov 0x9c(..),%edx; sar $0x10,%edx` legge 0x9e."""
    offsets: Dict[int, bool] = {}
    lines = asm_code.splitlines()
    for idx, line in enumerate(lines):
        code = line.split("/*")[0]
        for m in re.finditer(r"(?<![\w)])(0x[0-9a-fA-F]+|\d+)\(%e(?!sp)[a-z]{2}", code):
            off = int(m.group(1), 0)
            load = re.search(r"\bmov\s+[^,]+,%(e[a-z]{2})\s*$", code)
            if load and any(re.search(rf"\bsar\s+\$0x10,%{load.group(1)}\b", n) for n in lines[idx + 1:idx + 3]):
                offsets[off + 2] = True
            else:
                offsets.setdefault(off, False)
    return offsets


def extract_asm_symbols(asm_code: str) -> Tuple[List[str], List[str]]:
    """(funzioni chiamate, globali usate), con i nomi C: `ac_foo`/`ASM_foo` -> `foo`."""
    calls = re.findall(r"\bcall\s+(?:ac_|ASM_)?([A-Za-z_]\w*)", asm_code)
    globals_used = re.findall(r"EXPORT_SYMBOL\((\w+)\)", asm_code)
    return list(dict.fromkeys(calls)), list(dict.fromkeys(globals_used))


def _find_c_declaration(name: str, sources: List[str]) -> str:
    # Solo colonna 0: le righe indentate sono campi di struct o variabili locali omonime.
    pattern = re.compile(
        rf"^(?![#/*\s}}]|return\b|else\b|if\b|while\b|for\b|typedef\b)[^\n;{{}}()=]*\b{re.escape(name)}\b\s*(?=[;=(\[])[^;{{=]*",
        re.MULTILINE,
    )
    for text in sources:
        m = pattern.search(text)
        if m:
            return " ".join(m.group(0).split()) + ";"
    return ""


def _format_struct_fields(struct: str, fields: List[Tuple[int, int, str, str]], offsets: Dict[int, bool], signature: str) -> str:
    prefer = "UPerson" if "p_person" in signature else "UVehicle" if "p_vehicle" in signature else ""
    rows: List[str] = []
    for off in sorted(offsets):
        hits = [f for f in fields if f[0] <= off < f[0] + f[1]]
        preferred = [f for f in hits if prefer and f"U.{prefer}." in f[3]]
        for f_off, _size, type_name, path in (preferred or hits)[:3]:
            delta = off - f_off
            note = f" (byte/word +{delta} del campo: maschere spostate di {delta * 8} bit)" if delta else ""
            note += " (`mov` a 32 bit + `sar $0x10`: e' solo questo campo)" if offsets[off] else ""
            rows.append(f" * 0x{off:02x}: {type_name} {path}{note}")
    return f"/* Offset di `struct {struct}` usati da questa funzione:\n" + "\n".join(rows) + "\n */" if rows else ""


def collect_target_context(swars_dir: Path, target: Dict[str, Any]) -> str:
    """Contesto mirato: solo gli offset, le funzioni e le globali che l'assembly usa davvero.

    Senza `num_ctx` Ollama taglia l'INIZIO del prompt: header interi spingono fuori regole e campi.
    """
    c_rel = target["c_file"]
    signature = target["current_c_stub"].split("{")[0]
    calls, globals_used = extract_asm_symbols(target["asm_code"])
    offsets = extract_asm_memory_offsets(target["asm_code"])

    c_path = swars_dir / c_rel
    sources = [p.read_text(encoding="utf-8", errors="replace") for d in _project_include_dirs(swars_dir) if d.exists() for p in sorted(d.glob("*.h"))]
    if c_path.exists():
        sources.append(c_path.read_text(encoding="utf-8", errors="replace"))

    declarations: List[str] = []
    missing: List[str] = []
    for name in calls + globals_used:
        decl = _find_c_declaration(name, sources)
        (declarations.append(decl) if decl else missing.append(name))

    parts: List[str] = []
    param_structs = list(dict.fromkeys(re.findall(r"struct\s+(\w+)\s*\*", signature)))
    global_structs = list(dict.fromkeys(s for d in declarations if "(" not in d for s in re.findall(r"struct\s+(\w+)", d)))
    for struct in param_structs:
        parts.append(_format_struct_fields(struct, list(load_struct_layout(swars_dir, struct)), offsets, signature))
    for struct in global_structs:
        fields = list(load_struct_layout(swars_dir, struct))
        if struct in param_structs or not fields:
            continue
        if len(fields) <= 16:
            body = "\n".join(f" * 0x{o:02x}: {t} {p}" for o, _s, t, p in fields)
            parts.append(f"/* Layout di `struct {struct}`:\n{body}\n */")
        else:
            parts.append(_format_struct_fields(struct, fields, offsets, signature))
    if declarations:
        parts.append("/* Funzioni e globali gia' dichiarate, da usare senza ridichiararle: */\n" + "\n".join(declarations))
    if missing:
        parts.append("/* Simboli senza dichiarazione C nota, da dichiarare `extern` prima della funzione: " + ", ".join(missing) + " */")
    return "\n\n".join(p for p in parts if p)


_CONDITIONAL_JUMP_RE = re.compile(r"^\s*j(?!mp\b)[a-z]{1,4}\s", re.MULTILINE)
_MEMORY_WRITE_RE = re.compile(r"^\s*(?:mov|add|sub|and|or|xor|inc|dec|neg|not|shl|shr|sar)[bwl]?\s+(?:[^,\n]+,)?\s*(?:0x[0-9a-fA-F]+|\d+)?\(%e(?!sp)[a-z]{2}[^)]*\)\s*$", re.MULTILINE)
_PLACEHOLDER_RE = re.compile(r"\b(placeholder|for demonstration|not implemented|simplified|stub)\b|not used directly", re.IGNORECASE)
MAX_ASM_LINES_PER_STATEMENT = 10.0
MIN_CALL_COVERAGE = 0.8


def strip_c_comments(code: str) -> str:
    return re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL))


def check_translation_fidelity(asm_code: str, candidate_c: str, asm_line_count: int) -> Optional[str]:
    """Motivo di scarto se il C compila ma non puo' essere la traduzione di quest'assembly."""
    if _PLACEHOLDER_RE.search(candidate_c):
        return "Output is a placeholder, not a translation: implement the real logic of the assembly."
    code = strip_c_comments(candidate_c)

    calls, _ = extract_asm_symbols(asm_code)
    if calls:
        missing = [c for c in calls if not re.search(rf"\b(?:ac_)?{re.escape(c)}\b", code)]
        if (len(calls) - len(missing)) / len(calls) < MIN_CALL_COVERAGE:
            return f"The assembly calls {', '.join(missing)} but the C code does not: translate every call."

    statements = code.count(";")
    if asm_line_count >= 30 and asm_line_count / max(statements, 1) > MAX_ASM_LINES_PER_STATEMENT:
        return f"Output is too short: {statements} statements for {asm_line_count} lines of assembly."

    if len(_CONDITIONAL_JUMP_RE.findall(asm_code)) >= 3 and not re.search(r"\b(if|while|for|switch)\b|\?", code):
        return "The assembly has conditional branches but the C code has no control flow."

    if len(_MEMORY_WRITE_RE.findall(asm_code)) >= 2 and not re.search(r"(->\s*[\w.\[\]]+|\]|\*\s*\w+|\.\w+)\s*(?:[-+*/&|^]|<<|>>)?=(?!=)|\+\+|--", code):
        return "The assembly writes to memory but the C code never writes through a pointer."
    return None


def _save_raw_response(record: Dict[str, Any]) -> None:
    RAW_RESPONSES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RAW_RESPONSES_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_worker_prompt(
    target: Dict[str, Any],
    few_shots: List[Dict[str, Any]],
    header_ctx: str,
    compiler_error: str = "",
    previous_attempt: str = "",
) -> str:
    shots_txt = ""
    for idx, ex in enumerate(few_shots, 1):
        shots_txt += (
            f"\n--- VERIFIED EXAMPLE {idx}: `{ex['func_name']}` ({ex['c_file']}) ---\n"
            f"[Original Watcom x86 Assembly]:\n```asm\n{ex['asm_code']}\n```\n"
            f"[Verified Portable C]:\n```c\n{ex['c_code']}\n```\n"
        )

    draft_section = ""
    if target.get("c_draft"):
        draft_section = (
            f"\n[Existing Partial/Draft C Code found under #if 0 in {target['c_file']}]:\n"
            f"```c\n{target['c_draft']}\n```\n"
            "Verify this draft against the assembly below, fix any missing identifiers or types, and output the complete C function.\n"
        )

    repair_section = ""
    if compiler_error and previous_attempt:
        repair_section = (
            f"\n[PREVIOUS ATTEMPT FAILED CLANG COMPILATION]:\n```c\n{previous_attempt}\n```\n"
            f"[CLANG COMPILER DIAGNOSTIC]:\n```\n{compiler_error}\n```\n"
            "Fix all compiler errors above and output the corrected C function.\n"
        )

    sig = target['current_c_stub'].split('{')[0].strip()
    return (
        f"{SYSTEM_PROMPT_DECOMPILER}\n\n"
        f"=== CONTEXT HEADERS & GLOBALS ===\n{header_ctx}\n"
        f"{shots_txt}\n"
        f"=== TARGET FUNCTION TO DECOMPILE: `{target['func_name']}` in `{target['c_file']}` ===\n"
        f"Exact C Signature: `{sig}`\n"
        f"CRITICAL RULE: You MUST start the function implementation with the EXACT signature `{sig}`. NEVER change the return type to bool, int, or anything else.\n\n"
        f"{draft_section}"
        f"[Target Watcom x86 Assembly (`src/swars.sx` lines {target['asm_start_line']}-{target['asm_end_line']})]:\n"
        f"```asm\n{target['asm_code']}\n```\n"
        f"{repair_section}\n"
        "Keep reasoning concise (under 15 lines mapping registers to struct fields), "
        f"then provide the complete C implementation of `{target['func_name']}` inside ```c ... ```."
    )


def build_review_prompt(target: Dict[str, Any], candidate_c: str) -> str:
    return (
        "Sei il Revisore Contrattuale LFM 2.5 per la decompilazione C di Syndicate Wars.\n"
        "Controlla rigorosamente la funzione C candidata rispetto all'assembly Watcom x86 originale:\n"
        "1. La firma della funzione C corrisponde esattamente a quella attesa nel file?\n"
        "2. Sono assenti chiamate `ASM_`, blocchi `asm volatile`, `TODO` o corpi vuoti?\n"
        "3. La logica (registri %eax/%edx/%ebx/%ecx, condizioni di uscita e valori di ritorno) è fedele?\n\n"
        f"[Assembly Originale `ASM_{target['func_name']}`]:\n```asm\n{target['asm_code']}\n```\n\n"
        f"[Codice C Candidato]:\n```c\n{candidate_c}\n```\n\n"
        "Rispondi in JSON puro con lo schema:\n"
        '{"approved": true/false, "issues": "eventuali problemi", "corrected_c": "solo se necessario correggere"}'
    )


def extract_balanced_c_function(text: str, func_name: str) -> str:
    """Estrae una funzione C bilanciando le parentesi graffe a partire dalla firma di func_name."""
    # Match preciso sui qualificatori e tipi C validi per evitare cattura di 'c' o testo markdown isolato
    pattern = re.compile(
        rf"(?:\b(?:static|inline|extern|void|int|short|long|ulong|u32|s32|u16|s16|u8|s8|ubyte|uint|char|float|double|struct\s+\w+|\w+_t)\b[* \t\n]+)+"
        rf"\b{re.escape(func_name)}\s*\([^)]*\)\s*\{{",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        return ""
    start_idx = match.start()
    brace_start = match.end() - 1
    depth = 0
    in_string = False
    in_char = False
    in_line_comment = False
    in_block_comment = False
    for i in range(brace_start, len(text)):
        ch = text[i]
        prev_ch = text[i-1] if i > 0 else ""
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            continue
        if in_block_comment:
            if prev_ch == "*" and ch == "/":
                in_block_comment = False
            continue
        if in_string:
            if ch == '"' and prev_ch != "\\":
                in_string = False
            continue
        if in_char:
            if ch == "'" and prev_ch != "\\":
                in_char = False
            continue
        if ch == "/" and i + 1 < len(text) and text[i+1] == "/":
            in_line_comment = True
            continue
        if ch == "/" and i + 1 < len(text) and text[i+1] == "*":
            in_block_comment = True
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "'":
            in_char = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                prefix = text[max(0, start_idx - 400):start_idx]
                prefix_lines = []
                for line in prefix.splitlines():
                    ls = line.strip()
                    if ls.startswith(("//", "/*", "*", "extern", "void", "struct", "typedef", "#define")):
                        prefix_lines.append(line)
                preamble = ("\n".join(prefix_lines) + "\n") if prefix_lines else ""
                return preamble + text[start_idx:i+1]
    return ""


def extract_c_function_from_response(resp_text: str, func_name: str) -> Tuple[str, str]:
    """Estrae (reasoning_cot, c_code) dalla risposta del modello in modo resiliente."""
    parsed = UniversalModelParser.parse(resp_text)
    cot = parsed.reasoning_cot or ""

    # Le bozze nel ragionamento non sono la risposta: vale l'ultimo blocco dopo `</think>`.
    think_end = resp_text.rfind("</think>")
    answer = resp_text[think_end + len("</think>"):] if think_end >= 0 else resp_text

    # 1. Cerca blocchi ```c ... ``` o ``` ... ``` contenenti func_name
    blocks = re.findall(r"```(?:c|cpp|C)?\s*\n(.*?)(?:```|$)", answer, flags=re.DOTALL)
    for b in reversed(blocks):
        b_clean = b.strip()
        lines = b_clean.splitlines()
        if lines and lines[0].strip().lower() in ("c", "cpp"):
            b_clean = "\n".join(lines[1:]).strip()
        if re.search(r"^\s*(?:mov|push|pop|xor|add|sub|jmp|call|ret)\b", b_clean, flags=re.MULTILINE):
            continue
        if func_name in b_clean and "{" in b_clean and "}" in b_clean:
            return cot, b_clean

    # 2. Ricerca strutturata tramite parser a graffe bilanciate nel testo completo
    cand = extract_balanced_c_function(answer, func_name)
    if cand:
        return cot, cand

    # 3. Fallback: cerca dentro il testo del CoT nel caso il modello abbia ragionato incorporando il codice
    if cot:
        cand_cot = extract_balanced_c_function(cot, func_name)
        if cand_cot:
            return cot, cand_cot

    return cot, ""


def replace_function_in_c_file(c_text: str, old_stub: str, new_c_func: str) -> Optional[str]:
    """Sostituisce il blocco della funzione target nel testo del file .c."""
    if old_stub in c_text:
        return c_text.replace(old_stub, new_c_func, 1)
    return None


def export_sft_dataset() -> Dict[str, Any]:
    """Esporta l'intero corpus (Golden Pairs + CoT distillati) in formato SFT JSONL (ShareGPT/ChatML)."""
    golden = load_jsonl(GOLDEN_PATH)
    cot_distilled = {r["func_name"]: r for r in load_jsonl(COT_TRAIN_PATH)}

    sft_records: List[Dict[str, Any]] = []
    for g in golden:
        fname = g["func_name"]
        dist = cot_distilled.get(fname)
        cot_text = (
            dist["reasoning_cot"]
            if dist and dist.get("reasoning_cot")
            else (
                f"Decompiling `ASM_{fname}` ({g['c_file']}):\n"
                f"- Input assembly spans {g['asm_line_count']} lines using Watcom 32-bit register calling convention (__watcall).\n"
                f"- Mapped register arguments (%eax, %edx, %ebx, %ecx) and stack frame variables to local C types.\n"
                f"- Reconstructed control flow branches into structured C loops and conditionals."
            )
        )
        user_msg = (
            f"{g['instruction']}\n\n"
            f"### Watcom x86 Assembly (`ASM_{fname}`):\n```asm\n{g['asm_code']}\n```"
        )
        assistant_msg = f"<think>\n{cot_text}\n</think>\n\n```c\n{g['c_code']}\n```"
        sft_records.append({
            "func_name": fname,
            "c_file": g["c_file"],
            "has_deep_cot": bool(dist and dist.get("reasoning_cot")),
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_DECOMPILER},
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": assistant_msg},
            ],
        })

    # Aggiungi eventuali nuove funzioni in COT_TRAIN_PATH non ancora in golden
    golden_names = {g["func_name"] for g in golden}
    for fname, dist in cot_distilled.items():
        if fname not in golden_names and dist.get("clang_verified"):
            user_msg = (
                f"Decompile `ASM_{fname}` from `{dist['c_file']}` into portable C99.\n\n"
                f"### Watcom x86 Assembly (`ASM_{fname}`):\n```asm\n{dist['asm_code']}\n```"
            )
            reasoning = dist.get("reasoning_cot", "")
            assistant_msg = (
                f"<think>\n{reasoning}\n</think>\n\n```c\n{dist['verified_c']}\n```"
                if reasoning else f"```c\n{dist['verified_c']}\n```"
            )
            sft_records.append({
                "func_name": fname,
                "c_file": dist["c_file"],
                "has_deep_cot": bool(dist.get("reasoning_cot")),
                "verification": dist.get("verification", "clang"),
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT_DECOMPILER},
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": assistant_msg},
                ],
            })

    with open(SFT_EXPORT_PATH, "w", encoding="utf-8") as f:
        for rec in sft_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return {
        "total_sft_examples": len(sft_records),
        "deep_cot_examples": sum(1 for r in sft_records if r["has_deep_cot"]),
        "sft_dataset_path": str(SFT_EXPORT_PATH),
    }


def process_one_target(
    target: Dict[str, Any],
    golden_pairs: List[Dict[str, Any]],
    swars_dir: Path,
    apply_changes: bool = False,
) -> Dict[str, Any]:
    fname = target["func_name"]
    c_rel = target["c_file"]
    _log("TARGET", f"Avvio decompilazione `{fname}` ({c_rel}, {target['asm_line_count']} righe ASM, draft={target['has_if0_draft']})...")

    few_shots = select_few_shot_examples(golden_pairs, c_rel, k=1)
    header_ctx = collect_target_context(swars_dir, target)
    c_orig_text = (swars_dir / c_rel).read_text(encoding="utf-8", errors="replace")

    compiler_err = ""
    candidate_c = ""
    cot = ""
    clang_ok = False
    routed_node = "unknown"

    # Fino a 2 tentativi: tentativo 1 su Tier-1 Veloce (8B), tentativo 2 con fallback su Tier-2 Esperto (24B)
    for attempt in range(1, 3):
        current_model = WORKER_MODEL if attempt == 1 else EXPERT_MODEL
        tier_tag = "TIER1-FAST" if attempt == 1 else "TIER2-EXPERT"
        prompt = build_worker_prompt(
            target,
            few_shots,
            header_ctx,
            compiler_error=compiler_err,
            previous_attempt=candidate_c,
        )
        _log(tier_tag, f"Tentativo {attempt}/2 per `{fname}` su {current_model}...")
        res = execute_omen_prompt(prompt, model=current_model, timeout=GENERATION_TIMEOUT_S, num_ctx=NUM_CTX, num_predict=NUM_PREDICT)
        routed_node = res.get("routed_via", "unknown")
        if res.get("status") != "ok":
            _log("ERROR", f"{tier_tag} errore di rete: {res.get('error')}")
            return {"func_name": fname, "status": "network_error", "error": res.get("error")}

        cot, candidate_c = extract_c_function_from_response(res["response"], fname)
        raw_record = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "func_name": fname,
            "attempt": attempt,
            "model": current_model,
            "routed_via": routed_node,
            "prompt_chars": len(prompt),
            "prompt_eval_count": res.get("prompt_eval_count"),
            "eval_count": res.get("eval_count"),
            "response": res["response"],
        }
        _save_raw_response(raw_record)
        if NUM_PREDICT and res.get("eval_count", 0) >= NUM_PREDICT:
            _log("TRUNCATED", f"Risposta tagliata al limite di {NUM_PREDICT} token: il modello non ha finito.")
        tok_s = res.get("tok_s", 0.0)
        eval_cnt = res.get("eval_count", 0)
        eval_dur = res.get("eval_duration_s", res.get("elapsed_s", 0))
        prompt_cnt = res.get("prompt_eval_count", 0)
        prompt_tok_s = res.get("prompt_tok_s", 0.0)
        _log(
            "TELEMETRY",
            f"⚡ Velocità generaz.: {tok_s} tok/s ({eval_cnt} tok in {eval_dur}s) | "
            f"Prompt eval: {prompt_cnt} tok @ {prompt_tok_s} tok/s | Nodo: {routed_node}"
        )

        code_no_comments = strip_c_comments(candidate_c)
        if not candidate_c or "asm volatile" in code_no_comments or "call ASM_" in code_no_comments or re.search(r"\bASM_\w+\s*\(", code_no_comments):
            compiler_err = "Output did not contain a valid pure-C function without ASM calls."
            _log("PARSER", f"✗ Candidate C scartato: {compiler_err}")
            continue

        if "..." in code_no_comments or re.search(r"\bTODO\b", candidate_c, re.I):
            compiler_err = "Output contains incomplete placeholder ellipsis (...) or TODO."
            _log("PARSER", f"✗ Candidate C scartato: {compiler_err}")
            continue

        semicolon_count = code_no_comments.count(";")
        if target.get("asm_line_count", 0) >= 15 and semicolon_count < 2:
            compiler_err = f"Output is a hollow stub (only {semicolon_count} statements for {target.get('asm_line_count')} lines of ASM)."
            _log("PARSER", f"✗ Candidate C scartato: {compiler_err}")
            continue

        fidelity_err = check_translation_fidelity(target["asm_code"], candidate_c, target.get("asm_line_count", 0))
        if fidelity_err:
            compiler_err = fidelity_err
            _log("FIDELITY", f"✗ Candidate C scartato: {compiler_err}")
            continue

        _log("PREVIEW", f"Codice C estratto ({len(candidate_c.splitlines())} righe):\n{candidate_c[:300]}...")

        patched = replace_function_in_c_file(c_orig_text, target["current_c_stub"], candidate_c)
        if not patched:
            compiler_err = "Could not locate original stub block in C file."
            _log("PATCH", f"✗ {compiler_err}")
            break

        clang_ok, diag = verify_c_file_with_clang(swars_dir, c_rel, patched)
        if clang_ok:
            _log("CLANG", f"✓ `{fname}` compilato con ZERO errori da clang!")
            break
        else:
            _log("CLANG", f"✗ `{fname}` errore clang (tentativo {attempt}):\n{diag[:350]}...")
            compiler_err = diag

    if not clang_ok:
        return {
            "func_name": fname,
            "c_file": c_rel,
            "status": "clang_failed",
            "last_error": compiler_err[:500],
        }

    # Stage 2: Review Gate con Liquid AI LFM 2.5 (VRAM-resident)
    _log("LFM-REVIEW", f"Review contrattuale LFM 2.5 per `{fname}` ({REVIEW_MODEL})...")
    rev_prompt = build_review_prompt(target, candidate_c)
    rev_res = execute_omen_prompt(rev_prompt, model=REVIEW_MODEL, timeout=300, num_predict=384)
    lfm_approved = True
    lfm_notes = "ok"
    if rev_res.get("status") == "ok":
        rev_text = rev_res.get("response", "")
        if '"approved": false' in rev_text.lower():
            lfm_approved = False
            lfm_notes = rev_text[:300]

    # Salva in staging e nel dataset di training CoT
    stage_subdir = STAGING_DIR / Path(c_rel).stem
    stage_subdir.mkdir(parents=True, exist_ok=True)
    (stage_subdir / f"{fname}.c").write_text(candidate_c + "\n", encoding="utf-8")

    train_entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "func_name": fname,
        "c_file": c_rel,
        "worker_model": WORKER_MODEL,
        "review_model": REVIEW_MODEL,
        "routed_via": routed_node,
        "lfm_approved": lfm_approved,
        "lfm_notes": lfm_notes,
        "clang_verified": True,
        "asm_line_count": target["asm_line_count"],
        "asm_code": target["asm_code"],
        "reasoning_cot": cot,
        "verified_c": candidate_c,
    }
    with open(COT_TRAIN_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(train_entry, ensure_ascii=False) + "\n")

    applied = False
    if apply_changes and lfm_approved:
        patched = replace_function_in_c_file(c_orig_text, target["current_c_stub"], candidate_c)
        if patched:
            (swars_dir / c_rel).write_text(patched, encoding="utf-8")
            applied = True
            _log("APPLY", f"✓ Patch applicata a `{c_rel}` per `{fname}`.")

    export_sft_dataset()
    return {
        "func_name": fname,
        "c_file": c_rel,
        "status": "verified",
        "lfm_approved": lfm_approved,
        "applied": applied,
        "routed_via": routed_node,
    }


def run_batch(
    batch_size: int = 1,
    apply_changes: bool = False,
    file_filter: str = "",
    func_filter: str = "",
) -> Dict[str, Any]:
    if not is_thermal_safe():
        return {"status": "thermal_pause"}

    build_datasets(SWARS_DIR)
    golden = load_jsonl(GOLDEN_PATH)
    pending = load_jsonl(PENDING_PATH)
    already_done = {r["func_name"] for r in load_jsonl(COT_TRAIN_PATH) if r.get("clang_verified")}

    failed_attempts_path = DATA_DIR / "nightly" / "syndwars_failed_attempts.json"
    failed_map: Dict[str, int] = {}
    if failed_attempts_path.exists():
        try:
            failed_map = json.loads(failed_attempts_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    queue = [
        t for t in pending
        if t["func_name"] not in already_done
        and (not file_filter or file_filter in t["c_file"])
        and (not func_filter or func_filter == t["func_name"])
    ]
    # Ordina dando priorità alle funzioni che non hanno mai fallito
    queue.sort(key=lambda t: failed_map.get(t["func_name"], 0))

    results = []
    for target in queue[:batch_size]:
        res = process_one_target(target, golden, SWARS_DIR, apply_changes=apply_changes)
        results.append(res)
        fname = target["func_name"]
        if res.get("status") != "verified":
            failed_map[fname] = failed_map.get(fname, 0) + 1
            failed_attempts_path.parent.mkdir(parents=True, exist_ok=True)
            failed_attempts_path.write_text(json.dumps(failed_map, indent=2), encoding="utf-8")

    sft_info = export_sft_dataset()
    summary = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "processed": len(results),
        "verified": sum(1 for r in results if r.get("status") == "verified"),
        "remaining_in_queue": max(0, len(queue) - len(results)),
        "sft_dataset": sft_info,
        "results": results,
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Motore Sovrano di Decompilazione SyndWarsFX (Flint 40B + LFM 2.5 24B)")
    parser.add_argument("--once", action="store_true", help="Decompila e verifica 1 funzione dalla coda")
    parser.add_argument("--batch", type=int, default=1, help="Numero di funzioni da elaborare nel batch")
    parser.add_argument("--file", type=str, default="", help="Filtra per nome file (es. people.c)")
    parser.add_argument("--func", type=str, default="", help="Filtra per nome funzione specifico")
    parser.add_argument("--apply", action="store_true", help="Applica le funzioni verificate da clang direttamente ai file .c")
    parser.add_argument("--daemon", action="store_true", help="Esegui in ciclo continuo giorno e notte")
    parser.add_argument("--interval", type=int, default=15, help="Pausa in secondi tra i batch in modalità daemon")
    parser.add_argument("--export-sft", action="store_true", help="Esporta subito il dataset SFT per fine-tuning QLoRA/MLX")
    parser.add_argument("--apply-staged", action="store_true", help="Applica ai file .c tutte le funzioni già verificate nello staging dei nodi")
    args = parser.parse_args()

    if args.export_sft:
        info = export_sft_dataset()
        print(json.dumps(info, indent=2, ensure_ascii=False))
        return

    if args.apply_staged:
        pending_map = {t["func_name"]: t for t in load_jsonl(PENDING_PATH)}
        applied_list = []
        for rec in load_jsonl(COT_TRAIN_PATH):
            if rec.get("clang_verified") and rec.get("lfm_approved", True):
                fn = rec["func_name"]
                tgt = pending_map.get(fn)
                if not tgt:
                    continue
                c_path = SWARS_DIR / tgt["c_file"]
                c_txt = c_path.read_text(encoding="utf-8", errors="replace")
                patched = replace_function_in_c_file(c_txt, tgt["current_c_stub"], rec["verified_c"])
                if patched:
                    ok, _ = verify_c_file_with_clang(SWARS_DIR, tgt["c_file"], patched)
                    if ok:
                        c_path.write_text(patched, encoding="utf-8")
                        applied_list.append({"func_name": fn, "c_file": tgt["c_file"]})
        build_datasets(SWARS_DIR)
        print(json.dumps({"applied_count": len(applied_list), "applied": applied_list}, indent=2))
        return

    if args.daemon:
        _log("DAEMON", f"Avvio ciclo continuo giorno/notte (Turbo Full-VRAM {WORKER_MODEL}, batch={args.batch}, apply={args.apply})...")
        recent_durations = []
        while True:
            try:
                t_start = time.perf_counter()
                rep = run_batch(batch_size=args.batch, apply_changes=args.apply, file_filter=args.file, func_filter=args.func)
                batch_dur = time.perf_counter() - t_start
                recent_durations.append(batch_dur / max(1, rep.get("processed", 1)))
                if len(recent_durations) > 10:
                    recent_durations.pop(0)

                avg_sec = sum(recent_durations) / len(recent_durations)
                rem = rep.get("remaining_in_queue", 0)
                eta_sec = int(rem * avg_sec)
                eta_h = eta_sec // 3600
                eta_m = (eta_sec % 3600) // 60

                _log("DAEMON", f"Batch completato in {batch_dur:.1f}s: {rep.get('verified')}/{rep.get('processed')} verificati, {rem} rimanenti in coda.")
                _log("ETA", f"⏳ Velocità media: {avg_sec:.1f}s/funzione | Stima completamento coda (ETA): {eta_h} ore e {eta_m} minuti.")

                if rem == 0:
                    _log("DAEMON", "🎉 Tutte le funzioni in coda sono state elaborate!")
                    break
                time.sleep(args.interval)
            except KeyboardInterrupt:
                _log("DAEMON", "Arresto manuale.")
                break
            except Exception as exc:
                _log("ERROR", f"Errore nel loop daemon: {exc}")
                time.sleep(30)
    else:
        n = 1 if args.once else args.batch
        rep = run_batch(batch_size=n, apply_changes=args.apply, file_filter=args.file, func_filter=args.func)
        print(json.dumps(rep, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
