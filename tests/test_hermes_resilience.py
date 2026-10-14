# SPDX-License-Identifier: Apache-2.0
"""Test suite per il sistema di resilienza e decentralizzazione cloud Hermes."""

import base64
import gzip
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from shared.hermes_resilience import (
    DEFAULT_RETENTION,
    VAULT_MAGIC,
    VAULT_SCHEMA_VERSION,
    FilesystemStorageBackend,
    GitHubStorageBackend,
    HermesCryptoError,
    HermesMultiCloudVault,
    HermesSnapshotBundle,
    HermesVaultCipher,
    IPFSStorageBackend,
    S3StorageBackend,
    WebDAVStorageBackend,
    _sigv4_sign_headers,
)


class TestHermesVaultCipher(unittest.TestCase):
    """Verifica della cifratura e dell'envelope Zero-Knowledge AES-256-GCM."""

    def setUp(self):
        self.passphrase = "chiave-di-prova-sicura-12345"
        self.cipher = HermesVaultCipher(passphrase=self.passphrase)

    def test_configured_status(self):
        self.assertTrue(self.cipher.is_configured())
        empty_cipher = HermesVaultCipher(passphrase="")
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(empty_cipher.is_configured())

    def test_encrypt_and_decrypt_roundtrip(self):
        raw_payload = b"Payload di memoria Hermes top secret e confidenziale"
        metadata = {"entries_count": 42, "tag": "test"}

        vault_bytes = self.cipher.encrypt_vault(raw_payload, metadata=metadata)
        self.assertTrue(vault_bytes.startswith(VAULT_MAGIC))

        # Legge l'header senza decifrare
        header = HermesVaultCipher.read_header(vault_bytes)
        self.assertEqual(header["schema"], VAULT_SCHEMA_VERSION)
        self.assertEqual(header["algorithm"], "AES-256-GCM")
        self.assertEqual(header["metadata"]["entries_count"], 42)

        # Decifra il payload
        dec_header, dec_payload = self.cipher.decrypt_vault(vault_bytes)
        self.assertEqual(dec_payload, raw_payload)
        self.assertEqual(dec_header["snapshot_id"], header["snapshot_id"])

    def test_tamper_detection(self):
        raw_payload = b"Dati autenticati"
        vault_bytes = bytearray(self.cipher.encrypt_vault(raw_payload))

        # Manomissione dell'ultimo byte del ciphertext
        vault_bytes[-1] ^= 0xFF

        with self.assertRaises(HermesCryptoError):
            self.cipher.decrypt_vault(bytes(vault_bytes))

    def test_wrong_passphrase(self):
        raw_payload = b"Dati autenticati"
        vault_bytes = self.cipher.encrypt_vault(raw_payload)

        wrong_cipher = HermesVaultCipher(passphrase="passphrase-sbagliata")
        with self.assertRaises(HermesCryptoError):
            wrong_cipher.decrypt_vault(vault_bytes)


