# SPDX-License-Identifier: Apache-2.0
import tempfile
import json
import unittest
import threading
from pathlib import Path

from PIL import Image

from shared.anna_vision_selection import AnnaVisionSelection, AnnaSecondPass, parse_verdict


class AnnaVisionSelectionTests(unittest.TestCase):
    def test_second_pass_can_pause_and_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "images"
            root.mkdir()
            for name in ("a.jpg", "b.jpg"):
                Image.new("RGB", (20, 20), "white").save(root / name)
            first = Path(directory) / "first.json"
            first.write_text(json.dumps({"status": "completed", "results": {
                name: {"esito": "da_rivedere"} for name in ("a.jpg", "b.jpg")}}))
            entered, release = threading.Event(), threading.Event()
            calls = []

            def ask(*_):
                calls.append(1)
                if len(calls) == 1:
                    entered.set()
                    release.wait(timeout=5)
                return '{"esito":"da_rivedere","anomalie":["mano"],"confidenza":0.8}'

            worker = AnnaSecondPass(root, first, Path(directory) / "second.json", "test", ask)
            worker.start()
            self.assertTrue(entered.wait(timeout=5))
            self.assertEqual(worker.stop()["status"], "pausing")
            release.set()
            worker.thread.join(timeout=5)
            self.assertEqual(worker.status()["processed"], 1)
            self.assertEqual(worker.status()["status"], "paused")
            worker.start()
            worker.thread.join(timeout=5)
            self.assertEqual(worker.status()["processed"], 2)

    def test_stop_attende_immagine_corrente_e_start_riprende(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "images"
            root.mkdir()
            for name in ("a.jpg", "b.jpg"):
                Image.new("RGB", (20, 20), "white").save(root / name)
            entered, release = threading.Event(), threading.Event()
            calls = []

            def ask(*_):
                calls.append(1)
                if len(calls) == 1:
                    entered.set()
                    release.wait(timeout=5)
                return '{"esito":"da_rivedere","anomalie":["mano"],"confidenza":0.8}'

            review = AnnaVisionSelection(root, Path(directory) / "state.json", "test", ask)
            review.start()
            self.assertTrue(entered.wait(timeout=5))
            self.assertEqual(review.stop()["status"], "pausing")
            release.set()
            review.thread.join(timeout=5)
            self.assertEqual((review.status()["status"], review.status()["processed"]),
                             ("paused", 1))
            review.start()
            review.thread.join(timeout=5)
            self.assertEqual((review.status()["status"], review.status()["processed"]),
                             ("completed", 2))

    def test_fast_second_pass_only_rechecks_review_and_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "images"
            root.mkdir()
            for name in ("ok.jpg", "review.jpg", "error.jpg"):
                Image.new("RGB", (20, 20), "white").save(root / name)
            first = Path(directory) / "first.json"
            first.write_text(json.dumps({"status": "completed_with_errors", "results": {
                "ok.jpg": {"esito": "ok"}, "review.jpg": {"esito": "da_rivedere"},
                "error.jpg": {"esito": "errore"}}}))
            answers = iter(['{"esito":"ok","anomalie":[],"confidenza":0.96}',
                            '{"esito":"da_rivedere","anomalie":["dito extra"],"confidenza":0.9}'])
            second = AnnaSecondPass(root, first, Path(directory) / "second.json",
                                    "test-vision", lambda *_: next(answers))
            second.start()
            second.thread.join(timeout=5)
            state = second.status()
            self.assertEqual((state["status"], state["total"], state["selected"],
                              state["to_review"], state["errors"]),
                             ("completed", 2, 1, 1, 0))
            promoted = list((root / second.FOLDER).iterdir())
            self.assertEqual(len(promoted), 1)
            self.assertTrue((root / promoted[0].name).is_file())
            self.assertEqual(second.start()["job_id"], state["job_id"])

    def test_parses_fenced_json_and_rejects_prose(self):
        self.assertEqual(parse_verdict('```json\n{"esito":"ok","anomalie":[],"confidenza":0.9}\n```'),
                         ("ok", "anatomia visibile coerente"))
        self.assertEqual(parse_verdict('{"esito":"ok","anomalie":["dito extra"],"confidenza":0.9}')[0],
                         "da_rivedere")
        with self.assertRaises(ValueError):
            parse_verdict("Sembra tutto corretto")

    def test_real_files_are_copied_after_visual_verdict(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "images"
            root.mkdir()
            for name in ("a.jpg", "b.jpg"):
                Image.new("RGB", (20, 20), "white").save(root / name)
            answers = iter(['{"esito":"ok","anomalie":[],"confidenza":0.95}',
                            '{"esito":"ok","anomalie":[],"confidenza":0.95}',
                            '{"esito":"da_rivedere","anomalie":["mano incerta"],"confidenza":0.9}'])
            review = AnnaVisionSelection(root, Path(directory) / "state.json", "test-vision",
                                         lambda model, image, prompt: next(answers))
            self.assertTrue(review.start()["job_id"])
            review.thread.join(timeout=5)
            state = review.status()
            self.assertEqual((state["status"], state["processed"], state["selected"],
                              state["to_review"], state["errors"]),
                             ("completed", 2, 1, 1, 0))
            self.assertTrue((root / "Anna_selezionate" / "a.jpg").is_file())
            self.assertTrue((root / "Anna_da_rivedere" / "b.jpg").is_file())
            self.assertTrue((root / "a.jpg").is_file())
            self.assertEqual(review.start()["job_id"], state["job_id"])

    def test_second_review_can_downgrade_first_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "images"
            root.mkdir()
            Image.new("RGB", (20, 20), "white").save(root / "a.jpg")
            answers = iter(['{"esito":"ok","anomalie":[],"confidenza":1}',
                            '{"esito":"da_rivedere","anomalie":["dito sospetto"],"confidenza":0.9}'])
            review = AnnaVisionSelection(root, Path(directory) / "state.json", "test-vision",
                                         lambda *_: next(answers))
            review.start()
            review.thread.join(timeout=5)
            self.assertEqual(review.status()["to_review"], 1)
            self.assertFalse((root / "Anna_selezionate" / "a.jpg").exists())

    def test_second_review_without_a_defect_does_not_veto(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "images"
            root.mkdir()
            Image.new("RGB", (20, 20), "white").save(root / "a.jpg")
            answers = iter(['{"esito":"ok","anomalie":[],"confidenza":0.98}',
                            '{"esito":"da_rivedere","anomalie":[],"confidenza":0.95}'])
            review = AnnaVisionSelection(root, Path(directory) / "state.json", "test-vision",
                                         lambda *_: next(answers))
            review.start()
            review.thread.join(timeout=5)
            self.assertEqual(review.status()["selected"], 1)

    def test_new_review_version_rechecks_old_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "images"
            root.mkdir()
            Image.new("RGB", (20, 20), "white").save(root / "a.jpg")
            old_dir = root / "Anna_selezionate"
            old_dir.mkdir()
            (old_dir / "a.jpg").write_bytes((root / "a.jpg").read_bytes())
            state_path = Path(directory) / "state.json"
            state_path.write_text('{"version":1,"status":"running","filenames":["a.jpg"],'
                                  '"results":{"a.jpg":{"esito":"ok","folder":"Anna_selezionate"}}}')
            review = AnnaVisionSelection(root, state_path, "test-vision",
                                         lambda *_: '{"esito":"da_rivedere","anomalie":["mano"],"confidenza":0.9}')
            review.start()
            review.thread.join(timeout=5)
            self.assertFalse((old_dir / "a.jpg").exists())
            self.assertTrue((root / "Anna_da_rivedere" / "a.jpg").exists())


if __name__ == "__main__":
    unittest.main()
