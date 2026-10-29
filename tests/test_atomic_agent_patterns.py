# SPDX-License-Identifier: Apache-2.0
"""Test suite per i pattern integrati da Atomic Agent:
- GBNF Grammar Constraints (shared/gbnf_grammar.py)
- NDJSON Execution Tracer (shared/ndjson_tracer.py)
- HITL Mutation Guard & Proposal Gate (shared/mutation_guard.py)
"""

import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from shared.gbnf_grammar import (
    GBNFBuilder,
    GBNF_JSON_OBJECT,
    GBNF_PYTHON_AST_PROPOSAL,
    inject_gbnf_constraint,
)
from shared.ndjson_tracer import NDJSONTracer
from shared.mutation_guard import (
    ActionCategory,
    MutationGuard,
    ProposalStatus,
)


class TestGBNFGrammar(unittest.TestCase):
    def test_canonical_grammars_exist(self):
        self.assertIn("root ::= object", GBNF_JSON_OBJECT)
        self.assertIn("file_path", GBNF_PYTHON_AST_PROPOSAL)
        self.assertIn("code", GBNF_PYTHON_AST_PROPOSAL)

    def test_build_tool_call_grammar(self):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "parameters": {"type": "object", "properties": {"command": {"type": "string"}}},
                },
            },
        ]
        grammar = GBNFBuilder.build_tool_call_grammar(tools)
        self.assertIn("tool_read_file", grammar)
        self.assertIn("tool_run_command", grammar)
        self.assertIn('name', grammar)
        self.assertIn('arguments', grammar)
        self.assertIn("root ::=", grammar)

    def test_build_schema_grammar(self):
        schema = {
            "title": "string",
            "score": "number",
            "is_active": "boolean",
        }
        grammar = GBNFBuilder.build_schema_grammar(schema)
        self.assertIn('title', grammar)
        self.assertIn('score', grammar)
        self.assertIn('is_active', grammar)

    def test_inject_gbnf_constraint_llamacpp(self):
        payload = {"messages": [{"role": "user", "content": "hello"}]}
        constrained = inject_gbnf_constraint(payload, backend="llama.cpp")
        self.assertIn("grammar", constrained)
        self.assertEqual(constrained["response_format"], {"type": "json_object"})

    def test_inject_gbnf_constraint_ollama(self):
        payload = {"prompt": "hello"}
        constrained = inject_gbnf_constraint(payload, backend="ollama")
        self.assertEqual(constrained.get("format"), "json")
        self.assertIn("grammar", constrained.get("options", {}))


class TestNDJSONTracer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.tracer = NDJSONTracer(trace_dir=self.temp_dir, session_id="test_sess_001")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_log_and_replay(self):
        self.tracer.log_event("session_start", {"goal": "test_goal"})
        self.tracer.log_llm_call(
            node="OMEN",
            model="lfm-24b",
            prompt_tokens=150,
            completion_tokens=80,
            duration_ms=450.2,
            status="ok",
        )
        self.tracer.log_tool_call(
            tool_name="code_sandbox",
            arguments={"action": "read", "path": "main.py"},
            result="print('ok')",
            duration_ms=12.5,
            ok=True,
        )

        events = list(self.tracer.replay())
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["event"], "session_start")
        self.assertEqual(events[1]["event"], "llm_call")
        self.assertEqual(events[1]["model"], "lfm-24b")
        self.assertEqual(events[2]["event"], "tool_call")
        self.assertEqual(events[2]["tool"], "code_sandbox")

    def test_summary_calculation(self):
        self.tracer.log_tool_call("tool1", {}, "ok", 10.0, ok=True)
        self.tracer.log_tool_call("tool2", {}, "err", 20.0, ok=False, error="Fail")
        self.tracer.log_llm_call("node", "m", 100, 50, 200.0)

        summary = self.tracer.get_summary()
        self.assertEqual(summary["total_events"], 3)
        self.assertEqual(summary["tool_calls"], 2)
        self.assertEqual(summary["tool_errors"], 1)
        self.assertEqual(summary["tool_success_rate"], 0.5)
        self.assertEqual(summary["total_tokens"], 150)

    def test_thread_safety(self):
        def worker(w_id):
            for i in range(10):
                self.tracer.log_event("worker_event", {"worker": w_id, "idx": i})

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        events = list(self.tracer.replay())
        self.assertEqual(len(events), 50)


class TestMutationGuard(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.guard = MutationGuard(proposals_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_classification(self):
        self.assertEqual(
            MutationGuard.classify_action("read_file", {"path": "test.txt"}),
            ActionCategory.READ_ONLY,
        )
        self.assertEqual(
            MutationGuard.classify_action("code_sandbox", {"action": "read"}),
            ActionCategory.READ_ONLY,
        )
        self.assertEqual(
            MutationGuard.classify_action("code_sandbox", {"action": "write"}),
            ActionCategory.MUTATING,
        )
        self.assertEqual(
            MutationGuard.classify_action("run_command", {"command": "ls -la"}),
            ActionCategory.READ_ONLY,
        )
        self.assertEqual(
            MutationGuard.classify_action("run_command", {"command": "rm -rf tmp"}),
            ActionCategory.CRITICAL_SYSTEM,
        )
        self.assertEqual(
            MutationGuard.classify_action("run_command", {"command": "git commit -m 'test'"}),
            ActionCategory.CRITICAL_SYSTEM,
        )

    def test_read_only_execution_bypasses_gate(self):
        def mock_executor(name, args):
            return f"Executed {name} with {args}"

        ok, res = self.guard.execute_with_guard(
            "read_file", {"path": "a.txt"}, mock_executor
        )
        self.assertTrue(ok)
        self.assertEqual(res, "Executed read_file with {'path': 'a.txt'}")

    def test_mutating_action_generates_proposal(self):
        def mock_executor(name, args):
            return "Should not execute yet"

        ok, res = self.guard.execute_with_guard(
            "code_sandbox", {"action": "write", "content": "code"}, mock_executor
        )
        self.assertFalse(ok)
        self.assertTrue(res.get("gated"))
        proposal = res.get("proposal")
        self.assertIsNotNone(proposal)
        prop_id = proposal["proposal_id"]
        self.assertEqual(proposal["status"], ProposalStatus.PENDING_APPROVAL.value)

        # Now approve and re-execute
        approved = self.guard.approve(prop_id)
        self.assertTrue(approved)

        ok2, res2 = self.guard.execute_with_guard(
            "code_sandbox", {"action": "write", "content": "code"}, mock_executor, proposal_id=prop_id
        )
        self.assertTrue(ok2)
        self.assertEqual(res2, "Should not execute yet")

    def test_reject_proposal(self):
        prop = self.guard.create_proposal("write_file", {"path": "b.txt"})
        self.assertTrue(self.guard.reject(prop.proposal_id, reason="Security policy"))

        def mock_executor(name, args):
            return "Should not execute"

        ok, res = self.guard.execute_with_guard(
            "write_file", {"path": "b.txt"}, mock_executor, proposal_id=prop.proposal_id
        )
        self.assertFalse(ok)
        self.assertIn("non approvata", res)


if __name__ == "__main__":
    unittest.main()
