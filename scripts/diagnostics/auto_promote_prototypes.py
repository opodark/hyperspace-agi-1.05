#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Promozione automatica dei prototipi R&D, con cancelli stretti.

Perimetro: legge data/research/prototypes/, scrive solo con --apply (nuovo modulo in
shared/, test in tests/test_auto_<modulo>.py, record in data/research/promotions.jsonl
tramite promote_research_prototype). Non fa commit né push.

Un prototipo viene promosso solo se supera TUTTI i cancelli:
  1. AST valido, almeno una classe pubblica, almeno --min-nodes nodi AST.
  2. Solo import stdlib (senza rete/processi/ctypes/pickle) o shared.*; nessuna
     chiamata eval/exec/os.system/..., nessun open() in scrittura, nessun
     statement top-level con effetti (solo def, class, import, costanti).
  3. Nessuna classe pubblica già presente in shared/: MAI sovrascrive un modulo
     esistente e scarta i quasi-duplicati.
  4. I test che il prototipo porta con sé (classi Test*) girano e passano.
Poi promote_research_prototype assegna il tier: 'verified' solo se il test passa
da shared/. Se il tier non è verified, la promozione viene annullata.

Uso:
  python scripts/diagnostics/auto_promote_prototypes.py            # dry-run
  python scripts/diagnostics/auto_promote_prototypes.py --apply --max-promotions 3
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROTOTYPES_DIR = ROOT / "data" / "research" / "prototypes"
SHARED_DIR = ROOT / "shared"
TESTS_DIR = ROOT / "tests"
PROMOTIONS_FILE = ROOT / "data" / "research" / "promotions.jsonl"
STATE_FILE = ROOT / "data" / "research" / "auto_promotion_state.json"

from shared.prototype_gates import (  # noqa: E402
    embedded_test_classes,
    public_classes,
    run_embedded_tests,
    shared_class_names as _shared_class_names,
    snake as _snake,
    static_gate,
    extract_code,
    tests_prompt,
    with_tests,
    TEST_MODEL,
)
NO_TESTS = "nessun test incluso (serve generazione test)"

def _load_state() -> Dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"rejected": {}, "promoted": {}}


