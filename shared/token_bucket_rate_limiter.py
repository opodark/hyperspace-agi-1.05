#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
shared/token_bucket_rate_limiter.py
Modulo promosso in produzione da HyperSpace R&D Sovereign Lab.
Prototipo sorgente: proto_tokenbucketratelimiter_1793019924.py
Data promozione: 2026-10-28T10:17:49+00:00
Autore: antigravity_sovereign

Implementa un rate limiter thread-safe e asincrono basato sull'algoritmo Token Bucket
per distribuire e controllare i carichi di inferenza (MoE, batch notturni, dev loop)
evitando picchi di saturazione VRAM o surriscaldamento GPU.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Dict


class TokenBucketRateLimiter:
    """Token bucket concorrente per il controllo del throughput di inferenza GPU/MoE."""

    _registry: Dict[str, "TokenBucketRateLimiter"] = {}
    _registry_lock = threading.Lock()

    def __init__(self, capacity: int, refill_rate: float, name: str = "default"):
        """
        :param capacity: capacità massima del bucket (dimensione massima del burst)
        :param refill_rate: token aggiunti al secondo
        :param name: etichetta o identificativo del dispositivo / modello
        """
        self.capacity = max(1, capacity)
        self.tokens = float(capacity)
        self.refill_rate = max(0.1, refill_rate)
        self.name = name
        self._lock = threading.Lock()
        self._last_refill = time.monotonic()

    @classmethod
    def for_device(
        cls,
        name: str,
        capacity: int = 4096,
        refill_rate: float = 512.0,
    ) -> "TokenBucketRateLimiter":
        """Recupera o istanzia un rate limiter dedicato a un dispositivo/nodo."""
        with cls._registry_lock:
            if name not in cls._registry:
                cls._registry[name] = cls(capacity=capacity, refill_rate=refill_rate, name=name)
            return cls._registry[name]

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed > 0:
            added = elapsed * self.refill_rate
            self.tokens = min(float(self.capacity), self.tokens + added)
            self._last_refill = now

    def acquire(self, tokens: int = 1) -> bool:
        """Tenta di consumare `tokens`; restituisce True se disponibili, False altrimenti."""
        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def wait_and_acquire(self, tokens: int = 1, timeout: float = 10.0) -> bool:
        """Attesa bloccante (con backoff) per ottenere i token richiesti entro un timeout."""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            if self.acquire(tokens):
                return True
            time.sleep(0.05)
        return False

    async def acquire_async(self, tokens: int = 1, timeout: float = 10.0) -> bool:
        """Attesa non bloccante in event loop asincrono per ottenere i token richiesti."""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            if self.acquire(tokens):
                return True
            await asyncio.sleep(0.05)
        return False

    def release(self, tokens: int):
        """Restituisce token al bucket (es. al termine di un task leggero o abortito)."""
        with self._lock:
            self._refill()
            self.tokens = min(float(self.capacity), self.tokens + tokens)

    def available(self) -> int:
        """Quantità attuale di token disponibili nel bucket."""
        with self._lock:
            self._refill()
            return int(self.tokens)

    def status(self) -> Dict[str, Any]:
        with self._lock:
            self._refill()
            return {
                "name": self.name,
                "available_tokens": int(self.tokens),
                "capacity": self.capacity,
                "refill_rate": self.refill_rate,
                "utilization_pct": round((1.0 - (self.tokens / self.capacity)) * 100, 1),
            }
