#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
tests/test_mission_causal_graph.py
Test unitari per l'integrazione di CausalMemoryGraph in MissionController:
- Tracciamento causale della decomposizione del piano (Goal -> Task, Task -> Task dependencies)
- Tracciamento delle esecuzioni dei worker (Task -> Exec, Exec -> Artifacts)
- Tracciamento dei verdetti dei verifier (Exec -> Verdict)
- Tracciamento causale del replanning
- Genealogia causale (trace_task_lineage)
- Diagnostica di causa radice in caso di fallimento (diagnose_root_cause)
- Esportazione del sottografo causale di missione (export_mission_causal_subgraph)
"""

import tempfile
import unittest

from shared import mission_policy
from shared.causal_memory_graph import CausalMemoryGraph
from shared.mission import MissionStore
from shared.mission_controller import MissionController

NOW = lambda: 1_700_000_000.0


class FakePlanner:
    def __init__(self, plans):
        self.plans = list(plans)
        self.reasons = []

    def __call__(self, mission, reason=""):
        self.reasons.append(reason)
        return self.plans.pop(0) if self.plans else []


class FakeWorker:
    def __init__(self, behaviors=None, artifacts=None, default_ok=True):
        self.behaviors = dict(behaviors or {})
        self.artifacts = dict(artifacts or {})
        self.default_ok = default_ok

    def __call__(self, task, mission):
        tid = task["task_id"]
        ok = self.behaviors.get(tid, self.default_ok)
        arts = self.artifacts.get(tid, [])
        return {
            "ok": ok,
            "output": f"output of {tid}",
            "error": "" if ok else f"error in {tid}",
            "artifacts": arts,
            "model": "LFM2.5-24B-ASUS",
            "target": "asus-v16",
            "tokens": 42,
        }


class FakeVerifier:
    def __init__(self, task_verdicts=None, mission_verdict="pass"):
        self.task_verdicts = dict(task_verdicts or {})
        self.mission_verdict = mission_verdict

    def __call__(self, scope, *, mission, task=None, outcome=None):
        if scope == "mission":
            return {"verdict": self.mission_verdict, "reason": "mission verified"}
        tid = task["task_id"]
        v = self.task_verdicts.get(tid, "pass")
        return {"verdict": v, "reason": f"verdict {v} for {tid}"}


def sample_dag_plan():
    return [
        {"key": "fetch-data", "role": "repo-analyst", "title": "Fetch Data", "instruction": "fetch"},
        {"key": "process-code", "role": "coder", "title": "Process Code", "instruction": "process", "dependencies": ["fetch-data"]},
    ]


class MissionCausalGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = MissionStore(self.temp.name, clock=NOW)
        self.cmg = CausalMemoryGraph()

    def controller(self, planner, worker, verifier):
        budget = mission_policy.parse_budget(env={})
        return MissionController(
            self.store,
            planner=planner,
            worker=worker,
            verifier=verifier,
            budget=budget,
            clock=NOW,
            causal_graph=self.cmg,
        )

    def test_causal_graph_tracks_plan_decomposition_and_dependencies(self):
        mission = self.store.create("Refactor Auth Engine", ["security tests pass"])
        mid = mission["id"]

        ctrl = self.controller(FakePlanner([sample_dag_plan()]), FakeWorker(), FakeVerifier())
        summary = ctrl.run(mid)
        self.assertEqual(summary["status"], "done")

        # Verifica che il grafo contenga il nodo Goal e i due Task
        goal_node = f"goal:{mid}"
        task1_node = f"task:{mid}:fetch-data"
        task2_node = f"task:{mid}:process-code"

        # Goal -> Task1 e Goal -> Task2
        task1_causes = [c[0] for c in self.cmg.trace_lineage(task1_node)]
        self.assertIn(goal_node, task1_causes)

        # Task1 -> Task2 (dipendenza esplicita)
        task2_causes = [c[0] for c in self.cmg.trace_lineage(task2_node)]
        self.assertIn(task1_node, task2_causes)
        self.assertIn(goal_node, task2_causes)

    def test_causal_graph_tracks_executions_verdicts_and_artifacts(self):
        mission = self.store.create("Build Landing Page", ["html exists"])
        mid = mission["id"]

        artifacts = {"process-code": [{"type": "file", "path": "index.html", "applied": False}]}
        worker = FakeWorker(artifacts=artifacts)
        ctrl = self.controller(FakePlanner([sample_dag_plan()]), worker, FakeVerifier())

        summary = ctrl.run(mid)
        self.assertEqual(summary["status"], "done")

        # Verifica la catena causale per il task process-code
        lineage_info = ctrl.trace_task_lineage(mid, "process-code")
        causes = [c[0] for c in lineage_info["lineage"]]
        self.assertIn(f"task:{mid}:fetch-data", causes)
        self.assertIn(f"goal:{mid}", causes)

        # Verifica che l'artefatto sia registrato come conseguenza dell'esecuzione
        consequences = ctrl.causal_graph.get_forward_consequences(f"exec:{mid}:process-code:1")
        effect_nodes = [c[0] for c in consequences]
        self.assertIn(f"artifact:{mid}:index.html", effect_nodes)
        self.assertIn(f"verdict:{mid}:process-code:1", effect_nodes)

    def test_diagnose_root_cause_pinpoints_culprit_on_failure(self):
        mission = self.store.create("Broken Pipeline", ["passes"])
        mid = mission["id"]

        # fetch-data fallisce nel worker
        worker = FakeWorker(behaviors={"fetch-data": False})
        ctrl = self.controller(
            FakePlanner([sample_dag_plan()]),
            worker,
            FakeVerifier(task_verdicts={"fetch-data": "fail"}, mission_verdict="fail"),
        )

        summary = ctrl.run(mid)
        self.assertEqual(summary["status"], "failed")

        # Diagnosi di causa radice per il task
        diag = ctrl.diagnose_root_cause(mid, "fetch-data")
        self.assertIsNotNone(diag["suspected_culprit"])
        self.assertEqual(diag["suspected_culprit"]["model"], "LFM2.5-24B-ASUS")
        self.assertIn("error in fetch-data", diag["suspected_culprit"]["error"])

        # Diagnosi di causa radice per l'intera missione
        mission_diag = ctrl.diagnose_root_cause(mid)
        self.assertIsNotNone(mission_diag["root_cause_event"])
        self.assertGreater(mission_diag["failing_events_count"], 0)

    def test_export_mission_causal_subgraph(self):
        mission = self.store.create("SubGraph Test", ["clean"])
        mid = mission["id"]

        ctrl = self.controller(FakePlanner([sample_dag_plan()]), FakeWorker(), FakeVerifier())
        ctrl.run(mid)

        subgraph = ctrl.export_mission_causal_subgraph(mid)
        self.assertEqual(subgraph["mission_id"], mid)
        self.assertGreaterEqual(subgraph["total_nodes"], 4)
        self.assertGreaterEqual(subgraph["total_edges"], 3)
        self.assertTrue(all(mid in n for n in subgraph["nodes"]))

    def test_causal_graph_tracks_replan_recovery(self):
        mission = self.store.create("Replan Recovery Mission", ["passes"])
        mid = mission["id"]

        # Piano iniziale: [t1]
        plan1 = [{"key": "t1", "role": "worker", "title": "T1", "instruction": "do t1"}]
        # Piano di replan: [t2]
        plan2 = [{"key": "t2", "role": "worker", "title": "T2", "instruction": "do t2"}]

        planner = FakePlanner([plan1, plan2])
        worker = FakeWorker()
        verifier = FakeVerifier(task_verdicts={"t1": "replan", "t2": "pass"})

        ctrl = self.controller(planner, worker, verifier)
        summary = ctrl.run(mid)
        self.assertEqual(summary["status"], "done")

        # Verifica che il nodo replan sia presente e abbia causato t2
        subgraph = ctrl.export_mission_causal_subgraph(mid)
        nodes = subgraph["nodes"]
        replan_nodes = [n for n in nodes if f"replan:{mid}:" in n]
        self.assertGreaterEqual(len(replan_nodes), 1)

        t2_causes = [c[0] for c in self.cmg.trace_lineage(f"task:{mid}:t2")]
        self.assertIn(replan_nodes[0], t2_causes)


if __name__ == "__main__":
    unittest.main()
