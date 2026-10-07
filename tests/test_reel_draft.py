"""The reel draft survives a process restart without Gradio session state."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations" / "tiktok_editor" / "app"))
from draft import read_draft, valid_state, write_draft  # noqa: E402


class ReelDraftTests(unittest.TestCase):
    def test_persists_settings_and_media_state(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            media = base / "media"
            media.mkdir()
            (media / "scene.jpg").write_bytes(b"image")
            audio = base / "music.mp3"
            audio.write_bytes(b"audio")
            state = {"media_dir": str(media), "audio": str(audio),
                     "metas": [{"name": "scene.jpg"}]}
            write_draft(base, {"state": state})
            write_draft(base, {"settings": {"title_text": "Estate", "table": [[0, "scene.jpg", True, 0]]}})
            recovered = read_draft(base)
            self.assertTrue(valid_state(recovered["state"]))
            self.assertEqual(recovered["settings"]["title_text"], "Estate")
            audio.unlink()
            self.assertFalse(valid_state(recovered["state"]))


if __name__ == "__main__":
    unittest.main()
