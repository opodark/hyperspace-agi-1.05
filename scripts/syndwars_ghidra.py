#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Decompilazione in tre passi: Ghidra ricostruisce il flusso, il codice applica i campi noti e rende
compilabile la bozza, un modello locale propone solo i nomi delle variabili. Ghidra conosce `__watcall`
tramite scripts/ghidra/DecompileWatcom.java.

I risultati finiscono in `data/nightly/syndwars_ghidra/` e non nel dataset: vanno riletti prima.

Uso:
    .venv/bin/python scripts/syndwars_ghidra.py person_drop_item search_things_for_uniqueid
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.syndwars_decompile_sovereign import (
    PENDING_PATH,
    SWARS_DIR,
    _find_c_declaration,
    collect_target_context,
    load_jsonl,
    load_struct_layout,
    replace_function_in_c_file,
    verify_c_file_with_clang,
)
from scripts.syndwars_orchestrate import load_sources, parse_signature

GHIDRA_HOME = Path(os.getenv("GHIDRA_INSTALL_DIR", str(Path.home() / "ghidra_12.1.4_PUBLIC")))
JAVA_HOME = os.getenv("JAVA_HOME", "/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home")
OLLAMA_URL = os.getenv("SWARS_OLLAMA_URL", "http://127.0.0.1:21434").rstrip("/")
REFINE_MODEL = os.getenv("SWARS_REFINE_MODEL", "hf.co/mradermacher/Qwen3.5-9B-Coder-GGUF:Q4_K_M")
REFINE_NUM_CTX = int(os.getenv("SWARS_REFINE_NUM_CTX", "16384"))
REFINE_NUM_PREDICT = int(os.getenv("SWARS_REFINE_NUM_PREDICT", "1500"))
REFINE_TIMEOUT_S = int(os.getenv("SWARS_REFINE_TIMEOUT_S", "600"))
NETWORK_RETRIES = int(os.getenv("SWARS_NETWORK_RETRIES", "6"))
OUTPUT_DIR = ROOT / "data" / "nightly" / "syndwars_ghidra"

_ACCESS_SIZES = {"byte": 1, "char": 1, "undefined1": 1, "undefined": 1, "ubyte": 1, "sbyte": 1,
                 "short": 2, "ushort": 2, "undefined2": 2, "int": 4, "uint": 4, "undefined4": 4, "long": 4, "ulong": 4,
                 "u32": 4, "s32": 4, "u16": 2, "s16": 2, "u8": 1, "s8": 1}
_TYPE_WORDS = {"undefined8": "longlong", "undefined4": "int", "undefined2": "short", "undefined1": "ubyte", "undefined": "ubyte", "byte": "ubyte", "uint": "u32"}
EXTERNAL_SLOT = 0x10000


LIBC_DECLARATIONS = {
    "memset": "void *memset(void *s, int c, unsigned int n);",
    "memcpy": "void *memcpy(void *dest, const void *src, unsigned int n);",
    "memmove": "void *memmove(void *dest, const void *src, unsigned int n);",
    "strlen": "unsigned int strlen(const char *s);",
    "strcpy": "char *strcpy(char *dest, const char *src);",
    "strcat": "char *strcat(char *dest, const char *src);",
    "strcmp": "int strcmp(const char *a, const char *b);",
    "strncpy": "char *strncpy(char *dest, const char *src, unsigned int n);",
    "sprintf": "int sprintf(char *s, const char *f, ...);",
    "toupper": "int toupper(int c);",
}
INFERRED_SIGNATURES_PATH = OUTPUT_DIR / "_inferred_signatures.json"


@functools.lru_cache(maxsize=1)
def _project_sources() -> Tuple[str, ...]:
    """Tutto il progetto: una funzione puo' essere dichiarata in un header che il file corrente non include."""
    roots = (SWARS_DIR / "src", SWARS_DIR / "bflibrary" / "include")
    paths = [p for root in roots if root.exists() for pattern in ("*.h", "*.c") for p in sorted(root.glob(pattern)) if not p.name.startswith("tmp")]
    return tuple(p.read_text(encoding="utf-8", errors="replace") for p in paths)


def _clean_declaration(declaration: str) -> str:
    text = re.sub(r"//[^\n]*|/\*.*?\*/", " ", declaration, flags=re.DOTALL)
    return " ".join(re.sub(r"\b(?:static|inline|__inline__)\b", "", text).split()).rstrip("; ") + ";"


def lookup_declaration(name: str, sources: Sequence[str], inferred: Optional[Dict[str, str]] = None) -> str:
    """Prima il file corrente, poi libc e il resto del progetto, infine la firma ricavata da Ghidra."""
    found = _find_c_declaration(name, list(sources))
    if found:
        return _clean_declaration(found)
    if name in LIBC_DECLARATIONS:
        return LIBC_DECLARATIONS[name]
    found = _find_c_declaration(name, list(_project_sources()))
    if found:
        return _clean_declaration(found)
    return (inferred or {}).get(name, "")


def load_inferred_signatures() -> Dict[str, str]:
    if not INFERRED_SIGNATURES_PATH.exists():
        return {}
    return json.loads(INFERRED_SIGNATURES_PATH.read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=1)
def _assembly_source() -> str:
    return (SWARS_DIR / "src" / "swars.sx").read_text(encoding="utf-8", errors="replace")


