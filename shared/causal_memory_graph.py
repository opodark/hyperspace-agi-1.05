#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
shared/causal_memory_graph.py — Grafo di Memoria Causale per HyperSpace AGI Swarm

Prototipo promosso: proto_symbolic_causal_mesh_1792924003.py
Modello sintetizzatore: hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M (ASUS V16)

Unisce la memoria episodica con un grafo di causalità tra agenti eterogenei:
- Inserimento eventi causali (cause -> effect con peso)
- Tracciamento della genealogia/lineage causale (trace_lineage con DFS ricorsiva)
- Integrazione con la memoria di Hermes FTS5 e vector clocks
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class CausalMemoryGraph:
    """
    Unisce la memoria episodica con un grafo di causalità tra agenti eterogenei.
    Ogni evento è identificato da una causa e un effetto, collegati da un peso
    che indica l'influenza o la forza probabilistica.
    """

    def __init__(self, storage_path: Optional[Path | str] = None) -> None:
        self.storage_path = Path(storage_path) if storage_path else None
        # Adiacenza in avanti: cause -> list of (effect, weight)
        self._forward: Dict[str, List[Tuple[str, float]]] = {}
        # Adiacenza all'indietro: effect -> list of (cause, weight)
        self._reverse: Dict[str, List[Tuple[str, float]]] = {}
        # Memoria episodica: event_id -> record
        self._episodic_memory: Dict[str, Dict[str, Any]] = {}

        if self.storage_path and self.storage_path.exists():
            self.load()

    def record_event(
        self,
        cause_id: str,
        effect_id: str,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Registra un evento causale.

        Args:
            cause_id: ID dell'agente, paper o evento che ha generato la causa.
            effect_id: ID del risultato, prototipo o modulo (effetto).
            weight: Peso associato alla relazione causale (es. forza, confidenza).
            metadata: Informazioni opzionali associate all'evento.

        Returns:
            event_id univoco generato.
        """
        event_id = str(uuid.uuid4())
        ts = datetime.now(timezone.utc).isoformat()

        record = {
            "event_id": event_id,
            "cause_id": str(cause_id),
            "effect_id": str(effect_id),
            "weight": float(weight),
            "timestamp": ts,
            "metadata": metadata or {},
        }
        self._episodic_memory[event_id] = record

        # Aggiorna il grafo in avanti (evita duplicati identici)
        f_list = self._forward.setdefault(cause_id, [])
        if not any(target == effect_id for target, _ in f_list):
            f_list.append((effect_id, weight))

        # Aggiorna il grafo inverso per facilitare il tracing causale a ritroso
        r_list = self._reverse.setdefault(effect_id, [])
        if not any(c == cause_id for c, _ in r_list):
            r_list.append((cause_id, weight))

        if self.storage_path:
            self.save()

        return event_id

    def trace_lineage(self, effect_id: str) -> List[Tuple[str, float]]:
        """
        Traccia la genealogia causale di un effetto.

        Restituisce una lista di tuple (cause_id, weight) che rappresentano
        tutte le cause dirette e indirette che hanno portato a questo effetto.

        Args:
            effect_id: ID dell'effetto la cui lineage si vuole esplorare.

        Returns:
            Lista di tuple (cause_id, weight).
        """
        lineage: List[Tuple[str, float]] = []
        visited: Set[str] = set()

        def dfs(node: str) -> None:
            if node in visited:
                return
            visited.add(node)
            for cause, weight in self._reverse.get(node, []):
                lineage.append((cause, weight))
                dfs(cause)

        dfs(effect_id)
        return lineage

    def trace_detailed_lineage(self, effect_id: str) -> List[Dict[str, Any]]:
        """
        Traccia la genealogia causale completa arricchita con record di memoria episodica.
        """
        lineage_nodes = self.trace_lineage(effect_id)
        cause_ids = {c for c, _ in lineage_nodes}

        events = []
        for ev in self._episodic_memory.values():
            if ev.get("cause_id") in cause_ids or ev.get("effect_id") == effect_id:
                events.append(ev)

        # Ordina per timestamp crescente
        events.sort(key=lambda x: x.get("timestamp", ""))
        return events

    def get_forward_consequences(self, cause_id: str) -> List[Tuple[str, float]]:
        """Restituisce le conseguenze dirette derivanti da una causa."""
        return list(self._forward.get(cause_id, []))

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Recupera un record di memoria episodica per ID."""
        return self._episodic_memory.get(event_id)

    def total_events(self) -> int:
        return len(self._episodic_memory)

    def to_dict(self) -> Dict[str, Any]:
        """Serializza lo stato dell'intero grafo causale."""
        return {
            "forward": self._forward,
            "reverse": self._reverse,
            "episodic_memory": self._episodic_memory,
        }

    def save(self, path: Optional[Path | str] = None) -> None:
        """Salva il grafo su file JSON."""
        target = Path(path) if path else self.storage_path
        if not target:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def load(self, path: Optional[Path | str] = None) -> None:
        """Carica il grafo da file JSON."""
        target = Path(path) if path else self.storage_path
        if not target or not target.exists():
            return
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._forward = {k: [tuple(x) for x in v] for k, v in data.get("forward", {}).items()}
            self._reverse = {k: [tuple(x) for x in v] for k, v in data.get("reverse", {}).items()}
            self._episodic_memory = data.get("episodic_memory", {})
        except Exception:
            pass

    def export_graph_summary(self) -> Dict[str, Any]:
        """Restituisce statistiche e nodi salienti del grafo causale."""
        all_nodes = set(self._forward.keys()).union(self._reverse.keys())
        return {
            "total_nodes": len(all_nodes),
            "total_edges": sum(len(v) for v in self._forward.values()),
            "total_events": len(self._episodic_memory),
            "root_causes": [n for n in all_nodes if n not in self._reverse or not self._reverse[n]],
            "leaf_effects": [n for n in all_nodes if n not in self._forward or not self._forward[n]],
        }

