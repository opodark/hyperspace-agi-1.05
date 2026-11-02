# SPDX-License-Identifier: Apache-2.0
# tests/test_resin_bridge.py
"""Test unitari per shared/resin_bridge.py (Substrato d'inferenza Rust Resin per HyperSpace 1.06)."""

from __future__ import annotations

import unittest

from shared.memory_schema import VERIFIED, validate_evidence
from shared.resin_bridge import RESIN_PINNED_COMMIT, ResinBridge


@unittest.skipUnless(
    ResinBridge().is_local_runtime_available(),
    "modulo extra resin non installato (bash scripts/install_resin.sh)",
)
class TestResinBridge(unittest.TestCase):
    def setUp(self) -> None:
        self.bridge = ResinBridge()

    def test_substrate_info_and_crates(self) -> None:
        """Verifica i metadati del substrato Resin 1.06, i crate Rust e i pacchetti runner."""
        info = self.bridge.get_substrate_info()
        self.assertTrue(info["native_extension_ready"])
        self.assertEqual(info["target_release"], "HyperSpace 1.06")
        self.assertEqual(info["license"], "Apache-2.0")
        self.assertEqual(info["pinned_commit"], RESIN_PINNED_COMMIT)
        self.assertEqual(info["version"], "0.1.0")
        for crate in ("resin-core", "resin-http", "resin-py", "resin-recipe"):
            self.assertIn(crate, info["rust_crates"])
        for runner in ("cuda", "mlx", "torch"):
            self.assertIn(runner, info["model_runner_packages"])
        for skill in ("add-resin-model", "optimize-resin-performance"):
            self.assertIn(skill, info["bundled_skills"])

    def test_hybrid_slab_schedule_history_and_deltanet_state_prefix_reuse(self) -> None:
        """Verifica lo scheduler Rust con layout ibrido HISTORY + STATE e prefix caching LRU."""
        res = self.bridge.simulate_hybrid_slab_schedule(
            shared_prefix_tokens=[10, 20, 30, 40],
            agent_suffixes=[[101, 102], [201, 202], [301]],
            max_output_tokens=3,
            parent_capacity=16,
            block_tokens=4,
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["verdict"], VERIFIED)
        self.assertEqual(validate_evidence(res["evidence"]), [])
        self.assertEqual(len(res["schedule_hash"]), 64)

        # La prima richiesta non ha prefisso in cache; le due successive devono avere cached_prefix_tokens == 4
        reqs = res["requests"]
        self.assertEqual(len(reqs), 3)
        self.assertEqual(reqs[0]["cached_prefix_tokens"], 0)
        self.assertEqual(reqs[1]["cached_prefix_tokens"], 4)
        self.assertEqual(reqs[2]["cached_prefix_tokens"], 4)

        # Verifica che gli snapshot STATE (DeltaNet/Qwenputer) siano stati committati e ripristinati
        self.assertGreaterEqual(res["state_checkpoints_committed"], 1)
        self.assertGreaterEqual(res["state_restores_executed"], 2)
        self.assertEqual(res["prefix_cache_stats"]["hits"], 2)
        self.assertEqual(res["prefix_cache_stats"]["misses"], 1)

    def test_mesh_nodes_readiness_structure(self) -> None:
        """Verifica la struttura della diagnostica multi-nodo per HyperSpace 1.06."""
        report = self.bridge.check_mesh_nodes_readiness()
        self.assertEqual(report["target_version"], "HyperSpace 1.06 (Resin Substrate)")
        self.assertTrue(report["cluster_ready"])
        nodes = report["nodes"]
        self.assertIn("mac_m5_hub", nodes)
        self.assertIn("hp_omen_16", nodes)
        self.assertIn("asus_v16", nodes)
        self.assertEqual(nodes["mac_m5_hub"]["status"], "ready")


if __name__ == "__main__":
    unittest.main()
