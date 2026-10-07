# SPDX-License-Identifier: Apache-2.0
"""The legacy WebUI tool forwards pose references without rewriting scenes."""
import importlib.util
import unittest
from pathlib import Path
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "openwebui-tools" / "anna_image_batch.py"
spec = importlib.util.spec_from_file_location("anna_image_batch", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AnnaImageBatchTests(unittest.TestCase):
    def test_pose_scene_is_forwarded_and_reported(self):
        tool = module.Tools()
        tool.valves.author = "operatore"
        scene = [{"scene": "Anna seduta", "pose_image": "posa-01.jpg", "pose_strength": 0.9}]
        reply = mock.Mock(status_code=201)
        reply.json.return_value = {"accepted": [{"index": 1, "job_id": "abc",
                                                 "pose_mode": "image",
                                                 "pose_image": "posa-01.jpg"}], "rejected": []}
        with mock.patch.object(module.requests, "post", return_value=reply) as post:
            result = tool.genera_anna_batch_con_pose(scene)
        self.assertEqual(post.call_args.kwargs["json"]["scene"], scene)
        self.assertIn("1=image (posa-01.jpg)", result)


if __name__ == "__main__":
    unittest.main()
