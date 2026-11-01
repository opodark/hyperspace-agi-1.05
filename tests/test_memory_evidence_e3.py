#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""tests/test_memory_evidence_e3.py.

Suite di verifica per la Fase E3 dei Livelli di Evidenza della Memoria (docs/memory-evidence-tiers.md):
1. Motore di Ricerca Notturno (AGIResearchEngine):
   - Assegnazione del campo evidence (default: plausible) conforme al contratto di memory_schema.
   - Esclusione dei dossier con findings_summary vuoto/whitespace da AGI_SWARM_SYNTHESIS.md e sogni.
   - Metodi helper get_valid_dossiers() e get_latest_valid_dossier().
2. Albero di Ricerca & Sincronizzazione (ResearchTreeManager):
   - _sync_deep_dives_to_tree esclude i dossier con findings_summary vuoto.
   - find_exercising_tests rileva correttamente i file in tests/ che importano il modulo promosso.
3. Promozione Prototipi in Produzione (PrototypePromoter & ResearchTreeManager):
   - Modulo con test esercitanti superati: tier verified con check deterministico, command,
     exit_code 0, sha256 a 64 caratteri e timestamp ISO.
   - Modulo senza test esercitanti: promozione prudente con tier plausible e basis vuota.
   - Registrazione in promotions.jsonl con metadati test e validazione rigorosa validate_evidence().
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.diagnostics.promote_research_prototype import PrototypePromoter
from shared.agi_research_engine import AGIResearchEngine
from shared.memory_schema import PLAUSIBLE, VERIFIED, validate_evidence
from shared.research_tree import (
    ResearchTreeManager,
    find_exercising_tests,
)


