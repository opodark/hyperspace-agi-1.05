#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Collegamento delle bozze C con le funzioni e i dati che esistono solo in assembly.

Una bozza chiama `VNAV_goto(...)` o legge `save_hashtbl_01`, ma nel progetto quei nomi sono etichette
locali di `swars.sx` e con la convenzione Watcom: il linker non li vede. Dal log di collegamento ricava
i simboli mancanti e produce:
  - un'intestazione con `#define NOME NOME__c`, da includere per prima nei file C modificati;
  - un testo assembly da accodare a `swars.sx`: `.global` per i dati e, per ogni funzione, un adattatore
    `NOME__c` che passa dalla convenzione cdecl di gcc a quella Watcom (eax, edx, ebx, ecx, poi stack).

Uso:
    python scripts/syndwars_link.py --log /tmp/s192.log --sx src/swars.sx --out /tmp/link
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SUFFIX = "__c"
REGISTER_ARGS = ("eax", "edx", "ebx", "ecx")
UNDEFINED = re.compile(r"undefined reference to [`']([A-Za-z_][A-Za-z0-9_]*)'")


def undefined_symbols(link_log: str) -> List[str]:
    """Simboli non definiti, senza ripetizioni, nell'ordine in cui compaiono."""
    seen: Dict[str, None] = {}
    for name in UNDEFINED.findall(link_log):
        seen.setdefault(name)
    return list(seen)


def parameter_count(declaration: str) -> Optional[int]:
    """Numero di parametri di una dichiarazione C; None se non e' leggibile."""
    match = re.search(r"\((.*)\)\s*;?\s*$", declaration.strip(), re.DOTALL)
    if not match:
        return None
    body = match.group(1).strip()
    if body in ("", "void"):
        return 0
    depth = 0
    count = 1
    for char in body:
        depth += char == "("
        depth -= char == ")"
        count += char == "," and not depth
    return count


def is_function(name: str, drafts: Iterable[str], declarations: Dict[str, str]) -> bool:
    """Funzione se una bozza la chiama o se ne esiste una dichiarazione."""
    if name in declarations:
        return True
    call = re.compile(rf"\b{re.escape(name)}\s*\(")
    return any(call.search(code) for code in drafts)


def assembly_target(name: str, sx_texts: Iterable[str]) -> Optional[str]:
    """Etichetta da chiamare: il nome locale in swars.sx oppure `ASM_nome` se e' globale altrove."""
    texts = list(sx_texts)
    if texts and re.search(rf"^\s*(?:GLOBAL_FUNC\(\s*{re.escape(name)}\s*\)|{re.escape(name)}:)", texts[0], re.MULTILINE):
        return name
    pattern = rf"^\s*GLOBAL_FUNC\s*\(\s*ASM_{re.escape(name)}\s*\)"
    if any(re.search(pattern, text, re.MULTILINE) for text in texts):
        return f"ASM_{name}"
    return None


def count_from_return(target: str, sx_texts: Iterable[str]) -> Optional[int]:
    """Senza firma: i quattro registri piu' gli argomenti sullo stack letti da `ret $n`.

    Per eccesso: se gli argomenti reali sono meno di quattro, i registri in piu' portano valori inutili."""
    from scripts.syndwars_ghidra import stack_args_from_assembly

    for text in sx_texts:
        stack = stack_args_from_assembly(target, text)
        if stack is not None:
            return 4 + stack
    return None


C_KEYWORDS = {"if", "while", "for", "switch", "return", "sizeof", "defined"}
HELPER_MACROS = re.compile(r"^(CONCAT|SUB4|SBORROW|SCARRY|CARRY|POPCOUNT)")
_PROTOTYPE = r"^[A-Za-z_][\w\s\*]*?\b{name}\s*\(([^;{{}}]*)\)\s*;"


def c_function_definitions(c_texts: Iterable[str]) -> set:
    """Nomi di funzioni definite in C con collegamento esterno (non `static`)."""
    names = set()
    for text in c_texts:
        for match in re.finditer(r"^(?!static)[A-Za-z_][\w\s\*]*?\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\n?\{", text, re.MULTILINE):
            names.add(match.group(1))
    return names


def asm_global_functions(sx_texts: Iterable[str]) -> set:
    names = set()
    for text in sx_texts:
        names |= set(re.findall(r"GLOBAL_FUNC\s*\(\s*(\w+)\s*\)", text))
    return names