def stack_args_from_assembly(label: str, source: Optional[str] = None) -> Optional[int]:
    """Argomenti sullo stack letti da `ret $n`; None se la funzione non e' in assembly."""
    text = _assembly_source() if source is None else source
    start = re.search(rf"^\s*(?:GLOBAL_FUNC\({re.escape(label)}\)|{re.escape(label)}:)", text, re.MULTILINE)
    if not start:
        return None
    ret = re.compile(r"^\s*ret\b(?:\s+\$(0x[0-9a-fA-F]+|\d+))?", re.MULTILINE).search(text, start.end())
    return int(ret.group(1), 0) // 4 if ret and ret.group(1) else 0


def build_ghidra_spec(targets: Sequence[Dict[str, Any]]) -> str:
    lines: List[str] = []
    seen = set()
    for target in targets:
        return_type, name, params = parse_signature(target["current_c_stub"])
        lines.append(f"T\tASM_{name}\t{'void' if return_type == 'void' else 'value'}\t{','.join(p[1] for p in params)}")
        sources = load_sources(target["c_file"])
        for raw in re.findall(r"\bcall\s+([A-Za-z_]\w*)", target["asm_code"]):
            if raw in seen:
                continue
            seen.add(raw)
            decl = lookup_declaration(re.sub(r"^(?:ac_|ASM_)", "", raw), sources)
            m = re.match(r"(.*?)\b\w+\s*\((.*)\)\s*;?$", decl, re.DOTALL)
            if not m:
                stack_args = stack_args_from_assembly(raw)
                if stack_args is not None:
                    lines.append(f"I\t{raw}\t{stack_args}")
                continue
            args = [] if m.group(2).strip() in ("", "void") else [re.sub(r".*?(\w+)$", r"\1", a.strip(), flags=re.DOTALL) for a in m.group(2).split(",")]
            kind = "void" if m.group(1).replace("extern", "").strip() == "void" else "value"
            lines.append(f"C\t{raw}\t{kind}\t{','.join(args)}")
    return "\n".join(lines) + "\n"


def fake_external_section(undefined: Sequence[str], called: Sequence[str]) -> str:
    """Ghidra non gestisce `simbolo+offset` verso gli esterni: dati finti a indirizzi noti lo rendono risolvibile."""
    called_set = set(called)
    lines = ['.section .hsext,"aw",@nobits']
    for name in undefined:
        if name in called_set or name.startswith(("ac_", "ASM_")):
            continue
        lines.extend([".space 0x1000", f".global {name}", f"{name}:", f".space {EXTERNAL_SLOT - 0x1000}"])
    return "\n".join(lines) + "\n"


def parse_inferred_signatures(text: str) -> Dict[str, str]:
    """{nome C: dichiarazione}; il tipo degli argomenti non si conosce, resta `int`."""
    found: Dict[str, str] = {}
    for label, count, kind in re.findall(r"^//@@@INFER (\S+) (\d+) (void|value)$", text, re.MULTILINE):
        name = re.sub(r"^(?:ac_|ASM_)", "", label)
        params = ", ".join(f"int a{i + 1}" for i in range(int(count))) or "void"
        found[name] = f"{'void' if kind == 'void' else 'int'} {name}({params});"
    return found


def parse_ghidra_output(text: str) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int]]:
    head, *chunks = re.split(r"^//@@@ ", text, flags=re.MULTILINE)
    symbols = {m.group(1): int(m.group(2)) for m in re.finditer(r"^//@@@SYM (\S+) (\d+)$", head, re.MULTILINE)}
    result: Dict[str, Dict[str, Any]] = {}
    for chunk in chunks:
        name, _, code = chunk.partition("\n")
        sizes = {m.group(1): int(m.group(2)) for m in re.finditer(r"^//@@@GLOBAL (\S+) (\d+)$", code, re.MULTILINE)}
        for m in re.finditer(r"^//@@@ACCESS (\d+) (\d+)$", code, re.MULTILINE):
            key = f"_DAT_{int(m.group(1)):08x}"
            sizes[key] = max(sizes.get(key, 0), int(m.group(2)))
        for m in re.finditer(r"^//@@@WIDE (\S+) (\d+)$", code, re.MULTILINE):
            sizes[m.group(1)] = max(sizes.get(m.group(1), 0), int(m.group(2)))
        body = re.sub(r"^//@@@(?:GLOBAL|ACCESS|WIDE) .*\n", "", code, flags=re.MULTILINE).strip()
        result[re.sub(r"^ASM_", "", name.strip())] = {"code": body, "global_sizes": sizes}
    return result, symbols


