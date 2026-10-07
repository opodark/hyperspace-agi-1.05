# SPDX-License-Identifier: Apache-2.0
"""
title: HyperSpace Anna — batch immagini
description: Accoda fino a 50 immagini di Anna con la stessa vetrina usata dai canali HyperSpace.
required_open_webui_version: 0.4.0
version: 0.2.0
"""

# Importa questo file in Open WebUI: Admin Panel -> Workspace -> Tools -> "+".
# Poi abilitalo per il modello/chat. Configura nelle Valves:
#
# - channel_token: il token del client `webui` (o altro client dedicato) in
#   CHANNEL_CLIENTS. Non usare il token del bridge ComfyUI.
# - author: lo username configurato in CHANNEL_OPERATOR. Cosi' il batch passa
#   dalla medesima autorizzazione di Telegram/Instagram e dalla vetrina di Anna.
#   In SVILUPPO, finche' la WebUI non e' aperta agli utenti, serve solo un handle
#   qualsiasi purche' il control-plane abbia WEBUI_DEV_CREATOR=true: la superficie
#   `openwebui` vale come il creatore (stessa porta, stesso livello esplicito).
#
# Per mettere 50 scene nella coda in un solo invio, imposta IMAGE_QUEUE_MAX=50
# nel control-plane e riavvialo. Il renderer resta uno alla volta: il batch non
# aumenta il consumo di GPU, conserva solo i job in attesa.

from typing import List

import requests
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        control_plane_url: str = Field(
            default="http://control-plane:8085",
            description="URL del control-plane raggiungibile dal container Open WebUI.",
        )
        channel_token: str = Field(
            default="",
            description="Token del client dedicato Open WebUI in CHANNEL_CLIENTS.",
        )
        author: str = Field(
            default="",
            description="Handle del creatore, presente in CHANNEL_OPERATOR (senza @). "
                        "Con WEBUI_DEV_CREATOR=true (sviluppo) basta un handle qualsiasi.",
        )
        timeout_s: int = Field(default=30, description="Timeout HTTP in secondi.")

    def __init__(self):
        self.valves = self.Valves()

    def _headers(self) -> dict:
        token = (self.valves.channel_token or "").strip()
        return {"X-Hyperspace-Channel-Token": token} if token else {}

    def genera_anna_batch(self, scene: List[str]) -> str:
        """
        Accoda da 1 a 50 scene di Anna usando il suo volto e la sua ricetta ComfyUI.

        Ogni elemento di `scene` e' una descrizione autonoma: includi posa,
        inquadratura, abito, ambiente e luce. Il tool restituisce gli id dei job;
        usali con `stato_immagini` per seguire il rendering. Per 50 invii insieme,
        IMAGE_QUEUE_MAX del control-plane deve essere almeno 50.
        :param scene: lista di 1-50 descrizioni, una per immagine
        """
        if not isinstance(scene, list) or not scene:
            return "Indica una lista non vuota di scene."
        if len(scene) > 50:
            return "Il batch accetta al massimo 50 scene."
        author = (self.valves.author or "").strip()
        if not author:
            return ("Configura la Valve 'author' con l'handle presente in "
                    "CHANNEL_OPERATOR prima di accodare immagini di Anna.")
        try:
            response = requests.post(
                f"{self.valves.control_plane_url.rstrip('/')}/channel/anna-batch",
                json={"scene": scene, "author": author}, headers=self._headers(),
                timeout=max(5, self.valves.timeout_s),
            )
            data = response.json()
        except Exception as error:
            return f"Errore nel batch Anna: {error}"
        if response.status_code in (401, 503):
            return ("Control-plane non autorizzato (HTTP %s). Configura 'channel_token' "
                    "con un token valido di CHANNEL_CLIENTS." % response.status_code)
        if response.status_code == 400 and not data.get("rejected"):
            return "Batch rifiutato: " + str(data.get("error", "richiesta non valida"))
        accepted = data.get("accepted") or []
        rejected = data.get("rejected") or []
        ids = ", ".join(str(job.get("job_id")) for job in accepted)
        result = f"Accodate {len(accepted)} immagini di Anna. Job: {ids or 'nessuno'}."
        if accepted:
            result += " Pose: " + ", ".join(
                f"{job.get('index')}={job.get('pose_mode', 'text')}"
                + (f" ({job.get('pose_image') or job.get('pose_preset')})"
                   if job.get('pose_image') or job.get('pose_preset') else "")
                for job in accepted) + "."
        if rejected:
            result += (f" Non accodate: {len(rejected)}. "
                       + "; ".join(f"{job.get('index')}: {job.get('error')}"
                                   for job in rejected))
        return result

    def genera_anna_batch_con_pose(self, scene: List[dict]) -> str:
        """
        Accoda scene con una posa fotografica diversa per ogni immagine.

        Carica prima ogni foto in ComfyUI/input. Ogni elemento contiene `scene` e
        opzionalmente `pose_image` (nome restituito da ComfyUI), `pose_strength`
        fra 0 e 2, oppure `pose_preset` al posto della foto.
        :param scene: lista di oggetti, es. {"scene":"Anna seduta", "pose_image":"posa-01.jpg", "pose_strength":0.9}
        """
        return self.genera_anna_batch(scene)

    def stato_immagini(self, job_ids: List[str]) -> str:
        """
        Legge lo stato dei job Anna restituiti dal batch (massimo 50).
        :param job_ids: id dei job da verificare
        """
        if not isinstance(job_ids, list) or not job_ids:
            return "Indica almeno un job id."
        rows = []
        for job_id in job_ids[:50]:
            try:
                response = requests.get(
                    f"{self.valves.control_plane_url.rstrip('/')}/image/job/{job_id}",
                    headers=self._headers(), timeout=max(5, self.valves.timeout_s),
                )
                data = response.json()
                if response.status_code == 200:
                    job = data.get("job") or {}
                    rows.append(f"{job_id}: {job.get('stato', 'sconosciuto')}"
                                + (f" — {job.get('file')}" if job.get("file") else ""))
                else:
                    rows.append(f"{job_id}: {data.get('error', 'non disponibile')}")
            except Exception as error:
                rows.append(f"{job_id}: errore {error}")
        return "\n".join(rows)
