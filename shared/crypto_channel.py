# SPDX-License-Identifier: Apache-2.0
# shared/crypto_channel.py
# HyperSpace AGI — Encrypted Peer-to-Peer Telemetry Channel
#
# Canale crittografato end-to-end per lo scambio di telemetria, stato del codebase
# e diagnostica tra i nodi della mesh e il control-plane.
#
# Caratteristiche crittografiche:
#   - Scambio chiavi: ECDH su curva secp256k1 (stessa curva delle identità di HyperSpace)
#   - Perfect Forward Secrecy (PFS): ogni messaggio cifra usando una coppia effimera
#   - Cifratura simmetrica: AES-256-GCM (autenticata con Additional Authenticated Data)
#   - Key Derivation: HKDF-SHA256 su shared secret ECDH
#   - Autenticazione & Integrità: firma ECDSA (SHA-256) della chiave pubblica del mittente
#   - Protezione da replay attack: timestamp di finestra (default 120s) e nonce crittografico

import base64
import hashlib
import json
import os
import time
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class CryptoChannelError(Exception):
    """Errore base del canale crittografico."""
    pass


class InvalidSignatureError(CryptoChannelError):
    """Firma ECDSA dell'envelope non valida o mittente non autentico."""
    pass


class DecryptionError(CryptoChannelError):
    """Decifratura fallita: tag GCM errato, chiave errata o payload corrotto."""
    pass


class ExpiredEnvelopeError(CryptoChannelError):
    """Timestamp dell'envelope fuori dalla finestra di tolleranza (replay attack)."""
    pass


class InvalidEnvelopeError(CryptoChannelError):
    """Formato dell'envelope non valido o protocollo incompatibile."""
    pass


PROTOCOL_VERSION = 1
PROTOCOL_ID = "ecdh-secp256k1-aes256gcm"
DEFAULT_KDF_INFO = b"hyperspace-doctor-channel-v1"


def _pubkey_bytes(pub_key: ec.EllipticCurvePublicKey) -> bytes:
    """Restituisce la rappresentazione non compressa in byte della chiave pubblica secp256k1."""
    return pub_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )


def pubkey_from_hex(hex_str: str) -> ec.EllipticCurvePublicKey:
    """Decodifica una chiave pubblica secp256k1 da stringa esadecimale."""
    raw = bytes.fromhex(hex_str)
    return ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), raw)


def pubkey_to_hex(pub_key: ec.EllipticCurvePublicKey) -> str:
    """Codifica una chiave pubblica secp256k1 in stringa esadecimale uncompressed point."""
    return _pubkey_bytes(pub_key).hex()


