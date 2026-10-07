# SPDX-License-Identifier: Apache-2.0
import json
import tempfile
import unittest
from pathlib import Path

from shared.mission import MissionStore, validate_dag


PLAN = [
    {"key": "recon", "role": "repo-analyst", "title": "Recon",
     "instruction": "find the seam"},
    {"key": "code", "role": "coder", "title": "Change",
     "instruction": "write the change", "dependencies": ["recon"]},
    {"key": "verify", "role": "verifier", "title": "Verify",
     "instruction": "run the tests", "dependencies": ["code"]},
]


class MissionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = MissionStore(self.temp.name, clock=lambda: 1_700_000_000)

    def _mission(self):
        return self.store.create("Make the thing faster", ["p95 under 200ms"],
                                 budget={"max_steps": 12}, policy={"concurrency": 1})

    def test_create_persists_objective_criteria_and_provenance(self):
        mission = self._mission()
        self.assertTrue(mission["id"].startswith("mission-"))
        self.assertEqual(mission["status"], "planned")
        self.assertEqual(mission["success_criteria"], ["p95 under 200ms"])
        self.assertTrue(mission["trace_id"].startswith("trace-"))
        reloaded = MissionStore(self.temp.name).get(mission["id"])
        self.assertEqual(reloaded["objective"], "Make the thing faster")

    def test_plan_is_validated_and_dependencies_gate_readiness(self):
        mission = self._mission()
        self.store.set_plan(mission["id"], PLAN)
        self.assertEqual([t["task_id"] for t in self.store.ready_tasks(mission["id"])], ["recon"])
        self.store.claim(mission["id"], "recon")
        self.store.complete(mission["id"], "recon", output="seam found")
        self.assertEqual([t["task_id"] for t in self.store.ready_tasks(mission["id"])], ["code"])

    def test_claim_is_atomic_and_counts_attempts(self):
        mission = self._mission()
        self.store.set_plan(mission["id"], PLAN)
        claimed = self.store.claim(mission["id"], "recon")
        self.assertEqual(claimed["status"], "running")
        self.assertEqual(claimed["attempts"], 1)
        self.assertIsNone(self.store.claim(mission["id"], "recon"))

    def test_claim_refuses_task_with_unfinished_dependency(self):
        mission = self._mission()
        self.store.set_plan(mission["id"], PLAN)
        self.assertIsNone(self.store.claim(mission["id"], "code"))

    def test_fail_retries_until_max_attempts_then_gives_up(self):
        mission = self._mission()
        self.store.set_plan(mission["id"], PLAN)
        self.store.claim(mission["id"], "recon")
        self.assertEqual(self.store.fail(mission["id"], "recon", "boom", retry=True)["status"], "pending")
        self.store.claim(mission["id"], "recon")
        self.assertEqual(self.store.fail(mission["id"], "recon", "boom", retry=True)["status"], "failed")


    def test_replan_appends_tasks_and_bumps_counter(self):
        mission = self._mission()
        self.store.set_plan(mission["id"], PLAN)
        self.store.add_replan(mission["id"], [
            {"key": "extra", "role": "coder", "title": "Fix", "instruction": "again"}
        ])
        reloaded = self.store.get(mission["id"])
        self.assertEqual(reloaded["counters"]["replans"], 1)
        self.assertIn("extra", [t["task_id"] for t in reloaded["tasks"]])
        with self.assertRaises(ValueError):
            self.store.add_replan(mission["id"], [{"key": "extra", "instruction": "dupe"}])

    def test_summary_and_finish_track_terminal_state(self):
        mission = self._mission()
        self.store.set_plan(mission["id"], [{"key": "only", "instruction": "do it"}])
        self.store.claim(mission["id"], "only")
        self.store.complete(mission["id"], "only")
        summary = self.store.summary(mission["id"])
        self.assertTrue(summary["all_terminal"])
        self.store.finish(mission["id"], "done")
        self.assertEqual(self.store.get(mission["id"])["status"], "done")
        self.assertEqual(self.store.status()["by_status"]["done"], 1)

    def test_cancel_skips_open_tasks_and_is_terminal(self):
        mission = self._mission()
        self.store.set_plan(mission["id"], PLAN)
        cancelled = self.store.cancel(mission["id"], "operator stopped it")
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertTrue(all(t["status"] == "skipped" for t in cancelled["tasks"]))

    def test_review_never_applies_and_records_reviewer(self):
        mission = self._mission()
        reviewed = self.store.review(mission["id"], "approve", "alice", "diff inspected")
        self.assertFalse(reviewed["reviews"][0]["applied"])
        self.assertEqual(reviewed["reviews"][0]["reviewer"], "alice")
        with self.assertRaises(ValueError):
            self.store.review(mission["id"], "approve", "alice", "")

    def test_unknown_mission_raises_key_error(self):
        with self.assertRaises(KeyError):
            self.store.finish("mission-missing", "done")

    def test_state_survives_restart(self):
        mission = self._mission()
        self.store.set_plan(mission["id"], PLAN)
        self.store.claim(mission["id"], "recon")
        fresh = MissionStore(self.temp.name)
        self.assertEqual(fresh.get(mission["id"])["tasks"][0]["status"], "running")
        self.assertEqual(len(fresh.list()), 1)

    def test_journal_is_jsonl_backed(self):
        mission = self._mission()
        self.store.finish(mission["id"], "done")
        lines = Path(self.temp.name, "missions.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(json.loads(lines[-1])["status"], "done")


class DagValidationTests(unittest.TestCase):
    def test_cycle_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_dag([{"key": "a", "dependencies": ["b"]},
                          {"key": "b", "dependencies": ["a"]}])

    def test_unknown_dependency_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_dag([{"key": "a", "dependencies": ["ghost"]}])

    def test_self_dependency_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_dag([{"key": "a", "dependencies": ["a"]}])

    def test_duplicate_and_empty_plans_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_dag([{"key": "a"}, {"key": "a"}])
        with self.assertRaises(ValueError):
            validate_dag([])


if __name__ == "__main__":
    unittest.main()
