#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
shared/trimodal_memory_graph.py
Modulo promosso in produzione da HyperSpace R&D Sovereign Lab.
Prototipo sorgente: proto_trimodalmemorygraph_1793012372.py
Data promozione: 2026-10-28T12:36:29+00:00
Autore: antigravity_sovereign

Grafo di Memoria Trimodale unificato per HyperSpace:
- Chunks: frammenti di codice o documentazione tecnica
- Interactions: dialoghi tra agenti o utente-agente
- Notes: osservazioni ricorsive e riflessioni
- Fusione cross-modale e query unificate
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional


class TriModalMemoryGraph:
    CHUNK = "chunk"
    INTERACTION = "interaction"
    NOTE = "note"

    def __init__(self):
        self._chunks: Dict[str, dict] = {}
        self._interactions: Dict[str, dict] = {}
        self._notes: Dict[str, dict] = {}

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ---------- Chunk (Codice / Documenti) ----------
    def add_chunk(self, chunk_id: str, content: Any, metadata: Optional[dict] = None) -> dict:
        entry = {
            "type": self.CHUNK,
            "id": str(chunk_id),
            "content": content,
            "metadata": dict(metadata or {}),
            "created": self._now_iso(),
        }
        self._chunks[str(chunk_id)] = entry
        return entry

    def get_chunk(self, chunk_id: str) -> Optional[dict]:
        return self._chunks.get(str(chunk_id))

    # ---------- Interaction (Dialoghi / Eventi) ----------
    def add_interaction(
        self,
        interaction_id: str,
        sender: str,
        message: str,
        timestamp: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        entry = {
            "type": self.INTERACTION,
            "id": str(interaction_id),
            "sender": str(sender),
            "message": str(message),
            "timestamp": timestamp or self._now_iso(),
            "metadata": dict(metadata or {}),
        }
        self._interactions[str(interaction_id)] = entry
        return entry

    def get_interaction(self, interaction_id: str) -> Optional[dict]:
        return self._interactions.get(str(interaction_id))

    # ---------- Note (Riflessioni / Gerarchie) ----------
    def add_note(
        self,
        note_id: str,
        parent_note_id: Optional[str] = None,
        content: Any = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        entry = {
            "type": self.NOTE,
            "id": str(note_id),
            "parent": str(parent_note_id) if parent_note_id else None,
            "content": content,
            "metadata": dict(metadata or {}),
            "created": self._now_iso(),
        }
        self._notes[str(note_id)] = entry
        return entry

    def get_note(self, note_id: str) -> Optional[dict]:
        return self._notes.get(str(note_id))

    # ---------- Queries & Cross-modal Search ----------
    def all_chunks(self) -> List[dict]:
        return list(self._chunks.values())

    def all_interactions(self) -> List[dict]:
        return list(self._interactions.values())

    def all_notes(self) -> List[dict]:
        return list(self._notes.values())

    def search_all(self, keyword: str) -> List[dict]:
        """Cerca una parola chiave trasversalmente in tutte e tre le modalità cognitive."""
        kw = keyword.lower().strip()
        matches = []
        for c in self._chunks.values():
            if kw in str(c.get("content", "")).lower():
                matches.append(c)
        for i in self._interactions.values():
            if kw in str(i.get("message", "")).lower() or kw in str(i.get("sender", "")).lower():
                matches.append(i)
        for n in self._notes.values():
            if kw in str(n.get("content", "")).lower():
                matches.append(n)
        return matches

    # ---------- Fusion ----------
    def merge(self, other: "TriModalMemoryGraph") -> None:
        """Unisce lo stato di un altro grafo trimodale locale o remoto."""
        self._chunks.update(other._chunks)
        self._interactions.update(other._interactions)
        self._notes.update(other._notes)

    def stats(self) -> Dict[str, int]:
        return {
            "chunks_count": len(self._chunks),
            "interactions_count": len(self._interactions),
            "notes_count": len(self._notes),
            "total_nodes": len(self._chunks) + len(self._interactions) + len(self._notes),
        }
