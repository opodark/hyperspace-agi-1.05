# SPDX-License-Identifier: Apache-2.0
"""Pure scheduling helpers for the illustrated dream loop."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def in_hour_window(hour: int, start: int, end: int) -> bool:
    """Support normal windows (1..7) and windows crossing midnight (22..6)."""
    hour, start, end = int(hour) % 24, int(start) % 24, int(end) % 24
    if start == end:
        return True
    return start <= hour < end if start < end else hour >= start or hour < end


def choose_author(counts: dict, *, maximum: int, turn: int = 0,
                  total_maximum: int | None = None) -> str | None:
    """Choose the least-used sister, alternating ties, within the daily cap.

    `total_maximum` (opzionale) è il tetto sulla somma delle due sorelle: con un
    profilo social unico si vuole un sogno al giorno in tutto, non uno a testa.
    Vale solo se maggiore di zero; `None` conserva il comportamento storico
    (solo il tetto per autrice).
    """
    if total_maximum is not None and int(total_maximum) > 0:
        somma = sum(int(counts.get(n, 0)) for n in ("anna", "aurora"))
        if somma >= int(total_maximum):
            return None
    order = ("anna", "aurora") if int(turn) % 2 == 0 else ("aurora", "anna")
    available = [name for name in order if int(counts.get(name, 0)) < int(maximum)]
    if not available:
        return None
    return min(available, key=lambda name: int(counts.get(name, 0)))


def conteggi_del_giorno(voci, now: datetime, *, tipo: str = "sogno") -> tuple[dict, float]:
    """(sogni per autrice nel giorno locale di `now`, istante dell'ultimo).

    Quota giornaliera e distanza minima fra due sogni sono la stessa decisione
    presa due volte: dal loop, che decide se sognare, e dal monitor, che deve
    raccontare *perché* no. Vive qui perché le due risposte non possano divergere.
    L'istante dell'ultimo sogno torna come epoch: il loop ci calcola sopra
    `DREAM_LOOP_INTERVAL_S` senza rileggere il diario.
    """
    counts = {"anna": 0, "aurora": 0}
    latest = 0.0
    for row in voci or ():
        if not isinstance(row, dict) or row.get("tipo") != tipo:
            continue
        try:
            stamp = datetime.fromisoformat(str(row.get("ts", "")).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        latest = max(latest, stamp.timestamp())
        if stamp.astimezone(now.tzinfo).date() == now.date():
            author = str(row.get("author", "")).lower()
            if author in counts:
                counts[author] += 1
    return counts, latest


def prossima_finestra(now: datetime, start: int, end: int) -> datetime | None:
    """Quando la finestra notturna si riapre; None se è aperta adesso.

    Serve a una frase sola, che però è quella che si vuole leggere quando i sogni
    mancano: *non è rotto, si riapre alle 00:00*. Una finestra `start == end` è
    sempre aperta, quindi non c'è una prossima apertura da annunciare.
    """
    if in_hour_window(now.hour, start, end):
        return None
    apertura = now.replace(hour=int(start) % 24, minute=0, second=0, microsecond=0)
    if apertura <= now:
        apertura += timedelta(days=1)
    return apertura


def check_dream_power_guard(power_info: dict | None = None) -> tuple[bool, str]:
    """Valuta la policy energetica prima di avviare il ciclo di sogno.

    Ritorna (consentito: bool, motivo: str).
    I sogni notturni consumano GPU/CPU intensiva e devono essere rinviati se a batteria.
    """
    from shared.power_policy import should_defer_dream_cycle
    defer, reason = should_defer_dream_cycle(power_info)
    return (not defer, reason)