def asm_only_callees(drafts: Iterable[str], sx_texts: Iterable[str], c_texts: Iterable[str]) -> List[str]:
    """Funzioni chiamate dalle bozze che esistono solo come simbolo globale assembly (convenzione Watcom).

    Il linker le risolve da solo, quindi non compaiono fra i simboli non definiti, ma la bozza le chiama in
    cdecl: servono comunque un adattatore e un `#define`. Capita con le funzioni che il progetto richiama solo
    tramite un `static inline` con `asm volatile`."""
    only_asm = asm_global_functions(sx_texts) - c_function_definitions(c_texts)
    found: Dict[str, None] = {}
    for draft in drafts:
        for match in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", draft):
            name = match.group(1)
            if name in only_asm and name not in C_KEYWORDS and not HELPER_MACROS.match(name):
                found.setdefault(name)
    return sorted(found)


def prototype_from_drafts(name: str, drafts: Iterable[str]) -> Optional[str]:
    """Il prototipo che le bozze stesse dichiarano per `name`."""
    pattern = re.compile(_PROTOTYPE.format(name=re.escape(name)), re.MULTILINE)
    for draft in drafts:
        for match in pattern.finditer(draft):
            if match.group(1).strip():  # `()` e' una dichiarazione K&R: il numero di parametri non e' noto
                return match.group(0)
    return None


def adapter(name: str, target: str, count: int) -> str:
    """Adattatore cdecl -> Watcom. Salva ebx, esi, edi, ebp e rimette lo stack a posto dopo la chiamata."""
    stack = max(0, count - 4)
    lines = [
        f"\t.global {name}{SUFFIX}",
        f"{name}{SUFFIX}:",
        "\tpush   %ebx", "\tpush   %esi", "\tpush   %edi", "\tpush   %ebp",
        "\tmov    %esp,%ebp",
    ]
    for _ in range(stack):
        lines.append(f"\tpushl  {16 + 4 * count}(%esp)")
    for index, register in enumerate(REGISTER_ARGS[:min(count, 4)]):
        lines.append(f"\tmov    {20 + 4 * index + 4 * stack}(%esp),%{register}")
    lines += [
        f"\tcall   {target}",
        "\tmov    %ebp,%esp",
        "\tpop    %ebp", "\tpop    %edi", "\tpop    %esi", "\tpop    %ebx",
        "\tret",
    ]
    return "\n".join(lines)


def build_link_pack(symbols: List[str], sx_texts: List[str], drafts: List[str],
                    declarations: Dict[str, str]) -> Tuple[str, str, Dict[str, List[str]]]:
    """(intestazione, testo assembly, simboli non risolti per motivo)."""
    header: List[str] = []
    asm: List[str] = ["", "/* Collegamento delle bozze: generato da scripts/syndwars_link.py */", "\t.text"]
    unresolved: Dict[str, List[str]] = {"senza_target": [], "senza_firma": [], "dato_non_trovato": []}
    sx = sx_texts[0] if sx_texts else ""
    for name in symbols:
        if is_function(name, drafts, declarations):
            target = assembly_target(name, sx_texts)
            count = parameter_count(declarations.get(name, ""))
            if count is None and target is not None:
                count = count_from_return(target, sx_texts)
            if target is None:
                unresolved["senza_target"].append(name)
            elif count is None:
                unresolved["senza_firma"].append(name)
            else:
                header.append(f"#define {name} {name}{SUFFIX}")
                asm.append(adapter(name, target, count))
        elif re.search(rf"^\s*{re.escape(name)}:", sx, re.MULTILINE):
            asm.append(f"\t.global {name}")
        else:
            unresolved["dato_non_trovato"].append(name)
    guard = "SYNDWARS_DRAFTS_LINK_H"
    text = f"#ifndef {guard}\n#define {guard}\n" + "\n".join(header) + f"\n#endif\n"
    return text, "\n".join(asm) + "\n", unresolved


def extend_link_pack(header: str, sx_text: str, new_symbols: List[str], sx_texts: List[str], drafts: List[str],
                     declarations: Dict[str, str]) -> Tuple[str, str, Dict[str, List[str]]]:
    """Aggiunge a intestazione e assembly gia' applicati i soli simboli nuovi: (intestazione, assembly, irrisolti)."""
    known = set(re.findall(r"^#define (\w+) \1" + SUFFIX, header, re.MULTILINE))
    known |= set(re.findall(r"^\t\.global (\w+)$", sx_text[sx_text.find("/* Collegamento delle bozze"):], re.MULTILINE))
    todo = [name for name in new_symbols if name not in known]
    added_header, added_asm, unresolved = build_link_pack(todo, sx_texts, drafts, declarations)
    defines = re.findall(r"^#define (\w+ \w+" + SUFFIX + r")$", added_header, re.MULTILINE)
    lines = "".join(f"#define {define}\n" for define in defines)
    position = header.rfind("#endif")
    return header[:position] + lines + header[position:], sx_text.rstrip("\n") + "\n" + added_asm, unresolved


