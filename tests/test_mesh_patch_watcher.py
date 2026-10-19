# SPDX-License-Identifier: Apache-2.0
"""Il watcher host applica le patch depositate dal nodo, atomicamente e una volta sola."""

import base64
import gzip
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "mesh_patch_watcher", str(ROOT / "scripts" / "mesh_patch_watcher.py"))
_watcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_watcher)
processa = _watcher.processa


def _patch_diretto(rel: str, contenuto: str) -> dict:
    data = contenuto.encode("utf-8")
    return {
        "type": "git_patch",
        "direct_files": {
            rel: {
                "content_gz_b64": base64.b64encode(gzip.compress(data)).decode("ascii"),
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        },
    }


class WatcherTests(unittest.TestCase):
    def test_applica_un_file_e_scrive_il_risultato(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches = root / "mesh-patches"
            patches.mkdir(parents=True, exist_ok=True)
            repo = root / "repo"
            (repo / "sub").mkdir(parents=True)
            (repo / "sub" / "x.py").write_text("vecchio")

            patch = _patch_diretto("sub/x.py", "nuovo = 1\n")
            (patches / "a1.json").write_text(
                json.dumps({"patch_id": "a1", "update": patch}), encoding="utf-8")

            res = processa(patches, repo)
            self.assertEqual(res["applied"], 1)
            self.assertEqual((repo / "sub" / "x.py").read_text(), "nuovo = 1\n")
            risultato = json.loads((patches / "a1.result.json").read_text(encoding="utf-8"))
            self.assertEqual(risultato["status"], "applied")
            self.assertEqual(risultato["applied_files"], ["sub/x.py"])

    def test_checksum_errato_non_corrompe_il_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches = root / "mesh-patches"
            patches.mkdir(parents=True, exist_ok=True)
            repo = root / "repo"
            repo.mkdir()
            (repo / "x.py").write_text("originale")

            patch = _patch_diretto("x.py", "contenuto alterato")
            patch["direct_files"]["x.py"]["sha256"] = "0" * 64  # checksum sbagliato
            (patches / "b1.json").write_text(
                json.dumps({"patch_id": "b1", "update": patch}), encoding="utf-8")

            res = processa(patches, repo)
            self.assertEqual(res["failed"], 1)
            self.assertEqual((repo / "x.py").read_text(), "originale")
            risultato = json.loads((patches / "b1.result.json").read_text(encoding="utf-8"))
            self.assertEqual(risultato["status"], "failed")

    def test_una_patch_elaborata_non_si_riapplica(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches = root / "mesh-patches"
            patches.mkdir(parents=True, exist_ok=True)
            repo = root / "repo"
            repo.mkdir()

            patch = _patch_diretto("x.py", "contenuto")
            (patches / "c1.json").write_text(
                json.dumps({"patch_id": "c1", "update": patch}), encoding="utf-8")

            self.assertEqual(processa(patches, repo)["applied"], 1)
            # seconda passata: il .result.json c'è già, non si riapplica
            self.assertEqual(processa(patches, repo), {"applied": 0, "failed": 0})

    def test_processa_con_test_gate_successo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches = root / "mesh-patches"
            patches.mkdir(parents=True, exist_ok=True)
            repo = root / "repo"
            repo.mkdir()
            (repo / "worker.py").write_text("old")

            patch = _patch_diretto("worker.py", "new = 2\n")
            (patches / "d1.json").write_text(
                json.dumps({"patch_id": "d1", "update": patch}), encoding="utf-8")

            from unittest.mock import patch as mock_patch
            with mock_patch.object(_watcher, "run_role_test_gate", return_value=(True, "Role test-gate superato")):
                res = processa(patches, repo, node_role="worker-gpu", run_tests=True)
                self.assertEqual(res["applied"], 1)
                risultato = json.loads((patches / "d1.result.json").read_text(encoding="utf-8"))
                self.assertEqual(risultato["status"], "applied")
                self.assertEqual(risultato["role"], "worker-gpu")

    def test_processa_con_test_gate_fallito_esegue_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patches = root / "mesh-patches"
            patches.mkdir(parents=True, exist_ok=True)
            repo = root / "repo"
            repo.mkdir()
            (repo / "worker.py").write_text("safe_original")

            patch = _patch_diretto("worker.py", "breaking_change = True\n")
            (patches / "e1.json").write_text(
                json.dumps({"patch_id": "e1", "update": patch}), encoding="utf-8")

            from unittest.mock import patch as mock_patch
            with mock_patch.object(_watcher, "run_role_test_gate", return_value=(False, "Regression in test_image_jobs")):
                with mock_patch.object(_watcher, "rollback_applied_files", return_value=True) as mock_rb:
                    res = processa(patches, repo, node_role="worker-gpu", run_tests=True)
                    self.assertEqual(res["failed"], 1)
                    mock_rb.assert_called_once()
                    risultato = json.loads((patches / "e1.result.json").read_text(encoding="utf-8"))
                    self.assertEqual(risultato["status"], "failed")
                    self.assertTrue(risultato["rollback_applied"])
                    self.assertIn("Role test-gate fallito", risultato["errors"][0])


if __name__ == "__main__":
    unittest.main()

