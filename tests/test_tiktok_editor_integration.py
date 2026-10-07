"""Regression checks for the integrated reel editor."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1] / "integrations" / "tiktok_editor" / "app"
sys.path.insert(0, str(APP))

# numpy e librosa sono il motore dell'editor, non dipendenze del repository (vedi
# AGENTS.md): senza di esse questo modulo salta invece di far fallire la raccolta
# dell'intera suite. Lo skip vale solo per le dipendenze opzionali: un import
# rotto per altre ragioni deve continuare a farsi sentire.
try:
    from PIL import Image
    from autoedit.brief import discover_control_plane, validate_overrides  # noqa: E402
    from autoedit.guides import GUIDES, comics_for  # noqa: E402
    from autoedit.pipeline import crescendo_cut_times, fit_cut_times  # noqa: E402
    from autoedit.media import copy_upright_image  # noqa: E402
except ImportError as exc:
    if exc.name not in {"numpy", "librosa", "PIL"}:
        raise
    Image = None
    discover_control_plane = validate_overrides = None
    GUIDES = comics_for = None
    crescendo_cut_times = fit_cut_times = copy_upright_image = None
    _ENGINE = False
else:
    _ENGINE = True


@unittest.skipUnless(_ENGINE, "richiede il runtime dell'editor (numpy/librosa)")
class TikTokEditorIntegrationTests(unittest.TestCase):
    def test_autocut_exact_boundaries(self):
        cuts = fit_cut_times([0, 1, 2, 30, 30.1, 40], 45, 0, 30)
        self.assertEqual(cuts[0], 0)
        self.assertEqual(cuts[-1], 30)
        self.assertNotIn(30.1, cuts)

    def test_autocut_audio_start_and_hook(self):
        cuts = fit_cut_times([5, 5.5, 6, 7, 35], 40, 5, 30, 1)
        self.assertEqual(cuts[0], 6)
        self.assertEqual(cuts[-1], 35)

    def test_autocut_rejects_short_song(self):
        with self.assertRaisesRegex(ValueError, "meno di 60s"):
            fit_cut_times([1, 2], 59, 0, 60)

    def test_crescendo_timeline_has_exact_finale(self):
        cuts = crescendo_cut_times(12, 132)
        self.assertEqual(cuts[0], 12)
        self.assertIn(122, cuts)
        self.assertEqual(cuts[-1], 132)
        self.assertEqual(sum(cuts >= 122), 41)
        with self.assertRaisesRegex(ValueError, "120 secondi"):
            crescendo_cut_times(12, 131)

    def test_battista_preset_aligns_finale_with_bass_entry(self):
        preset = json.loads((APP / "presets" / "BATTISTA crescendo 2 minuti.json").read_text())
        self.assertTrue(preset["crescendo_finale"])
        cuts = crescendo_cut_times(preset["audio_start"], 157.083)
        self.assertAlmostEqual(cuts[-41], 123.7)
        self.assertAlmostEqual(cuts[-1], 133.7)

    def test_exif_portrait_is_upright_in_project_copy(self):
        with tempfile.TemporaryDirectory() as root:
            src = Path(root) / "source.jpg"
            dst = Path(root) / "copy.jpg"
            exif = Image.Exif()
            exif[274] = 8
            Image.new("RGB", (20, 10), "red").save(src, exif=exif)
            copy_upright_image(src, dst)
            with Image.open(src) as original, Image.open(dst) as upright:
                self.assertEqual(original.size, (20, 10))
                self.assertEqual(upright.size, (10, 20))
                self.assertEqual(upright.getexif().get(274, 1), 1)

    def test_local_control_plane_discovery(self):
        response = io.BytesIO(json.dumps({"data": [
            {"id": "🕸️ qwen3-vl:4b"}, {"id": "🕸️ qwen3:4b"},
            {"id": "other-remote"},
        ]}).encode())
        with patch("urllib.request.urlopen", return_value=response):
            cfg = discover_control_plane()
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.model, "🕸️ qwen3:4b")
        self.assertEqual(cfg.base_url, "http://127.0.0.1:8085/v1")

    def test_brief_duration_and_comic_cards(self):
        self.assertEqual(validate_overrides({"target_duration": 60})["target_duration"], 60)
        self.assertNotIn("target_duration", validate_overrides({"target_duration": 42}))
        self.assertIn("Autocut", comics_for("duration_preset"))
        self.assertGreaterEqual(len(GUIDES), 40)


if __name__ == "__main__":
    unittest.main()