def run_ghidra(targets: Sequence[Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int], Dict[str, str]]:
    """({funzione: C e dimensioni delle globali}, {esterno: indirizzo}, {funzione: firma ricavata}). Il progetto e' temporaneo."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        source = (SWARS_DIR / "src" / "swars.sx").read_text(encoding="utf-8", errors="replace")
        assemble = ["clang", "-target", "i386-unknown-linux-gnu", "-x", "assembler-with-cpp", "-c"]
        plain = work / "plain.sx"
        plain.write_text(source, encoding="utf-8")
        first = work / "plain.o"
        subprocess.run([*assemble, str(plain), "-o", str(first)], check=True, capture_output=True, text=True, timeout=180)
        nm = subprocess.run(["nm", "-u", str(first)], check=True, capture_output=True, text=True).stdout
        undefined = [line.split()[-1] for line in nm.splitlines() if line.strip()]
        called = re.findall(r"\bcall\s+([A-Za-z_]\w*)", source)
        combined = work / "swars.sx"
        combined.write_text(source + "\n" + fake_external_section(undefined, called), encoding="utf-8")
        obj = work / "swars.o"
        subprocess.run([*assemble, str(combined), "-o", str(obj)], check=True, capture_output=True, text=True, timeout=180)
        spec, out = work / "spec.tsv", work / "out.c"
        spec.write_text(build_ghidra_spec(targets), encoding="utf-8")
        (work / "proj").mkdir()
        subprocess.run(
            [str(GHIDRA_HOME / "support" / "analyzeHeadless"), str(work / "proj"), "swars", "-import", str(obj),
             "-scriptPath", str(ROOT / "scripts" / "ghidra"), "-postScript", "DecompileWatcom.java", str(spec), str(out)],
            check=True, capture_output=True, text=True, timeout=1800, env={**os.environ, "JAVA_HOME": JAVA_HOME},
        )
        text = out.read_text(encoding="utf-8")
        decompiled, symbols = parse_ghidra_output(text)
        return decompiled, symbols, parse_inferred_signatures(text)


# I 4 byte restano `int`: quando serve il confronto senza segno Ghidra scrive gia' `(uint)`.
_READ_TYPE = {1: "ubyte", 2: "ushort", 4: "int", 8: "ulonglong"}
_SIGNED_READ_TYPE = {1: "signed char", 2: "short", 4: "int", 8: "longlong"}


def _is_sign_extended(text: str, position: int) -> bool:
    """Ghidra scrive `(int)x` per l'estensione con segno e `(uint)x` per quella senza."""
    return text[:position].endswith("(int)")


def resolve_data_addresses(code: str, symbols: Dict[str, int], sizes: Dict[str, int]) -> str:
    """`_DAT_00abcd` torna `*(tipo *)((long)simbolo + offset)`; il tipo viene dalla dimensione vista da Ghidra."""
    ordered = sorted(symbols.items(), key=lambda kv: kv[1])

    def locate(address: int) -> Optional[Tuple[str, int]]:
        for name, start in ordered:
            if start - 0x1000 <= address < start + EXTERNAL_SLOT - 0x1000:
                return name, address - start
        return None

    def array(match: "re.Match[str]") -> str:
        hit = locate(int(match.group(2), 16))
        if not hit:
            return match.group(0)
        name, delta = hit
        location = f"((long)&{name} + {delta:#x})" if delta else f"((long)&{name})"
        size = sizes.get(f"{match.group(1)}DAT_{match.group(2)}", 1)
        return f"(({_READ_TYPE.get(size, 'ubyte')} *){location})["

    def rewrite(match: "re.Match[str]") -> str:
        amp, under, addr = match.group(1), match.group(2), int(match.group(3), 16)
        hit = locate(addr)
        if not hit:
            return match.group(0)
        name, delta = hit
        location = f"((long)&{name} + {delta:#x})" if delta else f"((long)&{name})"
        if amp:
            size = sizes.get(f"{under}DAT_{match.group(3)}", 1)
            followed = re.match(r"\s*\+", match.string[match.end():])
            # `&simbolo + n` di Ghidra e' scalato sull'elemento; `(int)&simbolo + n` no.
            if followed and size > 1 and not _is_sign_extended(match.string, match.start()):
                return f"(({_READ_TYPE.get(size, 'ubyte')} *){location})"
            return location
        size = sizes.get(f"{under}DAT_{match.group(3)}", 4 if under else 1)
        types = _SIGNED_READ_TYPE if _is_sign_extended(match.string, match.start()) else _READ_TYPE
        return f"(*({types.get(size, 'int')} *){location})"

    code = re.sub(r"\(&(_?)DAT_([0-9a-fA-F]{6,})\)\s*\[", array, code)
    return re.sub(r"(&?)(_?)DAT_([0-9a-fA-F]{6,})", rewrite, code)


def rewrite_named_globals(code: str, sizes: Dict[str, int]) -> str:
    """Accesso per indirizzo con la larghezza vista da Ghidra: non dipende dal tipo dichiarato in C."""
    for ghidra_name, size in sorted(sizes.items(), key=lambda kv: -len(kv[0])):
        if re.match(r"_?DAT_", ghidra_name) or not re.match(r"[A-Za-z_]\w*$", ghidra_name):
            continue
        name = ghidra_name[1:] if ghidra_name.startswith("_") else ghidra_name
        escaped = re.escape(ghidra_name)
        element = _READ_TYPE.get(size, "ubyte")
        code = re.sub(rf"\(&{escaped}\)(\s*\[)", rf"(({element} *)&{name})\1", code)
        if size > 1 and size in _READ_TYPE:
            # `&simbolo + n` di Ghidra e' scalato sull'elemento; `(int)&simbolo + n` no.
            code = re.sub(rf"(?<!\(int\))(?<!\*\))&{escaped}\b(?=\s*\+)", f"(({_READ_TYPE[size]} *)&{name})", code)
        code = re.sub(rf"(?<!\*\))&{escaped}\b", f"((long)&{name})", code)
        if size in _READ_TYPE:
            code = re.sub(
                rf"(?<![\w.>&]){escaped}\b(?!\s*\()",
                lambda m, n=name, s=size: f"(*({(_SIGNED_READ_TYPE if _is_sign_extended(m.string, m.start()) else _READ_TYPE)[s]} *)&{n})",
                code,
            )
    return code


