#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Riscrive in C leggibile le bozze Ghidra di Syndicate Wars con un modello locale, e tiene solo cio' che regge.

La bozza e' corretta ma illeggibile (`*(int *)(iVar6 + 0x1c)`). Il modello la riscrive; il risultato passa dal
verificatore per esecuzione (`syndwars_verify.py`) contro l'assembly originale. Se non concorda, il modello riceve
l'errore e riprova. Una riscrittura conta solo con verdetto `agree` e copertura non inferiore alla bozza.

I risultati stanno in `data/nightly/syndwars_clean/` (ignorata da git: derivano dal binario originale).

Uso:
    .venv/bin/python scripts/syndwars_cleanup.py add_node_thing remove_thing
    .venv/bin/python scripts/syndwars_cleanup.py --smallest 10
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DRAFTS = ROOT / "data" / "nightly" / "syndwars_ghidra"
OUTPUT_DIR = ROOT / "data" / "nightly" / "syndwars_clean"
GHIDRA_MARKS = re.compile(r"\b(?:[iu]Var\d+|[bcsp]Var\d+|local_[0-9a-f]+|unaff_\w+|in_\w+|extraout_\w+)\b")
CAST_DEREF = re.compile(r"\*\s*\(\s*(?:u?int|u?short|ubyte|char|long|u32|s32)\s*\*\s*\)")

PROMPT = """You are cleaning up decompiled C from the game Syndicate Wars so that a human can maintain it.
The code below is correct but unreadable. Rewrite it as idiomatic C99 in the style of the project.

Rules:
- Keep the function signature exactly as given.
- Keep the behaviour exactly: the same calls in the same order with the same argument values, the same writes in the
  same order and with the same width, the same integer truncations and the same signedness in comparisons.
- `(*(T *)&name)` is the global `name`: write `name` when T matches its declared type, keep a cast when the width differs.
- Replace integer locals that hold pointers with typed pointers when the type is evident, for example
  `struct Thing *p_thing = &things[idx];`, and pointer arithmetic with field access when the field is known.
- Rename `iVar1`, `uVar2`, `local_18` after what they hold. Replace `goto` with structured flow when it is safe.
- Do not add functions, globals, includes or explanations. Do not remove code because it looks useless.

Declarations visible to this function:
```c
{declarations}
```

Code to rewrite:
```c
{code}
```
{feedback}
Answer with one ```c block containing only the rewritten function."""


def split_draft(text: str, name: str) -> Tuple[str, str]:
    """(prefisso con le dichiarazioni, corpo della funzione) di un file di bozza."""
    pattern = re.compile(rf"^[A-Za-z_][\w \t\*]*\b{re.escape(name)}\s*\([^;{{}}]*\)\s*\{{", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        raise ValueError(f"funzione {name} non trovata nella bozza")
    return text[:match.start()], text[match.start():].strip()


def visible_declarations(prefix: str) -> str:
    """Le dichiarazioni dopo il blocco di compatibilita': quelle che il modello deve vedere."""
    marker = prefix.rfind("#endif")
    return prefix[marker + len("#endif"):].strip() if marker >= 0 else prefix.strip()


def readability(code: str) -> Dict[str, int]:
    """Misure grezze: quanti nomi di Ghidra, dereferenze con cast e righe restano."""
    return {"nomi_ghidra": len(GHIDRA_MARKS.findall(code)), "cast_deref": len(CAST_DEREF.findall(code)),
            "goto": len(re.findall(r"\bgoto\b", code)), "righe": len(code.splitlines())}


def draft_path(name: str) -> Path:
    manual = DRAFTS / "manual" / f"{name}.base.c"
    return manual if manual.exists() else DRAFTS / f"{name}.base.c"


def verify(name: str, path: Path, cases: int, mutants: bool = False) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "r.json"
        command = [sys.executable, str(ROOT / "scripts" / "syndwars_verify.py"), "--cases", str(cases), "--output", str(out)]
        if not mutants:
            command.append("--no-mutants")
        command.append(f"{name}={path}")
        done = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, timeout=1200)
        if not out.exists():
            return {"verdict": "errore", "error": (done.stderr or done.stdout)[-800:]}
        results = json.loads(out.read_text())
        return results[0] if results else {"verdict": "errore", "error": "nessun risultato"}


