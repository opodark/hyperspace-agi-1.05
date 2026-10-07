"""WebUI project handoff and safe VL profile validation."""
from __future__ import annotations

import json
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "integrations" / "tiktok_editor" / "app"
sys.path.insert(0, str(APP))
sys.path.append(str(ROOT))  # shared/webui_custom_tools/ vive nella radice del repository

# numpy e librosa sono il motore dell'editor, non dipendenze del repository (vedi
# AGENTS.md): senza di esse questo modulo salta invece di far fallire la raccolta
# dell'intera suite. Lo skip vale solo per le dipendenze opzionali: un import
# rotto per altre ragioni deve continuare a farsi sentire.
try:
    from PIL import Image
    from autoedit.scene_vision import analyze_scene, validate_scene  # noqa: E402
    from autoedit.pipeline import apply_scene_profiles  # noqa: E402
    from autoedit.render import Segment  # noqa: E402
    from autoedit.media import MediaItem  # noqa: E402
    from shared.webui_custom_tools.reel_editor import prepare_reel_project  # noqa: E402
except ImportError as exc:
    if exc.name not in {"numpy", "librosa", "PIL"}:
        raise
    Image = None
    analyze_scene = validate_scene = apply_scene_profiles = None
    Segment = MediaItem = prepare_reel_project = None
    _ENGINE = False
else:
    _ENGINE = True


@unittest.skipUnless(_ENGINE, "richiede il runtime dell'editor (numpy/librosa)")
class ReelWebUIVisionTests(unittest.TestCase):
    def test_scene_profile_allowlists_effects(self):
        profile = validate_scene({"subject": "Anna", "background": "spiaggia",
                                  "subject_position": "left", "style": "evil", "motion": "shell"})
        self.assertEqual(profile["subject"], "Anna")
        self.assertEqual(profile["background"], "spiaggia")
        self.assertEqual(profile["style"], "vivid")
        self.assertEqual(profile["motion"], "kenburns")
        self.assertEqual(profile["impact"], "none")

    def test_scene_profile_reaches_render_segment(self):
        item = MediaItem(path=Path("scene.jpg"), kind="image")
        strong = Segment(item=item, duration=1, transition="cut", accented=True, strong=True)
        plain = Segment(item=item, duration=1, transition="cut", accented=False, strong=False)
        apply_scene_profiles([strong, plain], {"scene.jpg": {
            "style": "neon", "motion": "sway", "impact": "pulse",
        }})
        self.assertEqual(strong.color_style, "neon")
        self.assertEqual(strong.motion, "sway")
        self.assertEqual(strong.impact_key, "pulse")
        self.assertEqual(plain.impact_key, "")

    def test_native_vision_response_is_validated(self):
        with tempfile.TemporaryDirectory() as temporary:
            image = Path(temporary) / "scene.jpg"
            Image.new("RGB", (16, 16), "blue").save(image)
            active = io.BytesIO(b'{"models":[]}')
            reply = io.BytesIO(json.dumps({"message": {"content": json.dumps({
                "subject": "persona", "background": "spiaggia", "style": "warm",
                "motion": "sway", "impact": "pulse",
            })}}).encode())
            with patch("urllib.request.urlopen", side_effect=[active, reply]) as urlopen:
                profile = analyze_scene(image, "🕸️ qwen3-vl:4b-instruct")
            self.assertEqual(profile["background"], "spiaggia")
            self.assertEqual(profile["impact"], "pulse")
            self.assertEqual(urlopen.call_count, 2)

    def test_webui_share_stages_exact_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            share = Path(temporary)
            (share / "frame.jpg").write_bytes(b"test-media")
            with patch.dict(os.environ, {"WEBUI_SHARE_DIR": str(share)}):
                result = prepare_reel_project("share", ["frame.jpg"])
            target = share / "reel-projects" / result["project"]
            self.assertEqual((target / "media" / "frame.jpg").read_bytes(), b"test-media")
            self.assertEqual(json.loads((target / "manifest.json").read_text())["filenames"],
                             ["frame.jpg"])

    def test_webui_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {"WEBUI_SHARE_DIR": temporary}):
                with self.assertRaises(ValueError):
                    prepare_reel_project("share", ["../secret.jpg"])


if __name__ == "__main__":
    unittest.main()
