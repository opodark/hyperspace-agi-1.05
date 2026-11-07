#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Applica ai sorgenti di Syndicate Wars le bozze verificate, sostituendo gli stub che chiamano l'assembly.

Lavora sulla copia di lavoro del repository indicato da --repo. Ogni file toccato include `drafts_link.h`
(adattatori verso l'assembly rimasto), il blocco di compatibilita' di Ghidra diventa `ghidra_compat.h`.
Scelta delle bozze: verdetto `agree` del verificatore oppure correzione a mano in `manual/`, meno `--exclude`.

Uso:
    python scripts/syndwars_apply.py --repo /percorso/syndwars-remake --list
    python scripts/syndwars_apply.py --repo /percorso/syndwars-remake [--only f g] [--exclude h]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DRAFTS = ROOT / "data" / "nightly" / "syndwars_ghidra"
MANUAL = DRAFTS / "manual"
PENDING = ROOT / "data" / "syndwars_pending_targets.jsonl"
COMPAT_HEADER = "ghidra_compat.h"
LINK_HEADER = "drafts_link.h"
TAIL_MARK = "/* Collegamento delle bozze"
# Diverse o non chiarite nel gioco vero: restano in assembly finche' non sono spiegate.
DEFAULT_EXCLUDE = {"mech_unkn_func_12", "create_a_pod", "explode_thing_building"}


def split_compat(code: str) -> Tuple[str, str]:
    """(blocco di compatibilita', resto): il blocco va da `#ifndef GHIDRA_COMPAT_H` al suo `#endif`."""
    start = code.find("#ifndef GHIDRA_COMPAT_H")
    if start < 0:
        return "", code
    depth = 0
    position = start
    for match in re.finditer(r"^[ \t]*#[ \t]*(ifndef|ifdef|if|endif)\b.*$", code[start:], re.MULTILINE):
        depth += -1 if match.group(1) == "endif" else 1
        if depth == 0:
            position = start + match.end()
            return code[start:position] + "\n", code[:start] + code[position:]
    raise ValueError("blocco di compatibilita' senza #endif")


def choose(results: Iterable[Dict], manual: Iterable[str], exclude: Iterable[str]) -> List[str]:
    manual_set, excluded = set(manual), set(exclude)
    return sorted(r["func"] for r in results
                  if (r.get("verdict") == "agree" or r["func"] in manual_set) and r["func"] not in excluded)


def replace_stub(text: str, stub: str, code: str) -> str:
    if stub not in text:
        raise KeyError("stub non trovato")
    return text.replace(stub, code, 1)


def add_includes(text: str) -> str:
    """Il collegamento va prima di tutto: i suoi #define devono valere anche nelle dichiarazioni del file."""
    if f'#include "{LINK_HEADER}"' in text:
        return text
    return f'#include "{LINK_HEADER}"\n' + text


def apply_drafts(repo: Path, names: List[str]) -> Dict[str, List[str]]:
    from scripts.syndwars_decompile_sovereign import load_jsonl

    targets = {t["func_name"]: t for t in load_jsonl(PENDING)}
    by_file: Dict[str, List[str]] = {}
    for name in names:
        by_file.setdefault(targets[name]["c_file"], []).append(name)
    compat = ""
    skipped: List[str] = []
    applied: List[str] = []
    for c_file, functions in sorted(by_file.items()):
        path = repo / c_file
        text = path.read_text(errors="replace")
        for name in functions:
            manual = MANUAL / f"{name}.base.c"
            code = (manual if manual.exists() else DRAFTS / f"{name}.base.c").read_text().strip()
            block, rest = split_compat(code)
            compat = compat or block
            try:
                text = replace_stub(text, targets[name]["current_c_stub"], f'#include "{COMPAT_HEADER}"\n' + rest.strip())
                applied.append(name)
            except KeyError:
                skipped.append(name)
        path.write_text(add_includes(text))
    (repo / "src" / COMPAT_HEADER).write_text("/* Tipi e macro usati dal codice ricavato da Ghidra. */\n" + compat)
    link = repo / "src" / LINK_HEADER
    if not link.exists():
        link.write_text("/* Adattatori verso l'assembly rimasto: generato da scripts/syndwars_link.py */\n")
    return {"applicate": applied, "stub_non_trovato": skipped, "file": sorted(by_file)}


def wrapper_line(declaration: str) -> Optional[str]:
    """Riga di `conf/wrappers_game.conf` per una firma ricavata: convenzione Watcom, tipo di ritorno, argomenti."""
    match = re.match(r"\s*(\w+)\s+(\w+)\s*\((.*)\)\s*;?\s*$", declaration, re.DOTALL)
    if not match:
        return None
    return_type, name, params = match.groups()
    count = 0 if params.strip() in ("", "void") else params.count(",") + 1
    kind = "v" if return_type == "void" else "i"
    return f"{name}\t\t\tW\t{kind}" + (f"\t{'i' * count}" if count else "")


def redirect_asm_calls(sx_text: str, name: str) -> Tuple[str, int, List[str]]:
    """Le chiamate assembly a `name` passano dal C: (testo, quante, altri riferimenti che non si possono deviare)."""
    tail_at = sx_text.find(TAIL_MARK)
    body, tail = (sx_text, "") if tail_at < 0 else (sx_text[:tail_at], sx_text[tail_at:])
    body, count = re.subn(rf"(\b(?:call|jmp)\s+){re.escape(name)}\b", rf"\1ac_{name}", body)
    # Il simbolo globale ora e' la funzione C: quello assembly resta solo come etichetta locale.
    body = re.sub(rf"^GLOBAL_FUNC\(\s*{re.escape(name)}\s*\)", f"{name}:", body, flags=re.MULTILINE)
    others = [line.strip() for line in body.split("\n")
              if re.search(rf"(?<![\w.]){re.escape(name)}\b", line.split("/*")[0]) and not re.match(rf"\s*{re.escape(name)}:", line)]
    return body + tail, count, others


def remove_adapter(sx_text: str, name: str) -> str:
    """Toglie l'adattatore `name__c` dalla coda: la bozza ora chiama direttamente la funzione C."""
    return re.sub(rf"^\t\.global {re.escape(name)}__c\n{re.escape(name)}__c:\n.*?^\tret\n", "", sx_text,
                  count=1, flags=re.MULTILINE | re.DOTALL)


def reconcile_declarations(text: str) -> str:
    """Toglie le dichiarazioni senza argomenti in conflitto con un prototipo vero dello stesso file."""
    typed: Dict[str, str] = {}
    for match in re.finditer(r"^((?:[A-Za-z_]\w*[ \t\*]+)+?)([A-Za-z_]\w*)\s*\((?!\s*\))[^;{}]*\)\s*;", text, re.MULTILINE):
        typed.setdefault(match.group(2), " ".join(match.group(1).split()))

    def fix(match: "re.Match[str]") -> str:
        known = typed.get(match.group(2))
        return "" if known and known != " ".join(match.group(1).split()) else match.group(0)

    return re.sub(r"^((?:[A-Za-z_]\w*[ \t\*]+)+?)([A-Za-z_]\w*)\s*\(\s*\)\s*;\n", fix, text, flags=re.MULTILINE)


def forward_structs(chunks: Iterable[str]) -> str:
    """Una `struct X` citata per la prima volta in un prototipo vale solo li': due prototipi uguali risulterebbero diversi."""
    names = sorted({name for chunk in chunks for name in re.findall(r"\bstruct\s+(\w+)\s*\*", chunk)})
    return "".join(f"struct {name};\n" for name in names)


def promote_local(repo: Path, names: Sequence[str], signatures: Dict[str, str]) -> Dict[str, Any]:
    """Porta in C le funzioni assembly locali verificate: definizione nel file C, thunk `ac_` e chiamate assembly deviate.

    L'assembly resta nel file finche' `syndwars_deadcode.py` non vede che nessuno lo raggiunge piu'. Una funzione con
    riferimenti che non siano `call` o `jmp` (tabelle di puntatori, indirizzi) resta in assembly."""
    from scripts.syndwars_decompile_sovereign import load_jsonl

    targets = {t["func_name"]: t for t in load_jsonl(PENDING)}
    sx_path = repo / "src" / "swars.sx"
    sx_text = sx_path.read_text(errors="replace")
    link_path = repo / "src" / LINK_HEADER
    link_text = link_path.read_text()
    conf_path = repo / "conf" / "wrappers_game.conf"
    conf_text = conf_path.read_text()
    promoted: List[str] = []
    refused: Dict[str, str] = {}
    additions: Dict[str, List[str]] = {}
    wrappers: Dict[str, Tuple[Tuple[str, str], ...]] = {}
    for name in names:
        target = targets[name]
        wrapper_text = target.get("wrapper_text")
        head = target["current_c_stub"].split("{")[0].strip() + ";" if wrapper_text else signatures.get(name, "")
        line = wrapper_line(head)
        if line is None:
            refused[name] = "firma non leggibile"
            continue
        new_text, _count, others = redirect_asm_calls(sx_text, name)
        if others:
            refused[name] = "riferimento non deviabile: " + others[0][:60]
            continue
        if re.search(rf"^{re.escape(name)}\s", conf_text, re.MULTILINE):
            refused[name] = "gia' nei thunk"
            continue
        sx_text = remove_adapter(new_text, name)
        link_text = re.sub(rf"^#define {re.escape(name)} {re.escape(name)}__c\n", "", link_text, flags=re.MULTILINE)
        conf_text += line + "\n"
        manual = MANUAL / f"{name}.base.c"
        code = (manual if manual.exists() else DRAFTS / f"{name}.base.c").read_text()
        _block, rest = split_compat(code)
        additions.setdefault(target["c_file"], []).append(f'#include "{COMPAT_HEADER}"\n' + rest.strip())
        if wrapper_text:
            wrappers[target["c_file"]] = wrappers.get(target["c_file"], ()) + ((wrapper_text, head + "\n"),)
        promoted.append(name)
    for c_file, chunks in additions.items():
        path = repo / c_file
        text = path.read_text(errors="replace")
        for old, new in wrappers.get(c_file, ()):  # il `static inline` verso l'assembly lascia il posto a un prototipo
            if old not in text:
                raise KeyError(f"wrapper non trovato in {c_file}: {new.strip()}")
            text = text.replace(old, new, 1)
        text = text.rstrip("\n") + "\n\n" + forward_structs(chunks) + "\n\n".join(chunks) + "\n"
        path.write_text(reconcile_declarations(add_includes(text)))
    sx_path.write_text(sx_text)
    link_path.write_text(link_text)
    conf_path.write_text(conf_text)
    return {"portate": promoted, "rifiutate": refused, "file": sorted(additions)}


def build_subset_tar(worktree: Path, names: List[str], all_files: List[str], link_dir: Path, tar_path: Path) -> None:
    """Riporta `worktree` a HEAD, applica `names` con il collegamento completo e impacchetta sempre gli stessi file."""
    import subprocess
    import tarfile

    subprocess.run(["git", "-C", str(worktree), "checkout", "-q", "."], check=True)
    subprocess.run(["git", "-C", str(worktree), "clean", "-fdq", "src"], check=True)
    save = worktree / "src" / "game_save.c"
    text = save.read_text(errors="replace")
    marker = "extern ubyte save_crypto_data_state[3];\n"
    if "save_hashtbl_01" not in text:
        save.write_text(text.replace(marker, marker + "extern ulong save_hashtbl_01[56];\nextern ulong save_hashtbl_02[56];\n"
                                     "extern ulong save_hashtbl_03[56];\nextern ulong save_hashtbl_verify_code;\n", 1))
    apply_drafts(worktree, names)
    (worktree / "src" / LINK_HEADER).write_text((link_dir / LINK_HEADER).read_text())
    with open(worktree / "src" / "swars.sx", "a") as asm:
        asm.write((link_dir / "drafts_link_tail.sx").read_text())
    with tarfile.open(tar_path, "w") as archive:
        for rel in all_files + [f"src/{COMPAT_HEADER}", f"src/{LINK_HEADER}", "src/swars.sx"]:
            archive.add(worktree / rel, arcname=rel)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--exclude", nargs="*", default=[])
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--report", default="")
    parser.add_argument("--promote", nargs="*", help="funzioni locali verificate da portare in C")
    args = parser.parse_args()
    if args.promote is not None:
        signatures = json.loads((DRAFTS / "_inferred_signatures.json").read_text())
        report = promote_local(Path(args.repo), args.promote, signatures)
        if args.report:
            Path(args.report).write_text(json.dumps(report, indent=1))
        print(f"portate {len(report['portate'])}, rifiutate {report['rifiutate'] or 'nessuna'}, file {len(report['file'])}")
        return 0
    results = json.loads((DRAFTS / "_verify_all.json").read_text())
    manual = [p.name.replace(".base.c", "") for p in MANUAL.glob("*.base.c")]
    names = choose(results, manual, DEFAULT_EXCLUDE | set(args.exclude))
    if args.only is not None:
        names = [n for n in args.only if n in names]
    if args.list:
        print(len(names), " ".join(names))
        return 0
    report = apply_drafts(Path(args.repo), names)
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=1))
    print(f"applicate {len(report['applicate'])}, stub non trovato {report['stub_non_trovato'] or 'nessuno'}, file {len(report['file'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
