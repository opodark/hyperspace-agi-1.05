#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
tests/test_causal_memory_graph.py
Test unitari per CausalMemoryGraph promosso da proto_symbolic_causal_mesh_1792924003.py.
"""

import unittest
from shared.causal_memory_graph import CausalMemoryGraph


class TestCausalMemoryGraph(unittest.TestCase):
    def setUp(self):
        self.cmg = CausalMemoryGraph()

    def test_record_single_event(self):
        eid = self.cmg.record_event("scout:arxiv", "hyp:fungal_routing", weight=0.85)
        self.assertIsNotNone(eid)
        self.assertEqual(self.cmg.total_events(), 1)

        ev = self.cmg.get_event(eid)
        self.assertEqual(ev["cause_id"], "scout:arxiv")
        self.assertEqual(ev["effect_id"], "hyp:fungal_routing")
        self.assertEqual(ev["weight"], 0.85)

    def test_trace_lineage_multi_hop(self):
        # Catena causale:
        # arXiv discovery -> Hyperspace Hypothesis -> Prototype AST -> Production Module
        self.cmg.record_event("arxiv:physarum", "hyp:mesh_routing", weight=0.9)
        self.cmg.record_event("hyp:mesh_routing", "proto:biomimetic_ast", weight=0.8)
        self.cmg.record_event("proto:biomimetic_ast", "prod:biomimetic_mesh", weight=0.95)

        lineage = self.cmg.trace_lineage("prod:biomimetic_mesh")
        causes = [c[0] for c in lineage]

        self.assertIn("proto:biomimetic_ast", causes)
        self.assertIn("hyp:mesh_routing", causes)
        self.assertIn("arxiv:physarum", causes)

    def test_forward_consequences(self):
        self.cmg.record_event("node:asus_online", "task:40b_flint_offload", weight=1.0)
        self.cmg.record_event("node:asus_online", "task:24b_lfm_offload", weight=1.0)

        consequences = self.cmg.get_forward_consequences("node:asus_online")
        self.assertEqual(len(consequences), 2)
        effects = [c[0] for c in consequences]
        self.assertIn("task:40b_flint_offload", effects)
        self.assertIn("task:24b_lfm_offload", effects)

    def test_persistence_save_and_load(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "causal_test.json"
            cmg1 = CausalMemoryGraph(storage_path=file_path)
            cmg1.record_event("cause:1", "effect:1", weight=0.75, metadata={"note": "test"})

            # Verifica caricamento su nuova istanza
            cmg2 = CausalMemoryGraph(storage_path=file_path)
            self.assertEqual(cmg2.total_events(), 1)
            self.assertEqual(len(cmg2.trace_lineage("effect:1")), 1)
            detailed = cmg2.trace_detailed_lineage("effect:1")
            self.assertEqual(len(detailed), 1)
            self.assertEqual(detailed[0]["metadata"]["note"], "test")

            summary = cmg2.export_graph_summary()
            self.assertEqual(summary["total_nodes"], 2)
            self.assertEqual(summary["total_edges"], 1)


if __name__ == "__main__":
    unittest.main()