def derive_symmetric_key(
    ecdh_secret: bytes,
    salt: Optional[bytes] = None,
    info: bytes = DEFAULT_KDF_INFO,
    length: int = 32,
) -> bytes:
    """Deriva una chiave simmetrica sicura a 256 bit dallo shared secret ECDH usando HKDF-SHA256."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        info=info,
    )
    return hkdf.derive(ecdh_secret)


def encrypt_envelope(
    payload: Dict[str, Any],
    recipient_pubkey_hex: str,
    sender_private_key,
    sender_node_id: str,
    sender_pubkey_hex: str,
    info: bytes = DEFAULT_KDF_INFO,
) -> Dict[str, Any]:
    """Cifra un dizionario in un envelope sigillato e firmato per il destinatario.

    1. Genera una chiave effimera secp256k1 per garantire Perfect Forward Secrecy.
    2. Calcola lo shared secret ECDH con la chiave pubblica del destinatario.
    3. Deriva una chiave AES-256 usando HKDF-SHA256.
    4. Genera un nonce casuale a 12 byte (96-bit per AES-GCM).
    5. Cifra il payload JSON in AES-256-GCM legando mittente e timestamp nei dati autenticati (AAD).
    6. Firma ECDSA l'impronta (effimera + nonce + AAD + cifrato) con la chiave privata del mittente.
    """
    recipient_pub = pubkey_from_hex(recipient_pubkey_hex)

    # 1. Coppia effimera per Forward Secrecy
    ephem_priv = ec.generate_private_key(ec.SECP256K1())
    ephem_pub_bytes = _pubkey_bytes(ephem_priv.public_key())

    # 2. Scambio Diffie-Hellman
    shared_secret = ephem_priv.exchange(ec.ECDH(), recipient_pub)

    # 3. KDF
    sym_key = derive_symmetric_key(shared_secret, salt=None, info=info)

    # 4. Nonce & AAD
    nonce = os.urandom(12)
    ts = int(time.time())
    aad_str = f"{sender_node_id}:{ts}"
    aad_bytes = aad_str.encode("utf-8")

    # 5. Cifratura AES-256-GCM
    plaintext = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    aesgcm = AESGCM(sym_key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, aad_bytes)

    # 6. Firma dell'envelope con la chiave d'identità persistente del nodo
    digest = hashlib.sha256(ephem_pub_bytes + nonce + aad_bytes + ciphertext).digest()
    signature = sender_private_key.sign(digest, ec.ECDSA(hashes.SHA256()))

    return {
        "version": PROTOCOL_VERSION,
        "protocol": PROTOCOL_ID,
        "sender_node_id": sender_node_id,
        "sender_pubkey": sender_pubkey_hex,
        "ephem_pubkey": ephem_pub_bytes.hex(),
        "nonce": nonce.hex(),
        "aad": aad_str,
        "timestamp": ts,
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "signature": signature.hex(),
    }


def decrypt_envelope(
    envelope: Dict[str, Any],
    recipient_private_key,
    expected_sender_pubkey: Optional[str] = None,
    max_age_s: int = 120,
    info: bytes = DEFAULT_KDF_INFO,
) -> Dict[str, Any]:
    """Decifra e verifica l'integrità e autenticità di un envelope sigillato.

    Controlla:
      - Protocollo e versione compatibili
      - Finestra temporale di ricezione per prevenire replay attack
      - Corrispondenza del node_id con la pubkey dichiarata
      - Firma ECDSA del mittente
      - Tag di autenticazione AES-GCM
    Restituisce il payload dict originario.
    """
    if not isinstance(envelope, dict):
        raise InvalidEnvelopeError("L'envelope deve essere un dizionario JSON.")

    if envelope.get("version") != PROTOCOL_VERSION or envelope.get("protocol") != PROTOCOL_ID:
        raise InvalidEnvelopeError(f"Protocollo non supportato: {envelope.get('protocol')} v{envelope.get('version')}")

    required_keys = ["sender_node_id", "sender_pubkey", "ephem_pubkey", "nonce", "aad", "timestamp", "ciphertext", "signature"]
    for k in required_keys:
        if k not in envelope:
            raise InvalidEnvelopeError(f"Campo mancante nell'envelope crittografico: {k}")

    # Verifica finestra temporale (anti-replay)
    ts = int(envelope["timestamp"])
    now = int(time.time())
    if max_age_s > 0 and abs(now - ts) > max_age_s:
        raise ExpiredEnvelopeError(f"Envelope scaduto: delta={abs(now - ts)}s > soglia={max_age_s}s")

    sender_pub_hex = envelope["sender_pubkey"]
    if expected_sender_pubkey and sender_pub_hex != expected_sender_pubkey:
        raise InvalidSignatureError(f"Pubkey del mittente non attesa: ricevuta {sender_pub_hex[:16]}... attesa {expected_sender_pubkey[:16]}...")

    # Verifica che sender_node_id derivi da sender_pubkey
    sender_pub_bytes = bytes.fromhex(sender_pub_hex)
    derived_node_id = hashlib.sha256(sender_pub_bytes).hexdigest()[:40]
    if derived_node_id != envelope["sender_node_id"]:
        raise InvalidEnvelopeError(f"Node ID {envelope['sender_node_id']} non corrisponde alla pubkey fornita.")

    ephem_pub_bytes = bytes.fromhex(envelope["ephem_pubkey"])
    nonce = bytes.fromhex(envelope["nonce"])
    aad_bytes = envelope["aad"].encode("utf-8")
    ciphertext = base64.b64decode(envelope["ciphertext"])
    sig_bytes = bytes.fromhex(envelope["signature"])

    # 1. Verifica firma mittente
    try:
        sender_pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), sender_pub_bytes)
        digest = hashlib.sha256(ephem_pub_bytes + nonce + aad_bytes + ciphertext).digest()
        sender_pub.verify(sig_bytes, digest, ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, Exception) as e:
        raise InvalidSignatureError(f"Verifica della firma fallita: {e}")

    # 2. Scambio ECDH ricevente + derivazione chiave
    try:
        ephem_pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), ephem_pub_bytes)
        shared_secret = recipient_private_key.exchange(ec.ECDH(), ephem_pub)
        sym_key = derive_symmetric_key(shared_secret, salt=None, info=info)
    except Exception as e:
        raise DecryptionError(f"Fallimento scambio ECDH: {e}")

    # 3. Decifratura AES-256-GCM
    try:
        aesgcm = AESGCM(sym_key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, aad_bytes)
        return json.loads(plaintext.decode("utf-8"))
    except Exception as e:
        raise DecryptionError(f"Decifratura fallita (payload corrotto o tag non valido): {e}")
