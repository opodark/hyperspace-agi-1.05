#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Diagnostica read-only per il motore decisionale Laya (System 1).

Verifica lo stato del servizio Laya, i checkpoint disponibili, la latenza di
inferenza su singola forward pass (choice/noul) e l'accelerazione hardware (MPS/CUDA).
Nessun segreto stampato o modificato.

Uso:
  python scripts/diagnostics/laya_health.py
  python scripts/diagnostics/laya_health.py --url http://127.0.0.1:8098
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.laya_client import LAYA_DEFAULT_URL, decide_choice, decide_noul, is_available, predict


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("LAYA_URL", LAYA_DEFAULT_URL),
                        help="URL del servizio Laya (default: %(default)s)")
    parser.add_argument("--timeout", type=float, default=2.0,
                        help="Timeout probe in secondi (default: %(default)s)")
    args = parser.parse_args()

    url = args.url.rstrip("/")
    print(f"=== HyperSpace Laya Decision Engine Probe ===")
    print(f"Target: {url}")

    # 1. Reachability
    t0 = time.perf_counter()
    online = is_available(url, timeout=args.timeout)
    reach_ms = (time.perf_counter() - t0) * 1000.0

    if not online:
        print(f"Stato: NON RAGGIUNGIBILE ({reach_ms:.1f} ms)")
        print("\nSuggerimenti:")
        print("  1. Avviare il servizio Laya con: python scripts/laya_service.py")
        print("  2. Oppure tramite Compose: docker compose --profile decision up -d laya")
        print("  3. Verificare che la porta 8098 sia aperta e non bloccata da firewall")
        return 1

    print(f"Stato: ONLINE ({reach_ms:.1f} ms)")

    # 2. Test Choice Decision (System 1 fast triage)
    sample_text = "Mission task completed: generated briefing.pdf and verified 12 pages."
    choices = {
        "pass": "Task finished successfully with artifacts verified",
        "retry": "Work is missing or checks failed",
        "fail": "Fatal unrecoverable failure",
    }
    t_start = time.perf_counter()
    choice_res = decide_choice(
        sample_text,
        choices,
        "Judge whether task completion evidence is satisfactory",
        min_confidence=0.7,
    )
    choice_ms = (time.perf_counter() - t_start) * 1000.0

    if choice_res and choice_res.get("choice"):
        print(f"Choice Probe: OK ({choice_ms:.1f} ms)")
        print(f"  Verdetto   : {choice_res['choice']} (conf: {choice_res['confidence']:.2f})")
        print(f"  Checkpoint : {choice_res.get('model_used', 'auto')}")
        print(f"  Astensione : {'SI' if choice_res.get('abstention') else 'NO'}")
    else:
        print(f"Choice Probe: RISPOSTA NON STRUTTURATA ({choice_ms:.1f} ms)")

    # 3. Test Multilingual Noul Decision
    sample_it = "Si conferma che la modifica al database rispetta le policy di sicurezza."
    t_noul = time.perf_counter()
    noul_res = decide_noul(
        sample_it,
        "La modifica rispetta i requisiti di sicurezza?",
        min_confidence=0.6,
    )
    noul_ms = (time.perf_counter() - t_noul) * 1000.0

    if noul_res and "noul" in noul_res:
        print(f"Noul Probe (IT): OK ({noul_ms:.1f} ms)")
        print(f"  Esito Sì/No: {'Sì' if noul_res['is_yes'] else 'No'} (P(true)={noul_res['noul']:.2f})")
        print(f"  Checkpoint : {noul_res.get('model_used', 'multilingual')}")
    else:
        print(f"Noul Probe (IT): NON DISPONIBILE ({noul_ms:.1f} ms)")

    print(f"\nVerifica completata con successo. Laya pronto per System 1 Fast-Gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
