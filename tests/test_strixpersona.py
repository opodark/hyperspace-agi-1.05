# SPDX-License-Identifier: Apache-2.0
"""Test per strixpersona-viewer (live_view + server) e guardie CLI persona-shell/strixpersona."""
import importlib.util
import json
import subprocess
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWER_DIR = ROOT / "scripts" / "strixpersona-viewer"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


live_view_mod = _load_module("strixpersona_live_view", VIEWER_DIR / "live_view.py")
server_mod = _load_module("strixpersona_server", VIEWER_DIR / "server.py")


class StrixPersonaViewerTests(unittest.TestCase):
    def test_live_view_records_agents_and_tool_lifecycle(self):
        view = live_view_mod.TuiLiveView()
        view.upsert_agent("root", name="Anna", status="running")
        view.record_user_message("root", "Analizza infra-ui")
        view.record_tool_call("root", "call_1", "shell", {"command": "ls -la"})
        view.record_tool_output("root", "call_1", "shell", "exit_code: 0", status="completed")
        view.record_assistant_message("root", "Nessun segreto trovato.")

        self.assertIn("root", view.agents)
        self.assertEqual(view.agents["root"]["name"], "Anna")
        self.assertEqual(len(view.events), 3)
        tool_ev = next(e for e in view.events if e["type"] == "tool")
        self.assertEqual(tool_ev["data"]["status"], "completed")
        self.assertEqual(tool_ev["data"]["result"], "exit_code: 0")
        self.assertGreaterEqual(tool_ev["version"], 1)

    def test_viewer_server_requires_session_and_handles_steer_confirmation(self):
        view = live_view_mod.TuiLiveView()
        view.upsert_agent("root", name="Anna", status="running")
        state = server_mod.ViewerState(view, {"run_name": "test-run", "status": "running", "finished": False})
        httpd, auth_link = server_mod.serve(state, open_browser=False)
        self.addCleanup(httpd.shutdown)

        base_url = auth_link.split("/?", 1)[0]

        # Senza cookie di sessione /api/run risponde 403
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"{base_url}/api/run", timeout=5)
        self.assertEqual(ctx.exception.code, 403)

        # Con il link autorizzato riceve il cookie di sessione e accede a /api/run e /api/transcript
        jar = CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        with opener.open(auth_link, timeout=5) as resp:
            self.assertEqual(resp.status, 200)

        with opener.open(f"{base_url}/api/run", timeout=5) as resp:
            run_data = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(run_data["run_name"], "test-run")

        # Verifica il ciclo di conferma via /api/agents/steer
        confirmed = []
        t = threading.Thread(target=lambda: confirmed.append(state.ask_confirmation("root", "ls", "elenco")))
        t.start()
        while state.pending_confirm is None:
            pass

        steer_req = urllib.request.Request(
            f"{base_url}/api/agents/steer",
            data=json.dumps({"message": "sì"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with opener.open(steer_req, timeout=5) as resp:
            steer_res = json.loads(resp.read().decode("utf-8"))
        self.assertTrue(steer_res["ok"])
        t.join(timeout=5)
        self.assertEqual(confirmed, [True])

    def test_node_scripts_help_and_syntax(self):
        for script in ("persona-shell.mjs", "strixpersona.mjs"):
            res = subprocess.run(
                ["node", str(ROOT / "scripts" / script), "--help"],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            self.assertIn("--shell", res.stdout)
            self.assertIn("--auto-deny", res.stdout)


if __name__ == "__main__":
    unittest.main()
