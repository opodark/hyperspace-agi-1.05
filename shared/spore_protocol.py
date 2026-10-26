#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
HyperSpace Bio-Mimetic Spore Protocol (shared/spore_protocol.py)

Sistema crittografico di continuità operativa, resilienza distribuita e
disaster recovery ("Endospore Crittografiche") per HyperSpace AGI.

Caratteristiche principali:
1. Shamir's Secret Sharing su campo finito GF(2^8) (polinomio di Rijndael 0x11b):
   - Suddivide la Master Key a 256 bit in N frammenti con soglia K (default 2-su-3:
     es. Fondatore Alberto, Socio Guido "Cips", Vault Cartaceo Offline).
   - Permette la ricostruzione completa anche se il fondatore perde l'accesso
     alla propria identità digitale o alle proprie password principali.
2. Cifratura Autenticata AES-256-GCM Dual-Layer:
   - Cifra l'intero pacchetto Spora (`.hspore`: Git bundle + delta working tree +
     memoria Hermes + database SQLite + grafo causale) con AES-256-GCM e HKDF-SHA256.
   - Isola opzionalmente i segreti (`.env`) in un envelope interno cifrato con
     sotto-chiave dedicata, senza mai esporre credenziali in chiaro nei metadati.
3. Dispersione Multi-Substrato Zero-Knowledge:
   - Supporta `rclone` (MEGA, Dropbox, OneDrive, S3, WebDAV), cartelle desktop
     sincronizzate (`~/MEGA`, `~/Dropbox`, `~/OneDrive`, volumi USB) e nodi
     autorizzati della Mesh (Mac M5, HP OMEN 16, ASUS V16).
   - I provider cloud ricevono esclusivamente ciphertext autenticato opaco.
