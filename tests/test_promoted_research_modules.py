#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Test suite per i 5 moduli R&D promossi in produzione in shared/."""

import unittest
from shared.self_healing_peer_mesh import SelfHealingPeerMesh
from shared.work_stealing_dag_scheduler import Task, Worker, DAG, WorkStealingDAGScheduler
from shared.context_compactor import ContinuousContextCompactor
from shared.distributed_rollback_journal import Node, DistributedRollbackJournal
from shared.trimodal_memory_graph import TriModalMemoryGraph


class TestPromotedResearchModules(unittest.TestCase):
    # 1. SelfHealingPeerMesh
    def test_self_healing_peer_mesh(self):
        mesh = SelfHealingPeerMesh("node-omen", peers={"node-mac", "node-asus"}, latency_threshold_ms=150.0)
        self.assertEqual(mesh.role, "Worker")

        # Aggiorna latenze
        mesh.update_status("node-mac", 20.0)    # < 150 -> vivo
        mesh.update_status("node-asus", 350.0)  # > 150 -> scartato

        self.assertIn("node-mac", mesh.alive_peers)
        self.assertNotIn("node-asus", mesh.alive_peers)

        # Rinegoziazione ruoli deterministica
        mesh.renegotiate_roles()
        self.assertIn(mesh.role, ("Leader", "Worker"))
        self.assertIsNotNone(mesh.leader)

        top = mesh.topology()
        self.assertEqual(top["id"], "node-omen")
        self.assertTrue(top["healthy"])

    # 2. WorkStealingDAGScheduler
    def test_work_stealing_dag_scheduler(self):
        w1 = Worker("w1")
        w2 = Worker("w2")
        scheduler = WorkStealingDAGScheduler([w1, w2], steal_threshold=2)

        # DAG: t1 -> t2, t3 indipendente
        t1 = Task(1, deps=[])
        t2 = Task(2, deps=[1])
        t3 = Task(3, deps=[])
        dag = DAG([t1, t2, t3])

        scheduler.submit(dag)
        # Inizialmente t1 e t3 sono ready
        self.assertEqual(len(scheduler.ready_tasks), 2)

        # Dispatch assegna ai worker liberi
        scheduler.dispatch_step()
        self.assertEqual(len(w1.queue), 1)
        self.assertEqual(len(w2.queue), 1)

        # Simula completamento t1
        w1.pop()
        newly_ready = scheduler.on_task_done(1)
        self.assertEqual(len(newly_ready), 1)
        self.assertEqual(newly_ready[0].node_id, 2)

    # 3. ContinuousContextCompactor
    def test_continuous_context_compactor(self):
        compactor = ContinuousContextCompactor(window_size=10)

        # Inserimento ed eliminazione duplicati
        self.assertTrue(compactor.push({"id": 1, "topic": "mesh_routing"}))
        self.assertFalse(compactor.push({"id": 1, "topic": "mesh_routing"}))  # duplicato

        for i in range(2, 8):
            compactor.push({"id": i, "topic": f"topic_{i}"})
        self.assertEqual(compactor.count(), 7)

        # Checkpoint e rollback
        ckpt = compactor.checkpoint()
        compactor.push({"id": 99, "topic": "extra"})
        self.assertEqual(compactor.count(), 8)

        compactor.rollback(ckpt)
        self.assertEqual(compactor.count(), 7)

        # Distillazione/Compattazione
        res = compactor.compact(keep_latest=3)
        self.assertTrue(res["distilled"])
        self.assertLessEqual(compactor.count(), 4)

    # 4. DistributedRollbackJournal
    def test_distributed_rollback_journal(self):
        n1 = Node("n1")
        n2 = Node("n2")
        n3 = Node("n3")
        journal = DistributedRollbackJournal([n1, n2, n3], quorum=2)

        txn = journal.begin("mesh code sync")
        state = {"file_written": True}

        def undo():
            state["file_written"] = False

        journal.record_undo(txn, undo, "cancella file locale")

        # Quorum non ancora raggiunto
        journal.vote(txn, "n1")
        # Abort causa fallimento
        rollbacks = journal.abort(txn)
        self.assertEqual(len(rollbacks), 1)
        self.assertFalse(state["file_written"])  # Undo applicato!

        # Nuova transazione con quorum raggiunto
        txn2 = journal.begin("successful commit")
        journal.vote(txn2, "n1")
        journal.vote(txn2, "n2")
        committed = journal.commit(txn2)
        self.assertTrue(committed)

    # 5. TriModalMemoryGraph
    def test_trimodal_memory_graph(self):
        g = TriModalMemoryGraph()
        g.add_chunk("code-1", "def route_task(): pass", metadata={"lang": "python"})
        g.add_interaction("chat-1", "creator", "Avvia la missione di routing")
        g.add_note("note-1", content="Il router deve privilegiare nodi a rete AC")

        st = g.stats()
        self.assertEqual(st["chunks_count"], 1)
        self.assertEqual(st["interactions_count"], 1)
        self.assertEqual(st["notes_count"], 1)
        self.assertEqual(st["total_nodes"], 3)

        # Cross-modal search (trova il chunk con 'route_task' e la chat con 'routing')
        results = g.search_all("route")
        self.assertGreaterEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()
