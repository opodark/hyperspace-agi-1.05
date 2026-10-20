# SPDX-License-Identifier: Apache-2.0
"""Unit tests per il diario ed evoluzione della codebase (shared/codebase_journal.py)."""

import tempfile
from pathlib import Path
from unittest import TestCase

from shared.codebase_journal import CodebaseJournal


class CodebaseJournalTests(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp_dir.name)
        self.chronicle = self.root / "test_chronicle.jsonl"
        self.calendar = self.root / "test_calendar.md"
        self.journal = CodebaseJournal(chronicle_path=self.chronicle, calendar_path=self.calendar)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_record_mutation_and_timeline(self):
        entry = self.journal.record_mutation(
            agent="TestAgent",
            intent="Refactoring tool runtime for sliding window",
            files_touched=["shared/tool_runtime.py", "tests/test_tool_runtime.py"],
            action_type="refactor",
            test_status="passed",
            lessons_learned="Always compact old tool outputs to avoid VRAM overflow.",
            commit_hash="abc1234",
        )
        self.assertTrue(self.chronicle.exists())
        self.assertTrue(self.calendar.exists())
        self.assertEqual(entry["agent"], "TestAgent")
        self.assertEqual(entry["action_type"], "refactor")

        timeline = self.journal.get_timeline()
        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0]["intent"], "Refactoring tool runtime for sliding window")

    def test_query_lessons(self):
        self.journal.record_mutation(
            agent="OmenAgent",
            intent="Battery thermal protection setup",
            files_touched=["scripts/setup-omen-247.ps1"],
            action_type="hardening",
            lessons_learned="Cap battery charge to 80% in BIOS to prevent cell swelling under 24/7 AC load.",
        )
        self.journal.record_mutation(
            agent="MacAgent",
            intent="Update web node landing",
            files_touched=["web-node/index.html"],
            action_type="feature",
            lessons_learned="Always test iframe embedding with dark mode.",
        )

        lessons = self.journal.query_lessons(query="battery")
        self.assertEqual(len(lessons), 1)
        self.assertIn("80%", lessons[0]["lessons_learned"])

    def test_markdown_calendar_generation(self):
        self.journal.record_mutation(
            agent="Antigravity",
            intent="Hermes shadow memory bridge",
            files_touched=["scripts/hermes_memory_bridge.py"],
            action_type="feature",
            lessons_learned="Fallback to local SQLite FTS5 when native agent is missing.",
            test_status="50 passed",
        )
        content = self.calendar.read_text(encoding="utf-8")
        self.assertIn("Hermes shadow memory bridge", content)
        self.assertIn("Antigravity", content)
        self.assertIn("Fallback to local SQLite FTS5", content)
