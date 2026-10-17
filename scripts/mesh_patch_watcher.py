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
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.mesh_sync import apply_mesh_update  # noqa: E402


def processa(patches: Path, repo: Path) -> dict:
    """Applica le patch `.json` presenti, una alla volta, scrivendo il risultato.

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
            result_file.write_text(json.dumps({
                "patch_id": patch.get("patch_id"),
                "processed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "status": "applied" if res.get("success") else "failed",
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
    ap.add_argument("--poll", type=float,
                    default=float(os.getenv("PATCH_WATCH_POLL_S", "10")))
    ap.add_argument("--once", action="store_true", help="processa le patch presenti ed esce")
    args = ap.parse_args(argv)

    patches = Path(args.patches)
    repo = Path(args.repo)
    patches.mkdir(parents=True, exist_ok=True)

    while True:
        res = processa(patches, repo)
        if res["applied"] or res["failed"]:
            print(f"[mesh-watcher] {res}", flush=True)
        if args.once:
            return 0
        time.sleep(max(1.0, args.poll))


if __name__ == "__main__":
    sys.exit(main())
