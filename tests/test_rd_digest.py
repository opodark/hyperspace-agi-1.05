# SPDX-License-Identifier: Apache-2.0
"""Digest R&D: contenuti e regole di attenzione."""
import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.diagnostics import rd_digest as rd


def iso(minutes_ago=1):
    t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes_ago)
    return t.isoformat()


def write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows))


class TestDigest(unittest.TestCase):
    def build(self, studies=(), promos=(), stream=(), state=None):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            research, nightly = d / "research", d / "nightly"
            (research / "prototypes").mkdir(parents=True)
            nightly.mkdir()
            write_jsonl(research / "agi_deep_dives.jsonl", studies)
            write_jsonl(research / "promotions.jsonl", promos)
            write_jsonl(nightly / "node_stream.jsonl", stream)
            (research / "auto_promotion_state.json").write_text(json.dumps(state or {"rejected": {}}))
            with patch.object(rd, "RESEARCH", research), patch.object(rd, "NIGHTLY", nightly):
                return rd.build_digest(24)

    def test_conteggi_e_testo_compatto(self):
        studies = [{"timestamp": iso(), "prototype_file": "p.py",
                    "generation": {"variants": 2, "repairs": 1, "tests_generated": True, "tests_passed": True}}] * 2
        promos = [{"timestamp": iso(), "target_module": "shared/x.py", "author": "auto_promoter",
                   "evidence": {"tier": "verified"}}]
        d = self.build(studies, promos)
        self.assertEqual(d["generazione"]["test_passati"], 2)
        self.assertEqual(d["generazione"]["riparazioni"], 2)
        self.assertEqual(d["promossi"][0]["modulo"], "shared/x.py")
        self.assertEqual(d["attenzione"], [])
        self.assertLess(len(rd.render(d)), 1500)

    def test_regole_di_attenzione(self):
        stream = [{"timestamp": iso(), "message": "HTTP Error 401: Unauthorized"}]
        studies = [{"timestamp": iso(), "generation": {"variants": 1, "tests_passed": False}}] * 12
        d = self.build(studies, [], stream)
        text = " ".join(d["attenzione"])
        self.assertIn("401", text)
        self.assertIn("nessuna promozione", text)
        self.assertIn("30%", text)

    def test_nessuno_studio(self):
        self.assertIn("demone fermo", " ".join(self.build()["attenzione"]))

    def test_fuori_finestra_ignorato(self):
        old = [{"timestamp": iso(60 * 48), "generation": {"tests_passed": True}}]
        self.assertEqual(self.build(old)["generazione"]["studi"], 0)


if __name__ == "__main__":
    unittest.main()
