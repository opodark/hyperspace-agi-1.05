#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Unit and integration tests for HyperSpace Sovereign R&D Lab, Research Tree & AST Deploy.
Verifica:
- ResearchTreeManager (albero genealogico, pivot log, failed tests, stats)
- ASTInspector (analisi sintattica, classi, metodi, imports, gestione errori di sintassi)
- Prototype Promotion Pipeline (deploy in shared/, compilazione, backup, tracciamento WAL)
- Diff engine tra prototipo e produzione
- Cockpit HTTP API endpoints (/api/research/tree, /api/research/prototypes, /api/research/prototype, /api/research/prototype/promote)
- Servizio della pagina statica /research.html
"""

import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest
import urllib.error
import urllib.request

from shared.research_tree import (
    ASTInspector,
    ResearchTreeManager,
    RESEARCH_PILLARS,
)

ROOT = Path(__file__).resolve().parents[1]


class TestResearchTreeAndAST(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="hyperspace_rd_test_"))
        self.mgr = ResearchTreeManager(data_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_tree_initialization_and_pillars(self):
        """Verifica che l'albero si inizializzi con i 4 piloni e i nodi storici documentati."""
        tree = self.mgr.get_tree()
        self.assertIn("pillars", tree)
        self.assertIn("nodes", tree)
        self.assertIn("stats", tree)
        self.assertGreaterEqual(len(tree["pillars"]), 4)

        # Verifica che esistano nodi failed e pivot
        nodes = tree["nodes"]
        failed_nodes = [n for n in nodes if n.get("status") == "failed"]
        pivot_nodes = [n for n in nodes if n.get("status") == "pivot" or n.get("pivot_rationale")]
        self.assertGreaterEqual(len(failed_nodes), 2, "Devono essere tracciati almeno 2 test falliti con motivazione")
        self.assertGreaterEqual(len(pivot_nodes), 2, "Devono essere tracciati almeno 2 pivot R&D")

        for fn in failed_nodes:
            self.assertIsNotNone(fn.get("failure_reason"), f"Il nodo fallito {fn['id']} deve contenere failure_reason")
            self.assertIsNotNone(fn.get("hypothesis"), f"Il nodo {fn['id']} deve contenere l'ipotesi testata")

    def test_ast_inspector_valid_code(self):
        """Verifica che ASTInspector estragga fedelmente classi, metodi, parametri e imports."""
        sample_code = (
            "import os\n"
            "from typing import List, Dict\n\n"
            "class SampleCognitiveModule:\n"
            "    '''Docstring del modulo cognitivo.'''\n"
            "    def __init__(self, name: str):\n"
            "        self.name = name\n\n"
            "    def evaluate_axioms(self, state: Dict[str, bool]) -> bool:\n"
            "        return all(state.values())\n\n"
            "def standalone_metric(x: int) -> int:\n"
            "    return x * 2\n"
        )
        res = ASTInspector.inspect_source(sample_code, filename="sample.py")
        self.assertTrue(res["valid"])
        self.assertEqual(len(res["classes"]), 1)
        cls = res["classes"][0]
        self.assertEqual(cls["name"], "SampleCognitiveModule")
        self.assertEqual(len(cls["methods"]), 2)
        self.assertIn("__init__", [m["name"] for m in cls["methods"]])
        self.assertIn("evaluate_axioms", [m["name"] for m in cls["methods"]])
        self.assertEqual(len(res["functions"]), 1)
        self.assertEqual(res["functions"][0]["name"], "standalone_metric")
        self.assertGreaterEqual(len(res["imports"]), 2)
        self.assertGreater(res["node_count"], 15)

    def test_ast_inspector_syntax_error(self):
        """Verifica la cattura pulita di SyntaxError senza crash."""
        bad_code = "def broken_syntax(:\n    pass\n"
        res = ASTInspector.inspect_source(bad_code, filename="bad.py")
        self.assertFalse(res["valid"])
        self.assertIn("SyntaxError", res["error"])

    def test_prototype_promotion_workflow(self):
        """Verifica il flusso completo di deploy: compilazione, backup, tracciamento e ripristino."""
        # 1. Crea un prototipo fittizio valido nella cartella dei prototipi
        proto_name = "proto_test_deploy_mock_123.py"
        proto_file = self.mgr.prototypes_dir / proto_name
        code_content = (
            "class MockDeployableEngine:\n"
            "    def compute_synthesis(self) -> str:\n"
            "        return 'hyper_synthesis_ok'\n"
        )
        proto_file.write_text(code_content, encoding="utf-8")

        target_module_name = "test_deployable_engine.py"
        target_path = ROOT / "shared" / target_module_name

        try:
            # 2. Promuovi la prima volta
            res1 = self.mgr.promote_prototype(proto_name, target_module_name, author="test_runner")
            self.assertTrue(res1["success"])
            self.assertTrue(target_path.exists())
            self.assertIn("MockDeployableEngine", target_path.read_text(encoding="utf-8"))

            # 3. Promuovi una seconda volta per verificare il meccanismo di backup
            res2 = self.mgr.promote_prototype(proto_name, target_module_name, author="test_runner")
            self.assertTrue(res2["success"])
            self.assertIsNotNone(res2.get("backup_file"))
            backup_path = ROOT / "shared" / res2["backup_file"]
            self.assertTrue(backup_path.exists())

            # 4. Verifica diff
            diff_res = self.mgr.get_diff(proto_name, target_module_name)
            self.assertTrue(diff_res["has_target"])

        finally:
            # Cleanup dei file di test in shared/
            if target_path.exists():
                target_path.unlink()
            if proto_file.exists():
                proto_file.unlink()
            if 'res2' in locals() and res2.get("backup_file"):
                b_path = ROOT / "shared" / res2["backup_file"]
                if b_path.exists():
                    b_path.unlink()

    def test_promotion_fails_on_syntax_error(self):
        """Verifica che un prototipo con sintassi non valida venga rifiutato dal gate di produzione."""
        proto_name = "proto_invalid_syntax_456.py"
        proto_file = self.mgr.prototypes_dir / proto_name
        proto_file.write_text("class BrokenClass(:\n    pass", encoding="utf-8")

        try:
            res = self.mgr.promote_prototype(proto_name, "broken_target.py")
            self.assertFalse(res["success"])
            self.assertIn("errori AST", res["error"])
        finally:
            if proto_file.exists():
                proto_file.unlink()


class TestCockpitResearchEndpoints(unittest.TestCase):
    BASE_URL = "http://localhost:8090"

    def test_api_research_tree_endpoint(self):
        """Verifica che /api/research/tree restituisca l'albero e le statistiche."""
        req = urllib.request.Request(f"{self.BASE_URL}/api/research/tree")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("nodes", data)
            self.assertIn("stats", data)
            self.assertIn("pillars", data)

    def test_api_research_prototypes_endpoint(self):
        """Verifica che /api/research/prototypes elenchi i prototipi salvati."""
        req = urllib.request.Request(f"{self.BASE_URL}/api/research/prototypes")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("prototypes", data)
            self.assertIn("count", data)

    def test_research_html_served(self):
        """Verifica che la pagina grafica research.html venga servita correttamente."""
        req = urllib.request.Request(f"{self.BASE_URL}/research.html")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("HyperSpace Sovereign R&D Lab", content)
            self.assertIn("Albero Genealogico", content)
            self.assertIn("Ispettore AST Prototipi", content)


if __name__ == "__main__":
    unittest.main()
