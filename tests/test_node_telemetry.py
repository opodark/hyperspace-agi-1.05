# SPDX-License-Identifier: Apache-2.0
# tests/test_node_telemetry.py
"""Test di unità per shared/node_telemetry.py (codebase, hardware, graphify e servizi)."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.node_telemetry import (
    get_codebase_status,
    get_system_hardware,
    get_services_status,
    collect_full_node_telemetry,
    _read_git_pure_python,
)


class NodeTelemetryTests(unittest.TestCase):
    def test_codebase_status_on_real_repo(self):
        """Verifica che il repository corrente venga rilevato con commit, branch e graphify."""
        status = get_codebase_status(str(ROOT))
        self.assertTrue(status["found"])
        self.assertNotEqual(status["git_commit"], "unknown")
        self.assertEqual(len(status["git_commit"]), 8)
        self.assertIn(status["git_branch"], ["main", "master", "detached"])
        self.assertIn("graphify", status)
        self.assertIn("freshness", status["graphify"])

    def test_pure_python_git_reader(self):
        """Verifica il parser pure-python leggendo un finto .git creato in cartella temporanea."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            git_dir = tmppath / ".git"
            git_dir.mkdir()
            (git_dir / "HEAD").write_text("ref: refs/heads/feature-doctor-mesh\n")
            heads_dir = git_dir / "refs" / "heads"
            heads_dir.mkdir(parents=True)
            fake_sha = "abcdef1234567890abcdef1234567890abcdef12"
            (heads_dir / "feature-doctor-mesh").write_text(fake_sha + "\n")

            res = _read_git_pure_python(git_dir)
            self.assertEqual(res["git_branch"], "feature-doctor-mesh")
            self.assertEqual(res["git_commit_full"], fake_sha)
            self.assertEqual(res["git_commit"], "abcdef12")

    def test_hardware_telemetry_schema(self):
        """Verifica che get_system_hardware restituisca i campi essenziali senza errori."""
        hw = get_system_hardware()
        self.assertIn("os", hw)
        self.assertIn("arch", hw)
        self.assertIn("cpu_count", hw)
        self.assertIn("ram_total_gb", hw)
        self.assertGreaterEqual(hw["cpu_count"], 1)

    def test_services_status_resilient_to_down_ports(self):
        """Verifica che get_services_status non crashi su porte spente o irraggiungibili."""
        serv = get_services_status(
            ollama_url="http://127.0.0.1:59999",
            laya_url="http://127.0.0.1:59998",
            comfy_url="http://127.0.0.1:59997",
        )
        self.assertFalse(serv["ollama"]["online"])
        self.assertFalse(serv["laya"]["online"])
        self.assertFalse(serv["comfyui"]["online"])

    def test_collect_full_node_telemetry_assembly(self):
        """Verifica l'assemblaggio del pacchetto completo di telemetria."""
        telemetry = collect_full_node_telemetry(
            node_id="test_node_id_123456",
            public_key_hex="04" + "aa" * 64,
            tier="hub",
            runtime_info={"active_requests": 2, "degraded": False},
            repo_hint=str(ROOT),
        )
        self.assertEqual(telemetry["node_id"], "test_node_id_123456")
        self.assertEqual(telemetry["tier"], "hub")
        self.assertIn("codebase", telemetry)
        self.assertIn("hardware", telemetry)
        self.assertIn("services", telemetry)
        self.assertEqual(telemetry["runtime"]["active_requests"], 2)


if __name__ == "__main__":
    unittest.main()
