#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Sonda diagnostica read-only per la resilienza e i vault cloud della memoria Hermes.

Verifica in modalità non-mutante:
1. Integrità e presenza degli archivi locali Hermes (MEMORY.md, USER.md, state.db, skills/)
2. Stato del mirror locale HyperSpace (memory.json.gz) e della outbox (memory-outbox.jsonl)
3. Disponibilità della crittografia client-side Zero-Knowledge (AES-256-GCM / PBKDF2)
4. Raggiungibilità e credenziali dei cloud backend configurati (S3/R2, WebDAV, GitHub, IPFS)
5. Validità crittografica dell'ultimo snapshot disponibile sui remoti (se presente)

Nessun segreto (chiavi o token) viene mai stampato a video.

Uso:
    python scripts/diagnostics/hermes_resilience_probe.py
    python scripts/diagnostics/hermes_resilience_probe.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.hermes_resilience import (
    HermesMultiCloudVault,
    HermesVaultCipher,
)


def _detect_hermes_dir() -> Path | None:
    env_home = os.getenv("HERMES_HOME", "").strip()
    if env_home and Path(env_home).exists():
        return Path(env_home)

    local_app_data = os.getenv("LOCALAPPDATA", "")
    if local_app_data:
        cand = Path(local_app_data) / "hermes"
        if cand.exists():
            return cand

    user_home = Path.home() / ".hermes"
    if user_home.exists():
        return user_home

    return None


def run_probe() -> dict:
    hermes_dir = _detect_hermes_dir()
    mem_file = os.getenv("MEMORY_FILE", "").strip()
    mirror_path = Path(mem_file) if mem_file else REPO_ROOT / "data" / "control-plane" / "memory.json.gz"
    if not mirror_path.exists():
        mirror_path = REPO_ROOT / "data" / "memory.json.gz"

    outbox_file = os.getenv("MEMORY_OUTBOX_FILE", "").strip()
    outbox_path = Path(outbox_file) if outbox_file else mirror_path.with_name("memory-outbox.jsonl")

    vault = HermesMultiCloudVault.from_env()
    verification = vault.verify_all_remotes()

    # Redazione sicura: mostra solo se la chiave è presente e la sua lunghezza, MAI il valore
    cipher_configured = vault.cipher.is_configured()

    backends_summary = {}
    for b_name, b_info in verification.get("backends", {}).items():
        backends_summary[b_name] = {
            "type": b_info.get("type"),
            "healthy": b_info.get("healthy", False),
            "snapshots_count": b_info.get("snapshots_count", 0),
            "error": b_info.get("error", None),
        }

    probe_result = {
        "status": verification.get("status", "unknown"),
        "timestamp": verification.get("timestamp"),
        "encryption": {
            "configured": cipher_configured,
            "algorithm": "AES-256-GCM",
            "kdf": "PBKDF2-HMAC-SHA256 (100k iter)",
        },
        "hermes_local": {
            "path": str(hermes_dir) if hermes_dir else None,
            "has_memory_md": (hermes_dir / "MEMORY.md").exists() if hermes_dir else False,
            "has_user_md": (hermes_dir / "USER.md").exists() if hermes_dir else False,
            "has_state_db": (hermes_dir / "state.db").exists() if hermes_dir else False,
            "has_skills": (hermes_dir / "skills").is_dir() if hermes_dir else False,
        },
        "hyperspace_mirror": {
            "mirror_exists": mirror_path.exists(),
            "mirror_path": str(mirror_path) if mirror_path.exists() else None,
            "mirror_size_bytes": mirror_path.stat().st_size if mirror_path.exists() else 0,
            "outbox_exists": outbox_path.exists(),
            "outbox_path": str(outbox_path) if outbox_path.exists() else None,
        },
        "cloud_backends": backends_summary,
        "total_snapshots": verification.get("total_snapshots", 0),
        "latest_snapshot_verification": verification.get("verification", {}),
    }

    return probe_result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Formatta l'output come JSON")
    args = parser.parse_args()

    result = run_probe()

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=================================================================")
    print("      DIAGNOSI RESILIENZA MEMORIA HERMES & VAULT DECENTRALIZZATO  ")
    print("=================================================================")

    # Crittografia
    enc = result["encryption"]
    if enc["configured"]:
        print(" [OK] Crittografia Zero-Knowledge: CONFIGURATA (AES-256-GCM)")
    else:
        print(" [!] Crittografia Zero-Knowledge: NON CONFIGURATA")
        print("     -> Imposta HERMES_VAULT_PASSPHRASE per abilitare i backup remoti")

    # Hermes Local
    hl = result["hermes_local"]
    if hl["path"]:
        print(f" [OK] Runtime Hermes rilevato: {hl['path']}")
        print(f"      - MEMORY.md: {'SI' if hl['has_memory_md'] else 'NO'}")
        print(f"      - USER.md:   {'SI' if hl['has_user_md'] else 'NO'}")
        print(f"      - state.db:  {'SI' if hl['has_state_db'] else 'NO'}")
    else:
        print(" [INFO] Runtime nativo Hermes non individuato su questa macchina (normale se Hermes è su altro nodo)")

    # HyperSpace Mirror
    hm = result["hyperspace_mirror"]
    if hm["mirror_exists"]:
        print(f" [OK] Mirror locale HyperSpace: {hm['mirror_path']} ({hm['mirror_size_bytes']} bytes)")
    else:
        print(" [!] Mirror locale HyperSpace non trovato")

    # Cloud Backends
    print("\n Provider di Storage & Decentralizzazione:")
    for b_name, b_info in result["cloud_backends"].items():
        if b_info["healthy"]:
            print(f"  [+] {b_name:<16} ({b_info['type']}): CONNESSO ({b_info['snapshots_count']} snapshot)")
        else:
            print(f"  [-] {b_name:<16} ({b_info['type']}): ERRORE - {b_info['error']}")

    # Verifica Ultimo Snapshot
    v = result["latest_snapshot_verification"]
    if v.get("tested"):
        if v.get("ok"):
            print(f"\n [OK] Integrità Ultimo Snapshot ({v.get('verified_snapshot')}): VERIFICATA")
            print(f"      Voci recuperabili: {v.get('entries_count')} | Dimensione payload chiaro: {v.get('unencrypted_bytes')} B")
        else:
            print(f"\n [KO] Integrità Ultimo Snapshot ({v.get('verified_snapshot')}): FALLITA ({v.get('error')})")

    print("\nVerdetto Diagnosi:")
    if result["status"] == "healthy":
        print(" ESITO: SANO - Il sistema di resilienza è pronto e operativo.")
        return 0
    else:
        print(" ESITO: DEGRADATO - Configurare almeno un cloud backend o la passphrase master.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
