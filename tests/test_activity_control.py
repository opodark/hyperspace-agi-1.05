# SPDX-License-Identifier: Apache-2.0
"""The public activity page must not turn into an unauthenticated queue control."""
import ast
import os
import unittest
from pathlib import Path
from unittest import mock

from flask import Flask, jsonify, request

from shared.image_jobs import ImmagineQueue, nuovo_job
from shared.image_memory_gate import ImageMemoryGate
from shared.network_security import token_authorized


class ActivityControlTests(unittest.TestCase):
    def test_token_and_pause_resume_of_persisted_queue(self):
        source = Path(__file__).resolve().parents[1] / "control-plane" / "main.py"
        function = next(node for node in ast.parse(source.read_text()).body
                        if isinstance(node, ast.FunctionDef) and node.name == "activity_control")
        function.decorator_list = []
        queue = ImmagineQueue()
        job = queue.accoda(nuovo_job("un faro"))
        app = Flask(__name__)
        scope = {"os": os, "request": request, "jsonify": jsonify,
                 "token_authorized": token_authorized, "image_queue": queue,
                 "image_memory_gate": ImageMemoryGate()}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), scope)
        app.add_url_rule("/activity/control", view_func=scope["activity_control"], methods=["POST"])
        client = app.test_client()
        with mock.patch.dict(os.environ, {"WEBUI_TOOLS_TOKEN": "a" * 32}):
            self.assertEqual(client.post("/activity/control", json={"target": "images", "action": "stop"}).status_code, 401)
            headers = {"Authorization": "Bearer " + "a" * 32}
            self.assertEqual(client.post("/activity/control", json={"target": "images", "action": "stop"}, headers=headers).status_code, 200)
            self.assertIsNone(queue.prossimo())
            self.assertEqual(client.post("/activity/control", json={"target": "images", "action": "start"}, headers=headers).status_code, 200)
            self.assertEqual(queue.prossimo()["id"], job["id"])


if __name__ == "__main__":
    unittest.main()
