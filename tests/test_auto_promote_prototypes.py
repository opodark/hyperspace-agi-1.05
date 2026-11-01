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


if __name__ == "__main__":
    unittest.main()
