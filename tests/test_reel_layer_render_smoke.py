# SPDX-License-Identifier: Apache-2.0
"""Exercise the actual masked FFmpeg path, including motion and impact filters."""
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations/tiktok_editor/app"))
try:
    from PIL import Image
    from autoedit import render
    from autoedit.effects import IMPACT_EFFECTS
    from autoedit.media import MediaItem
except ImportError as exc:
    if exc.name not in {"numpy", "librosa", "PIL"}:
        raise
    ENGINE = False
else:
    ENGINE = bool(shutil.which("ffmpeg"))


@unittest.skipUnless(ENGINE, "richiede runtime editor e FFmpeg")
class MaskedRenderSmokeTests(unittest.TestCase):
    def run_ffmpeg(self, cmd):
        return subprocess.run(cmd, check=True, capture_output=True, timeout=20)

    def test_image_motion_and_flash_with_and_without_outline(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(render, "_run", self.run_ffmpeg):
            root = Path(directory)
            Image.new("RGB", (160, 284), "blue").save(root / "image.png")
            Image.new("L", (160, 284), 255).save(root / "mask.png")
            item = MediaItem(path=root / "image.png", kind="image", width=160, height=284)
            for color in ("none", "cyan"):
                with self.subTest(outline=color):
                    out = root / f"{color}.mp4"
                    render.build_image_segment(item, .5, 160, 284, 30, "vivid", random.Random(1),
                        False, out, person_mask=root / "mask.png", motion="bounce",
                        impact=IMPACT_EFFECTS["flash"], outline_color=color, outline_strength=.8)
                    self.assertGreater(out.stat().st_size, 0)

    def test_video_mask_keeps_motion_and_flash(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(render, "_run", self.run_ffmpeg):
            root = Path(directory)
            for name, source in (("clip", "testsrc2=size=160x284:rate=30:duration=1"),
                                 ("mask", "color=white:size=160x284:rate=30:duration=1")):
                self.run_ffmpeg(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", source,
                                "-y", str(root / f"{name}.mp4")])
            item = MediaItem(path=root / "clip.mp4", kind="video", width=160, height=284, duration=1)
            out = root / "out.mp4"
            render.build_video_segment(item, .5, 160, 284, 30, "vivid", random.Random(1), out,
                person_mask=root / "mask.mp4", impact=IMPACT_EFFECTS["flash"], finish="vignette=PI/4.5")
            self.assertGreater(out.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