GHIDRA_COMPAT = """#ifndef GHIDRA_COMPAT_H
#define GHIDRA_COMPAT_H
#include <string.h>
#include <stdlib.h>
#include <ctype.h>
#ifndef bool
#define bool _Bool
#define true 1
#define false 0
#endif
typedef long long longlong;
typedef unsigned long long ulonglong;
typedef signed char int1;
typedef short int2;
typedef int int4;
typedef unsigned char uint1;
typedef unsigned short uint2;
typedef unsigned int uint4;
typedef int int3;
typedef long long int5;
typedef long long int6;
typedef long long int7;
typedef unsigned int uint3;
typedef unsigned long long uint5;
typedef unsigned long long uint6;
typedef unsigned long long uint7;
#define CONCAT11(h, l) ((ushort)(((ubyte)(h) << 8) | (ubyte)(l)))
#define CONCAT12(h, l) (((u32)(ubyte)(h) << 16) | (ushort)(l))
#define CONCAT13(h, l) (((u32)(ubyte)(h) << 24) | ((u32)(l) & 0xFFFFFF))
#define CONCAT22(h, l) (((u32)(ushort)(h) << 16) | (ushort)(l))
#define CONCAT31(h, l) (((u32)(h) << 8) | (ubyte)(l))
#define CONCAT44(h, l) (((unsigned long long)(u32)(h) << 32) | (u32)(l))
#define SUB41(x, b) ((ubyte)((u32)(x) >> ((b) * 8)))
#define SUB42(x, b) ((ushort)((u32)(x) >> ((b) * 8)))
#define SBORROW1(a, b) ((signed char)((a) - (b)) != (int)(signed char)(a) - (int)(signed char)(b))
#define SBORROW2(a, b) ((short)((a) - (b)) != (int)(short)(a) - (int)(short)(b))
#define SBORROW4(a, b) ((int)((u32)(a) - (u32)(b)) != (long long)(int)(a) - (long long)(int)(b))
#define SCARRY1(a, b) ((signed char)((a) + (b)) != (int)(signed char)(a) + (int)(signed char)(b))
#define SCARRY2(a, b) ((short)((a) + (b)) != (int)(short)(a) + (int)(short)(b))
#define SCARRY4(a, b) ((int)((u32)(a) + (u32)(b)) != (long long)(int)(a) + (long long)(int)(b))
#define CARRY1(a, b) ((ubyte)((a) + (b)) < (ubyte)(a))
#define CARRY2(a, b) ((ushort)((a) + (b)) < (ushort)(a))
#define CARRY4(a, b) ((u32)((u32)(a) + (u32)(b)) < (u32)(a))
#define POPCOUNT(x) __builtin_popcount(x)
#endif
"""


def join_statements(code: str) -> List[str]:
    """Riunisce le istruzioni spezzate su piu' righe: togliere una riga non deve lasciare parentesi aperte."""
    joined: List[str] = []
    pending = ""
    for line in code.splitlines():
        pending = f"{pending} {line.strip()}" if pending else line
        if pending.count("(") > pending.count(")"):
            continue
        joined.append(pending)
        pending = ""
    if pending:
        joined.append(pending)
    return joined


def clean_ghidra_c(code: str, symbols: Optional[Dict[str, int]] = None, sizes: Optional[Dict[str, int]] = None) -> str:
    """Toglie il rumore delle `push`/`call` su stack, i prefissi e i tipi `undefinedN` di Ghidra."""
    lines = [l for l in join_statements(code) if not l.lstrip().startswith("/* WARNING")]

    # Solo cio' che deriva davvero da ESP e' rumore: i puntatori `puVar` veri restano.
    tainted = {m.group(1) for l in lines for m in [re.search(r"(\w+)\s*=\s*.*(?:&stack0x|&uStackY_|in_ESP)", l)] if m}
    changed = True
    while changed:
        changed = False
        for line in lines:
            m = re.match(r"\s*(\w+)\s*=\s*(?:\(\w+ \*\))?\(?(?:\(int\))?(\w+)(?:\s*\+\s*-?0x[0-9a-fA-F]+)?\)?;\s*$", line)
            if m and m.group(1) not in tainted and m.group(2) in tainted:
                tainted.add(m.group(1))
                changed = True
    noise = "|".join(re.escape(t) for t in sorted(tainted)) or "(?!x)x"
    noise_re = re.compile(rf"\b(?:{noise}|uStackY_\w+|in_ESP|stack0x\w+|BADSPACEBASE)\b")
    slot = rf"\*\(\w+ \*\)\((\(int\)(?:{noise}) \+ -?0x[0-9a-fA-F]+|(?:{noise}) \+ -?0x[0-9a-fA-F]+)\)"
    slots: Dict[str, str] = {}
    kept: List[str] = []
    for line in lines:
        write = re.match(rf"\s*{slot} = (.+);\s*$", line)
        if write and not noise_re.search(write.group(2)):
            slots[write.group(1)] = write.group(2)
            continue
        line = re.sub(slot, lambda m: slots.get(m.group(1), m.group(0)), line)
        if noise_re.search(line):
            continue
        kept.append(line)
    text = "\n".join(kept)
    if symbols:
        text = resolve_data_addresses(text, symbols, sizes or {})
    text = rewrite_named_globals(text, sizes or {})
    text = re.sub(r"\b(?:ac|ASM)_(\w+)\s*\(", r"\1(", text)
    text = re.sub(r"(?<![\w.>])_([a-zA-Z]\w*)", r"\1", text)
    text = re.sub(r"\b(undefined[1248]?|byte|uint)\b", lambda m: _TYPE_WORDS[m.group(1)], text)
    return text


