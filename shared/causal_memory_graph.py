#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# shared/causal_memory_graph.py
# Modulo promosso in produzione da HyperSpace R&D Sovereign Lab
# Prototipo sorgente: proto_symbolic_causal_mesh_1792927875.py
# Data promozione: 2026-10-26T08:36:40.810529+00:00
# Autore: antigravity_sovereign

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class CausalEdge:
    cause_id: str
    effect_id: str
    weight: float
    created_at: float
    agent_id: Optional[str] = None

    def __getitem__(self, index: int) -> Any:
        if index == 0:
            return self.cause_id
        elif index == 1:
            return self.weight
        elif index == 2:
            return self.effect_id
        raise IndexError("CausalEdge index out of range")


class CausalMemoryGraph:
    """
    Integra una memoria episodica basata su SQLite WAL con FTS5 di Hermes
    con un grafo causale distribuito tra agenti eterogenei dello swarm mesh.
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        fts5_table: str = "hermes_events_fts",
        storage_path: Optional[Path | str] = None,
    ) -> None:
        self.storage_path = Path(storage_path) if storage_path else None
        self.fts5_table: str = fts5_table

        # Storage in memoria compatibile
        self._forward: Dict[str, List[Tuple[str, float]]] = {}
        self._reverse: Dict[str, List[Tuple[str, float]]] = {}
        self._episodic_memory: Dict[str, Dict[str, Any]] = {}

        # Connessione SQLite per query FTS5 e persistenza WAL
        self.db_path: str = str(db_path) if db_path else ":memory:"
        self.conn: sqlite3.Connection = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
        )
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

        if self.storage_path and self.storage_path.exists():
            self.load()

    def _init_schema(self) -> None:
        self.conn.execute("PRAGMA journal_mode = WAL")

        self.conn.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS {self.fts5_table} USING fts5(
                event_text,
                tokenize = 'porter unicode61'
            )
            """
        )

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS causal_edges (
                id TEXT PRIMARY KEY,
                cause_id TEXT NOT NULL,
                effect_id TEXT NOT NULL,
                weight REAL NOT NULL,
                created_at REAL NOT NULL,
                agent_id TEXT
            )
            """
        )

        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_causal_edges_effect ON causal_edges(effect_id)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_causal_edges_cause ON causal_edges(cause_id)"
        )

        self.conn.commit()

    def record_event(
        self,
        cause_id: str,
        effect_id: str,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Registra un evento causale nello swarm mesh.
        """
        event_id: str = str(uuid.uuid4())
        created_at: float = time.time()
        agent_id: Optional[str] = metadata.get("agent_id") if metadata else None

        # 1. SQLite & FTS5
        self.conn.execute(
            """
            INSERT INTO causal_edges (
                id,
                cause_id,
                effect_id,
                weight,
                created_at,
                agent_id
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, str(cause_id), str(effect_id), float(weight), created_at, agent_id),
        )

        event_text: str = f"cause={cause_id};effect={effect_id};weight={weight}"
        fts_rowid: int = int(time.time() * 1_000_000) + int(uuid.uuid4().int % 1_000_000)
        self.conn.execute(
            f"INSERT INTO {self.fts5_table}(rowid, event_text) VALUES (?, ?)",
            (fts_rowid, event_text),
        )
        self.conn.commit()

        # 2. In-memory graph structures
        record = {
            "event_id": event_id,
            "cause_id": str(cause_id),
            "effect_id": str(effect_id),
            "weight": float(weight),
            "timestamp": created_at,
            "metadata": metadata or {},
        }
        self._episodic_memory[event_id] = record

        f_list = self._forward.setdefault(str(cause_id), [])
        if not any(target == effect_id for target, _ in f_list):
            f_list.append((str(effect_id), float(weight)))

        r_list = self._reverse.setdefault(str(effect_id), [])
        if not any(c == cause_id for c, _ in r_list):
            r_list.append((str(cause_id), float(weight)))

        if self.storage_path:
            self.save()

        return event_id

    def trace_lineage(self, effect_id: str, max_depth: int = 10) -> List[CausalEdge]:
        """
        Risale lungo la genesi causale dell'effetto partendo dall'effetto.
        Restituisce una lista di CausalEdge (che supportano anche indicizzazione tupla c[0], c[1]).
        """
        edges: List[CausalEdge] = []
        visited: Set[str] = set()
        queue: List[Tuple[str, int]] = [(effect_id, 0)]

        while queue:
            current_id, depth = queue.pop(0)

            if depth > max_depth or current_id in visited:
                continue

            visited.add(current_id)

            rows = self.conn.execute(
                """
                SELECT cause_id, effect_id, weight, created_at, agent_id
                FROM causal_edges
                WHERE effect_id = ?
                """,
                (current_id,),
            ).fetchall()

            for row in rows:
                edge = CausalEdge(
                    cause_id=row["cause_id"],
                    effect_id=row["effect_id"],
                    weight=row["weight"],
                    created_at=row["created_at"],
                    agent_id=row["agent_id"],
                )
                edges.append(edge)
                queue.append((edge.cause_id, depth + 1))

        return edges

    def trace_detailed_lineage(self, effect_id: str) -> List[Dict[str, Any]]:
        """
        Traccia la genealogia causale completa arricchita con record di memoria episodica.
        """
        lineage_nodes = self.trace_lineage(effect_id)
        cause_ids = {c[0] for c in lineage_nodes}

        events = []
        for ev in self._episodic_memory.values():
            if ev.get("cause_id") in cause_ids or ev.get("effect_id") == effect_id:
                events.append(ev)

        events.sort(key=lambda x: str(x.get("timestamp", "")))
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
        return {
            "forward": self._forward,
            "reverse": self._reverse,
            "episodic_memory": self._episodic_memory,
        }

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

    def save(self, path: Optional[Path | str] = None) -> None:
        target = Path(path) if path else self.storage_path
        if not target:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    def load(self, path: Optional[Path | str] = None) -> None:
        target = Path(path) if path else self.storage_path
        if not target or not target.exists():
            return
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._forward = {k: [tuple(x) for x in v] for k, v in data.get("forward", {}).items()}
            self._reverse = {k: [tuple(x) for x in v] for k, v in data.get("reverse", {}).items()}
            self._episodic_memory = data.get("episodic_memory", {})
            for ev in self._episodic_memory.values():
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO causal_edges (id, cause_id, effect_id, weight, created_at, agent_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (ev.get("event_id"), ev.get("cause_id"), ev.get("effect_id"), ev.get("weight", 1.0), time.time(), None)
                )
            self.conn.commit()
        except Exception:
            pass

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> CausalMemoryGraph:
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()
