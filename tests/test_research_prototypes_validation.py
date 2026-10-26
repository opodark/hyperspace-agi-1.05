#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Unit and integration tests per la validazione automatica dei prototipi di ricerca HyperSpace.
Verifica:
- Ispezione AST di tutti i file in data/research/prototypes/
- Esecuzione corretta e isolata del PrototypeValidator
- Conformità funzionale dei 6 piloni scientifici (Aleksander, Causal, Swarm, Modular, Poetry, BioMesh)
- Allineamento delle metriche nell'albero genealogico R&D
"""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

from scripts.diagnostics.validate_research_prototypes import PrototypeValidator, PROTOTYPES_DIR
from shared.research_tree import ResearchTreeManager


class TestResearchPrototypesValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = PrototypeValidator(verbose=False)
        cls.summary = cls.validator.run_all()

    def test_prototypes_directory_exists_and_populated(self):
        """Verifica che la directory prototipi contenga i file generati dalle sessioni di ricerca."""
        self.assertTrue(PROTOTYPES_DIR.exists())
        proto_files = list(PROTOTYPES_DIR.glob("*.py"))
        self.assertGreaterEqual(len(proto_files), 10, "Devono essere presenti almeno 10 prototipi generati")

    def test_global_ast_validation_rate(self):
        """Verifica che tutti i prototipi generati rispettino la sintassi AST Python."""
        ast_results = self.validator.validate_all_ast()
        invalid = [r for r in ast_results if not r.get("ast_valid")]
        self.assertEqual(len(invalid), 0, f"Rilevati prototipi con sintassi non valida: {invalid}")

    def test_pillar_aleksander_axioms(self):
        """Verifica l'aderenza ai 5 assiomi di Aleksander."""
        res = self.summary["pillar_details"]["aleksander_axioms"]
        self.assertTrue(res.get("passed"), f"Errore nel pilone aleksander_axioms: {res.get('error')}")
        adherence = res.get("adherence_1402", {})
        for axiom in ["self_depiction", "imagination", "attention", "planning", "valuation"]:
            self.assertIn(axiom, adherence)
            self.assertGreaterEqual(adherence[axiom], 0.0)
            self.assertLessEqual(adherence[axiom], 1.0)

    def test_pillar_symbolic_causal_mesh(self):
        """Verifica il grafo causale SQLite + FTS5 e la risalita retrospettiva della lineage."""
        res = self.summary["pillar_details"]["symbolic_causal_mesh"]
        self.assertTrue(res.get("passed"), f"Errore nel pilone symbolic_causal_mesh: {res.get('error')}")
        self.assertEqual(res.get("events_recorded"), 3)
        self.assertGreaterEqual(res.get("lineage_depth"), 2)
        causes = res.get("causes_traced", [])
        self.assertIn("user_prompt", causes)

    def test_pillar_swarm_emergence(self):
        """Verifica lo sciame stigmergico, il gradiente di feromone e i vector clocks."""
        res = self.summary["pillar_details"]["swarm_emergence"]
        self.assertTrue(res.get("passed"), f"Errore nel pilone swarm_emergence: {res.get('error')}")
        grad = res.get("gradient", {})
        self.assertGreater(grad.get("average", 0.0), 0.0)
        self.assertGreaterEqual(grad.get("variance", 0.0), 0.0)
        self.assertTrue(res.get("vector_clocks_active"))

    def test_pillar_modular_intellect(self):
        """Verifica la memoria tri-modale, le note ricorsive e l'alignment auditor."""
        res = self.summary["pillar_details"]["modular_intellect"]
        self.assertTrue(res.get("passed"), f"Errore nel pilone modular_intellect: {res.get('error')}")
        self.assertGreaterEqual(res.get("traversed_nodes", 0), 2)
        self.assertTrue(res.get("alignment_auditor_verified"))

    def test_pillar_algorithmic_poetry(self):
        """Verifica la generazione poetica neuro-simbolica e il prompt visuale ComfyUI."""
        res = self.summary["pillar_details"]["algorithmic_poetry_aesthetics"]
        self.assertTrue(res.get("passed"), f"Errore nel pilone algorithmic_poetry: {res.get('error')}")
        self.assertEqual(res.get("verses_generated"), 4)

    def test_pillar_biomimetic_nature_mesh(self):
        """Verifica il calcolo dell'entropia di Shannon e la potatura link ad alta latenza."""
        res = self.summary["pillar_details"]["biomimetic_nature_mesh"]
        self.assertTrue(res.get("passed"), f"Errore nel pilone biomimetic_nature_mesh: {res.get('error')}")
        self.assertGreater(res.get("entropia_mesh", 0.0), 0.0)
        self.assertTrue(res.get("pruning_verified"))

    def test_all_pillars_global_success(self):
        """Verifica che l'esito globale di tutti i piloni sia 100% GREEN."""
        self.assertTrue(self.summary.get("all_pillars_passed"))
        self.assertEqual(self.summary.get("pillars_passed"), self.summary.get("pillars_evaluated"))


if __name__ == "__main__":
    unittest.main()
