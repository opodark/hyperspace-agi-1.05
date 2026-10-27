#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# tests/test_aleksander_causal_bridge.py
"""
Test di validazione per il Ponte R&D 1:
Integrazione tra i 5 Assiomi della Coscienza Sintetica (Igor Aleksander)
e il Grafo Causale Distribuito (CausalMemoryGraph Pearl-Style SQLite FTS5 WAL).
"""

import math
import os
import tempfile
import time
import unittest

from shared.causal_memory_graph import CausalMemoryGraph
from shared.synthetic_consciousness_governor import (
    ANNA_PERSONA,
    CheckpointManager,
    DreamEngine,
    SyntheticConsciousnessGovernor,
    TaskScheduler,
)


class TestAleksanderCausalBridge(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test_causal_bridge.db")
        self.graph_json = os.path.join(self.tmp_dir.name, "causal_bridge.json")
        self.causal_graph = CausalMemoryGraph(
            db_path=self.db_path,
            storage_path=self.graph_json,
        )

        # Popola il grafo con eventi di causa-effetto eterogenei
        self.causal_graph.record_event(
            cause_id="cache_invalidation",
            effect_id="model_latency_reduction",
            weight=0.92,
            metadata={"agent_id": "agent_alpha"},
        )
        self.causal_graph.record_event(
            cause_id="model_latency_reduction",
            effect_id="user_interaction_speedup",
            weight=0.88,
            metadata={"agent_id": "agent_alpha"},
        )
        self.causal_graph.record_event(
            cause_id="vram_leak_incident",
            effect_id="process_crash_error",
            weight=0.95,
            metadata={"agent_id": "agent_beta"},
        )
        self.causal_graph.record_event(
            cause_id="task_dag_optimization",
            effect_id="Explore imagination",
            weight=0.85,
            metadata={"agent_id": "agent_anna"},
        )

        self.governor = SyntheticConsciousnessGovernor(
            persona=ANNA_PERSONA.copy(),
            node_id="test_node_m5",
            causal_graph=self.causal_graph,
        )

    def tearDown(self) -> None:
        self.causal_graph.close()
        self.tmp_dir.cleanup()

    def test_counterfactual_dream_engine_with_causal_graph(self) -> None:
        """Verifica la generazione di scenari controfattuali basati sul grafo reale."""
        dream_engine = DreamEngine(causal_graph=self.causal_graph)
        scenarios = dream_engine.generate_counterfactuals(n=6)

        self.assertEqual(len(scenarios), 6)
        for s in scenarios:
            self.assertIn("scenario", s)
            self.assertIn(s["outcome"], {-1, 0, 1})
            self.assertIn("cause_id", s)
            self.assertIn("effect_id", s)
            self.assertIn("intervention", s)
            self.assertIn("downstream", s)

        # Verifica che gli interventi abbiano esplorato suppression, amplification, inversion
        interventions = {s["intervention"] for s in scenarios}
        self.assertIn("suppression", interventions)
        self.assertIn("amplification", interventions)
        self.assertIn("inversion", interventions)

    def test_imagination_entropy_score(self) -> None:
        """Verifica che la misura di immaginazione con il grafo causale produca entropia positiva."""
        score = self.governor.measure_imagination(n=10)
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_planning_causal_path_evaluation(self) -> None:
        """Verifica che la misura di pianificazione (Assioma 4) premi azioni con legami causali provati."""
        # 1. Nessuna azione -> 0.0
        self.assertEqual(self.governor.measure_planning(), 0.0)

        # 2. Pianifica un'azione con legame provato nel grafo causale ("cache_invalidation")
        # e una con target_goal dichiarato nella persona ("Explore imagination")
        self.governor.scheduler.schedule_task({"id": "cache_invalidation", "cost": 1.0})
        self.governor.scheduler.schedule_task({"id": "task_dag_optimization", "target_goal": "Explore imagination", "cost": 1.2})
        
        score = self.governor.measure_planning()
        # Entrambe hanno legami causali dimostrati nel grafo
        self.assertEqual(score, 1.0)

    def test_valuation_modulated_by_causal_events(self) -> None:
        """Verifica che la valenza affettiva risponda agli incidenti nel grafo causale."""
        val_score = self.governor.measure_valuation()
        self.assertGreaterEqual(val_score, 0.1)
        self.assertLessEqual(val_score, 1.0)

        # Se rimuoviamo i goal, la valenza scende a 0.0
        empty_gov = SyntheticConsciousnessGovernor(persona={"self_model": {"goals": []}})
        self.assertEqual(empty_gov.measure_valuation(), 0.0)

    def test_dream_causal_cycle_end_to_end(self) -> None:
        """
        Esegue il ciclo onirico completo:
        - genera controfattuali
        - consolida l'insight come nuovo evento nel grafo causale
        - scrive il checkpoint WAL
        """
        initial_events = self.causal_graph.total_events()
        cycle_result = self.governor.dream_causal_cycle(n_scenarios=8)

        self.assertEqual(cycle_result["status"], "consolidated")
        self.assertGreater(cycle_result["imagination_score"], 0.0)
        self.assertEqual(len(cycle_result["scenarios"]), 8)
        self.assertIsNotNone(cycle_result["consolidated_event_id"])

        # Il grafo causale ha ora un evento in più
        self.assertEqual(self.causal_graph.total_events(), initial_events + 1)

        # L'evento consolidato può essere recuperato con la sua genealogia
        event_id = cycle_result["consolidated_event_id"]
        ev = self.causal_graph.get_event(event_id)
        self.assertIsNotNone(ev)
        self.assertIn("dream_cycle_test_node_m5", ev["cause_id"])
        self.assertEqual(ev["metadata"]["persona_identity"], "Anna")

        # Il checkpoint WAL contiene i riferimenti del sogno
        latest_cp = self.governor.checkpoint.read_latest_checkpoint()
        self.assertIsNotNone(latest_cp)
        self.assertEqual(latest_cp["dream_event_id"], event_id)
        self.assertEqual(latest_cp["node_id"], "test_node_m5")

    def test_fallback_without_causal_graph(self) -> None:
        """Garantisce la compatibilità all'indietro quando nessun grafo è collegato."""
        standalone_gov = SyntheticConsciousnessGovernor()
        standalone_gov.scheduler.schedule_task({"id": "init_task", "cost": 1.5})
        adherence = standalone_gov.overall_adherence()
        for k in ["self_depiction", "imagination", "attention", "planning", "valuation"]:
            self.assertGreater(adherence[k], 0.0)

        axioms = standalone_gov.evaluate_axioms()
        for k, v in axioms.items():
            self.assertTrue(v, f"Axiom {k} should be True")

        cycle_res = standalone_gov.dream_causal_cycle(n_scenarios=4)
        self.assertEqual(cycle_res["status"], "consolidated")
        self.assertIsNone(cycle_res["consolidated_event_id"])


if __name__ == "__main__":
    unittest.main()
