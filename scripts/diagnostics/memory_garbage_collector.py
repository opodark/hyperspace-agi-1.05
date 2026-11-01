#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Diagnostica e Garbage Collector delle Allucinazioni HyperSpace AGI.

Esegue la scansione prudente della memoria secondo docs/memory-evidence-tiers.md:
1. Scadenza memorie plausible di retention 'project', mai consultate da N giorni (default 14).
2. Rilevamento collisioni tra ipotesi attive e memorie smentite (refuted) o sogni rifiutati (sovrapposizione token >= 0.8).
3. Ricontrollo a campione dei check deterministici delle memorie 'verified'; declassamento a 'plausible' se il check fallisce.

Regole ferree:
- MAI cancellare o revocare record 'refuted'.
- MAI alzare i livelli di evidenza.
- MAI toccare MEMORY.md o il profilo utente (USER.md).
- MAI toccare memorie persistenti (dream_insight, vault_note).

Uso:
  python scripts/diagnostics/memory_garbage_collector.py                  # Dry-run di simulazione
  python scripts/diagnostics/memory_garbage_collector.py --apply          # Applica le quarantene e declassamenti
  python scripts/diagnostics/memory_garbage_collector.py --days 7         # Soglia 7 giorni di inattività
  python scripts/diagnostics/memory_garbage_collector.py --json           # Output strutturato JSON
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.hermes_memory import HermesMemoryClient, HermesMemoryError
from shared.memory_gc import (
    DEFAULT_REFUTE_OVERLAP_THRESHOLD,
    DEFAULT_UNACCESSED_DAYS,
    MemoryGarbageCollector,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Garbage Collector delle Allucinazioni per i Livelli di Evidenza della Memoria (docs/memory-evidence-tiers.md)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Applica effettivamente le modifiche a Hermes (senza questo flag gira in dry-run sicuro)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Esegue la scansione in sola lettura senza applicare modifiche (attivo di default)",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="URL del bridge Hermes (default: env HERMES_MEMORY_URL oppure http://127.0.0.1:8098 sull'host)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_UNACCESSED_DAYS,
        help=f"Giorni di mancata consultazione prima della quarantena per record plausible (default: {DEFAULT_UNACCESSED_DAYS})",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_REFUTE_OVERLAP_THRESHOLD,
        help=f"Soglia di sovrapposizione token per collisioni con record smentiti (default: {DEFAULT_REFUTE_OVERLAP_THRESHOLD})",
    )
    parser.add_argument(
        "--no-audit",
        action="store_true",
        help="Disabilita il ricontrollo dei check deterministici delle memorie verified",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Numero massimo di memorie verified da rieseguire a campione",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Stampa il report completo in formato JSON",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Stampa dettagli operativi su ogni candidato",
    )

    args = parser.parse_args()
    dry_run = not args.apply

    bridge_url = args.url or os.getenv("HERMES_MEMORY_URL") or "http://127.0.0.1:8098"
    client = HermesMemoryClient(base_url=bridge_url)
    gc = MemoryGarbageCollector(client=client, repo_root=ROOT)

    report = gc.run_gc(
        days_unaccessed=args.days,
        refute_threshold=args.threshold,
        audit_verified=not args.no_audit,
        sample_size=args.sample,
        dry_run=dry_run,
    )

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report.get("ok") else 1

    mode_label = "🟡 SIMULAZIONE (DRY-RUN)" if dry_run else "🟢 ESECUZIONE ATTIVA (--apply)"
    print("=" * 72)
    print(" HYPERSPACE MEMORY GARBAGE COLLECTOR — HALLUCINATION SWEEP")
    print(f" Modalità: {mode_label}")
    print(f" Bridge Hermes: {bridge_url}")
    print(f" Timestamp: {report.get('timestamp')}")
    print(f" Memorie scansionate: {report.get('scanned_entries', 0)}")
    print(f" Parametri: soglia inattività = {args.days}d, soglia collisione = {args.threshold}")
    print("=" * 72)

    if not report.get("ok") and "error" in report:
        print(f"\n⚠️  ATTENZIONE: {report['error']}")
        print("   Il servizio bridge Hermes non risponde sull'endpoint specificato.")
        print("   Per avviarlo sul host eseguire:")
        print("     python scripts/hermes_memory_bridge.py")
        print("\n" + "=" * 72)
        return 1

    # 1. Scadenza plausible
    print(f"\n[1] Memorie Plausible Progetto Inattive: {report.get('quarantined_expired_count', 0)} candidate")
    for item in report.get("expired_candidates", []):
        print(f"  - {item['id'][:24]}... (inattiva da {item['age_days']}d)")
        if args.verbose:
            print(f"    Motivo: {item['reason']}")

    # 2. Collisioni smentite
    print(f"\n[2] Collisioni con Claim Smentiti (Refuted): {report.get('quarantined_collision_count', 0)} candidate")
    for item in report.get("collision_candidates", []):
        print(f"  - {item['id'][:24]}... (overlap {item['overlap']:.2f} con {item['refuted_id'][:20]})")

    # 3. Audit verified
    print(f"\n[3] Ricontrollo Verifiche Deterministiche: {report.get('verified_audited_count', 0)} auditate")
    if report.get("verified_downgrade_count", 0) > 0:
        print(f"  ⚠️ Declassamenti a 'plausible': {report['verified_downgrade_count']}")
        for item in report.get("downgrade_candidates", []):
            print(f"  - {item['id'][:24]}... -> {item['reason']}")
    else:
        print("  ✅ Tutti i check verificati sono passati senza regressioni.")

    # Invarianti
    print("\n[4] Garanzie di Sicurezza Epistemica:")
    for k, v in report.get("guarantees", {}).items():
        symbol = "✅" if v else "❌"
        print(f"  {symbol} {k}: {v}")

    # Azioni applicate
    if dry_run:
        total_quarantine = report.get("total_quarantine_candidates", 0)
        total_downgrade = report.get("verified_downgrade_count", 0)
        print(f"\nℹ️  In modalità dry-run nessuna modifica è stata applicata.")
        print(f"   (Per applicare {total_quarantine} quarantene e {total_downgrade} declassamenti, esegui con --apply)")
    else:
        print(f"\n✅ Azioni applicate:")
        print(f"  - Quarantene eseguite: {len(report.get('quarantined_applied', []))}")
        print(f"  - Declassamenti eseguiti: {len(report.get('downgraded_applied', []))}")
        if report.get("errors"):
            print(f"  ⚠️ Errori riscontrati: {len(report['errors'])}")
            for err in report["errors"]:
                print(f"    - {err}")

    print("\n" + "=" * 72)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
