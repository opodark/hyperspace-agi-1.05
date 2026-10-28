#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# scripts/mesh_patch_watcher.py
"""Watcher host: applica le patch P2P depositate dai nodi nella cartella scrivibile.

Il nodo (container) ha il repository montato in sola lettura (`:/repo:ro`) per la
telemetria, quindi riceve e VERIFICA la patch (E2EE + firma) ma la deposita in
`<data>/node-1/mesh-patches/`. Questo watcher gira **sull'host** — dove il
repository è scrivibile — e le applica atomicamente con backup e rollback, poi
scrive il risultato in `<id>.result.json`. È l'unico processo che tocca il codice.

Include gestione Zero-Popup su Windows (CREATE_NO_WINDOW) e trigger automatico
di rebuild per i container quando la patch tocca node/, control-plane/ o shared/.

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

# Flag per azzerare qualsiasi creazione di finestra console/popup su Windows
WIN32_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


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
    """Esegue la suite di test pertinente per il ruolo del nodo locale in modo completamente headless."""
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
            creationflags=WIN32_NO_WINDOW,
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
                creationflags=WIN32_NO_WINDOW,
            )
            return p.returncode == 0
        except Exception:
            return False
    return False


def detect_docker_actions(applied_files: List[str]) -> List[str]:
    """Determina quali container devono essere ricostruiti/riavviati in base ai file modificati."""
    actions = []
    for f in applied_files:
        norm = f.replace("\\", "/").strip("/")
        if norm.startswith(("node/", "shared/")) or norm.endswith(("docker-compose.yml", "docker-compose.windows.yml")):
            actions.append("node-1")
        if norm.startswith(("control-plane/", "shared/")):
            actions.append("control-plane")
    return list(dict.fromkeys(actions))


def emit_docker_action_signal(actions: List[str], repo: Path, patch_id: str = "") -> Optional[Path]:
    """Deposita un file di segnale atomico per notificare la necessità di rebuild/restart."""
    if not actions:
        return None
    signal_dir = repo / "data" / "node-1"
    signal_dir.mkdir(parents=True, exist_ok=True)
    signal_file = signal_dir / "docker_action.signal"
    payload = {
        "signal_id": f"sig-{int(time.time())}-{patch_id[:8] if patch_id else 'patch'}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "action": "rebuild",
        "services": actions,
        "source": "mesh_patch_watcher",
        "status": "pending",
    }
    tmp_file = signal_file.with_suffix(".tmp")
    tmp_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_file.replace(signal_file)
    return signal_file


def execute_docker_action_silently(actions: List[str], repo: Path) -> dict:
    """Esegue la ricostruzione o riavvio dei servizi in modo 100% headless (zero finestre/popup)."""
    if not actions:
        return {"executed": False, "reason": "no_actions"}

    log_file = repo / "data" / "docker_rebuild.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # 1. Host Windows: esegue rebuild-node.ps1 in modo nascosto
    if sys.platform == "win32" and "node-1" in actions:
        rebuild_script = repo / "scripts" / "rebuild-node.ps1"
        if rebuild_script.exists():
            cmd = [
                "powershell.exe",
                "-WindowStyle", "Hidden",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", str(rebuild_script),
            ]
            try:
                p = subprocess.run(
                    cmd,
                    cwd=str(repo),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=180,
                    creationflags=WIN32_NO_WINDOW,
                )
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] DOCKER REBUILD (Windows node-1): exit {p.returncode}\n{p.stdout}\n{p.stderr}\n")
                return {"executed": True, "success": p.returncode == 0, "platform": "win32", "services": actions}
            except Exception as e:
                return {"executed": True, "success": False, "error": str(e), "platform": "win32"}

    # 2. Host macOS / Linux
    docker_bin = shutil.which("docker")
    if docker_bin:
        try:
            cmd = [docker_bin, "compose", "up", "-d", "--build"] + actions
            p = subprocess.run(
                cmd,
                cwd=str(repo),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=240,
                creationflags=WIN32_NO_WINDOW,
            )
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] DOCKER REBUILD ({actions}): exit {p.returncode}\n{p.stdout}\n{p.stderr}\n")
            return {"executed": True, "success": p.returncode == 0, "platform": sys.platform, "services": actions}
        except Exception as e:
            return {"executed": True, "success": False, "error": str(e), "platform": sys.platform}

    return {"executed": False, "reason": "no_docker_runner_found"}


def processa(
    patches: Path,
    repo: Path,
    node_role: str = "authority",
    run_tests: bool = False,
    auto_rebuild: bool = True,
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

            # Rilevamento e dispatch segnale Docker se la patch è stata applicata con successo
            docker_actions = []
            docker_rebuild_res = None
            if res.get("success"):
                docker_actions = detect_docker_actions(res.get("applied_files", []))
                if docker_actions:
                    emit_docker_action_signal(docker_actions, repo, patch.get("patch_id", ""))
                    if auto_rebuild:
                        docker_rebuild_res = execute_docker_action_silently(docker_actions, repo)

            result_file.write_text(json.dumps({
                "patch_id": patch.get("patch_id"),
                "processed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "status": "applied" if res.get("success") else "failed",
                "role": node_role,
                "applied_files": res.get("applied_files", []),
                "errors": res.get("errors", []),
                "rollback_applied": res.get("rollback_applied", False),
                "docker_actions": docker_actions,
                "docker_rebuild": docker_rebuild_res,
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
                    help="esegue i test associati al ruolo prima di confermare la patch")
    ap.add_argument("--no-auto-rebuild", action="store_true",
                    help="disattiva il rebuild automatico dei container dopo l'applicazione")
    ap.add_argument("--once", action="store_true",
                    help="esegue una sola passata e termina")
    ap.add_argument("--interval", type=float, default=2.0,
                    help="intervallo del ciclo in secondi (default: %(default)s)")
    args = ap.parse_args(argv)

    patches_dir = (Path(args.repo) / args.patches).resolve()
    repo_dir = Path(args.repo).resolve()
    patches_dir.mkdir(parents=True, exist_ok=True)
    auto_rebuild = not args.no_auto_rebuild

    if args.once:
        ris = processa(patches_dir, repo_dir, node_role=args.role, run_tests=args.run_tests, auto_rebuild=auto_rebuild)
        print(f"mesh_patch_watcher: applied={ris['applied']} failed={ris['failed']}")
        return 0

    print(f"mesh_patch_watcher attivo (role={args.role}, zero-popup=on, auto-rebuild={auto_rebuild}) su {patches_dir} (Ctrl+C per uscire)")
    try:
        while True:
            processa(patches_dir, repo_dir, node_role=args.role, run_tests=args.run_tests, auto_rebuild=auto_rebuild)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nmesh_patch_watcher terminato")
        return 0


if __name__ == "__main__":
    sys.exit(main())
