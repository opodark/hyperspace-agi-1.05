#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
shared/distributed_rollback_journal.py
Modulo promosso in produzione da HyperSpace R&D Sovereign Lab.
Prototipo sorgente: proto_distributedrollbackjournal_1793021129.py
Data promozione: 2026-10-28T12:36:29+00:00
Autore: antigravity_sovereign

Giornale transazionale atomico distribuito per la mesh:
- Gestione transazioni atomiche multi-nodo con quorum
- Undo log con esecuzione automatica delle azioni inverse in caso di fallimento o partizione
- Supporto a registrazione di checkpoint locali e rollback istantaneo
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional


class Node:
    """Rappresentazione di un nodo partecipante alla transazione distribuita."""
    def __init__(self, node_id: str, endpoint: str = ""):
        self.node_id = str(node_id)
        self.endpoint = endpoint
        self.alive = True

    def __repr__(self) -> str:
        return f"Node({self.node_id})"


class DistributedRollbackJournal:
    """Gestisce transazioni atomiche cross-nodo con rollback automatico."""

    def __init__(self, nodes: List[Node], quorum: Optional[int] = None):
        self.nodes = list(nodes)
        self.quorum = quorum if quorum is not None else max(1, (len(self.nodes) // 2) + 1)
        self.log: Dict[str, dict] = {}
        self.active: Dict[str, bool] = {}

    def begin(self, description: str = "") -> str:
        """Avvia una nuova transazione distribuita e ne restituisce l'ID univoco."""
        txn_id = f"txn_{int(time.time()*1000)}_{len(self.log) + 1}"
        self.log[txn_id] = {
            "state": "pending",
            "description": description,
            "undo": [],
            "votes": set(),
            "created_at": time.time(),
        }
        self.active[txn_id] = True
        return txn_id

    def record_undo(self, txn_id: str, undo_action: Callable[[], Any], description: str = "") -> None:
        """Registra un'azione inversa da eseguire obbligatoriamente se la transazione abortisce."""
        if txn_id not in self.log or not self.active.get(txn_id):
            raise ValueError(f"Transazione '{txn_id}' non valida o già chiusa.")
        self.log[txn_id]["undo"].append({
            "action": undo_action,
            "description": description,
        })

    def vote(self, txn_id: str, node_id: str) -> bool:
        """Registra il voto di conferma di un nodo per il raggiungimento del quorum."""
        if txn_id not in self.log or not self.active.get(txn_id):
            raise ValueError(f"Transazione '{txn_id}' non attiva.")
        self.log[txn_id]["votes"].add(node_id)
        return len(self.log[txn_id]["votes"]) >= self.quorum

    def commit(self, txn_id: str) -> bool:
        """Conferma la transazione se il quorum dei nodi è stato raggiunto."""
        if txn_id not in self.log:
            raise ValueError(f"Transazione '{txn_id}' inesistente.")
        entry = self.log[txn_id]
        if len(entry["votes"]) < self.quorum and len(self.nodes) > 1:
            self.abort(txn_id)
            return False
        entry["state"] = "committed"
        self.active[txn_id] = False
        return True

    def abort(self, txn_id: str) -> List[str]:
        """Esegue il rollback atomico di tutte le azioni inverse registrate in ordine LIFO."""
        if txn_id not in self.log:
            raise ValueError(f"Transazione '{txn_id}' inesistente.")
        entry = self.log[txn_id]
        applied_rollbacks = []

        # Applica l'undo log in ordine inverso
        for item in reversed(entry.get("undo", [])):
            action = item.get("action")
            desc = item.get("description", "undo")
            if callable(action):
                try:
                    action()
                    applied_rollbacks.append(desc)
                except Exception as exc:
                    applied_rollbacks.append(f"{desc}:failed({exc})")

        entry["state"] = "aborted"
        self.active[txn_id] = False
        return applied_rollbacks

    def on_node_failure(self, failed_node_id: str) -> List[str]:
        """Fa fallire e scatta il rollback di tutte le transazioni aperte che dipendono da quel nodo."""
        aborted = []
        for txn_id, active in list(self.active.items()):
            if active:
                self.abort(txn_id)
                aborted.append(txn_id)
        return aborted

    def status(self) -> Dict[str, Any]:
        return {
            "total_transactions": len(self.log),
            "active_transactions": sum(1 for a in self.active.values() if a),
            "nodes_count": len(self.nodes),
            "quorum": self.quorum,
        }
