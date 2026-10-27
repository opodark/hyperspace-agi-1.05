#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Gestione e rilascio delle chiavi di accesso (Access Key) per HyperSpace Web Node.

Permette all'operatore di generare, listare e revocare le chiavi di autenticazione
utilizzate dagli utenti per accedere ai modelli remoti della rete mesh.
Le chiavi sono salvate nel database SQLite persistente del Control Plane e
sono attive immediatamente a runtime (senza bisogno di riavviare Docker).

Uso:
  # Genera una chiave per un utente:
  python scripts/diagnostics/manage_keys.py --create --name "Ugo" --email "tecnicirollout@gmail.com"

  # Mostra tutte le chiavi emesse:
  python scripts/diagnostics/manage_keys.py --list

  # Revoca una chiave:
  python scripts/diagnostics/manage_keys.py --revoke hs-mesh-ugo-xxxx
"""
from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import shared.db as db


def find_db_path() -> Path:
    env_path = os.getenv("DB_PATH")
    if env_path and Path(env_path).exists():
        return Path(env_path)
    cp_db = ROOT / "data" / "control-plane" / "hyperspace.db"
    if cp_db.exists():
        return cp_db
    return ROOT / "data" / "hyperspace.db"


def generate_key_string(name: str) -> str:
    slug = "".join(c for c in name.lower() if c.isalnum())[:10] or "user"
    random_part = secrets.token_hex(4)
    return f"hs-mesh-{slug}-{random_part}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=find_db_path(),
                        help="Percorso al file SQLite (default: %(default)s)")
    parser.add_argument("--create", action="store_true",
                        help="Crea una nuova chiave di accesso")
    parser.add_argument("--name", type=str, default="",
                        help="Nome o alias dell'utente (es. 'Ugo')")
    parser.add_argument("--email", type=str, default="",
                        help="Indirizzo email dell'utente")
    parser.add_argument("--key", type=str, default="",
                        help="Specifica manualmente la stringa della chiave (opzionale)")
    parser.add_argument("--role", choices=["member", "admin"], default="member",
                        help="Ruolo associato alla chiave (default: member)")
    parser.add_argument("--send-email", action="store_true",
                        help="Invia automaticamente l'email con la chiave all'utente via SMTP")
    parser.add_argument("--list", action="store_true",
                        help="Mostra tutte le chiavi di accesso registrate")
    parser.add_argument("--revoke", type=str, metavar="KEY_OR_ID",
                        help="Revoca una chiave specifica tramite il valore della chiave o key_id")
    args = parser.parse_args()

    # Imposta e assicura inizializzazione tabelle
    db.DB_PATH = str(args.db)
    db.init_db()

    if args.revoke:
        revoked = db.revoke_auth_key(args.revoke)
        if revoked:
            print(f"✓ Chiave '{args.revoke}' revocata con successo.")
        else:
            print(f"Chiave '{args.revoke}' non trovata.")
        return 0

    if args.list or (not args.create and not args.revoke):
        keys = db.list_auth_keys()
        print(f"\n🔑 HyperSpace Mesh Access Keys (Totale: {len(keys)})")
        print("─" * 78)
        if not keys:
            print("Nessuna chiave emessa finora.")
            print("Crea la prima chiave con: python scripts/diagnostics/manage_keys.py --create --name \"Nome\"")
            return 0
        for k in keys:
            status_badge = "🟢 ATTIVA" if k["status"] == "active" else "🔴 REVOCATA"
            print(f"Chiave: {k.get('key_hint') or '…'} | id {k['key_id']} | {status_badge} | Ruolo: {k['role']}")
            print(f"Label:  {k['label'] or '—'}  | Email: {k['email'] or '—'}")
            print(f"Creata: {k['created_at']}  | Ultimo uso: {k['last_used'] or 'mai'}")
            print("─" * 78)
        return 0

    if args.create:
        auth_key = args.key.strip() if args.key else generate_key_string(args.name)
        label = args.name.strip() or "Utente Autorizzato"
        email = args.email.strip()

        created = db.insert_auth_key(auth_key=auth_key, label=label, email=email, role=args.role)

        print("\n" + "═" * 78)
        print("🔑 NUOVA CHIAVE MESH CREATA CON SUCCESSO!")
        print("═" * 78)
        print(f"Utente:      {created['label']}")
        if created['email']:
            print(f"Email:       {created['email']}")
        print(f"Chiave Mesh: {created['auth_key']}")
        print(f"Stato:       ATTIVA IMMEDIATAMENTE (nel database del Control Plane)")
        print("─" * 78)
        print("📋 Messaggio di risposta pronto da inviare all'utente:\n")
        message_template = f"""Ciao {label or 'utente'},
ecco la tua chiave di accesso per i modelli remoti della mesh HyperSpace:

Chiave: {auth_key}

Come utilizzarla:
1. Apri https://oszerozero.onrender.com/ (oppure https://zerozerocomputer.it/)
2. Clicca in alto a destra su "🔑 Chiave Mesh"
3. Incolla la tua chiave e premi "Verifica e Accedi"

La chat passerà automaticamente su "Mesh Remota", sbloccando tutti i modelli ad alte prestazioni della rete neurale distribuita."""
        print(message_template)
        print("═" * 78 + "\n")

        if args.send_email:
            if not email:
                print("⚠️ Invio email saltato: nessun indirizzo email specificato (--email).")
            else:
                import shared.mailer as mailer
                print(f"📧 Invio email a {email} in corso...")
                sent, msg = mailer.send_key_email(to_email=email, name=label, auth_key=auth_key)
                if sent:
                    print(f"✓ {msg}\n")
                else:
                    print(f"⚠️ {msg}\n")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
