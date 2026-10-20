# SPDX-License-Identifier: Apache-2.0
"""Unit test per endpoint /api/devloop del cockpit service (scripts/cockpit_service.py)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.cockpit_service import CockpitHandler


class TestCockpitDevloopEndpoint(unittest.TestCase):
    def test_devloop_handler_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            data_dir = tmppath / "data"
            data_dir.mkdir(parents=True)

            # Crea dati finti per testare il parsing
            (data_dir / "omen_dev_loop.jsonl").write_text(
                json.dumps({"cycle": 1, "success": True, "action": "test_ast"}) + "\n" +
                json.dumps({"cycle": 2, "success": True, "action": "graphify_sync"}) + "\n",
                encoding="utf-8"
            )

            (data_dir / "synthetic_cot_dataset.jsonl").write_text(
                json.dumps({"id": "sample-1", "prompt": "Scrivi un parser", "ast_verified": True}) + "\n",
                encoding="utf-8"
            )

            (data_dir / "codebase_chronicle.jsonl").write_text(
                json.dumps({"id": "mut-1", "action_type": "feat", "intent": "Test mutazione"}) + "\n",
                encoding="utf-8"
            )

            (data_dir / "omen_247_telemetry.jsonl").write_text(
                json.dumps({"gpu": {"temp_c": 64}, "thermal_alert": False}) + "\n",
                encoding="utf-8"
            )

            # Test CockpitHandler.handle_api_devloop
            with patch("scripts.cockpit_service.REPO_ROOT", tmppath):
                handler = MagicMock()
                # Binding handle_api_devloop to the mock
                CockpitHandler.handle_api_devloop(handler)

                # Verifica la chiamata a send_json
                handler.send_json.assert_called_once()
                payload = handler.send_json.call_args[0][0]

                self.assertEqual(payload["status"], "ok")
                self.assertEqual(payload["total_cycles"], 2)
                self.assertEqual(payload["cot_samples_count"], 1)
                self.assertEqual(payload["latest_sample"]["id"], "sample-1")
                self.assertEqual(len(payload["recent_chronicles"]), 1)
                self.assertEqual(payload["thermal"]["temp_c"], 64)
                self.assertFalse(payload["thermal"]["alert"])


if __name__ == "__main__":
    unittest.main()