def _save_state(state: Dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _already_promoted() -> Set[str]:
    done: Set[str] = set()
    if PROMOTIONS_FILE.exists():
        for line in PROMOTIONS_FILE.read_text(encoding="utf-8").splitlines():
            try:
                pf = json.loads(line).get("prototype_file")
            except Exception:
                continue
            if pf:
                done.add(pf)
    return done


def run_auto_promotion(
    apply: bool = False,
    max_promotions: int = 3,
    max_tested: int = 10,
    min_nodes: int = 250,
    executor: Optional[Any] = None,
    backfill: int = 3,
) -> Dict[str, Any]:
    executor = executor if apply else None  # il recupero dei test modifica i prototipi: solo con --apply
    state = _load_state()
    state.setdefault("backfill_attempts", {})
    promoted_already = _already_promoted()
    known_classes = _shared_class_names()
    report: Dict[str, Any] = {
        "apply": apply, "scanned": 0, "static_rejected": 0, "tested": 0,
        "eligible": [], "promoted": [], "rolled_back": [], "skipped_known": 0, "backfilled": 0,
    }
    needs_tests: List[Any] = []

    candidates = []
    for p in sorted(PROTOTYPES_DIR.glob("proto_*.py")):
        report["scanned"] += 1
        retry_tests = bool(executor) and str(state["rejected"].get(p.name, "")).startswith("nessun test incluso")
        if p.name in promoted_already or p.name in state["promoted"] or (p.name in state["rejected"] and not retry_tests):
            report["skipped_known"] += 1
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except Exception as exc:
            state["rejected"][p.name] = f"AST non valido: {exc}"[:120]
            continue
        reason = static_gate(tree, min_nodes)
        pub, tests = public_classes(tree), embedded_test_classes(tree)
        if not reason and not pub:
            reason = "nessuna classe pubblica"
        if not reason and not tests:
            reason = NO_TESTS
        if reason == NO_TESTS and executor and state["backfill_attempts"].get(p.name, 0) < 2:
            needs_tests.append((sum(1 for _ in ast.walk(tree)), p, pub))
            continue
        if reason:
            state["rejected"][p.name] = reason
            report["static_rejected"] += 1
            continue
        candidates.append((sum(1 for _ in ast.walk(tree)), p, pub, tests))

    # Recupero all'indietro: test scritti dal modello piccolo per prototipi sostanziosi senza test
    needs_tests.sort(key=lambda c: -c[0])
    known_now = _shared_class_names()
    for nodes, path, pub in needs_tests:
        if report["backfilled"] >= backfill:
            break
        if any(c in known_now for c in pub):
            state["rejected"][path.name] = f"classe già in shared/: {next(c for c in pub if c in known_now)}"
            continue
        code = path.read_text(encoding="utf-8")
        res = executor(tests_prompt(code), model=TEST_MODEL, timeout=120)
        block = extract_code(res.get("response", "")) if res.get("status") == "ok" else None
        state["backfill_attempts"][path.name] = state["backfill_attempts"].get(path.name, 0) + 1
        if not block:
            continue
        combined = with_tests(code, block)
        try:
            ctree = ast.parse(combined)
        except SyntaxError:
            continue
        if static_gate(ctree, min_nodes) or not embedded_test_classes(ctree):
            continue
        tmp = path.with_name(f"btmp_{path.stem}.py")
        tmp.write_text(combined, encoding="utf-8")
        try:
            ok = run_embedded_tests(tmp)["ok"]
        finally:
            tmp.unlink(missing_ok=True)
        if ok:
            path.write_text(combined, encoding="utf-8")
            report["backfilled"] += 1
            candidates.append((nodes, path, pub, embedded_test_classes(ctree)))
            state["rejected"].pop(path.name, None)

    candidates.sort(key=lambda c: -c[0])
    for _, path, pub, tests in candidates:
        if report["tested"] >= max_tested or len(report["promoted"]) >= max_promotions:
            break
        clash = [c for c in pub if c in known_classes]
        if clash:
            state["rejected"][path.name] = f"classe già in shared/: {clash[0]}"
            continue
        stem = _snake(pub[0])
        if (SHARED_DIR / f"{stem}.py").exists() or (TESTS_DIR / f"test_auto_{stem}.py").exists():
            state["rejected"][path.name] = f"modulo {stem}.py già esistente"
            continue
        report["tested"] += 1
        res = run_embedded_tests(path)
        if not res["ok"]:
            state["rejected"][path.name] = f"{res['reason']}"
            continue
        entry = {"prototype": path.name, "target": f"shared/{stem}.py", "classes": pub, "tests": res["passed"]}
        report["eligible"].append(entry)
        if not apply:
            continue

        test_file = TESTS_DIR / f"test_auto_{stem}.py"
        test_file.write_text(
            "# SPDX-License-Identifier: Apache-2.0\n"
            f"\"\"\"Test portati dal prototipo {path.name} (auto_promote_prototypes).\"\"\"\n"
            f"from shared.{stem} import {', '.join(tests)}  # noqa: F401\n",
            encoding="utf-8",
        )
        from scripts.diagnostics.promote_research_prototype import PrototypePromoter
        out = PrototypePromoter(author="auto_promoter").promote_single(path.name, f"{stem}.py")
        tier = (out.get("evidence") or {}).get("tier")
        if out.get("success") and tier == "verified":
            report["promoted"].append({**entry, "tier": tier})
            state["promoted"][path.name] = {"target": entry["target"], "at": int(time.time())}
            known_classes.update(pub)
        else:
            (SHARED_DIR / f"{stem}.py").unlink(missing_ok=True)
            test_file.unlink(missing_ok=True)
            for bak in SHARED_DIR.glob(f"{stem}.py.*.bak"):
                bak.unlink(missing_ok=True)
            why = out.get("error") or f"tier {tier}"
            state["rejected"][path.name] = f"annullata dopo promozione: {why}"[:160]
            report["rolled_back"].append({"prototype": path.name, "reason": why[:160]})

    if apply:
        _save_state(state)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="Promuove davvero (default: dry-run)")
    ap.add_argument("--max-promotions", type=int, default=3)
    ap.add_argument("--max-tested", type=int, default=10)
    ap.add_argument("--min-nodes", type=int, default=250)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rep = run_auto_promotion(a.apply, a.max_promotions, a.max_tested, a.min_nodes)
    if a.json:
        print(json.dumps(rep, indent=2, ensure_ascii=False))
    else:
        mode = "APPLY" if a.apply else "DRY-RUN"
        print(f"[{mode}] scansionati {rep['scanned']} | già noti {rep['skipped_known']} | test recuperati {rep['backfilled']} | "
              f"scartati statici {rep['static_rejected']} | testati {rep['tested']}")
        for e in rep["eligible"]:
            print(f"  idoneo: {e['prototype']} -> {e['target']} ({e['tests']} test) classi={e['classes']}")
        for e in rep["promoted"]:
            print(f"  PROMOSSO: {e['target']} [{e['tier']}]")
        for e in rep["rolled_back"]:
            print(f"  ANNULLATO: {e['prototype']} ({e['reason']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
