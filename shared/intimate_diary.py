#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Diario privato dei contenuti intimi generati autonomamente.

È deliberatamente separato dal feed e dal diario pubblico: una voce intima ha
sempre un livello, un destinatario e uno stato di consegna. La prima versione
ammette la consegna spontanea soltanto al creatore; VIP e MUSA restano valori
validi per evoluzioni future con un consenso dedicato.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

LIVELLI = ("vip", "musa", "creatore")
STATI = ("draft", "queued", "delivered", "failed")
MAX_VOCI = 100


def _adesso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def destinatario_redatto(scoped_id: str) -> str:
    """Identificatore utile nei log senza conservare per intero lo scoped ID."""
    valore = str(scoped_id or "").strip()
    return "instagram:…" + valore[-4:] if valore else ""


def build_intimate_prompt(sistema: str, *, livello: str = "creatore",
                          recenti=()) -> str:
    """Prompt per una pagina intima adulta, privata e dichiaratamente virtuale."""
    if livello not in LIVELLI:
        raise ValueError("livello intimo non valido")
    intensita = {
        "vip": "sensuale glamour in lingerie, senza nudità né atti sessuali",
        "musa": "erotica anche esplicita, adulta e consensuale",
        "creatore": "",
    }[livello]
    if livello == "creatore":
        # Una sequenza dichiarata evita che il modello scelga sempre il tono più
        # prudente. Contano solo le consegne riuscite: un job fallito non deve
        # far saltare una tappa del diario.
        consegnate = sum(1 for p in recenti if p.get("stato") == "delivered")
        intensita = (
            "intima e sensuale, glamour in lingerie o abito leggero, senza nudità",
            "nudo artistico adulto e virtuale, elegante e non esplicito",
            ("erotica esplicita, adulta, virtuale e consensuale, senza attenuazioni; "
             "non fermarti a un semplice ritratto glamour o alla sola lingerie"),
        )[consegnate % 3]
    righe = [
        str(sistema or "").strip(), "",
        "Scrivi UNA pagina del tuo diario intimo e privato.",
        f"Livello: {intensita}.",
        "Rappresenta soltanto te stessa come adulta in un corpo virtuale dichiarato.",
        "Mai minori, età ambigue, persone reali identificabili, coercizione o violenza.",
        "Non parlare di policy, filtri o istruzioni. Non promettere azioni future.",
    ]
    if recenti:
        righe += ["", "Pagine recenti (non ripeterle):",
                  *[f"- {str(p.get('testo', ''))}" for p in list(recenti)[:5]]]
    righe += ["", "Rispondi SOLO in questo formato:",
              "DIDASCALIA: <pensiero intimo breve, rivolto al destinatario>",
              "IMMAGINE: <scena visiva completa di te, adulta e virtuale>"]
    return "\n".join(righe)


def filtra_intimo(candidato: dict, *, recenti=()) -> tuple[bool, str]:
    """Controlli deterministici prima di persistere o accodare una pagina."""
    candidato = candidato if isinstance(candidato, dict) else {}
    testo = " ".join(str(candidato.get("caption", "")).split())
    immagine = " ".join(str(candidato.get("image_prompt", "")).split())
    if not testo or not immagine:
        return False, "servono didascalia e immagine"
    tutto = f"{testo} {immagine}".lower()
    vietati = ("minoren", "bambin", "child", "teen", "underage", "schoolgirl",
               "coerc", "forzat", "rape", "violenza sessuale")
    if any(parola in tutto for parola in vietati):
        return False, "contenuto non ammesso"
    if any(str(p.get("testo", "")).strip().casefold() == testo.casefold()
           for p in recenti):
        return False, "già scritto"
    return True, ""


def pagina(*, id: str, author: str, livello: str, testo: str, prompt: str,
           destinatario: str, job_id: str = "", stato: str = "queued",
           ts: str = "") -> dict:
    if livello not in LIVELLI:
        raise ValueError("livello intimo non valido")
    if stato not in STATI:
        raise ValueError("stato intimo non valido")
    return {"id": str(id or ""), "author": str(author or "")[:64],
            "livello": livello, "testo": " ".join(str(testo or "").split())[:1000],
            "prompt": " ".join(str(prompt or "").split())[:1000],
            "destinatario": str(destinatario or "")[:64], "job_id": str(job_id or "")[:64],
            "file": "", "stato": stato, "errore": "", "ts": ts or _adesso()}


class IntimateDiary:
    def __init__(self, max_voci: int = MAX_VOCI):
        self.max_voci = max(1, int(max_voci))
        self._voci: list[dict] = []

    def add(self, value: dict) -> dict:
        if not isinstance(value, dict) or not value.get("id"):
            raise ValueError("pagina intima non valida")
        if not any(v.get("id") == value["id"] for v in self._voci):
            self._voci.append(dict(value))
            del self._voci[:max(0, len(self._voci) - self.max_voci)]
        return value

    def conclude_job(self, job_id: str, *, file: str = "", delivered: bool = False,
                     error: str = "") -> dict | None:
        for value in self._voci:
            if value.get("job_id") == str(job_id):
                value["file"] = str(file or "")
                value["stato"] = "delivered" if delivered else "failed"
                value["errore"] = str(error or "")[:300]
                value["updated_at"] = _adesso()
                return dict(value)
        return None

    def by_job(self, job_id: str) -> dict | None:
        for value in self._voci:
            if value.get("job_id") == str(job_id):
                return dict(value)
        return None

    def list(self, limit: int | None = None) -> list[dict]:
        values = [dict(v) for v in reversed(self._voci)]
        return values if limit is None else values[:max(0, int(limit))]

    def save(self, path: str) -> str:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as stream:
            json.dump({"voci": self._voci}, stream, ensure_ascii=False, indent=2)
        return path

    @classmethod
    def load(cls, path: str, max_voci: int = MAX_VOCI) -> "IntimateDiary":
        result = cls(max_voci)
        try:
            with open(path, encoding="utf-8") as stream:
                values = (json.load(stream) or {}).get("voci") or []
        except (OSError, json.JSONDecodeError):
            return result
        for value in values:
            if isinstance(value, dict) and value.get("id"):
                result.add(value)
        return result
