# SPDX-License-Identifier: Apache-2.0
"""Test suite per l'integrazione della Tassonomia Harness² e di HarnessReflector."""

import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from shared.harness_reflector import HarnessReflector, HARNESS_BASE_TYPE_MAP

ROOT = Path(__file__).resolve().parents[1]


class TestHarnessReflector(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.forge_dir = self.tmp_path / "forge"
        self.exp_path = self.tmp_path / "experience.jsonl"
        self.exp_md = self.tmp_path / "experience.md"
        self.reflector = HarnessReflector(
            forge_dir=self.forge_dir,
            experience_path=self.exp_path,
            experience_md_path=self.exp_md,
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_harness_components_taxonomy_completeness(self):
        expected_components = {
            "system_prompt",
            "guardrail",
            "memory",
            "tool_guidance",
            "subagent",
            "skill",
            "script",
            "plugin",
        }
        self.assertEqual(set(HARNESS_BASE_TYPE_MAP.keys()), expected_components)

    def test_write_draft_artifact_creates_inert_files(self):
        item = self.reflector.write_draft_artifact(
            name="Test Guardrail Safety",
            source="# Test Guardrail\n\nNEVER execute unapproved code.",
            component="guardrail",
            description="Test guardrail artifact",
        )

        self.assertEqual(item["status"], "draft")
        self.assertEqual(item["harness_component"], "guardrail")
        self.assertEqual(item["type"], "skill")

        json_file = self.forge_dir / f"{item['id']}.json"
        md_file = self.forge_dir / f"{item['id']}.md"
        self.assertTrue(json_file.exists())
        self.assertTrue(md_file.exists())

        with open(json_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved["id"], item["id"])
        self.assertEqual(saved["status"], "draft")
        self.assertEqual(saved["harness_component"], "guardrail")

    def test_reflect_on_mission_tool_error(self):
        mission_payload = {
            "id": "mission-test-tool-err-123",
            "status": "failed",
            "objective": "Generate analytical report",
            "error": "task failed",
            "tasks": {
                "t1": {
                    "role": "repo-analyst",
                    "status": "failed",
                    "error": "TypeError: web_search got an unexpected argument 'query_mode'",
                }
            },
            "counters": {"steps": 1, "replans": 0, "elapsed_seconds": 12},
        }

        draft = self.reflector.reflect_on_mission(mission_payload)
        self.assertIsNotNone(draft)
        self.assertEqual(draft["harness_component"], "tool_guidance")
        self.assertEqual(draft["status"], "draft")
        self.assertIn("repo-analyst", draft["name"])

        # Verifica registrazione nel log di esperienza
        self.assertTrue(self.exp_path.exists())
        with open(self.exp_path, "r", encoding="utf-8") as f:
            lines = [json.loads(l) for l in f if l.strip()]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["event_type"], "mission_tool_error")
        self.assertEqual(lines[0]["target_component"], "tool_guidance")

        # Verifica sincronizzazione markdown
        self.assertTrue(self.exp_md.exists())
        md_text = self.exp_md.read_text(encoding="utf-8")
        self.assertIn("mission-test-tool-err-123", md_text)
        self.assertIn("tool_guidance", md_text)

    def test_reflect_on_mission_budget_exhaustion(self):
        mission_payload = {
            "id": "mission-loop-test",
            "status": "failed",
            "objective": "Heavy refactoring",
            "error": "budget exhausted: steps=40 replans=3 elapsed=3600s",
            "tasks": {},
            "counters": {"steps": 40, "replans": 3, "elapsed_seconds": 3600},
        }

        draft = self.reflector.reflect_on_mission(mission_payload)
        self.assertIsNotNone(draft)
        self.assertEqual(draft["harness_component"], "guardrail")
        self.assertEqual(draft["status"], "draft")
        self.assertIn("Guardrail", draft["name"])

    def test_reflect_on_mission_success(self):
        mission_payload = {
            "id": "mission-success-test",
            "status": "done",
            "objective": "Build documentation portal",
            "acceptance_criteria": "Static portal deployed",
            "tasks": {
                "t1": {"role": "planner", "status": "done", "description": "Plan steps"},
                "t2": {"role": "coder", "status": "done", "description": "Create site"},
            },
            "counters": {"steps": 2, "replans": 0, "elapsed_seconds": 45},
        }

        draft = self.reflector.reflect_on_mission(mission_payload)
        self.assertIsNotNone(draft)
        self.assertEqual(draft["harness_component"], "skill")
        self.assertEqual(draft["status"], "draft")
        self.assertIn("Skill", draft["name"])


class TestForgeHarnessIntegration(unittest.TestCase):
    def test_forge_components_definition_in_forge_py(self):
        forge_py = (ROOT / "control-plane" / "cp" / "forge.py").read_text(encoding="utf-8")
        self.assertIn("_FORGE_TYPES = {\"tool\", \"skill\", \"patch\"}", forge_py)
        self.assertIn("_HARNESS_COMPONENTS", forge_py)
        for comp in ("system_prompt", "guardrail", "memory", "tool_guidance", "subagent", "skill", "script", "plugin"):
            self.assertIn(f'"{comp}"', forge_py)


if __name__ == "__main__":
    unittest.main()
