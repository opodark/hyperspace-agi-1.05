# SPDX-License-Identifier: Apache-2.0
# tests/test_crypto_channel.py
"""Test di unità per il canale crittografico cifrato peer-to-peer (ECDH + AES-256-GCM)."""

import hashlib
import time
import unittest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

import sys
from pathlib import Path
ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.crypto_channel import (
    encrypt_envelope,
    decrypt_envelope,
    pubkey_to_hex,
    pubkey_from_hex,
    InvalidSignatureError,
    DecryptionError,
    ExpiredEnvelopeError,
    InvalidEnvelopeError,
)


def _make_keypair():
    priv = ec.generate_private_key(ec.SECP256K1())
    pub = priv.public_key()
    pub_hex = pubkey_to_hex(pub)
    node_id = hashlib.sha256(bytes.fromhex(pub_hex)).hexdigest()[:40]
    return priv, pub_hex, node_id


class CryptoChannelTests(unittest.TestCase):
    def setUp(self):
        self.node_a_priv, self.node_a_pub, self.node_a_id = _make_keypair()
        self.node_b_priv, self.node_b_pub, self.node_b_id = _make_keypair()

    def test_encrypt_and_decrypt_roundtrip(self):
        """Un payload cifrato da A per B viene decifrato con successo da B."""
        telemetry = {
            "node_id": self.node_a_id,
            "git_commit": "4c56def9",
            "branch": "main",
            "clean": True,
            "models": ["granite3.3:8b", "qwen3.5:4b"],
            "vram_free_gb": 6.8,
        }

        envelope = encrypt_envelope(
            payload=telemetry,
            recipient_pubkey_hex=self.node_b_pub,
            sender_private_key=self.node_a_priv,
            sender_node_id=self.node_a_id,
            sender_pubkey_hex=self.node_a_pub,
        )

        self.assertEqual(envelope["version"], 1)
        self.assertEqual(envelope["protocol"], "ecdh-secp256k1-aes256gcm")
        self.assertEqual(envelope["sender_node_id"], self.node_a_id)
        self.assertNotIn("git_commit", str(envelope))  # Nessun dato in chiaro

        # B decifra
        decrypted = decrypt_envelope(
            envelope=envelope,
            recipient_private_key=self.node_b_priv,
            expected_sender_pubkey=self.node_a_pub,
        )
        self.assertEqual(decrypted, telemetry)

    def test_third_party_cannot_decrypt(self):
        """Un terzo nodo C non può decifrare un payload destinato a B."""
        node_c_priv, node_c_pub, node_c_id = _make_keypair()

        envelope = encrypt_envelope(
            payload={"secret": "salute_nodi_confidenziale"},
            recipient_pubkey_hex=self.node_b_pub,
            sender_private_key=self.node_a_priv,
            sender_node_id=self.node_a_id,
            sender_pubkey_hex=self.node_a_pub,
        )

        with self.assertRaises(DecryptionError):
            decrypt_envelope(
                envelope=envelope,
                recipient_private_key=node_c_priv,
            )

    def test_tampered_ciphertext_fails_integrity(self):
        """La manomissione di un singolo byte del testo cifrato fallisce la verifica di autenticità."""
        envelope = encrypt_envelope(
            payload={"telemetry": "ok"},
            recipient_pubkey_hex=self.node_b_pub,
            sender_private_key=self.node_a_priv,
            sender_node_id=self.node_a_id,
            sender_pubkey_hex=self.node_a_pub,
        )

        # Manomettiamo il testo cifrato base64
        corrupted_ct = list(envelope["ciphertext"])
        corrupted_ct[4] = "Z" if corrupted_ct[4] != "Z" else "A"
        envelope["ciphertext"] = "".join(corrupted_ct)

        # Dovrebbe fallire la firma ECDSA o la decifratura GCM
        with self.assertRaises((InvalidSignatureError, DecryptionError)):
            decrypt_envelope(
                envelope=envelope,
                recipient_private_key=self.node_b_priv,
            )

    def test_forged_sender_signature_rejected(self):
        """Un envelope con firma contraffatta viene rifiutato come non autentico."""
        envelope = encrypt_envelope(
            payload={"spoofed": True},
            recipient_pubkey_hex=self.node_b_pub,
            sender_private_key=self.node_a_priv,
            sender_node_id=self.node_a_id,
            sender_pubkey_hex=self.node_a_pub,
        )

        # Sostituiamo la firma con quella di un altro nodo
        other_priv, other_pub, _ = _make_keypair()
        fake_digest = hashlib.sha256(b"fake").digest()
        fake_sig = other_priv.sign(fake_digest, ec.ECDSA(ec.hashes.SHA256()))
        envelope["signature"] = fake_sig.hex()

        with self.assertRaises(InvalidSignatureError):
            decrypt_envelope(
                envelope=envelope,
                recipient_private_key=self.node_b_priv,
            )

    def test_replay_protection_expires_old_envelopes(self):
        """Un envelope con timestamp vecchio oltre la finestra consentita viene rigettato."""
        envelope = encrypt_envelope(
            payload={"timestamp_test": 123},
            recipient_pubkey_hex=self.node_b_pub,
            sender_private_key=self.node_a_priv,
            sender_node_id=self.node_a_id,
            sender_pubkey_hex=self.node_a_pub,
        )

        # Forziamo timestamp vecchio di 200 secondi (supera max_age_s=120)
        envelope["timestamp"] = int(time.time()) - 200

        with self.assertRaises(ExpiredEnvelopeError):
            decrypt_envelope(
                envelope=envelope,
                recipient_private_key=self.node_b_priv,
                max_age_s=120,
            )


if __name__ == "__main__":
    unittest.main()
