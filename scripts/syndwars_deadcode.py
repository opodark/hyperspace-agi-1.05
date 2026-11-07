#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Trova il codice assembly di Syndicate Wars che nessuno raggiunge piu' e lo mette in `#if 0`.

Ritirate le funzioni gia' riscritte in C, restano in `swars.sx` molte funzioni locali che solo quelle chiamavano.
Il file si divide in blocchi (da un'intestazione di funzione alla successiva). Partendo da cio' che il C e le altre
sorgenti citano, dai dati e dai blocchi dentro condizioni del preprocessore, si seguono riferimenti e cadute nel
blocco seguente: cio' che non si raggiunge e' morto. Gli adattatori in coda (`syndwars_link.py`) contano solo se il
C usa il nome che adattano; quelli inutili vengono tolti, altrimenti terrebbero vive le funzioni che chiamano.

Uso:
    python scripts/syndwars_deadcode.py --repo /percorso/syndwars-remake --out /tmp/dead
Scrive `swars.sx` e un rapporto in --out; non tocca il repository.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple

SEPARATOR = re.compile(r"^/\*-{5,}")
GLOBAL_FUNC = re.compile(r"^\s*GLOBAL_FUNC\s*\(\s*(\w+)\s*\)")
LABEL = re.compile(r"^\s*([A-Za-z_.$][\w.$]*):")
IF_ZERO = re.compile(r"^\s*#\s*if\s+0\b")
OPEN_IF = re.compile(r"^\s*#\s*(if|ifdef|ifndef)\b")
ELSE_IF = re.compile(r"^\s*#\s*(else|elif)\b")
END_IF = re.compile(r"^\s*#\s*endif\b")
TOKEN = re.compile(r"[A-Za-z_.][\w.$]*")  # `$nome` e' l'indirizzo di `nome`: il `$` non fa parte del nome
COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
LINE_COMMENT = re.compile(r"//[^\n]*")
TAIL_MARK = "/* Collegamento delle bozze"
NO_FALLTHROUGH = {"ret", "retl", "lret", "iret", "jmp", "ljmp", "hlt"}
GLOBAL_DIRECTIVE = re.compile(r"^\.glob(?:a)?l\s+(\w+)")
SECTION = re.compile(r"^\s*\.(text|data|bss|section)\b")
DATA_DIRECTIVE = re.compile(r"\.(?:byte|short|word|long|int|quad|ascii|asciz|string|fill|space|zero|skip)\b")
SOURCE_SUFFIXES = {".c", ".h", ".cpp", ".hpp", ".sx", ".S", ".s", ".inc"}


@dataclass
class Block:
    start: int
    end: int
    labels: Set[str] = field(default_factory=set)
    refs: Set[str] = field(default_factory=set)
    root: bool = False
    falls_through: bool = True
    has_code: bool = False
    has_data: bool = False


def strip_comments(text: str) -> str:
    return LINE_COMMENT.sub("", COMMENT.sub(" ", text))


def strip_disabled(text: str) -> str:
    """Toglie i blocchi `#if 0`, spesso con la vecchia chiamata all'assembly; il ramo `#else` resta."""
    kept: List[str] = []
    stack: List[bool] = []  # True dove il ramo corrente e' spento
    for line in text.split("\n"):
        if OPEN_IF.match(line):
            stack.append(bool(IF_ZERO.match(line)))
        elif ELSE_IF.match(line) and stack:
            stack[-1] = False
        elif END_IF.match(line) and stack:
            stack.pop()
        elif not any(stack):
            kept.append(line)
    return "\n".join(kept)


def line_code(line: str) -> str:
    return line.split("/*")[0]


def is_header(lines: Sequence[str], index: int) -> bool:
    """`/*---`, nome, `/*---`: comincia una funzione. Vale anche `GLOBAL_FUNC` senza separatori."""
    if not SEPARATOR.match(lines[index]):
        return False
    # fra il separatore e il nome possono esserci righe di commento (`/* TODO ... */`)
    position = index + 1
    while position < len(lines) and position <= index + 8 and lines[position].lstrip().startswith(("/*", "*")) and not SEPARATOR.match(lines[position]):
        position += 1
    if position + 1 < len(lines) and SEPARATOR.match(lines[position + 1]):
        return bool(LABEL.match(lines[position]) or GLOBAL_FUNC.match(lines[position]))
    return False


def starts_jump_table(lines: Sequence[str], index: int) -> bool:
    """`vtable_x:` seguito da `.long`: tabella di salto, spesso in coda a una funzione che non la usa."""
    if not LABEL.match(line_code(lines[index])) or line_code(lines[index]).split(":", 1)[1].strip():
        return False
    return index + 1 < len(lines) and bool(re.match(r"\s*\.long\s+[A-Za-z_]", lines[index + 1]))


def split_blocks(lines: Sequence[str]) -> List[Block]:
    """Blocchi attivi del file, in ordine. Le righe in `#if 0` non appartengono a nessun blocco."""
    blocks: List[Block] = []
    current: Block | None = None
    conditionals: List[bool] = []  # True per `#if 0` (o per il ramo morto), False per ogni altra condizione
    section = "text"

    def close(end: int) -> None:
        nonlocal current
        if current is not None:
            current.end = end
            blocks.append(current)
            current = None

    in_comment = False
    for index, line in enumerate(lines):
        # Commento su piu' righe: le sue righe non sono ne' istruzioni ne' direttive.
        if in_comment:
            if "*/" in line:
                in_comment = False
            continue
        if line.count("/*") > line.count("*/") and not SEPARATOR.match(line):
            in_comment = True
        # Corpo di una macro su piu' righe: non e' codice in questo punto.
        if index and lines[index - 1].rstrip().endswith("\\"):
            continue
        if OPEN_IF.match(line):
            close(index)
            conditionals.append(bool(IF_ZERO.match(line)))
            continue
        if ELSE_IF.match(line) and conditionals:
            close(index)
            conditionals[-1] = False  # il ramo `#else` di un `#if 0` e' attivo: per prudenza conta come condizione
            continue
        if END_IF.match(line) and conditionals:
            close(index)
            conditionals.pop()
            continue
        if any(conditionals):
            continue
        section_match = SECTION.match(line)
        if section_match:
            close(index)
            section = "text" if section_match.group(1) == "text" else "data"
        elif (is_header(lines, index) or (GLOBAL_FUNC.match(line) and not (index and SEPARATOR.match(lines[index - 1])))
              or starts_jump_table(lines, index)):
            close(index)
        if current is None:
            current = Block(index, index, root=bool(conditionals) or section != "text")
        code = line_code(line)
        match = GLOBAL_FUNC.match(code)
        if match:
            current.labels.add(match.group(1))
            continue
        match = LABEL.match(code)
        if match:
            current.labels.add(match.group(1))
            code = code.split(":", 1)[1]
        stripped = code.strip()
        if not stripped or stripped.startswith("#") or stripped.endswith("\\") or GLOBAL_DIRECTIVE.match(stripped):
            continue  # direttive, macro su piu' righe; dichiarare un simbolo globale non e' usarlo
        current.refs.update(TOKEN.findall(stripped))
        if stripped.startswith("."):
            current.has_data = current.has_data or bool(DATA_DIRECTIVE.match(stripped))
        else:
            current.has_code = True
            current.falls_through = stripped.split()[0] not in NO_FALLTHROUGH
    close(len(lines))
    return blocks


def reachable(blocks: Sequence[Block], external: Set[str]) -> Set[int]:
    """Indici dei blocchi raggiungibili da `external`, dai blocchi `root` e dalle cadute nel blocco seguente."""
    owner: Dict[str, int] = {}
    for position, block in enumerate(blocks):
        for label in block.labels:
            owner.setdefault(label, position)
    seen: Set[int] = set()
    todo = [i for i, b in enumerate(blocks) if b.root or b.labels & external]
    seeds = set(todo)
    while todo:
        position = todo.pop()
        if position in seen:
            continue
        seen.add(position)
        block = blocks[position]
        todo.extend(owner[ref] for ref in block.refs if ref in owner)
        # Senza istruzioni un punto di partenza non esegue nulla, e i dati non si eseguono mai.
        passes_control = block.has_code or not (block.has_data or position in seeds)
        if block.falls_through and passes_control and position + 1 < len(blocks):
            todo.append(position + 1)
    return seen


def split_tail(text: str) -> Tuple[str, str]:
    """(file senza coda, coda degli adattatori). La coda comincia dal suo commento."""
    position = text.find(TAIL_MARK)
    if position < 0:
        return text, ""
    return text[:position], text[position:]


def filter_tail(tail: str, used: Set[str]) -> Tuple[str, List[str], List[str]]:
    """Tiene gli adattatori `X__c` con X usato dal C. (coda, tenuti, tolti)."""
    if not tail:
        return "", [], []
    pieces = re.split(r"(?=^\t\.global\s)", tail, flags=re.MULTILINE)
    out = [pieces[0]]
    kept: List[str] = []
    dropped: List[str] = []
    for piece in pieces[1:]:
        match = re.match(r"\t\.global\s+(\w+)__c\b", piece)
        if match:
            (kept if match.group(1) in used else dropped).append(match.group(1))
            if match.group(1) in used:
                out.append(piece)
        else:
            out.append(piece)
    return "".join(out), kept, dropped


def external_names(repo: Path, skip: Iterable[str]) -> Set[str]:
    """Identificatori citati dalle sorgenti del progetto, commenti esclusi."""
    names: Set[str] = set()
    skipped = set(skip)
    for path in repo.rglob("*"):
        if path.suffix not in SOURCE_SUFFIXES or not path.is_file() or path.name in skipped:
            continue
        if {"build", ".git", "tools"} & set(path.relative_to(repo).parts):
            continue
        names.update(TOKEN.findall(strip_disabled(strip_comments(path.read_text(errors="replace")))))
    return names


def retire_blocks(lines: Sequence[str], blocks: Sequence[Block], dead: Set[int]) -> List[str]:
    out = list(lines)
    for position in sorted(dead, key=lambda p: -blocks[p].start):
        block = blocks[position]
        end = block.end
        while end > block.start and not out[end - 1].strip():
            end -= 1
        out.insert(end, "#endif")
        out.insert(block.start, "#if 0\n/* Unreachable after remaking its callers, found by scripts/syndwars_deadcode.py */")
    return out


def count_instructions(lines: Iterable[str]) -> int:
    total = 0
    for line in lines:
        code = line_code(line).strip()
        if code and not code.startswith((".", "#")) and not LABEL.match(code) and not GLOBAL_FUNC.match(code):
            total += 1
    return total


def global_labels(sx_text: str) -> Set[str]:
    """Solo questi sono visibili al linker: un'etichetta locale omonima di una funzione C non e' un riferimento."""
    names = set(re.findall(r"^\s*GLOBAL_FUNC\s*\(\s*(\w+)\s*\)", sx_text, re.MULTILINE))
    return names | set(re.findall(r"^\s*\.glob(?:a)?l\s+(\w+)", sx_text, re.MULTILINE))


def analyse(sx_text: str, external: Set[str]) -> Dict[str, object]:
    body, tail = split_tail(sx_text)
    new_tail, kept, dropped = filter_tail(tail, external)
    lines = body.split("\n")
    blocks = split_blocks(lines)
    tail_refs = set(TOKEN.findall(strip_comments(new_tail)))
    live = reachable(blocks, (external & global_labels(body + new_tail)) | tail_refs)
    dead = {i for i in range(len(blocks)) if i not in live and blocks[i].labels}
    out = "\n".join(retire_blocks(lines, blocks, dead)) + new_tail
    before = sum(count_instructions(lines[b.start:b.end]) for b in blocks)
    removed = sum(count_instructions(lines[blocks[i].start:blocks[i].end]) for i in dead)
    return {"text": out, "blocks": len(blocks), "dead": sorted(sorted(blocks[i].labels)[0] for i in dead),
            "instructions_before": before, "instructions_removed": removed, "adapters_kept": kept, "adapters_dropped": dropped}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--file", default="src/swars.sx", help="file assembly da analizzare, relativo al repository")
    args = parser.parse_args()
    repo = Path(args.repo)
    sx = repo / args.file
    # L'intestazione ha un #define per ogni simbolo mai servito: non dice cosa e' usato.
    external = external_names(repo, {sx.name, "drafts_link.h"})
    result = analyse(sx.read_text(errors="replace"), external)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / sx.name).write_text(str(result.pop("text")))
    (out / "report.json").write_text(json.dumps(result, indent=1))
    print(f"blocchi {result['blocks']}, morti {len(result['dead'])}, istruzioni {result['instructions_before']} "
          f"-> {result['instructions_before'] - result['instructions_removed']}, "
          f"adattatori tenuti {len(result['adapters_kept'])} tolti {len(result['adapters_dropped'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