class TestMemoryEvidenceE3ResearchEngine(unittest.TestCase):
    """Verifica il comportamento di AGIResearchEngine per la Fase E3."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.engine = AGIResearchEngine(data_dir=self.data_dir)
        self.engine.prototypes_dir = self.data_dir / "prototypes"
        self.engine.prototypes_dir.mkdir(parents=True, exist_ok=True)
        self.engine.deep_dives_log = self.data_dir / "agi_deep_dives.jsonl"
        self.engine.synthesis_md = self.data_dir / "AGI_SWARM_SYNTHESIS.md"

    def tearDown(self):
        self.tmp.cleanup()

    def test_study_cycle_attaches_plausible_evidence(self):
        record = self.engine.execute_study_cycle(pillar_id="aleksander_axioms")
        self.assertIn("evidence", record)
        evidence = record["evidence"]
        self.assertEqual(evidence["tier"], PLAUSIBLE)
        self.assertEqual(evidence["basis"], [])
        self.assertEqual(evidence.get("assigned_by"), "agi_research_engine")
        errors = validate_evidence(evidence)
        self.assertEqual(errors, [])

    def test_get_valid_dossiers_filters_empty_summaries(self):
        # Scrive 3 record nel log: 1 valido, 1 con summary vuoto, 1 con summary whitespace
        records = [
            {"id": "study-1", "pillar_id": "p1", "findings_summary": "Ottima scoperta sulla coscienza."},
            {"id": "study-2", "pillar_id": "p2", "findings_summary": ""},
            {"id": "study-3", "pillar_id": "p3", "findings_summary": "   \n\t  "},
            {"id": "study-4", "pillar_id": "p4", "findings_summary": "Emergenza stigmergica convalidata."},
        ]
        with open(self.engine.deep_dives_log, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

        valid = self.engine.get_valid_dossiers()
        self.assertEqual(len(valid), 2)
        self.assertEqual([d["id"] for d in valid], ["study-1", "study-4"])

        latest = self.engine.get_latest_valid_dossier()
        self.assertIsNotNone(latest)
        self.assertEqual(latest["id"], "study-4")

    def test_synthesis_document_excludes_empty_dossier(self):
        # 1. Scrive uno studio valido precedente
        valid_rec = {
            "id": "study-valid-01",
            "pillar_id": "aleksander_axioms",
            "domain": "Coscienza Sintetica",
            "model_used": "flint:latest",
            "ast_valid": True,
            "prototype_file": "proto_valid.py",
            "findings_summary": "Assiomi formalmente verificati.",
            "evidence": {"tier": PLAUSIBLE, "basis": []},
        }
        with open(self.engine.deep_dives_log, "w", encoding="utf-8") as f:
            f.write(json.dumps(valid_rec) + "\n")

        # 2. Aggiorna sintesi con un record che ha summary vuoto
        empty_rec = {
            "id": "study-empty-02",
            "pillar_id": "swarm_emergence",
            "domain": "Swarm AI",
            "model_used": "ollama:mock",
            "ast_valid": False,
            "prototype_file": None,
            "findings_summary": "",
            "evidence": {"tier": PLAUSIBLE, "basis": []},
        }
        self.engine._update_synthesis_document(empty_rec)

        md_text = self.engine.synthesis_md.read_text(encoding="utf-8")
        # Deve aver ripiegato sull'ultimo valido (study-valid-01), non mostrare quello vuoto
        self.assertIn("Coscienza Sintetica", md_text)
        self.assertIn("Assiomi formalmente verificati.", md_text)
        self.assertNotIn("study-empty-02", md_text)

    def test_synthesis_document_handles_all_empty_dossiers(self):
        # Nessun record valido
        empty_rec = {
            "id": "study-empty-01",
            "pillar_id": "p1",
            "domain": "Empty Domain",
            "findings_summary": "",
        }
        self.engine._update_synthesis_document(empty_rec)
        md_text = self.engine.synthesis_md.read_text(encoding="utf-8")
        self.assertIn("Nessuno studio con sommario valido registrato", md_text)


class TestMemoryEvidenceE3ResearchTree(unittest.TestCase):
    """Verifica il filtraggio dell'albero e il rilevamento test in ResearchTreeManager."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.tmp.name)
        self.data_dir = self.root_dir / "data" / "research"
        self.tree_mgr = ResearchTreeManager(data_dir=self.data_dir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_sync_deep_dives_skips_empty_summaries(self):
        records = [
            {
                "id": "study-valid",
                "findings_summary": "Studio sintetico valido",
                "ast_valid": True,
                "prototype_file": "proto_val.py",
                "domain": "Valid Domain",
                "pillar_id": "aleksander_axioms",
            },
            {
                "id": "study-empty",
                "findings_summary": "",
                "ast_valid": False,
                "prototype_file": None,
                "domain": "Empty Domain",
                "pillar_id": "aleksander_axioms",
            },
        ]
        with open(self.tree_mgr.deep_dives_log, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

        nodes = []
        self.tree_mgr._sync_deep_dives_to_tree(nodes)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["id"], "node-study-valid")

    def test_find_exercising_tests_detection(self):
        tests_dir = self.root_dir / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)

        # File 1 importa shared.my_target
        (tests_dir / "test_one.py").write_text(
            "import unittest\nfrom shared.my_target import MyTargetClass\n",
            encoding="utf-8",
        )
        # File 2 importa direttamente my_target
        (tests_dir / "test_two.py").write_text(
            "import unittest\nimport my_target\n",
            encoding="utf-8",
        )
        # File 3 non importa my_target
        (tests_dir / "test_three.py").write_text(
            "import unittest\nimport other_module\n",
            encoding="utf-8",
        )

        found = find_exercising_tests(
            target_module="my_target.py",
            tests_dir=tests_dir,
            repo_root=self.root_dir,
        )
        self.assertEqual(sorted(found), ["tests/test_one.py", "tests/test_two.py"])

        # Modulo inesistente
        none_found = find_exercising_tests(
            target_module="unreferenced_mod.py",
            tests_dir=tests_dir,
            repo_root=self.root_dir,
        )
        self.assertEqual(none_found, [])


