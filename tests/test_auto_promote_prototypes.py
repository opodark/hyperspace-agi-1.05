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
        # max_promotions=0: si ferma prima del passo di revisione (TestReviewGate sotto),
        # quindi qui l'unica chiamata e' quella di backfill dei test.
        self.assertEqual(calls, [ap.TEST_MODEL])
        rep, text = self._run(False, ex)
        self.assertEqual(rep["backfilled"], 0)
        self.assertNotIn("TestZzBackfillThing", text)

    def test_test_inventati_che_falliscono_non_vengono_scritti(self):
        bad = self.TESTS.replace("a(), 1", "a(), 99")
        rep, text = self._run(True, lambda p, model, timeout: {"status": "ok", "response": f"```python\n{bad}\n```"})
        self.assertEqual(rep["backfilled"], 0)
        self.assertNotIn("Test", text)


class TestReviewGate(unittest.TestCase):
    """La revisione indipendente prima della promozione: un modello diverso dal generatore
    legge il prototipo e puo' bloccarlo. Codice gia' con test incorporati, cosi' il backfill
    non interferisce e si isola solo il passo di revisione. `PrototypePromoter.promote_single`
    e' mockato: usa percorsi propri (non quelli patchati qui) e farebbe verifica pytest reale,
    quindi non e' lui l'oggetto del test — qui si verifica solo se VIENE chiamato o no."""

    CODE = textwrap.dedent('''
        import unittest
        class ZzReviewGateThing:
            def a(self): return 1
        class TestZzReviewGateThing(unittest.TestCase):
            def test_a(self): self.assertEqual(ZzReviewGateThing().a(), 1)
    ''')

    def _run(self, executor, promote_single=None):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "proto_x_1.py").write_text(self.CODE)
            # SHARED_DIR/TESTS_DIR vanno sandboxati anche loro: il passo di scrittura del
            # file di test e il controllo "modulo gia' esistente" scrivono/leggono li', non
            # solo nella cartella dei prototipi — altrimenti si scrive per davvero nel repo.
            with patch.object(ap, "PROTOTYPES_DIR", d), patch.object(ap, "STATE_FILE", d / "state.json"), \
                 patch.object(ap, "PROMOTIONS_FILE", d / "none.jsonl"), \
                 patch.object(ap, "SHARED_DIR", d), patch.object(ap, "TESTS_DIR", d), \
                 patch("scripts.diagnostics.promote_research_prototype.PrototypePromoter.promote_single",
                       promote_single or (lambda self, *a, **k: {"success": True, "evidence": {"tier": "verified"}})):
                rep = ap.run_auto_promotion(apply=True, max_promotions=1, min_nodes=10, executor=executor)
            return rep

    def test_rigetta_blocca_la_promozione_prima_del_promoter(self):
        chiamato = []
        rep = self._run(
            lambda prompt, model, timeout: {"status": "ok", "response": "RIGETTA\nla classe non fa quello che dice"},
            promote_single=lambda self, *a, **k: chiamato.append(1) or {"success": True, "evidence": {"tier": "verified"}},
        )
        self.assertEqual(rep["eligible"], [])
        self.assertEqual(rep["promoted"], [])
        self.assertEqual(chiamato, [], "il promoter non deve essere chiamato se la revisione rigetta")

    def test_approva_lascia_proseguire_fino_al_promoter(self):
        rep = self._run(lambda prompt, model, timeout: {"status": "ok", "response": "APPROVA\ntutto a posto"})
        self.assertEqual([e["prototype"] for e in rep["eligible"]], ["proto_x_1.py"])
        self.assertEqual([e["target"] for e in rep["promoted"]], ["shared/zz_review_gate_thing.py"])

    def test_verdetto_non_interpretabile_non_blocca(self):
        rep = self._run(lambda prompt, model, timeout: {"status": "ok", "response": "non ho capito la domanda"})
        self.assertEqual([e["target"] for e in rep["promoted"]], ["shared/zz_review_gate_thing.py"])

    def test_errore_di_rete_non_blocca(self):
        rep = self._run(lambda prompt, model, timeout: {"status": "error"})
        self.assertEqual([e["target"] for e in rep["promoted"]], ["shared/zz_review_gate_thing.py"])

    def test_dry_run_non_chiama_il_revisore(self):
        calls = []

        def ex(prompt, model, timeout):
            calls.append(model)
            return {"status": "ok", "response": "APPROVA"}

        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "proto_x_1.py").write_text(self.CODE)
            with patch.object(ap, "PROTOTYPES_DIR", d), patch.object(ap, "STATE_FILE", d / "state.json"), \
                 patch.object(ap, "PROMOTIONS_FILE", d / "none.jsonl"):
                ap.run_auto_promotion(apply=False, min_nodes=10, executor=ex)
        self.assertEqual(calls, [])


class TestParseReviewVerdict(unittest.TestCase):
    def test_approva_e_rigetta_case_insensitive(self):
        self.assertTrue(ap._parse_review_verdict("approva\nok"))
        self.assertFalse(ap._parse_review_verdict("Rigetta: bug evidente"))

    def test_testo_senza_verdetto_e_none(self):
        self.assertIsNone(ap._parse_review_verdict("non saprei dire"))
        self.assertIsNone(ap._parse_review_verdict(""))
        self.assertIsNone(ap._parse_review_verdict(None))


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
