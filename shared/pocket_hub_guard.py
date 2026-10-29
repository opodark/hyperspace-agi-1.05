# SPDX-License-Identifier: Apache-2.0
"""Pocket Hub Failover Guard per nodi mobile HyperSpace (es. Samsung S24 Ultra).

Consente a un nodo mobile con `NODE_TIER=mobile` di fungere da Control Plane
di riserva (Pocket Hub) quando il Control Plane primario (Mac M5 o cluster root)
diventa irraggiungibile o va in stop.

Fasi operative:
1. STANDBY: il nodo monitora il Control Plane primario (`/health`).
2. ACTIVE_FAILOVER: dopo N mancate risposte consecutive, il nodo si auto-promuove
   ad Hub temporaneo per la mesh: accetta registrazioni dai peer (`/mesh/announce`),
   mantiene il registro nodi attivi (`/nodes/active`) e consente il bypass
   d'emergenza del gate di lavoro mobile.
3. RECOVERING / STANDBY: al ripristino del nodo primario, cede ordinatamente
   il ruolo di Hub tornando in ascolto passivo.
"""

from __future__ import annotations

import enum
import http.client
import json
import logging
import threading
import time
import urllib.parse
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger("hyperspace.pocket_hub")


class PocketHubState(str, enum.Enum):
    """Stati operativi del Pocket Hub Guard."""
    STANDBY = "standby"
    ACTIVE_FAILOVER = "active_failover"
    RECOVERING = "recovering"


