#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
shared/adaptive_mesh_circuit_breaker.py
Modulo promosso in produzione da HyperSpace R&D Sovereign Lab.
Prototipo sorgente: proto_adaptivemeshcircuitbreaker_1793022231.py
Data promozione: 2026-10-28T10:17:23+00:00
Autore: antigravity_sovereign

Implementa il pattern Circuit Breaker per chiamate distribuite inter-nodo nella mesh
(OMEN, ASUS, Mac) con stati CLOSED (normale), OPEN (guasto, fail-fast), HALF_OPEN (sonda).
Supporta chiamate sincrone e asincrone, fallback automatici e registry multi-target.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Callable, Dict, Optional, TypeVar

T = TypeVar("T")


class CircuitBreakerOpenError(ConnectionError):
    """Sollevata quando una chiamata viene tentata mentre il circuito è OPEN."""
    pass


class AdaptiveMeshCircuitBreaker:
    CLOSED = 0
    OPEN = 1
    HALF_OPEN = 2

    STATE_NAMES = {
        CLOSED: "CLOSED",
        OPEN: "OPEN",
        HALF_OPEN: "HALF_OPEN",
    }

    _registry: Dict[str, "AdaptiveMeshCircuitBreaker"] = {}
    _registry_lock = threading.Lock()

    def __init__(
        self,
        name: str = "default",
        fail_thresh: int = 3,
        recov_timeout: float = 5.0,
    ):
        self.name = name
        self.fail_thresh = fail_thresh
        self.recov_timeout = recov_timeout
        self.state = self.CLOSED
        self.failures = 0
        self.last_fail: Optional[float] = None
        self._lock = threading.Lock()

    @classmethod
    def for_target(
        cls,
        name: str,
        fail_thresh: int = 3,
        recov_timeout: float = 5.0,
    ) -> "AdaptiveMeshCircuitBreaker":
        """Recupera o inizializza l'istanza singleton per un target specifico (es. 'asus-v16', 'omen-16')."""
        with cls._registry_lock:
            if name not in cls._registry:
                cls._registry[name] = cls(name=name, fail_thresh=fail_thresh, recov_timeout=recov_timeout)
            return cls._registry[name]

    @property
    def state_name(self) -> str:
        with self._lock:
            self.maybe_recover()
            return self.STATE_NAMES.get(self.state, "UNKNOWN")

    def is_available(self) -> bool:
        """Restituisce True se il circuito consente il transito della richiesta (CLOSED o HALF_OPEN)."""
        with self._lock:
            self.maybe_recover()
            return self.state != self.OPEN

    def call(
        self,
        func: Callable[..., T],
        *args: Any,
        fallback: Optional[Callable[..., T]] = None,
        **kwargs: Any,
    ) -> T:
        """Esegue una funzione sincrona protetta dal circuito con fallback opzionale."""
        with self._lock:
            self.maybe_recover()
            if self.state == self.OPEN:
                if fallback is not None:
                    return fallback(*args, **kwargs)
                raise CircuitBreakerOpenError(
                    f"Circuit breaker per '{self.name}' è OPEN (ultimo fallimento {time.time() - (self.last_fail or 0):.1f}s fa)."
                )

        try:
            result = func(*args, **kwargs)
            with self._lock:
                self._on_success()
            return result
        except Exception as exc:
            with self._lock:
                self._on_failure()
            if fallback is not None:
                return fallback(*args, **kwargs)
            raise exc

    async def async_call(
        self,
        coro_func: Callable[..., Any],
        *args: Any,
        fallback: Optional[Callable[..., Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Esegue una coroutine protetta dal circuito con fallback opzionale."""
        with self._lock:
            self.maybe_recover()
            if self.state == self.OPEN:
                if fallback is not None:
                    if asyncio.iscoroutinefunction(fallback):
                        return await fallback(*args, **kwargs)
                    return fallback(*args, **kwargs)
                raise CircuitBreakerOpenError(
                    f"Circuit breaker per '{self.name}' è OPEN (asincrono)."
                )

        try:
            result = await coro_func(*args, **kwargs)
            with self._lock:
                self._on_success()
            return result
        except Exception as exc:
            with self._lock:
                self._on_failure()
            if fallback is not None:
                if asyncio.iscoroutinefunction(fallback):
                    return await fallback(*args, **kwargs)
                return fallback(*args, **kwargs)
            raise exc

    def _on_success(self):
        if self.state == self.HALF_OPEN:
            self.state = self.CLOSED
        self.failures = 0

    def _on_failure(self):
        self.failures += 1
        if self.failures >= self.fail_thresh:
            self.state = self.OPEN
            self.last_fail = time.time()

    def maybe_recover(self):
        """Se il circuito è OPEN e il timeout di recovery è trascorso, passa a HALF_OPEN."""
        if self.state == self.OPEN and time.time() - (self.last_fail or 0) >= self.recov_timeout:
            self.state = self.HALF_OPEN

    def reset(self):
        """Ripristina forzatamente il circuito allo stato CLOSED."""
        with self._lock:
            self.state = self.CLOSED
            self.failures = 0
            self.last_fail = None

    def status(self) -> Dict[str, Any]:
        with self._lock:
            self.maybe_recover()
            return {
                "name": self.name,
                "state": self.STATE_NAMES.get(self.state, "UNKNOWN"),
                "failures": self.failures,
                "fail_thresh": self.fail_thresh,
                "recov_timeout": self.recov_timeout,
                "last_fail": self.last_fail,
            }
