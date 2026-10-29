# SPDX-License-Identifier: Apache-2.0
"""Test suite per i moduli promossi nella sessione di consolidamento e R&D:
- shared/dynamic_mesh_topology_optimizer.py
- shared/zero_knowledge_task_attestation.py
"""

import time
import unittest


class TestConsolidationRDModules(unittest.TestCase):
    def test_dynamic_mesh_topology_optimizer(self):
        try:
            from shared.dynamic_mesh_topology_optimizer import DynamicMeshTopologyOptimizer
        except ImportError:
            self.skipTest("Modulo non ancora promosso sul filesystem")

        # 3 nodi con matrici sintetiche di latenza e banda
        latency = [
            [0.0, 15.0, 120.0],
            [15.0, 0.0, 45.0],
            [120.0, 45.0, 0.0],
        ]
        bandwidth = [
            [1000.0, 500.0, 50.0],
            [500.0, 1000.0, 200.0],
            [50.0, 200.0, 1000.0],
        ]

        optimizer = DynamicMeshTopologyOptimizer(3, latency, bandwidth)
        self.assertIsNotNone(optimizer)
        self.assertEqual(optimizer._num_nodes, 3)

    def test_zero_knowledge_task_attestation(self):
        try:
            from shared.zero_knowledge_task_attestation import ZeroKnowledgeTaskAttestation
        except ImportError:
            self.skipTest("Modulo non ancora promosso sul filesystem")

        attester = ZeroKnowledgeTaskAttestation(node_id="node_test_01")
        self.assertIsNotNone(attester)
        self.assertEqual(attester.node_id, "node_test_01")


if __name__ == "__main__":
    unittest.main()