class PocketHubGuard:
    """Watchdog e controller di transizione per il failover del Control Plane su nodo mobile."""

    def __init__(
        self,
        primary_cp_url: str = "",
        enabled: bool = False,
        check_interval_s: float = 10.0,
        failover_threshold_misses: int = 3,
        recovery_threshold_hits: int = 2,
        on_state_change: Optional[Callable[[PocketHubState, PocketHubState], None]] = None,
    ) -> None:
        self.primary_cp_url = primary_cp_url.strip().rstrip("/")
        self.enabled = enabled
        self.check_interval_s = max(1.0, float(check_interval_s))
        self.failover_threshold_misses = max(1, int(failover_threshold_misses))
        self.recovery_threshold_hits = max(1, int(recovery_threshold_hits))
        self.on_state_change = on_state_change

        self._state = PocketHubState.STANDBY
        self._consecutive_misses = 0
        self._consecutive_hits = 0
        self._last_probe_ts: Optional[float] = None
        self._last_probe_ok: Optional[bool] = None
        self._last_probe_latency_ms: Optional[float] = None
        self._last_state_change_ts: float = time.time()
        self._promotions_total: int = 0
        self._demotions_total: int = 0
        self._force_active: bool = False

        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._watchdog_thread: Optional[threading.Thread] = None

    @property
    def state(self) -> PocketHubState:
        with self._lock:
            return self._state

    def is_active_hub(self) -> bool:
        """Indica se il nodo deve agire correntemente come Hub attivo della mesh."""
        with self._lock:
            if self._force_active:
                return True
            return self.enabled and self._state == PocketHubState.ACTIVE_FAILOVER

    def set_forced_active(self, force: bool) -> None:
        """Forza o revoca manualmente la modalità hub attivo per test e diagnostica."""
        with self._lock:
            self._force_active = force

    def probe_primary(self, timeout: float = 3.0) -> Tuple[bool, float]:
        """Esegue un check HTTP GET /health verso il Control Plane primario."""
        if not self.primary_cp_url:
            return False, -1.0

        t0 = time.time()
        try:
            parsed = urllib.parse.urlparse(self.primary_cp_url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            path = (parsed.path.rstrip("/") + "/health") or "/health"

            if parsed.scheme == "https":
                conn = http.client.HTTPSConnection(host, port, timeout=timeout)
            else:
                conn = http.client.HTTPConnection(host, port, timeout=timeout)

            conn.request("GET", path, headers={"User-Agent": "HyperSpace-PocketHubGuard/1.05"})
            resp = conn.getresponse()
            status = resp.status
            conn.close()

            elapsed_ms = round((time.time() - t0) * 1000, 2)
            return status == 200, elapsed_ms
        except Exception as e:
            elapsed_ms = round((time.time() - t0) * 1000, 2)
            logger.debug(f"[PocketHubGuard] Probe failed for {self.primary_cp_url}: {e}")
            return False, elapsed_ms

    def tick(self, force_probe_result: Optional[bool] = None) -> PocketHubState:
        """Esegue una singola iterazione di verifica e transizione di stato."""
        if not self.enabled and not self._force_active:
            return self._state

        if force_probe_result is not None:
            is_ok = force_probe_result
            latency_ms = 10.0 if is_ok else -1.0
        else:
            is_ok, latency_ms = self.probe_primary()

        now = time.time()
        old_state = self._state
        transition_to: Optional[PocketHubState] = None

        with self._lock:
            self._last_probe_ts = now
            self._last_probe_ok = is_ok
            self._last_probe_latency_ms = latency_ms

            if is_ok:
                self._consecutive_hits += 1
                self._consecutive_misses = 0

                if self._state == PocketHubState.ACTIVE_FAILOVER:
                    if self._consecutive_hits >= self.recovery_threshold_hits:
                        transition_to = PocketHubState.RECOVERING
                elif self._state == PocketHubState.RECOVERING:
                    transition_to = PocketHubState.STANDBY

            else:
                self._consecutive_misses += 1
                self._consecutive_hits = 0

                if self._state in (PocketHubState.STANDBY, PocketHubState.RECOVERING):
                    if self._consecutive_misses >= self.failover_threshold_misses:
                        transition_to = PocketHubState.ACTIVE_FAILOVER

            if transition_to and transition_to != self._state:
                self._state = transition_to
                self._last_state_change_ts = now
                if transition_to == PocketHubState.ACTIVE_FAILOVER:
                    self._promotions_total += 1
                elif transition_to == PocketHubState.STANDBY:
                    self._demotions_total += 1

        if transition_to and transition_to != old_state:
            logger.warning(
                f"[PocketHubGuard] Transizione di stato: {old_state.value} -> {transition_to.value} "
                f"(hits={self._consecutive_hits}, misses={self._consecutive_misses})"
            )
            if self.on_state_change:
                try:
                    self.on_state_change(old_state, transition_to)
                except Exception as cb_err:
                    logger.error(f"[PocketHubGuard] Errore nel callback on_state_change: {cb_err}")

        return self._state

    def start_watchdog(self) -> None:
        """Avvia il thread in background per il monitoraggio continuo."""
        with self._lock:
            if self._watchdog_thread and self._watchdog_thread.is_alive():
                return
            self._stop_event.clear()
            self._watchdog_thread = threading.Thread(
                target=self._watchdog_loop,
                name="PocketHubWatchdog",
                daemon=True
            )
            self._watchdog_thread.start()
            logger.info(
                f"[PocketHubGuard] Watchdog avviato verso {self.primary_cp_url} "
                f"(intervallo: {self.check_interval_s}s, threshold misses: {self.failover_threshold_misses})"
            )

    def stop_watchdog(self, timeout: float = 3.0) -> None:
        """Arresta in modo pulito il thread watchdog."""
        self._stop_event.set()
        thread = self._watchdog_thread
        if thread and thread.is_alive():
            thread.join(timeout=timeout)
        with self._lock:
            self._watchdog_thread = None
        logger.info("[PocketHubGuard] Watchdog arrestato.")

    def _watchdog_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.tick()
            except Exception as e:
                logger.error(f"[PocketHubGuard] Errore non gestito nel tick del watchdog: {e}")

            if self._stop_event.wait(timeout=self.check_interval_s):
                break

    def snapshot(self) -> Dict[str, Any]:
        """Restituisce un riepilogo JSON dello stato operativo del Pocket Hub."""
        with self._lock:
            return {
                "enabled": self.enabled,
                "state": self._state.value,
                "is_active_hub": self.is_active_hub(),
                "forced_active": self._force_active,
                "primary_cp_url": self.primary_cp_url,
                "consecutive_misses": self._consecutive_misses,
                "consecutive_hits": self._consecutive_hits,
                "failover_threshold_misses": self.failover_threshold_misses,
                "recovery_threshold_hits": self.recovery_threshold_hits,
                "last_probe_ts": self._last_probe_ts,
                "last_probe_ok": self._last_probe_ok,
                "last_probe_latency_ms": self._last_probe_latency_ms,
                "last_state_change_ts": self._last_state_change_ts,
                "promotions_total": self._promotions_total,
                "demotions_total": self._demotions_total,
            }
