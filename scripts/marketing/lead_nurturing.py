# SPDX-License-Identifier: Apache-2.0
"""Lead Nurturing & Onboarding Manager per HyperSpace.

Legge i contatti acquisiti dal form di zerozerocomputer.it in SQLite,
analizza l'intento dell'utente, genera proposte di risposta personalizzate e
fornisce un funnel di accoglienza per guidare il lead all'adozione della chat e della mesh.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from shared import db
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from shared import db

DEFAULT_LEADS_STATE_FILE = Path(__file__).resolve().parents[2] / "data" / "marketing" / "leads_state.json"


@dataclass
class LeadAction:
    action_id: str
    contact_id: str
    name: str
    email: str
    intent: str
    auth_key: str
    suggested_reply: str
    stage: str = "new"  # 'new' | 'nurturing' | 'converted' | 'archived'
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    operator_approved: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> LeadAction:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class LeadNurturingManager:
    """Gestisce il funnel di accoglienza e follow-up dei contatti web."""

    def __init__(self, state_path: Optional[Path] = None):
        self.state_path = state_path or DEFAULT_LEADS_STATE_FILE
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_path.is_file():
            self._write_state({})

    def _read_state(self) -> dict:
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write_state(self, state: dict) -> None:
        temp_dir = self.state_path.parent
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=temp_dir, delete=False) as tf:
            json.dump(state, tf, ensure_ascii=False, indent=2)
            temp_name = tf.name
        os.replace(temp_name, self.state_path)

    def classify_intent(self, subject: str, message: str) -> str:
        """Classifica l'intento del contatto in base a parole chiave semantiche."""
        text = f"{subject} {message}".lower()
        if any(w in text for w in ("node", "mesh", "gpu", "vram", "ollama", "hardware", "install", "api", "codice", "git", "setup", "linux", "mac")):
            return "dev_mesh"
        if any(w in text for w in ("chiave", "token", "auth", "login", "password", "accesso", "chat", "crediti")):
            return "access_key"
        if any(w in text for w in ("prezzo", "costo", "collaborazione", "partnership", "azienda", "consulenza", "business", "progetto")):
            return "partnership_project"
        return "general_curiosity"

    def compose_onboarding_reply(self, name: str, email: str, subject: str, message: str, auth_key: str, intent: str) -> str:
        """Costruisce una risposta di accoglienza calda, professionale e personalizzata."""
        first_name = name.split()[0] if name else "utente"
        # Il DB conserva solo l'hash delle chiavi: per un contatto che ne ha gia'
        # una, la risposta rimanda a quella ricevuta via email all'emissione.
        if auth_key:
            chat_url = f"https://www.zerozerocomputer.it/chat.html?key={auth_key}"
            key_line = f"🔑 **Chiave Membro**: `{auth_key}`\n"
        else:
            chat_url = "https://www.zerozerocomputer.it/chat.html"
            key_line = "🔑 **Chiave Membro**: quella che ti abbiamo inviato via email alla registrazione\n"

        if intent == "dev_mesh":
            body = (
                f"Grazie per l'interesse nell'infrastruttura di HyperSpace. Abbiamo sviluppato una mesh "
                f"completamente distribuita ed end-to-end encrypted (secp256k1 + AES-GCM) capace di federare GPU "
                f"consumer e chip Apple Silicon per eseguire modelli densi e MoE in locale a costo zero.\n\n"
                f"Puoi testare subito la risposta dei nodi accedendo alla nostra Chat AI con la tua chiave dedicata:\n"
                f"{key_line}"
                f"🌐 **Link Diretto**: {chat_url}\n\n"
                f"Un prompt consigliato da testare: 'Spiegami l'architettura di bilanciamento della memoria in HyperSpace'."
            )
        elif intent == "access_key":
            body = (
                f"Ecco le tue credenziali per accedere immediatamente alla rete neurale di HyperSpace.\n\n"
                f"{key_line}"
                f"🌐 **Accesso Immediato**: {chat_url}\n\n"
                f"Cliccando sul link verrai autenticato automaticamente e potrai interagire con i modelli attivi sulla mesh in tempo reale."
            )
        elif intent == "partnership_project":
            body = (
                f"Abbiamo ricevuto la tua richiesta per '{subject or 'collaborazione HyperSpace'}'. Il nostro team "
                f"di architetti AI è a disposizione per valutare integrazioni personalizzate, nodi dedicati e pipeline ad-hoc.\n\n"
                f"Nel frattempo, hai già accesso completo alla nostra sandbox pubblica:\n"
                f"{key_line}"
                f"🌐 **Console di Prova**: {chat_url}\n\n"
                f"Ti ricontatteremo a breve per approfondire i dettagli operativi."
            )
        else:
            body = (
                f"Benvenuto nella dimensione di HyperSpace. Siamo felici di averti a bordo.\n\n"
                f"Abbiamo attivato il tuo profilo membro e generato la tua chiave di accesso personale:\n"
                f"{key_line}"
                f"🌐 **Entra nella Chat**: {chat_url}\n\n"
                f"Puoi conversare liberamente con la nostra intelligenza artificiale Aurora e testare la fluidità dell'inferenza distribuita."
            )

        return (
            f"Ciao {first_name},\n\n"
            f"{body}\n\n"
            f"A presto,\n"
            f"Il Team di HyperSpace\n"
            f"https://www.zerozerocomputer.it"
        )

    def process_pending_contacts(self, limit: int = 20) -> list[LeadAction]:
        """Scansiona i contatti nel DB e genera le azioni di onboarding per chi non ne ha ancora."""
        contacts = db.list_web_contacts(limit=limit)
        state = self._read_state()
        new_actions: list[LeadAction] = []

        for c in contacts:
            cid = c["contact_id"]
            if cid in state:
                continue

            email = c["email"]
            name = c["name"]
            subject = c.get("subject", "")
            message = c.get("message", "")

            # Recupera o usa la auth_key assegnata
            key_record = db.get_auth_key_by_email(email)
            auth_key = "" if key_record else f"hs-mesh-temp-{cid[:8]}"

            intent = self.classify_intent(subject, message)
            reply = self.compose_onboarding_reply(name, email, subject, message, auth_key, intent)

            action = LeadAction(
                action_id=f"act-{uuid.uuid4().hex[:10]}",
                contact_id=cid,
                name=name,
                email=email,
                intent=intent,
                auth_key=auth_key,
                suggested_reply=reply,
                stage="nurturing"
            )
            state[cid] = action.to_dict()
            new_actions.append(action)

        if new_actions:
            self._write_state(state)
        return new_actions

    def get_action(self, contact_id: str) -> Optional[LeadAction]:
        state = self._read_state()
        item = state.get(contact_id)
        return LeadAction.from_dict(item) if item else None

    def approve_action(self, contact_id: str) -> bool:
        state = self._read_state()
        if contact_id not in state:
            return False
        state[contact_id]["operator_approved"] = True
        state[contact_id]["stage"] = "converted"
        self._write_state(state)
        return True

    def list_actions(self, stage: Optional[str] = None) -> list[LeadAction]:
        state = self._read_state()
        actions = [LeadAction.from_dict(v) for v in state.values()]
        if stage:
            actions = [a for a in actions if a.stage == stage]
        return actions
