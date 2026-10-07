# SPDX-License-Identifier: Apache-2.0
import importlib.util
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "openwebui-tools" / "anna_batch_direct.py"
spec = importlib.util.spec_from_file_location("anna_batch_direct", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AnnaBatchDirectTests(unittest.TestCase):
    def test_numbered_scenes_only(self):
        self.assertEqual(module.parse_scenes("Crea scene:\n1. Primo ritratto\n2) Secondo ritratto"),
                         ["Primo ritratto", "Secondo ritratto"])

    def test_more_than_fifty_rejected_before_submit(self):
        with self.assertRaisesRegex(ValueError, "massimo"):
            module.parse_scenes("\n".join(f"{i}. Ritratto" for i in range(1, 52)))

    def test_pose_reference_is_per_scene_and_plain_text_stays_plain(self):
        self.assertEqual(module.parse_scenes(
            "1. [pose=pose/seduta.jpg] [strength=0.9] Anna seduta\n"
            "2. Anna in piedi"), [
                {"scene": "Anna seduta", "pose_image": "pose/seduta.jpg",
                 "pose_strength": 0.9}, "Anna in piedi"])
        with self.assertRaisesRegex(ValueError, "sintassi della posa"):
            module.parse_scenes("1. [pose=posa.jpg]")

    def test_result_lists_jobs_and_rejections(self):
        result = module.format_result({"accepted": [{"index": 1, "job_id": "abc",
                                                   "pose_mode": "image",
                                                   "pose_image": "posa.jpg"}],
                                       "rejected": [{"index": 2, "error": "coda piena"}]})
        self.assertIn("1=abc", result)
        self.assertIn("image:posa.jpg", result)
        self.assertIn("2: coda piena", result)


if __name__ == "__main__":
    unittest.main()
