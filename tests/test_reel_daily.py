# SPDX-License-Identifier: Apache-2.0
import json
import ast
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo
from types import SimpleNamespace

from shared import reel_daily
from shared.webui_custom_tools.reel_editor import prepare_reel_project
from scripts import reel_daily_scheduler


class ReelDailyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        project = self.root / "reel-projects" / "reel-012345abcdef"
        (project / "media").mkdir(parents=True)
        (project / "media" / "clip.mp4").write_bytes(b"media")
        (project / "audio").mkdir()
        (project / "audio" / "song.mp3").write_bytes(b"audio")
        (project / "manifest.json").write_text(json.dumps({
            "creator": "Anna", "audio_file": "audio/song.mp3"
        }))
        self.project = project

    def test_project_tool_copies_audio_into_project(self):
        share = self.root / "share"
        share.mkdir()
        (share / "clip.mp4").write_bytes(b"clip")
        (share / "song.mp3").write_bytes(b"song")
        with patch.dict(os.environ, {"WEBUI_SHARE_DIR": str(share)}):
            result = prepare_reel_project("share", ["clip.mp4"], creator="Anna",
                                          audio_filename="song.mp3")
        staged = share / "reel-projects" / result["project"]
        manifest = json.loads((staged / "manifest.json").read_text())
        self.assertEqual(manifest["audio_file"], "audio/song.mp3")
        self.assertEqual((staged / "audio" / "song.mp3").read_bytes(), b"song")
        scheduled = reel_daily.validate_schedule(share, result["project"],
                                                 "09:00", "Europe/Rome", 30)
        self.assertEqual(scheduled["creator"], "Anna")

    def test_schedule_validates_project_and_can_cancel(self):
        result = reel_daily.create_schedule(self.root, "reel-012345abcdef")
        self.assertTrue(result["ok"])
        self.assertEqual(result["daily_time"], "09:00")
        with self.assertRaises(ValueError):
            reel_daily.create_schedule(self.root, "reel-012345abcdef")
        cancelled = reel_daily.cancel_schedule(self.root)
        self.assertFalse(cancelled["enabled"])

    def test_schedule_rejects_missing_audio_and_bad_time(self):
        with self.assertRaisesRegex(ValueError, "HH:MM"):
            reel_daily.validate_schedule(self.root, "reel-012345abcdef", "25:00", "Europe/Rome", 30)
        (self.project / "audio" / "song.mp3").unlink()
        with self.assertRaises((ValueError, FileNotFoundError)):
            reel_daily.validate_schedule(self.root, "reel-012345abcdef", "09:00", "Europe/Rome", 30)

    def test_daily_tick_claims_date_before_render_to_prevent_duplicates(self):
        reel_daily.create_schedule(self.root, "reel-012345abcdef", "09:00")
        now = datetime(2026, 10, 6, 10, 0, tzinfo=ZoneInfo("Europe/Rome"))
        fake_result = {"status": "needs_review"}
        with patch.object(reel_daily_scheduler, "SHARE", self.root), \
             patch.object(reel_daily_scheduler, "render", return_value=fake_result) as render:
            self.assertEqual(reel_daily_scheduler.tick(self.root, now), fake_result)
            self.assertIsNone(reel_daily_scheduler.tick(self.root, now))
        self.assertEqual(render.call_count, 1)

    def test_worker_resolves_audio_and_output_under_explicit_share(self):
        reel_daily.create_schedule(self.root, "reel-012345abcdef")
        seen = []
        def run(argv, **kwargs):
            seen.append(argv)
            if "--audio" in argv:
                self.assertEqual(Path(argv[argv.index("--audio") + 1]),
                                 (self.project / "audio/song.mp3").resolve())
                Path(argv[argv.index("--out") + 1]).write_bytes(b"render")
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps({
                "format": {"duration": "30.0"}, "streams": [
                    {"codec_type": "audio"}, {"codec_type": "video", "width": 1080, "height": 1920}]}))
        with patch.object(reel_daily_scheduler.subprocess, "run", side_effect=run):
            result = reel_daily_scheduler.tick(self.root,
                datetime(2026, 10, 6, 10, tzinfo=ZoneInfo("Europe/Rome")))
        self.assertEqual(result["status"], "needs_review", result)
        self.assertEqual(Path(result["output"]).read_bytes(), b"render")
        self.assertEqual(len(seen), 2)
        self.assertFalse(list(self.root.rglob("*.partial.mp4")))

    def test_cancel_clears_manual_request(self):
        reel_daily.create_schedule(self.root, "reel-012345abcdef")
        reel_daily.request_render_now(self.root)
        reel_daily.cancel_schedule(self.root)
        self.assertFalse(reel_daily.get_status(self.root)["queued_now"])

    def test_manual_render_supplies_daily_reel_without_duplicate(self):
        reel_daily.create_schedule(self.root, "reel-012345abcdef")
        reel_daily.request_render_now(self.root)
        with patch.object(reel_daily_scheduler, "render") as render:
            reel_daily_scheduler.tick(self.root, datetime(2026, 10, 6, 8, tzinfo=ZoneInfo("Europe/Rome")))
            reel_daily_scheduler.tick(self.root, datetime(2026, 10, 6, 10, tzinfo=ZoneInfo("Europe/Rome")))
        self.assertEqual(render.call_count, 1)

    def test_anna_approved_media_can_include_shared_audio(self):
        images = self.root / "anna"
        images.mkdir()
        (images / "anna.jpg").write_bytes(b"image")
        (self.root / "song.mp3").write_bytes(b"audio")
        review = self.root / "review.json"
        review.write_text(json.dumps({"results": {"anna.jpg": {"esito": "ok"}}}))
        with patch.dict(os.environ, {"WEBUI_SHARE_DIR": str(self.root),
                "WEBUI_ANNA_IMAGES_DIR": str(images), "ANNA_REVIEW_STATE_FILE": str(review)}):
            result = prepare_reel_project("anna", ["anna.jpg"], creator="Anna", audio_filename="song.mp3")
        self.assertEqual(result["audio"], "song.mp3")

    def test_gui_loads_staged_audio_with_project(self):
        path = Path(__file__).resolve().parents[1] / "integrations/tiktok_editor/app/gui.py"
        tree = ast.parse(path.read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == "_open_webui_project")
        manifest = json.loads((self.project / "manifest.json").read_text())
        manifest["filenames"] = ["clip.mp4"]
        (self.project / "manifest.json").write_text(json.dumps(manifest))
        env = {"Path": Path, "json": json,
               "WEBUI_PROJECTS": self.root / "reel-projects",
               "gr": SimpleNamespace(Error=ValueError, update=lambda **kwargs: kwargs)}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), env)
        result = env["_open_webui_project"](self.project.name)
        self.assertEqual(Path(result[-1]), (self.project / "audio/song.mp3").resolve())

    def test_failed_renderer_never_promotes_partial_video(self):
        reel_daily.create_schedule(self.root, "reel-012345abcdef")
        def fail(argv, **kwargs):
            Path(argv[argv.index("--out") + 1]).write_bytes(b"incomplete")
            return SimpleNamespace(returncode=1, stdout="", stderr="render failed")
        with patch.object(reel_daily_scheduler.subprocess, "run", side_effect=fail):
            state = reel_daily_scheduler.tick(self.root,
                datetime(2026, 10, 6, 10, tzinfo=ZoneInfo("Europe/Rome")))
        self.assertEqual(state["status"], "failed")
        self.assertFalse(list((self.root / "reel-review").glob("*.mp4")))


if __name__ == "__main__":
    unittest.main()
