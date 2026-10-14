# SPDX-License-Identifier: Apache-2.0
# tests/test_mesh_sync.py
"""Test di unità per shared/mesh_sync.py (creazione e applicazione patch e bundle P2P)."""

import base64
import gzip
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives.asymmetric import ec

ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.crypto_channel import pubkey_to_hex
from shared.mesh_sync import (
    create_git_patch_payload,
    create_graphify_bundle_payload,
    apply_mesh_update,
    distribute_payload_to_node,
)


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


class MeshSyncTests(unittest.TestCase):
    def setUp(self):
        self.sender = _make_identity()
        self.receiver = _make_identity()

    def test_create_and_apply_direct_files(self):
        """Verifica la creazione di un payload con file diretti e la sua applicazione corretta."""
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
            src_path = Path(src_dir)
            dst_path = Path(dst_dir)

            # Crea file sorgente
            test_file = src_path / "config" / "test_mesh.json"
            test_file.parent.mkdir(parents=True)
            test_content = b'{"mesh_network": "sovereign", "active": true}'
            test_file.write_bytes(test_content)

            # Pacchettizza
            payload = create_git_patch_payload(
                repo_dir=str(src_path),
                include_files=["config/test_mesh.json"],
            )
            self.assertEqual(payload["type"], "git_patch")
            self.assertIn("config/test_mesh.json", payload["direct_files"])

            # Applica nella destinazione
            res = apply_mesh_update(payload, repo_dir=str(dst_path))
            self.assertTrue(res["success"])
            self.assertIn("config/test_mesh.json", res["applied_files"])

            applied_dest = dst_path / "config" / "test_mesh.json"
            self.assertTrue(applied_dest.exists())
            self.assertEqual(applied_dest.read_bytes(), test_content)

    def test_apply_rollback_on_corrupted_checksum(self):
        """Verifica che un checksum corrotto blocchi l'applicazione e scateni il rollback."""
        with tempfile.TemporaryDirectory() as dst_dir:
            dst_path = Path(dst_dir)
            existing_file = dst_path / "secret.txt"
            existing_file.write_text("original content")

            fake_payload = {
                "type": "git_patch",
                "direct_files": {
                    "secret.txt": {
                        "content_gz_b64": base64.b64encode(gzip.compress(b"hacked content")).decode("ascii"),
                        "size": 14,
                        "sha256": "wrong_hash_1234567890",
                    }
                }
            }

            res = apply_mesh_update(fake_payload, repo_dir=str(dst_path), backup=True)
            self.assertFalse(res["success"])
            self.assertTrue(res.get("rollback_applied"))
            # Il file originale deve essere intatto
            self.assertEqual(existing_file.read_text(), "original content")

    def test_create_and_apply_graphify_bundle(self):
        """Verifica la sincronizzazione di un Knowledge Graph precompilato."""
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
            src_path = Path(src_dir)
            dst_path = Path(dst_dir)

            graph_dir = src_path / "graphify-out"
            graph_dir.mkdir(parents=True)
            (graph_dir / "graph.json").write_text('{"nodes": [1, 2, 3]}')
            (graph_dir / ".graphify_analysis.json").write_text('{"communities": {"0": [1, 2]}}')

            bundle = create_graphify_bundle_payload(repo_dir=str(src_path))
            self.assertEqual(bundle["type"], "graphify_sync")
            self.assertIn("graph.json", bundle["files"])

            res = apply_mesh_update(bundle, repo_dir=str(dst_path))
            self.assertTrue(res["success"])

            self.assertTrue((dst_path / "graphify-out" / "graph.json").exists())
            self.assertTrue((dst_path / "graphify-out" / ".graphify_analysis.json").exists())

    @patch("requests.post")
    def test_distribute_payload_to_node_encrypted(self, mock_post):
        """Verifica che distribute_payload_to_node invii un envelope cifrato al nodo remoto."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": "applied",
            "node_id": self.receiver["node_id"],
            "applied_files": ["test.py"],
        }
        mock_post.return_value = mock_resp

        payload = {"type": "git_patch", "test": True}
        res = distribute_payload_to_node(
            node_endpoint="http://100.81.234.102:8081",
            node_pubkey_hex=self.receiver["public_key"],
            update_payload=payload,
            sender_identity=self.sender,
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["ack"]["status"], "applied")

        # Verifica che i dati inviati via POST siano cifrati in un envelope
        called_args, called_kwargs = mock_post.call_args
        sent_body = called_kwargs["json"]
        self.assertTrue(sent_body.get("encrypted"))
        self.assertIn("envelope", sent_body)
        self.assertEqual(sent_body["envelope"]["sender_node_id"], self.sender["node_id"])


if __name__ == "__main__":
    unittest.main()