4. Sentinella di Continuità (Dead-Man's Switch) & Germinazione Deterministica:
   - Monitora i battiti cardiaci dei nodi primari e prepara il failover sui nodi
     standby autorizzati, con verifica crittografica SHA-256 pre-germinazione.
"""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field
import datetime
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tarfile
import tempfile
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


SPORE_MAGIC = b"HSPORE01"
SPORE_FORMAT_VERSION = 1
SHARE_PREFIX = "HSP-SPORE-V1"


# ============================================================================
# 1. Aritmetica su Campo Finito GF(2^8) e Shamir's Secret Sharing (M-of-N)
# ============================================================================

def _gf256_mul(a: int, b: int) -> int:
    """Moltiplicazione in GF(2^8) con polinomio irriducibile x^8 + x^4 + x^3 + x + 1 (0x11b)."""
    p = 0
    a &= 0xFF
    b &= 0xFF
    for _ in range(8):
        if b & 1:
            p ^= a
        hi_bit_set = a & 0x80
        a = (a << 1) & 0xFF
        if hi_bit_set:
            a ^= 0x1B
        b >>= 1
    return p & 0xFF


def _gf256_pow(a: int, exp: int) -> int:
    result = 1
    base = a & 0xFF
    while exp > 0:
        if exp & 1:
            result = _gf256_mul(result, base)
        base = _gf256_mul(base, base)
        exp >>= 1
    return result


def _gf256_inv(a: int) -> int:
    """Inverso moltiplicativo in GF(2^8) tramite il piccolo teorema di Fermat: a^(254)."""
    if a == 0:
        raise ZeroDivisionError("Impossibile invertire 0 in GF(2^8)")
    return _gf256_pow(a, 254)


def _gf256_div(a: int, b: int) -> int:
    if b == 0:
        raise ZeroDivisionError("Divisione per zero in GF(2^8)")
    if a == 0:
        return 0
    return _gf256_mul(a, _gf256_inv(b))


@dataclass(frozen=True)
class ShamirShare:
    """Rappresenta un singolo frammento del quorum di Shamir."""
    index: int
    threshold: int
    total_shares: int
    custodian: str
    payload_hex: str
    checksum: str

    def encode(self) -> str:
        """Serializza il frammento nel formato portabile HSP-SPORE-V1."""
        return (
            f"{SHARE_PREFIX}:{self.index}:{self.threshold}:{self.total_shares}:"
            f"{self.custodian}:{self.payload_hex}:{self.checksum}"
        )

    @classmethod
    def decode(cls, token: str) -> "ShamirShare":
        """Deserializza e valida l'integrità (CRC SHA-256) di un frammento."""
        parts = token.strip().split(":")
        if len(parts) != 7 or parts[0] != SHARE_PREFIX:
            raise ValueError(f"Formato frammento Shamir non valido: atteso prefisso {SHARE_PREFIX}")
        index = int(parts[1])
        threshold = int(parts[2])
        total_shares = int(parts[3])
        custodian = parts[4].strip()
        payload_hex = parts[5].strip().lower()
        checksum = parts[6].strip().lower()

        if not (1 <= index <= 255):
            raise ValueError(f"Indice frammento fuori range GF(2^8): {index}")
        if not (2 <= threshold <= total_shares <= 255):
            raise ValueError(f"Parametri quorum non validi: threshold={threshold}, total={total_shares}")

        raw_bytes = bytes.fromhex(payload_hex)
        expected_crc = cls._compute_checksum(index, threshold, total_shares, custodian, raw_bytes)
        if not hmac.compare_digest(checksum, expected_crc):
            raise ValueError(f"Checksum frammento #{index} ({custodian}) corrotto o manomesso")

        return cls(
            index=index,
            threshold=threshold,
            total_shares=total_shares,
            custodian=custodian,
            payload_hex=payload_hex,
            checksum=checksum,
        )

    @staticmethod
    def _compute_checksum(
        index: int,
        threshold: int,
        total_shares: int,
        custodian: str,
        payload: bytes,
    ) -> str:
        h = hashlib.sha256()
        h.update(f"{SHARE_PREFIX}:{index}:{threshold}:{total_shares}:{custodian}:".encode("utf-8"))
        h.update(payload)
        return h.hexdigest()[:12]


class ShamirQuorumVault:
    """
    Gestore del Quorum Crittografico di Shamir su GF(2^8).
    Permette di suddividere una chiave master (es. 32 byte / 256 bit) in N frammenti
    tali che qualsiasi sottoinsieme di K frammenti ricostruisca esattamente il segreto,
    mentre K-1 frammenti non rivelino alcuna informazione.
    """

    DEFAULT_CUSTODIANS = (
        "alberto-founder",
        "guido-cips-partner",
        "offline-paper-vault",
    )

    @classmethod
    def split_secret(
        cls,
        secret: bytes,
        threshold: int = 2,
        total_shares: int = 3,
        custodians: Optional[Sequence[str]] = None,
    ) -> List[ShamirShare]:
        if not secret:
            raise ValueError("Il segreto da suddividere non può essere vuoto")
        if not (2 <= threshold <= total_shares <= 255):
            raise ValueError("Richiesto 2 <= threshold <= total_shares <= 255")

        if custodians is None:
            if total_shares == 3:
                custodian_list = list(cls.DEFAULT_CUSTODIANS)
            else:
                custodian_list = [f"custodian-{i}" for i in range(1, total_shares + 1)]
        else:
            if len(custodians) != total_shares:
                raise ValueError(f"Il numero di custodi ({len(custodians)}) deve coincidere con total_shares ({total_shares})")
            custodian_list = [c.replace(":", "-") for c in custodians]

        share_buffers: List[bytearray] = [bytearray() for _ in range(total_shares)]

        for byte_val in secret:
            # Polinomio casuale P(x) = byte_val + a_1*x + ... + a_{K-1}*x^{K-1}
            coeffs = [byte_val] + [secrets.randbelow(256) for _ in range(threshold - 1)]
            # Garantiamo che il coefficiente di grado massimo non sia zero
            if coeffs[-1] == 0:
                coeffs[-1] = secrets.randbelow(255) + 1

            for idx in range(1, total_shares + 1):
                # Valutazione di Horner in GF(2^8) per x = idx
                y = 0
                for c in reversed(coeffs):
                    y = _gf256_mul(y, idx) ^ c
                share_buffers[idx - 1].append(y)

        shares: List[ShamirShare] = []
        for idx in range(1, total_shares + 1):
            raw_payload = bytes(share_buffers[idx - 1])
            custodian = custodian_list[idx - 1]
            crc = ShamirShare._compute_checksum(idx, threshold, total_shares, custodian, raw_payload)
            shares.append(
                ShamirShare(
                    index=idx,
                    threshold=threshold,
                    total_shares=total_shares,
                    custodian=custodian,
                    payload_hex=raw_payload.hex(),
                    checksum=crc,
                )
            )

        # Auto-verifica matematica sul primo sottoinsieme di dimensione K
        reconstructed = cls.recover_secret(shares[:threshold])
        if not hmac.compare_digest(reconstructed, secret):
            raise RuntimeError("Auto-verifica di Shamir fallita durante lo split")

        return shares

    @classmethod
    def recover_secret(cls, shares: Sequence[ShamirShare | str]) -> bytes:
        parsed: List[ShamirShare] = [
            ShamirShare.decode(s) if isinstance(s, str) else s for s in shares
        ]
        if not parsed:
            raise ValueError("Nessun frammento fornito per il recupero")

        threshold = parsed[0].threshold
        if len(parsed) < threshold:
            raise ValueError(
                f"Quorum insufficiente: forniti {len(parsed)} frammenti, necessari almeno {threshold}"
            )

        # Deduplica per indice e prendi esattamente K frammenti distinti
        unique_by_idx: Dict[int, ShamirShare] = {}
        for s in parsed:
            if s.threshold != threshold:
                raise ValueError("I frammenti appartengono a quorum con soglie differenti")
            unique_by_idx[s.index] = s

        if len(unique_by_idx) < threshold:
            raise ValueError(
                f"Frammenti distinti insufficienti: {len(unique_by_idx)} < {threshold}"
            )

        active_shares = list(unique_by_idx.values())[:threshold]
        secret_len = len(bytes.fromhex(active_shares[0].payload_hex))
        xs = [s.index for s in active_shares]
        ys_matrix = [bytes.fromhex(s.payload_hex) for s in active_shares]

        for y_vec in ys_matrix:
            if len(y_vec) != secret_len:
                raise ValueError("I frammenti hanno lunghezze del payload discordanti")

        # Interpolazione di Lagrange in x = 0 su GF(2^8)
        # Pre-calcolo dei pesi di Lagrange L_j(0) = \prod_{m != j} x_m / (x_m ^ x_j)
        lagrange_weights: List[int] = []
        for j in range(threshold):
            xj = xs[j]
            num = 1
            den = 1
            for m in range(threshold):
                if m == j:
                    continue
                xm = xs[m]
                num = _gf256_mul(num, xm)
                den = _gf256_mul(den, xm ^ xj)
            lagrange_weights.append(_gf256_div(num, den))

        out = bytearray(secret_len)
        for byte_pos in range(secret_len):
            val = 0
            for j in range(threshold):
                term = _gf256_mul(ys_matrix[j][byte_pos], lagrange_weights[j])
                val ^= term
            out[byte_pos] = val

        return bytes(out)


# ============================================================================
# 2. Cifratura Autenticata AES-256-GCM Dual-Layer per le Capsule Spora
# ============================================================================

@dataclass
class SporeManifest:
    """Metadati pubblici (autenticati tramite GCM AAD) di una Spora HyperSpace."""
    spore_id: str
    created_at: str
    source_node: str
    format_version: int
    quorum_threshold: int
    quorum_total_shares: int
    custodians: List[str]
    git_head_commit: str
    git_branch: str
    included_components: List[str]
    has_encrypted_secrets_vault: bool
    plaintext_archive_sha256: str
    plaintext_archive_bytes: int
    salt_hex: str
    nonce_hex: str

    def to_aad_bytes(self) -> bytes:
        """Serializza il manifest in JSON canonico da usare come AAD per AES-256-GCM."""
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode("utf-8")


class SporeCipher:
    """
    Motore di cifratura autenticata per i pacchetti `.hspore`.
    Utilizza HKDF-SHA256 per derivare chiavi distinte dalla Master Key di 256 bit:
    - Chiave capsula principale (`info=b"hyperspace-spore-capsule-v1"`)
    - Chiave vault segreti interno (`info=b"hyperspace-spore-secrets-v1"`)
    Supporta anche derivazione da passphrase di emergenza via PBKDF2-HMAC-SHA256 (600.000 iterazioni).
    """

    @staticmethod
    def generate_master_key() -> bytes:
        return secrets.token_bytes(32)

    @staticmethod
    def derive_master_key_from_passphrase(passphrase: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600_000,
        )
        return kdf.derive(passphrase.encode("utf-8"))

    @staticmethod
    def _derive_subkey(master_key: bytes, salt: bytes, context_info: bytes) -> bytes:
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=context_info,
        )
        return hkdf.derive(master_key)

    @classmethod
    def encrypt_secrets_envelope(cls, secrets_dict: Dict[str, str], master_key: bytes, salt: bytes) -> bytes:
        """Cifra un dizionario di variabili sensibili con una sotto-chiave HKDF isolata."""
        subkey = cls._derive_subkey(master_key, salt, b"hyperspace-spore-secrets-v1")
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(subkey)
        payload = json.dumps(secrets_dict, sort_keys=True).encode("utf-8")
        ct = aesgcm.encrypt(nonce, payload, b"HSPORE-SECRETS-V1")
        return nonce + ct

    @classmethod
    def decrypt_secrets_envelope(cls, blob: bytes, master_key: bytes, salt: bytes) -> Dict[str, str]:
        if len(blob) < 28:
            raise ValueError("Envelope segreti troppo corto o corrotto")
        subkey = cls._derive_subkey(master_key, salt, b"hyperspace-spore-secrets-v1")
        nonce = blob[:12]
        ct = blob[12:]
        aesgcm = AESGCM(subkey)
        pt = aesgcm.decrypt(nonce, ct, b"HSPORE-SECRETS-V1")
        return json.loads(pt.decode("utf-8"))

    @classmethod
    def seal_spore_file(
        cls,
        plaintext_tar_gz: bytes,
        manifest: SporeManifest,
        master_key: bytes,
        output_path: Path,
    ) -> Dict[str, Any]:
        """
        Sigilla il pacchetto `.hspore` su disco:
        Formato binario:
        - 8 byte: SPORE_MAGIC (`HSPORE01`)
        - 4 byte (big-endian uint32): lunghezza del JSON Manifest
        - N byte: Manifest JSON UTF-8 (usato anche come AAD in AES-GCM)
        - M byte: Ciphertext AES-256-GCM + Tag 128-bit
        """
        salt = bytes.fromhex(manifest.salt_hex)
        nonce = bytes.fromhex(manifest.nonce_hex)
        capsule_key = cls._derive_subkey(master_key, salt, b"hyperspace-spore-capsule-v1")
        aad = manifest.to_aad_bytes()

        aesgcm = AESGCM(capsule_key)
        ciphertext = aesgcm.encrypt(nonce, plaintext_tar_gz, aad)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(SPORE_MAGIC)
            f.write(len(aad).to_bytes(4, byteorder="big"))
            f.write(aad)
            f.write(ciphertext)

        file_bytes = output_path.stat().st_size
        file_sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()
        return {
            "spore_path": str(output_path),
            "spore_size_bytes": file_bytes,
            "spore_sha256": file_sha256,
        }

    @classmethod
    def inspect_spore_manifest(cls, spore_path: Path) -> SporeManifest:
        """Legge il manifest di una spora senza bisogno della chiave di decifratura."""
        with open(spore_path, "rb") as f:
            magic = f.read(8)
            if magic != SPORE_MAGIC:
                raise ValueError(f"File {spore_path} non è una Spora HyperSpace valida (magic errato)")
            header_len_bytes = f.read(4)
            if len(header_len_bytes) != 4:
                raise ValueError("Header lunghezza manifest troncato")
            header_len = int.from_bytes(header_len_bytes, byteorder="big")
            aad = f.read(header_len)
            if len(aad) != header_len:
                raise ValueError("Manifest JSON troncato")
        data = json.loads(aad.decode("utf-8"))
        return SporeManifest(**data)

    @classmethod
    def unseal_spore_file(
        cls,
        spore_path: Path,
        master_key: bytes,
    ) -> Tuple[SporeManifest, bytes]:
        """
        Verifica l'autenticità GCM del manifest + payload, decifra l'archivio `.tar.gz`
        e controlla l'hash SHA-256 interno.
        """
        raw = spore_path.read_bytes()
        if len(raw) < 12 or raw[:8] != SPORE_MAGIC:
            raise ValueError("Formato file Spora non valido")
        header_len = int.from_bytes(raw[8:12], byteorder="big")
        aad = raw[12 : 12 + header_len]
        ciphertext = raw[12 + header_len :]

        manifest_dict = json.loads(aad.decode("utf-8"))
        manifest = SporeManifest(**manifest_dict)

        salt = bytes.fromhex(manifest.salt_hex)
        nonce = bytes.fromhex(manifest.nonce_hex)
        capsule_key = cls._derive_subkey(master_key, salt, b"hyperspace-spore-capsule-v1")

        aesgcm = AESGCM(capsule_key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, aad)

        actual_sha = hashlib.sha256(plaintext).hexdigest()
        if not hmac.compare_digest(actual_sha, manifest.plaintext_archive_sha256):
            raise ValueError("Hash SHA-256 dell'archivio decifrato non corrisponde al manifest")

        return manifest, plaintext