class TestHermesSnapshotBundle(unittest.TestCase):
    """Verifica della creazione ed estrazione dell'archivio tar.gz dei componenti Hermes."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)

        # Prepara finti file Hermes
        self.hermes_dir = Path(self.temp_dir) / "hermes"
        self.hermes_dir.mkdir()
        (self.hermes_dir / "MEMORY.md").write_text("# Memoria Curata\nFatti utente", encoding="utf-8")
        (self.hermes_dir / "USER.md").write_text("Nome: Utente", encoding="utf-8")

        skills_dir = self.hermes_dir / "skills"
        skills_dir.mkdir()
        (skills_dir / "analisi.py").write_text("def run(): pass", encoding="utf-8")

        # Prepara specchio memoria HyperSpace
        self.mirror_file = Path(self.temp_dir) / "memory.json.gz"
        entries = [{"id": "m1", "content": "nota 1", "ts": "2026-10-14T00:00:00Z"}]
        with gzip.open(self.mirror_file, "wt", encoding="utf-8") as f:
            json.dump(entries, f)

    def test_bundle_creation_and_extraction(self):
        tar_gz_bytes, manifest = HermesSnapshotBundle.create_bundle(
            hermes_dir=self.hermes_dir,
            memory_mirror_file=self.mirror_file,
            hermes_client_entries=[{"id": "m2", "content": "nota bridge"}],
        )

        self.assertGreater(len(tar_gz_bytes), 0)
        self.assertIn("hermes/MEMORY.md", manifest["files"])
        self.assertIn("hermes/USER.md", manifest["files"])
        self.assertIn("hermes/skills/analisi.py", manifest["files"])
        self.assertIn("hyperspace/memory.json.gz", manifest["files"])
        self.assertIn("hermes/bridge_entries.json", manifest["files"])

        # Estrazione
        extract_dir = Path(self.temp_dir) / "extracted"
        result = HermesSnapshotBundle.extract_bundle(tar_gz_bytes, extract_dir)

        self.assertTrue((extract_dir / "hermes/MEMORY.md").exists())
        self.assertTrue((extract_dir / "hermes/USER.md").exists())
        self.assertTrue((extract_dir / "hermes/skills/analisi.py").exists())
        self.assertTrue((extract_dir / "hyperspace/memory.json.gz").exists())
        self.assertTrue((extract_dir / "manifest.json").exists())


class TestStorageBackends(unittest.TestCase):
    """Verifica dei singoli adattatori di storage cloud e decentralizzati."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)

    def test_filesystem_backend(self):
        backend = FilesystemStorageBackend(self.temp_dir, name="local_test")
        data = b"Contenuto vault di test"
        fname = "snap-01.vault"

        # Upload
        up = backend.upload(fname, data)
        self.assertEqual(up["status"], "ok")
        self.assertTrue((Path(self.temp_dir) / fname).exists())

        # List
        snaps = backend.list_snapshots()
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0]["filename"], fname)

        # Download
        down = backend.download(fname)
        self.assertEqual(down, data)

        # Health
        health = backend.health_check()
        self.assertTrue(health["healthy"])

        # Delete
        self.assertTrue(backend.delete(fname))
        self.assertEqual(len(backend.list_snapshots()), 0)

    def test_sigv4_signing(self):
        headers = _sigv4_sign_headers(
            method="PUT",
            url="https://r2.example.com/mio-bucket/snap.vault",
            payload_bytes=b"dummy",
            access_key="CHIAVE_ACCESSO",
            secret_key="SEGRETO_PROVA",
            region="auto",
        )
        self.assertIn("Authorization", headers)
        self.assertTrue(headers["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=CHIAVE_ACCESSO/"))
        self.assertIn("x-amz-date", headers)
        self.assertIn("x-amz-content-sha256", headers)

    @patch("shared.hermes_resilience.requests.put")
    @patch("shared.hermes_resilience.requests.get")
    @patch("shared.hermes_resilience.requests.delete")
    def test_s3_backend_mock(self, mock_del, mock_get, mock_put):
        backend = S3StorageBackend(
            endpoint_url="https://test.r2.cloudflarestorage.com",
            bucket="test-vault",
            access_key="AKIA123",
            secret_key="SECRET123",
        )

        mock_put.return_value.ok = True
        mock_put.return_value.status_code = 200
        up = backend.upload("snap.vault", b"dati")
        self.assertEqual(up["status"], "ok")

        mock_get.return_value.ok = True
        mock_get.return_value.content = b"dati"
        down = backend.download("snap.vault")
        self.assertEqual(down, b"dati")

        mock_del.return_value.status_code = 204
        self.assertTrue(backend.delete("snap.vault"))

    @patch("shared.hermes_resilience.requests.request")
    @patch("shared.hermes_resilience.requests.put")
    @patch("shared.hermes_resilience.requests.get")
    def test_webdav_backend_mock(self, mock_get, mock_put, mock_req):
        backend = WebDAVStorageBackend(
            base_url="https://nextcloud.example.com/remote.php/dav/files/user",
            username="testuser",
            password="testpass",
        )
        mock_put.return_value.ok = True
        mock_put.return_value.status_code = 201
        up = backend.upload("snap.vault", b"dati")
        self.assertEqual(up["status"], "ok")

        mock_get.return_value.ok = True
        mock_get.return_value.content = b"dati"
        down = backend.download("snap.vault")
        self.assertEqual(down, b"dati")

    @patch("shared.hermes_resilience.requests.post")
    @patch("shared.hermes_resilience.requests.get")
    def test_github_backend_mock(self, mock_get, mock_post):
        backend = GitHubStorageBackend(token="ghp_test123")
        mock_post.return_value.ok = True
        mock_post.return_value.json.return_value = {"id": "gist_abc123"}
        up = backend.upload("snap.vault", b"dati")
        self.assertEqual(up["gist_id"], "gist_abc123")

        mock_get.return_value.ok = True
        b64 = base64.b64encode(b"dati").decode("ascii")
        mock_get.return_value.json.return_value = {
            "files": {"snap.vault": {"content": b64}}
        }
        down = backend.download("snap.vault")
        self.assertEqual(down, b"dati")