def ghidra_parameter_types(header: str) -> Dict[str, str]:
    match = re.search(r"\((.*)\)", header, re.DOTALL)
    types: Dict[str, str] = {}
    for part in match.group(1).split(",") if match else []:
        found = re.match(r"\s*(.*?)(\w+)\s*$", part, re.DOTALL)
        if found and found.group(1).strip():
            types[found.group(2)] = " ".join(found.group(1).replace("*", " * ").split())
    return types


_UNSIGNED_WORDS = {"ushort", "ubyte", "byte", "u8", "u16", "u32", "uint", "ulong", "TbBool"}
_SIGNED_WORDS = {"short", "char", "sbyte", "s8", "s16", "s32", "int", "long", "ThingIdx", "MapCoord"}


def _sign_of(ctype: str) -> Optional[bool]:
    """True con segno, False senza, None se il tipo non si conosce."""
    word = ctype.replace("const", "").strip()
    return True if word in _SIGNED_WORDS else False if word in _UNSIGNED_WORDS else None


def _is_written(match: "re.Match[str]") -> bool:
    after = match.string[match.end():match.end() + 4]
    return bool(re.match(r"\s*(?:=(?!=)|\+\+|--|[-+*/|&^%]=|<<=|>>=)", after)) or match.string[:match.start()].endswith("&")


def _field_for(fields: Sequence[Tuple[int, int, str, str]], offset: int, size: int, prefer: str) -> Optional[Tuple[str, int, int, str]]:
    hits = [f for f in fields if f[0] <= offset < f[0] + f[1]]
    hits.sort(key=lambda f: (0 if prefer and f"U.{prefer}." in f[3] else 1))
    for f_off, f_size, field_type, path in hits:
        if prefer and ".U" not in f".{path}"[:3] and path.startswith("U.") and f"U.{prefer}." not in path:
            continue
        return path, f_size, offset - f_off, field_type
    return None


def apply_known_fields(code: str, params: Sequence[Tuple[str, str]], layouts: Dict[str, Sequence[Tuple[int, int, str, str]]]) -> str:
    """Solo per i parametri tipizzati: `*(short *)(p + 0x3a)` -> `p->Health`. Gli altri restano al modello."""
    header_end = code.find("{")
    seen_types = ghidra_parameter_types(code[:header_end]) if header_end > 0 else {}
    for param_type, param in params:
        m = re.match(r"struct\s+(\w+)\s*\*", param_type)
        if not m or m.group(1) not in layouts:
            continue
        if "*" in seen_types.get(param, ""):
            continue  # Per Ghidra `p + n` e' scalato sul suo tipo: non e' un offset in byte.
        fields = layouts[m.group(1)]
        prefer = "UPerson" if "p_person" in param else "UVehicle" if "p_vehicle" in param else ""

        def high_word(match: "re.Match[str]") -> str:
            hit = _field_for(fields, int(match.group(1), 0) + 2, 2, prefer)
            if not hit or hit[1] != 2 or hit[2] != 0:
                return match.group(0)
            # `sar $0x10` estende col segno anche se il campo in C e' senza segno.
            return f"((short){param}->{hit[0]})" if _sign_of(hit[3]) is False else f"{param}->{hit[0]}"

        code = re.sub(rf"\*\(int \*\)\({re.escape(param)} \+ (0x[0-9a-fA-F]+|\d+)\) >> 0x10", high_word, code)

        def access(match: "re.Match[str]") -> str:
            ctype, offset = match.group(1), int(match.group(2), 0)
            size = _ACCESS_SIZES.get(ctype)
            hit = _field_for(fields, offset, size or 1, prefer)
            if not hit or not size:
                return match.group(0)
            path, field_size, delta, field_type = hit
            if field_size == size and delta == 0:
                expression = f"{param}->{path}"
                if _is_written(match):
                    return expression
                if "*" in field_type:  # L'aritmetica di Ghidra sui puntatori e' in byte.
                    return f"((long){expression})"
                wanted, actual = _sign_of(ctype), _sign_of(field_type)
                # Il segno dell'accesso viene dall'assembly, non dal tipo dichiarato nella struct.
                if wanted is not None and actual is not None and wanted != actual:
                    return f"(({ctype}){expression})"
                return expression
            if size < field_size:
                kind = "ubyte" if size == 1 else "ushort"
                return f"((({kind} *)&{param}->{path})[{delta // size}])"
            return match.group(0)

        code = re.sub(rf"\*\((\w+) \*\)\({re.escape(param)} \+ (0x[0-9a-fA-F]+|\d+)\)", access, code)
        for _offset, _size, field_type, path in fields:
            if "*" in field_type:
                code = re.sub(rf"^(\s*{re.escape(param)}->{re.escape(path)} = )(?!0;)(.+);\s*$", rf"\1({field_type})(\2);", code, flags=re.MULTILINE)
    return code


_PIECE_TYPES = {1: "ubyte", 2: "ushort", 4: "int"}
_PIECE_BASE = r"\(\*\(\w+ \*\)(?:&\w+|\(\(long\)&\w+(?: \+ -?0x[0-9a-fA-F]+)?\))\)|\b[A-Za-z_]\w*"


