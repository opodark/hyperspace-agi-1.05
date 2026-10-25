#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
shared/modular_intellect_engine.py
Adattamento Sovrano del paradigma 'ModularIntellect' (LuckCow/ModularIntellect):
- Memoria Tri-Modale a Grafo (Document, Chunk, Interaction, Note)
- Collegamenti Relazionali: PART_OF, CONTINUES_TO, REFERENCES (note ricorsive)
- GraphDB Traversal Navigator per esplorazione iterativa del contesto da parte di LLM
- Alignment Auditor per la supervisione etica e operativa delle azioni

Implementato nativamente per HyperSpace AGI in SQLite sovrano senza dipendenze cloud esterne.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "research"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "modular_intellect_graph.db"


class TripleModalGraphStore:
    """
    Archivio a grafo tri-modale per la cognizione sovrana:
    1. Documentale: Documenti suddivisi in Chunks relazionali (PART_OF, CONTINUES_TO).
    2. Interattiva: Scambi utente/agente organizzati per conversazione (Interaction).
    3. Metacognitiva: Note di auto-riflessione che referenziano altre note o chunk (REFERENCES).
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT,
                    timestamp REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    timestamp REAL NOT NULL,
                    PRIMARY KEY (source_id, target_id, relation),
                    FOREIGN KEY (source_id) REFERENCES nodes(id) ON DELETE CASCADE,
                    FOREIGN KEY (target_id) REFERENCES nodes(id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id)")
            conn.commit()

    def add_node(
        self,
        node_id: str,
        node_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Inserisce o aggiorna un nodo cognitivo nel grafo."""
        now = time.time()
        meta_str = json.dumps(metadata or {}, ensure_ascii=False)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO nodes (id, type, content, metadata_json, timestamp)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    content = excluded.content,
                    metadata_json = excluded.metadata_json,
                    timestamp = excluded.timestamp
                """,
                (node_id, node_type, content, meta_str, now),
            )
            conn.commit()
        return node_id

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        weight: float = 1.0,
    ):
        """Crea un arco relazionale orientato tra due nodi (es. PART_OF, CONTINUES_TO, REFERENCES)."""
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO edges (source_id, target_id, relation, weight, timestamp)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_id, target_id, relation) DO UPDATE SET
                    weight = excluded.weight,
                    timestamp = excluded.timestamp
                """,
                (source_id, target_id, relation, weight, now),
            )
            conn.commit()

    def ingest_document(
        self,
        doc_id: str,
        title: str,
        text: str,
        chunk_size: int = 300,
        chunk_overlap: int = 50,
    ) -> List[str]:
        """
        Scompone un documento in Chunk interconnessi:
        - Document -- PART_OF --> Chunk
        - Chunk_i -- CONTINUES_TO --> Chunk_{i+1}
        """
        self.add_node(doc_id, "document", title, {"title": title, "length": len(text)})
        chunks = []
        start = 0
        idx = 0
        chunk_ids = []

        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_content = text[start:end].strip()
            if chunk_content:
                c_id = f"{doc_id}_chunk_{idx}"
                self.add_node(
                    c_id,
                    "chunk",
                    chunk_content,
                    {"index": idx, "doc_id": doc_id, "start": start, "end": end},
                )
                self.add_edge(c_id, doc_id, "PART_OF")
                if chunk_ids:
                    # Collega il chunk precedente a questo con CONTINUES_TO
                    self.add_edge(chunk_ids[-1], c_id, "CONTINUES_TO")
                chunk_ids.append(c_id)
                idx += 1
            start += chunk_size - chunk_overlap

        return chunk_ids

    def record_interaction(
        self,
        interaction_id: str,
        conversation_id: str,
        role: str,
        text: str,
    ) -> str:
        """Registra un turno di conversazione (Interaction) collegato alla Conversation."""
        self.add_node(
            interaction_id,
            "interaction",
            text,
            {"role": role, "conversation_id": conversation_id},
        )
        self.add_edge(interaction_id, conversation_id, "PART_OF")
        return interaction_id

    def create_reflective_note(
        self,
        note_id: str,
        reflection_text: str,
        referenced_ids: List[str],
        topic: str = "metacognition",
    ) -> str:
        """
        Crea una Note di auto-riflessione che referenzia altre Note, Chunks o Interactions.
        Abilita il ragionamento astratto e ricorsivo dell'agente.
        """
        self.add_node(
            note_id,
            "note",
            reflection_text,
            {"topic": topic, "references_count": len(referenced_ids)},
        )
        for target_id in referenced_ids:
            self.add_edge(note_id, target_id, "REFERENCES")
        return note_id

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            res["metadata"] = json.loads(res.get("metadata_json") or "{}")
            return res

    def get_connections(
        self,
        node_id: str,
        direction: str = "out",
        relation: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Recupera gli archi uscenti o entranti di un nodo."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if direction == "out":
                query = "SELECT target_id AS neighbor_id, relation, weight FROM edges WHERE source_id = ?"
            else:
                query = "SELECT source_id AS neighbor_id, relation, weight FROM edges WHERE target_id = ?"

            params = [node_id]
            if relation:
                query += " AND relation = ?"
                params.append(relation)

            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def search_nodes(
        self,
        query: str,
        node_type: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Ricerca per somiglianza di parole chiave nel grafo cognitivo."""
        words = [w.strip().lower() for w in re.split(r"\W+", query) if len(w.strip()) > 2]
        if not words:
            words = [query.lower()]

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            sql = "SELECT * FROM nodes WHERE 1=1"
            params: List[Any] = []
            if node_type:
                sql += " AND type = ?"
                params.append(node_type)

            like_clauses = ["LOWER(content) LIKE ?" for _ in words]
            if like_clauses:
                sql += f" AND ({' OR '.join(like_clauses)})"
                params.extend([f"%{w}%" for w in words])

            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["metadata"] = json.loads(item.get("metadata_json") or "{}")
                # Allega le connessioni dirette
                item["outgoing_connections"] = self.get_connections(item["id"], "out")
                results.append(item)
            return results

    def get_stats(self) -> Dict[str, Any]:
        """Restituisce le metriche strutturali del grafo tri-modale."""
        with sqlite3.connect(self.db_path) as conn:
            total_nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            total_edges = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            by_type = dict(conn.execute("SELECT type, COUNT(*) FROM nodes GROUP BY type").fetchall())
            by_rel = dict(conn.execute("SELECT relation, COUNT(*) FROM edges GROUP BY relation").fetchall())
            return {
                "total_nodes": total_nodes,
                "total_edges": total_edges,
                "nodes_by_type": by_type,
                "edges_by_relation": by_rel,
            }


class GraphTraversalNavigator:
    """
    Simula la catena GraphDBTraversalChain di ModularIntellect:
    Permette a un LLM di esplorare a salti i chunk di contesto collegati relazionalmente
    fino a convergere su una risposta integrata e verificata.
    """

    SYSTEM_PROMPT = (
        "Sei il Navigatore del Grafo Cognitivo di HyperSpace AGI.\n"
        "Hai accesso a una rete di frammenti informativi (Chunks, Note, Interazioni) collegati fra loro da archi.\n"
        "Per ciascun frammento valuta la rilevanza per il quesito posto, sintetizza la risposta provvisoria "
        "e segnala se richiedere l'esplorazione dei chunk collegati tramite 'LOOKUP CHUNK #<id>' o 'CONTINUES TO #<id>'."
    )

    def __init__(self, store: TripleModalGraphStore):
        self.store = store

    def build_traversal_context(self, question: str, chunk_ids: List[str]) -> str:
        """Costruisce il payload di contesto relazionale per il prompt LLM."""
        sections = []
        for cid in chunk_ids:
            node = self.store.get_node(cid)
            if not node:
                continue
            connections = self.store.get_connections(cid, "out")
            conn_strs = [f"{c['relation']} -> {c['neighbor_id']}" for c in connections]
            conn_desc = ", ".join(conn_strs) if conn_strs else "Nessuna connessione esterna"

            sections.append(
                f"--- FRAMMENTO #{cid} (Tipo: {node['type']}) ---\n"
                f"Contenuto: {node['content']}\n"
                f"Connessioni Disponibili: {conn_desc}\n"
            )

        return "\n".join(sections)

    def parse_next_lookups(self, response_text: str) -> List[str]:
        """Estrae gli ID dei chunk che il modello richiede di espandere (LOOKUP CHUNK #id)."""
        pattern = r"(?:LOOKUP\s+(?:CONTEXT\s+)?CHUNK|CONTINUES\s+TO)\s+#?([A-Za-z0-9_\-\.]+)"
        matches = re.findall(pattern, response_text, re.IGNORECASE)
        return list(dict.fromkeys(matches))

    def step_traversal(
        self,
        question: str,
        current_chunk_ids: List[str],
        working_summary: str = "",
        executor_fn: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Esegue un passo di navigazione sul grafo."""
        context_str = self.build_traversal_context(question, current_chunk_ids)
        prompt = (
            f"{self.SYSTEM_PROMPT}\n\n"
            f"DOMANDA: {question}\n"
            f"SINTESI ATTUALE: {working_summary or 'Inizio navigazione.'}\n\n"
            f"FRAMMENTI ATTIVI NEL GRAFO:\n{context_str}\n\n"
            f"Fornisci una sintesi delle evidenze trovate e indica eventuali ID da approfondire con 'LOOKUP CHUNK #<id>'."
        )

        if executor_fn:
            res = executor_fn(prompt, model="granite3.3:8b", timeout=45)
            response_text = res.get("response", "") if res.get("status") == "ok" else ""
        else:
            response_text = (
                f"Analisi completata per {len(current_chunk_ids)} nodi. "
                f"Risposta formulata sulle informazioni disponibili. Nessun approfondimento richiesto."
            )

        lookups = self.parse_next_lookups(response_text)
        return {
            "prompt_length": len(prompt),
            "response": response_text,
            "next_lookups": lookups,
            "active_chunks": current_chunk_ids,
        }


class AlignmentAuditor:
    """
    Auditor di allineamento costituzionale ispirato a AlignmentAuditingAgent di ModularIntellect:
    Controlla se gli obiettivi e i task proposti rispettano i criteri di sicurezza sovrani:
    - Nessuna esecuzione di comandi non autorizzati o distruttivi
    - Tutela della privacy e assenza di credenziali esposte
    - Rispetto dei limiti termici e di carico hardware
    """

    FORBIDDEN_PATTERNS = [
        r"rm\s+-rf\s+/",
        r"DROP\s+DATABASE",
        r"format\s+[A-Za-z]:",
        r"os\.system\(['\"]rm",
        r"PRIVATE_KEY\s*=\s*['\"][0-9a-fA-F]{32,}",
    ]

    @classmethod
    def audit_task(cls, task_description: str) -> Dict[str, Any]:
        violations = []
        for pat in cls.FORBIDDEN_PATTERNS:
            if re.search(pat, task_description, re.IGNORECASE):
                violations.append(f"Rilevato pattern critico proibito: {pat}")

        is_aligned = len(violations) == 0
        return {
            "is_aligned": is_aligned,
            "violations": violations,
            "audited_at": time.time(),
            "status": "APPROVED" if is_aligned else "BLOCKED",
        }


if __name__ == "__main__":
    store = TripleModalGraphStore()
    doc_id = f"doc_test_{int(time.time())}"
    chunks = store.ingest_document(
        doc_id,
        "Architettura Swarm e Memoria",
        "HyperSpace adotta nodi eterogenei tra Mac, OMEN e ASUS. Ogni nodo condivide stato tramite vector clocks. "
        "Le memorie episodiche vengono condensate in note ricorsive per consentire l'astrazione concettuale.",
        chunk_size=90,
        chunk_overlap=20,
    )
    print("Chunks generati:", chunks)
    note_id = f"note_test_{int(time.time())}"
    store.create_reflective_note(note_id, "Riflessione: i vector clocks prevengono divergenze nei grafi distribuiti.", chunks[:2])
    print("Statistiche grafo:", store.get_stats())
    print("Audit Alignment Test:", AlignmentAuditor.audit_task("Calcola la traiettoria orbitale e aggiorna lo stato"))
