# SPDX-License-Identifier: Apache-2.0
"""Test per il parsing e rendering dei sottotitoli del TikTok Editor."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from PIL import Image

import sys
APP_DIR = Path(__file__).resolve().parents[1] / "integrations" / "tiktok_editor" / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# numpy e librosa sono il motore dell'editor, non dipendenze del repository (vedi
# AGENTS.md): senza di esse questo modulo salta invece di far fallire la raccolta
# dell'intera suite.
try:
    from PIL import Image
    from autoedit.overlays import render_subtitle_png
    from autoedit.pipeline import RenderConfig, _build_overlays
    from autoedit.subtitles import SubtitleCue, parse_srt, parse_subtitles, parse_timestamp, parse_vtt
    _ENGINE = True
except ImportError as exc:
    if exc.name not in {"numpy", "librosa", "PIL"}:
        raise
    Image = None
    render_subtitle_png = None
    RenderConfig = _build_overlays = None
    SubtitleCue = parse_srt = parse_subtitles = parse_timestamp = parse_vtt = None
    _ENGINE = False


SAMPLE_SRT = """1
00:00:01,000 --> 00:00:04,500
Mi piace pensare
a un <b>prato cibernetico</b>

2
00:00:04,800 --> 00:00:08,200
dove mammiferi e computer vivono insieme.
"""

SAMPLE_VTT = """WEBVTT

00:00:01.000 --> 00:00:04.500
Mi piace pensare
a un prato cibernetico

00:00:04.800 --> 00:00:08.200
dove mammiferi e computer vivono insieme.
"""


@unittest.skipUnless(_ENGINE, "richiede il runtime dell'editor (numpy/librosa/PIL)")
class TestSubtitles(unittest.TestCase):
    def test_parse_timestamp(self):
        self.assertAlmostEqual(parse_timestamp("00:00:05,500"), 5.5)
        self.assertAlmostEqual(parse_timestamp("00:01:02.250"), 62.25)
        self.assertAlmostEqual(parse_timestamp("01:10.500"), 70.5)
        self.assertAlmostEqual(parse_timestamp("15.2"), 15.2)

    def test_parse_srt(self):
        cues = parse_srt(SAMPLE_SRT)
        self.assertEqual(len(cues), 2)
        self.assertAlmostEqual(cues[0].start, 1.0)
        self.assertAlmostEqual(cues[0].end, 4.5)
        self.assertIn("Mi piace pensare", cues[0].text)
        self.assertIn("prato cibernetico", cues[0].text)
        self.assertNotIn("<b>", cues[0].text)  # HTML tag pulito
        self.assertAlmostEqual(cues[1].start, 4.8)
        self.assertAlmostEqual(cues[1].end, 8.2)

    def test_parse_vtt(self):
        cues = parse_vtt(SAMPLE_VTT)
        self.assertEqual(len(cues), 2)
        self.assertAlmostEqual(cues[0].start, 1.0)
        self.assertAlmostEqual(cues[0].end, 4.5)

    def test_parse_from_file_and_dict(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".srt", delete=False) as f:
            f.write(SAMPLE_SRT)
            f_path = Path(f.name)
        try:
            cues_file = parse_subtitles(f_path)
            self.assertEqual(len(cues_file), 2)
        finally:
            f_path.unlink(missing_ok=True)

        dict_cues = parse_subtitles([
            {"start": 0.5, "end": 2.0, "text": "Test battuta 1"},
            {"start": 2.2, "end": 4.0, "text": "Test battuta 2"},
        ])
        self.assertEqual(len(dict_cues), 2)
        self.assertEqual(dict_cues[0].text, "Test battuta 1")

    def test_render_subtitle_png_styles(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            for style in ("tiktok_bold", "box", "yellow", "minimal"):
                out_png = td_path / f"sub_{style}.png"
                render_subtitle_png("Test sottotitolo\nsu due righe", 1080, 1920,
                                    out_png, pos="bottom", style=style)
                self.assertTrue(out_png.is_file())
                with Image.open(out_png) as im:
                    self.assertEqual(im.size, (1080, 1920))
                    self.assertEqual(im.mode, "RGBA")

    def test_pipeline_build_overlays_with_subtitles(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            cfg = RenderConfig(
                media_dir=td_path,
                audio=td_path / "dummy.wav",
                subtitles_text=SAMPLE_SRT,
                subtitles_pos="bottom",
                subtitles_style="tiktok_bold",
            )
            overlays = _build_overlays(cfg, 1080, 1920, td_path,
                                       audio_offset=0.5, total_dur=10.0)
            self.assertEqual(len(overlays), 2)
            # Offset sottratto: 1.0 - 0.5 = 0.5
            self.assertAlmostEqual(overlays[0]["start"], 0.5)
            self.assertAlmostEqual(overlays[0]["end"], 4.0)
            self.assertTrue(Path(overlays[0]["png"]).is_file())


if __name__ == "__main__":
    unittest.main()