def expand_ghidra_pieces(code: str) -> str:
    """`x._3_1_` e' un pezzo di variabile per Ghidra: in C diventa un accesso per indirizzo."""

    def piece(match: "re.Match[str]") -> str:
        base, offset, size = match.group(1), int(match.group(2)), int(match.group(3))
        address = f"(long)&{base} + {offset}" if offset else f"(long)&{base}"
        if size == 3:
            return f"((*(u32 *)({address})) & 0xFFFFFF)"
        return f"(*({_PIECE_TYPES[size]} *)({address}))" if size in _PIECE_TYPES else match.group(0)

    return re.sub(rf"({_PIECE_BASE})\._(\d+)_(\d+)_\b", piece, code)


def declare_missing_globals(code: str, diagnostics: str, signature: str) -> str:
    """Solo cio' che il codice usa per indirizzo: una variabile locale mancante resta un errore visibile."""
    names = dict.fromkeys(re.findall(r"undeclared identifier '(\w+)'", diagnostics))
    for name in names:
        # `simbolo_2` e' il pezzo di Ghidra a +2 di una globale gia' usata per indirizzo.
        piece = re.fullmatch(r"(\w+?)_(\d+)", name)
        if piece and re.search(rf"&{re.escape(piece.group(1))}\b", code):
            code = re.sub(rf"\b{re.escape(name)}\b", f"(*(ushort *)((long)&{piece.group(1)} + {piece.group(2)}))", code)
    missing = [n for n in names if (n.startswith("data_") or re.search(rf"&{re.escape(n)}\b", code)) and f"extern int {n};" not in code]
    if not missing or signature not in code:
        return code
    return code.replace(signature, "".join(f"extern int {n};\n" for n in missing) + signature, 1)


def declare_unknown_symbols(target: Dict[str, Any], body: str, sources: Sequence[str], inferred: Optional[Dict[str, str]] = None) -> List[str]:
    """Globali note solo all'assembly: `extern` col tipo usato da Ghidra, le chiamate senza prototipo K&R."""
    declared: List[str] = []
    calls = {re.sub(r"^(?:ac_|ASM_)", "", c) for c in re.findall(r"\bcall\s+([A-Za-z_]\w*)", target["asm_code"])}
    for name in dict.fromkeys(re.findall(r"EXPORT_SYMBOL\((\w+)\)", target["asm_code"])):
        if name not in calls and not lookup_declaration(name, sources, inferred) and re.search(rf"\b{re.escape(name)}\b", body):
            declared.append(f"extern int {name};")
    for name in calls:
        if not lookup_declaration(name, sources, inferred) and re.search(rf"\b{re.escape(name)}\s*\(", body):
            declared.append(f"int {name}();")
    return declared


def split_top_level_args(text: str) -> List[str]:
    args, depth, current = [], 0, ""
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            args.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        args.append(current.strip())
    return args


def cast_call_arguments(body: str, name: str, declaration: str) -> str:
    """Gli interi di Ghidra vanno convertiti nei tipi puntatore del prototipo reale."""
    m = re.match(r".*?\b" + re.escape(name) + r"\s*\((.*)\)\s*;?$", declaration, re.DOTALL)
    if not m:
        return body
    params = [] if m.group(1).strip() in ("", "void") else split_top_level_args(m.group(1))
    casts = [re.sub(r"\s*\w+$", "", p).strip() if "*" in p else "" for p in params]
    result, pos = "", 0
    pattern = re.compile(rf"(?<![\w.>]){re.escape(name)}\s*\(")
    while True:
        call = pattern.search(body, pos)
        if not call:
            return result + body[pos:]
        depth, i = 1, call.end()
        while i < len(body) and depth:
            depth += {"(": 1, ")": -1}.get(body[i], 0)
            i += 1
        args = split_top_level_args(body[call.end():i - 1])
        rewritten = [f"({casts[k]})({a})" if k < len(casts) and casts[k] else a for k, a in enumerate(args)]
        result += body[pos:call.start()] + f"{name}({', '.join(rewritten)})"
        pos = i


_SIGNED_C_TYPES = {"int", "long", "short", "char", "sbyte", "s8", "s16", "s32", "ThingIdx"}


def keep_unsigned_parameters(header: str, body: str, params: Sequence[Tuple[str, str]]) -> str:
    """Se Ghidra vede `uint` dove il C dichiara un tipo con segno, i confronti devono restare senza segno."""
    match = re.search(r"\((.*)\)", header, re.DOTALL)
    seen = {part.split()[-1]: part.split()[0] for part in (match.group(1).split(",") if match else []) if len(part.split()) >= 2}
    declarations = []
    for ctype, name in params:
        if seen.get(name) == "u32" and ctype.replace("const", "").strip() in _SIGNED_C_TYPES:
            body = re.sub(rf"(?<![\w.>]){re.escape(name)}\b", f"{name}_u", body)
            declarations.append(f"  u32 {name}_u = (u32){name};\n")
    return body.replace("{\n", "{\n" + "".join(declarations), 1) if declarations else body


