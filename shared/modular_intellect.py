#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# shared/modular_intellect.py
# Modulo promosso in produzione da HyperSpace R&D Sovereign Lab
# Prototipo sorgente: proto_modular_intellect_1793002957.py
# Data promozione: 2026-10-26T11:51:47.401255+00:00
# Autore: antigravity_sovereign

from typing import List, Dict, Optional, Any, Set
from collections import deque


class SovereignModularIntellect:
    """
    Architettura della Memoria ModularIntellect per HyperSpace AGI.
    Implementa una memoria tri‑modale (documenti, interazioni, note),
    note ricorsive tramite riferimenti e navigazione a grafo con
    un auditor di allineamento deontologico.
    """

    def __init__(self) -> None:
        # Dizionario: id -> esperienza
        self.experiences: Dict[int, Dict[str, Any]] = {}
        # ID progressivo per le nuove esperienze
        self.next_id: int = 0
        # Log delle azioni per l'audit (allineamento e operazioni)
        self.audit_log: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # 1. Memorizzazione dell'esperienza (Tri‑Modale + Auditor)
    # -------------------------------------------------------------------------
    def store_experience(
        self,
        kind: str,
        content: Any,
        refs: Optional[List[int]] = None
    ) -> int:
        """
        Salva un'esperienza nella memoria tri‑modale.

        Args:
            kind: Uno tra 'document', 'interaction', 'note'.
            content: Il contenuto (testo, dati strutturati, ecc.).
            refs: Lista opzionale di ID che fanno riferimento ad altre esperienze
                  (usata per note ricorsive e collegamenti).

        Returns:
            L'identificatore univoco dell'esperienza appena creata.
        """
        # Validazione del tipo di esperienza
        if kind not in ("document", "interaction", "note"):
            raise ValueError(f"Kind sconosciuto: {kind!r}")

        # Normalizzazione dei riferimenti
        refs = refs if refs is not None else []

        # Costruzione del record dell'esperienza
        experience: Dict[str, Any] = {
            "id": self.next_id,
            "kind": kind,
            "content": content,
            "refs": list(refs),
            "parent_id": None,   # per PART_OF
            "next_id": None,    # per CONTINUES_TO
            "timestamp": self.next_id,  # uso semplice: ordine di inserimento
        }

        # --- Alignment Auditor (controllo deontologico) ---
        aligned = self._alignment_check(experience)
        violation = not aligned

        # Registrazione nell'audit log
        entry = {
            "action": "store_experience",
            "id": experience["id"],
            "kind": kind,
            "aligned": aligned,
            "violation": violation,
            "timestamp": self.next_id,
        }
        self.audit_log.append(entry)

        # Salvataggio effettivo
        self.experiences[self.next_id] = experience
        self.next_id += 1
        return experience["id"]

    # -------------------------------------------------------------------------
    # 2. Navigazione a grafo (GraphDB Traversal)
    # -------------------------------------------------------------------------
    def traverse_graph_context(self, query: str, max_hops: int) -> List[Dict[str, Any]]:
        """
        Esplora il grafo delle esperienze a partire da quelle che contengono
        la stringa *query* nel contenuto.

        Args:
            query: Termine di ricerca (case‑insensitive).
            max_hops: Numero massimo di salti (livelli) da percorrere.

        Returns:
            Lista delle esperienze raggiunte, in ordine di scoperta BFS.
        """
        # Ricerca dei nodi di partenza
        query_lower = query.lower()
        start_nodes = [
            exp["id"]
            for exp in self.experiences.values()
            if query_lower in str(exp.get("content", "")).lower()
        ]

        if not start_nodes:
            return []

        # BFS con limite di profondità
        visited: Set[int] = set()
        result: List[Dict[str, Any]] = []
        queue: deque = deque()

        for nid in start_nodes:
            queue.append((nid, 0))

        while queue:
            node_id, depth = queue.popleft()
            if node_id in visited:
                continue
            if depth > max_hops:
                continue

            visited.add(node_id)
            result.append(self.experiences[node_id])

            # Determinazione dei vicini: parent_id, next_id, e refs
            exp = self.experiences[node_id]
            neighbors: List[int] = []

            parent = exp.get("parent_id")
            if parent is not None:
                neighbors.append(parent)

            nxt = exp.get("next_id")
            if nxt is not None:
                neighbors.append(nxt)

            for ref in exp.get("refs", []):
                neighbors.append(ref)

            # Accodamento dei vicini non ancora visitati
            for nb in neighbors:
                if nb not in visited:
                    queue.append((nb, depth + 1))

        return result

    # -------------------------------------------------------------------------
    # 3. Auditor di allineamento (deontologico/constituzionale)
    # -------------------------------------------------------------------------
    def _alignment_check(self, exp: Dict[str, Any]) -> bool:
        """
        Verifica che l'esperienza rispetti le regole minimali di allineamento.

        - note: devono citare almeno una referenza.
        - interaction: devono contenere contenuto testuale non vuoto.
        - document: devono avere almeno un legame strutturale (parent_id o next_id).

        Returns:
            True se l'esperienza è allineata, False altrimenti.
        """
        kind = exp["kind"]

        if kind == "note":
            # Le note devono referenziare altre note
            return len(exp.get("refs", [])) > 0

        if kind == "interaction":
            # L'interazione deve avere contenuto testuale
            content = exp.get("content")
            return isinstance(content, str) and len(content.strip()) > 0

        if kind == "document":
            # Un documento deve appartenere a un contesto (PART_OF o CONTINUES_TO)
            return exp.get("parent_id") is not None or exp.get("next_id") is not None

        # Per tipi sconosciuti accettiamo
        return True

    # -------------------------------------------------------------------------
    # Metodi ausiliari (non richiesti ma utili per estensione)
    # -------------------------------------------------------------------------
    def create_recursive_note(self, parent_note_id: int, content: Any) -> int:
        """
        Crea una nota che fa riferimento a una nota esistente (recursione).
        Simula la capacità di generare pensieri complessi tramite note annidate.
        """
        if parent_note_id not in self.experiences:
            raise KeyError(f"Nota padre non trovata: {parent_note_id}")

        refs = [parent_note_id]
        new_id = self.store_experience(kind="note", content=content, refs=refs)
        return new_id

    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Restituisce il log delle azioni e degli allineamenti."""
        return list(self.audit_log)