class TestHermesMultiCloudVault(unittest.TestCase):
    """Verifica dell'orchestratore multi-cloud e del disaster recovery."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)

        self.cipher = HermesVaultCipher(passphrase="super-segreto-multi-cloud")

        # Due backend locali distinti per simulare cloud primario e secondario
        self.dir1 = Path(self.temp_dir) / "primary_cloud"
        self.dir2 = Path(self.temp_dir) / "secondary_cloud"
        self.b1 = FilesystemStorageBackend(self.dir1, name="primary")
        self.b2 = FilesystemStorageBackend(self.dir2, name="secondary")

        self.vault = HermesMultiCloudVault(
            cipher=self.cipher,
            backends=[self.b1, self.b2],
            retention_count=2,
        )

        # Finti file Hermes sorgente
        self.hermes_source = Path(self.temp_dir) / "source_hermes"
        self.hermes_source.mkdir()
        (self.hermes_source / "MEMORY.md").write_text("Conoscenza iniziale", encoding="utf-8")

    def test_snapshot_fan_out_and_redundancy(self):
        res = self.vault.create_and_push_snapshot(
            hermes_dir=self.hermes_source,
            tag="collaudo_resilienza",
        )

        self.assertTrue(res["ok"])
        self.assertEqual(len(res["targets_succeeded"]), 2)
        self.assertIn("primary", res["targets_succeeded"])
        self.assertIn("secondary", res["targets_succeeded"])

        # Verifica che il file esista su entrambi i backend
        fname = res["filename"]
        self.assertTrue((self.dir1 / fname).exists())
        self.assertTrue((self.dir2 / fname).exists())

    def test_fallback_download_when_primary_fails(self):
        res = self.vault.create_and_push_snapshot(hermes_dir=self.hermes_source)
        fname = res["filename"]

        # Simula il guasto o cancellazione del provider primario
        (self.dir1 / fname).unlink()

        # Scarica specificando 'primary' come preferito: deve fare fallback su 'secondary'
        header, payload = self.vault.pull_and_decrypt_snapshot(fname, preferred_backend="primary")
        self.assertEqual(header["source_backend"], "secondary")
        self.assertGreater(len(payload), 0)

    def test_restore_to_directory(self):
        res = self.vault.create_and_push_snapshot(hermes_dir=self.hermes_source)

        restore_target = Path(self.temp_dir) / "restored_hermes"
        rest_res = self.vault.restore_to_directory(restore_target, res["filename"])

        self.assertTrue(rest_res["ok"])
        self.assertTrue((restore_target / "hermes/MEMORY.md").exists())
        self.assertEqual(
            (restore_target / "hermes/MEMORY.md").read_text(encoding="utf-8"),
            "Conoscenza iniziale",
        )

    def test_pruning_retention(self):
        # Crea 3 snapshot con retention=2
        s1 = self.vault.create_and_push_snapshot(hermes_dir=self.hermes_source)
        s2 = self.vault.create_and_push_snapshot(hermes_dir=self.hermes_source)
        s3 = self.vault.create_and_push_snapshot(hermes_dir=self.hermes_source)

        all_snaps = self.vault.list_all_snapshots()
        self.assertEqual(len(all_snaps), 2)
        # Il primo snapshot s1 deve essere stato potato
        filenames = [s["filename"] for s in all_snaps]
        self.assertNotIn(s1["filename"], filenames)
        self.assertIn(s3["filename"], filenames)

    def test_verify_all_remotes(self):
        self.vault.create_and_push_snapshot(hermes_dir=self.hermes_source)
        verification = self.vault.verify_all_remotes()

        self.assertEqual(verification["status"], "healthy")
        self.assertTrue(verification["backends"]["primary"]["healthy"])
        self.assertTrue(verification["backends"]["secondary"]["healthy"])
        self.assertTrue(verification["verification"]["tested"])
        self.assertTrue(verification["verification"]["ok"])


class TestControlPlaneResilienceRoutes(unittest.TestCase):
    """Verifica delle rotte Flask del Control Plane per la gestione della resilienza."""

    @classmethod
    def setUpClass(cls):
        import sys
        REPO_ROOT = Path(__file__).resolve().parents[1]
        cp_path = str(REPO_ROOT / "control-plane")
        if cp_path not in sys.path:
            sys.path.insert(0, cp_path)

        from flask import Flask
        from cp.memoria import _bp

        cls.app = Flask("test_cp")
        cls.app.config["TESTING"] = True
        cls.app.register_blueprint(_bp)
        cls.client = cls.app.test_client()

    def test_get_status_route(self):
        resp = self.client.get("/memory/resilience/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("backends", data)
        self.assertIn("crypto", data)

    def test_get_snapshots_route(self):
        resp = self.client.get("/memory/resilience/snapshots")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("snapshots", data)

    def test_snapshot_route_without_passphrase(self):
        with patch.dict(os.environ, {"HERMES_VAULT_PASSPHRASE": "", "HERMES_ENCRYPTION_KEY": ""}, clear=True):
            resp = self.client.post("/memory/resilience/snapshot", json={"tag": "test"})
            self.assertEqual(resp.status_code, 400)
            self.assertIn("Passphrase", resp.get_json().get("error", ""))

    def test_verify_route(self):
        resp = self.client.post("/memory/resilience/verify")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("backends", data)


if __name__ == "__main__":
    unittest.main()

