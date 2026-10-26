#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# shared/semantic_memory_decay.py
# Modulo promosso in produzione da HyperSpace R&D Sovereign Lab
# Prototipo sorgente: proto_semanticmemorydecaycontroller_1793010783.py
# Data promozione: 2026-10-26T11:52:13.515873+00:00
# Autore: antigravity_sovereign

import math

class SemanticMemoryDecayController:
    def __init__(self, base: float, alpha: float, beta: float):
        self.base = base
        self.alpha = alpha
        self.beta = beta
        self.salience: dict[str, float] = {}
        self.recall_freq: dict[str, int] = {}

    def update_salience(self, item_id: str, value: float) -> None:
        self.salience[item_id] = value

    def record_recall(self, item_id: str) -> None:
        self.recall_freq[item_id] = self.recall_freq.get(item_id, 0) + 1

    def get_decay_rate(self, item_id: str) -> float:
        sal = self.salience.get(item_id, 0.0)
        rec = self.recall_freq.get(item_id, 0)
        return self.base * math.exp(-self.alpha * sal + self.beta * rec)
