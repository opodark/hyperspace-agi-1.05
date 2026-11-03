# SPDX-License-Identifier: Apache-2.0
"""Generazione R&D: test scritti dal modello piccolo, riparazione, varianti, scelta del pilastro."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shared.agi_research_engine import AGIResearchEngine, RESEARCH_PILLARS

BASE = """
class ZzCounter:
    def __init__(self):
        self.n = 0

    def inc(self):
        self.n += 1
        return self.n
"""
TESTS = """
import unittest

class TestZzCounter(unittest.TestCase):
    def test_a(self):
        self.assertEqual(ZzCounter().inc(), 1)

    def test_b(self):
        c = ZzCounter(); c.inc()
        self.assertEqual(c.inc(), 2)

    def test_c(self):
        self.assertEqual(ZzCounter().n, 0)
"""
BROKEN = BASE.replace("self.n += 1", "self.n += 2")


def block(code):
    return {"status": "ok", "response": f"```python\n{code}\n```", "elapsed_s": 0.1}


def make_executor(base_codes, repair_code=None, tests=TESTS):
    calls = {"gen": 0, "tests": 0, "repair": 0}
    codes = list(base_codes)

    def executor(prompt, model, timeout):
        if "Scrivi SOLO i test" in prompt:
            calls["tests"] += 1
            return block(tests)
        if "ERRORE:" in prompt:
            calls["repair"] += 1
            return block(repair_code or BASE + TESTS)
        calls["gen"] += 1
        return block(codes.pop(0) if len(codes) > 1 else codes[0])

    return executor, calls


class TestStudyGeneration(unittest.TestCase):
    def run_cycle(self, executor):
        with tempfile.TemporaryDirectory() as d:
            eng = AGIResearchEngine(data_dir=Path(d))
            rec = eng.execute_study_cycle(pillar_id="swarm_emergence", omen_executor_fn=executor)
            saved = (eng.prototypes_dir / rec["prototype_file"]).read_text() if rec["prototype_file"] else ""
            return rec, saved

    def test_test_mancanti_generati_dal_modello_piccolo(self):
        ex, calls = make_executor([BASE])
        rec, saved = self.run_cycle(ex)
        self.assertEqual(calls, {"gen": 1, "tests": 1, "repair": 0})
        self.assertTrue(rec["generation"]["tests_generated"])
        self.assertTrue(rec["generation"]["tests_passed"])
        self.assertIn("class TestZzCounter", saved)

    def test_riparazione_dopo_test_falliti(self):
        ex, calls = make_executor([BROKEN + TESTS], repair_code=BASE + TESTS)
        rec, _ = self.run_cycle(ex)
        self.assertEqual(calls["repair"], 1)
        self.assertEqual(calls["gen"], 1)
        self.assertTrue(rec["generation"]["tests_passed"])

    def test_varianti_fino_al_massimo_se_nessuna_passa(self):
        ex, calls = make_executor([BROKEN + TESTS], repair_code=BROKEN + TESTS)
        rec, saved = self.run_cycle(ex)
        self.assertEqual(calls["gen"], 3)
        self.assertFalse(rec["generation"]["tests_passed"])
        self.assertTrue(rec["prototype_file"])
        self.assertIn("ZzCounter", saved)

    def test_codice_vietato_non_viene_eseguito(self):
        evil = "import subprocess\nclass Zz:\n    pass\n" + TESTS
        ex, calls = make_executor([evil])
        with patch("shared.prototype_gates.subprocess.run") as run:
            rec, _ = self.run_cycle(ex)
            run.assert_not_called()
        self.assertFalse(rec["generation"]["tests_passed"] or False)


class TestPickPillar(unittest.TestCase):
    def test_pilastri_con_meno_verificati_pesano_di_piu(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            eng = AGIResearchEngine(data_dir=d)
            lines = [json.dumps({"prototype_file": f"proto_aleksander_axioms_{i}.py", "evidence": {"tier": "verified"}})
                     for i in range(9)]
            (d / "promotions.jsonl").write_text("\n".join(lines))
            picks = [eng.pick_pillar()["id"] for _ in range(600)]
            self.assertLess(picks.count("aleksander_axioms"), picks.count("swarm_emergence"))
            self.assertEqual({p["id"] for p in RESEARCH_PILLARS} >= set(picks), True)


if __name__ == "__main__":
    unittest.main()


class TestProgressLogging(unittest.TestCase):
    """Senza queste righe un ciclo di ricerca resta muto per 600-800s (chiamata principale +
    eventuale generazione test + eventuale riparazione), e da fuori sembra fermo mentre lavora."""

    def test_call_models_logs_before_and_after(self):
        executor = lambda *a, **k: {"status": "ok", "response": BASE, "elapsed_s": 1.0}
        with patch("shared.agi_research_engine._log") as mock_log:
            AGIResearchEngine._call_models(executor, "prompt", "model-a", "fallback-b")
        tags = [c.args[0] for c in mock_log.call_args_list]
        self.assertEqual(tags, ["RESEARCH-CALL", "RESEARCH-CALL"])

    def test_call_models_logs_fallback_path(self):
        calls = {"n": 0}

        def executor(*a, **k):
            calls["n"] += 1
            return {"status": "error" if calls["n"] == 1 else "ok", "response": BASE, "elapsed_s": 1.0}

        with patch("shared.agi_research_engine._log") as mock_log:
            AGIResearchEngine._call_models(executor, "prompt", "model-a", "fallback-b")
        msgs = " ".join(c.args[1] for c in mock_log.call_args_list)
        self.assertIn("fallback-b", msgs)

    def test_log_writes_a_flushed_line(self):
        from shared.agi_research_engine import _log
        with patch("builtins.print") as mock_print:
            _log("TAG", "messaggio")
        mock_print.assert_called_once()
        self.assertTrue(mock_print.call_args.kwargs.get("flush"))
        self.assertIn("[TAG] messaggio", mock_print.call_args.args[0])