class TestMemoryEvidenceE3Promotion(unittest.TestCase):
    """Verifica l'attribuzione di evidence (verified vs plausible) durante la promozione."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.tmp.name)
        self.promotions_file = self.root_dir / "data" / "research" / "promotions.jsonl"
        self.promotions_file.parent.mkdir(parents=True, exist_ok=True)
        self.prototypes_dir = self.root_dir / "data" / "research" / "prototypes"
        self.prototypes_dir.mkdir(parents=True, exist_ok=True)
        self.shared_dir = self.root_dir / "shared"
        self.shared_dir.mkdir(parents=True, exist_ok=True)
        self.tests_dir = self.root_dir / "tests"
        self.tests_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_promote_single_with_passing_exercising_tests_is_verified(self):
        # 1. Crea un prototipo valido
        proto_content = "class TargetPromotedService:\n    def compute(self):\n        return 42\n"
        proto_name = "proto_target_test_123.py"
        (self.prototypes_dir / proto_name).write_text(proto_content, encoding="utf-8")

        # 2. Crea un test che importa il target
        test_content = (
            "import unittest\nfrom shared.target_promoted_service import TargetPromotedService\n"
            "class MyTest(unittest.TestCase):\n"
            "    def test_compute(self):\n"
            "        self.assertEqual(TargetPromotedService().compute(), 42)\n"
        )
        (self.tests_dir / "test_target_promoted.py").write_text(test_content, encoding="utf-8")

        promoter = PrototypePromoter()

        # Patch ROOT, PROTOTYPES_DIR, SHARED_DIR, PROMOTIONS_FILE
        with patch("scripts.diagnostics.promote_research_prototype.ROOT", self.root_dir), \
             patch("scripts.diagnostics.promote_research_prototype.PROTOTYPES_DIR", self.prototypes_dir), \
             patch("scripts.diagnostics.promote_research_prototype.SHARED_DIR", self.shared_dir), \
             patch("scripts.diagnostics.promote_research_prototype.PROMOTIONS_FILE", self.promotions_file), \
             patch("scripts.diagnostics.promote_research_prototype.run_pytest_verification", return_value=(True, "4 passed")), \
             patch("scripts.diagnostics.promote_research_prototype.run_test_command", return_value=(0, "1 passed in 0.01s")):

            res = promoter.promote_single(
                prototype_filename=proto_name,
                target_name="target_promoted_service.py",
                verify_pytest=True,
            )

        self.assertTrue(res.get("success"), res.get("error"))
        evidence = res.get("evidence")
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence["tier"], VERIFIED)
        self.assertEqual(len(evidence["basis"]), 1)
        check = evidence["basis"][0]
        self.assertEqual(check["kind"], "check")
        self.assertEqual(check["exit_code"], 0)
        self.assertEqual(len(check["output_sha256"]), 64)
        self.assertIn("at", check)
        self.assertEqual(evidence["exercising_tests"], ["tests/test_target_promoted.py"])

        # Validazione del contratto di memoria
        errors = validate_evidence(evidence)
        self.assertEqual(errors, [])

        # Verifica registrazione nel file promotions.jsonl
        lines = self.promotions_file.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["evidence"]["tier"], VERIFIED)
        self.assertEqual(record["test_exit_code"], 0)
        self.assertEqual(record["test_output_sha256"], check["output_sha256"])

    def test_promote_single_without_exercising_tests_is_plausible(self):
        # 1. Crea un prototipo valido
        proto_content = "class UntestedFeature:\n    def run(self):\n        return True\n"
        proto_name = "proto_untested_feature_123.py"
        (self.prototypes_dir / proto_name).write_text(proto_content, encoding="utf-8")

        # Nessun file in tests/ importa 'untested_feature'
        promoter = PrototypePromoter()

        with patch("scripts.diagnostics.promote_research_prototype.ROOT", self.root_dir), \
             patch("scripts.diagnostics.promote_research_prototype.PROTOTYPES_DIR", self.prototypes_dir), \
             patch("scripts.diagnostics.promote_research_prototype.SHARED_DIR", self.shared_dir), \
             patch("scripts.diagnostics.promote_research_prototype.PROMOTIONS_FILE", self.promotions_file), \
             patch("scripts.diagnostics.promote_research_prototype.run_pytest_verification", return_value=(True, "4 passed")):

            res = promoter.promote_single(
                prototype_filename=proto_name,
                target_name="untested_feature.py",
                verify_pytest=True,
            )

        self.assertTrue(res.get("success"), res.get("error"))
        evidence = res.get("evidence")
        self.assertIsNotNone(evidence)
        # Deve essere declassato o preservato a plausible
        self.assertEqual(evidence["tier"], PLAUSIBLE)
        self.assertEqual(evidence["basis"], [])
        self.assertIn("Nessun test esercita", evidence.get("reason", ""))

        errors = validate_evidence(evidence)
        self.assertEqual(errors, [])

        lines = self.promotions_file.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["evidence"]["tier"], PLAUSIBLE)
        self.assertIsNone(record["test_command"])

    def test_research_tree_manager_promote_prototype_evidence(self):
        # Verifica che anche ResearchTreeManager.promote_prototype rispetti il contratto E3
        proto_content = "class TreeService:\n    def ping(self):\n        return 'pong'\n"
        proto_name = "proto_tree_service_456.py"
        (self.prototypes_dir / proto_name).write_text(proto_content, encoding="utf-8")

        mgr = ResearchTreeManager(data_dir=self.root_dir / "data" / "research")
        mgr.promotions_file = self.promotions_file
        mgr.prototypes_dir = self.prototypes_dir

        with patch("shared.research_tree.ROOT", self.root_dir), \
             patch("shared.research_tree.find_exercising_tests", return_value=[]):
            res = mgr.promote_prototype(
                prototype_filename=proto_name,
                target_module_name="tree_service.py",
                verify_tests=False,
            )

        self.assertTrue(res.get("success"), res.get("error"))
        evidence = res.get("evidence")
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence["tier"], PLAUSIBLE)
        self.assertEqual(validate_evidence(evidence), [])


if __name__ == "__main__":
    unittest.main()
