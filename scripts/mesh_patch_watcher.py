#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# scripts/mesh_patch_watcher.py
"""Watcher host: applica le patch P2P depositate dai nodi nella cartella scrivibile.

Il nodo (container) ha il repository montato in sola lettura (`:/repo:ro`) per la
telemetria, quindi riceve e VERIFICA la patch (E2EE + firma) ma la deposita in
`<data>/node-1/mesh-patches/`. Questo watcher gira **sull'host** — dove il
repository è scrivibile — e le applica atomicamente con backup e rollback, poi
scrive il risultato in `<id>.result.json`. È l'unico processo che tocca il codice.

Uso:
  python scripts/mesh_patch_watcher.py --patches data/node-1/mesh-patches --repo . --once
  python scripts/mesh_patch_watcher.py --patches data/node-1/mesh-patches --repo .   # ciclo
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.mesh_sync import apply_mesh_update  # noqa: E402


ROLE_TEST_SUITES: Dict[str, List[str]] = {
    "worker-gpu": [
        "tests/test_comfyui_bridge_modelli.py",
        "tests/test_image_jobs.py",
    ],
    "worker-leaf": [
        "tests/test_mesh_sync.py",
    ],
    "worker-cpu": [
        "tests/test_mesh_sync.py",
    ],
    "leaf": [
        "tests/test_mesh_sync.py",
    ],
    "authority": [
        "tests/test_mesh_sync.py",
        "tests/test_mesh_patch_watcher.py",
    ],
    "hub": [
        "tests/test_mesh_sync.py",
        "tests/test_mesh_patch_watcher.py",
    ],
}


def run_role_test_gate(node_role: str, repo: Path) -> Tuple[bool, str]:
    """Esegue la suite di test pertinente per il ruolo del nodo locale."""
    role = (node_role or "authority").lower().strip()
    test_files = ROLE_TEST_SUITES.get(role, [])
    if not test_files:
        return True, "Nessun test registrato per questo ruolo"

    existing_tests = [f for f in test_files if (repo / f).exists()]
    if not existing_tests:
        return True, "Nessun file di test trovato nel percorso del repository"

    # Ricerca binario python nel .venv del repository
    py_candidates = [
        repo / ".venv" / "bin" / "python",
        repo / ".venv" / "Scripts" / "python.exe",
        Path(sys.executable),
    ]
    py_bin = next((p for p in py_candidates if p.exists()), Path(sys.executable))

    cmd = [str(py_bin), "-m", "pytest"] + existing_tests + ["-q"]
    try:
        p = subprocess.run(
            cmd,
            cwd=str(repo),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        if p.returncode == 0:
            return True, "Role test-gate superato con successo"
        detail = (p.stdout.strip()[-300:] + " " + p.stderr.strip()[-200:]).strip()
        return False, f"Test falliti (exit code {p.returncode}): {detail}"
    except Exception as e:
        return False, f"Errore esecuzione test-gate: {e}"


def rollback_applied_files(applied_files: List[str], repo: Path) -> bool:
    """Esegue il rollback dei file applicati tramite git checkout o ripristino filesystem."""
    git_bin = shutil.which("git")
    if git_bin and (repo / ".git").exists() and applied_files:
        try:
            p = subprocess.run(
                [git_bin, "-C", str(repo), "checkout", "--"] + applied_files,
                capture_output=True,
                timeout=10,
            )
            return p.returncode == 0
        except Exception:
            return False
    return False


def processa(
    patches: Path,
    repo: Path,
    node_role: str = "authority",
    run_tests: bool = False,
) -> dict:
    """Applica le patch `.json` presenti, una alla volta, validandole con il role test-gate.

    Idempotente: una patch già elaborata (`.result.json` presente) non si riapplica.
    """
    risultati = {"applied": 0, "failed": 0}
    for patch_file in sorted(patches.glob("*.json")):
        if patch_file.name.endswith(".result.json"):
            continue
        result_file = patch_file.with_name(patch_file.stem + ".result.json")
        if result_file.exists():
            continue
        try:
            patch = json.loads(patch_file.read_text(encoding="utf-8"))
            update = patch.get("update", {})
            res = apply_mesh_update(update, repo_dir=str(repo), backup=True)

            # Esecuzione del test-gate per ruolo se l'applicazione iniziale ha avuto successo
            if res.get("success") and run_tests:
                test_ok, test_detail = run_role_test_gate(node_role, repo)
                if not test_ok:
                    rollback_ok = rollback_applied_files(res.get("applied_files", []), repo)
                    res["success"] = False
                    res["errors"].append(f"Role test-gate fallito: {test_detail}")
                    res["rollback_applied"] = rollback_ok

            result_file.write_text(json.dumps({
                "patch_id": patch.get("patch_id"),
                "processed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "status": "applied" if res.get("success") else "failed",
                "role": node_role,
                "applied_files": res.get("applied_files", []),
                "errors": res.get("errors", []),
                "rollback_applied": res.get("rollback_applied", False),
                "codebase": res.get("codebase", {}),
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            risultati["applied" if res.get("success") else "failed"] += 1
        except Exception as error:  # noqa: BLE001 — il watcher non deve mai morire
            result_file.write_text(json.dumps({
                "patch_id": patch_file.stem,
                "processed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "status": "error",
                "role": node_role,
                "errors": [str(error)],
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            risultati["failed"] += 1
    return risultati


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--patches", default="data/node-1/mesh-patches",
                    help="cartella delle patch depositate dal nodo (default: %(default)s)")
    ap.add_argument("--repo", default=".",
                    help="radice del repository da aggiornare (default: %(default)s)")
    ap.add_argument("--role", default=os.getenv("NODE_ROLE", os.getenv("NODE_TIER", "authority")),
                    help="ruolo del nodo locale per RBAC e test-gate (default: %(default)s)")
    ap.add_argument("--run-tests", action="store_true",
                    default=os.getenv("WATCHER_RUN_TESTS", "false").lower() == "true",
                    help="esegue il role test-gate dopo l'apply della patch")
    ap.add_argument("--poll", type=float,
                    default=float(os.getenv("PATCH_WATCH_POLL_S", "10")))
    ap.add_argument("--once", action="store_true", help="processa le patch presenti ed esce")
    args = ap.parse_args(argv)

    patches = Path(args.patches)
    repo = Path(args.repo)
    patches.mkdir(parents=True, exist_ok=True)

    while True:
        res = processa(patches, repo, node_role=args.role, run_tests=args.run_tests)
        if res["applied"] or res["failed"]:
            print(f"[mesh-watcher] {res}", flush=True)
        if args.once:
            return 0
        time.sleep(max(1.0, args.poll))


if __name__ == "__main__":
    sys.exit(main())