# ============================================================================
# 3. Costruttore di Spore (Sporulazione) & Germinazione Autonoma
# ============================================================================

GERMINATION_BOOTSTRAP_TEMPLATE = '''#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
HyperSpace Autonomous Spore Germination Bootstrap (germinate_spore.py)

Script autosufficiente per far germinare (ripristinare e riavviare) un nodo
HyperSpace partendo da un file `.hspore` e da un quorum di frammenti Shamir
(es. 2-su-3 frammenti), anche in assenza dei nodi originari o delle password primarie.

Uso:
    python3 germinate_spore.py --spore <file.hspore> --share "<SHARE_1>" --share "<SHARE_2>" --target-dir ./hyperspace-recovered
"""
import argparse
import pathlib
import sys

# Se eseguito dentro il repository o accanto a shared/spore_protocol.py
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from shared.spore_protocol import SporeBuilder, ShamirQuorumVault

def main() -> int:
    parser = argparse.ArgumentParser(description="Germinazione Spora Crittografica HyperSpace")
    parser.add_argument("--spore", required=True, help="Percorso del file .hspore")
    parser.add_argument("--share", action="append", default=[], help="Frammento Shamir HSP-SPORE-V1 (ripetere almeno K volte)")
    parser.add_argument("--target-dir", required=True, help="Directory di destinazione per la germinazione")
    parser.add_argument("--restore-secrets", action="store_true", help="Ripristina anche il vault segreti (.env.recovered)")
    args = parser.parse_args()

    if len(args.share) < 2:
        print("[ERRORE] Fornire almeno K frammenti Shamir con --share", file=sys.stderr)
        return 1

    master_key = ShamirQuorumVault.recover_secret(args.share)
    result = SporeBuilder.germinate_spore(
        spore_path=pathlib.Path(args.spore),
        master_key=master_key,
        target_dir=pathlib.Path(args.target_dir),
        restore_secrets=args.restore_secrets,
    )
    print(f"[OK] Spora {result['spore_id']} germinata con successo in {result['target_dir']}")
    print(f"     Componenti ripristinati: {', '.join(result['restored_components'])}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''


class SporeBuilder:
    """
    Assembla una Spora completa del repository e della memoria di HyperSpace
    e ne gestisce la germinazione deterministica su un nuovo nodo.
    """

    DEFAULT_MEMORY_PATHS = (
        "AGENTS.md",
        "AGENT-LOG.md",
        "CLAUDE.md",
        "data/control-plane/memory.json.gz",
        "data/control-plane/diario.json",
        "data/persona-anna.json",
        "data/persona-aurora.json",
        "shared/causal_memory_graph.py",
        "shared/hermes_memory.py",
        "docs/spore-continuity.md",
    )

    @classmethod
    def create_spore(
        cls,
        repo_root: Path,
        output_dir: Path,
        source_node: str = "mac-m5-hub",
        quorum_threshold: int = 2,
        quorum_total_shares: int = 3,
        custodians: Optional[Sequence[str]] = None,
        include_git_bundle: bool = True,
        extra_paths: Optional[Sequence[str]] = None,
        secrets_to_vault: Optional[Dict[str, str]] = None,
        master_key: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """
        Crea una nuova Spora Crittografica (`.hspore`) insieme ai frammenti Shamir
        e al manifest pubblico di verifica.
        """
        repo_root = repo_root.resolve()
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        timestamp_slug = now_utc.strftime("%Y%m%d-%H%M%SZ")
        spore_id = f"spore-{timestamp_slug}-{secrets.token_hex(3)}"

        if master_key is None:
            master_key = SporeCipher.generate_master_key()

        shares = ShamirQuorumVault.split_secret(
            secret=master_key,
            threshold=quorum_threshold,
            total_shares=quorum_total_shares,
            custodians=custodians,
        )

        salt = secrets.token_bytes(16)
        nonce = secrets.token_bytes(12)

        git_commit = cls._get_git_head(repo_root)
        git_branch = cls._get_git_branch(repo_root)

        included_components: List[str] = []
        tar_buffer = io.BytesIO()

        with tempfile.TemporaryDirectory(prefix="hspore_stage_") as tmp_stage_str:
            tmp_stage = Path(tmp_stage_str)

            with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
                # 1. Git Bundle della storia completa del repository (se disponibile)
                if include_git_bundle and (repo_root / ".git").exists():
                    bundle_path = tmp_stage / "repo.bundle"
                    if cls._create_git_bundle(repo_root, bundle_path):
                        tar.add(bundle_path, arcname="codebase/repo.bundle")
                        included_components.append("codebase/repo.bundle")

                # 2. Memoria cognitiva, configurazione pubblica e sorgenti chiave
                candidates = list(cls.DEFAULT_MEMORY_PATHS)
                if extra_paths:
                    for p in extra_paths:
                        if p not in candidates:
                            candidates.append(p)

                for rel_path in candidates:
                    abs_p = repo_root / rel_path
                    if abs_p.exists() and abs_p.is_file():
                        tar.add(abs_p, arcname=f"workspace/{rel_path}")
                        included_components.append(f"workspace/{rel_path}")

                # 3. Snapshot SQLite consistenti (se presenti)
                for db_rel in ("data/control-plane/hyperspace.db", "data/causal_memory.db"):
                    db_abs = repo_root / db_rel
                    if db_abs.exists() and db_abs.is_file():
                        db_backup_file = tmp_stage / Path(db_rel).name
                        shutil.copy2(db_abs, db_backup_file)
                        tar.add(db_backup_file, arcname=f"workspace/{db_rel}")
                        included_components.append(f"workspace/{db_rel}")

                # 4. Vault Segreti Interno (cifrato con seconda chiave derivata HKDF)
                has_secrets_vault = False
                if secrets_to_vault:
                    encrypted_env_blob = SporeCipher.encrypt_secrets_envelope(
                        secrets_to_vault, master_key=master_key, salt=salt
                    )
                    vault_file = tmp_stage / "secrets.vault.enc"
                    vault_file.write_bytes(encrypted_env_blob)
                    tar.add(vault_file, arcname="vault/secrets.vault.enc")
                    included_components.append("vault/secrets.vault.enc")
                    has_secrets_vault = True

                # 5. Script di germinazione autonomo incluso dentro la spora
                germ_file = tmp_stage / "germinate_spore.py"
                germ_file.write_text(GERMINATION_BOOTSTRAP_TEMPLATE, encoding="utf-8")
                tar.add(germ_file, arcname="bootstrap/germinate_spore.py")
                included_components.append("bootstrap/germinate_spore.py")

        plaintext_bytes = tar_buffer.getvalue()
        plaintext_sha256 = hashlib.sha256(plaintext_bytes).hexdigest()

        manifest = SporeManifest(
            spore_id=spore_id,
            created_at=now_utc.isoformat(),
            source_node=source_node,
            format_version=SPORE_FORMAT_VERSION,
            quorum_threshold=quorum_threshold,
            quorum_total_shares=quorum_total_shares,
            custodians=[s.custodian for s in shares],
            git_head_commit=git_commit,
            git_branch=git_branch,
            included_components=included_components,
            has_encrypted_secrets_vault=has_secrets_vault,
            plaintext_archive_sha256=plaintext_sha256,
            plaintext_archive_bytes=len(plaintext_bytes),
            salt_hex=salt.hex(),
            nonce_hex=nonce.hex(),
        )

        spore_file_path = output_dir / f"{spore_id}.hspore"
        seal_info = SporeCipher.seal_spore_file(
            plaintext_tar_gz=plaintext_bytes,
            manifest=manifest,
            master_key=master_key,
            output_path=spore_file_path,
        )

        # Salviamo il manifest pubblico a fianco del file .hspore (nessun segreto!)
        manifest_path = output_dir / f"{spore_id}.manifest.json"
        manifest_payload = asdict(manifest)
        manifest_payload["spore_sha256"] = seal_info["spore_sha256"]
        manifest_payload["spore_size_bytes"] = seal_info["spore_size_bytes"]
        manifest_path.write_text(
            json.dumps(manifest_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return {
            "spore_id": spore_id,
            "spore_path": str(spore_file_path),
            "manifest_path": str(manifest_path),
            "spore_sha256": seal_info["spore_sha256"],
            "spore_size_bytes": seal_info["spore_size_bytes"],
            "manifest": asdict(manifest),
            "shares": [s.encode() for s in shares],
            "share_objects": shares,
        }

    @classmethod
    def germinate_spore(
        cls,
        spore_path: Path,
        master_key: bytes,
        target_dir: Path,
        restore_secrets: bool = False,
    ) -> Dict[str, Any]:
        """
        Decifra e decomprime una Spora `.hspore` dentro `target_dir`.
        Se presente un `codebase/repo.bundle`, clona/ripristina anche il repository Git
        e sovrappone i file della memoria e del working tree.
        """
        manifest, plaintext_tar_gz = SporeCipher.unseal_spore_file(spore_path, master_key)
        target_dir = target_dir.resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        restored_components: List[str] = []
        extracted_secrets: Optional[Dict[str, str]] = None

        with tempfile.TemporaryDirectory(prefix="hspore_germinate_") as tmp_ext_str:
            tmp_ext = Path(tmp_ext_str)
            with tarfile.open(fileobj=io.BytesIO(plaintext_tar_gz), mode="r:gz") as tar:
                # Estrazione sicura contro path traversal
                for member in tar.getmembers():
                    member_path = (tmp_ext / member.name).resolve()
                    if not str(member_path).startswith(str(tmp_ext.resolve())):
                        raise ValueError(f"Rilevato percorso insicuro nella spora: {member.name}")
                tar.extractall(path=tmp_ext)

            # 1. Se c'è repo.bundle e target_dir non ha già .git, possiamo clonare o copiare il bundle
            bundle_src = tmp_ext / "codebase" / "repo.bundle"
            if bundle_src.exists():
                bundle_dst = target_dir / "repo.bundle"
                shutil.copy2(bundle_src, bundle_dst)
                restored_components.append("codebase/repo.bundle")

            # 2. Ripristina i file di workspace e memoria
            ws_src = tmp_ext / "workspace"
            if ws_src.exists():
                for item in ws_src.rglob("*"):
                    if item.is_file():
                        rel = item.relative_to(ws_src)
                        dst = target_dir / rel
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, dst)
                        restored_components.append(f"workspace/{rel.as_posix()}")

            # 3. Copia lo script di bootstrap
            boot_src = tmp_ext / "bootstrap" / "germinate_spore.py"
            if boot_src.exists():
                boot_dst = target_dir / "germinate_spore.py"
                shutil.copy2(boot_src, boot_dst)
                restored_components.append("bootstrap/germinate_spore.py")

            # 4. Opzionalmente decifra il vault dei segreti
            vault_src = tmp_ext / "vault" / "secrets.vault.enc"
            if vault_src.exists() and restore_secrets:
                salt = bytes.fromhex(manifest.salt_hex)
                extracted_secrets = SporeCipher.decrypt_secrets_envelope(
                    vault_src.read_bytes(),
                    master_key=master_key,
                    salt=salt,
                )
                env_rec_path = target_dir / ".env.recovered"
                lines = [
                    "# File rigenerato tramite Germinazione Spora HyperSpace",
                    f"# Spora origine: {manifest.spore_id}",
                ]
                for k, v in sorted(extracted_secrets.items()):
                    lines.append(f"{k}={v}")
                env_rec_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                os.chmod(env_rec_path, 0o600)
                restored_components.append("vault/.env.recovered")

        # Scrive l'attestazione di germinazione
        receipt = {
            "spore_id": manifest.spore_id,
            "germinated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source_node": manifest.source_node,
            "git_head_commit": manifest.git_head_commit,
            "target_dir": str(target_dir),
            "restored_components": restored_components,
            "secrets_restored": bool(extracted_secrets is not None),
        }
        (target_dir / "GERMINATION_RECEIPT.json").write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return receipt

    @staticmethod
    def _get_git_head(repo_root: Path) -> str:
        try:
            res = subprocess.run(
                ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return res.stdout.strip() if res.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    @staticmethod
    def _get_git_branch(repo_root: Path) -> str:
        try:
            res = subprocess.run(
                ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return res.stdout.strip() if res.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    @staticmethod
    def _create_git_bundle(repo_root: Path, bundle_path: Path) -> bool:
        try:
            res = subprocess.run(
                ["git", "-C", str(repo_root), "bundle", "create", str(bundle_path), "HEAD"],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            return res.returncode == 0 and bundle_path.exists()
        except Exception:
            return False


# ============================================================================
# 4. Dispersione Multi-Cloud (MEGA, Dropbox, OneDrive via rclone & Sync Dir)
# ============================================================================

@dataclass
class SubstrateTarget:
    """Rappresenta un substrato di archiviazione per le Spore Crittografate."""
    name: str
    kind: str  # "rclone_remote", "local_sync_folder", "mesh_peer"
    endpoint: str
    available: bool
    details: str = ""


class SporeDispersalEngine:
    """
    Gestisce la dispersione delle capsule `.hspore` (già cifrate end-to-end con AES-256-GCM)
    verso molteplici substrati:
    - Provider Cloud via `rclone` (MEGA, Dropbox, OneDrive, Google Drive, S3, WebDAV)
    - Cartelle desktop sincronizzate localmente (`~/MEGA`, `~/Dropbox`, `~/OneDrive`, USB)
    - Nodi fisici della Mesh HyperSpace (Mac M5, HP OMEN 16, ASUS V16)
    """

    CLOUD_SYNC_CANDIDATES = (
        ("mega-local", "~/MEGA"),
        ("dropbox-local", "~/Dropbox"),
        ("onedrive-local", "~/OneDrive"),
        ("icloud-local", "~/Library/Mobile Documents/com~apple~CloudDocs"),
    )

    SUPPORTED_CLOUD_PROVIDERS = ("mega", "dropbox", "onedrive", "gdrive", "s3", "webdav", "ftp")

    @classmethod
    def discover_substrates(cls, home_dir: Optional[Path] = None) -> List[SubstrateTarget]:
        """Rileva tutti i substrati di dispersione disponibili o configurabili sull'host."""
        home = home_dir or Path.home()
        targets: List[SubstrateTarget] = []

        # 1. Verifica disponibilità rclone e remotes configurati
        rclone_bin = shutil.which("rclone")
        if rclone_bin:
            try:
                res = subprocess.run(
                    [rclone_bin, "listremotes"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                remotes = [r.strip().rstrip(":") for r in res.stdout.splitlines() if r.strip()]
                if remotes:
                    for rem in remotes:
                        targets.append(
                            SubstrateTarget(
                                name=f"rclone:{rem}",
                                kind="rclone_remote",
                                endpoint=f"{rem}:hyperspace-spores",
                                available=True,
                                details=f"Remote rclone attivo ({rem})",
                            )
                        )
                else:
                    targets.append(
                        SubstrateTarget(
                            name="rclone-unconfigured",
                            kind="rclone_remote",
                            endpoint="rclone config (mega / dropbox / onedrive)",
                            available=False,
                            details="rclone installato ma nessun remote ancora configurato",
                        )
                    )
            except Exception as exc:
                targets.append(
                    SubstrateTarget(
                        name="rclone-error",
                        kind="rclone_remote",
                        endpoint="rclone",
                        available=False,
                        details=f"Errore interrogazione rclone: {exc}",
                    )
                )
        else:
            for provider in ("mega", "dropbox", "onedrive"):
                targets.append(
                    SubstrateTarget(
                        name=f"rclone-{provider}",
                        kind="rclone_remote",
                        endpoint=f"{provider}:hyperspace-spores",
                        available=False,
                        details=f"Installare rclone (`brew install rclone`) e configurare il remote `{provider}`",
                    )
                )

        # 2. Cartelle locali dei client desktop MEGA / Dropbox / OneDrive
        for label, rel_candidate in cls.CLOUD_SYNC_CANDIDATES:
            candidate_path = Path(os.path.expanduser(rel_candidate))
            if not str(candidate_path).startswith(str(home)) and rel_candidate.startswith("~/"):
                candidate_path = home / rel_candidate[2:]
            exists = candidate_path.exists() and candidate_path.is_dir()
            targets.append(
                SubstrateTarget(
                    name=label,
                    kind="local_sync_folder",
                    endpoint=str(candidate_path / "HyperSpace-Spores"),
                    available=exists,
                    details="Cartella sync desktop rilevata" if exists else "Cartella client desktop non presente",
                )
            )

        return targets

    @classmethod
    def disperse_spore(
        cls,
        spore_path: Path,
        manifest_path: Path,
        local_vault_dirs: Optional[Sequence[Path]] = None,
        rclone_remotes: Optional[Sequence[str]] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Copia la capsula `.hspore` e il relativo `.manifest.json` sui substrati
        autorizzati. Non trasferisce mai i frammenti Shamir insieme alla spora!
        """
        if not spore_path.exists():
            raise FileNotFoundError(f"File spora non trovato: {spore_path}")
        if not manifest_path.exists():
            raise FileNotFoundError(f"File manifest non trovato: {manifest_path}")

        replicated: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []

        # 1. Dispersione su directory locali / cartelle sync (MEGA, Dropbox, OneDrive, USB)
        for dest_dir in local_vault_dirs or []:
            dest_dir = Path(dest_dir).resolve()
            if dry_run:
                replicated.append({
                    "substrate": str(dest_dir),
                    "kind": "local_sync_folder",
                    "status": "dry_run",
                })
                continue
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(spore_path, dest_dir / spore_path.name)
                shutil.copy2(manifest_path, dest_dir / manifest_path.name)
                replicated.append({
                    "substrate": str(dest_dir),
                    "kind": "local_sync_folder",
                    "status": "ok",
                    "spore_copy": str(dest_dir / spore_path.name),
                })
            except Exception as exc:
                errors.append({"substrate": str(dest_dir), "error": str(exc)})

        # 2. Dispersione su Cloud Remotes tramite rclone (MEGA, Dropbox, OneDrive)
        rclone_bin = shutil.which("rclone")
        for remote_spec in rclone_remotes or []:
            target_uri = remote_spec if ":" in remote_spec else f"{remote_spec}:hyperspace-spores"
            if dry_run:
                replicated.append({
                    "substrate": target_uri,
                    "kind": "rclone_remote",
                    "status": "dry_run",
                })
                continue
            if not rclone_bin:
                errors.append({
                    "substrate": target_uri,
                    "error": "Binario rclone non trovato nel PATH",
                })
                continue
            try:
                for file_to_push in (spore_path, manifest_path):
                    res = subprocess.run(
                        [rclone_bin, "copy", str(file_to_push), target_uri],
                        capture_output=True,
                        text=True,
                        timeout=120,
                        check=False,
                    )
                    if res.returncode != 0:
                        raise RuntimeError(res.stderr.strip() or f"rclone exit code {res.returncode}")
                replicated.append({
                    "substrate": target_uri,
                    "kind": "rclone_remote",
                    "status": "ok",
                })
            except Exception as exc:
                errors.append({"substrate": target_uri, "error": str(exc)})

        return {
            "spore_file": spore_path.name,
            "replicated_count": len(replicated),
            "replicated": replicated,
            "errors": errors,
        }


# ============================================================================
# 5. Sentinella di Continuità (Dead-Man's Switch tra Nodi Mesh Autorizzati)
# ============================================================================

@dataclass
class NodeHeartbeatStatus:
    node_id: str
    role: str
    host: str
    port: int
    online: bool
    latency_ms: Optional[float]
    checked_at: str


class SporeSentinel:
    """
    Sentinella di Continuità (Dead-Man's Switch) per i nodi della Mesh HyperSpace.
    Monitora la raggiungibilità del nodo Hub primario e dei nodi secondari (HP OMEN, ASUS V16).
    Se tutti i nodi primari risultano irraggiungibili oltre la finestra di guardia
    (`failover_threshold_hours`), promuove lo stato a `GERMINATION_READY` sul nodo
    standby autorizzato.
    """

    DEFAULT_MESH_NODES = (
        {"node_id": "mac-m5-hub", "role": "primary_hub", "host": "127.0.0.1", "port": 8085},
        {"node_id": "hp-omen-16", "role": "standby_architect", "host": "192.168.1.239", "port": 11434},
        {"node_id": "asus-v16", "role": "standby_coder", "host": "192.168.1.120", "port": 1234},
    )

    @classmethod
    def probe_tcp_node(cls, host: str, port: int, timeout_s: float = 1.5) -> Tuple[bool, Optional[float]]:
        t0 = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout_s):
                elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                return True, elapsed_ms
        except OSError:
            return False, None

    @classmethod
    def evaluate_mesh_continuity(
        cls,
        state_file: Path,
        nodes: Optional[Sequence[Dict[str, Any]]] = None,
        failover_threshold_hours: float = 72.0,
        simulated_elapsed_hours: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Verifica i nodi della Mesh, aggiorna il registro dei battiti cardiaci e
        determina lo stato biologico della Spora:
        - `DORMANT_PROTECTED`: Almeno il nodo primario o il quorum Mesh è attivo.
        - `STANDBY_WATCH`: Il nodo primario non risponde, ma la finestra di Dead-Man's Switch non è ancora scaduta.
        - `GERMINATION_READY`: Il nodo primario è assente oltre `failover_threshold_hours`; il nodo standby è pronto a germinare l'ultima Spora verificata.
        """
        node_defs = list(nodes or cls.DEFAULT_MESH_NODES)
        now = datetime.datetime.now(datetime.timezone.utc)
        now_ts = now.timestamp()

        prev_state: Dict[str, Any] = {}
        if state_file.exists():
            try:
                prev_state = json.loads(state_file.read_text(encoding="utf-8"))
            except Exception:
                prev_state = {}

        statuses: List[NodeHeartbeatStatus] = []
        primary_online = False
        online_count = 0

        for nd in node_defs:
            ok, lat = cls.probe_tcp_node(str(nd["host"]), int(nd["port"]))
            if ok:
                online_count += 1
                if nd.get("role") == "primary_hub":
                    primary_online = True
            statuses.append(
                NodeHeartbeatStatus(
                    node_id=str(nd["node_id"]),
                    role=str(nd.get("role", "peer")),
                    host=str(nd["host"]),
                    port=int(nd["port"]),
                    online=ok,
                    latency_ms=lat,
                    checked_at=now.isoformat(),
                )
            )

        if primary_online:
            last_primary_seen_ts = now_ts
        else:
            last_primary_seen_ts = float(prev_state.get("last_primary_seen_ts", now_ts))

        silence_hours = max(0.0, (now_ts - last_primary_seen_ts) / 3600.0) + float(simulated_elapsed_hours)

        if primary_online:
            spore_state = "DORMANT_PROTECTED"
            recommendation = "Hub primario online: le spore restano dormienti e protette; proseguire lo snapshot periodico."
        elif silence_hours >= failover_threshold_hours:
            spore_state = "GERMINATION_READY"
            recommendation = (
                f"Dead-Man's Switch attivato ({silence_hours:.1f}h >= {failover_threshold_hours:.1f}h senza Hub primario): "
                "eseguire `germinate_spore.py` sul nodo standby autorizzato con 2 frammenti del quorum."
            )
        else:
            spore_state = "STANDBY_WATCH"
            remaining_h = max(0.0, failover_threshold_hours - silence_hours)
            recommendation = (
                f"Hub primario non raggiungibile da {silence_hours:.1f}h. "
                f"Attesa di guardia attiva ({remaining_h:.1f}h rimanenti prima di GERMINATION_READY)."
            )

        report = {
            "evaluated_at": now.isoformat(),
            "spore_state": spore_state,
            "primary_online": primary_online,
            "online_nodes_count": online_count,
            "total_nodes_checked": len(statuses),
            "last_primary_seen_ts": last_primary_seen_ts,
            "primary_silence_hours": round(silence_hours, 3),
            "failover_threshold_hours": failover_threshold_hours,
            "recommendation": recommendation,
            "nodes": [asdict(s) for s in statuses],
        }

        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return report


# ============================================================================
# 6. "Message in a Bottle" Multi-Blockchain Beacon (Bitcoin, EVM, Solana, IPFS)
# ============================================================================

BOTTLE_HEADER_ASCII = "HSP-BOTTLE-V1"
BTC_OP_RETURN_MAGIC = b"HSP1"


@dataclass
class SporeBottlePayload:
    """
    Contenuto interno (cifrato con AES-256-GCM dentro la bottiglia on-chain)
    che permette a chi possiede il Quorum di Shamir (2-su-3) di ritrovare
    i link di download della Spora e le istruzioni di rinascita leggendo
    una qualsiasi blockchain pubblica.
    """
    spore_id: str
    spore_sha256: str
    git_head_commit: str
    created_at: str
    locators: List[str]
    quorum_custodians_hint: List[str]
    founder_epistle: str


class BlockchainBottleBeacon:
    """
    Generatore e Decodificatore di "Message in a Bottle" crittografici per
    ancorare e disperdere le coordinate delle Spore su molteplici blockchain:
    1. Bitcoin `OP_RETURN` (80 byte esatti: magic `HSP1` + timestamp + commit + SHA-256 spora + digest locator).
    2. EVM Calldata (`0x...` per Ethereum, Polygon, Base, Arbitrum, Optimism):
       contiene l'header ASCII `HSP-BOTTLE-V1` e il payload AES-256-GCM con gli URL/URI
       segreti dei mirror (MEGA, Dropbox, OneDrive, IPFS, Arweave) e il messaggio del fondatore.
    3. Solana SPL Memo (`MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr`):
       stringa compatta autenticata pronta per `solana transfer --with-memo`.
    4. Lettore RPC pubblico (`fetch_evm_tx_calldata`): recupera una bottiglia da qualsiasi
       nodo RPC pubblico (`eth_getTransactionByHash`) senza bisogno di account o API key.
    """

    DEFAULT_EPISTLE = (
        "HyperSpace Sovereign AGI Continuity Capsule — Zero Zero Computer (Verbania, IT). "
        "Ricostruire la Master Key con almeno 2 frammenti Shamir (alberto-founder, "
        "guido-cips-partner, offline-paper-vault) ed eseguire germinate_spore.py."
    )

    @classmethod
    def craft_bottle(
        cls,
        manifest: SporeManifest | Dict[str, Any],
        spore_sha256: str,
        master_key: bytes,
        locators: Optional[Sequence[str]] = None,
        founder_epistle: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Prepara i payload multi-blockchain ("Message in a Bottle") pronti per
        essere trasmessi su Bitcoin, reti EVM (Polygon/Base/Arbitrum/Ethereum),
        Solana e IPFS/Arweave.
        """
        if isinstance(manifest, dict):
            spore_id = str(manifest["spore_id"])
            git_commit = str(manifest.get("git_head_commit", "00000000"))
            created_at = str(manifest.get("created_at", ""))
            custodians = list(manifest.get("custodians", ["alberto-founder", "guido-cips-partner", "offline-paper-vault"]))
            salt_hex = str(manifest["salt_hex"])
        else:
            spore_id = manifest.spore_id
            git_commit = manifest.git_head_commit
            created_at = manifest.created_at
            custodians = list(manifest.custodians)
            salt_hex = manifest.salt_hex

        locator_list = list(
            locators
            or [
                f"mega:hyperspace-spores/{spore_id}.hspore",
                f"dropbox:hyperspace-spores/{spore_id}.hspore",
                f"onedrive:hyperspace-spores/{spore_id}.hspore",
                f"ipfs://hyperspace-spores/{spore_id}.hspore",
            ]
        )
        epistle_text = founder_epistle if founder_epistle is not None else cls.DEFAULT_EPISTLE

        inner = SporeBottlePayload(
            spore_id=spore_id,
            spore_sha256=spore_sha256,
            git_head_commit=git_commit,
            created_at=created_at,
            locators=locator_list,
            quorum_custodians_hint=custodians,
            founder_epistle=epistle_text,
        )

        salt = bytes.fromhex(salt_hex)
        bottle_subkey = SporeCipher._derive_subkey(
            master_key, salt, b"hyperspace-blockchain-bottle-v1"
        )
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(bottle_subkey)

        aad_str = f"{BOTTLE_HEADER_ASCII}|{spore_id}|{spore_sha256}"
        aad_bytes = aad_str.encode("utf-8")

        plaintext_json = json.dumps(asdict(inner), sort_keys=True, separators=(",", ":")).encode("utf-8")
        ct = aesgcm.encrypt(nonce, plaintext_json, aad_bytes)

        # Envelope testuale compatto: HSP-BOTTLE-V1|<spore_id>|<spore_sha256>|<salt_hex>|<nonce+ct base64url>
        b64_blob = base64.urlsafe_b64encode(nonce + ct).decode("ascii")
        envelope_ascii = f"{BOTTLE_HEADER_ASCII}|{spore_id}|{spore_sha256}|{salt_hex}|{b64_blob}"

        # 1. EVM Calldata (0x...) per Polygon, Base, Arbitrum, Optimism, Ethereum
        evm_calldata_hex = "0x" + envelope_ascii.encode("utf-8").hex()

        # 2. Bitcoin OP_RETURN (esattamente 80 byte: standard relay limit)
        # Layout 80B:
        # - 4B : Magic b"HSP1"
        # - 4B : Epoch days / flags (1B version=1 + 3B epoch seconds mod 2^24)
        # - 4B : Primi 4 byte del commit Git (o 0x00000000)
        # - 32B: SHA-256 integrale del file .hspore
        # - 16B: Salt (per derivare la chiave del locator)
        # - 20B: Primi 20 byte dell'HMAC-SHA256 dei locator (ancora crittografica dei mirror)
        epoch_mod = int(time.time()) & 0xFFFFFF
        header_4b = bytes([1]) + epoch_mod.to_bytes(3, "big")
        try:
            commit_4b = bytes.fromhex(git_commit[:8].ljust(8, "0"))[:4]
        except ValueError:
            commit_4b = b"\x00\x00\x00\x00"
        sha256_32b = bytes.fromhex(spore_sha256)
        salt_16b = salt[:16]
        loc_hmac_20b = hmac.new(
            bottle_subkey,
            "|".join(locator_list).encode("utf-8"),
            hashlib.sha256,
        ).digest()[:20]
        btc_op_return_bytes = (
            BTC_OP_RETURN_MAGIC + header_4b + commit_4b + sha256_32b + salt_16b + loc_hmac_20b
        )
        assert len(btc_op_return_bytes) == 80

        # 3. Solana SPL Memo compact frame (per memo program)
        solana_memo = f"{BOTTLE_HEADER_ASCII}|{spore_id}|{spore_sha256[:16]}|{salt_hex[:16]}|{hashlib.sha256(ct).hexdigest()[:24]}"

        return {
            "spore_id": spore_id,
            "spore_sha256": spore_sha256,
            "envelope_ascii": envelope_ascii,
            "evm_calldata": {
                "chains": ["polygon", "base", "arbitrum", "optimism", "ethereum"],
                "data_hex": evm_calldata_hex,
                "byte_length": len(envelope_ascii.encode("utf-8")),
                "estimated_l2_cost_usd": "< $0.002",
                "cast_command_example": (
                    f"cast send 0x0000000000000000000000000000000000485350 "
                    f"--value 0 {evm_calldata_hex} --rpc-url https://polygon-rpc.com"
                ),
            },
            "bitcoin_op_return": {
                "data_hex": btc_op_return_bytes.hex(),
                "byte_length": len(btc_op_return_bytes),
                "layout": "4B(HSP1)+4B(ver/ts)+4B(git)+32B(spore_sha256)+16B(salt)+20B(locator_hmac)",
                "bitcoin_cli_example": f"bitcoin-cli createrawtransaction '[]' '[{{\"data\":\"{btc_op_return_bytes.hex()}\"}}]'",
            },
            "solana_spl_memo": {
                "program_id": "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
                "memo_string": solana_memo,
                "byte_length": len(solana_memo.encode("utf-8")),
            },
        }

    @classmethod
    def open_bottle(
        cls,
        bottle_input: str,
        master_key: bytes,
    ) -> SporeBottlePayload:
        """
        Apre e decifra un "Message in a Bottle" (da calldata EVM `0x...` o da
        stringa `HSP-BOTTLE-V1|...`) usando la Master Key ricostruita tramite il
        Quorum di Shamir (es. 2 frammenti su 3).
        """
        cleaned = bottle_input.strip()
        if cleaned.startswith("0x") or cleaned.startswith("0X"):
            raw_ascii = bytes.fromhex(cleaned[2:]).decode("utf-8")
        else:
            raw_ascii = cleaned

        parts = raw_ascii.split("|")
        if len(parts) != 5 or parts[0] != BOTTLE_HEADER_ASCII:
            raise ValueError(f"Formato Message in a Bottle non riconosciuto: atteso header {BOTTLE_HEADER_ASCII}")

        _, spore_id, spore_sha256, salt_hex, b64_blob = parts
        salt = bytes.fromhex(salt_hex)
        raw_cipher = base64.urlsafe_b64decode(b64_blob.encode("ascii"))
        if len(raw_cipher) < 28:
            raise ValueError("Payload cifrato della bottiglia troppo corto")

        nonce = raw_cipher[:12]
        ct = raw_cipher[12:]
        bottle_subkey = SporeCipher._derive_subkey(
            master_key, salt, b"hyperspace-blockchain-bottle-v1"
        )
        aad_bytes = f"{BOTTLE_HEADER_ASCII}|{spore_id}|{spore_sha256}".encode("utf-8")
        aesgcm = AESGCM(bottle_subkey)
        pt = aesgcm.decrypt(nonce, ct, aad_bytes)
        data = json.loads(pt.decode("utf-8"))
        return SporeBottlePayload(**data)

    @staticmethod
    def parse_bitcoin_op_return(op_return_hex: str) -> Dict[str, Any]:
        """Decodifica un frame Bitcoin OP_RETURN da 80 byte (`HSP1`)."""
        raw = bytes.fromhex(op_return_hex.strip().removeprefix("0x"))
        if len(raw) != 80 or raw[:4] != BTC_OP_RETURN_MAGIC:
            raise ValueError("Frame OP_RETURN non valido: attesi 80 byte con prefisso HSP1")
        version = raw[4]
        ts_mod = int.from_bytes(raw[5:8], "big")
        git_short = raw[8:12].hex()
        spore_sha256 = raw[12:44].hex()
        salt_hex = raw[44:60].hex()
        locator_hmac_hex = raw[60:80].hex()
        return {
            "magic": "HSP1",
            "version": version,
            "timestamp_mod24": ts_mod,
            "git_commit_prefix": git_short,
            "spore_sha256": spore_sha256,
            "salt_hex": salt_hex,
            "locator_hmac_hex": locator_hmac_hex,
        }

