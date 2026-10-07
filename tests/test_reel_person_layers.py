"""Foreground/background grading is wired to a real pixel mask."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations" / "tiktok_editor" / "app"))

# numpy e librosa sono il motore dell'editor, non dipendenze del repository (vedi
# AGENTS.md): senza di esse questo modulo salta invece di far fallire la raccolta
# dell'intera suite. Lo skip vale solo per le dipendenze opzionali: un import
# rotto per altre ragioni deve continuare a farsi sentire.
try:
    from PIL import Image
    from autoedit.person_layers import layer_filter  # noqa: E402
    from autoedit.pipeline import RenderConfig, _build_overlays  # noqa: E402
except ImportError as exc:
    if exc.name not in {"numpy", "librosa", "PIL"}:
        raise
    Image = None
    layer_filter = RenderConfig = _build_overlays = None
    _ENGINE = False
else:
    _ENGINE = True


@unittest.skipUnless(_ENGINE, "richiede il runtime dell'editor (numpy/librosa)")
class PersonLayersTests(unittest.TestCase):
    def test_separate_grade_graph_uses_mask(self):
        graph = layer_filter(1080, 1920, "warm", "cold", 3, 0.62, 0.02, 0.45)
        self.assertIn("[bg][fg][mask]maskedmerge", graph)
        self.assertIn("gblur=sigma=3", graph)
        self.assertIn("gamma_r=1.06", graph)
        self.assertIn("rs=-.06", graph)
        self.assertIn("eq=brightness=-0.62", graph)
        self.assertIn("eq=brightness=0.02", graph)
        self.assertIn("eq=brightness=-0.45", graph)
        self.assertIn("format=gbrp", graph)

    def test_invalid_grade_is_rejected(self):
        with self.assertRaises(ValueError):
            layer_filter(1080, 1920, "unknown", "cold", 0)

    def test_cross_light_pulses_at_final_beats(self):
        with tempfile.TemporaryDirectory() as root:
            cfg = RenderConfig(media_dir=Path(root), audio=Path(root) / "audio.mp3",
                               crescendo_finale=True, cross_strobe=True, audio_start=13.7)
            overlays = _build_overlays(cfg, 360, 640, Path(root),
                                       SimpleNamespace(beat_times=[123.7, 124.2, 125.0]))
            self.assertEqual(overlays[0]["pulse_times"], [110.0, 110.5, 111.3])
            with Image.open(overlays[0]["png"]) as cross:
                self.assertGreater(cross.getpixel((180, 224))[3], 100)
                self.assertEqual(cross.getpixel((0, 0))[3], 0)


if __name__ == "__main__":
    unittest.main()
