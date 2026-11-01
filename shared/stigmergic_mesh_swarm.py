#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# shared/stigmergic_mesh_swarm.py
# Modulo promosso in produzione da HyperSpace R&D Sovereign Lab
# Prototipo sorgente: proto_swarm_emergence_1792877797.py
# Data promozione: 2026-11-01T13:32:59.940211+00:00
# Autore: antigravity_sovereign

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


class VectorClock:
    """
    Orologio vettoriale distribuito per monitorare la precedenza causale
    e rilevare conflitti o divergenze tra nodi della rete sovrana (OMEN, ASUS, Mac).
    """

    def __init__(self, clock: Optional[Dict[str, int]] = None):
        self.clock: Dict[str, int] = dict(clock) if clock else {}

    def update(self, node_id: str) -> int:
        """Incrementa il contatore logico per il nodo specificato."""
        val = self.clock.get(node_id, 0) + 1
        self.clock[node_id] = val
        return val

    def compare(self, other: VectorClock) -> List[str]:
        """
        Restituisce i nodi in cui questo orologio è strettamente avanti rispetto ad `other`.
        """
        divergences: List[str] = []
        all_nodes = set(self.clock.keys()) | set(other.clock.keys())
        for node in all_nodes:
            self_val = self.clock.get(node, 0)
            other_val = other.clock.get(node, 0)
            if self_val > other_val or (node in self.clock and node not in other.clock):
                divergences.append(node)
        return divergences

    def to_dict(self) -> Dict[str, int]:
        return dict(self.clock)

    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> VectorClock:
        return cls(data)


class StigmergicMeshSwarm:
    """
    Sistema stigmergico a feromoni per la cooperazione autonoma di swarm.
    Permette ai nodi di depositare tracce di attenzione/risultati in memoria
    condivisa (Hermes), navigare i gradienti di priorità e raggiungere
    il consenso senza bottleneck centralizzati.
    """

    def __init__(self):
        # Mappa (signal_type, node_id) -> record segnale
        self.hermes: Dict[Tuple[str, str], Dict[str, Any]] = {}
        # Orologi vettoriali per nodo
        self.vector_clocks: Dict[str, VectorClock] = defaultdict(VectorClock)
        # Cronologia delle tracce
        self.pheromone_traces: Dict[str, Dict[str, List[Tuple[float, Any]]]] = defaultdict(lambda: defaultdict(list))

    def deposit_pheromone(
        self,
        signal_type: str,
        payload: Dict[str, Any],
        decay_rate: float = 0.05,
        node_id: str = "local_node",
    ) -> Dict[str, Any]:
        """
        Deposita un segnale feromonico nel substrato stigmergico.
        """
        now = time.time()
        self.vector_clocks[node_id].update(node_id)
        current_clock = self.vector_clocks[node_id].to_dict()

        intensity = float(
            payload.get("importance")
            if "importance" in payload
            else payload.get("importanza", payload.get("intensity", 1.0))
        )
        record = {
            "timestamp": now,
            "signal_type": signal_type,
            "node_id": node_id,
            "payload": payload,
            "clock": current_clock,
            "decay": 0.0,
            "decay_rate": decay_rate,
            "intensity": intensity,
        }

        self.hermes[(signal_type, node_id)] = record
        self.pheromone_traces[signal_type][node_id].append((now, payload))

        # Applica decadimento fisiologico
        self.decay_pheromones(decay_rate=decay_rate * 0.1)
        return record

    def sense_gradient(
        self,
        signal_type: str,
        threshold: float = 0.1,
    ) -> List[Dict[str, Any]]:
        """
        Legge il gradiente di intensità feromonica nello spazio stigmergico.
        Restituisce i nodi attivi ordinati per intensità decrescente.
        """
        candidates = []
        for (st, nid), record in self.hermes.items():
            if st != signal_type:
                continue

            current_decay = record.get("decay", 0.0)
            net_strength = max(0.0, record["intensity"] * (1.0 - current_decay))
            if net_strength >= threshold:
                candidates.append({
                    "node_id": nid,
                    "strength": round(net_strength, 4),
                    "payload": record["payload"],
                    "clock": record["clock"],
                    "timestamp": record["timestamp"],
                })

        candidates.sort(key=lambda x: x["strength"], reverse=True)
        return candidates

    def compute_gradient_field(self, signal_type: str) -> Dict[str, Any]:
        """
        Calcola metriche descrittive del campo feromonico (media, varianza, hotspot).
        """
        signals = self.sense_gradient(signal_type, threshold=0.0)
        if not signals:
            return {
                "signal_type": signal_type,
                "average_strength": 0.0,
                "variance": 0.0,
                "hotspot_node": None,
                "active_signals_count": 0,
                "signals": [],
            }

        strengths = [s["strength"] for s in signals]
        avg = sum(strengths) / len(strengths)
        variance = sum((s - avg) ** 2 for s in strengths) / len(strengths) if len(strengths) > 1 else 0.0
        hotspot = signals[0]["node_id"]

        return {
            "signal_type": signal_type,
            "average_strength": round(avg, 4),
            "variance": round(variance, 4),
            "hotspot_node": hotspot,
            "active_signals_count": len(signals),
            "signals": signals,
        }

    def decay_pheromones(self, decay_rate: float = 0.05) -> int:
        """
        Applica il decadimento a tutti i feromoni attivi.
        Elimina le tracce la cui evaporazione ha raggiunto il 100%.
        """
        evaporated_keys = []
        for key, signal_data in list(self.hermes.items()):
            current_decay = signal_data.get("decay", 0.0)
            step_rate = signal_data.get("decay_rate", decay_rate)
            new_decay = current_decay + step_rate
            signal_data["decay"] = new_decay
            if new_decay >= 1.0:
                evaporated_keys.append(key)

        for key in evaporated_keys:
            self.hermes.pop(key, None)

        return len(evaporated_keys)

    def consensus_converged(
        self,
        signal_type: Optional[str] = None,
        threshold: float = 0.9,
    ) -> bool:
        """
        Verifica se i nodi attivi sono causalmente allineati rispetto alla soglia.
        """
        if not self.vector_clocks:
            return True

        nodes = list(self.vector_clocks.keys())
        if len(nodes) <= 1:
            return True

        clock_differences = set()
        for i, node1 in enumerate(nodes):
            for j, node2 in enumerate(nodes):
                if i != j:
                    diffs = self.vector_clocks[node1].compare(self.vector_clocks[node2])
                    clock_differences.update(diffs)

        ratio = 1.0 - (len(clock_differences) / max(1, len(nodes)))
        return ratio >= threshold


if __name__ == "__main__":
    swarm = StigmergicMeshSwarm()
    swarm.deposit_pheromone("attenzione", {"importanza": 0.95, "target": "OMEN-16"}, decay_rate=0.05, node_id="asus-v16")
    swarm.deposit_pheromone("attenzione", {"importanza": 0.80, "target": "MacBook"}, decay_rate=0.05, node_id="omen-16")
    print("Gradienti rilevati:", swarm.sense_gradient("attenzione"))
    print("Consenso raggiunto:", swarm.consensus_converged())