def load_declarations(inferred_path: Path) -> Dict[str, str]:
    """Firme ricavate da Ghidra per le funzioni solo assembly."""
    import json

    declarations: Dict[str, str] = {}
    if inferred_path.exists():
        declarations.update(json.loads(inferred_path.read_text(encoding="utf-8")))
    return declarations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", default="", help="log di make con gli `undefined reference`")
    parser.add_argument("--sx", default="", help="src/swars.sx")
    parser.add_argument("--extra-sx", nargs="*", default=[], help="altri file .sx con funzioni globali ASM_")
    parser.add_argument("--drafts", default=str(ROOT / "data/nightly/syndwars_ghidra"))
    parser.add_argument("--signatures", default=str(ROOT / "data/nightly/syndwars_ghidra/_inferred_signatures.json"))
    parser.add_argument("--project-src", default="", help="cartella src del progetto, per le firme scritte a mano e le definizioni C")
    parser.add_argument("--out", default="")
    parser.add_argument("--extend", default="", help="repository a cui aggiungere i simboli nuovi, invece di scrivere in --out")
    parser.add_argument("--names", nargs="*", default=[], help="con --extend: le funzioni appena portate in C")
    args = parser.parse_args()

    if args.extend:
        repo = Path(args.extend)
        sx_path, header_path = repo / "src" / "swars.sx", repo / "src" / "drafts_link.h"
        sx_text = sx_path.read_text(errors="replace")
        sx_all = [sx_text] + [Path(p).read_text(errors="replace") for p in args.extra_sx]
        drafts = [(Path(args.drafts) / f"{name}.base.c").read_text(errors="replace") for name in args.names]
        c_texts = [p.read_text(errors="replace") for p in (repo / "src").glob("*.c")]
        symbols = undefined_symbols(Path(args.log).read_text(errors="replace")) if args.log else []
        for name in asm_only_callees(drafts, sx_all, c_texts):
            if name not in symbols:
                symbols.append(name)
        declarations = load_declarations(Path(args.signatures))
        for name in symbols:
            found = prototype_from_drafts(name, drafts)
            if found and name not in declarations:
                declarations[name] = found
        header, new_sx, unresolved = extend_link_pack(header_path.read_text(), sx_text, symbols, sx_all, drafts, declarations)
        header_path.write_text(header)
        sx_path.write_text(new_sx)
        print(f"simboli considerati {len(symbols)}, irrisolti { {k: v for k, v in unresolved.items() if v} or 'nessuno'}")
        return 0
    if not args.out or not args.log:
        parser.error("servono --log e --out, oppure --extend")

    symbols = undefined_symbols(Path(args.log).read_text(errors="replace"))
    sx_texts = [Path(args.sx).read_text(errors="replace")] + [Path(p).read_text(errors="replace") for p in args.extra_sx]
    manual = {p.name: p for p in (Path(args.drafts) / "manual").glob("*.base.c")}  # correzioni a mano: hanno la precedenza
    drafts = [manual.get(p.name, p).read_text(errors="replace") for p in Path(args.drafts).glob("*.base.c")]
    declarations = load_declarations(Path(args.signatures))
    if args.project_src:
        for path in Path(args.project_src).glob("*.h"):
            text = path.read_text(errors="replace")
            for name in symbols:
                if name in declarations:
                    continue
                found = re.search(rf"^[A-Za-z_][\w\s\*]*\b{re.escape(name)}\s*\([^;{{}}]*\)\s*;", text, re.MULTILINE)
                if found:
                    declarations[name] = found.group(0)
    for name in symbols:
        if name not in declarations:
            declaration = prototype_from_drafts(name, drafts)
            if declaration:
                declarations[name] = declaration
    if args.project_src:
        c_texts = [p.read_text(errors="replace") for p in Path(args.project_src).glob("*.c")]
        for name in asm_only_callees(drafts, sx_texts, c_texts):
            if name not in symbols:
                symbols.append(name)
                print(f"  chiamata a funzione globale solo assembly, aggiunta: {name}")
            if name not in declarations:
                declaration = prototype_from_drafts(name, drafts)
                if declaration:
                    declarations[name] = declaration
    header, asm, unresolved = build_link_pack(symbols, sx_texts, drafts, declarations)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "drafts_link.h").write_text(header, encoding="utf-8")
    (out / "drafts_link_tail.sx").write_text(asm, encoding="utf-8")
    resolved = len(symbols) - sum(len(v) for v in unresolved.values())
    print(f"simboli mancanti {len(symbols)}, risolti {resolved}")
    for reason, names in unresolved.items():
        if names:
            print(f"  {reason} ({len(names)}): {' '.join(names[:12])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
