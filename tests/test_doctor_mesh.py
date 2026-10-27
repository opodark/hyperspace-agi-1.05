# SPDX-License-Identifier: Apache-2.0
# tests/test_doctor_mesh.py
"""Test di unità per control-plane/cp/doctor_mesh.py."""

import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives.asymmetric import ec

ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CP_PATH = ROOT / "control-plane"
if str(CP_PATH) not in sys.path:
    sys.path.insert(0, str(CP_PATH))

from shared.crypto_channel import encrypt_envelope, pubkey_to_hex
from cp.doctor_mesh import poll_node_telemetry, run_mesh_codebase_and_health_checks


def _make_identity():
    priv = ec.generate_private_key(ec.SECP256K1())
    pub = priv.public_key()
    pub_hex = pubkey_to_hex(pub)
    node_id = hashlib.sha256(bytes.fromhex(pub_hex)).hexdigest()[:40]
    return {
        "node_id": node_id,
        "public_key": pub_hex,
        "_private_key": priv,
    }


class DoctorMeshTests(unittest.TestCase):
    def setUp(self):
        self.cp_id = _make_identity()
        self.node_id = _make_identity()

    @patch("requests.post")
    def test_poll_node_telemetry_successful_decryption(self, mock_post):
        """poll_node_telemetry riceve un envelope cifrato dal nodo e lo decifra correttamente."""
        telemetry_payload = {
            "node_id": self.node_id["node_id"],
            "codebase": {
                "git_commit": "4c56def9",
                "git_branch": "main",
                "git_dirty": False,
            },
            "services": {"ollama": {"online": True}},
        }

        # Simula nodo che cifra per la pubkey del CP
        envelope = encrypt_envelope(
            payload=telemetry_payload,
            recipient_pubkey_hex=self.cp_id["public_key"],
            sender_private_key=self.node_id["_private_key"],
            sender_node_id=self.node_id["node_id"],
            sender_pubkey_hex=self.node_id["public_key"],
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"encrypted": True, "envelope": envelope}
        mock_post.return_value = mock_resp

        res = poll_node_telemetry(
            endpoint="http://100.81.234.102:8081",
            node_pubkey=self.node_id["public_key"],
            cp_identity=self.cp_id,
        )

        self.assertEqual(res["channel"], "encrypted_ecdh_aes_gcm")
        self.assertTrue(res["channel_verified"])
        self.assertEqual(res["codebase"]["git_commit"], "4c56def9")

    @patch("requests.post")
    @patch("requests.get")
    def test_poll_node_telemetry_fallback_to_status(self, mock_get, mock_post):
        """Se il nodo non ha ancora /doctor/telemetry (404), fall-back su /status."""
        mock_post.return_value = MagicMock(status_code=404)
        mock_status = MagicMock()
        mock_status.status_code = 200
        mock_status.json.return_value = {
            "node_id": self.node_id["node_id"],
            "tier": "leaf",
            "vram_gb": 8.0,
            "engine": "ollama",
            "uptime_s": 120,
        }
        mock_get.return_value = mock_status

        res = poll_node_telemetry(
            endpoint="http://100.81.234.102:8081",
            node_pubkey=self.node_id["public_key"],
            cp_identity=self.cp_id,
        )

        self.assertEqual(res["channel"], "legacy_status")
        self.assertFalse(res["channel_verified"])
        self.assertEqual(res["hardware"]["vram_total_gb"], 8.0)

    def test_checks_alignment_ok_and_warning(self):
        """Verifica i check diagnostici con nodi allineati vs disallineati."""
        active_nodes = [
            {"node_id": "node_windows", "endpoint": "http://127.0.0.1:8084", "public_key": "04aa"},
        ]

        from shared.node_telemetry import get_codebase_status
        current_commit = get_codebase_status(str(ROOT)).get("git_commit", "unknown")

        with patch("cp.doctor_mesh.poll_node_telemetry") as mock_poll:
            # Caso 1: stesso commit
            mock_poll.return_value = {
                "channel": "encrypted_ecdh_aes_gcm",
                "codebase": {"git_commit": current_commit, "git_branch": "main", "git_dirty": False},
                "services": {"ollama": {"online": True}},
            }
            checks, _ = run_mesh_codebase_and_health_checks(active_nodes, self.cp_id, local_repo_hint=str(ROOT))
            align_check = next(c for c in checks if c["id"] == "mesh_codebase_alignment")
            self.assertEqual(align_check["status"], "ok")

            # Caso 2: commit disallineato
            mock_poll.return_value = {
                "channel": "encrypted_ecdh_aes_gcm",
                "codebase": {"git_commit": "3a12b01c", "git_branch": "main", "git_dirty": False},
                "services": {"ollama": {"online": True}},
            }
            checks_warn, _ = run_mesh_codebase_and_health_checks(active_nodes, self.cp_id, local_repo_hint=str(ROOT))
            align_warn = next(c for c in checks_warn if c["id"] == "mesh_codebase_alignment")
            self.assertEqual(align_warn["status"], "warn")
            self.assertIn("Disallineamento", align_warn["detail"])

            # Caso 3: commit disallineato ma role_aligned == True (coerenza di ruolo)
            mock_poll.return_value = {
                "channel": "encrypted_ecdh_aes_gcm",
                "tier": "worker-gpu",
                "codebase": {"git_commit": "3a12b01c", "git_branch": "main", "git_dirty": False, "role_aligned": True},
                "services": {"ollama": {"online": True}},
            }
            checks_role, _ = run_mesh_codebase_and_health_checks(active_nodes, self.cp_id, local_repo_hint=str(ROOT))
            align_role = next(c for c in checks_role if c["id"] == "mesh_codebase_alignment")
            self.assertEqual(align_role["status"], "ok")
            self.assertIn("Nodi coerenti per ruolo", align_role["detail"])

    def test_graph_check_compares_remote_nodes_with_local_graph(self):
        """Il check Graphify segnala i nodi remoti che non hanno ricevuto l'ultimo grafo."""
        active_nodes = [
            {"node_id": "node_omen", "alias": "omen", "endpoint": "http://127.0.0.1:8081", "public_key": "04aa"},
            {"node_id": "node_asus", "alias": "asus", "endpoint": "http://127.0.0.1:8082", "public_key": "04bb"},
        ]
        graph = {"available": True, "freshness": "fresh", "communities_count": 839, "size_bytes": 1000}
        local = {"codebase": {"git_commit": "abc", "graphify": graph}, "services": {}, "hardware": {}}

        def remote(size):
            return {
                "channel": "encrypted_ecdh_aes_gcm",
                "codebase": {"git_commit": "abc", "graphify": {**graph, "size_bytes": size}},
                "services": {},
            }

        with patch("cp.doctor_mesh.collect_full_node_telemetry", return_value=local), \
             patch("cp.doctor_mesh.poll_node_telemetry") as mock_poll:
            mock_poll.side_effect = [remote(1000), remote(1000)]
            checks, _ = run_mesh_codebase_and_health_checks(active_nodes, self.cp_id)
            graph_check = next(c for c in checks if c["id"] == "mesh_graph_freshness")
            self.assertEqual(graph_check["status"], "ok")
            self.assertIn("2/2", graph_check["detail"])

            mock_poll.side_effect = [remote(1000), remote(500)]
            checks, _ = run_mesh_codebase_and_health_checks(active_nodes, self.cp_id)
            graph_check = next(c for c in checks if c["id"] == "mesh_graph_freshness")
            self.assertEqual(graph_check["status"], "warn")
            self.assertIn("1/2", graph_check["detail"])
            self.assertIn("asus", graph_check["detail"])
            self.assertIn("--sync-graphify", graph_check["fix_hint"])


if __name__ == "__main__":
    unittest.main()

