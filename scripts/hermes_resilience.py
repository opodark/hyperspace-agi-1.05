#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""CLI per la resilienza e replica cloud decentralizzata della memoria Hermes.

Uso:
    # Stato di salute, crittografia e cloud backends configurati
    python scripts/hermes_resilience.py --status

    # Crea uno snapshot cifrato Zero-Knowledge e lo invia a tutti i cloud
    python scripts/hermes_resilience.py --snapshot --tag "pre_upgrade"

    # Elenca tutti gli snapshot disponibili nei vault locali e remoti
    python scripts/hermes_resilience.py --list

    # Verifica la connettività di tutti i provider e l'integrità dell'ultimo vault
    python scripts/hermes_resilience.py --verify

    # Ripristina uno snapshot in una directory di destinazione (Disaster Recovery)
    python scripts/hermes_resilience.py --restore [ID_O_FILE] --target-dir ./hermes_recovered

    # Esegue il pruning degli snapshot remoti eccedenti la retention (default: 7)
    python scripts/hermes_resilience.py --prune --keep 7

Variabili d'ambiente per la configurazione:
    HERMES_VAULT_PASSPHRASE       Passphrase master per la cifratura AES-256-GCM
    HERMES_VAULT_KEY_FILE         File contenente la passphrase master
    HERMES_VAULT_LOCAL_DIR        Directory locale per vault offline/mount rclone
    HERMES_VAULT_S3_ENDPOINT      Endpoint S3 (es. Cloudflare R2, Backblaze B2, AWS)
    HERMES_VAULT_S3_BUCKET        Nome del bucket S3
    HERMES_VAULT_S3_KEY           Access Key ID
    HERMES_VAULT_S3_SECRET        Secret Access Key
    HERMES_VAULT_WEBDAV_URL       URL WebDAV (es. Nextcloud, ownCloud, pCloud)
    HERMES_VAULT_WEBDAV_USER      Username WebDAV
    HERMES_VAULT_WEBDAV_PASS      Password/Token applicazione WebDAV
    HERMES_VAULT_GITHUB_TOKEN     GitHub Personal Access Token (per Gist privato)
    HERMES_VAULT_GITHUB_GIST_ID   ID del Gist privato (opzionale, auto-creato)
    HERMES_VAULT_IPFS_API         URL RPC nodo IPFS locale (default: http://127.0.0.1:5001)
    HERMES_VAULT_PINATA_JWT       JWT API per pinning su cloud Pinata
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Aggiunge root al PYTHONPATH per importare shared
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.hermes_memory import HermesMemoryClient
from shared.hermes_resilience import (
    DEFAULT_RETENTION,
    HermesCryptoError,
    HermesMultiCloudVault,
    HermesVaultCipher,
)


def _detect_hermes_dir() -> Optional[Path]:
    """Individua la directory di runtime Hermes su Mac, Linux o Windows."""
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


def _detect_memory_files() -> tuple[Optional[Path], Optional[Path]]:
    """Trova il mirror locale e la coda outbox di HyperSpace."""
    mem_file = os.getenv("MEMORY_FILE", "").strip()
    mirror_path = Path(mem_file) if mem_file else REPO_ROOT / "data" / "control-plane" / "memory.json.gz"
    if not mirror_path.exists():
        mirror_path = REPO_ROOT / "data" / "memory.json.gz"

    outbox_file = os.getenv("MEMORY_OUTBOX_FILE", "").strip()
    outbox_path = Path(outbox_file) if outbox_file else mirror_path.with_name("memory-outbox.jsonl")

    return (
        mirror_path if mirror_path.exists() else None,
        outbox_path if outbox_path.exists() else None,
    )


def cmd_status(vault: HermesMultiCloudVault, json_mode: bool = False) -> int:
    hermes_dir = _detect_hermes_dir()
    mirror_file, outbox_file = _detect_memory_files()
    verification = vault.verify_all_remotes()

    report = {
        "encryption": {
            "configured": vault.cipher.is_configured(),
            "algorithm": "AES-256-GCM",
            "kdf": "PBKDF2-HMAC-SHA256 (100k iter)",
        },
        "hermes_local": {
            "found": hermes_dir is not None,
            "path": str(hermes_dir) if hermes_dir else None,
            "has_memory_md": (hermes_dir / "MEMORY.md").exists() if hermes_dir else False,
            "has_user_md": (hermes_dir / "USER.md").exists() if hermes_dir else False,
            "has_state_db": (hermes_dir / "state.db").exists() if hermes_dir else False,
        },
        "hyperspace_mirror": {
            "mirror_file": str(mirror_file) if mirror_file else None,
            "outbox_file": str(outbox_file) if outbox_file else None,
        },
        "backends": verification.get("backends", {}),
        "total_snapshots": verification.get("total_snapshots", 0),
        "latest_verification": verification.get("verification", {}),
    }

    if json_mode:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    print("=== HYPERSPACE HERMES RESILIENCE VAULT ===")
    print(f"Crittografia Zero-Knowledge: {'ATTIVA (AES-256-GCM)' if report['encryption']['configured'] else 'NON CONFIGURATA'}")
    if not report['encryption']['configured']:
        print("  [!] Imposta HERMES_VAULT_PASSPHRASE o HERMES_VAULT_KEY_FILE per abilitare i backup.")

    print(f"\nSorgenti Locali:")
    print(f"  - Hermes Home: {report['hermes_local']['path'] or 'non trovata'}")
    if report['hermes_local']['found']:
        print(f"    MEMORY.md: {'presente' if report['hermes_local']['has_memory_md'] else 'assente'}")
        print(f"    state.db:  {'presente' if report['hermes_local']['has_state_db'] else 'assente'}")
    print(f"  - Mirror Gzip: {report['hyperspace_mirror']['mirror_file'] or 'non trovato'}")
    print(f"  - Outbox Coda: {report['hyperspace_mirror']['outbox_file'] or 'assente'}")

    print(f"\nProvider Cloud & Decentralizzati Connessi:")
    for b_name, b_info in report["backends"].items():
        state = "OK (Sano)" if b_info.get("healthy") else f"ERRORE ({b_info.get('error', 'non raggiungibile')})"
        print(f"  - [{b_name}] ({b_info.get('type')}): {state}")

    print(f"\nSnapshot Totali Disponibili: {report['total_snapshots']}")
    v = report["latest_verification"]
    if v.get("tested"):
        v_status = "VERIFICATO CON SUCCESSO" if v.get("ok") else f"FALLITO ({v.get('error')})"
        print(f"Ultima Verifica Round-trip: {v_status} ({v.get('verified_snapshot')})")

    return 0


def cmd_snapshot(vault: HermesMultiCloudVault, tag: str = "auto", json_mode: bool = False) -> int:
    if not vault.cipher.is_configured():
        print("Errore: Passphrase di cifratura non configurata (HERMES_VAULT_PASSPHRASE).", file=sys.stderr)
        return 1

    hermes_dir = _detect_hermes_dir()
    mirror_file, outbox_file = _detect_memory_files()

    # Tenta di interrogare il bridge Hermes se attivo
    bridge_entries = None
    try:
        client = HermesMemoryClient(timeout=2.0)
        bridge_entries = client.entries(limit=1000)
    except Exception:
        pass

    try:
        res = vault.create_and_push_snapshot(
            hermes_dir=hermes_dir,
            memory_mirror_file=mirror_file,
            memory_outbox_file=outbox_file,
            hermes_client_entries=bridge_entries,
            tag=tag,
        )
    except Exception as exc:
        print(f"Errore durante la creazione dello snapshot: {exc}", file=sys.stderr)
        return 1

    if json_mode:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res.get("ok") else 1

    print("=== CREAZIONE SNAPSHOT COMPLETATA ===")
    print(f"Snapshot ID:        {res['snapshot_id']}")
    print(f"File Vault:         {res['filename']}")
    print(f"Dimensione Cifrata: {res['ciphertext_bytes']} bytes")
    print(f"Dimensione Chiara:  {res['unencrypted_bytes']} bytes")
    print(f"Voci di Memoria:    {res['entries_count']}")
    print("\nEsito Destinazioni:")
    for b_name, b_res in res["targets_results"].items():
        status = "OK" if b_res.get("ok") else f"KO: {b_res.get('error')}"
        print(f"  - {b_name}: {status}")

    if res.get("pruned"):
        pruned_info = ", ".join(f"{k}: {v}" for k, v in res["pruned"].items() if v > 0)
        if pruned_info:
            print(f"\nSnapshot obsoleti rimossi per retention: {pruned_info}")

    return 0 if res.get("ok") else 1


def cmd_list(vault: HermesMultiCloudVault, json_mode: bool = False) -> int:
    snaps = vault.list_all_snapshots()
    if json_mode:
        print(json.dumps(snaps, indent=2, ensure_ascii=False))
        return 0

    print("=== SNAPSHOT VAULT DISPONIBILI SUI PROVIDER ===")
    if not snaps:
        print("Nessuno snapshot trovato nei vault configurati.")
        return 0

    print(f"{'FILENAME':<45} {'DIMENSIONE':<12} {'DISPONIBILE SU'}")
    print("-" * 80)
    for s in snaps:
        size_kb = f"{round(s.get('size_bytes', 0) / 1024, 1)} KB"
        providers = ", ".join(s.get("available_on", []))
        print(f"{s['filename']:<45} {size_kb:<12} {providers}")

    return 0


def cmd_verify(vault: HermesMultiCloudVault, json_mode: bool = False) -> int:
    verification = vault.verify_all_remotes()
    if json_mode:
        print(json.dumps(verification, indent=2, ensure_ascii=False))
        return 0 if verification.get("status") == "healthy" else 1

    print("=== VERIFICA CONNETTIVITÀ & INTEGRITÀ PROVIDER ===")
    for b_name, b_info in verification.get("backends", {}).items():
        st = "ONLINE" if b_info.get("healthy") else f"OFFLINE: {b_info.get('error')}"
        print(f"Provider [{b_name}]: {st}")

    v = verification.get("verification", {})
    if v.get("tested"):
        print(f"\nTest Integrità Crittografica Ultimo Snapshot ({v.get('verified_snapshot')}):")
        if v.get("ok"):
            print(f"  [OK] Decifratura AES-256-GCM riuscita. SHA256 verificato. Voci: {v.get('entries_count')}")
        else:
            print(f"  [KO] Errore verifica: {v.get('error')}")

    return 0 if verification.get("status") == "healthy" else 1


def cmd_restore(
    vault: HermesMultiCloudVault,
    snapshot_id: Optional[str],
    target_dir: str,
    json_mode: bool = False,
) -> int:
    if not vault.cipher.is_configured():
        print("Errore: Passphrase di cifratura non configurata (HERMES_VAULT_PASSPHRASE).", file=sys.stderr)
        return 1

    target_path = Path(target_dir).resolve()
    print(f"Ripristino in corso in: {target_path} ...")

    try:
        res = vault.restore_to_directory(target_path, snapshot_id)
    except Exception as exc:
        print(f"Errore durante il ripristino: {exc}", file=sys.stderr)
        return 1

    if json_mode:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0

    print("=== RIPRISTINO COMPLETATO ===")
    print(f"Snapshot ID:        {res.get('snapshot_id')}")
    print(f"Scaricato da:       {res.get('source_backend')}")
    print(f"File estratti ({len(res['extraction']['extracted_files'])}):")
    for f in res['extraction']['extracted_files']:
        print(f"  - {f}")

    return 0


def cmd_prune(vault: HermesMultiCloudVault, keep: int, json_mode: bool = False) -> int:
    pruned = vault.prune_all(keep=keep)
    if json_mode:
        print(json.dumps(pruned, indent=2, ensure_ascii=False))
        return 0

    print(f"=== PRUNING COMPLETATO (Conservati gli ultimi {keep} snapshot) ===")
    for b_name, count in pruned.items():
        print(f"  - {b_name}: {count} rimossi")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gestione Resilienza e Decentralizzazione Cloud Memoria Hermes HyperSpace"
    )
    parser.add_argument("--status", action="store_true", help="Mostra lo stato di salute e i provider")
    parser.add_argument("--snapshot", action="store_true", help="Crea e carica un nuovo snapshot cifrato")
    parser.add_argument("--list", action="store_true", help="Elenca gli snapshot presenti sui provider")
    parser.add_argument("--verify", action="store_true", help="Verifica raggiungibilità e integrità")
    parser.add_argument("--restore", nargs="?", const="", help="Ripristina uno snapshot (ID o nome file opzionale)")
    parser.add_argument("--prune", action="store_true", help="Pota gli snapshot obsoleti")
    parser.add_argument("--keep", type=int, default=DEFAULT_RETENTION, help="Numero di snapshot da conservare nel prune")
    parser.add_argument("--target-dir", default="./hermes_restored", help="Cartella di destinazione per restore")
    parser.add_argument("--tag", default="manual", help="Tag descrittivo per lo snapshot")
    parser.add_argument("--passphrase", help="Passphrase master temporanea (sconsigliata su CLI, preferire env)")
    parser.add_argument("--json", action="store_true", help="Output in formato JSON")

    args = parser.parse_args()

    vault = HermesMultiCloudVault.from_env()
    if args.passphrase:
        vault.cipher = HermesVaultCipher(passphrase=args.passphrase)

    if args.status or (not any([args.snapshot, args.list, args.verify, args.restore is not None, args.prune])):
        return cmd_status(vault, json_mode=args.json)
    if args.snapshot:
        return cmd_snapshot(vault, tag=args.tag, json_mode=args.json)
    if args.list:
        return cmd_list(vault, json_mode=args.json)
    if args.verify:
        return cmd_verify(vault, json_mode=args.json)
    if args.restore is not None:
        return cmd_restore(vault, args.restore if args.restore else None, args.target_dir, json_mode=args.json)
    if args.prune:
        return cmd_prune(vault, keep=args.keep, json_mode=args.json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
