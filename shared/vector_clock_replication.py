#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# shared/vector_clock_replication.py
# Modulo promosso in produzione da HyperSpace R&D Sovereign Lab
# Prototipo sorgente: proto_vectorclockstatereplication_1793010377.py
# Data promozione: 2026-10-31T13:41:20.669393+00:00
# Autore: antigravity_sovereign

from typing import Dict, Any, Optional

class VectorClockStateReplication:
    """Motorino di replica con Vector Clock per nodi eterogenei."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.vector_clock: Dict[str, int] = {}
        self.state: Dict[str, Any] = {}

    def _increment(self) -> None:
        self.vector_clock[self.node_id] = self.vector_clock.get(self.node_id, 0) + 1

    def apply(self, payload: Dict[str, Any]) -> None:
        """Applica una nuova versione dello stato."""
        self.state.update(payload)
        self._increment()

    def merge(self, other: "VectorClockStateReplication") -> None:
        """Fonde i vector clock di due nodi."""
        for node, ts in other.vector_clock.items():
            self.vector_clock[node] = max(self.vector_clock.get(node, 0), ts)

    def get_state(self) -> Dict[str, Any]:
        """Restituisce una copia dello stato corrente."""
        return self.state.copy()

    def get_vector_clock(self) -> Dict[str, int]:
        """Restituisce il vector clock aggiornato."""
        return self.vector_clock.copy()
