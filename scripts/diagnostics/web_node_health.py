#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Diagnostica per le funzioni di Web Node, Contact Form e Autenticazione.

Verifica la raggiungibilità e integrità degli endpoint /web/status, /web/contact,
/web/auth/verify e la persistenza SQLite nel database locale.
Nessun segreto o token reale viene stampato in chiaro.

Uso:
  python scripts/diagnostics/web_node_health.py
  python scripts/diagnostics/web_node_health.py --url http://127.0.0.1:8085
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import shared.db as db


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("CP_URL", "http://127.0.0.1:8085"),
                        help="URL del control-plane o gateway (default: %(default)s)")
    parser.add_argument("--timeout", type=float, default=3.0,
                        help="Timeout in secondi per richiesta (default: %(default)s)")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    print("=== HyperSpace Web Node Health & Diagnostics ===")
    print(f"Target: {base}")

    # 1. Database locale
    try:
        db.init_db()
        counts = db.count_web_contacts()
        print(f"[DB] SQLite web_contacts: OK (totale: {counts['total']}, non letti: {counts['unread']})")
    except Exception as exc:
        print(f"[DB] Errore inizializzazione SQLite: {exc}")
        return 1

    # 2. Control Plane / Gateway reachability & /web/status
    t0 = time.perf_counter()
    try:
        res = requests.get(f"{base}/web/status", timeout=args.timeout)
        ms = (time.perf_counter() - t0) * 1000.0
        if res.status_code == 200:
            info = res.json()
            nodes_count = len(info.get("nodes", []))
            print(f"[/web/status] ONLINE ({ms:.1f} ms) — nodi attivi: {nodes_count}, enabled: {info.get('enabled')}")
        else:
            print(f"[/web/status] Risposta inattesa HTTP {res.status_code} ({ms:.1f} ms)")
    except Exception as exc:
        print(f"[/web/status] Control plane non raggiungibile su {base} ({exc})")
        print("Nota: il control-plane locale potrebbe non essere avviato. Test DB locale completato.")
        return 0

    # 3. Probe Form di Contatto (/web/contact)
    try:
        # Probe validazione (invio vuoto -> atteso 400)
        res_empty = requests.post(f"{base}/web/contact", json={}, timeout=args.timeout)
        if res_empty.status_code == 400:
            print("[/web/contact] Validazione input vuoto: OK (HTTP 400 Bad Request)")
        else:
            print(f"[/web/contact] Validazione input vuoto: WARN (HTTP {res_empty.status_code})")

        # Probe honeypot (campo bot -> atteso 200 silent trap senza inquinamento)
        res_bot = requests.post(
            f"{base}/web/contact",
            json={"name": "Bot", "email": "bot@test.com", "message": "spam message", "honeypot": "trap"},
            timeout=args.timeout,
        )
        if res_bot.status_code == 200:
            print("[/web/contact] Trappola Honeypot anti-spam: OK (HTTP 200 silent)")
        else:
            print(f"[/web/contact] Trappola Honeypot: WARN (HTTP {res_bot.status_code})")
    except Exception as exc:
        print(f"[/web/contact] Errore probe: {exc}")

    # 4. Probe Autenticazione (/web/auth/verify)
    try:
        res_auth_empty = requests.post(f"{base}/web/auth/verify", json={}, timeout=args.timeout)
        if res_auth_empty.status_code == 401:
            print("[/web/auth/verify] Rigetto token vuoto: OK (HTTP 401 Unauthorized)")
        else:
            print(f"[/web/auth/verify] Rigetto token vuoto: WARN (HTTP {res_auth_empty.status_code})")

        res_auth_bad = requests.post(
            f"{base}/web/auth/verify",
            json={"token": "invalid_probe_token_12345"},
            timeout=args.timeout,
        )
        if res_auth_bad.status_code == 401:
            print("[/web/auth/verify] Rigetto token non autorizzato: OK (HTTP 401 Unauthorized)")
        else:
            print(f"[/web/auth/verify] Rigetto token non autorizzato: WARN (HTTP {res_auth_bad.status_code})")
    except Exception as exc:
        print(f"[/web/auth/verify] Errore probe: {exc}")

    print("\nVerifica diagnostica completata.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
