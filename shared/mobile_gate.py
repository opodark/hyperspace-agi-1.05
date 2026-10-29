# SPDX-License-Identifier: Apache-2.0
# shared/mobile_gate.py
# HyperSpace AGI 1.05 — Gate di lavoro per nodi mobili (tier "mobile")
"""Decide se un nodo mobile (telefono Android in Termux) può accettare lavoro
dalla mesh in questo momento.

Un telefono non è un laptop: lavorare a batteria lo scarica in poche ore e
scalda, e un utente lo usa anche come telefono. La regola quindi è più stretta
di shared/power_policy.py, che resta valida per i portatili:

  1. lavora solo collegato al caricatore (MOBILE_REQUIRE_CHARGER, default on);
  2. mai sotto una carica minima (MOBILE_MIN_BATTERY_PCT, default 40);
  3. si ferma quando la batteria scalda (MOBILE_MAX_TEMP_C, default 41 °C) e
     riparte solo quando è scesa sotto MOBILE_RESUME_TEMP_C (default 38 °C):
     l'isteresi evita l'accendi-spegni attorno alla soglia;
  4. facoltativamente solo in una finestra oraria (MOBILE_WORK_WINDOW, es.
     "23:00-07:00"): il telefono di giorno è una console, di notte un worker.

Il gate non rifiuta solo le richieste: quando è chiuso il nodo si dichiara
`degraded` in /status, /metrics e nel registry, così il control-plane smette di
sceglierlo invece di ricevere 503 a ripetizione.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, time as dtime
from typing import Any, Callable, Dict, List, Optional, Tuple

MOBILE_TIER = "mobile"

REASON_NOT_PLUGGED = "not_plugged"
REASON_BATTERY_LOW = "battery_low"
REASON_TOO_HOT = "too_hot"
REASON_OUTSIDE_WINDOW = "outside_window"

_REASON_TEXT = {
    REASON_NOT_PLUGGED: "non collegato al caricatore",
    REASON_BATTERY_LOW: "batteria sotto la soglia minima",
    REASON_TOO_HOT: "batteria troppo calda",
    REASON_OUTSIDE_WINDOW: "fuori dalla finestra di lavoro",
}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "") or default)
    except ValueError:
        return default


def parse_window(spec: str) -> Optional[Tuple[dtime, dtime]]:
    """"23:00-07:00" -> (23:00, 07:00). Vuoto o malformato -> None (sempre)."""
    spec = (spec or "").strip()
    if not spec or "-" not in spec:
        return None
    try:
        a, b = (part.strip() for part in spec.split("-", 1))
        start = datetime.strptime(a, "%H:%M").time()
        end = datetime.strptime(b, "%H:%M").time()
    except ValueError:
        return None
    if start == end:
        return None
    return start, end


def in_window(now: dtime, window: Optional[Tuple[dtime, dtime]]) -> bool:
    """True se `now` cade nella finestra. Gestisce le finestre a cavallo della
    mezzanotte (23:00-07:00)."""
    if window is None:
        return True
    start, end = window
    if start < end:
        return start <= now < end
    return now >= start or now < end


@dataclass
class MobileGateConfig:
    require_charger: bool = True
    min_battery_pct: float = 40.0
    max_temp_c: float = 41.0
    resume_temp_c: float = 38.0
    window: Optional[Tuple[dtime, dtime]] = None
    window_spec: str = ""

    @classmethod
    def from_env(cls) -> "MobileGateConfig":
        spec = os.getenv("MOBILE_WORK_WINDOW", "").strip()
        max_t = _env_float("MOBILE_MAX_TEMP_C", 41.0)
        resume_t = min(_env_float("MOBILE_RESUME_TEMP_C", 38.0), max_t)
        return cls(
            require_charger=_env_bool("MOBILE_REQUIRE_CHARGER", True),
            min_battery_pct=_env_float("MOBILE_MIN_BATTERY_PCT", 40.0),
            max_temp_c=max_t,
            resume_temp_c=resume_t,
            window=parse_window(spec),
            window_spec=spec if parse_window(spec) else "",
        )


def evaluate_mobile_gate(
    power: Optional[Dict[str, Any]],
    cfg: MobileGateConfig,
    now: Optional[dtime] = None,
    was_hot: bool = False,
) -> Dict[str, Any]:
    """Valutazione pura (testabile) del gate.

    `was_hot` è lo stato dell'isteresi termica: se l'ultima valutazione aveva
    fermato il nodo per calore, la ripartenza richiede di scendere sotto
    `resume_temp_c`, non solo sotto `max_temp_c`."""
    p = power or {}
    reasons: List[str] = []

    ac_line = bool(p.get("ac_line", False))
    pct = p.get("battery_pct")
    temp = p.get("temperature_c")

    if cfg.require_charger and not ac_line:
        reasons.append(REASON_NOT_PLUGGED)
    if pct is not None and float(pct) < cfg.min_battery_pct:
        reasons.append(REASON_BATTERY_LOW)

    hot = False
    if temp is not None:
        t = float(temp)
        hot = t > cfg.resume_temp_c if was_hot else t >= cfg.max_temp_c
        if hot:
            reasons.append(REASON_TOO_HOT)

    if now is None:
        now = datetime.now().time()
    if not in_window(now, cfg.window):
        reasons.append(REASON_OUTSIDE_WINDOW)

    return {
        "open": not reasons,
        "reasons": reasons,
        "summary": "pronto a lavorare" if not reasons else "; ".join(_REASON_TEXT[r] for r in reasons),
        "hot": hot,
        "ac_line": ac_line,
        "battery_pct": pct,
        "temperature_c": temp,
        "window": cfg.window_spec or None,
    }


class MobileGate:
    """Stato del gate con aggiornamento in background.

    La lettura della batteria su Android (termux-battery-status) è lenta e
    sincrona: un thread la aggiorna ogni `refresh_s` secondi e gli endpoint
    leggono lo stato già pronto, senza bloccare l'event loop."""

    def __init__(
        self,
        cfg: MobileGateConfig,
        power_fn: Callable[[], Dict[str, Any]],
        enabled: bool = True,
        refresh_s: float = 30.0,
        clock: Callable[[], dtime] = lambda: datetime.now().time(),
    ):
        self.cfg = cfg
        self.enabled = enabled
        self._power_fn = power_fn
        self._refresh_s = max(5.0, float(refresh_s))
        self._clock = clock
        self._lock = threading.Lock()
        self._state: Optional[Dict[str, Any]] = None
        self._updated = 0.0
        self._was_hot = False
        self._thread: Optional[threading.Thread] = None

    def refresh(self) -> Dict[str, Any]:
        if not self.enabled:
            state = {"open": True, "reasons": [], "summary": "gate disattivato", "enabled": False}
        else:
            try:
                power = self._power_fn()
            except Exception:
                power = None
            with self._lock:
                was_hot = self._was_hot
            state = evaluate_mobile_gate(power, self.cfg, now=self._clock(), was_hot=was_hot)
            state["enabled"] = True
            state["checked_at"] = int(time.time())
        with self._lock:
            self._was_hot = bool(state.get("hot"))
            self._state = state
            self._updated = time.monotonic()
        return dict(state)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            state, age = self._state, time.monotonic() - self._updated
        if state is None or age > self._refresh_s * 3:
            return self.refresh()
        return dict(state)

    def allows_work(self) -> bool:
        return bool(self.snapshot().get("open", True))

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return

        def _loop():
            while True:
                self.refresh()
                time.sleep(self._refresh_s)

        self._thread = threading.Thread(target=_loop, name="mobile-gate", daemon=True)
        self._thread.start()
