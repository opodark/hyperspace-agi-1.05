#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Ritira da `#if 0` le funzioni assembly che il progetto ha gia' riscritto in C.

Una funzione `GLOBAL_FUNC(ASM_nome)` e' ritirabile quando:
  - esiste in C una funzione con lo stesso nome che non chiama piu' l'assembly;
  - nessun'altra funzione assembly attiva la richiama in modo diretto (`call ASM_nome`, `jmp`);
    le chiamate `ac_nome` passano dal C e non contano;
  - nessuna delle sue etichette locali (`jump_xxx:`) e' usata fuori dal suo corpo;
  - il suo corpo non contiene direttive del preprocessore.

Uso:
    python scripts/syndwars_retire.py --src /percorso/syndwars-remake/src --out /tmp/retired --list ritirabili.json
Scrive i file `.sx` modificati in --out e un rapporto; non tocca --src.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

GLOBAL_FUNC = re.compile(r"^\s*GLOBAL_FUNC\s*\(\s*(\w+)\s*\)")
LABEL = re.compile(r"^\s*([A-Za-z_]\w*):")
CALL = re.compile(r"\b(?:call|jmp|j[a-z]{1,3})\s+(?:\*)?(\w+)")
SEPARATOR = re.compile(r"^/\*-{5,}")
DIRECTIVE = re.compile(r"^\s*#\s*(if|ifdef|ifndef|else|elif|endif)\b")


def function_regions(lines: List[str]) -> Dict[str, Tuple[int, int]]:
    """nome -> (prima riga, riga dopo l'ultima) del blocco di una funzione attiva.

    Il blocco comincia dal separatore `/*----` sopra `GLOBAL_FUNC` e finisce prima del separatore della funzione
    seguente (globale o locale) o prima di una direttiva del preprocessore."""
    starts: List[Tuple[int, str]] = []
    active_depth = 0
    zero_stack: List[bool] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r"#\s*if\b", stripped) or re.match(r"#\s*ifn?def\b", stripped):
            zero_stack.append(bool(re.match(r"#\s*if\s+0\b", stripped)))
        elif re.match(r"#\s*endif\b", stripped) and zero_stack:
            zero_stack.pop()
        match = GLOBAL_FUNC.match(line)
        if match and not any(zero_stack):
            start = index - 1 if index and SEPARATOR.match(lines[index - 1]) else index
            starts.append((start, match.group(1)))
    regions: Dict[str, Tuple[int, int]] = {}
    for position, (start, name) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        # si ferma alla prima direttiva del preprocessore dopo il nome (blocco `#if 0` seguente, `#endif`, ...)
        for index in range(start + 2, end):
            if DIRECTIVE.match(lines[index]):
                end = index
                break
            # intestazione di una funzione locale (separatore, `nome:`, separatore): non fa parte di questo blocco
            if (SEPARATOR.match(lines[index]) and index + 2 < len(lines)
                    and LABEL.match(lines[index + 1]) and SEPARATOR.match(lines[index + 2])):
                end = index
                break
        regions[name] = (start, end)
    return regions


def local_labels(lines: List[str], region: Tuple[int, int]) -> Set[str]:
    labels = set()
    for line in lines[region[0]:region[1]]:
        match = LABEL.match(line)
        if match:
            labels.add(match.group(1))
    return labels


def has_directive(lines: List[str], region: Tuple[int, int]) -> bool:
    return any(DIRECTIVE.match(line) for line in lines[region[0]:region[1]])


def direct_callers(files: Dict[str, List[str]], regions: Dict[str, Dict[str, Tuple[int, int]]]) -> Dict[str, Set[str]]:
    """Per ogni etichetta, le funzioni attive che la richiamano senza passare da `ac_`."""
    callers: Dict[str, Set[str]] = defaultdict(set)
    for file_name, lines in files.items():
        for name, (start, end) in regions[file_name].items():
            for line in lines[start:end]:
                code = line.split("/*")[0].split("#")[0]
                for target in CALL.findall(code):
                    if not target.startswith("ac_") and target != name:
                        callers[target].add(name)
    return callers


