# SPDX-License-Identifier: Apache-2.0
"""Telegram Gate per HyperSpace Marketing — Interfaccia Human-in-the-Loop.

Invia bozze di contenuti e alert lead all'operatore su Telegram con pulsanti interattivi
inline per l'approvazione in 1 tap prima della pubblicazione o invio.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import requests

from .content_factory import ContentDraft, ContentFactory
from .lead_nurturing import LeadAction, LeadNurturingManager


class TelegramGate:
    """Interfaccia Telegram per la revisione e approvazione dei contenuti e lead."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        factory: Optional[ContentFactory] = None,
        lead_mgr: Optional[LeadNurturingManager] = None
    ):
        self.bot_token = (
            bot_token
            or os.getenv("TELEGRAM_MARKETING_BOT_TOKEN")
            or os.getenv("CONTACT_TELEGRAM_BOT_TOKEN")
            or os.getenv("TELEGRAM_BOT_TOKEN")
            or ""
        ).strip()
        self.chat_id = (
            chat_id
            or os.getenv("TELEGRAM_MARKETING_CHAT_ID")
            or os.getenv("CONTACT_TELEGRAM_CHAT_ID")
            or ""
        ).strip()
        self.factory = factory or ContentFactory()
        self.lead_mgr = lead_mgr or LeadNurturingManager()

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def _api_call(self, method: str, payload: dict) -> dict:
        if not self.is_configured:
            # Modalità Dry-Run / Simulazione sicura
            return {"ok": True, "dry_run": True, "method": method, "payload": payload}

        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        try:
            resp = requests.post(url, json=payload, timeout=15)
            return resp.json()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def send_content_review(self, draft: ContentDraft) -> dict:
        """Invia una bozza di contenuto per approvazione."""
        self.factory.update_status(draft.draft_id, "queued_approval")

        tags_str = " ".join(draft.tags)
        channels_str = ", ".join(draft.channel_targets).upper()
        text = (
            f"📢 **PROPOSTA MARKETING HYPERSPACE**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 **Traccia**: {draft.track.upper()} ({draft.category})\n"
            f"🎯 **Titolo**: {draft.title}\n"
            f"📡 **Canali**: {channels_str}\n\n"
            f"📝 **Testo Proposto**:\n{draft.text}\n\n"
            f"🏷️ **Tag**: {tags_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Cosa desideri fare con questa bozza?"
        )

        inline_keyboard = [
            [
                {"text": "✅ Approva & Pubblica", "callback_data": f"approve_draft:{draft.draft_id}"},
                {"text": "🔄 Rigenera", "callback_data": f"regen_draft:{draft.draft_id}"},
            ],
            [
                {"text": "❌ Scarta", "callback_data": f"reject_draft:{draft.draft_id}"}
            ]
        ]

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": inline_keyboard}
        }
        return self._api_call("sendMessage", payload)

    def send_lead_alert(self, lead: LeadAction) -> dict:
        """Invia la notifica di un nuovo lead con proposta di risposta al volo."""
        preview_reply = lead.suggested_reply[:400] + ("..." if len(lead.suggested_reply) > 400 else "")
        text = (
            f"👤 **NUOVO CONTATTO DA ZEROZEROCOMPUTER.IT**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Nome: **{lead.name}**\n"
            f"Email: `{lead.email}`\n"
            f"Intento Rilevato: **{lead.intent.upper()}**\n"
            f"Chiave Emessa: `{lead.auth_key}`\n\n"
            f"💡 **Bozza Risposta Onboarding Suggerita**:\n"
            f"_{preview_reply}_\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        inline_keyboard = [
            [
                {"text": "📤 Approva Risposta", "callback_data": f"approve_lead:{lead.contact_id}"},
                {"text": "👁️ Dettaglio", "callback_data": f"detail_lead:{lead.contact_id}"}
            ]
        ]

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": inline_keyboard}
        }
        return self._api_call("sendMessage", payload)

    def handle_callback(self, callback_data: str) -> dict:
        """Elabora l'azione dell'operatore dal bottone inline."""
        if ":" not in callback_data:
            return {"ok": False, "error": "Formato callback non valido"}

        action, target_id = callback_data.split(":", 1)

        if action == "approve_draft":
            success = self.factory.update_status(target_id, "approved")
            return {"ok": success, "action": action, "draft_id": target_id, "status": "approved"}
        elif action == "reject_draft":
            success = self.factory.update_status(target_id, "rejected")
            return {"ok": success, "action": action, "draft_id": target_id, "status": "rejected"}
        elif action == "regen_draft":
            draft = self.factory.get_draft(target_id)
            if not draft:
                return {"ok": False, "error": "Bozza non trovata"}
            new_draft = (
                self.factory.generate_creative_draft()
                if draft.track == "creative"
                else self.factory.generate_tech_draft()
            )
            return {"ok": True, "action": action, "new_draft_id": new_draft.draft_id}
        elif action == "approve_lead":
            success = self.lead_mgr.approve_action(target_id)
            return {"ok": success, "action": action, "contact_id": target_id, "stage": "converted"}

        return {"ok": False, "error": f"Azione '{action}' sconosciuta"}
