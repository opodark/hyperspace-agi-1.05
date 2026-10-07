# SPDX-License-Identifier: Apache-2.0
"""Behavioral regressions from the 2026-10-07 review; no live tools/models."""

import ast
import json
import runpy
import tempfile
import time
import unittest
from pathlib import Path

from shared import mission_policy
from shared.mission import MissionStore, task_review_status
from shared.mission_controller import MissionController
from shared.tool_runtime import Invocation, ExecutionStopped

ROOT = Path(__file__).resolve().parents[1]
HARNESS = runpy.run_path(str(ROOT / "tests/test_tool_passthrough.py"))


def extracted(names, scope):
    source = ROOT / "control-plane/main.py"
    nodes = [
        n
        for n in ast.parse(source.read_text()).body
        if isinstance(n, ast.FunctionDef) and n.name in names
    ]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), scope)
    return scope


class InvocationTests(unittest.TestCase):
    def run_calls(self, names, execution=None, offered=None):
        ns = HARNESS["carica"](
            [
                HARNESS["risposta_con_tool_calls"](*names),
                HARNESS["risposta_testo"]("done"),
            ]
        )
        ns["_run_tool_loop"](
            {"model": "fake", "messages": []},
            "http://unused",
            builtin_tools=offered or [HARNESS["CATALOGO_FINTO"][0]],
            execution=execution,
        )
        return ns["_registrato"]

    def test_unoffered_native_tool_cannot_reach_handler(self):
        log = self.run_calls(["shell_run"])
        self.assertEqual(log["nativi"], [])
        self.assertEqual(log["connettore"].chiamate, [])
        self.assertIn("not allowed", log["ollama"][1]["messages"][-1]["content"])

    def test_client_cannot_smuggle_a_native_tool_into_restricted_role(self):
        ns = HARNESS["carica"](
            [
                HARNESS["risposta_con_tool_calls"]("shell_run"),
                HARNESS["risposta_testo"]("done"),
            ]
        )
        ns["_run_tool_loop"](
            {
                "model": "fake",
                "messages": [],
                "tools": [{"type": "function", "function": {"name": "shell_run"}}],
            },
            "http://unused",
            builtin_tools=[HARNESS["CATALOGO_FINTO"][0]],
        )
        self.assertEqual(ns["_registrato"]["nativi"], [])

    def test_verifier_actions_are_enforced_at_tool_dispatch(self):
        for action in ["write", "replace", "run", "discard", "create"]:
            with self.subTest(action=action):
                response = HARNESS["risposta_con_tool_calls"]("code_sandbox")
                response["choices"][0]["message"]["tool_calls"][0]["function"][
                    "arguments"
                ] = json.dumps({"action": action})
                ns = HARNESS["carica"]([response, HARNESS["risposta_testo"]("blocked")])
                ns["_run_tool_loop"](
                    {"model": "fake", "messages": []},
                    "http://unused",
                    builtin_tools=[{"function": {"name": "code_sandbox"}}],
                    execution=Invocation(role="verifier"),
                )
                self.assertEqual(ns["_registrato"]["nativi"], [])
        args = Invocation(role="verifier").authorize(
            "code_sandbox",
            {"action": "check"},
            [{"function": {"name": "code_sandbox"}}],
        )
        self.assertEqual(args["action"], "check")

    def test_malformed_arguments_do_not_turn_into_empty_object(self):
        ctx = Invocation()
        for args in ["{broken", "[]", [], None]:
            with self.assertRaises(ValueError):
                ctx.authorize("web_search", args, HARNESS["CATALOGO_FINTO"])

    def test_budget_is_cumulative_and_missing_usage_is_not_free(self):
        ctx = Invocation(max_tokens=10)
        payload = ctx.model_payload({})
        self.assertEqual(payload["max_tokens"], 10)
        self.assertEqual(payload["options"]["num_predict"], 10)
        ctx.model_result({"usage": {"completion_tokens": 6}}, payload)
        self.assertEqual(ctx.model_payload({})["max_tokens"], 4)
        ctx.model_result({}, ctx.model_payload({}))
        self.assertFalse(ctx.usage_known)
        with self.assertRaises(ExecutionStopped):
            ctx.model_payload({})

    def test_transport_failure_reserves_unknown_usage(self):
        ctx = Invocation(max_tokens=20)
        payload = ctx.model_payload({})
        ctx.model_failed(payload)
        self.assertFalse(ctx.usage_known)
        self.assertEqual(ctx.reserved_tokens, 20)
        with self.assertRaises(ExecutionStopped):
            ctx.model_payload({})

    def test_cancelled_or_expired_context_never_dispatches(self):
        for context in [
            Invocation(cancelled=lambda: True),
            Invocation(deadline=time.time() - 1),
        ]:
            with self.assertRaises(ExecutionStopped):
                context.authorize("web_search", {}, HARNESS["CATALOGO_FINTO"])
            ns = HARNESS["carica"]([HARNESS["risposta_testo"]("never")])
            result = ns["_run_tool_loop"](
                {"model": "fake"}, "http://unused", execution=context
            )
            self.assertIn("error", result)
            self.assertEqual(ns["_registrato"]["ollama"], [])

    def test_error_results_are_not_success_and_raw_secrets_not_logged(self):
        context = Invocation()
        self.assertFalse(context.record("check", {"ok": True, "passed": False}))
        self.assertFalse(context.results[-1]["ok"])
        ns = HARNESS["carica"](
            [
                HARNESS["risposta_con_tool_calls"]("web_search"),
                HARNESS["risposta_testo"]("error"),
            ]
        )
        ns["_tool_web_search"] = lambda args: '{"ok":false,"error":"secret-sentinel"}'
        ns["_run_tool_loop"]({"model": "fake"}, "http://unused")
        log = ns["_registrato"]["log"]
        self.assertNotIn("secret-sentinel", str(log))
        self.assertTrue(
            any(
                "tool_result" in str(args) and kw.get("status") == "warn"
                for args, kw in log
            )
        )


class MissionContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = MissionStore(self.tmp.name)

    def controller(self, plan, worker=None, **limits):
        return MissionController(
            self.store,
            planner=lambda *a: plan,
            worker=worker or (lambda *a: {"ok": True, "output": "done"}),
            verifier=lambda *a, **kw: {"verdict": "pass"},
            budget=mission_policy.parse_budget(env={}, overrides=limits),
        )

    def test_mission_budget_caps_parallel_claims_and_does_not_leak_to_next_run(self):
        plan = [{"key": "a", "instruction": "one"}, {"key": "b", "instruction": "two"}]
        calls = []
        ctrl = self.controller(
            plan,
            lambda t, m: (
                calls.append((t["task_id"], m["_execution_budget"]["max_steps"]))
                or {"ok": True}
            ),
            max_steps=10,
        )
        mission = self.store.create(
            "test", budget={"max_steps": 1, "max_concurrency": 1}
        )
        self.assertEqual(ctrl.run(mission["id"])["status"], "failed")
        self.assertEqual(calls, [("a", 1)])
        calls.clear()
        other = self.store.create("test", budget={"max_steps": 100})
        self.assertEqual(ctrl.run(other["id"])["status"], "done")
        self.assertTrue(all(b == 10 for _, b in calls))
        self.assertEqual(ctrl.budget["max_steps"], 10)

    def test_failed_attempts_count_usage_and_stop_at_task_cap(self):
        calls = []

        def worker(task, mission):
            calls.append(task["task_id"])
            return {
                "ok": False,
                "error": "transport",
                "tokens": 7,
                "charged_tokens": 256,
                "usage_known": False,
            }

        mission = self.store.create("test", budget={"max_tokens_per_task": 256})
        ctrl = self.controller(
            [{"key": "a", "instruction": "one", "max_attempts": 5}], worker
        )
        ctrl.run(mission["id"])
        saved = self.store.get(mission["id"])
        self.assertEqual(calls, ["a"])
        self.assertEqual(saved["counters"]["tokens"], 7)
        self.assertEqual(saved["tasks"][0]["charged_tokens"], 256)
        self.assertFalse(saved["tasks"][0]["usage_known"])

    def test_task_attempt_budget_cannot_be_raised_by_the_plan(self):
        calls = []

        def worker(task, mission):
            calls.append(task["task_id"])
            return {"ok": False, "error": "failed"}

        mission = self.store.create("test", budget={"max_task_attempts": 1})
        self.controller(
            [{"key": "a", "instruction": "one", "max_attempts": 5}], worker
        ).run(mission["id"])
        self.assertEqual(calls, ["a"])

    def test_exact_task_limit_can_finish_but_cannot_start_an_extra_attempt(self):
        mission = self.store.create("test", budget={"max_steps": 1})
        ctrl = self.controller([{"key": "a", "instruction": "one"}])
        self.assertEqual(ctrl.run(mission["id"])["status"], "done")
        self.assertEqual(self.store.get(mission["id"])["counters"]["steps"], 1)

    def test_resume_keeps_elapsed_budget(self):
        mission = self.store.create("test", budget={"max_wall_seconds": 30})
        self.store.record_runtime(mission["id"], 31)
        ctrl = self.controller([{"key": "a", "instruction": "one"}])
        self.assertEqual(ctrl.run(mission["id"])["status"], "failed")
        self.assertEqual(self.store.get(mission["id"])["counters"]["steps"], 0)

    def test_reviews_bind_action_and_artifact_version(self):
        m = self.store.create("test")
        self.store.set_plan(
            m["id"], [{"key": "a", "role": "coder", "instruction": "code"}]
        )
        self.store.claim(m["id"], "a")
        self.store.complete(m["id"], "a", artifacts=[{"diff": "v1"}])
        ctrl = self.controller([])
        for action in ["defer", "reopen", "reject", "approve"]:
            reviewed = self.store.review(m["id"], action, "operator", "reason")
            self.assertEqual(task_review_status(reviewed, reviewed["tasks"][0]), action)
            self.assertEqual(
                len(ctrl.pending_review(reviewed)), 0 if action == "approve" else 1
            )
        self.store.complete(m["id"], "a", artifacts=[{"diff": "v2"}])
        self.assertEqual(len(ctrl.pending_review(self.store.get(m["id"]))), 1)
        self.store.review(m["id"], "approve", "operator", "review v2")
        self.store.add_replan(
            m["id"], [{"key": "b", "role": "coder", "instruction": "more"}]
        )
        self.store.claim(m["id"], "b")
        self.store.complete(m["id"], "b", artifacts=[{"diff": "v3"}])
        self.assertEqual(
            [t["task_id"] for t in ctrl.pending_review(self.store.get(m["id"]))], ["b"]
        )

    def test_criteria_reach_planner_worker_and_both_verification_prompts(self):
        prompts = []
        ns = extracted(
            {"_mission_plan", "_mission_verify", "_mission_task_digest"},
            {
                "mission_policy": mission_policy,
                "json": json,
                "_mission_budget": lambda: mission_policy.parse_budget(env={}),
                "_mission_roles_hint": lambda: "worker",
                "_mission_reasoning": lambda *a: (False, ""),
                "_mission_llm": lambda prompt, *a, **kw: (
                    prompts.append(prompt) or "{}"
                ),
                "_mission_json": json.loads,
                "MISSION_MODEL": "fake",
                "MISSION_PLANNER_MODEL": "fake",
                "push_log": lambda *a, **kw: None,
            },
        )
        mission = self.store.create("test", ["CRITERION_SENTINEL"])
        ns["_mission_plan"](mission)
        self.assertIn("CRITERION_SENTINEL", prompts[-1])
        for scope in ["task", "mission"]:
            verdict = ns["_mission_verify"](
                scope,
                mission,
                task={"task_id": "a", "role": "worker"},
                outcome={"ok": True, "output": "claimed success"},
            )
            self.assertIn("CRITERION_SENTINEL", prompts[-1])
            self.assertNotEqual(verdict["verdict"], "pass")
            self.assertFalse(verdict["verified"])
        harness = runpy.run_path(str(ROOT / "tests/test_mission_routes.py"))
        cls = harness["MissionWorkerFailureTests"]
        seen = []
        cls.worker(cls.LOOP, seen=seen)(cls.TASK, mission)
        self.assertIn("CRITERION_SENTINEL", str(seen[0]["messages"]))

    def test_coder_without_evidence_is_not_verified_even_with_a_friendly_model(self):
        ns = extracted({"_mission_verify"}, {})
        result = ns["_mission_verify"](
            "task",
            {},
            task={"role": "coder"},
            outcome={"ok": True, "output": "everything works"},
        )
        self.assertEqual(result["verdict"], "retry")
        self.assertFalse(result["verified"])


if __name__ == "__main__":
    unittest.main()
