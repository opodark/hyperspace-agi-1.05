#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Registro dettagliato dei sogni: una riga JSON per ogni passo della pipeline.

Perché esiste: `push_log` dice *che* un sogno è stato scritto, ma non porta
l'identificativo della voce — dopo non si può più ricostruire che fine ha fatto
lo sketch (in coda? disegnato? pubblicato? fallito?) né perché una notte è
passata senza sogni. Qui ogni passo è una riga legata dalla stessa `voce_id`, e la
coda dei job immagine chiude il cerchio: *il sogno di stanotte* diventa una storia
leggibile invece di cinque righe scollegate.

Il file è JSONL append-only (come `data/development_dreams.jsonl`): una riga
illeggibile non deve rendere illeggibile il registro, e un registro che cresce non
deve costare una riscrittura a ogni notte.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

# Le fasi della pipeline, nell'ordine in cui accadono. `scartato` e `saltato`
# rispondono alla domanda che si fa per prima — "perché stanotte non ha sognato
# nessuno?" — che senza di loro non lascerebbe traccia da nessuna parte.
FASI = ("scritto", "sketch", "disegnato", "pubblicato", "fallito", "scartato", "saltato")
MAX_DETTAGLIO = 400
COOLDOWN_SALTI_S = 1800


def adesso() -> str:
    """L'istante del registro, in UTC: come i log del control-plane."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def riga(*, fase: str, autore: str = "", voce_id: str = "", motivo: str = "",
         dettaglio: str = "", job_id: str = "", file: str = "", media_id: str = "",
         testo: str = "", prompt: str = "", ts: str = "") -> dict:
    """Una riga del registro. Una fase fuori da `FASI` è un errore, non un default."""
    fase = str(fase or "").strip().lower()
    if fase not in FASI:
        raise ValueError(f"fase sconosciuta: {fase!r} (attese: {', '.join(FASI)})")
    return {
        "ts": str(ts or adesso()),
        "voce_id": str(voce_id or ""),
        "autore": str(autore or "").strip().lower()[:64],
        "fase": fase,
        "motivo": str(motivo or "")[:120],
        "dettaglio": " ".join(str(dettaglio or "").split())[:MAX_DETTAGLIO],
        "job_id": str(job_id or ""),
        "file": str(file or ""),
        "media_id": str(media_id or ""),
        "testo": " ".join(str(testo or "").split())[:MAX_DETTAGLIO],
        "prompt": " ".join(str(prompt or "").split())[:MAX_DETTAGLIO],
    }


def _momento(valore) -> datetime | None:
    testo = str(valore or "").strip()
    if not testo:
        return None
    try:
        momento = datetime.fromisoformat(testo.replace("Z", "+00:00"))
    except ValueError:
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def salto_da_scrivere(motivo: str, precedente: dict | None, *,
                      istante: str = "", cooldown_s: int = COOLDOWN_SALTI_S) -> bool:
    """True se il salto merita una riga: motivo nuovo, o cooldown scaduto.

    Il loop ripassa ogni pochi minuti: senza questa regola «fuori finestra»
    riempirebbe il registro di righe identiche e annegherebbe l'unica cosa che
    conta, cioè il *primo* salto con il suo motivo.
    """
    motivo = str(motivo or "").strip()
    if not motivo:
        return False
    if not isinstance(precedente, dict) or precedente.get("motivo") != motivo:
        return True
    ora = _momento(istante or adesso())
    prima = _momento(precedente.get("ts"))
    if ora is None or prima is None:
        return True
    return (ora - prima).total_seconds() >= max(0, int(cooldown_s))


class RegistroSogni:
    """Append-only su file: scrive una riga, legge le ultime N.

    Senza percorso non scrive e non legge: è il modo in cui i test e la sandbox
    usano la stessa classe senza toccare i dati del control-plane.
    """

    def __init__(self, percorso: str = ""):
        self.percorso = str(percorso or "")

    def append(self, voce: dict) -> dict:
        """Accoda una riga (dict da `riga()`). Senza percorso non scrive."""
        voce = voce if isinstance(voce, dict) else {}
        if voce.get("fase") not in FASI:
            raise ValueError("riga senza una fase valida")
        if not self.percorso:
            return voce
        cartella = os.path.dirname(self.percorso)
        if cartella:
            os.makedirs(cartella, exist_ok=True)
        with open(self.percorso, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(voce, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return voce

    def read(self, limit: int = 200) -> list[dict]:
        """Le ultime `limit` righe valide, in ordine cronologico.

        Una riga rotta (JSON troncato, fase ignota) viene saltata: il registro
        serve a capire cosa è successo, non a fallire su una riga.
        """
        if not self.percorso or not os.path.isfile(self.percorso):
            return []
        righe: list[dict] = []
        with open(self.percorso, "r", encoding="utf-8") as stream:
            for linea in stream:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    voce = json.loads(linea)
                except ValueError:
                    continue
                if isinstance(voce, dict) and voce.get("fase") in FASI:
                    righe.append(voce)
        limite = max(0, int(limit))
        return righe[-limite:] if limite else []

    def ultimo(self, *, fase: str = "", voce_id: str = "") -> dict | None:
        """L'ultima riga (della fase o della voce indicata), o None."""
        for voce in reversed(self.read()):
            if fase and voce.get("fase") != fase:
                continue
            if voce_id and str(voce.get("voce_id") or "") != str(voce_id):
                continue
            return voce
        return None

    def ultimo_per_voce(self) -> dict[str, dict]:
        """La fase in cui si trova adesso ogni voce: `{voce_id: riga}`."""
        out: dict[str, dict] = {}
        for voce in self.read():
            if voce.get("voce_id"):
                out[str(voce["voce_id"])] = voce
        return out


def scrivi(percorso: str, **campi) -> dict:
    """Scorciatoia: aggiunge una riga e non fallisce mai forte.

    La pipeline dei sogni non deve morire perché il registro non è scrivibile
    (disco pieno, volume in sola lettura): il sogno è più importante della sua
    traccia. Chi vuole vedere l'errore usa direttamente `RegistroSogni`.
    """
    try:
        return RegistroSogni(percorso).append(riga(**campi))
    except (OSError, ValueError):
        return {}
