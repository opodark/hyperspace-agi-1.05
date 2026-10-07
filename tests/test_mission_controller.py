# SPDX-License-Identifier: Apache-2.0
import tempfile
import threading
import unittest

from shared import mission_policy
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
        self.calls = {}

    def __call__(self, task, mission):
        count = self.calls.get(task["task_id"], 0)
        self.calls[task["task_id"]] = count + 1
        sequence = self.behaviors.get(task["task_id"])
        ok = self.default_ok if sequence is None else sequence[min(count, len(sequence) - 1)]
        return {"ok": ok, "output": "out", "error": "" if ok else "boom",
                "artifacts": self.artifacts.get(task["task_id"], []),
                "model": "fake-model", "target": "local", "tokens": 10}


class FakeVerifier:
    def __init__(self, task_verdicts=None, mission_verdict="pass"):
        self.task_verdicts = list(task_verdicts or [])
        self.mission_verdict = mission_verdict
        self.mission_calls = 0

    def __call__(self, scope, *, mission, task=None, outcome=None):
        if scope == "mission":
            self.mission_calls += 1
            return {"verdict": self.mission_verdict, "reason": "mission verdict"}
        verdict = self.task_verdicts.pop(0) if self.task_verdicts else "pass"
        return {"verdict": verdict, "reason": f"verdict for {task['task_id']}"}


def linear_plan():
    return [
        {"key": "a", "role": "repo-analyst", "title": "A", "instruction": "a"},
        {"key": "b", "role": "coder", "title": "B", "instruction": "b", "dependencies": ["a"]},
    ]


class MissionControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = MissionStore(self.temp.name, clock=NOW)

    def controller(self, planner, worker, verifier, **budget_overrides):
        budget = mission_policy.parse_budget(env={}, overrides=budget_overrides)
        return MissionController(self.store, planner=planner, worker=worker,
                                 verifier=verifier, budget=budget, clock=NOW)

    def mission(self):
        return self.store.create("Ship feature X", ["tests pass"])

    def test_happy_path_runs_the_dag_to_done(self):
        mission = self.mission()
        worker = FakeWorker()
        controller = self.controller(FakePlanner([linear_plan()]), worker, FakeVerifier())
        summary = controller.run(mission["id"])
        self.assertEqual(summary["status"], "done")
        self.assertEqual(summary["tasks"], {"done": 2})
        self.assertEqual(set(worker.calls), {"a", "b"})
        self.assertFalse(controller.running)

    def test_worker_failure_is_retried_then_succeeds(self):
        mission = self.mission()
        worker = FakeWorker(behaviors={"a": [False, True]})
        controller = self.controller(FakePlanner([linear_plan()]), worker, FakeVerifier())
        summary = controller.run(mission["id"])
        self.assertEqual(summary["status"], "done")
        self.assertEqual(worker.calls["a"], 2)

    def test_worker_failure_beyond_max_attempts_fails_the_task_and_mission(self):
        mission = self.mission()
        worker = FakeWorker(behaviors={"a": [False, False, False]})
        controller = self.controller(FakePlanner([linear_plan()]), worker,
                                     FakeVerifier(mission_verdict="fail"))
        summary = controller.run(mission["id"])
        self.assertEqual(summary["status"], "failed")
        self.assertEqual(worker.calls["a"], 2)
        tasks = {t["task_id"]: t["status"] for t in self.store.get(mission["id"])["tasks"]}
        self.assertEqual(tasks["a"], "failed")
        self.assertEqual(tasks["b"], "skipped")  # dependent of a failed task

    def test_replan_adds_tasks_and_can_recover(self):
        mission = self.mission()
        planner = FakePlanner([linear_plan(),
                               [{"key": "extra", "role": "coder", "title": "Fix", "instruction": "fix"}]])
        verifier = FakeVerifier(task_verdicts=["replan"])
        controller = self.controller(planner, FakeWorker(), verifier)
        summary = controller.run(mission["id"])
        self.assertEqual(summary["status"], "done")
        self.assertEqual(summary["counters"]["replans"], 1)
        self.assertEqual(planner.reasons[1], "verdict for a")

    def test_mission_verifier_replan_respects_replan_budget(self):
        mission = self.mission()
        controller = self.controller(FakePlanner([linear_plan(), []]), FakeWorker(),
                                     FakeVerifier(mission_verdict="replan"), max_replans=0)
        summary = controller.run(mission["id"])
        self.assertEqual(summary["status"], "failed")
        self.assertIsNotNone(self.store.get(mission["id"])["finished_at"])

    def test_invalid_plan_fails_the_mission(self):
        mission = self.mission()
        planner = FakePlanner([[{"key": "x", "dependencies": ["y"]}, {"key": "y", "dependencies": ["x"]}]])
        controller = self.controller(planner, FakeWorker(), FakeVerifier())
        summary = controller.run(mission["id"])
        self.assertEqual(summary["status"], "failed")
        self.assertIn("cycle", self.store.get(mission["id"])["error"])

    def test_budget_steps_exhaustion_stops_the_mission(self):
        mission = self.mission()
        plan = [{"key": f"t{i}", "role": "worker", "instruction": "work"} for i in range(5)]
        controller = self.controller(FakePlanner([plan]), FakeWorker(), FakeVerifier(),
                                     max_steps=1)
        summary = controller.run(mission["id"])
        self.assertEqual(summary["status"], "failed")
        self.assertIn("budget exhausted", self.store.get(mission["id"])["error"])

    def test_plan_and_replan_share_one_budget_replan_counter(self):
        mission = self.mission()
        controller = self.controller(FakePlanner([linear_plan()]), FakeWorker(), FakeVerifier())
        controller.run(mission["id"])
        self.assertEqual(self.store.get(mission["id"])["counters"]["replans"], 0)



class MissionControllerRobustnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = MissionStore(self.temp.name, clock=NOW)

    def controller(self, planner, worker, verifier, **budget_overrides):
        budget = mission_policy.parse_budget(env={}, overrides=budget_overrides)
        return MissionController(self.store, planner=planner, worker=worker,
                                 verifier=verifier, budget=budget, clock=NOW)

    def mission(self):
        return self.store.create("Ship feature X", ["tests pass"])

    def test_cancel_mid_run_stops_the_mission(self):
        mission = self.mission()
        store = self.store

        def worker(task, current):
            store.cancel(current["id"], "operator hit the kill switch")
            return {"ok": True, "output": "out"}

        controller = self.controller(FakePlanner([linear_plan()]), worker, FakeVerifier())
        summary = controller.run(mission["id"])
        self.assertEqual(summary["status"], "cancelled")

    def test_two_independent_tasks_run_concurrently_up_to_the_cap(self):
        mission = self.mission()
        barrier = threading.Barrier(2, timeout=5)

        def worker(task, current):
            barrier.wait()
            return {"ok": True, "output": "out"}

        plan = [{"key": "l", "role": "worker", "instruction": "l"},
                {"key": "r", "role": "worker", "instruction": "r"}]
        controller = self.controller(FakePlanner([plan]), worker, FakeVerifier(), max_concurrency=2)
        summary = controller.run(mission["id"])
        self.assertEqual(summary["status"], "done")
        self.assertEqual(summary["tasks"], {"done": 2})

    def test_concurrency_is_clamped_by_the_ceiling(self):
        controller = self.controller(FakePlanner([linear_plan()]), FakeWorker(), FakeVerifier(),
                                     max_concurrency=999)
        self.assertEqual(controller.budget["max_concurrency"], mission_policy.MAX_CONCURRENCY_CEILING)

    def test_review_gated_artifacts_stay_pending_and_unapplied(self):
        mission = self.mission()
        worker = FakeWorker(artifacts={"b": [{"kind": "diff", "path": "a.py"}]})
        controller = self.controller(FakePlanner([linear_plan()]), worker, FakeVerifier())
        controller.run(mission["id"])
        after = self.store.get(mission["id"])
        pending = controller.pending_review(after)
        self.assertEqual([t["task_id"] for t in pending], ["b"])
        self.assertNotIn("applied", after["tasks"][1])
        self.store.review(mission["id"], "approve", "alice", "reviewed the diff")
        self.assertEqual(controller.pending_review(self.store.get(mission["id"])), [])

    def test_resume_from_disk_continues_a_planned_mission(self):
        mission = self.mission()
        self.store.set_plan(mission["id"], linear_plan())
        self.store.claim(mission["id"], "a")
        fresh = MissionStore(self.temp.name, clock=NOW)
        controller = MissionController(fresh, planner=FakePlanner([]), worker=FakeWorker(),
                                       verifier=FakeVerifier(),
                                       budget=mission_policy.parse_budget(env={}), clock=NOW)
        summary = controller.run(mission["id"])
        self.assertEqual(summary["status"], "done")

    def test_events_are_emitted_for_observability(self):
        mission = self.mission()
        events = []
        controller = MissionController(
            self.store, planner=FakePlanner([linear_plan()]), worker=FakeWorker(),
            verifier=FakeVerifier(), budget=mission_policy.parse_budget(env={}), clock=NOW,
            on_event=lambda event, mission_id, detail: events.append(event))
        controller.run(mission["id"])
        self.assertIn("plan", events)
        self.assertIn("task_done", events)
        self.assertIn("mission_end", events)

    def test_terminal_mission_is_not_rerun(self):
        mission = self.mission()
        self.store.finish(mission["id"], "done")
        controller = self.controller(FakePlanner([linear_plan()]), FakeWorker(), FakeVerifier())
        self.assertEqual(controller.run(mission["id"])["status"], "done")


if __name__ == "__main__":
    unittest.main()