def cast_pointer_locals(body: str) -> str:
    """Le globali sono lette come interi: per un puntatore locale l'assegnamento va convertito."""
    for ctype, name in re.findall(r"^\s*((?:struct\s+)?\w+\s*\*+)\s*(\w+);\s*$", body, re.MULTILINE):
        body = re.sub(rf"^(\s*{re.escape(name)} = )(?!\(\s*{re.escape(ctype)}\))(.+);\s*$", rf"\1({ctype})(\2);", body, flags=re.MULTILINE)
    return body


def make_compilable_draft(target: Dict[str, Any], draft: str, sources: Sequence[str], inferred: Optional[Dict[str, str]] = None) -> str:
    """C corretto senza modello: indirizzi come interi, cosi' l'aritmetica in byte di Ghidra resta valida."""
    signature = target["current_c_stub"].split("{")[0].strip()
    return_type, _name, params = parse_signature(target["current_c_stub"])
    header = draft[:draft.index("{")]
    seen_types = ghidra_parameter_types(header)
    body = keep_unsigned_parameters(header, draft[draft.index("{"):], params)

    prefix: List[str] = []
    calls = re.findall(r"\bcall\s+(?:ac_|ASM_)?([A-Za-z_]\w*)", target["asm_code"])
    for name in dict.fromkeys(calls):
        decl = lookup_declaration(name, sources, inferred)
        if decl:
            if name in LIBC_DECLARATIONS:  # Gia' negli header di sistema, e su macOS sono macro.
                pass
            elif decl == (inferred or {}).get(name):
                # Firma ricavata: i tipi degli argomenti non si conoscono, quindi niente controllo.
                prefix.append(f"{decl.split()[0]} {name}();")
                continue
            else:
                prefix.append(decl)
            body = cast_call_arguments(body, name, decl)
            if re.match(rf"[^(]*\*\s*{re.escape(name)}\s*\(", decl):
                body = re.sub(rf"(?<![\w)]){re.escape(name)}\s*\(", f"(long){name}(", body)
    for _type, param in params:
        if "*" in _type:
            seen = seen_types.get(param, "")
            if "*" in seen:
                # Per Ghidra e' un puntatore tipizzato: indici e somme usano la scala del suo tipo.
                if " ".join(_type.replace("*", " * ").split()) != seen:
                    body = re.sub(rf"(?<=\*){re.escape(param)}\b", f"(({seen}){param})", body)
                    body = re.sub(rf"(?<![\w.>&)]){re.escape(param)}\b(?!\s*(?:=(?!=)|->))", f"(({seen}){param})", body)
            else:
                # Dopo la riscrittura dei campi restano solo offset grezzi: anche questi vanno in byte.
                body = re.sub(rf"\(\s*{re.escape(param)}\s*([+-])(?!>)", rf"((long){param} \1", body)
                body = re.sub(rf"(?<![\w>(*&)]){re.escape(param)}(?=\s*[+-](?!>))", f"(long){param}", body)
                body = re.sub(rf"= {re.escape(param)};", f"= (long){param};", body)
            body = re.sub(rf"^(\s*){re.escape(param)}\s*=(?!=)\s*(.+);", rf"\1{param} = ({_type})(\2);", body, flags=re.MULTILINE)
    if "*" in return_type:
        body = re.sub(r"\breturn\s+([^;]+);", rf"return ({return_type})(\1);", body)
    prefix.extend(declare_unknown_symbols(target, body, sources, inferred))
    body = cast_pointer_locals(body)
    return GHIDRA_COMPAT + "".join(d + "\n" for d in prefix) + signature + "\n" + body


_LOCAL_NAME_RE = re.compile(r"\b(?:[a-z]{1,3}Var\d+|local_[0-9a-f]+|aux\w*_\d+|unaff_\w+|extraout_\w+|in_\w+)\b")
_C_RESERVED = {"auto", "break", "case", "char", "const", "continue", "default", "do", "double", "else", "enum", "extern",
               "float", "for", "goto", "if", "int", "long", "register", "return", "short", "signed", "sizeof", "static",
               "struct", "switch", "typedef", "union", "unsigned", "void", "volatile", "while"}


def list_local_names(code: str) -> List[str]:
    return sorted(set(_LOCAL_NAME_RE.findall(code)), key=lambda n: code.index(n))


def build_names_prompt(target: Dict[str, Any], base: str, names: Sequence[str], context: str) -> str:
    body = base[base.rindex(target["current_c_stub"].split("{")[0].strip()):]
    return (
        "This C function was decompiled from a Syndicate Wars routine. Suggest a short meaningful snake_case name for "
        "each local variable below, using the struct fields and calls it touches as hints. Do not rewrite the code.\n"
        'Reply with only one JSON object mapping old name to new name, for example {"iVar1": "tile_x"}.\n\n'
        f"Variables: {', '.join(names)}\n\n{context}\n\n```c\n{body}\n```\n"
    )


def parse_names_reply(content: str, names: Sequence[str], code: str) -> Dict[str, str]:
    """Tiene solo i nomi validi: identificatori nuovi, unici e non riservati."""
    answer = content[content.rfind("</think>") + 8:] if "</think>" in content else content
    match = re.search(r"\{.*\}", answer, re.DOTALL)
    if not match:
        return {}
    try:
        proposed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    existing = set(re.findall(r"\b[A-Za-z_]\w*\b", code))
    accepted: Dict[str, str] = {}
    used = set()
    for old in names:
        new = proposed.get(old)
        if (isinstance(new, str) and re.fullmatch(r"[a-z_][a-z0-9_]*", new) and new not in _C_RESERVED
                and new not in existing and new not in used):
            accepted[old] = new
            used.add(new)
    return accepted


