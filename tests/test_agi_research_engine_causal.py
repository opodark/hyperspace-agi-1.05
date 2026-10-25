#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
tests/test_agi_research_engine_causal.py
Verifica l'integrazione di CausalMemoryGraph con AGIResearchEngine:
- Tracciamento automatico di execute_study_cycle (ref -> infer -> proto)
- Promozione in produzione (proto -> prod)
- Tracciamento della lineage per componenti (trace_component_lineage)
- Sintesi markdown e statistiche grafo
"""

import tempfile
import unittest
from pathlib import Path

from shared.agi_research_engine import AGIResearchEngine


class TestAGIResearchEngineCausalIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.engine = AGIResearchEngine(data_dir=self.data_dir)
        self.engine.prototypes_dir = self.data_dir / "prototypes"
        self.engine.prototypes_dir.mkdir(parents=True, exist_ok=True)
        self.engine.deep_dives_log = self.data_dir / "agi_deep_dives.jsonl"
        self.engine.synthesis_md = self.data_dir / "AGI_SWARM_SYNTHESIS.md"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_execute_study_cycle_records_causal_event(self):
        # Esecuzione studio con mock interno (senza invio LLM remoto)
        record = self.engine.execute_study_cycle(pillar_id="aleksander_axioms")

        self.assertIn("causal_lineage", record)
        self.assertGreater(len(record["causal_lineage"]), 0)

        # Verifica che il grafo contenga i nodi ref e proto
        summary = self.engine.causal_graph.export_graph_summary()
        self.assertGreaterEqual(summary["total_nodes"], 2)
        self.assertIn("ref:aleksander_axioms", summary["root_causes"])

    def test_register_production_promotion_and_lineage_trace(self):
        # 1. Simula studio con prototipo
        record = self.engine.execute_study_cycle(pillar_id="symbolic_causal_mesh")
        proto_file = record.get("prototype_file")
        self.assertIsNotNone(proto_file)

        # 2. Promuove a modulo di produzione
        eid = self.engine.register_production_promotion(
            prototype_file=proto_file,
            module_name="causal_memory_graph",
            confidence=1.0,
            metadata={"domain": "Causal AI"},
        )
        self.assertIsNotNone(eid)

        # 3. Traccia lineage del componente di produzione
        res = self.engine.trace_component_lineage("prod:causal_memory_graph")
        causes = [c[0] for c in res["lineage"]]

        self.assertIn(f"proto:{proto_file}", causes)
        self.assertIn("ref:symbolic_causal_mesh", causes)
        self.assertEqual(len(res["detailed_events"]), 3)

    def test_synthesis_document_contains_causal_graph_metrics(self):
        self.engine.execute_study_cycle(pillar_id="swarm_emergence")
        self.assertTrue(self.engine.synthesis_md.exists())

        md_text = self.engine.synthesis_md.read_text(encoding="utf-8")
        self.assertIn("Grafo di Causalità & Lineage Cognitiva", md_text)
        self.assertIn("Nodi Totali nel Grafo", md_text)
        self.assertIn("Archi di Causalità Diretta/Indiretta", md_text)


if __name__ == "__main__":
    unittest.main()