def references_outside(files: Dict[str, List[str]], regions: Dict[str, Dict[str, Tuple[int, int]]],
                       skip: Set[str], labels: Set[str], own_file: str, own_region: Tuple[int, int]) -> Set[str]:
    """Etichette locali di una funzione citate da qualunque riga fuori dal suo blocco o da funzioni non ritirate."""
    found: Set[str] = set()
    if not labels:
        return found
    pattern = re.compile(r"\b(" + "|".join(re.escape(label) for label in labels) + r")\b")
    for file_name, lines in files.items():
        for index, line in enumerate(lines):
            if file_name == own_file and own_region[0] <= index < own_region[1]:
                continue
            code = line.split("/*")[0]
            if LABEL.match(code) and not code.split(":", 1)[1].strip():
                continue  # la definizione di un'etichetta non e' un riferimento
            for match in pattern.finditer(code):
                # un riferimento da un blocco gia' ritirato non conta
                owner = next((n for n, (s, e) in regions[file_name].items() if s <= index < e), None)
                if owner in skip:
                    continue
                found.add(match.group(1))
    return found


def plan(files: Dict[str, List[str]], candidates: Iterable[str]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """(nome -> file ritirabili, nome -> motivo per quelli scartati)."""
    regions = {name: function_regions(lines) for name, lines in files.items()}
    where = {n: f for f, r in regions.items() for n in r}
    candidates = [c for c in candidates if c in where]
    skip = set(candidates)
    callers = direct_callers(files, regions)
    rejected: Dict[str, str] = {}
    changed = True
    while changed:  # togliere una funzione dall'insieme puo' bloccarne un'altra
        changed = False
        for name in list(skip):
            file_name = where[name]
            region = regions[file_name][name]
            outside = {c for c in callers.get(name, set()) if c not in skip}
            if outside:
                rejected[name] = "chiamata da " + ",".join(sorted(outside)[:3])
            elif has_directive(files[file_name], region):
                rejected[name] = "direttive nel corpo"
            else:
                bad = references_outside(files, regions, skip - {name}, local_labels(files[file_name], region), file_name, region)
                if bad:
                    rejected[name] = "etichette usate altrove: " + ",".join(sorted(bad)[:3])
                else:
                    continue
            skip.discard(name)
            changed = True
    return {n: where[n] for n in skip}, rejected


def apply(files: Dict[str, List[str]], retire: Dict[str, str]) -> Dict[str, List[str]]:
    regions = {name: function_regions(lines) for name, lines in files.items()}
    out = {name: list(lines) for name, lines in files.items()}
    for file_name in files:
        todo = sorted(((regions[file_name][n], n) for n, f in retire.items() if f == file_name), key=lambda x: -x[0][0])
        for (start, end), name in todo:
            out[file_name].insert(end, "#endif")
            out[file_name].insert(start, "#if 0\n/* Remade in C, asm retired by scripts/syndwars_retire.py */")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", required=True)
    parser.add_argument("--list", required=True, help="json con la lista `retirable`")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    src = Path(args.src)
    files = {p.name: p.read_text(errors="replace").split("\n") for p in sorted(src.glob("*.sx"))}
    candidates = json.loads(Path(args.list).read_text())["retirable"]
    retire, rejected = plan(files, candidates)
    out = apply(files, retire)
    destination = Path(args.out)
    destination.mkdir(parents=True, exist_ok=True)
    changed = sorted({f for f in retire.values()})
    for file_name in changed:
        (destination / file_name).write_text("\n".join(out[file_name]))
    report = {"ritirate": sorted(retire), "scartate": rejected, "file": changed}
    (destination / "report.json").write_text(json.dumps(report, indent=1))
    print(f"candidate {len(candidates)}, ritirate {len(retire)}, scartate {len(rejected)}, file modificati {changed}")
    for name, why in sorted(rejected.items())[:12]:
        print(f"  scartata {name}: {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
