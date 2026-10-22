# SPDX-License-Identifier: Apache-2.0
"""
title: HyperSpace — Scripting, Voce Nicole & Forge On-the-Fly
description: Esecuzione di codice Python on-the-fly, sintesi vocale con Nicole (Kokoro TTS), PDF e apertura ticket Forge per autosviluppo.
required_open_webui_version: 0.4.0
version: 1.0.0
"""

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import time
import traceback
import urllib.request
from pydantic import BaseModel, Field

ROOT = Path("/app/hyperspace_share")


class Tools:
    class Valves(BaseModel):
        kokoro_url: str = Field(
            default="http://host.docker.internal:8880",
            description="URL del servizio Kokoro TTS (raggiungibile da Docker via host.docker.internal).",
        )
        control_plane_url: str = Field(
            default="http://host.docker.internal:8085",
            description="URL del Control Plane per esportazione PDF e servizi mesh.",
        )
        voce_predefinita: str = Field(
            default="af_nicole",
            description="Voce predefinita Kokoro (af_nicole, poetica, documentarista, giornalista, af_heart).",
        )

    def __init__(self):
        self.valves = self.Valves()

    def esegui_script(self, codice: str) -> str:
        """Esegue uno script o frammento di codice Python on-the-fly e restituisce l'output stdout/stderr.
        :param codice: codice Python da eseguire on-the-fly
        """
        if not codice or not codice.strip():
            return "Nessun codice fornito."

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            try:
                scope = {"__builtins__": __builtins__, "Path": Path}
                exec(codice, scope)
                out = buffer.getvalue()
                if not out:
                    user_vars = {k: v for k, v in scope.items() if not k.startswith("_")}
                    if user_vars:
                        return f"Script eseguito con successo. Variabili generate: {user_vars}"
                    return "Script eseguito con successo (nessun output a schermo)."
                return out
            except Exception as e:
                return f"Errore esecuzione script: {e}\n{traceback.format_exc()}"

    def parla_ad_alta_voce(self, testo: str, voce: str = "", riproduci_casse: bool = True) -> str:
        """Sintetizza il testo con Kokoro (voce predefinita: Nicole) e lo riproduce in tempo reale dagli altoparlanti fisici.
        :param testo: testo, poesia o messaggio da recitare ad alta voce
        :param voce: voce o stile (default: af_nicole; alternative: poetica, documentarista, giornalista, af_heart)
        :param riproduci_casse: se True, fa suonare l'audio direttamente dagli altoparlanti del computer
        """
        if not testo or not testo.strip():
            return "Testo vuoto."

        selected_voice = voce.strip() if voce and voce.strip() else self.valves.voce_predefinita
        url = f"{self.valves.kokoro_url.rstrip('/')}/v1/audio/speech"

        try:
            payload = json.dumps({
                "input": testo,
                "voice": selected_voice,
                "play": riproduci_casse
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=45) as resp:
                audio_bytes = resp.read()

            ROOT.mkdir(parents=True, exist_ok=True)
            out_file = ROOT / "ultimo_vocale_nicole.wav"
            out_file.write_bytes(audio_bytes)

            status_audio = "e riproduzione altoparlanti avviata!" if riproduci_casse else ""
            return f"Audio sintetizzato con voce '{selected_voice}' ({len(audio_bytes)} byte salvati in hyperspace_share) {status_audio}"
        except Exception as e:
            return f"Errore sintesi vocale su {url}: {e}"

    def genera_pdf(self, titolo: str, contenuto_markdown: str, nome_file: str = "documento.pdf") -> str:
        """Genera un documento PDF A4 impaginato e lo salva nella cartella condivisa per il download immediato.
        :param titolo: titolo principale del documento
        :param contenuto_markdown: testo completo formattato in Markdown
        :param nome_file: nome del file PDF da salvare (es. relazione.pdf)
        """
        if not contenuto_markdown:
            return "Contenuto vuoto."

        url = f"{self.valves.control_plane_url.rstrip('/')}/web/export/pdf"
        try:
            payload = json.dumps({
                "title": titolo,
                "content": contenuto_markdown
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                pdf_bytes = resp.read()

            ROOT.mkdir(parents=True, exist_ok=True)
            if not nome_file.endswith(".pdf"):
                nome_file += ".pdf"
            out_path = ROOT / nome_file
            out_path.write_bytes(pdf_bytes)

            return f"Documento PDF generato con successo: {nome_file} ({len(pdf_bytes)} byte in hyperspace_share)."
        except Exception as e:
            return f"Errore generazione PDF su {url}: {e}"

    def apri_ticket_forge(self, titolo: str, descrizione_gap: str, codice_o_bozza: str = "") -> str:
        """Apre un ticket di capability gap inoltrandolo all'Architect / Forge di HyperSpace per autosviluppo e collaudo.
        :param titolo: titolo del ticket / capability richiesta (es. 'Conversione file SVG')
        :param descrizione_gap: spiegazione dettagliata del gap o funzionalità mancante
        :param codice_o_bozza: eventuale bozza di codice o specifiche di test
        """
        ticket_id = f"ticket-{int(time.time())}"
        data = {
            "id": ticket_id,
            "title": titolo,
            "gap_description": descrizione_gap,
            "draft_code": codice_o_bozza,
            "status": "pending_forge_review",
            "created_at": time.time(),
            "target": "architect_lead_model"
        }

        try:
            ticket_dir = ROOT / "forge_tickets"
            ticket_dir.mkdir(parents=True, exist_ok=True)
            ticket_file = ticket_dir / f"{ticket_id}.json"
            ticket_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return f"Ticket Forge creato con successo: {ticket_id} (salvato in hyperspace_share/forge_tickets/{ticket_id}.json). L'Architect riceverà la segnalazione per lo sviluppo e il collaudo in Sandbox."
        except Exception as e:
            return f"Errore creazione ticket Forge: {e}"
