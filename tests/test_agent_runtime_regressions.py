# SPDX-License-Identifier: Apache-2.0
"""Behavioral regressions from the 2026-10-07 review; no live tools/models."""

import ast
import json
import re
import runpy
import tempfile
import time
import unittest
from pathlib import Path

from shared import mission_policy
from shared.mission import MissionStore, task_review_status
from shared.mission_controller import MissionController
from shared.tool_runtime import Invocation, ExecutionStopped

from tests import cp_source

ROOT = Path(__file__).resolve().parents[1]
HARNESS = runpy.run_path(str(ROOT / "tests/test_tool_passthrough.py"))


def extracted(names, scope):
    nodes = [
        n
        for n in cp_source.albero().body
        if isinstance(n, ast.FunctionDef) and n.name in names
    ]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<extracted>", "exec"), scope)
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

    def test_a_chain_reuses_the_upstream_workspace_instead_of_creating_one(self):
        """La seconda `create` di una catena diventa `reuse`: niente sandbox nuovo.

        Il prompt lo chiede al modello, ma un 8B ricrea il workspace a ogni task e
        il PDF finisce in un sandbox diverso da quello verificato (misurato il
        2026-10-07). Qui il riuso è forzato nel runtime, non affidato al modello.
        """
        offered = [{"function": {"name": "code_sandbox"}}]
        ctx = Invocation(role="worker", workspace_id="docker:abc-123")
        args = ctx.authorize("code_sandbox", {"action": "create", "label": "x"}, offered)
        self.assertEqual(args, {"action": "reuse", "workspace_id": "docker:abc-123"})

    def test_a_chain_forces_its_workspace_id_on_every_work_action(self):
        offered = [{"function": {"name": "code_sandbox"}}]
        ctx = Invocation(role="worker", workspace_id="docker:abc-123")
        for action in ["list", "read", "write", "replace", "run", "diff",
                       "inspect", "check", "verify"]:
            with self.subTest(action=action):
                args = ctx.authorize(
                    "code_sandbox",
                    {"action": action, "workspace_id": "docker:wrong", "path": "a.txt"},
                    offered,
                )
                self.assertEqual(args["workspace_id"], "docker:abc-123")
                self.assertEqual(args["action"], action)

    def test_global_or_destructive_actions_are_not_hijacked_by_the_chain(self):
        offered = [{"function": {"name": "code_sandbox"}}]
        ctx = Invocation(role="worker", workspace_id="docker:abc-123")
        self.assertEqual(ctx.authorize("code_sandbox", {"action": "status"}, offered),
                         {"action": "status"})
        discard = ctx.authorize(
            "code_sandbox", {"action": "discard", "workspace_id": "docker:mine"}, offered)
        self.assertEqual(discard["workspace_id"], "docker:mine")

    def test_without_an_upstream_workspace_the_first_create_is_untouched(self):
        offered = [{"function": {"name": "code_sandbox"}}]
        ctx = Invocation(role="worker")
        self.assertEqual(ctx.authorize("code_sandbox", {"action": "create"}, offered),
                         {"action": "create"})

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

    def test_temperature_travels_in_the_openai_field_too(self):
        """`options` e' la forma di Ollama: un backend OpenAI-compatibile la ignora.

        Misurato il 2026-10-08 su Bonsai 2 27B (llama-server): il planner della
        missione chiedeva temperature=0.2 ma girava col sampling del server
        (temp 1.0), e a volte rispondeva senza il JSON del piano ("invalid plan").
        La temperatura deve viaggiare anche nel campo di primo livello.
        """
        ctx = Invocation(max_tokens=10)
        payload = ctx.model_payload(
            {"options": {"temperature": 0.2}, "messages": []})
        self.assertEqual(payload["temperature"], 0.2)
        # Un valore già al primo livello non viene toccato.
        payload = ctx.model_payload(
            {"temperature": 0.9, "options": {"temperature": 0.2}})
        self.assertEqual(payload["temperature"], 0.9)
        # Nessuna temperatura non e' un caso da inventare.
        self.assertNotIn("temperature", ctx.model_payload({"options": {}}))


    def test_transport_failure_reserves_unknown_usage(self):
        ctx = Invocation(max_tokens=20)
        payload = ctx.model_payload({})
        ctx.model_failed(payload)
        self.assertFalse(ctx.usage_known)
        self.assertEqual(ctx.reserved_tokens, 20)
        with self.assertRaises(ExecutionStopped):
            ctx.model_payload({})

    def test_transient_ollama_error_retries_with_tools_and_spares_the_budget(self):
        """Un errore transitorio (modello non ancora caricato) non brucia il budget.

        Il 2026-10-08 il worker e' morto su "task output-token budget exhausted"
        mentre l'errore vero era "timed out waiting for llama-server to start":
        il body d'errore (senza `usage`) veniva contato come se il modello avesse
        consumato l'intero budget, e il retry senza tool moriva subito. Qui il
        retry deve riprovare CON i tool e non contare l'errore nel budget.
        """
        errore = {"error": {"message": "timed out waiting for llama-server to start - ",
                            "type": "api_error", "param": None, "code": None}}
        tool_call = {"id": "c1", "choices": [{"index": 0, "finish_reason": "tool_calls",
                     "message": {"role": "assistant", "content": "",
                                 "tool_calls": [{"id": "t1", "type": "function",
                                                 "function": {"name": "web_search",
                                                              "arguments": json.dumps({"prompt": "x"})}}]}}],
                     "usage": {"completion_tokens": 5}}
        testo = {"id": "c2", "choices": [{"index": 0, "finish_reason": "stop",
                 "message": {"role": "assistant", "content": "done"}}],
                 "usage": {"completion_tokens": 5}}
        ns = HARNESS["carica"]([errore, tool_call, testo])
        execution = Invocation(max_tokens=100)
        ns["_run_tool_loop"](
            {"model": "fake", "messages": []}, "http://unused",
            builtin_tools=[HARNESS["CATALOGO_FINTO"][0]], execution=execution)
        self.assertEqual([n for n, _ in ns["_registrato"]["nativi"]], ["web_search"],
                         "il retry deve avvenire CON i tool, non degradare a prosa")
        self.assertEqual(execution.reserved_tokens, 10,
                         "l'errore non deve consumare budget: contano solo i token reali")
        self.assertTrue(execution.usage_known,
                        "un errore non ha generato nulla: l'usage resta noto")

    def test_does_not_support_tools_still_falls_back_without_tools(self):
        """Il solo errore che degrada a no-tools e' 'does not support tools'."""
        errore = {"error": {"message": "modello-finto does not support tools",
                            "type": "api_error"}}
        testo = {"id": "c2", "choices": [{"index": 0, "finish_reason": "stop",
                 "message": {"role": "assistant", "content": "done"}}],
                 "usage": {"completion_tokens": 5}}
        ns = HARNESS["carica"]([errore, testo])
        ns["_run_tool_loop"](
            {"model": "fake", "messages": []}, "http://unused",
            builtin_tools=[HARNESS["CATALOGO_FINTO"][0]])
        payloads = ns["_registrato"]["ollama"]
        self.assertEqual(len(payloads), 2)
        self.assertIn("tools", payloads[0])
        self.assertNotIn("tools", payloads[1],
                         "il retry senza tool non deve offrire i tool")

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
            {"_mission_plan", "_mission_verify", "_mission_task_digest",
             "_mission_role_allowed"},
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

    def test_a_bad_pdf_cannot_be_passed_by_a_friendly_verifier(self):
        """Il gate indipendente batte il modello: niente `pass` su un finto PDF."""
        ns = extracted(
            {"_mission_verify", "_mission_task_digest"},
            {
                "json": json,
                "_mission_reasoning": lambda *a: (False, ""),
                "_mission_llm": lambda *a, **kw: '{"verdict": "pass", "reason": "looks good"}',
                "_mission_json": json.loads,
                "MISSION_MODEL": "fake",
                # Il gate vero interrogherebbe il runner; qui si inietta il verdetto
                # negativo per isolare l'override di `_mission_verify`.
                "_mission_pdf_gate": lambda mission, artifacts, *a: {
                    "ok": False, "reason": "PDF artifact not verified", "checked": [],
                },
            },
        )
        artifacts = [{"workspace_id": "w-1", "changed_files": ["brief.pdf"]}]
        mission = {"objective": "Produce a PDF briefing",
                   "success_criteria": ["a readable PDF"],
                   "tasks": [{"task_id": "a", "role": "coder", "artifacts": artifacts}]}
        task = {"task_id": "a", "role": "coder", "instruction": "write the PDF"}
        outcome = {"ok": True, "output": "done", "artifacts": artifacts}

        task_verdict = ns["_mission_verify"]("task", mission, task=task, outcome=outcome)
        self.assertEqual(task_verdict["verdict"], "retry")
        self.assertFalse(task_verdict["verified"])
        self.assertEqual(task_verdict.get("gate"), "pdf")

        mission_verdict = ns["_mission_verify"]("mission", mission, task=task,
                                                outcome=outcome)
        self.assertEqual(mission_verdict["verdict"], "fail")
        self.assertEqual(mission_verdict.get("gate"), "pdf")

    def test_an_intermediate_task_is_not_failed_by_the_pdf_gate(self):
        """Il gate PDF vincola la missione, non ogni task intermedio.

        Un task che crea solo il workspace non ha `.pdf` nel diff: a livello task
        il gate deve tacere (altrimenti la catena muore al primo passo, come il
        2026-10-07), mentre la missione resta bocciata finché non esiste un PDF.
        """

        class _Sandbox:
            enabled = True

            def call(self, action, args, timeout=None):
                raise AssertionError(
                    "il gate non deve interrogare il runner su un task senza PDF")

        ns = extracted(
            {"_mission_verify", "_mission_task_digest", "_mission_pdf_gate",
             "_mission_pdf_candidates", "_mission_expects_pdf"},
            {
                "json": json,
                "re": re,
                "_ARTIFACT_PDF": re.compile(r"\.pdf$", re.IGNORECASE),
                "code_sandbox": _Sandbox(),
                "_mission_reasoning": lambda *a: (False, ""),
                "_mission_llm": lambda *a, **kw: '{"verdict": "pass", "reason": "ok"}',
                "_mission_json": json.loads,
                "MISSION_MODEL": "fake",
            },
        )
        empty = {"workspace_id": "w-1", "changed_files": []}
        mission = {"objective": "Produce a PDF briefing",
                   "success_criteria": ["a readable PDF"],
                   "tasks": [{"task_id": "a", "role": "coder", "artifacts": [empty]}]}
        task = {"task_id": "a", "role": "coder", "instruction": "create a workspace"}
        outcome = {"ok": True, "output": "created", "artifacts": [empty]}

        task_verdict = ns["_mission_verify"]("task", mission, task=task, outcome=outcome)
        self.assertEqual(task_verdict["verdict"], "pass")

        mission_verdict = ns["_mission_verify"]("mission", mission, task=task,
                                                outcome=outcome)
        self.assertEqual(mission_verdict["verdict"], "fail")
        self.assertEqual(mission_verdict.get("gate"), "pdf")

    def test_a_mission_without_a_gate_keeps_the_model_verdict(self):
        ns = extracted(
            {"_mission_verify", "_mission_task_digest"},
            {
                "json": json,
                "_mission_reasoning": lambda *a: (False, ""),
                "_mission_llm": lambda *a, **kw: '{"verdict": "pass", "reason": "ok"}',
                "_mission_json": json.loads,
                "MISSION_MODEL": "fake",
                "_mission_pdf_gate": lambda mission, artifacts, *a: None,
            },
        )
        result = ns["_mission_verify"](
            "mission",
            {"objective": "Write a summary", "success_criteria": [],
             "tasks": [{"task_id": "a", "role": "worker",
                        "artifacts": [{"workspace_id": "w-1",
                                       "changed_files": ["notes.md"]}]}]},
            task={"task_id": "a", "role": "worker"},
            outcome={"ok": True, "output": "done"},
        )
        self.assertEqual(result["verdict"], "pass")

    def test_the_mission_verifier_sees_the_artifacts_and_the_gate_fact(self):
        """Il verdetto di missione poggia sui fatti del runner, non su un tabellone cieco.

        Misurato il 2026-10-08 con Bonsai 2 27B: PDF prodotto e gate superato, ma
        il verifier di missione ha risposto `fail` ("no PDF file was generated or
        verified in the sandbox workspace") perche' il prompt elencava solo
        chiave/stato/titolo dei task. Artifact ed esito del gate devono arrivare
        nel prompt.
        """
        prompts = []
        ns = extracted(
            {"_mission_verify", "_mission_task_digest"},
            {
                "json": json,
                "_mission_reasoning": lambda *a: (False, ""),
                "_mission_llm": lambda prompt, *a, **kw: (
                    prompts.append(prompt) or '{"verdict": "pass", "reason": "ok"}'),
                "_mission_json": json.loads,
                "MISSION_MODEL": "fake",
                "_mission_pdf_gate": lambda mission, artifacts, *a: {
                    "ok": True, "reason": "PDF artifact verified", "checked": []},
            },
        )
        mission = {
            "objective": "Produce a PDF",
            "success_criteria": ["a readable PDF"],
            "tasks": [{"task_id": "a", "role": "coder", "status": "done",
                       "title": "Build the PDF",
                       "artifacts": [{"workspace_id": "w-1",
                                      "changed_files": ["artifacts/docs-briefing.pdf"]}]}],
        }
        verdict = ns["_mission_verify"](
            "mission", mission, task={"task_id": "a", "role": "coder"},
            outcome={"ok": True, "output": "done"})
        self.assertEqual(verdict["verdict"], "pass")
        self.assertIn("artifacts/docs-briefing.pdf", prompts[-1])
        self.assertIn("Artifact gate", prompts[-1])
        self.assertIn("PASS", prompts[-1])

    def test_the_task_verifier_is_scoped_to_the_task_not_the_mission(self):
        """Un task intermedio non va bocciato perché manca il deliverable finale.

        Il verifier-model, guardando l'obiettivo della missione ("un PDF"), il
        2026-10-07 bocciava `create-workspace` per un PDF che arriva tre passi
        dopo. Il prompt deve dire esplicitamente di giudicare il SOLO task.
        """
        prompts = []
        ns = extracted(
            {"_mission_verify", "_mission_task_digest"},
            {
                "json": json,
                "_mission_reasoning": lambda *a: (False, ""),
                "_mission_llm": lambda prompt, *a, **kw: (
                    prompts.append(prompt) or '{"verdict": "pass", "reason": "ok"}'),
                "_mission_json": json.loads,
                "MISSION_MODEL": "fake",
                "_mission_pdf_gate": lambda *a: None,
            },
        )
        verdict = ns["_mission_verify"](
            "task",
            {"objective": "Produce a PDF briefing", "success_criteria": ["a PDF"]},
            task={"task_id": "a", "role": "worker", "instruction": "create a workspace"},
            outcome={"ok": True, "output": "created the workspace"},
        )
        self.assertEqual(verdict["verdict"], "pass")
        self.assertIn("Judge ONLY this single task", prompts[-1])
        self.assertIn("Do NOT", prompts[-1])

    def test_upstream_workspace_id_reaches_downstream_tasks(self):
        """Il workspace_id usa-e-getta deve viaggiare con la catena.

        Un task a valle scrive NELLO STESSO workspace creato a monte: se il modello
        omette l'id nella prosa, il contesto lo fornisce comunque dagli artifact (o,
        in mancanza, dall'evidence) del task completato.
        """
        ns = extracted({"_mission_task_context"}, {})
        upstream = {
            "task_id": "create-workspace", "key": "create-workspace",
            "status": "done", "title": "Create workspace", "output": "ready",
            "artifacts": [{"workspace_id": "docker:abc-123", "changed_files": []}],
        }
        mission = {"tasks": [upstream, {"task_id": "write", "dependencies": ["create-workspace"]}]}
        context = ns["_mission_task_context"](mission, mission["tasks"][1])
        self.assertIn("docker:abc-123", context)
        self.assertIn("workspace_id", context)

    def test_upstream_workspace_id_falls_back_to_tool_evidence(self):
        """Senza artifact persistito l'id si recupera dall'evidence del task a monte."""
        ns = extracted({"_mission_task_context"}, {})
        upstream = {
            "task_id": "create-workspace", "key": "create-workspace",
            "status": "done", "title": "Create workspace", "output": "",
            "tool_evidence": [{"tool": "code_sandbox", "ok": True,
                               "workspace_id": "docker:xyz-999"}],
        }
        mission = {"tasks": [upstream, {"task_id": "write", "dependencies": ["create-workspace"]}]}
        context = ns["_mission_task_context"](mission, mission["tasks"][1])
        self.assertIn("docker:xyz-999", context)

    def test_a_downstream_task_without_upstream_results_gets_a_clear_default(self):
        ns = extracted({"_mission_task_context"}, {})
        self.assertEqual(
            ns["_mission_task_context"]({"tasks": []}, {"dependencies": []}),
            "No upstream results.")


    def test_chain_workspace_id_reads_the_upstream_artifact(self):
        """Il riuso forzato pesca l'id della catena dagli artifact a monte."""
        ns = extracted({"_mission_chain_workspace_id"}, {})
        upstream = {
            "task_id": "create", "status": "done",
            "artifacts": [{"workspace_id": "docker:abc-123"}],
        }
        mission = {"tasks": [upstream, {"task_id": "write", "dependencies": ["create"]}]}
        self.assertEqual(
            ns["_mission_chain_workspace_id"](mission, mission["tasks"][1]),
            "docker:abc-123")

    def test_chain_workspace_id_is_empty_without_a_done_upstream(self):
        ns = extracted({"_mission_chain_workspace_id"}, {})
        pending = {"task_id": "create", "status": "running",
                   "artifacts": [{"workspace_id": "docker:abc-123"}]}
        mission = {"tasks": [pending, {"task_id": "write", "dependencies": ["create"]}]}
        self.assertEqual(
            ns["_mission_chain_workspace_id"](mission, mission["tasks"][1]), "")

    def test_the_reused_workspace_diff_is_captured_for_the_gate(self):
        """Il workspace riusato era già in `before`: il suo diff va comunque preso.

        Senza questa cattura il PDF scritto a valle non comparirebbe fra gli
        artifact e il gate di missione lo cercherebbe invano.
        """
        class FakeSandbox:
            def call(self, action, arguments, timeout=None):
                return {"ok": True, "changed_files": ["out.pdf"], "diff": "..."}

        scope = {
            "_mission_sandbox_workspaces": lambda: {
                "docker:reused": {"label": "chain"},
                "docker:new": {"label": "other"},
            },
            "code_sandbox": FakeSandbox(),
        }
        ns = extracted({"_mission_sandbox_artifacts"}, scope)
        artifacts = ns["_mission_sandbox_artifacts"]({"docker:reused"}, "docker:reused")
        by_id = {a["workspace_id"]: a for a in artifacts}
        self.assertEqual(set(by_id), {"docker:reused", "docker:new"})
        self.assertEqual(by_id["docker:reused"]["changed_files"], ["out.pdf"])

    def test_older_tool_outputs_are_compacted_while_recent_stay_full(self):
        """Compatta gli output tool piu' vecchi oltre la finestra keep_recent per preservare la VRAM."""
        ctx = Invocation(role="coder", max_tokens=500)
        long_old = "HEAD_MARKER_" + ("x" * 2000) + "_TAIL_MARKER"
        long_recent = "RECENT_MARKER_" + ("y" * 2000)
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "usr"},
            {"role": "tool", "content": long_old},
            {"role": "tool", "content": "short_old"},
            {"role": "tool", "content": long_recent},
            {"role": "tool", "content": long_recent},
            {"role": "tool", "content": long_recent},
            {"role": "tool", "content": long_recent},
        ]
        payload = ctx.model_payload({"messages": messages})
        compacted_msgs = payload["messages"]
        self.assertIn("HEAD_MARKER_", compacted_msgs[2]["content"])
        self.assertIn("_TAIL_MARKER", compacted_msgs[2]["content"])
        self.assertIn("output compattato", compacted_msgs[2]["content"])
        self.assertLess(len(compacted_msgs[2]["content"]), len(long_old))
        self.assertEqual(compacted_msgs[3]["content"], "short_old")
        # Recent 4 tool outputs remain untouched
        for idx in (4, 5, 6, 7):
            self.assertEqual(compacted_msgs[idx]["content"], long_recent)

    def test_mission_task_digest_reports_checks_and_websites(self):
        ns = extracted({"_mission_task_digest"}, {})
        mission = {
            "tasks": [
                {
                    "task_id": "t1",
                    "status": "done",
                    "title": "Run checks and build site",
                    "artifacts": [
                        {"workspace_id": "w1", "changed_files": ["app.py"]},
                        {"kind": "website-project", "project_id": "demo-site"},
                    ],
                    "tool_evidence": [
                        {"tool": "code_sandbox", "ok": True, "completed": True, "passed": True},
                    ],
                }
            ]
        }
        digest = ns["_mission_task_digest"](mission)
        self.assertIn("artifacts: app.py", digest)
        self.assertIn("websites: demo-site", digest)
        self.assertIn("checks: 1 passed", digest)


if __name__ == "__main__":
    unittest.main()
