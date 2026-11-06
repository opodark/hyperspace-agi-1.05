#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Cerca per bisezione le bozze che fanno divergere il gioco vero dall'originale.

Per ogni sottoinsieme costruisce il tar delle bozze (scripts/syndwars_patch.py), lo carica con `--upload`,
lo valuta con `--eval` (compilazione + replay fino al turno 400 + confronto) e legge la riga
`RISULTATO <nome> IDENTICO|DIVERSO|BUILD_FALLITA|NESSUN_DUMP ...`. Trova un colpevole alla volta, lo toglie
dall'insieme e riprova, finche' il resto coincide con l'originale.

    python scripts/syndwars_bisect.py --solid --workdir /tmp/bis \\
        --upload 'scp -q {tar} utente@host:C:/sets/{name}.tar' --eval './evalset_run.sh {name}'
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Dict, FrozenSet, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RESULT = re.compile(r"RISULTATO\s+(\S+)\s+(\S+)(.*)")


class EvalError(RuntimeError):
    pass


def parse_result(output: str, name: str) -> Tuple[str, str]:
    """(esito, dettaglio) dall'ultima riga RISULTATO del nome dato."""
    found = [m for m in RESULT.finditer(output) if m.group(1) == name]
    if not found:
        raise EvalError(f"nessun risultato per {name}: {output[-300:]!r}")
    last = found[-1]
    return last.group(2), last.group(3).strip()


def find_culprits(funcs: List[str], is_bad: Callable[[List[str]], bool], log: Callable[[str], None] = print,
                  limit: int = 20) -> Tuple[List[str], List[List[str]]]:
    """Colpevoli singoli e gruppi che divergono solo insieme."""
    rest = list(funcs)
    culprits: List[str] = []
    interactions: List[List[str]] = []
    while rest and len(culprits) + len(interactions) < limit and is_bad(rest):
        current = rest
        while len(current) > 1:
            half = len(current) // 2
            first, second = current[:half], current[half:]
            if is_bad(first):
                current = first
            elif is_bad(second):
                current = second
            else:
                log(f"interazione: {len(current)} bozze divergono solo insieme")
                interactions.append(current)
                break
        if len(current) == 1:
            log(f"colpevole: {current[0]}")
            culprits.append(current[0])
        rest = [f for f in rest if f not in current]
    return culprits, interactions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--upload", required=True, help="comando con {tar} e {name}")
    parser.add_argument("--eval", required=True, dest="evaluate", help="comando con {name}")
    parser.add_argument("--worktree", help="albero git su cui applicare le bozze con syndwars_apply.py")
    parser.add_argument("--link-dir", help="cartella con drafts_link.h e drafts_link_tail.sx completi")
    parser.add_argument("--all-files", help="file con l'elenco dei sorgenti da impacchettare sempre")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--funcs", nargs="+")
    group.add_argument("--funcs-file", help="un nome per riga")
    group.add_argument("--solid", action="store_true")
    group.add_argument("--all", action="store_true")
    args = parser.parse_args()

    from scripts.syndwars_patch import DRAFTS, build_tar, solid_functions

    funcs = (solid_functions() if args.solid
             else [r["func"] for r in json.loads((DRAFTS / "_verify_all.json").read_text())] if args.all
             else Path(args.funcs_file).read_text().split() if args.funcs_file
             else args.funcs)
    work = Path(args.workdir)
    work.mkdir(parents=True, exist_ok=True)
    cache: Dict[FrozenSet[str], bool] = {}
    started = time.time()
    counter = [0]

    def log(message: str) -> None:
        print(f"[{time.time() - started:6.0f}s] {message}", flush=True)

    def is_bad(subset: List[str]) -> bool:
        key = frozenset(subset)
        if key in cache:
            return cache[key]
        counter[0] += 1
        name = f"b{counter[0]:03d}"
        tar = work / f"{name}.tar"
        if args.worktree:
            from scripts.syndwars_apply import build_subset_tar
            build_subset_tar(Path(args.worktree), subset, Path(args.all_files).read_text().split(), Path(args.link_dir), tar)
        else:
            build_tar(subset, tar)
        subprocess.run(args.upload.format(tar=tar, name=name), shell=True, check=True)
        done = subprocess.run(args.evaluate.format(name=name), shell=True, capture_output=True, text=True)
        outcome, detail = parse_result(done.stdout + done.stderr, name)
        log(f"{name}: {len(subset)} bozze -> {outcome} {detail}")
        if outcome not in ("IDENTICO", "DIVERSO", "NESSUN_DUMP"):
            raise EvalError(f"{name}: {outcome} {detail}")
        cache[key] = outcome != "IDENTICO"  # un blocco o un'uscita prima del turno 400 e' una divergenza
        return cache[key]

    culprits, interactions = find_culprits(funcs, is_bad, log)
    log(f"colpevoli: {culprits}")
    log(f"interazioni: {interactions}")
    (work / "bisect_result.json").write_text(json.dumps({"colpevoli": culprits, "interazioni": interactions,
                                                         "valutazioni": counter[0]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
