# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "reel_media.py"
spec = importlib.util.spec_from_file_location("reel_media", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReelMediaTests(unittest.TestCase):
    def test_only_approved_anna_files_are_staged(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "source"
            source.mkdir()
            (source / "anna.jpg").write_bytes(b"anna")
            (source / "old.jpg").write_bytes(b"old")
            first = base / "first.json"
            first.write_text(json.dumps({"results": {
                "anna.jpg": {"esito": "ok"}, "old.jpg": {"esito": "da_rivedere"}}}))
            approved = module.anna_approved(first, base / "second.json")
            with self.assertRaises(ValueError):
                module.stage_media("Anna", source, base / "out", ["old.jpg"], approved)
            folder = module.stage_media("Anna", source, base / "out", ["anna.jpg"], approved)
            self.assertEqual((folder / "media" / "anna.jpg").read_bytes(), b"anna")
            self.assertEqual(json.loads((folder / "manifest.json").read_text())["persona"], "Anna")

    def test_aurora_requires_explicit_safe_names(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "source"
            source.mkdir()
            (source / "aurora.png").write_bytes(b"aurora")
            with self.assertRaises(ValueError):
                module.stage_media("Aurora", source, base / "out", ["../aurora.png"])
            folder = module.stage_media("Aurora", source, base / "out", ["aurora.png"])
            self.assertTrue((folder / "media" / "aurora.png").exists())


if __name__ == "__main__":
    unittest.main()
