# SPDX-License-Identifier: Apache-2.0
"""Test suite per il Motore Notturno Sovrano (HP OMEN 16 & Mesh HyperSpace)."""

import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from shared.dream_visual import parse_dream, filtra_dream
from shared.resumable_state_machine import CheckpointStore, ResumableStateMachine, RunState, ExecutionStatus
from scripts.omen_allnight_sovereign import (
    is_thermal_safe,
    get_nightly_status,
    AUTONOMOUS_DEV_TASKS,
    IMAGE_SCENARIOS,
    run_autonomous_dev_distillation,
    run_nightly_dreams,
)


class TestOmenAllnightSovereign(unittest.TestCase):
    def test_thermal_safety_check(self):
        with patch("pathlib.Path.exists", return_value=False):
            self.assertTrue(is_thermal_safe())

    def test_nightly_status_structure(self):
        st = get_nightly_status()
        self.assertEqual(st.get("status"), "online")
        self.assertIn("metrics", st)
        self.assertIn("total_cot_samples", st["metrics"])
        self.assertIn("thermal_safe", st["metrics"])

    def test_autonomous_dev_tasks_configuration(self):
        self.assertGreaterEqual(len(AUTONOMOUS_DEV_TASKS), 4)
        for t in AUTONOMOUS_DEV_TASKS:
            self.assertIn("topic", t)
            self.assertIn("prompt", t)
            self.assertIn("<think>", t["prompt"])

    def test_image_scenarios_configuration(self):
        self.assertGreaterEqual(len(IMAGE_SCENARIOS), 4)
        for s in IMAGE_SCENARIOS:
            self.assertIn("title", s)
            self.assertIn("prompt", s)
            self.assertIn("family", s)

    def test_visual_dream_parser_and_filter(self):
        sample_response = (
            "SCENA: Una distesa di dune illuminate da laser quantici.\n"
            "DISEGNO: Silhouette di Anna che guarda l'orizzonte con cielo a gradienti ciano e violetto."
        )
        parsed = parse_dream(sample_response)
        self.assertIsNotNone(parsed)
        self.assertIn("dune", parsed["scena"])
        self.assertIn("Silhouette", parsed["disegno"])

        ok, reason = filtra_dream(parsed, autore="anna")
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_state_machine_steps_execution(self):
        tmp_store = MagicMock(spec=CheckpointStore)
        sm = ResumableStateMachine(tmp_store)

        step1 = MagicMock(return_value={"a": 1})
        step2 = MagicMock(return_value={"b": 2})

        sm.register_step(0, "s1", step1)
        sm.register_step(1, "s2", step2)

        st = sm.start_or_resume("test-nightly-run")
        self.assertEqual(st.step_index, 0)

        st1 = sm.step()
        self.assertEqual(st1.step_index, 1)

        st2 = sm.step()
        self.assertEqual(st2.status, ExecutionStatus.COMPLETED.value)
        self.assertEqual(st2.payload.get("a"), 1)
        self.assertEqual(st2.payload.get("b"), 2)

    @patch("scripts.omen_allnight_sovereign.execute_omen_prompt")
    def test_autonomous_dev_distillation_success(self, mock_exec):
        mock_exec.return_value = {
            "status": "ok",
            "model": "granite3.3:8b",
            "elapsed_s": 1.2,
            "response": "<think>Analisi dei requisiti Chase-Lev</think>\n```python\ndef calculate_pouw(difficulty: int) -> bool:\n    return True\n```"
        }
        res = run_autonomous_dev_distillation(cycles=1)
        self.assertIn("distilled_count", res)
        self.assertGreaterEqual(res["distilled_count"], 1)
        self.assertTrue(res["tasks"][0]["valid"])

    def test_agi_research_pillars_and_execution(self):
        from shared.agi_research_engine import AGIResearchEngine, RESEARCH_PILLARS
        self.assertGreaterEqual(len(RESEARCH_PILLARS), 3)

        mock_omen_fn = MagicMock(return_value={
            "status": "ok",
            "model": "granite3.3:8b",
            "elapsed_s": 1.5,
            "response": "<think>Analisi dei 5 assiomi di Aleksander</think>\n```python\nclass SyntheticConsciousnessTestGovernor:\n    pass\n```"
        })

        engine = AGIResearchEngine()
        study = engine.execute_study_cycle("aleksander_axioms", omen_executor_fn=mock_omen_fn)
        self.assertEqual(study["pillar_id"], "aleksander_axioms")
        self.assertTrue(study["ast_valid"])
        self.assertTrue(study["prototype_file"].endswith(".py"))

        st = engine.get_research_status()
        self.assertGreaterEqual(st["total_studies"], 1)
        self.assertTrue(st["has_synthesis_document"])


if __name__ == "__main__":
    unittest.main()
