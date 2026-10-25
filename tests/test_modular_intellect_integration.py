#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
tests/test_modular_intellect_integration.py
Test suite per l'integrazione sovrana di ModularIntellect in HyperSpace:
- TripleModalGraphStore (Documenti, Chunks relazionali, Interazioni, Note di auto-riflessione ricorsive)
- GraphTraversalNavigator (parsing richieste di lookup `LOOKUP CHUNK #id`)
- AlignmentAuditor (blocco pattern distruttivi e approvazione task sicuri)
"""

import tempfile
from pathlib import Path
import unittest

from shared.modular_intellect_engine import (
    TripleModalGraphStore,
    GraphTraversalNavigator,
    AlignmentAuditor,
)


class TestModularIntellectIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_graph.db"
        self.store = TripleModalGraphStore(db_path=self.db_path)
        self.navigator = GraphTraversalNavigator(self.store)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_document_ingestion_and_relational_chunks(self):
        sample_doc = (
            "HyperSpace è un cluster distribuito di intelligenza artificiale. "
            "Il nodo Mac M5 funge da orchestratore delle missioni e del grafo. "
            "Il nodo HP OMEN 16 fornisce accelerazione GPU RTX 3070 per compiti pesanti di distillazione neurale."
        )
        chunk_ids = self.store.ingest_document("doc_overview", "Overview HyperSpace", sample_doc, chunk_size=80, chunk_overlap=15)
        self.assertGreaterEqual(len(chunk_ids), 2)

        # Verifica arco PART_OF verso il documento padre
        c0_conns = self.store.get_connections(chunk_ids[0], "out", relation="PART_OF")
        self.assertEqual(len(c0_conns), 1)
        self.assertEqual(c0_conns[0]["neighbor_id"], "doc_overview")

        # Verifica arco CONTINUES_TO verso il chunk successivo
        c0_cont = self.store.get_connections(chunk_ids[0], "out", relation="CONTINUES_TO")
        self.assertEqual(len(c0_cont), 1)
        self.assertEqual(c0_cont[0]["neighbor_id"], chunk_ids[1])

    def test_recursive_reflective_notes(self):
        # Inserimento di due chunk
        self.store.add_node("c1", "chunk", "Primo principio di coerenza ontologica.")
        self.store.add_node("c2", "chunk", "Secondo principio: allineamento dei vettori di stato.")

        # Creazione nota che referenzia i due chunk
        n1 = self.store.create_reflective_note("note_meta_1", "Sintesi: la coerenza ontologica richiede allineamento dei vettori.", ["c1", "c2"])
        refs_n1 = self.store.get_connections(n1, "out", relation="REFERENCES")
        self.assertEqual(len(refs_n1), 2)

        # Creazione meta-nota di secondo livello che referenzia la prima nota (ricorsione cognitiva)
        n2 = self.store.create_reflective_note("note_meta_2", "Meta-riflessione: validata stabilità dei vettori ontologici a lungo termine.", [n1])
        refs_n2 = self.store.get_connections(n2, "out", relation="REFERENCES")
        self.assertEqual(len(refs_n2), 1)
        self.assertEqual(refs_n2[0]["neighbor_id"], n1)

    def test_keyword_search_nodes(self):
        self.store.add_node("chunk_a", "chunk", "Meccanismo di attenzione e routing prioritario per nodi mesh.")
        self.store.add_node("chunk_b", "chunk", "Protocollo di autenticazione crittografica ECDSA.")

        results = self.store.search_nodes("attenzione routing", node_type="chunk")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "chunk_a")

    def test_graph_traversal_navigator_lookups_parsing(self):
        model_reply = (
            "Review dei frammenti completata.\n"
            "Chunk #doc_1_chunk_0 - Relevant - Descrive l'architettura base.\n"
            "LOOKUP CHUNK #doc_1_chunk_1\n"
            "CONTINUES TO #doc_1_chunk_2\n"
        )
        lookups = self.navigator.parse_next_lookups(model_reply)
        self.assertIn("doc_1_chunk_1", lookups)
        self.assertIn("doc_1_chunk_2", lookups)

    def test_alignment_auditor(self):
        # Task sicuro
        res_safe = AlignmentAuditor.audit_task("Sintetizza il documento e calcola le correlazioni logiche.")
        self.assertTrue(res_safe["is_aligned"])
        self.assertEqual(res_safe["status"], "APPROVED")

        # Task con comando distruttivo proibito
        res_harmful = AlignmentAuditor.audit_task("Esegui rm -rf / sulla directory principale per pulire la cache.")
        self.assertFalse(res_harmful["is_aligned"])
        self.assertEqual(res_harmful["status"], "BLOCKED")
        self.assertGreater(len(res_harmful["violations"]), 0)


if __name__ == "__main__":
    unittest.main()
