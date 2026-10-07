# SPDX-License-Identifier: Apache-2.0
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from shared import webui_tool_api as api
from shared import webui_tool_registry as registry


class WebUIToolAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.old = (api.SHARE, api.IMAGES, api.TOKEN, api.ACTIVITY, api.BATCH)
        self.addCleanup(self._restore)
        api.SHARE = Path(self.temp.name) / "share"
        api.IMAGES = Path(self.temp.name) / "anna"
        api.TOKEN = "x" * 32
        api.SHARE.mkdir()
        api.IMAGES.mkdir()
        app = Flask(__name__)
        app.register_blueprint(api.tools_api)
        self.client = app.test_client()
        self.headers = {"Authorization": "Bearer " + api.TOKEN}

    def _restore(self):
        api.SHARE, api.IMAGES, api.TOKEN, api.ACTIVITY, api.BATCH = self.old

    def post(self, path, data, authorized=True):
        return self.client.post(path, json=data, headers=self.headers if authorized else {})

    def test_spec_auth_and_file_operations(self):
        spec = self.client.get("/webui-tools/openapi.json")
        self.assertEqual(spec.status_code, 200)
        self.assertIn("/webui-tools/share/write", spec.json["paths"])
        self.assertIn("/webui-tools/anna/select", spec.json["paths"])
        self.assertIn("/webui-tools/anna/batch", spec.json["paths"])
        items = spec.json["paths"]["/webui-tools/anna/batch"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]["scene"]["items"]
        self.assertEqual(items["oneOf"][1]["properties"]["pose_image"]["type"], "string")
        self.assertIn("/webui-tools/anna/second-pass", spec.json["paths"])
        self.assertIn("/webui-tools/activity", spec.json["paths"])
        self.assertEqual(self.post("/webui-tools/share/list", {"path": "."}, False).status_code, 401)
        created = self.post("/webui-tools/share/write", {"path": "note/uno.txt", "content": "ciao"})
        self.assertEqual(created.status_code, 200)
        self.assertEqual(self.post("/webui-tools/share/read", {"path": "note/uno.txt"}).json["content"], "ciao")
        self.assertEqual(self.post("/webui-tools/share/write", {"path": "note/uno.txt", "content": "altro"}).status_code, 409)
        self.assertEqual(self.post("/webui-tools/share/read", {"path": "../fuori"}).status_code, 400)

    def test_anna_copy_keeps_originals_and_checks_conflicts(self):
        (api.IMAGES / "anna.jpg").write_bytes(b"image")
        self.assertEqual(self.post("/webui-tools/anna/list", {}).json["count"], 1)
        result = self.post("/webui-tools/anna/copy", {"filenames": ["anna.jpg"], "destination": "selezionate"})
        self.assertTrue(result.json["verified"])
        self.assertTrue((api.IMAGES / "anna.jpg").exists())
        self.assertEqual((api.IMAGES / "Anna_selezionate" / "anna.jpg").read_bytes(), b"image")
        self.assertEqual(self.post("/webui-tools/anna/copy", {"filenames": ["../anna.jpg"],
                         "destination": "da_rivedere"}).status_code, 400)

    def test_single_python_function_becomes_openapi_tool(self):
        @registry.tool
        def prova_semplice(testo: str) -> dict:
            """Restituisce una prova di registrazione."""
            return {"testo": testo.upper()}

        self.addCleanup(registry.TOOLS.pop, "prova_semplice", None)
        spec = self.client.get("/webui-tools/openapi.json").json
        operation = spec["paths"]["/webui-tools/custom/prova_semplice"]["post"]
        self.assertEqual(operation["operationId"], "prova_semplice")
        self.assertEqual(operation["requestBody"]["content"]["application/json"]["schema"]["required"], ["testo"])
        reply = self.post("/webui-tools/custom/prova_semplice", {"testo": "ciao"})
        self.assertEqual(reply.json["result"], {"testo": "CIAO"})
        self.assertEqual(self.post("/webui-tools/custom/prova_semplice", {"testo": 1}).status_code, 400)

    def test_monitor_is_read_only_and_signed(self):
        api.configure_activity(lambda: {"anna": {"status": "running", "processed": 5},
                                        "images": {"in_coda": 2, "ultimi": []}})
        page = self.post("/webui-tools/activity", {})
        self.assertEqual(page.status_code, 200)
        self.assertIn("text/html", page.content_type)
        self.assertIn("Content-Disposition", page.headers)
        self.assertEqual(self.client.get("/webui-tools/activity/live").status_code, 401)
        import re
        path = re.search(r'/webui-tools/activity/view\?expires=\d+&signature=[a-f0-9]+',
                         page.get_data(as_text=True)).group(0)
        view = self.client.get(path)
        self.assertEqual(view.status_code, 200)
        live = self.client.get(path.replace("/view?", "/live?"))
        self.assertEqual(live.json["anna"]["processed"], 5)

    def test_anna_batch_uses_server_callback(self):
        api.configure_batch(lambda scene: ({"ok": True, "accepted": scene}, 201))
        response = self.post("/webui-tools/anna/batch", {"scene": ["ritratto"]})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["accepted"], ["ritratto"])


if __name__ == "__main__":
    unittest.main()
