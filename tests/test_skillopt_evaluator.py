# SPDX-License-Identifier: Apache-2.0
"""Test per il modulo diagnostico e Validation Gate di SkillOpt."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.diagnostics.skillopt_evaluator import (
    FORGE_MAX_BYTES,
    compute_sha256,
    evaluate_skill_gate,
    format_forge_draft,
    parse_frontmatter,
    scan_safety,
)


class TestSkillOptEvaluator(unittest.TestCase):
    def setUp(self):
        self.valid_skill = (
            "---\n"
            "name: test-skill\n"
            "description: Descrizione di test per la validazione della skill.\n"
            "---\n\n"
            "# Titolo Skill\n\n"
            "Regole: usa percorsi relativi allo workspace. Budget di massimo 3 step.\n"
            "Esegui assert per verificare l'artefatto: gate_verified.\n"
        )

    def test_frontmatter_extraction(self):
        meta, body = parse_frontmatter(self.valid_skill)
        self.assertEqual(meta.get("name"), "test-skill")
        self.assertIn("Descrizione di test", meta.get("description", ""))
        self.assertIn("# Titolo Skill", body)

    def test_sha256_computation(self):
        h = compute_sha256("test-content")
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))

    def test_evaluation_gate_passes_on_valid_skill(self):
        meta, _ = parse_frontmatter(self.valid_skill)
        res = evaluate_skill_gate(self.valid_skill, meta)
        self.assertTrue(res["passed"])
        self.assertEqual(res["score"], 100.0)
        self.assertLessEqual(res["byte_len"], FORGE_MAX_BYTES)

    def test_safety_catches_tokens_and_host_paths(self):
        unsafe_token = self.valid_skill + "\nBearer sk-1234567890abcdef123456\n"
        issues_token = scan_safety(unsafe_token)
        self.assertTrue(len(issues_token) > 0)

        unsafe_path = self.valid_skill + "\nFile path: /Users/opo/secret.txt\n"
        issues_path = scan_safety(unsafe_path)
        self.assertTrue(len(issues_path) > 0)

    def test_gate_fails_on_oversized_content(self):
        oversized = self.valid_skill + ("A" * (FORGE_MAX_BYTES + 100))
        meta, _ = parse_frontmatter(oversized)
        res = evaluate_skill_gate(oversized, meta)
        self.assertFalse(res["passed"])

    def test_forge_draft_export_format(self):
        meta, _ = parse_frontmatter(self.valid_skill)
        draft = format_forge_draft(Path("test-skill.md"), self.valid_skill, meta)
        self.assertEqual(draft["type"], "skill")
        self.assertEqual(draft["name"], "test-skill")
        self.assertTrue(draft["id"].startswith("skill-test-skill-"))
        self.assertEqual(draft["generator"], "skillopt-evaluator")
        self.assertEqual(draft["provenance"]["license"], "Apache-2.0")

    def test_pdf_mission_coder_skill_passes_validation(self):
        skill_path = Path(__file__).resolve().parents[1] / "docs" / "skills" / "pdf-mission-coder-skill.md"
        self.assertTrue(skill_path.exists())
        content = skill_path.read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(content)
        res = evaluate_skill_gate(content, meta)
        self.assertTrue(res["passed"], f"Checks failed: {res['checks']}")
        self.assertEqual(res["score"], 100.0)


if __name__ == "__main__":
    unittest.main()
