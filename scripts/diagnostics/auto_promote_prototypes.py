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

DENY_MODULES = {
    "subprocess", "socket", "ssl", "http", "urllib", "ftplib", "smtplib", "telnetlib",
    "shutil", "ctypes", "multiprocessing", "pickle", "marshal", "importlib", "pty",
    "webbrowser", "xmlrpc",
}
DENY_CALLS = {"eval", "exec", "compile", "__import__", "input", "breakpoint"}
DENY_OS_ATTRS = {
    "system", "popen", "remove", "unlink", "rmdir", "removedirs", "rename", "kill",
    "fork", "execv", "execve", "execl", "execvp", "spawnl", "spawnv", "chmod", "chown",
}
ALLOWED_TOP_LEVEL = (
    ast.Import, ast.ImportFrom, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef,
    ast.Assign, ast.AnnAssign,
)


def _stdlib() -> Set[str]:
    return set(getattr(sys, "stdlib_module_names", ()))


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _shared_class_names() -> Set[str]:
    names: Set[str] = set()
    for f in SHARED_DIR.glob("*.py"):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.ClassDef):
                names.add(n.name)
    return names


def static_gate(tree: ast.Module, min_nodes: int) -> Optional[str]:
    """Restituisce il motivo del rifiuto, o None se il codice passa i cancelli statici."""
    node_count = sum(1 for _ in ast.walk(tree))
    if node_count < min_nodes:
        return f"troppo piccolo ({node_count} nodi < {min_nodes})"
    stdlib = _stdlib()
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        if isinstance(node, ast.If) and "__main__" in ast.dump(node.test):
            continue
        if not isinstance(node, ALLOWED_TOP_LEVEL):
            return f"statement top-level non ammesso ({type(node).__name__})"
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.decorator_list:
            return "funzione top-level decorata (possibile fixture/hook)"
    for node in ast.walk(tree):
        mods: List[str] = []
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                return "import relativo non ammesso"
            mods = [node.module or ""]
        for m in mods:
            root = m.split(".")[0]
            if m in DENY_MODULES or root in DENY_MODULES:
                return f"import vietato: {m}"
            if root == "shared":
                parts = m.split(".")
                if len(parts) > 1 and not (SHARED_DIR / f"{parts[1]}.py").exists():
                    return f"modulo shared inesistente: {m}"
                continue
            if root not in stdlib:
                return f"dipendenza non stdlib: {m}"
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in DENY_CALLS:
                return f"chiamata vietata: {f.id}()"
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                if f.value.id == "os" and f.attr in DENY_OS_ATTRS:
                    return f"chiamata vietata: os.{f.attr}()"
            if isinstance(f, ast.Name) and f.id == "open":
                mode = None
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    mode = node.args[1].value
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        mode = kw.value.value
                if mode is not None and any(c in str(mode) for c in "wax+"):
                    return "open() in scrittura"
                if len(node.args) > 1 and not isinstance(node.args[1], ast.Constant):
                    return "open() con modo non costante"
    return None


def public_classes(tree: ast.Module) -> List[str]:
    return [
        n.name for n in tree.body
        if isinstance(n, ast.ClassDef) and not n.name.startswith(("Test", "_"))
    ]


def embedded_test_classes(tree: ast.Module) -> List[str]:
    return [n.name for n in tree.body if isinstance(n, ast.ClassDef) and n.name.startswith("Test")]


def run_embedded_tests(path: Path, timeout: int = 60) -> Dict[str, Any]:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(path), "-q", "-p", "no:cacheprovider"],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": f"timeout {timeout}s"}
    m = re.search(r"(\d+) passed", proc.stdout)
    passed = int(m.group(1)) if m else 0
    if proc.returncode != 0:
        return {"ok": False, "reason": "test falliti", "tail": proc.stdout.strip()[-300:]}
    if passed < 1:
        return {"ok": False, "reason": "nessun test eseguito"}
    return {"ok": True, "passed": passed}


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
) -> Dict[str, Any]:
    state = _load_state()
    promoted_already = _already_promoted()
    known_classes = _shared_class_names()
    report: Dict[str, Any] = {
        "apply": apply, "scanned": 0, "static_rejected": 0, "tested": 0,
        "eligible": [], "promoted": [], "rolled_back": [], "skipped_known": 0,
    }

    candidates = []
    for p in sorted(PROTOTYPES_DIR.glob("proto_*.py")):
        report["scanned"] += 1
        if p.name in promoted_already or p.name in state["rejected"] or p.name in state["promoted"]:
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
            reason = "nessun test incluso (serve generazione test)"
        if reason:
            state["rejected"][p.name] = reason
            report["static_rejected"] += 1
            continue
        candidates.append((sum(1 for _ in ast.walk(tree)), p, pub, tests))

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
        print(f"[{mode}] scansionati {rep['scanned']} | già noti {rep['skipped_known']} | "
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
