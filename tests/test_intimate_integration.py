# SPDX-License-Identifier: Apache-2.0
"""Invarianti statici del diario intimo nel control-plane."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class IntimateIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "control-plane" / "main.py").read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.functions = {node.name: node for node in cls.tree.body
                         if isinstance(node, ast.FunctionDef)}

    def test_scheduler_parte_nei_due_entrypoint(self):
        self.assertEqual(self.source.count("threading.Thread(target=intimate_loop"), 2)

    def test_scheduler_seleziona_solo_creator_scoped_ids(self):
        body = ast.unparse(self.functions["_run_intimate_once"])
        self.assertIn("_creator_scoped_ids", body)
        self.assertNotIn("instagram_vips.list", body)
        self.assertIn("livello='creatore'", body)

    def test_archivio_privato_richiede_autenticazione(self):
        body = ast.unparse(self.functions["diario_intimo_data"])
        self.assertIn("_network_admin_error", body)
        self.assertIn("diario_intimo.list", body)

    def test_generazione_manuale_richiede_autenticazione(self):
        body = ast.unparse(self.functions["diario_intimo_genera"])
        self.assertIn("_network_admin_error", body)
        self.assertIn("_run_intimate_once('anna')", body)


if __name__ == "__main__":
    unittest.main()
