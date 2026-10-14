#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# scripts/mesh_distribute.py
"""Strumento CLI per la distribuzione P2P cifrata di codice e Knowledge Graph ai nodi della mesh.

Permette di sincronizzare commit Git, file e artefatti Graphify verso nodi remoti
(Mac, HP Omen, ecc.) in modalità decentralizzata senza dipendere da GitHub.

Uso:
  python scripts/mesh_distribute.py --all
  python scripts/mesh_distribute.py --target http://100.81.234.102:8081
  python scripts/mesh_distribute.py --sync-graphify --all
  python scripts/mesh_distribute.py --base HEAD~2 --target-commit HEAD --all
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.identity import generate_or_load_identity
from shared.mesh_sync import (
    create_git_patch_payload,
    create_graphify_bundle_payload,
    distribute_payload_to_node,
)


def _log(tag: str, msg: str, color: str = ""):
    colors = {
        "cyan": "\033[96m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "reset": "\033[0m",
        "bold": "\033[1m",
    }
    prefix = f"{colors.get(color, '')}[{tag}]{colors['reset']} " if color else f"[{tag}] "
    print(f"{prefix}{msg}")


def get_active_mesh_nodes(cp_url: str = "http://127.0.0.1:8085") -> List[Dict[str, Any]]:
    """Recupera la lista dei nodi attivi interrogando il control-plane locale."""
    try:
        r = requests.get(f"{cp_url}/nodes/active", timeout=3)
        if r.status_code == 200:
            return [n for n in r.json() if not n.get("is_local")]
    except Exception:
        pass
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=str, help="Endpoint HTTP del singolo nodo target (es. http://100.81.234.102:8081)")
    parser.add_argument("--all", action="store_true", help="Invia l'aggiornamento a tutti i nodi remoti attivi nella mesh")
    parser.add_argument("--base", default="HEAD~1", help="Commit di riferimento base per la diff (default: %(default)s)")
    parser.add_argument("--target-commit", default="HEAD", help="Commit target da distribuire (default: %(default)s)")
    parser.add_argument("--files", type=str, help="Elenco separato da virgola di file specifici da includere direttamente")
    parser.add_argument("--sync-graphify", action="store_true", help="Invia il Knowledge Graph (graph.json e .graphify_analysis.json)")
    parser.add_argument("--cp-url", default=os.getenv("CONTROL_PLANE_URL", "http://127.0.0.1:8085"), help="URL Control Plane locale")
    args = parser.parse_args()

    _log("MESH-DISTRIBUTE", "HyperSpace P2P Code & Knowledge Graph Distribution", "cyan")

    # 1. Carica l'identità crittografica del mittente (Hub / Control-Plane)
    identity = generate_or_load_identity()
    sender_id = identity["node_id"]
    sender_pub = identity["public_key"]
    _log("IDENTITY", f"Mittente: {sender_id[:16]}... (Pubkey: {sender_pub[:16]}...)", "cyan")

    # 2. Prepara il payload di aggiornamento
    if args.sync_graphify:
        _log("PACK", "Compilazione pacchetto Knowledge Graph (Graphify)...", "cyan")
        payload = create_graphify_bundle_payload(repo_dir=str(ROOT))
        file_count = len(payload.get("files", {}))
        if file_count == 0:
            _log("ERROR", "Nessun artefatto Graphify trovato in graphify-out/", "red")
            return 1
        _log("PACK", f"Pronto bundle Graphify ({file_count} file compressi)", "green")
    else:
        files_list = [f.strip() for f in args.files.split(",")] if args.files else None
        _log("PACK", f"Generazione diff git tra {args.base} e {args.target_commit}...", "cyan")
        payload = create_git_patch_payload(
            base_commit=args.base,
            target_commit=args.target_commit,
            repo_dir=str(ROOT),
            include_files=files_list,
        )
        meta = payload.get("commit_metadata", {})
        if meta.get("short_sha"):
            _log("PACK", f"Commit target: {meta['short_sha']} - '{meta.get('subject', '')}'", "green")
        if files_list:
            _log("PACK", f"File diretti inclusi: {len(payload.get('direct_files', {}))}", "green")

    # 3. Individua i destinatari
    targets = []
    if args.target:
        # Recupera pubkey interrogando /status del nodo target se possibile
        target_ep = args.target.strip().rstrip("/")
        pubkey = ""
        try:
            r = requests.get(f"{target_ep}/status", timeout=2)
            if r.status_code == 200:
                pubkey = r.json().get("public_key", "")
        except Exception:
            pass
        targets.append({"endpoint": target_ep, "public_key": pubkey, "alias": "nodo-diretto"})
    elif args.all:
        nodes = get_active_mesh_nodes(args.cp_url)
        for n in nodes:
            ep = n.get("endpoint")
            pk = n.get("public_key")
            if ep and pk:
                targets.append({"endpoint": ep, "public_key": pk, "alias": n.get("alias") or n.get("node_id", "")[:8]})
        if not targets:
            _log("WARN", "Nessun nodo remoto attivo trovato tramite il Control-Plane.", "yellow")
            return 0
    else:
        _log("ERROR", "Specificare un nodo con --target <url> oppure --all per l'intero cluster.", "red")
        return 1

    # 4. Distribuzione cifrata verso ciascun nodo
    successes = 0
    for t in targets:
        ep = t["endpoint"]
        pubkey = t["public_key"]
        alias = t["alias"]
        if not pubkey:
            _log("SKIP", f"Nodo {alias} ({ep}) senza public_key nota, impossibile cifrare E2EE.", "yellow")
            continue

        _log("SEND", f"Cifratura E2EE ed invio verso {alias} ({ep})...", "cyan")
        res = distribute_payload_to_node(
            node_endpoint=ep,
            node_pubkey_hex=pubkey,
            update_payload=payload,
            sender_identity=identity,
        )

        if res.get("success"):
            ack = res.get("ack", {})
            status = ack.get("status", "unknown")
            cb = ack.get("codebase", {})
            applied_files = ack.get("applied_files", [])
            _log("OK", f"Nodo {alias}: Stato = {status.upper()} (Commit={cb.get('git_commit', 'n/d')}, File applicati={len(applied_files)})", "green")
            successes += 1
        else:
            _log("FAIL", f"Nodo {alias}: Errore = {res.get('error') or res.get('status_code')}", "red")

    _log("SUMMARY", f"Completato: {successes}/{len(targets)} nodi sincronizzati con successo.", "cyan")
    return 0 if successes == len(targets) else 1


if __name__ == "__main__":
    sys.exit(main())
