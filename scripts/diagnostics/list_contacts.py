#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Visualizza e gestisce i messaggi inviati dal form di contatto pubblico.

Legge i messaggi archiviati nel database SQLite persistente del Control Plane
(tabella `web_contacts`).

Uso:
  python scripts/diagnostics/list_contacts.py
  python scripts/diagnostics/list_contacts.py --limit 10
  python scripts/diagnostics/list_contacts.py --mark-read cnt-xxxx
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def find_db_path() -> Path:
    # 1. Variabile d'ambiente se impostata
    env_path = os.getenv("DB_PATH")
    if env_path and Path(env_path).exists():
        return Path(env_path)
    # 2. Volume del control plane Docker
    cp_db = ROOT / "data" / "control-plane" / "hyperspace.db"
    if cp_db.exists():
        return cp_db
    # 3. DB locale di root
    root_db = ROOT / "data" / "hyperspace.db"
    return root_db


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=find_db_path(),
                        help="Percorso al file SQLite (default: %(default)s)")
    parser.add_argument("--limit", type=int, default=20,
                        help="Numero massimo di messaggi da mostrare (default: %(default)s)")
    parser.add_argument("--status", choices=["all", "unread", "read", "archived"], default="all",
                        help="Filtra per stato (default: %(default)s)")
    parser.add_argument("--mark-read", type=str, metavar="CONTACT_ID",
                        help="Contrassegna un messaggio come 'read' tramite il suo contact_id")
    args = parser.parse_args()

    db_path = args.db
    if not db_path.exists():
        print(f"Errore: database non trovato in {db_path}")
        return 1

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    if args.mark_read:
        cur.execute("UPDATE web_contacts SET status = 'read' WHERE contact_id = ?", (args.mark_read,))
        con.commit()
        if cur.rowcount > 0:
            print(f"✓ Messaggio {args.mark_read} contrassegnato come 'read'.")
        else:
            print(f"Messaggio {args.mark_read} non trovato.")
        con.close()
        return 0

    query = "SELECT * FROM web_contacts"
    params = []
    if args.status != "all":
        query += " WHERE status = ?"
        params.append(args.status)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(args.limit)

    cur.execute(query, params)
    rows = cur.fetchall()

    cur.execute("SELECT COUNT(*), SUM(CASE WHEN status='unread' THEN 1 ELSE 0 END) FROM web_contacts")
    tot, unread = cur.fetchone()
    con.close()

    print(f"\n📬 HyperSpace Web Contacts (Totale: {tot or 0} · Non letti: {unread or 0})")
    print(f"Database: {db_path}\n" + "─" * 78)

    if not rows:
        print("Nessun messaggio trovato con i filtri selezionati.")
        return 0

    for r in rows:
        status_badge = "🔴 NON LETTO" if r["status"] == "unread" else "🟢 LETTO"
        print(f"ID: {r['contact_id']} | {r['ts']} | {status_badge}")
        print(f"Da: {r['name']} <{r['email']}>")
        if r["subject"]:
            print(f"Oggetto: {r['subject']}")
        print("Messaggio:")
        for line in str(r["message"]).splitlines():
            print(f"  {line}")
        print("─" * 78)

    return 0


if __name__ == "__main__":
    sys.exit(main())
