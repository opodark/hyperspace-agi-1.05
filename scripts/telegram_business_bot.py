#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Bot Telegram Aziendale per Vittoria (HyperSpace AGI).

Consente al titolare di PMI, artigiano o professionista di interagire con
Vittoria direttamente da Telegram (mobile o desktop).

Caratteristiche:
- Interfaccia conversazionale naturale con la persona aziendale Vittoria.
- Accesso ai tool del Control Plane (preventivi, fatture PDF, calcolo IVA/ritenute).
- Consegna automatica dei PDF generati direttamente come allegati Telegram (sendDocument).
- Sicurezza fail-closed: risponde solo agli ID chat/utenti autorizzati in configurazione.

Configurazione (variabili d'ambiente o data/telegram-bot.env):
  TELEGRAM_BUSINESS_TOKEN       Token del bot Telegram dedicato (da @BotFather)
  TELEGRAM_BUSINESS_USERS       Lista ID utenti/username Telegram ammessi (separati da virgola)
  CP_URL                        URL del Control Plane (default: http://127.0.0.1:8085)
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.persona import PersonaStore
from shared.audio_transcriber import transcribe_audio, is_stt_available

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("telegram_vittoria")

PERSONA_PATH = REPO_ROOT / "data" / "persona-vittoria.json"
DATA_DOCS_DIR = REPO_ROOT / "data" / "documents"


def load_allowed_users() -> set[str]:
    raw = os.getenv("TELEGRAM_BUSINESS_USERS", "")
    env_file = REPO_ROOT / "data" / "telegram-bot.env"
    if not raw and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("TELEGRAM_BUSINESS_USERS="):
                raw = line.split("=", 1)[1].strip()
                break
            elif not raw and line.startswith("TELEGRAM_BUSINESS_ALLOWLIST="):
                raw = line.split("=", 1)[1].strip()
    return {u.strip().lower().lstrip("@") for u in raw.split(",") if u.strip()}


def load_token() -> str:
    token = os.getenv("TELEGRAM_BUSINESS_TOKEN", "").strip()
    if not token:
        env_file = REPO_ROOT / "data" / "telegram-bot.env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("TELEGRAM_BUSINESS_TOKEN="):
                    token = line.split("=", 1)[1].strip()
                    break
    return token


class TelegramBusinessBot:
    def __init__(self, token: str, cp_url: str = "http://127.0.0.1:8085", allowed_users: Optional[set[str]] = None):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.cp_url = cp_url.rstrip("/")
        self.allowed_users = allowed_users or set()
        self.conversations: Dict[int, List[Dict[str, str]]] = {}
        self.persona_prompt = self._load_persona_prompt()

    def _load_persona_prompt(self) -> str:
        if PERSONA_PATH.exists():
            store = PersonaStore.load(str(PERSONA_PATH))
            return store.system_block(surface="business")
        return (
            "Sei Vittoria, consulente operativa e assistente per PMI, studi e artigiani. "
            "Gestisci preventivi, fatture e scadenze con rigore, precisione e tono professionale."
        )

    def is_user_allowed(self, user_info: dict) -> bool:
        if "*" in self.allowed_users:
            return True
        if not self.allowed_users:
            # Se la lista non è definita, per sicurezza fail-closed consentiamo solo se impostata
            return False
        username = str(user_info.get("username") or "").lower().lstrip("@")
        user_id = str(user_info.get("id") or "")
        return username in self.allowed_users or user_id in self.allowed_users

    def tg_request(self, method: str, data: Optional[dict] = None, files: Optional[dict] = None, timeout: int = 35) -> dict:
        url = f"{self.api_url}/{method}"
        try:
            if files:
                r = requests.post(url, data=data, files=files, timeout=timeout)
            else:
                r = requests.post(url, json=data, timeout=timeout)
            return r.json()
        except Exception as e:
            logger.error("Errore chiamata Telegram %s: %s", method, e)
            return {"ok": False, "error": str(e)}

    def send_message(self, chat_id: int, text: str) -> dict:
        return self.tg_request("sendMessage", {"chat_id": chat_id, "text": text})

    def send_document(self, chat_id: int, file_path: str, caption: str = "") -> dict:
        p = Path(file_path)
        if not p.is_file():
            logger.warning("File da inviare non trovato: %s", file_path)
            return {"ok": False, "error": "file not found"}
        try:
            with open(p, "rb") as f:
                return self.tg_request(
                    "sendDocument",
                    data={"chat_id": chat_id, "caption": caption},
                    files={"document": (p.name, f, "application/pdf")},
                    timeout=60,
                )
        except Exception as e:
            logger.error("Errore invio documento %s: %s", file_path, e)
            return {"ok": False, "error": str(e)}

    def send_typing(self, chat_id: int):
        self.tg_request("sendChatAction", {"chat_id": chat_id, "action": "typing"})

    def download_telegram_file(self, file_id: str, dest_path: Path) -> bool:
        """Ottiene il percorso da getFile e scarica il file audio."""
        res = self.tg_request("getFile", {"file_id": file_id})
        if not res.get("ok"):
            logger.error("Errore getFile Telegram: %s", res)
            return False
        file_path = res.get("result", {}).get("file_path")
        if not file_path:
            return False
        file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        try:
            r = requests.get(file_url, timeout=30)
            r.raise_for_status()
            dest_path.write_bytes(r.content)
            return True
        except Exception as e:
            logger.error("Errore download file Telegram %s: %s", file_path, e)
            return False

    def handle_voice_message(self, chat_id: int, voice_info: dict) -> Optional[str]:
        """Scarica e trascrive un messaggio vocale inviato su Telegram."""
        file_id = voice_info.get("file_id")
        if not file_id:
            return None

        if not is_stt_available():
            self.send_message(chat_id, "Il modulo di trascrizione audio (Whisper/ffmpeg) non è attualmente attivo sul server.")
            return None

        self.send_typing(chat_id)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_f:
            tmp_path = Path(tmp_f.name)

        try:
            ok = self.download_telegram_file(file_id, tmp_path)
            if not ok:
                self.send_message(chat_id, "Non sono riuscita a scaricare l'audio inviato da Telegram. Riprova tra poco.")
                return None

            self.send_message(chat_id, "🎙️ *Sto ascoltando il tuo messaggio vocale...*")
            transcribed = transcribe_audio(tmp_path, language="it")
            if transcribed:
                self.send_message(chat_id, f"🎙️ *Ho trascritto:* \"{transcribed}\"")
                return transcribed
            else:
                self.send_message(chat_id, "Non sono riuscita a comprendere chiaramente l'audio. Puoi ripetere o scriverlo?")
                return None
        except Exception as exc:
            logger.error("Errore durante ascolto vocale: %s", exc)
            self.send_message(chat_id, f"Errore nell'ascolto del messaggio vocale: {exc}")
            return None
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

    def handle_message(self, message: dict) -> None:
        chat_id = (message.get("chat") or {}).get("id")
        user_info = message.get("from") or {}
        text = str(message.get("text") or "").strip()

        if not chat_id:
            return

        if not self.is_user_allowed(user_info):
            logger.warning("Messaggio rifiutato da utente non autorizzato: %s (id: %s)", user_info.get("username"), user_info.get("id"))
            self.send_message(chat_id, "Accesso non autorizzato. Questo bot è configurato ad uso esclusivo aziendale.")
            return

        voice_obj = message.get("voice") or message.get("audio")
        if not text and voice_obj:
            text = self.handle_voice_message(chat_id, voice_obj) or ""
            if not text:
                return

        if not text:
            return

        if text.startswith("/start"):
            self.send_message(
                chat_id,
                "Buongiorno. Sono Vittoria, la tua assistente aziendale per PMI e professionisti.\n\n"
                "Come posso aiutarti oggi? Posso:\n"
                "- 🎙️ Ascoltare i tuoi messaggi vocali e trascriverli istantaneamente\n"
                "- 📄 Redigere preventivi ufficiali e fatture in PDF\n"
                "- 💶 Calcolare imponibile, IVA e ritenute d'acconto\n"
                "- 🔍 Cercare informazioni e listini aggiornati sul web\n"
                "- 🌐 Leggere ed esaminare interi siti web di clienti o concorrenti\n"
                "- ✉️ Preparare bozze di corrispondenza per clienti e fornitori\n\n"
                "Puoi inviarmi messaggi di testo o direttamente un messaggio vocale registrato dal cantiere!"
            )
            return

        if text.startswith("/chiamata") or text.lower().strip() in ("chiamami", "avvia chiamata", "chiamata vocale"):
            self.send_message(
                chat_id,
                "📞 *Chiamata Vocale in Diretta con Vittoria*\n\n"
                "Per conversare in vivavoce in tempo reale con microfono aperto, puoi inviarmi una sequenza di messaggi vocali continui (che ascolto e a cui rispondo immediatamente) oppure usare il link di chiamata vocale WebRTC diretta:\n"
                "👉 http://127.0.0.1:8085/call (o apri Open WebUI su localhost:3000 con modalità voce attiva).\n\n"
                "In alternativa puoi semplicemente premere l'icona del microfono qui in basso e parlarmi liberamente!"
            )
            return

        self.send_typing(chat_id)

        # Gestione cronologia conversazione per chat
        history = self.conversations.setdefault(chat_id, [])
        history.append({"role": "user", "content": text})
        if len(history) > 10:
            history = history[-10:]
            self.conversations[chat_id] = history

        messages = [{"role": "system", "content": self.persona_prompt}] + history

        try:
            model_name = os.getenv("TELEGRAM_BUSINESS_MODEL", "granite3.3:8b").strip()
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.2
            }
            res = requests.post(f"{self.cp_url}/v1/chat/completions", json=payload, timeout=90)
            if res.status_code == 200:
                data = res.json()
                reply_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if not reply_text:
                    reply_text = "Ho elaborato la richiesta ma non ho generato testo. Puoi riformulare?"
            else:
                logger.error("Errore Control Plane: HTTP %s %s", res.status_code, res.text[:200])
                reply_text = f"Si è verificato un errore nel collegamento al Control Plane aziendale (HTTP {res.status_code})."
        except Exception as exc:
            logger.error("Eccezione durante inferenza: %s", exc)
            reply_text = f"Impossibile completare la richiesta: {exc}"

        history.append({"role": "assistant", "content": reply_text})
        self.send_message(chat_id, reply_text)

        # Rileva se nella risposta o nei documenti recenti è stato generato un PDF
        self._check_and_send_generated_docs(chat_id, reply_text)

    def _check_and_send_generated_docs(self, chat_id: int, reply_text: str):
        """Se nella risposta c'è un riferimento a un file PDF generato, invialo come allegato Telegram."""
        # Cerca pattern tipo /repo/data/documents/*.pdf oppure data/documents/*.pdf
        matches = re.findall(r"(\S+\.pdf)", reply_text)
        sent = set()
        for path_str in matches:
            clean_path = path_str.strip("`'\"(),;:")
            # Se è un path relativo o nel container, converti in path host locale
            if "/data/documents/" in clean_path:
                doc_name = clean_path.split("/data/documents/")[-1]
                local_file = DATA_DOCS_DIR / doc_name
            else:
                local_file = Path(clean_path)

            if local_file.is_file() and local_file not in sent:
                logger.info("Invio documento generato al cliente: %s", local_file)
                self.send_document(chat_id, str(local_file), caption=f"Documento: {local_file.name}")
                sent.add(local_file)

    def poll_loop(self):
        offset = 0
        logger.info("Avvio bot Vittoria Telegram (allowed_users: %s)...", self.allowed_users)
        while True:
            try:
                res = self.tg_request("getUpdates", {"offset": offset, "timeout": 20}, timeout=25)
                if not res.get("ok"):
                    time.sleep(3)
                    continue
                updates = res.get("result", [])
                for upd in updates:
                    offset = max(offset, upd["update_id"] + 1)
                    if "message" in upd:
                        self.handle_message(upd["message"])
            except KeyboardInterrupt:
                logger.info("Arresto richiesto.")
                break
            except Exception as e:
                logger.error("Errore nel ciclo di poll: %s", e)
                time.sleep(3)


def main():
    token = load_token()
    if not token:
        logger.warning(
            "TELEGRAM_BUSINESS_TOKEN non configurato. "
            "Configuralo in data/telegram-bot.env o come variabile d'ambiente."
        )
        sys.exit(1)

    allowed = load_allowed_users()
    cp_url = os.getenv("CP_URL", "http://127.0.0.1:8085")
    bot = TelegramBusinessBot(token=token, cp_url=cp_url, allowed_users=allowed)
    bot.poll_loop()


if __name__ == "__main__":
    main()
