# SPDX-License-Identifier: Apache-2.0
"""Test suite per il Motore Notturno Sovrano (HP OMEN 16 & Mesh HyperSpace)."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from shared.dream_visual import parse_dream, filtra_dream
from shared.resumable_state_machine import CheckpointStore, ResumableStateMachine, RunState, ExecutionStatus
import scripts.omen_allnight_sovereign as allnight
from scripts.omen_allnight_sovereign import (
    is_thermal_safe,
    get_nightly_status,
    AUTONOMOUS_DEV_TASKS,
    IMAGE_SCENARIOS,
    run_autonomous_dev_distillation,
    run_nightly_dreams,
)


class TestOmenAllnightSovereign(unittest.TestCase):
    def setUp(self):
        # I log notturni veri (node_stream, dataset CoT, audit...) alimentano il Cockpit:
        # i test scrivono in una cartella temporanea, non in data/.
        self._tmp = tempfile.TemporaryDirectory(prefix="omen_allnight_test_")
        tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        for name in ("STATE_FILE", "AUDIT_LOG", "COT_DATASET", "DREAM_LOG", "IMAGE_LOG", "NODE_STREAM_LOG"):
            patcher = patch.object(allnight, name, tmp / getattr(allnight, name).name)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.research_dir = tmp / "research"

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

        engine = AGIResearchEngine(data_dir=self.research_dir)
        study = engine.execute_study_cycle("aleksander_axioms", omen_executor_fn=mock_omen_fn)
        self.assertEqual(study["pillar_id"], "aleksander_axioms")
        self.assertTrue(study["ast_valid"])
        self.assertTrue(study["prototype_file"].endswith(".py"))

        st = engine.get_research_status()
        self.assertGreaterEqual(st["total_studies"], 1)
        self.assertTrue(st["has_synthesis_document"])

    @patch("scripts.omen_allnight_sovereign._is_asus_available", return_value=False)
    @patch("urllib.request.urlopen")
    def test_flint_40b_routes_to_omen_when_asus_offline(self, mock_urlopen, mock_asus_check):
        from scripts.omen_allnight_sovereign import execute_omen_prompt

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"response": "OK"}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = execute_omen_prompt("Test prompt 40B", model="flint:latest", timeout=60)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["routed_via"], "OMEN_NODE")
        # Verifica che la chiamata sia andata a OMEN (:8081) e non ad ASUS
        req_arg = mock_urlopen.call_args[0][0]
        self.assertIn("100.104.238.125:8081", req_arg.full_url)

    @patch("urllib.request.urlopen")
    def test_asus_disabled_keeps_everything_on_omen(self, mock_urlopen):
        """ALLNIGHT_USE_ASUS=false: nessuna richiesta verso ASUS, nemmeno la sonda."""
        from scripts.omen_allnight_sovereign import execute_omen_prompt

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"response": "OK"}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with patch.object(allnight, "USE_ASUS", False):
            res = execute_omen_prompt("Test prompt 40B", model="flint:latest", timeout=60)
        self.assertEqual(res["routed_via"], "OMEN_NODE")
        urls = [c[0][0].full_url for c in mock_urlopen.call_args_list]
        self.assertTrue(urls)
        self.assertFalse([u for u in urls if "11434" in u])

    @patch("scripts.omen_allnight_sovereign._is_asus_available", return_value=True)
    @patch("urllib.request.urlopen")
    def test_asus_fallback_mode_tries_omen_first(self, mock_urlopen, mock_asus_check):
        """ALLNIGHT_USE_ASUS=fallback: anche un 24B parte dall'OMEN; ASUS solo se l'OMEN fallisce."""
        from scripts.omen_allnight_sovereign import execute_omen_prompt

        ok_resp = MagicMock()
        ok_resp.read.return_value = json.dumps({"response": "OK"}).encode("utf-8")
        ok_resp.__enter__.return_value = ok_resp
        model = "hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M"

        with patch.object(allnight, "ASUS_PRIMARY", False):
            mock_urlopen.return_value = ok_resp
            res = execute_omen_prompt("Test 24B", model=model, timeout=60)
            self.assertEqual(res["routed_via"], "OMEN_NODE")
            self.assertEqual(mock_urlopen.call_count, 1)

            mock_urlopen.reset_mock()
            mock_urlopen.side_effect = [OSError("OMEN giù"), ok_resp]
            res = execute_omen_prompt("Test 24B", model=model, timeout=60)
            self.assertEqual(res["routed_via"], "ASUS_FALLBACK")
            urls = [c[0][0].full_url for c in mock_urlopen.call_args_list]
            self.assertIn("100.104.238.125:8081", urls[0])
            self.assertIn("100.64.31.18:11434", urls[1])

    @patch("scripts.omen_allnight_sovereign._is_asus_available", return_value=True)
    @patch("urllib.request.urlopen")
    def test_flint_40b_routes_to_asus_when_online(self, mock_urlopen, mock_asus_check):
        from scripts.omen_allnight_sovereign import execute_omen_prompt

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"response": "OK"}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = execute_omen_prompt("Test prompt 40B", model="flint:latest", timeout=60)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["routed_via"], "ASUS_OLLAMA")
        # Verifica che la chiamata sia andata ad ASUS (:11434)
        req_arg = mock_urlopen.call_args[0][0]
        self.assertIn("100.64.31.18:11434", req_arg.full_url)


if __name__ == "__main__":
    unittest.main()
