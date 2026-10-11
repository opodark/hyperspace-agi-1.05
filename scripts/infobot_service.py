#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Servizio interattivo per il bot Telegram (@hyperspace_infobot).

Permette all'operatore di gestire i contatti web e rilasciare chiavi di accesso (Access Key)
direttamente da Telegram con 1 tocco o tramite comandi chat:

Funzionalità:
- Pulsante inline [ 🔑 Emetti e Invia Token a <Nome> ] sui messaggi di notifica contatti
- Invio automatico dell'email all'utente via SMTP (con template HTML/testo Cyberpunk)
- Comandi chat supportati:
    /grant <email_o_id>       Emette la chiave per il contatto e la spedisce via email
    /keygen <nome> <email>    Genera una nuova chiave e la invia all'email specificata
    /contacts                 Elenco ultimi contatti ricevuti con pulsanti inline
    /keys                     Elenco chiavi attive e ultimo utilizzo
    /revoke <chiave>          Revoca una chiave di accesso
    /status                   Stato del bot, database e configurazione SMTP
    /help                     Riepilogo comandi

Avvio:
    python scripts/infobot_service.py
"""
from __future__ import annotations

import argparse
import atexit
import html
import os
import re
import secrets
import signal
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import shared.db as db
import shared.mailer as mailer

LOCK_FILE = ROOT / "data" / "infobot.lock"


def load_env_if_missing():
    """Carica variabili da .env se non già presenti in os.environ."""
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if k not in os.environ:
                os.environ[k] = v


load_env_if_missing()


def acquire_lock() -> bool:
    os.makedirs(LOCK_FILE.parent, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            # Controlla se il PID è attivo
            os.kill(pid, 0)
            return False
        except (ValueError, OSError):
            pass  # Processo precedente terminato
    LOCK_FILE.write_text(str(os.getpid()))
    return True


def release_lock():
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception:
        pass


atexit.register(release_lock)


class InfoBotService:
    def __init__(self, token: str, chat_id: str):
        self.token = token.strip()
        self.chat_id = str(chat_id).strip()
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.running = True

    def _call(self, method: str, payload: dict | None = None, timeout: float = 30.0) -> dict | None:
        try:
            url = f"{self.api_url}/{method}"
            res = requests.post(url, json=payload or {}, timeout=timeout)
            if res.ok:
                data = res.json()
                if data.get("ok"):
                    return data.get("result")
            print(f"[Bot] API {method} error: HTTP {res.status_code} - {res.text[:150]}")
            return None
        except Exception as exc:
            print(f"[Bot] API {method} exception: {exc}")
            return None

    def send_message(self, text: str, reply_markup: dict | None = None, chat_id: str | None = None) -> dict | None:
        target = chat_id or self.chat_id
        payload = {
            "chat_id": target,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self._call("sendMessage", payload)

    def answer_callback(self, callback_id: str, text: str = "", show_alert: bool = False):
        self._call("answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": text,
            "show_alert": show_alert,
        })

    def edit_reply_markup(self, message_id: int, reply_markup: dict | None = None, chat_id: str | None = None):
        self._call("editMessageReplyMarkup", {
            "chat_id": chat_id or self.chat_id,
            "message_id": message_id,
            "reply_markup": reply_markup or {"inline_keyboard": []},
        })

    def is_authorized(self, user_id: int | str) -> bool:
        return str(user_id) == self.chat_id

    # ── LOGICA GESTIONE CHIAVE ED EMAIL ────────────────────────────────────────

    def issue_and_send_key(self, name: str, email: str, contact_id: str | None = None) -> tuple[bool, str, str]:
        """Emette la chiave nel DB e invia l'email.
        
        Ritorna (success: bool, auth_key: str, message: str).
        """
        slug = "".join(c for c in name.lower() if c.isalnum())[:10] or "user"
        random_part = secrets.token_hex(4)
        auth_key = f"hs-mesh-{slug}-{random_part}"
        clean_name = name.strip() or "Utente Autorizzato"
        clean_email = email.strip()

        # 1. Salva nel DB
        db.insert_auth_key(auth_key=auth_key, label=clean_name, email=clean_email, role="member")

        # 2. Aggiorna stato contatto se presente
        if contact_id:
            db.update_web_contact_status(contact_id, "replied")

        # 3. Invia email via SMTP
        if not clean_email:
            return False, auth_key, "Nessun indirizzo email associato."

        sent, msg = mailer.send_key_email(to_email=clean_email, name=clean_name, auth_key=auth_key)
        return sent, auth_key, msg

    # ── GESTIONE CALLBACK QUERY (PULSANTI INLINE) ──────────────────────────────

    def handle_callback_query(self, cb: dict):
        cb_id = cb.get("id")
        from_user = cb.get("from", {})
        user_id = from_user.get("id")

        if not self.is_authorized(user_id):
            self.answer_callback(cb_id, "Non autorizzato", show_alert=True)
            return

        data = str(cb.get("data", "")).strip()
        message = cb.get("message", {})
        msg_id = message.get("message_id")

        if data.startswith("grant:"):
            cid = data.split(":", 1)[1].strip()
            contact = db.get_web_contact(cid)
            if not contact:
                self.answer_callback(cb_id, f"Contatto {cid} non trovato", show_alert=True)
                return

            c_name = contact.get("name", "Utente")
            c_email = contact.get("email", "")

            sent, auth_key, status_msg = self.issue_and_send_key(c_name, c_email, contact_id=cid)

            if sent:
                self.answer_callback(cb_id, f"✅ Chiave inviata a {c_email}!")
                # Aggiorna il pulsante sul messaggio originale per mostrare che è completato
                if msg_id:
                    self.edit_reply_markup(msg_id, {
                        "inline_keyboard": [
                            [{"text": f"✅ Inviato a {c_email} ({auth_key})", "callback_data": "noop"}]
                        ]
                    })
                # Invia messaggio di riepilogo
                self.send_message(
                    f"🎉 <b>Chiave di accesso emessa ed inviata con successo!</b>\n\n"
                    f"👤 <b>Utente:</b> {html.escape(c_name)}\n"
                    f"📧 <b>Email:</b> <code>{html.escape(c_email)}</code>\n"
                    f"🔑 <b>Chiave Mesh:</b> <code>{auth_key}</code>\n"
                    f"✉️ <i>Email recapitata correttamente tramite SMTP.</i>"
                )
            else:
                self.answer_callback(cb_id, "⚠️ Chiave creata nel DB, ma invio email fallito", show_alert=True)
                # Disabilita il pulsante
                if msg_id:
                    self.edit_reply_markup(msg_id, {
                        "inline_keyboard": [
                            [{"text": f"⚠️ Creata nel DB: {auth_key}", "callback_data": "noop"}]
                        ]
                    })

                tmpl = (
                    f"Ciao {c_name},\n"
                    f"ecco la tua chiave di accesso per i modelli remoti HyperSpace Mesh:\n\n"
                    f"Chiave: {auth_key}\n\n"
                    f"Accedi a: https://oszerozero.onrender.com/\n"
                    f"Clicca su '🔑 Chiave Mesh' in alto a destra e incolla il codice."
                )
                self.send_message(
                    f"⚠️ <b>Chiave creata nel DB, ma l'email NON è stata inviata!</b>\n\n"
                    f"<b>Motivo:</b> <i>{html.escape(status_msg)}</i>\n\n"
                    f"👤 <b>Utente:</b> {html.escape(c_name)}\n"
                    f"📧 <b>Email:</b> <code>{html.escape(c_email)}</code>\n"
                    f"🔑 <b>Chiave Mesh:</b> <code>{auth_key}</code>\n\n"
                    f"📋 <b>Testo pronto da inoltrare manualmente:</b>\n"
                    f"<pre>{html.escape(tmpl)}</pre>"
                )

        elif data == "noop":
            self.answer_callback(cb_id, "Azione già completata.")

    # ── GESTIONE COMANDI CHAT ──────────────────────────────────────────────────

    def handle_message(self, msg: dict):
        from_user = msg.get("from", {})
        user_id = from_user.get("id")
        text = str(msg.get("text", "")).strip()

        if not self.is_authorized(user_id):
            return  # Ignora utenti non autorizzati

        if not text:
            return

        cmd = text.split()[0].lower()
        parts = text.split()

        if cmd in ("/start", "/help"):
            help_text = (
                "🤖 <b>HyperSpace Mesh — Bot Operatore</b>\n\n"
                "Comandi disponibili:\n\n"
                "🔑 <b>Emissione Chiavi & Email:</b>\n"
                "• <code>/grant &lt;email_o_id&gt;</code> — Genera e invia chiave per un contatto\n"
                "• <code>/keygen &lt;nome&gt; &lt;email&gt;</code> — Crea una chiave nuova e la spedisce\n"
                "• <code>/revoke &lt;chiave&gt;</code> — Revoca una chiave di accesso\n\n"
                "📊 <b>Monitoraggio:</b>\n"
                "• <code>/contacts</code> — Ultimi messaggi ricevuti dal form\n"
                "• <code>/keys</code> — Elenco chiavi attive e ultimo utilizzo\n"
                "• <code>/status</code> — Stato del bot, DB e servizio SMTP"
            )
            self.send_message(help_text)

        elif cmd == "/status":
            counts = db.count_web_contacts()
            keys = db.list_auth_keys(status="active")
            smtp_ok = mailer.is_smtp_configured()
            cfg = mailer.get_smtp_config()
            smtp_status = f"🟢 Attivo ({cfg['host']}:{cfg['port']})" if smtp_ok else "🔴 Non configurato in .env"

            status_text = (
                f"⚙️ <b>HyperSpace InfoBot — Stato Servizi</b>\n\n"
                f"🗄️ <b>Database:</b> <code>{db.DB_PATH}</code>\n"
                f"📧 <b>SMTP Mailer:</b> {smtp_status}\n"
                f"📬 <b>Messaggi Contatto:</b> {counts.get('total', 0)} totali ({counts.get('unread', 0)} non letti)\n"
                f"🔑 <b>Chiavi Mesh Attive:</b> {len(keys)}\n"
                f"🆔 <b>Chat Operatore:</b> <code>{self.chat_id}</code>"
            )
            self.send_message(status_text)

        elif cmd == "/contacts":
            contacts = db.list_web_contacts(limit=6)
            if not contacts:
                self.send_message("Nessun messaggio di contatto registrato.")
                return

            self.send_message(f"📬 <b>Ultimi {len(contacts)} messaggi di contatto:</b>")
            for c in contacts:
                status_icon = "🔴 NON LETTO" if c["status"] == "unread" else ("🟢 GESTITO" if c["status"] == "replied" else "⚪ LETTO")
                btn_markup = None
                if c["status"] != "replied":
                    btn_markup = {
                        "inline_keyboard": [
                            [{"text": f"🔑 Emetti e Invia a {c['name'][:18]}", "callback_data": f"grant:{c['contact_id']}"}]
                        ]
                    }
                item_text = (
                    f"👤 <b>{html.escape(c['name'])}</b> &lt;<code>{html.escape(c['email'])}</code>&gt;\n"
                    f"🏷️ <b>Oggetto:</b> {html.escape(c['subject'] or '—')}\n"
                    f"🆔 <code>{c['contact_id']}</code> &middot; {status_icon}\n"
                    f"💬 <i>{html.escape(c['message'][:120])}</i>"
                )
                self.send_message(item_text, reply_markup=btn_markup)

        elif cmd == "/keys":
            keys = db.list_auth_keys()
            if not keys:
                self.send_message("Nessuna chiave di accesso registrata.")
                return

            msg_lines = [f"🔑 <b>Chiavi Mesh Registrate ({len(keys)}):</b>\n"]
            for k in keys[:10]:
                badge = "🟢" if k["status"] == "active" else "🔴"
                msg_lines.append(
                    f"{badge} <code>{k['auth_key']}</code>\n"
                    f"   👤 {html.escape(k['label'] or '—')} | 📧 <code>{html.escape(k['email'] or '—')}</code>\n"
                    f"   🕒 Uso: {k['last_used'] or 'mai'}\n"
                )
            self.send_message("\n".join(msg_lines))

        elif cmd == "/grant":
            if len(parts) < 2:
                self.send_message("⚠️ Uso: <code>/grant &lt;email_o_id_contatto&gt;</code>\nEs: <code>/grant cnt-a0403c31ecda</code> oppure <code>/grant tecnicirollout@gmail.com</code>")
                return

            target = parts[1].strip()
            contact = None
            if target.startswith("cnt-"):
                contact = db.get_web_contact(target)
            else:
                contact = db.get_web_contact_by_email(target)

            if contact:
                sent, auth_key, msg_err = self.issue_and_send_key(contact["name"], contact["email"], contact_id=contact.get("contact_id"))
                if sent:
                    self.send_message(
                        f"✅ <b>Chiave generata e inviata con successo!</b>\n\n"
                        f"👤 <b>Utente:</b> {html.escape(contact['name'])}\n"
                        f"📧 <b>Email:</b> <code>{html.escape(contact['email'])}</code>\n"
                        f"🔑 <b>Chiave:</b> <code>{auth_key}</code>"
                    )
                else:
                    self.send_message(
                        f"⚠️ <b>Chiave emessa nel DB, ma errore email:</b> <i>{html.escape(msg_err)}</i>\n\n"
                        f"👤 <b>Utente:</b> {html.escape(contact['name'])}\n"
                        f"🔑 <b>Chiave:</b> <code>{auth_key}</code>"
                    )
            else:
                # Se è un indirizzo email puro senza contatto pregresso
                if "@" in target:
                    name = target.split("@")[0].capitalize()
                    sent, auth_key, msg_err = self.issue_and_send_key(name, target)
                    if sent:
                        self.send_message(
                            f"✅ <b>Nuova chiave creata e inviata a {html.escape(target)}!</b>\n\n"
                            f"🔑 <b>Chiave:</b> <code>{auth_key}</code>"
                        )
                    else:
                        self.send_message(
                            f"⚠️ <b>Chiave creata nel DB, ma errore email:</b> <i>{html.escape(msg_err)}</i>\n\n"
                            f"🔑 <b>Chiave:</b> <code>{auth_key}</code>"
                        )
                else:
                    self.send_message(f"❌ Nessun contatto trovato con ID o email <code>{html.escape(target)}</code>.")

        elif cmd == "/keygen":
            if len(parts) < 3:
                self.send_message("⚠️ Uso: <code>/keygen &lt;nome&gt; &lt;email&gt;</code>\nEs: <code>/keygen Mario mario@example.com</code>")
                return
            name = parts[1].strip()
            email = parts[2].strip()
            sent, auth_key, msg_err = self.issue_and_send_key(name, email)
            if sent:
                self.send_message(
                    f"✅ <b>Chiave emessa e inviata via email con successo!</b>\n\n"
                    f"👤 <b>Nome:</b> {html.escape(name)}\n"
                    f"📧 <b>Email:</b> <code>{html.escape(email)}</code>\n"
                    f"🔑 <b>Chiave:</b> <code>{auth_key}</code>"
                )
            else:
                self.send_message(
                    f"⚠️ <b>Chiave creata nel DB:</b> <code>{auth_key}</code>\n"
                    f"Invio email: <i>{html.escape(msg_err)}</i>"
                )

        elif cmd == "/revoke":
            if len(parts) < 2:
                self.send_message("⚠️ Uso: <code>/revoke &lt;chiave&gt;</code>")
                return
            key_val = parts[1].strip()
            if db.revoke_auth_key(key_val):
                self.send_message(f"✓ Chiave <code>{html.escape(key_val)}</code> revocata.")
            else:
                self.send_message(f"❌ Chiave <code>{html.escape(key_val)}</code> non trovata.")

    # ── POLLING LOOP ───────────────────────────────────────────────────────────

    def run(self):
        print(f"[InfoBot] Avvio polling Telegram per operatore {self.chat_id}...")
        offset = 0
        while self.running:
            try:
                res = self._call("getUpdates", {"offset": offset, "timeout": 20}, timeout=25.0)
                if not res:
                    time.sleep(1)
                    continue

                for update in res:
                    offset = max(offset, update["update_id"] + 1)

                    if "callback_query" in update:
                        self.handle_callback_query(update["callback_query"])
                    elif "message" in update:
                        self.handle_message(update["message"])

            except KeyboardInterrupt:
                print("\n[InfoBot] Interruzione ricevuta, chiusura in corso...")
                break
            except Exception as exc:
                print(f"[InfoBot] Loop exception: {exc}")
                time.sleep(3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token", type=str, default=os.getenv("CONTACT_TELEGRAM_BOT_TOKEN", ""),
                        help="Token del bot Telegram (default: da CONTACT_TELEGRAM_BOT_TOKEN in .env)")
    parser.add_argument("--chat-id", type=str, default=os.getenv("CONTACT_TELEGRAM_CHAT_ID", ""),
                        help="Chat ID autorizzato dell'operatore (default: da CONTACT_TELEGRAM_CHAT_ID in .env)")
    args = parser.parse_args()

    if not args.token or not args.chat_id:
        sys.exit("Errore: CONTACT_TELEGRAM_BOT_TOKEN e CONTACT_TELEGRAM_CHAT_ID sono obbligatori in .env")

    if not acquire_lock():
        sys.exit("Un'istanza di infobot_service è già in esecuzione (lock data/infobot.lock).")

    # Inizializza DB
    db.init_db()

    bot = InfoBotService(token=args.token, chat_id=args.chat_id)

    def handle_sig(sig, frame):
        bot.running = False
        release_lock()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    bot.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
