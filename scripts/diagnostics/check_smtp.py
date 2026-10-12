#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Diagnostica di connessione e autenticazione SMTP per HyperSpace.

Testa la raggiungibilità del server di posta, il certificato TLS/SSL,
l'autenticazione delle credenziali configurate nel file .env e
la sintassi dell'indirizzo mittente (FROM).

Uso:
    python scripts/diagnostics/check_smtp.py [--send-test destinatario@example.com]
"""
from __future__ import annotations

import argparse
import email.utils
import os
import smtplib
import socket
import ssl
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import shared.mailer as mailer


def run_diagnostics(test_recipient: str | None = None) -> int:
    print("=" * 70)
    print("🔍 DIAGNOSTICA SMTP HYPERSPACE")
    print("=" * 70)

    cfg = mailer.get_smtp_config()
    host = cfg["host"]
    port = cfg["port"]
    user = cfg["user"]
    password = cfg["password"]
    from_addr = cfg["from_addr"]
    use_ssl = cfg["use_ssl"]

    print(f"Host:       {host or '❌ NON CONFIGURATO'}")
    print(f"Porta:      {port}")
    print(f"Utente:     {user or '❌ NON CONFIGURATO'}")
    print(f"Password:   {'✅ Presente (lunghezza ' + str(len(password)) + ')' if password else '❌ ASSENTE'}")
    print(f"From raw:   {from_addr}")
    print(f"Usa SSL:    {use_ssl}")

    # 1. Verifica sintassi From
    print("\n[1/4] Verifica sintassi indirizzo FROM...")
    display_name, extracted_email = email.utils.parseaddr(from_addr)
    print(f"  Display Name estratto:  {repr(display_name)}")
    print(f"  Email Address estratto: {repr(extracted_email)}")
    if not extracted_email or "@" not in extracted_email or " " in extracted_email or "<" in extracted_email:
        print(f"  ⚠️ ATTENZIONE: Indirizzo mittente malformato! I server SMTP rifiuteranno MAIL FROM:<{extracted_email}>")
        print("  Suggerimento: rimuovere doppi apici o formattare come: Nome Mittente <email@dominio.it>")
    else:
        print("  ✓ Sintassi indirizzo mittente valida.")

    if not host:
        print("\n❌ SMTP_HOST non impostato in .env. Impossibile procedere.")
        return 1

    # 2. Risoluzione DNS e test socket
    print(f"\n[2/4] Risoluzione DNS e connessione socket a {host}:{port}...")
    try:
        ip = socket.gethostbyname(host)
        print(f"  ✓ Risoluzione DNS riuscita: {host} -> {ip}")
    except socket.gaierror as e:
        print(f"  ❌ Risoluzione DNS fallita: {e}")
        return 1

    try:
        sock = socket.create_connection((host, port), timeout=7.0)
        sock.close()
        print(f"  ✓ Connessione TCP a {ip}:{port} riuscita.")
    except Exception as e:
        print(f"  ❌ Connessione TCP fallita a {host}:{port}: {e}")
        # Prova alternativa
        alt_port = 587 if port == 465 else 465
        print(f"  Provo porta alternativa {alt_port}...")
        try:
            sock_alt = socket.create_connection((host, alt_port), timeout=5.0)
            sock_alt.close()
            print(f"  ℹ️ NOTA: Porta alternativa {alt_port} è APERTA! Considerare cambio porta.")
        except Exception:
            print(f"  Anche la porta {alt_port} non risponde.")
        return 1

    # 3. Test Handshake e Autenticazione SMTP
    print(f"\n[3/4] Handshake SMTP e Autenticazione (Host: {host}, Porta: {port}, SSL: {use_ssl})...")
    smtp_conn = None
    try:
        context = mailer._create_ssl_context()
        if use_ssl or port == 465:
            smtp_conn = smtplib.SMTP_SSL(host, port, context=context, timeout=10.0)
        else:
            smtp_conn = smtplib.SMTP(host, port, timeout=10.0)
            smtp_conn.ehlo()
            if smtp_conn.has_extn("STARTTLS"):
                smtp_conn.starttls(context=context)
                smtp_conn.ehlo()
            else:
                print("  ℹ️ Server non offre STARTTLS.")

        print(f"  ✓ Handshake completato. Banner/EHLO accettato.")

        if user and password:
            print(f"  Tentativo di login per utente '{user}'...")
            smtp_conn.login(user, password)
            print(f"  ✓ Autenticazione SMTP RIUSCITA!")
        elif not user:
            print("  ℹ️ Nessun utente configurato.")
        else:
            print("  ⚠️ Password mancante: autenticazione saltata.")

    except smtplib.SMTPAuthenticationError as e:
        print(f"  ❌ Errore autenticazione (codice {e.smtp_code}): {e.smtp_error.decode('utf-8', errors='replace')}")
        print("  Verificare correttezza di SMTP_USER e SMTP_PASSWORD.")
        return 1
    except ssl.SSLError as e:
        print(f"  ❌ Errore SSL/TLS: {e}")
        print("  Verificare se il server supporta SSL diretto (porta 465) oppure STARTTLS (porta 587).")
        return 1
    except Exception as e:
        print(f"  ❌ Errore durante la sessione SMTP: {e}")
        return 1

    # 4. Test invio (opzionale)
    if test_recipient and smtp_conn:
        print(f"\n[4/4] Invio email di test a '{test_recipient}'...")
        try:
            sent, msg = mailer.send_key_email(
                to_email=test_recipient,
                name="Test Utente",
                auth_key="hs-mesh-test-0000"
            )
            if sent:
                print(f"  ✓ {msg}")
            else:
                print(f"  ❌ {msg}")
        except Exception as e:
            print(f"  ❌ Eccezione durante send_key_email: {e}")
        finally:
            try:
                smtp_conn.quit()
            except Exception:
                pass
    else:
        if smtp_conn:
            try:
                smtp_conn.quit()
            except Exception:
                pass
        print("\n[4/4] Test invio effettivo saltato (specifica --send-test <email> per inviare).")

    print("\n" + "=" * 70)
    print("Diagnostica completata.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send-test", type=str, default=None,
                        help="Invia un'email di prova all'indirizzo specificato")
    args = parser.parse_args()
    sys.exit(run_diagnostics(test_recipient=args.send_test))
