# SPDX-License-Identifier: Apache-2.0
"""Cancelli di sicurezza e verifica per il codice generato dai modelli (prototipi R&D).

Usati sia dal generatore (shared/agi_research_engine.py, prima di eseguire i test di una
variante) sia dal promotore (scripts/diagnostics/auto_promote_prototypes.py).
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parents[1]
SHARED_DIR = ROOT / "shared"

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


def snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def shared_class_names() -> Set[str]:
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
            env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
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


# --- Valutazione di una variante generata, riparazione e test scritti dal modello piccolo ---

import os  # noqa: E402

TEST_MODEL = os.getenv("HYPERSPACE_TEST_MODEL", "granite3.3:8b")


def extract_code(text: str) -> Optional[str]:
    """Primo blocco ```python con AST valido nella risposta di un modello."""
    from shared.universal_model_parser import UniversalModelParser

    parsed = UniversalModelParser.parse(text or "")
    for block in parsed.code_blocks:
        if block.is_valid_ast and block.code.strip():
            return block.code
    return None


def tests_prompt(code: str) -> str:
    return (
        "Scrivi SOLO i test unittest per questo codice Python. Rispondi con UN SOLO blocco ```python "
        "che contiene (senza ripetere il codice sotto) `import unittest` e una classe "
        "`Test<Nome>(unittest.TestCase)` con almeno 3 test deterministici sulle classi del codice; "
        "le classi sono già nello stesso file, quindi non importarle. Solo libreria standard.\n\n"
        f"```python\n{code}\n```"
    )


def repair_prompt(code: str, failure_tail: str) -> str:
    return (
        "Il codice seguente ha test che falliscono. Correggilo mantenendo le classi e i test, e rispondi "
        "con UN SOLO blocco ```python completo e chiuso, solo libreria standard, nessun codice eseguito "
        "a livello di modulo.\n\nERRORE:\n" + failure_tail[-600:] + f"\n\nCODICE:\n```python\n{code}\n```"
    )


def with_tests(code: str, test_block: str) -> str:
    return code.rstrip() + "\n\n\n" + test_block.strip() + "\n"


def evaluate_code(code: str, workdir: Path, name: str, timeout: int = 60) -> Dict[str, Any]:
    """Cancelli statici + test del codice. ok=True solo se almeno un test gira e passa."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return {"ok": False, "reason": f"sintassi: {exc}", "has_tests": False}
    reason = static_gate(tree, 1)
    if reason:
        return {"ok": False, "reason": reason, "has_tests": False}
    if not public_classes(tree):
        return {"ok": False, "reason": "nessuna classe pubblica", "has_tests": False}
    if not embedded_test_classes(tree):
        return {"ok": False, "reason": "no_tests", "has_tests": False}
    workdir.mkdir(parents=True, exist_ok=True)
    path = workdir / f"{uuid.uuid4().hex[:8]}_{name}"
    path.write_text(code, encoding="utf-8")
    try:
        res = run_embedded_tests(path, timeout=timeout)
    finally:
        path.unlink(missing_ok=True)
    res["has_tests"] = True
    return res