def describe_failure(result: Dict[str, Any]) -> str:
    if result.get("error"):
        return str(result["error"])[-600:]
    first = (result.get("mismatches") or [{}])[0]
    return (f"verdict {result.get('verdict')}: {result.get('disagreed')} test cases differ. First difference: "
            f"arguments {first.get('args')}, status {first.get('status')}, return {first.get('return')}, "
            f"written addresses that differ {first.get('write_diffs')}, calls {first.get('calls')}.")


def cleanup_function(name: str, model: str, retries: int, cases: int) -> Dict[str, Any]:
    from scripts.syndwars_decompile_sovereign import extract_c_function_from_response
    from scripts.syndwars_orchestrate import call_model

    prefix, code = split_draft(draft_path(name).read_text(), name)
    report: Dict[str, Any] = {"func": name, "model": model, "prima": readability(code), "tentativi": 0, "esito": "fallita"}
    feedback = ""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, retries + 1):
        report["tentativi"] = attempt
        prompt = PROMPT.format(declarations=visible_declarations(prefix), code=code, feedback=feedback)
        try:
            reply = call_model(prompt, model=model)["message"]["content"]
        except Exception as error:  # rete o modello occupato: si riprova
            feedback = ""
            report["ultimo_errore"] = f"modello: {error}"
            continue
        _, candidate = extract_c_function_from_response(reply, name)
        if not candidate:
            feedback = "\nYour last answer had no complete function in a ```c block.\n"
            report["ultimo_errore"] = "nessuna funzione nella risposta"
            continue
        path = OUTPUT_DIR / f"{name}.clean.c"
        path.write_text(prefix + candidate.strip() + "\n")
        result = verify(name, path, cases)
        if result.get("verdict") == "agree":
            final = verify(name, path, cases, mutants=True)
            report.update(esito="agree" if final.get("verdict") == "agree" else str(final.get("verdict")),
                          dopo=readability(candidate), verifica={k: final.get(k) for k in
                          ("verdict", "agreed", "coverage", "mutants", "undefined_input")})
            if report["esito"] == "agree":
                return report
        report["ultimo_errore"] = describe_failure(result)
        feedback = ("\nYour previous rewrite was executed against the original and failed:\n"
                    f"{report['ultimo_errore']}\nPrevious rewrite:\n```c\n{candidate.strip()}\n```\nFix it.\n")
    path = OUTPUT_DIR / f"{name}.clean.c"
    if path.exists():
        path.rename(path.with_suffix(".rejected"))
    return report


def smallest_solid(count: int) -> List[str]:
    from scripts.syndwars_patch import is_solid

    results = json.loads((DRAFTS / "_verify_all.json").read_text())
    rows = []
    for result in results:
        if is_solid(result):
            _, code = split_draft(draft_path(result["func"]).read_text(), result["func"])
            rows.append((len(code.splitlines()), result["func"]))
    return [name for _, name in sorted(rows)[:count]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("functions", nargs="*")
    parser.add_argument("--smallest", type=int, default=0)
    parser.add_argument("--model", default="hf.co/mradermacher/Qwen3.5-9B-Coder-GGUF:Q4_K_M")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--cases", type=int, default=200)
    parser.add_argument("--report", default=str(OUTPUT_DIR / "_report.json"))
    args = parser.parse_args()
    names = list(args.functions) + (smallest_solid(args.smallest) if args.smallest else [])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reports: List[Dict[str, Any]] = []
    for index, name in enumerate(names, 1):
        report = cleanup_function(name, args.model, args.retries, args.cases)
        reports.append(report)
        Path(args.report).write_text(json.dumps(reports, indent=1, ensure_ascii=False))
        print(f"[{index}/{len(names)}] {name}: {report['esito']} tentativi={report['tentativi']} "
              f"prima={report['prima']} dopo={report.get('dopo')} {str(report.get('ultimo_errore', ''))[:160]}", flush=True)
    ok = [r for r in reports if r["esito"] == "agree"]
    print(f"riuscite {len(ok)} su {len(reports)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
