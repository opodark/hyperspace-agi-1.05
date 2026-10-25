#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
tests/test_promoted_rd_modules.py
Unit tests per i moduli promossi in produzione dal laboratorio sovrano R&D:
- shared.neuro_symbolic_poetry (NeuroSymbolicPoetryEngine)
- shared.stigmergic_mesh_swarm (StigmergicMeshSwarm, VectorClock)
- shared.synthetic_consciousness_governor (SyntheticConsciousnessGovernor)
"""

import unittest
from shared.neuro_symbolic_poetry import NeuroSymbolicPoetryEngine
from shared.stigmergic_mesh_swarm import StigmergicMeshSwarm, VectorClock
from shared.synthetic_consciousness_governor import SyntheticConsciousnessGovernor


class TestNeuroSymbolicPoetryEngine(unittest.TestCase):
    def setUp(self):
        self.engine = NeuroSymbolicPoetryEngine({
            "location": "torre di controllo",
            "emotion": "chiarezza",
            "weather": "notte stellata",
            "sky": "firmamento digitale",
        })

    def test_generate_poem_abab(self):
        poem = self.engine.generate_poem(scheme="ABAB")
        self.assertIn("torre di controllo", poem)
        self.assertIn("chiarezza", poem)
        lines = poem.strip().split("\n")
        self.assertEqual(len(lines), 4)

    def test_generate_poem_aabb(self):
        poem = self.engine.generate_poem(scheme="AABB")
        self.assertIn("firmamento digitale", poem)
        lines = poem.strip().split("\n")
        self.assertEqual(len(lines), 4)

    def test_extract_visual_prompt_default(self):
        prompt_data = self.engine.extract_visual_prompt()
        self.assertIn("positive_prompt", prompt_data)
        self.assertIn("negative_prompt", prompt_data)
        self.assertEqual(prompt_data["style"], "watercolor")
        self.assertIn("Anna portrait", prompt_data["positive_prompt"])

    def test_extract_visual_prompt_custom_style(self):
        prompt_data = self.engine.extract_visual_prompt(
            keywords=["cybercore", "neon grid"],
            style="cyberpunk_dream",
        )
        self.assertEqual(prompt_data["theme"], "cybercore")
        self.assertIn("cyberpunk", prompt_data["positive_prompt"])

    def test_generate_poem_sonnet_14_lines(self):
        poem = self.engine.generate_poem(form="sonnet")
        # Deve contenere 14 versi (escluse le righe vuote tra quartine e terzine)
        verse_lines = [l for l in poem.strip().split("\n") if l.strip()]
        self.assertEqual(len(verse_lines), 14)
        self.assertIn("torre di controllo", poem)

    def test_count_syllables_prosodic(self):
        # "luce" -> 2 sillabe
        self.assertEqual(self.engine.count_syllables("luce"), 2)
        # "memoria" -> 3-4 sillabe
        self.assertGreaterEqual(self.engine.count_syllables("memoria"), 3)

    def test_extract_visual_prompt_typography_constraints(self):
        prompt_data = self.engine.extract_visual_prompt()
        self.assertIn("typography", prompt_data)
        typo = prompt_data["typography"]
        self.assertEqual(typo["title_font"], "Playfair Display")
        self.assertEqual(typo["title_size_pt"], 24)
        self.assertEqual(typo["body_font"], "Garamond")
        self.assertIn("Playfair Display", prompt_data["positive_prompt"])


class TestStigmergicMeshSwarm(unittest.TestCase):
    def setUp(self):
        self.swarm = StigmergicMeshSwarm()

    def test_vector_clock_causality(self):
        v1 = VectorClock()
        v2 = VectorClock()
        v1.update("node-a")
        v1.update("node-b")
        v2.update("node-b")

        diff = v1.compare(v2)
        self.assertIn("node-a", diff)

    def test_deposit_and_sense_gradient(self):
        self.swarm.deposit_pheromone("attenzione", {"importanza": 0.95}, decay_rate=0.05, node_id="omen-16")
        self.swarm.deposit_pheromone("attenzione", {"importanza": 0.40}, decay_rate=0.05, node_id="laptop-asus")

        gradient = self.swarm.sense_gradient("attenzione")
        self.assertEqual(len(gradient), 2)
        # Il segnale con intensità maggiore deve essere in cima al gradiente
        self.assertGreater(gradient[0]["strength"], gradient[1]["strength"])
        self.assertEqual(gradient[0]["node_id"], "omen-16")

    def test_compute_gradient_field_hotspot_and_variance(self):
        self.swarm.deposit_pheromone("calcolo", {"importanza": 0.90}, node_id="omen-16")
        self.swarm.deposit_pheromone("calcolo", {"importanza": 0.30}, node_id="asus-v16")
        self.swarm.deposit_pheromone("calcolo", {"importanza": 0.60}, node_id="mac-m5")

        field = self.swarm.compute_gradient_field("calcolo")
        self.assertEqual(field["signal_type"], "calcolo")
        self.assertEqual(field["hotspot_node"], "omen-16")
        self.assertEqual(field["active_signals_count"], 3)
        self.assertGreater(field["average_strength"], 0.5)
        self.assertGreater(field["variance"], 0.0)

    def test_decay_pheromones_evaporation(self):
        self.swarm.deposit_pheromone("allerta", {"importanza": 0.5}, decay_rate=0.6, node_id="node-1")
        # Primo decadimento: decay passa a 0.6 -> ancora attivo
        self.assertEqual(len(self.swarm.sense_gradient("allerta")), 1)

        # Secondo decadimento con rate 0.5: decay passa a 1.1 -> evaporato
        evaporated = self.swarm.decay_pheromones(decay_rate=0.5)
        self.assertEqual(evaporated, 1)
        self.assertEqual(len(self.swarm.sense_gradient("allerta")), 0)

    def test_consensus_converged_single_or_empty(self):
        self.assertTrue(self.swarm.consensus_converged())
        self.swarm.deposit_pheromone("task", {"cmd": "build"}, node_id="omen")
        self.assertTrue(self.swarm.consensus_converged())


class TestSyntheticConsciousnessGovernor(unittest.TestCase):
    def setUp(self):
        self.governor = SyntheticConsciousnessGovernor(node_id="OMEN-16")

    def test_evaluate_axioms_full_compliance(self):
        axioms = self.governor.evaluate_axioms()
        expected_keys = ["depiction_of_self", "imagination", "attention", "planning", "valencing"]
        for k in expected_keys:
            self.assertTrue(axioms.get(k), f"Assioma mancante o Falso: {k}")

    def test_audit_node_report(self):
        audit = self.governor.audit_node({"persona_loaded": True, "dream_cycle_active": True})
        self.assertEqual(audit["score"], 1.0)
        self.assertEqual(audit["status"], "conformant")
        self.assertIn("definitions", audit)
        self.assertEqual(len(audit["definitions"]), 5)


if __name__ == "__main__":
    unittest.main()
