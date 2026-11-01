# SPDX-License-Identifier: Apache-2.0
"""Cancelli del promotore automatico (scripts/diagnostics/auto_promote_prototypes.py)."""
import ast
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.diagnostics import auto_promote_prototypes as ap


def gate(src: str, min_nodes: int = 1):
    return ap.static_gate(ast.parse(textwrap.dedent(src)), min_nodes)


class TestStaticGate(unittest.TestCase):
    def test_codice_pulito_passa(self):
        self.assertIsNone(gate("import json\nclass A:\n    def f(self):\n        return json.dumps({})\n"))

    def test_troppo_piccolo(self):
        self.assertIn("piccolo", gate("x = 1\n", min_nodes=250))

    def test_import_vietati_e_non_stdlib(self):
        self.assertIn("vietato", gate("import subprocess\n"))
        self.assertIn("non stdlib", gate("import torch\n"))

    def test_chiamate_pericolose(self):
        self.assertIn("eval", gate("def f(x):\n    return eval(x)\n"))
        self.assertIn("os.system", gate("import os\ndef f():\n    os.system('x')\n"))
        self.assertIn("scrittura", gate("def f():\n    open('a', 'w')\n"))

    def test_open_in_lettura_ammesso(self):
        self.assertIsNone(gate("def f():\n    return open('a').read()\n"))

    def test_effetti_a_livello_di_modulo(self):
        self.assertIn("top-level", gate("print('ciao')\n"))
        self.assertIn("top-level", gate("try:\n    import json\nexcept ImportError:\n    pass\n"))

    def test_funzione_decorata_rifiutata(self):
        self.assertIn("decorata", gate("import functools\n@functools.cache\ndef f():\n    pass\n"))

    def test_shared_inesistente(self):
        self.assertIn("inesistente", gate("from shared.non_esiste_xyz import A\n"))


class TestClassiENomi(unittest.TestCase):
    def test_classi_pubbliche_e_test(self):
        t = ast.parse("class Foo: pass\nclass _Priv: pass\nclass TestFoo: pass\n")
        self.assertEqual(ap.public_classes(t), ["Foo"])
        self.assertEqual(ap.embedded_test_classes(t), ["TestFoo"])

    def test_snake(self):
        self.assertEqual(ap._snake("SovereignModularIntellect"), "sovereign_modular_intellect")


class TestDryRun(unittest.TestCase):
    def test_dry_run_non_scrive_e_scarta_duplicati(self):
        good = textwrap.dedent('''
            import unittest
            class ZzUniqueWindowForTest:
                def a(self): return 1
                def b(self): return 2
            class TestZz(unittest.TestCase):
                def test_a(self): self.assertEqual(ZzUniqueWindowForTest().a(), 1)
        ''')
        dup = good.replace("ZzUniqueWindowForTest", "NeuroSymbolicPoetryEngine")
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "proto_good_1.py").write_text(good)
            (d / "proto_dup_2.py").write_text(dup)
            with patch.object(ap, "PROTOTYPES_DIR", d), patch.object(ap, "STATE_FILE", d / "state.json"), \
                 patch.object(ap, "PROMOTIONS_FILE", d / "none.jsonl"):
                rep = ap.run_auto_promotion(apply=False, min_nodes=20)
            self.assertEqual([e["prototype"] for e in rep["eligible"]], ["proto_good_1.py"])
            self.assertEqual(rep["promoted"], [])
            self.assertFalse((d / "state.json").exists())


class TestBackfillTest(unittest.TestCase):
    CODE = textwrap.dedent('''
        class ZzBackfillThing:
            def a(self): return 1
            def b(self): return 2
            def c(self): return 3
    ''')
    TESTS = "import unittest\nclass TestZzBackfillThing(unittest.TestCase):\n    def test_a(self):\n        self.assertEqual(ZzBackfillThing().a(), 1)\n"

    def _run(self, apply, executor):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "proto_x_1.py").write_text(self.CODE)
            with patch.object(ap, "PROTOTYPES_DIR", d), patch.object(ap, "STATE_FILE", d / "state.json"), \
                 patch.object(ap, "PROMOTIONS_FILE", d / "none.jsonl"):
                rep = ap.run_auto_promotion(apply=apply, max_promotions=0, min_nodes=10, executor=executor)
            return rep, (d / "proto_x_1.py").read_text()

    def test_test_generati_e_scritti_solo_con_apply(self):
        calls = []

        def ex(prompt, model, timeout):
            calls.append(model)
            return {"status": "ok", "response": f"```python\n{self.TESTS}\n```"}

        rep, text = self._run(True, ex)
        self.assertEqual(rep["backfilled"], 1)
        self.assertIn("TestZzBackfillThing", text)
        self.assertEqual(calls, [ap.TEST_MODEL])
        rep, text = self._run(False, ex)
        self.assertEqual(rep["backfilled"], 0)
        self.assertNotIn("TestZzBackfillThing", text)

    def test_test_inventati_che_falliscono_non_vengono_scritti(self):
        bad = self.TESTS.replace("a(), 1", "a(), 99")
        rep, text = self._run(True, lambda p, model, timeout: {"status": "ok", "response": f"```python\n{bad}\n```"})
        self.assertEqual(rep["backfilled"], 0)
        self.assertNotIn("Test", text)


class TestBudget(unittest.TestCase):
    CODE = textwrap.dedent('''
        import unittest
        class ZzBudgetThing:
            def a(self): return 1
        class TestZzBudgetThing(unittest.TestCase):
            def test_a(self): self.assertEqual(ZzBudgetThing().a(), 1)
    ''')

    def test_tetto_di_tempo_ferma_il_lavoro_costoso(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for i in range(4):
                (d / f"proto_x_{i}.py").write_text(self.CODE)
            with patch.object(ap, "PROTOTYPES_DIR", d), patch.object(ap, "STATE_FILE", d / "state.json"), \
                 patch.object(ap, "PROMOTIONS_FILE", d / "none.jsonl"), \
                 patch.object(ap, "run_embedded_tests") as tests:
                rep = ap.run_auto_promotion(apply=False, min_nodes=10, budget_s=-1)
            tests.assert_not_called()
            self.assertTrue(rep["time_exhausted"])
            self.assertEqual(rep["tested"], 0)

    def test_budget_ampio_lascia_lavorare(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "proto_x_0.py").write_text(self.CODE)
            with patch.object(ap, "PROTOTYPES_DIR", d), patch.object(ap, "STATE_FILE", d / "state.json"), \
                 patch.object(ap, "PROMOTIONS_FILE", d / "none.jsonl"):
                rep = ap.run_auto_promotion(apply=False, min_nodes=10, budget_s=120)
            self.assertFalse(rep["time_exhausted"])
            self.assertEqual(rep["tested"], 1)
            self.assertIsInstance(rep["elapsed_s"], float)


if __name__ == "__main__":
    unittest.main()
