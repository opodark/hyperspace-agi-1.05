#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
tests/test_biomimetic_mesh.py
Test unitari per i meccanismi biomimetici della mesh HyperSpace:
- MyceliumNetworkRouter (Physarum routing, rinforzo e potatura ifale)
- BacterialQuorumGovernor (accumulo autoinduttore, decadimento e soglia di quorum)
- ViralGossipDisseminator (impacchettamento virale, verifica antigene e diffusione epidemica)
- SymbioticParasiteStealer (cleptoparassitismo simbiotico e rilascio istantaneo)
"""

import time
import unittest
from shared.biomimetic_mesh import (
    BacterialQuorumGovernor,
    MyceliumNetworkRouter,
    SymbioticParasiteStealer,
    ViralGossipDisseminator,
    calculate_flow_effectiveness,
    calculate_mesh_entropy,
)


class TestMyceliumNetworkRouter(unittest.TestCase):
    def setUp(self):
        self.router = MyceliumNetworkRouter(decay_rate=0.1, reinforcement_factor=0.5, min_conductivity=0.05)
        # Nodi: Mac M5, HP OMEN, ASUS V16, Web Node
        self.router.grow_hypha("mac-m5", "hp-omen", latency_ms=10.0, initial_conductivity=1.0)
        self.router.grow_hypha("mac-m5", "asus-v16", latency_ms=25.0, initial_conductivity=0.5)
        self.router.grow_hypha("hp-omen", "web-node", latency_ms=15.0, initial_conductivity=1.0)
        self.router.grow_hypha("asus-v16", "web-node", latency_ms=50.0, initial_conductivity=0.2)

    def test_find_optimal_path_initial(self):
        path = self.router.find_optimal_path("mac-m5", "web-node")
        self.assertEqual(path, ["mac-m5", "hp-omen", "web-node"])

    def test_flux_reinforcement_alters_path(self):
        # Rinforziamo pesantemente il canale ASUS (es. carichi massicci VRAM)
        for _ in range(20):
            self.router.reinforce_flux("mac-m5", "asus-v16", flux_amount=5.0)
            self.router.reinforce_flux("asus-v16", "web-node", flux_amount=5.0)

        path = self.router.find_optimal_path("mac-m5", "web-node")
        self.assertEqual(path, ["mac-m5", "asus-v16", "web-node"])

    def test_decay_and_prune(self):
        # Creiamo un'ifa debole e trascurata
        self.router.grow_hypha("hp-omen", "stale-node", latency_ms=100.0, initial_conductivity=0.04)
        pruned = self.router.decay_and_prune()
        self.assertGreaterEqual(pruned, 1)
        # Il canale stale è stato potato
        self.assertNotIn(("hp-omen", "stale-node"), self.router.conduits)


class TestBacterialQuorumGovernor(unittest.TestCase):
    def setUp(self):
        self.gov = BacterialQuorumGovernor(half_life_seconds=60.0)

    def test_quorum_not_reached_initially(self):
        self.assertFalse(self.gov.check_quorum("heavy_moe_40b", threshold=2.0))

    def test_quorum_reached_with_multiple_senders(self):
        self.gov.emit_autoinducer("mac-m5", "heavy_moe_40b", concentration=1.0)
        self.gov.emit_autoinducer("hp-omen", "heavy_moe_40b", concentration=1.0)
        self.gov.emit_autoinducer("asus-v16", "heavy_moe_40b", concentration=0.8)

        # Concentrazione totale: 2.8 >= 2.5 -> Quorum attivo!
        self.assertTrue(self.gov.check_quorum("heavy_moe_40b", threshold=2.5))
        self.assertGreaterEqual(self.gov.get_concentration("heavy_moe_40b"), 2.7)

    def test_decay_reduces_concentration(self):
        gov_fast_decay = BacterialQuorumGovernor(half_life_seconds=0.01)
        gov_fast_decay.emit_autoinducer("node-1", "wal_compaction", concentration=1.0)
        time.sleep(0.03)
        # Dopo 3 emivite, concentrazione inferiore a 0.2
        self.assertLess(gov_fast_decay.get_concentration("wal_compaction"), 0.2)
        self.assertFalse(gov_fast_decay.check_quorum("wal_compaction", threshold=0.5))


class TestViralGossipDisseminator(unittest.TestCase):
    def setUp(self):
        self.cluster = ["mac-m5", "hp-omen", "asus-v16", "web-node"]
        self.disseminator = ViralGossipDisseminator(known_nodes=self.cluster)

    def test_package_and_verify_valid_ast(self):
        code = "def bio_consensus(a, b):\n    return a + b\n"
        virion = self.disseminator.package_payload("ast_prototype", code)
        self.assertTrue(self.disseminator.verify_antigen(virion))

    def test_reject_tampered_or_invalid_ast(self):
        broken_code = "def broken(:\n    syntax error"
        virion = self.disseminator.package_payload("ast_prototype", broken_code)
        # Rifiutato dall'antigene per errore di sintassi AST
        self.assertFalse(self.disseminator.verify_antigen(virion))
        self.assertFalse(self.disseminator.infect_peer(virion, "hp-omen"))

    def test_epidemic_spread_calculation(self):
        virion = self.disseminator.package_payload("vector_clock", "nodeA:4,nodeB:2")
        self.disseminator.infect_peer(virion, "mac-m5")
        self.disseminator.infect_peer(virion, "hp-omen")
        spread = self.disseminator.calculate_epidemic_spread(virion)
        self.assertEqual(spread, 0.5)  # 2 su 4 nodi = 50%


class TestSymbioticParasiteStealer(unittest.TestCase):
    def setUp(self):
        self.stealer = SymbioticParasiteStealer(idle_cpu_threshold=30.0, idle_gpu_threshold=40.0)
        self.stealer.update_host_telemetry("omen-gpu", cpu=15.0, gpu=20.0, ram=45.0, priority=False)

    def test_acquire_slot_when_host_idle(self):
        acquired = self.stealer.acquire_stolen_slot("task-ast-eval-1", "omen-gpu")
        self.assertTrue(acquired)
        self.assertIn("task-ast-eval-1", self.stealer.active_parasites)

    def test_cannot_steal_when_host_busy(self):
        self.stealer.update_host_telemetry("omen-gpu", cpu=75.0, gpu=85.0, ram=80.0, priority=False)
        acquired = self.stealer.acquire_stolen_slot("task-heavy-2", "omen-gpu")
        self.assertFalse(acquired)

    def test_instant_yield_on_host_priority(self):
        self.stealer.acquire_stolen_slot("task-ast-eval-1", "omen-gpu")
        self.stealer.acquire_stolen_slot("task-ast-eval-2", "omen-gpu")

        # L'host attiva un lavoro prioritario
        self.stealer.update_host_telemetry("omen-gpu", cpu=90.0, gpu=95.0, ram=60.0, priority=True)
        evicted = self.stealer.yield_host("omen-gpu")
        self.assertEqual(len(evicted), 2)
        self.assertEqual(len(self.stealer.active_parasites), 0)


class TestBiomimeticMetrics(unittest.TestCase):
    def test_calculate_mesh_entropy_uniform(self):
        # 4 nodi con carico perfettamente bilanciato (0.25 ciascuno)
        # H = log2(4) = 2.0
        entropy = calculate_mesh_entropy([0.25, 0.25, 0.25, 0.25])
        self.assertAlmostEqual(entropy, 2.0, places=3)

    def test_calculate_mesh_entropy_empty_or_zero(self):
        self.assertEqual(calculate_mesh_entropy([]), 0.0)
        self.assertEqual(calculate_mesh_entropy([0.0, 0.0]), 0.0)

    def test_calculate_flow_effectiveness(self):
        # latenza 10ms su soglia 50ms -> score 0.8; throughput 2.5 su 10 -> score 0.25 -> 0.8 * 0.25 = 0.2
        eff = calculate_flow_effectiveness(latency_ms=10.0, throughput_gbps=2.5, threshold_latency_ms=50.0, max_throughput_gbps=10.0)
        self.assertEqual(eff, 0.2)

    def test_calculate_flow_effectiveness_high_latency(self):
        eff = calculate_flow_effectiveness(latency_ms=60.0, throughput_gbps=5.0)
        self.assertEqual(eff, 0.0)


if __name__ == "__main__":
    unittest.main()