def apply_names(code: str, mapping: Dict[str, str]) -> str:
    """Sostituzione solo a parola intera, mai dentro un accesso a campo: la logica non cambia."""
    for old, new in mapping.items():
        code = re.sub(rf"(?<![\w.>]){re.escape(old)}\b", new, code)
    return code


def call_model(prompt: str, model: str, temperature: float = 0.1) -> Dict[str, Any]:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"num_ctx": REFINE_NUM_CTX, "num_predict": REFINE_NUM_PREDICT, "temperature": temperature},
    }).encode("utf-8")
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=body, headers={"Content-Type": "application/json"})
    # Il Wi-Fi dell'OMEN cade di continuo: il tunnel si ricollega da solo, la richiesta va ripetuta.
    for attempt in range(NETWORK_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=REFINE_TIMEOUT_S) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            if attempt == NETWORK_RETRIES - 1:
                raise
            print(f"[RETE] {exc}: riprovo tra 20 s ({attempt + 1}/{NETWORK_RETRIES})", flush=True)
            time.sleep(20)
    raise RuntimeError("unreachable")


def compile_candidate(target: Dict[str, Any], code: str) -> Tuple[bool, str]:
    original = (SWARS_DIR / target["c_file"]).read_text(encoding="utf-8", errors="replace")
    patched = replace_function_in_c_file(original, target["current_c_stub"], code)
    return verify_c_file_with_clang(SWARS_DIR, target["c_file"], patched) if patched else (False, "stub not found")


def suggest_names(target: Dict[str, Any], base: str, model: str, retries: int = 1) -> Tuple[str, Dict[str, str]]:
    """Il modello propone, il codice applica. Se il risultato non compila resta la bozza."""
    names = list_local_names(base)
    if not names:
        return base, {}
    prompt = build_names_prompt(target, base, names, collect_target_context(SWARS_DIR, target))
    for attempt in range(retries + 1):
        data = call_model(prompt, model, 0.1 + 0.3 * attempt)
        mapping = parse_names_reply(data.get("message", {}).get("content", ""), names, base)
        print(f"[NOMI] {len(mapping)}/{len(names)} accettati ({data.get('eval_count')} token)", flush=True)
        if mapping:
            named = apply_names(base, mapping)
            ok, diagnostics = compile_candidate(target, named)
            if ok:
                return named, mapping
            print(f"[NOMI] scartati, non compila: {diagnostics[:200]}", flush=True)
    return base, {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("functions", nargs="*")
    parser.add_argument("--all", action="store_true", help="tutta la coda")
    parser.add_argument("--no-names", action="store_true", help="solo Ghidra e bozza, senza modello")
    parser.add_argument("--model", default=REFINE_MODEL)
    args = parser.parse_args()
    targets = {t["func_name"]: t for t in load_jsonl(PENDING_PATH)}
    selected = list(targets.values()) if args.all else [targets[n] for n in args.functions]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Ghidra su {len(selected)} funzioni...", flush=True)
    decompiled, symbols, inferred = run_ghidra(selected)
    INFERRED_SIGNATURES_PATH.write_text(json.dumps(inferred, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Firme ricavate da Ghidra: {len(inferred)}", flush=True)
    summary: Dict[str, Any] = {}
    for target in selected:
        name = target["func_name"]
        entry = decompiled.get(name, {})
        raw = entry.get("code", "")
        if not raw or raw.startswith("// ERRORE"):
            print(f"RISULTATO {name}: Ghidra non ha prodotto codice", flush=True)
            summary[name] = {"status": "no_ghidra"}
            continue
        _rt, _n, params = parse_signature(target["current_c_stub"])
        layouts = {s: load_struct_layout(SWARS_DIR, s) for s in set(re.findall(r"struct\s+(\w+)\s*\*", target["current_c_stub"].split("{")[0]))}
        draft = expand_ghidra_pieces(apply_known_fields(clean_ghidra_c(raw, symbols, entry.get("global_sizes")), params, layouts))
        base = make_compilable_draft(target, draft, load_sources(target["c_file"]), inferred)
        ok, diagnostics = compile_candidate(target, base)
        for _ in range(3):
            repaired = declare_missing_globals(base, diagnostics, target["current_c_stub"].split("{")[0].strip()) if not ok else base
            if repaired == base:
                break
            base = repaired
            ok, diagnostics = compile_candidate(target, base)
        (OUTPUT_DIR / f"{name}.base.c").write_text(base + "\n", encoding="utf-8")
        if not ok:
            print(f"RISULTATO {name}: bozza non compilabile: {diagnostics[:200]}", flush=True)
            summary[name] = {"status": "base_failed", "error": diagnostics[:500]}
            continue
        mapping: Dict[str, str] = {}
        named = base
        if not args.no_names:
            try:
                named, mapping = suggest_names(target, base, args.model)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                print(f"[NOMI] rete non disponibile, resta la bozza: {exc}", flush=True)
        (OUTPUT_DIR / f"{name}.c").write_text(named + "\n", encoding="utf-8")
        summary[name] = {"status": "compiled", "names": mapping}
        print(f"RISULTATO {name}: compila, {len(mapping)} nomi", flush=True)
    (OUTPUT_DIR / "_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    done = sum(1 for v in summary.values() if v["status"] == "compiled")
    print(f"TOTALE: {done} su {len(selected)} compilano", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
