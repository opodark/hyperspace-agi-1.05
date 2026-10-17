# SPDX-License-Identifier: Apache-2.0
# tests/test_mesh_sync_monitor.py
"""Test per l'endpoint di monitoraggio P2P Sync & Canali Crittografici (/mesh/sync/status)."""

import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
CP_DIR = ROOT / "control-plane"
if str(CP_DIR) not in sys.path:
    sys.path.insert(0, str(CP_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flask import Flask
from cp.mesh import _bp


class TestMeshSyncMonitor(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(_bp)
        self.client = self.app.test_client()

    @patch("cp.mesh._node_list")
    @patch("cp.doctor_mesh.run_mesh_codebase_and_health_checks")
    def test_mesh_sync_status_endpoint(self, mock_inspect, mock_nodes):
        mock_nodes.return_value = [{"node_id": "n1", "status": "active"}]
        mock_inspect.return_value = (
            [{"id": "mesh_encrypted_channel", "status": "ok", "detail": "All channels encrypted"}],
            [
                {
                    "node_id": "n1_local",
                    "alias": "MacBook",
                    "is_local": True,
                    "channel": "local_memory",
                    "channel_verified": True,
                    "codebase": {"git_commit": "7bed7952", "git_branch": "main", "git_dirty": False},
                    "hardware": {"power": {"ac_line": False, "battery_pct": 60.0}, "ram_free_gb": 4.0},
                },
                {
                    "node_id": "n2_remote",
                    "alias": "HP-Omen",
                    "is_local": False,
                    "endpoint": "http://100.104.238.125:8081",
                    "channel": "encrypted_ecdh_aes_gcm",
                    "channel_verified": True,
                    "public_key": "04d2ffc3115935f7b9384b202a175b797e053d6f",
                    "codebase": {"git_commit": "7bed7952", "git_branch": "main", "git_dirty": False},
                    "hardware": {"ac_line": True, "battery_pct": None, "vram_total_gb": 8.0},
                }
            ]
        )

        resp = self.client.get("/mesh/sync/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("protocol"), "ecdh-secp256k1-aes256gcm")
        self.assertEqual(data.get("peers_count"), 2)
        peers = data.get("peers", [])
        self.assertEqual(len(peers), 2)

        p1 = peers[0]
        self.assertEqual(p1["alias"], "MacBook")
        self.assertFalse(p1["power_ac"])
        self.assertEqual(p1["battery_pct"], 60.0)

        p2 = peers[1]
        self.assertEqual(p2["alias"], "HP-Omen")
        self.assertTrue(p2["power_ac"])
        self.assertEqual(p2["vram_gb"], 8.0)
        self.assertTrue(p2["fingerprint"].startswith("04d2ffc3"))


if __name__ == "__main__":
    unittest.main()
