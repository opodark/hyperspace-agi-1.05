#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
shared/inference_latency_pid.py
Modulo promosso in produzione da HyperSpace R&D Sovereign Lab.
Ispirato allo studio del ciclo notturno OMEN 'Adaptive Inference Latency PID Controller'.
Data: 2026-10-28T10:18:00+00:00
Autore: antigravity_sovereign

Implementa un controller PID (Proportional-Integral-Derivative) per la regolazione
adattiva della latenza di inferenza dei modelli LLM/VLM distribuiti nella mesh.
Previene timeout a cascata e saturazione termica modulando dinamicamente il token budget
o il batch size in base alle oscillazioni dei tempi di risposta reali.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional


class InferenceLatencyPIDController:
    """Controller PID per mantenere la latenza di generazione LLM vicina a un target prestabilito."""

    def __init__(
        self,
        target_latency_s: float = 30.0,
        kp: float = 0.5,
        ki: float = 0.05,
        kd: float = 0.1,
        min_output: float = 0.2,
        max_output: float = 2.0,
        integral_limit: float = 10.0,
    ):
        """
        :param target_latency_s: tempo obiettivo desiderato per richiesta (in secondi)
        :param kp: guadagno proporzionale
        :param ki: guadagno integrale
        :param kd: guadagno derivativo
        :param min_output: fattore minimo di scala applicabile (es. 0.2 = -80% token)
        :param max_output: fattore massimo di scala applicabile (es. 2.0 = +100% token)
        :param integral_limit: limite anti-windup per l'accumulo dell'integrale
        """
        self.target_latency_s = float(target_latency_s)
        self.kp = float(kp)
        self.ki = float(ki)
        self.kd = float(kd)
        self.min_output = float(min_output)
        self.max_output = float(max_output)
        self.integral_limit = float(integral_limit)

        self.integral = 0.0
        self.last_error = 0.0
        self.last_time: Optional[float] = None
        self.last_adjustment = 1.0

    def compute(self, measured_latency_s: float, current_time: Optional[float] = None) -> float:
        """
        Calcola il fattore di scala correttivo (1.0 = nominale, < 1.0 = riduci carico, > 1.0 = aumenta carico).
        Se la latenza misurata è maggiore del target, l'errore è negativo e il fattore scende per alleggerire.
        """
        now = current_time if current_time is not None else time.monotonic()
        if self.last_time is None:
            dt = 1.0
        else:
            dt = max(0.001, now - self.last_time)
        self.last_time = now

        # Errore: positivo se siamo più veloci del target (possiamo espandere),
        # negativo se stiamo impiegando troppo tempo (dobbiamo contrarre).
        error = self.target_latency_s - measured_latency_s

        # Proporzionale
        p_term = self.kp * error

        # Integrale con anti-windup
        self.integral += error * dt
        self.integral = max(-self.integral_limit, min(self.integral_limit, self.integral))
        i_term = self.ki * self.integral

        # Derivativo
        d_term = self.kd * ((error - self.last_error) / dt)
        self.last_error = error

        # Control output normalizzato attorno a 1.0 (nominale)
        raw_output = 1.0 + (p_term + i_term + d_term) / max(1.0, self.target_latency_s)
        adjustment = max(self.min_output, min(self.max_output, raw_output))
        self.last_adjustment = adjustment
        return adjustment

    def adjust_token_limit(
        self,
        base_tokens: int,
        measured_latency_s: float,
        min_tokens: int = 128,
        max_tokens: int = 4096,
        current_time: Optional[float] = None,
    ) -> int:
        """Applica il fattore PID a una quota nominale di token, garantendo i limiti min/max."""
        factor = self.compute(measured_latency_s, current_time=current_time)
        adjusted = int(round(base_tokens * factor))
        return max(min_tokens, min(max_tokens, adjusted))

    def reset(self):
        """Azzera la memoria dell'integrale e dell'errore."""
        self.integral = 0.0
        self.last_error = 0.0
        self.last_time = None
        self.last_adjustment = 1.0

    def status(self) -> Dict[str, Any]:
        return {
            "target_latency_s": self.target_latency_s,
            "kp": self.kp,
            "ki": self.ki,
            "kd": self.kd,
            "last_error": round(self.last_error, 2),
            "integral": round(self.integral, 2),
            "last_adjustment": round(self.last_adjustment, 3),
        }
