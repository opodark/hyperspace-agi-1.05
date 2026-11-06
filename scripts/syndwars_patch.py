#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Innesta un sottoinsieme di bozze nei sorgenti di syndwarsfx e produce un tar pronto da estrarre.

Le bozze sostituiscono lo stub della funzione nel file .c all'ultimo commit (HEAD): il lavoro in corso
nella cartella del gioco non viene toccato. I file che l'utente ha modificato a mano e non committato
(`src/game_save.c`) si leggono dalla copia di lavoro.

Uso:
    python scripts/syndwars_patch.py --out /tmp/sub.tar --funcs remove_thing add_node_thing
    python scripts/syndwars_patch.py --out /tmp/solid.tar --solid
"""
from __future__ import annotations

import argparse
import collections
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.syndwars_decompile_sovereign import PENDING_PATH, SWARS_DIR, load_jsonl, replace_function_in_c_file  # noqa: E402

DRAFTS = ROOT / "data" / "nightly" / "syndwars_ghidra"
MANUAL = DRAFTS / "manual"  # bozze corrette a mano: hanno la precedenza su quelle generate
WORKTREE_FILES = {"src/game_save.c"}
LINK_INCLUDE = '#include "drafts_link.h"\n'


def is_solid(result: Dict) -> bool:
    mutants = result.get("mutants")
    return bool(result["verdict"] == "agree" and mutants and result["coverage"] >= 0.9 and mutants["killed"] >= 5
                and not mutants["unbuilt"] and not result["undefined_input"] and result["agreed"] == 400)


def committed_text(c_file: str) -> str:
    if c_file in WORKTREE_FILES:
        return (SWARS_DIR / c_file).read_text(errors="replace")
    done = subprocess.run(["git", "-C", str(SWARS_DIR), "show", f"HEAD:{c_file}"], capture_output=True, check=True)
    return done.stdout.decode(errors="replace")


def solid_functions() -> List[str]:
    results = json.loads((DRAFTS / "_verify_all.json").read_text())
    return [r["func"] for r in results if is_solid(r)]


def build_tar(funcs: Iterable[str], out: Path, link_include: bool = True) -> Dict[str, List[str]]:
    """Scrive il tar e dice quali funzioni non si sono potute innestare."""
    targets = {t["func_name"]: t for t in load_jsonl(PENDING_PATH)}
    by_file: Dict[str, List[str]] = collections.defaultdict(list)
    for name in funcs:
        by_file[targets[name]["c_file"]].append(name)
    skipped: List[str] = []
    with tarfile.open(out, "w") as archive:
        for c_file, names in sorted(by_file.items()):
            text = committed_text(c_file)
            for name in names:
                manual = MANUAL / f"{name}.base.c"
                code = (manual if manual.exists() else DRAFTS / f"{name}.base.c").read_text().strip()
                new = replace_function_in_c_file(text, targets[name]["current_c_stub"], code)
                if new:
                    text = new
                else:
                    skipped.append(name)
            if link_include:
                text = LINK_INCLUDE + text
            data = text.encode()
            info = tarfile.TarInfo(c_file)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return {"files": sorted(by_file), "non_innestate": skipped}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--funcs", nargs="+")
    group.add_argument("--solid", action="store_true", help="solo le bozze con prova forte")
    group.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if args.solid:
        funcs = solid_functions()
    elif args.all:
        funcs = [r["func"] for r in json.loads((DRAFTS / "_verify_all.json").read_text())]
    else:
        funcs = args.funcs
    report = build_tar(funcs, Path(args.out))
    print(f"{len(funcs)} funzioni, {len(report['files'])} file, non innestate: {report['non_innestate'] or 'nessuna'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
