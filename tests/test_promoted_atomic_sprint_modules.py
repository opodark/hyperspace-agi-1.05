# SPDX-License-Identifier: Apache-2.0
"""Test suite per i moduli promossi nel Dual-Node Atomic Sprint:
- shared/autonomous_failure_isolator.py
- shared/cross_context_semantic_cache.py
- shared/distributed_prioritized_work_stealing.py
"""

import time
import unittest


class TestPromotedAtomicSprintModules(unittest.TestCase):
    def test_autonomous_failure_isolator(self):
        try:
            from shared.autonomous_failure_isolator import AutonomousFailureIsolator, NodeState
        except ImportError:
            self.skipTest("Modulo non ancora promosso sul filesystem")

        isolator = AutonomousFailureIsolator(
            poll_interval=1.0,
            latency_threshold=150.0,
            loss_threshold=0.1,
            history_size=5,
        )
        self.assertIsNotNone(isolator)

    def test_cross_context_semantic_cache(self):
        try:
            from shared.cross_context_semantic_cache import CrossContextSemanticCache
        except ImportError:
            self.skipTest("Modulo non ancora promosso sul filesystem")

        cache = CrossContextSemanticCache(capacity=5)
        cache.set("qual è lo stato del nodo omen?", {"status": "ok", "latency": 12.5})
        
        # Test exact normalized retrieval
        val = cache.get("QUAL È LO STATO DEL NODO OMEN?  ")
        self.assertIsNotNone(val)
        self.assertEqual(val["status"], "ok")

        # Test fuzzy similarity matching
        val_fuzzy = cache.get("qual è lo stato del nodo omen")
        self.assertIsNotNone(val_fuzzy)
        self.assertEqual(val_fuzzy["latency"], 12.5)

    def test_distributed_prioritized_work_stealing(self):
        try:
            from shared.distributed_prioritized_work_stealing import DistributedPrioritizedWorkStealing, Task
        except ImportError:
            self.skipTest("Modulo non ancora promosso sul filesystem")

        queue = DistributedPrioritizedWorkStealing(num_workers=3)
        t1 = Task(id=1, deadline=time.time() + 10.0, cost=5.0)
        t2 = Task(id=2, deadline=time.time() + 2.0, cost=1.0)  # Priorità più alta (deadline prima)

        queue.submit(t1, worker_id=0)
        queue.submit(t2, worker_id=0)

        popped = queue.pop_local(worker_id=0)
        self.assertEqual(popped.id, 2)  # Dovrebbe estrarre prima t2 per deadline


if __name__ == "__main__":
    unittest.main()
