#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prepara come obiettivi di decompilazione le funzioni assembly locali di Syndicate Wars (senza simbolo globale).

La catena lavora su `GLOBAL_FUNC(ASM_nome)` con uno stub C. Le funzioni locali non hanno ne' l'uno ne' l'altro, ma
sono ormai la maggior parte dell'assembly vivo. Su una copia di lavoro separata questo script:
  - aggiunge l'alias `GLOBAL_FUNC(ASM_nome)` sopra l'etichetta locale;
  - accoda lo stub al file C della funzione assembly gia' nota piu' vicina: nell'originale le funzioni contigue
    stavano nella stessa unita' di compilazione, quindi quel file ha gia' gli include giusti;
  - accoda l'obiettivo alla coda delle funzioni da decompilare.

Uso:
    python scripts/syndwars_local_targets.py --tree /tmp/wt_local --names tank_los inside_the_quad
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SEPARATOR = re.compile(r"^/\*-{5,}")


def find_local_function(lines: Sequence[str], name: str) -> Optional[Tuple[int, int]]:
    """(riga dell'etichetta, riga dopo il blocco) di una funzione locale con intestazione a separatori."""
    label = re.compile(rf"^(?:{re.escape(name)}:|GLOBAL_FUNC\(\s*{re.escape(name)}\s*\))")
    for index, line in enumerate(lines):
        if not label.match(line):
            continue
        if not (index and SEPARATOR.match(lines[index - 1]) and index + 1 < len(lines) and SEPARATOR.match(lines[index + 1])):
            continue
        for end in range(index + 2, len(lines)):
            if SEPARATOR.match(lines[end]) or re.match(r"^\s*#\s*(if|endif|else)\b", lines[end]):
                return index, end
        return index, len(lines)
    return None


def add_global_alias(lines: List[str], name: str) -> bool:
    """Mette `GLOBAL_FUNC(ASM_nome)` subito sopra l'etichetta: stesso indirizzo, nessuna istruzione in piu'."""
    found = find_local_function(lines, name)
    if found is None:
        return False
    lines.insert(found[0], f"GLOBAL_FUNC(ASM_{name})")
    return True


def stub_from_declaration(declaration: str) -> str:
    """Stub C dalla firma ricavata: il corpo non conta, la catena lo sostituisce."""
    head = declaration.strip().rstrip(";").strip()
    body = "\n{\n}" if head.startswith("void ") else "\n{\n    return 0;\n}"
    return head + body


def nearest_c_file(line: int, targets: Sequence[Dict[str, Any]]) -> Optional[str]:
    """Il file C dell'obiettivo noto con la riga assembly piu' vicina."""
    best: Optional[Tuple[int, str]] = None
    for target in targets:
        start = target.get("asm_start_line")
        if not isinstance(start, int) or target.get("local"):
            continue
        distance = abs(start - line)
        if best is None or distance < best[0]:
            best = (distance, target["c_file"])
    return best[1] if best else None


def find_wrapper(c_text: str, name: str) -> Optional[Tuple[str, str]]:
    """(testo intero, firma) del `static inline` che chiama l'assembly col nome della funzione stessa."""
    pattern = re.compile(rf"^static inline __attribute__\(\(always_inline\)\)\s+([^\n;{{}}]*\b{re.escape(name)}\s*\([^;{{}}]*\))\s*\{{.*?^\}}\n",
                         re.MULTILINE | re.DOTALL)
    match = pattern.search(c_text)
    return (match.group(0), match.group(1).strip()) if match else None


def make_target(name: str, declaration: str, sx_lines: Sequence[str], c_file: str, region: Tuple[int, int],
                includes: Sequence[str]) -> Dict[str, Any]:
    start, end = region
    code = "\n".join([f"GLOBAL_FUNC(ASM_{name})", *sx_lines[start:end]])
    return {"func_name": name, "c_file": c_file, "c_start_line": 0, "c_end_line": 0, "asm_start_line": start + 1,
            "asm_end_line": end, "asm_line_count": end - start, "has_if0_draft": False, "c_draft": "",
            "includes": list(includes), "asm_code": code, "current_c_stub": stub_from_declaration(declaration), "local": True}


def main() -> int:
    from scripts.syndwars_decompile_sovereign import PENDING_PATH, load_jsonl

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", required=True, help="copia di lavoro da modificare (non quella del gioco)")
    parser.add_argument("--names", nargs="+", required=True)
    parser.add_argument("--signatures", default=str(ROOT / "data/nightly/syndwars_ghidra/_inferred_signatures.json"))
    args = parser.parse_args()
    tree = Path(args.tree)
    signatures = json.loads(Path(args.signatures).read_text())
    known = load_jsonl(PENDING_PATH)
    known_names = {t["func_name"] for t in known}
    sx_path = tree / "src" / "swars.sx"
    lines = sx_path.read_text(errors="replace").split("\n")
    added: List[Dict[str, Any]] = []
    for name in args.names:
        if name in known_names:
            print(f"{name}: gia' in coda")
            continue
        region = find_local_function(lines, name)
        if region is None:
            print(f"{name}: etichetta locale non trovata")
            continue
        wrapper = None
        for c_path in sorted((tree / "src").glob("*.c")):
            wrapper = find_wrapper(c_path.read_text(errors="replace"), name)
            if wrapper:
                break
        if wrapper:
            # Il `static inline` ha i tipi veri: la firma viene da li' e lo stub prende il suo posto.
            c_file = f"src/{c_path.name}"
            neighbour = next((t for t in known if t["c_file"] == c_file), {})
            target = make_target(name, wrapper[1] + ";", lines, c_file, region, neighbour.get("includes", []))
            target["wrapper_text"] = wrapper[0]
            c_path.write_text(c_path.read_text(errors="replace").replace(wrapper[0], target["current_c_stub"] + "\n", 1))
        else:
            if name not in signatures:
                print(f"{name}: senza firma ricavata")
                continue
            c_file = nearest_c_file(region[0], known)
            if c_file is None:
                print(f"{name}: nessun file C vicino")
                continue
            neighbour = next(t for t in known if t["c_file"] == c_file)
            target = make_target(name, signatures[name], lines, c_file, region, neighbour.get("includes", []))
            path = tree / c_file
            path.write_text(path.read_text(errors="replace").rstrip("\n") + "\n\n" + target["current_c_stub"] + "\n")
        add_global_alias(lines, name)
        added.append(target)
        print(f"{name}: {c_file}, {target['asm_line_count']} righe")
    sx_path.write_text("\n".join(lines))
    with open(PENDING_PATH, "a", encoding="utf-8") as queue:
        for target in added:
            queue.write(json.dumps(target, ensure_ascii=False) + "\n")
    print(f"obiettivi aggiunti: {len(added)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
