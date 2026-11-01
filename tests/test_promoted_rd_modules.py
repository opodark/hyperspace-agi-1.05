#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
tests/test_promoted_rd_modules.py
Unit tests per i moduli promossi in produzione dal laboratorio sovrano R&D:
- shared.neuro_symbolic_poetry (NeuroSymbolicPoetryEngine)
- shared.stigmergic_mesh_swarm (StigmergicMeshSwarm, VectorClock)
- shared.synthetic_consciousness_governor (SyntheticConsciousnessGovernor)
- shared.biomimetic_nature_mesh (MeshOrchestrator, Monitors, Mycelium, Quorum)
"""

import unittest
from shared.neuro_symbolic_poetry import NeuroSymbolicPoetryEngine
from shared.stigmergic_mesh_swarm import StigmergicMeshSwarm, VectorClock
from shared.synthetic_consciousness_governor import SyntheticConsciousnessGovernor
from shared.biomimetic_nature_mesh import (
    MyceliumNetwork,
    BacterialQuorum,
    EpidemicGossip,
    SymbioticCleptoparasitism,
    Node,
    Connection,
    MeshOrchestrator,
    MeshEntropyMonitor,
    FlowEffectivenessMonitor,
    HyperSpaceMeshMonitor,
)


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


class TestBiomimeticNatureMesh(unittest.TestCase):
    def test_mycelium_reinforce_and_prune(self):
        net = MyceliumNetwork(num_nodes=4)
        path = (0, 1)
        net.latencies[path] = 120.0  # ms
        new_weight = net.reinforce(path, amount=1.5)
        self.assertEqual(new_weight, 1.5)

        # Potatura con soglia 100 ms
        pruned = net.prune(latency_threshold=100.0)
        self.assertIn(path, pruned)
        self.assertNotIn(path, net.paths)

    def test_bacterial_quorum_and_trigger(self):
        quorum = BacterialQuorum(threshold=0.6, total_nodes=10)
        self.assertFalse(quorum.update_density(current=4))
        self.assertIsNone(quorum.trigger_task(lambda: "executed"))

        # Densità sufficiente (7/10 = 0.7 >= 0.6)
        self.assertTrue(quorum.update_density(current=7))
        res = quorum.trigger_task(lambda: "moe_cluster_ready")
        self.assertEqual(res, "moe_cluster_ready")

    def test_epidemic_gossip_antigenic_filter(self):
        gossip = EpidemicGossip(antigenic_filter=True)
        self.assertTrue(gossip.replicate({"state": "sovereign_wal_123"}))
        self.assertFalse(gossip.replicate({"state": "tampered", "corrupted": True}))
        self.assertFalse(gossip.replicate(None))
        self.assertEqual(len(gossip.state_payloads), 1)

    def test_symbiotic_cleptoparasitism(self):
        clepto = SymbioticCleptoparasitism(steal_rate=0.25)
        # Host con capacità 4.0 -> ruba 1.0 ciclo
        stolen = clepto.steal_cycles(host_capacity=4.0)
        self.assertEqual(stolen, 1.0)
        # Host esausto
        self.assertEqual(clepto.steal_cycles(host_capacity=0.05), 0.0)

    def test_mesh_orchestrator_and_topological_monitors(self):
        nodes = [
            Node("omen_compute", "heavy", compute_capacity=8.0),
            Node("asus_compute", "heavy", compute_capacity=6.0),
            Node("mac_edge", "edge", compute_capacity=2.0),
        ]
        conns = [
            Connection(nodes[0], nodes[1], latency=10.0, bandwidth=100.0, weight=1.0),
            Connection(nodes[0], nodes[2], latency=15.0, bandwidth=50.0, weight=1.0),
            Connection(nodes[1], nodes[2], latency=20.0, bandwidth=50.0, weight=1.0),
        ]
        orchestrator = MeshOrchestrator(nodes=nodes)
        orchestrator.connections = conns

        # Test monitor di entropia di Shannon sui gradi dei nodi
        entropy_mon = MeshEntropyMonitor(orchestrator)
        entropy = entropy_mon.calculate_entropy()
        self.assertGreater(entropy, 0.0)

        # Test monitor di efficienza di flusso
        flow_mon = FlowEffectivenessMonitor(orchestrator)
        metrics = flow_mon.compute_metrics()
        self.assertGreater(metrics["throughput"], 0.0)
        self.assertGreater(metrics["efficiency"], 0.0)
        self.assertGreaterEqual(metrics["avg_latency"], 10.0)

        # Test cleptoparassitismo tra nodi edge e heavy
        stolen_records = orchestrator.steal_compute()
        self.assertGreaterEqual(len(stolen_records), 1)
        self.assertEqual(stolen_records[0]["edge_id"], "mac_edge")

        # Test gossip state
        accepted = orchestrator.gossip_state({"epoch": 42})
        self.assertEqual(accepted, 3)
        self.assertEqual(nodes[0].state, {"epoch": 42})

    def test_hyperspace_mesh_monitor_legacy(self):
        monitor = HyperSpaceMeshMonitor(num_nodes=5)
        entropy = monitor.compute_entropy()
        self.assertGreater(entropy, 0.0)
        monitor.update_metrics(latencies=[5.0, 10.0], throughput=100.0, success=95)
        flow = monitor.compute_flow_effectiveness()
        self.assertEqual(flow, 0.95)


if __name__ == "__main__":
    unittest.main()
