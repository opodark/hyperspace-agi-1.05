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
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DRAFTS = ROOT / "data" / "nightly" / "syndwars_ghidra"
MANUAL = DRAFTS / "manual"
PENDING = ROOT / "data" / "syndwars_pending_targets.jsonl"
COMPAT_HEADER = "ghidra_compat.h"
LINK_HEADER = "drafts_link.h"
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
    args = parser.parse_args()
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
