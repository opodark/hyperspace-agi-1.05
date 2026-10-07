#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Il monitor dei sogni: risponde dall'esterno, senza toccare la pipeline.

Le domande vere, in ordine di frequenza: quand'è stato l'ultimo sogno? che fine ha
fatto lo sketch? il post è arrivato su Instagram? perché stanotte non ha sognato
nessuno? Il registro dettagliato (`shared/dream_log.py`) e la coda dei job
rispondono; qui si combinano in una riga di stato per sogno, più un verdetto di
salute — perché l'unico guasto davvero silenzioso è il loop che smette di sognare
senza che nessuno se ne accorga.

Logica pura: niente IO, niente rete. Il control-plane e `scripts/dream_monitor.py`
passano diario, coda e registro e ricevono la stessa fotografia, così il monitor
della dashboard e quello da terminale non possono dire cose diverse.
"""
from __future__ import annotations

from datetime import datetime, timezone

from shared.dream_schedule import conteggi_del_giorno, in_hour_window, prossima_finestra

FASE_IN_ATTESA = "in attesa di sketch"
FASE_IN_CODA = "sketch in coda"
FASE_IN_CORSO = "sketch in corso"
FASE_DA_PUBBLICARE = "disegnato, da pubblicare"
FASE_PUBBLICATO = "pubblicato"
FASE_SKETCH_FALLITO = "sketch fallito"
FASE_PUBBLICAZIONE_FALLITA = "pubblicazione fallita"

_STATI_JOB = {"pending": FASE_IN_CODA, "running": FASE_IN_CORSO}


def quando(valore) -> datetime | None:
    """ISO (con o senza Z) oppure epoch → datetime con fuso; None se illeggibile."""
    if isinstance(valore, (int, float)) and valore:
        return datetime.fromtimestamp(float(valore), tz=timezone.utc)
    testo = str(valore or "").strip()
    if not testo:
        return None
    try:
        momento = datetime.fromisoformat(testo.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.fromtimestamp(float(testo), tz=timezone.utc)
        except (TypeError, ValueError):
            return None
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def fase_di(voce: dict, job: dict | None = None, evento: dict | None = None) -> str:
    """Dove si trova un sogno, adesso: dal testo scritto al post pubblicato.

    L'ordine dei controlli è l'ordine dei fatti: l'esito della pubblicazione vince
    su tutto (anche quando è negativo), poi parla lo stato dello sketch, e solo
    alla fine il file della voce. Un job `done` senza `published` non è un guasto:
    è la finestra fra il disegno finito e la pubblicazione, che dura secondi.
    """
    voce = voce if isinstance(voce, dict) else {}
    job = job if isinstance(job, dict) else {}
    evento = evento if isinstance(evento, dict) else {}
    stato_ig = str(voce.get("instagram_status") or "").strip().lower()
    fase_evento = str(evento.get("fase") or "").strip().lower()
    if fase_evento == "pubblicato" or stato_ig == "published":
        return FASE_PUBBLICATO
    if fase_evento == "fallito" or stato_ig == "failed":
        return FASE_PUBBLICAZIONE_FALLITA
    stato_job = str(job.get("stato") or "").strip().lower()
    if stato_job == "failed":
        return FASE_SKETCH_FALLITO
    if stato_job == "done":
        return FASE_DA_PUBBLICARE
    if stato_job in _STATI_JOB:
        return _STATI_JOB[stato_job]
    return FASE_DA_PUBBLICARE if voce.get("file") else FASE_IN_ATTESA


def indice_job(jobs) -> dict[str, dict]:
    """`{voce_id: job più recente}` da una coda o da un elenco di job.

    Accetta il dict di `image-jobs.json`, il risultato di `ImmagineQueue.stato()`
    o una lista: la forma della coda è cambiata una volta, il monitor non deve
    rompersi la prossima. Se la stessa voce ha più job (rigenerazione), vince il
    più recente: è quello che ha prodotto l'immagine che si vede adesso.
    """
    elenco: list = []
    if isinstance(jobs, dict):
        grezzo = jobs.get("jobs", jobs)
        if isinstance(grezzo, dict):
            elenco = [v for v in grezzo.values() if isinstance(v, dict)]
        elif isinstance(grezzo, list):
            elenco = [v for v in grezzo if isinstance(v, dict)]
        elif isinstance(jobs, dict) and jobs and all(isinstance(v, dict) for v in jobs.values()):
            elenco = [v for v in jobs.values() if isinstance(v, dict)]
    elif isinstance(jobs, (list, tuple)):
        elenco = [v for v in jobs if isinstance(v, dict)]
    indice: dict[str, dict] = {}
    for job in elenco:
        voce_id = str(job.get("destinazione") or "")
        if not voce_id:
            continue
        prima = indice.get(voce_id)
        if prima is None or float(job.get("creato_ts") or 0) >= float(prima.get("creato_ts") or 0):
            indice[voce_id] = job
    return indice


def pipeline(voci, jobs=None, registro=None, *, tipo: str = "sogno",
             limit: int = 12) -> list[dict]:
    """Le ultime `limit` voci di un tipo, con la fase in cui si trovano.

    Non presume l'ordine dell'elenco: il diario lo consegna dal più recente, la
    coda dal più vecchio, e un monitor che si fida dell'ordine racconta la
    pipeline al contrario. Ordina per `ts` e mostra per prima la più recente.

    `registro`: `{voce_id: riga}` dal registro dettagliato (opzionale). Serve a
    distinguere "pubblicato adesso" da "pubblicato" e a mostrare l'ultimo motivo
    di uno scarto, che non sta nel diario.
    """
    indice = indice_job(jobs)
    registro = registro if isinstance(registro, dict) else {}
    righe = [v for v in (voci or ()) if isinstance(v, dict) and v.get("tipo") == tipo]
    righe.sort(key=lambda v: quando(v.get("ts")) or datetime.min.replace(tzinfo=timezone.utc))
    righe = righe[-max(0, int(limit)):] if limit else righe
    out: list[dict] = []
    for voce in reversed(righe):                    # le più recenti per prime
        voce_id = str(voce.get("id") or "")
        job = indice.get(voce_id) or {}
        evento = registro.get(voce_id) or {}
        out.append({
            "voce_id": voce_id,
            "autore": str(voce.get("author") or ""),
            "ts": str(voce.get("ts") or ""),
            "testo": str(voce.get("testo") or "")[:160],
            "prompt": str(voce.get("prompt") or "")[:160],
            "fase": fase_di(voce, job, evento),
            "instagram": str(voce.get("instagram_status") or "n/d"),
            "instagram_errore": str(voce.get("instagram_error") or "")[:200],
            "job_id": str(job.get("id") or ""),
            "job_stato": str(job.get("stato") or ""),
            "disegnato": bool(voce.get("file")),
            "evento": str(evento.get("fase") or ""),
            "dettaglio": str(evento.get("dettaglio") or "")[:200],
        })
    return out


def salute(ultimo, adesso: datetime, *, abilitato: bool = True,
           aperta: bool = False) -> dict:
    """Il verdetto sul ciclo: `ok`, `attenzione`, `muto` o `spento`.

    `muto` è il guasto che nessuno nota: acceso, e nessun sogno da due o più
    notti. Un giorno senza sogni (`attenzione`) non è ancora un guasto — la
    finestra notturna può essere appena iniziata — ma è l'ultimo avviso utile.
    """
    if not abilitato:
        return {"verdetto": "spento", "notti": 0,
                "dettaglio": "DREAM_LOOP_ENABLED non è true: il ciclo dei sogni è fermo"}
    momento = quando(ultimo)
    if momento is None:
        return {"verdetto": "muto", "notti": None,
                "dettaglio": "nessun sogno nel diario da quando il ciclo è acceso"}
    notti = (adesso.date() - momento.astimezone(adesso.tzinfo).date()).days
    if notti <= 0:
        return {"verdetto": "ok", "notti": 0,
                "dettaglio": f"ultimo sogno {momento.astimezone(adesso.tzinfo):%Y-%m-%d %H:%M} "
                             f"({momento.astimezone(adesso.tzinfo).strftime('%Z')})"}
    if notti == 1 and aperta:
        return {"verdetto": "attenzione", "notti": 1,
                "dettaglio": "stanotte non ha ancora sognato, ma la finestra è aperta"}
    if notti == 1:
        return {"verdetto": "attenzione", "notti": 1,
                "dettaglio": "un giorno senza sogni: la finestra si riapre stanotte"}
    return {"verdetto": "muto", "notti": notti,
            "dettaglio": f"nessun sogno da {notti} giorni: il ciclo è acceso ma tace"}


def indice_eventi(righe) -> dict[str, dict]:
    """`{voce_id: ultima riga del registro}` — solo le righe legate a una voce."""
    out: dict[str, dict] = {}
    for riga in righe or ():
        if isinstance(riga, dict) and riga.get("voce_id"):
            out[str(riga["voce_id"])] = riga
    return out


def salti(righe, *, limit: int = 5) -> list[dict]:
    """Gli ultimi motivi per cui non si è sognato, dal più recente.

    È la parte del registro che il diario non può raccontare: quando non nasce
    nessuna voce, l'unica traccia di quella notte è qui.
    """
    motivi = [riga for riga in (righe or ())
              if isinstance(riga, dict) and riga.get("fase") == "saltato"]
    limite = max(0, int(limit))
    return list(reversed(motivi[-limite:])) if limite else []


def sintesi(*, voci, adesso: datetime, jobs=None, eventi=(), config=None,
            limit: int = 12) -> dict:
    """La fotografia completa: config, quota, ultimo sogno, pipeline, salute.

    `config` sono i valori con cui il loop decide (`abilitato`, `finestra`
    (inizio, fine), `quota_per_autrice`, `intervallo_s`): chi chiama li legge
    dall'ambiente. Qui non si legge nulla da soli, così la stessa funzione gira
    in un test e in un container.
    """
    config = dict(config or {})
    righe = list(voci or ())
    inizio, fine = tuple(config.get("finestra") or (0, 8))[:2]
    conteggi, ultimo = conteggi_del_giorno(righe, adesso)
    aperta = in_hour_window(adesso.hour, inizio, fine)
    prossima = prossima_finestra(adesso, inizio, fine)
    ultimo_iso = (datetime.fromtimestamp(ultimo, tz=timezone.utc).isoformat(timespec="seconds")
                  if ultimo else None)
    return {
        "adesso": adesso.isoformat(timespec="seconds"),
        "fuso": str(adesso.tzinfo),
        "config": {**config, "finestra": [inizio, fine]},
        "finestra_aperta": aperta,
        "prossima_finestra": prossima.isoformat(timespec="seconds") if prossima else None,
        "quota": {**conteggi, "totale": sum(conteggi.values())},
        "ultimo_sogno": ultimo_iso,
        "salute": salute(ultimo_iso, adesso, abilitato=bool(config.get("abilitato", True)),
                         aperta=aperta),
        "sogni": pipeline(righe, jobs, indice_eventi(eventi), limit=limit),
        "salti": salti(eventi, limit=5),
    }
