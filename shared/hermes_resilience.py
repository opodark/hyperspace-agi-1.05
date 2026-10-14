# SPDX-License-Identifier: Apache-2.0
"""Sistema di resilienza e decentralizzazione cloud per la memoria Hermes di HyperSpace.

Questo modulo implementa la replica decentralizzata e sicura (Zero-Knowledge)
della memoria Hermes e del mirror locale HyperSpace attraverso molteplici provider
cloud (gratuiti e a pagamento) e reti decentralizzate (IPFS, WebDAV, S3/R2/B2, GitHub).

Caratteristiche fondamentali:
1. Crittografia Zero-Knowledge Client-Side:
   I dati di memoria (conversazioni, stato cognitivo, preferenze utente, skill)
   vengono cifrati localmente con AES-256-GCM (derivazione chiave PBKDF2-HMAC-SHA256
   con salt casuale a 16 byte e nonce a 12 byte) PRIMA di essere trasmessi. I cloud
   provider memorizzano solo ciphertext autenticato e indecifrabile.
2. Formato Vault Unificato (`hyperspace.hermes.vault.v1`):
   Pacchetto auto-consistente con header JSON pubblico/verificabile e payload
   cifrato contenente un archivio tar.gz con:
   - Hermes `MEMORY.md` e `USER.md`
   - Hermes `state.db` (snapshot SQLite FTS5 sicuro)
   - Hermes `skills/`
   - Mirror locale `hyperspace.memory.v1` e coda outbox
3. Adattatori Cloud e P2P Pluggable:
   - S3-compatible: Cloudflare R2 (10 GB gratuiti, 0 costi egress), Backblaze B2 (10 GB free), AWS S3, MinIO, Wasabi.
     Implementazione autonoma SigV4 senza dipendenze pesanti.
   - WebDAV: Nextcloud, ownCloud, pCloud, Koofr, Infomaniak.
   - GitHub: Gist privato o repository release/contents per decentralizzazione git gratuita.
   - IPFS / Filecoin: Pinning decentralizzato tramite nodo IPFS locale o gateway Pinata.
   - Filesystem / Mount: Directory locale, disco esterno, NAS o mount point rclone (Google Drive, Dropbox, OneDrive).
4. Multi-Cloud Fan-Out & Disaster Recovery:
   - Caricamento sincrono/parallelo su molteplici destinazioni configurate ("regola del backup 3-2-1").
   - Fallback trasparente in download da qualsiasi provider disponibile.
   - Ripristino atomico o re-iniezione via API nel bridge Hermes attivo.
   - Pruning automatico delle versioni più vecchie per non sforare i tier gratuiti.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import hmac
import io
import json
import os
import shutil
import sqlite3
import tarfile
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import quote, urlparse
import xml.etree.ElementTree as ET

import requests

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


VAULT_MAGIC = b"HSMV"  # HyperSpace Memory Vault
VAULT_SCHEMA_VERSION = "hyperspace.hermes.vault.v1"
PBKDF2_ITERATIONS = 100_000
DEFAULT_RETENTION = 7


# ==============================================================================
# 1. CRITTOGRAFIA & ENVELOPE ZERO-KNOWLEDGE (AES-256-GCM + PBKDF2)
# ==============================================================================

class HermesCryptoError(RuntimeError):
    """Errore durante la cifratura, decifratura o verifica di integrità del vault."""


class HermesVaultCipher:
    """Gestisce la cifratura e decifratura client-side dei pacchetti di memoria."""

    def __init__(self, passphrase: Optional[str] = None, key_bytes: Optional[bytes] = None):
        if not _HAS_CRYPTO:
            raise HermesCryptoError(
                "Libreria 'cryptography' non disponibile nell'ambiente. "
                "Installare cryptography per abilitare la cifratura zero-knowledge."
            )
        self.passphrase = passphrase or ""
        self._key_bytes = key_bytes

        if not self.passphrase and not self._key_bytes:
            # Tenta di leggere dall'ambiente o da file
            self.passphrase = os.getenv("HERMES_VAULT_PASSPHRASE") or os.getenv("HERMES_ENCRYPTION_KEY") or ""
            if not self.passphrase:
                key_file = os.getenv("HERMES_VAULT_KEY_FILE", "")
                if key_file and Path(key_file).exists():
                    try:
                        self.passphrase = Path(key_file).read_text(encoding="utf-8").strip()
                    except OSError:
                        pass

    def is_configured(self) -> bool:
        return bool(self.passphrase or self._key_bytes)

    def _derive_key(self, salt: bytes) -> bytes:
        if self._key_bytes and len(self._key_bytes) == 32:
            return self._key_bytes
        if not self.passphrase:
            raise HermesCryptoError("Nessuna chiave o passphrase configurata per Hermes Vault.")
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
        )
        return kdf.derive(self.passphrase.encode("utf-8"))

    def encrypt_vault(self, payload: bytes, metadata: Optional[Dict[str, Any]] = None) -> bytes:
        """Cifra un payload grezzo (es. tar.gz) incapsulandolo nell'envelope HSMV."""
        salt = os.urandom(16)
        nonce = os.urandom(12)
        key = self._derive_key(salt)
        aesgcm = AESGCM(key)

        unencrypted_sha256 = hashlib.sha256(payload).hexdigest()
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        snapshot_id = (metadata or {}).get("snapshot_id") or f"hermes-snap-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{os.urandom(4).hex()}"

        header_dict: Dict[str, Any] = {
            "magic": "HSMV",
            "version": "1.0",
            "schema": VAULT_SCHEMA_VERSION,
            "snapshot_id": snapshot_id,
            "created_at": now_iso,
            "algorithm": "AES-256-GCM",
            "kdf": "PBKDF2-HMAC-SHA256",
            "kdf_iterations": PBKDF2_ITERATIONS,
            "salt_b64": base64.b64encode(salt).decode("ascii"),
            "nonce_b64": base64.b64encode(nonce).decode("ascii"),
            "unencrypted_sha256": unencrypted_sha256,
            "unencrypted_bytes": len(payload),
            "metadata": metadata or {},
        }

        header_bytes = json.dumps(header_dict, ensure_ascii=False, sort_keys=True).encode("utf-8")
        # Autentica l'header come Additional Authenticated Data (AAD)
        ciphertext = aesgcm.encrypt(nonce, payload, header_bytes)
        header_dict["ciphertext_bytes"] = len(ciphertext)
        header_dict["ciphertext_sha256"] = hashlib.sha256(ciphertext).hexdigest()

        # Ri-serializziamo l'header con i campi finali e usiamo AAD definitivo
        final_header_bytes = json.dumps(header_dict, ensure_ascii=False, sort_keys=True).encode("utf-8")
        final_ciphertext = aesgcm.encrypt(nonce, payload, final_header_bytes)

        # Formato binario: [MAGIC 4B][HEADER_LEN 4B (big endian)][HEADER JSON][CIPHERTEXT]
        header_len = len(final_header_bytes)
        buffer = bytearray()
        buffer.extend(VAULT_MAGIC)
        buffer.extend(header_len.to_bytes(4, byteorder="big"))
        buffer.extend(final_header_bytes)
        buffer.extend(final_ciphertext)
        return bytes(buffer)

    def decrypt_vault(self, vault_data: bytes) -> Tuple[Dict[str, Any], bytes]:
        """Verifica e decifra un pacchetto HSMV restituendo (header_metadata, payload)."""
        if len(vault_data) < 8:
            raise HermesCryptoError("File vault troppo corto o non valido.")
        if vault_data[:4] != VAULT_MAGIC:
            raise HermesCryptoError(f"Magic header non riconosciuto (atteso {VAULT_MAGIC.decode('latin1')}).")

        header_len = int.from_bytes(vault_data[4:8], byteorder="big")
        if len(vault_data) < 8 + header_len:
            raise HermesCryptoError("Dati vault troncati: header incompleto.")

        header_bytes = vault_data[8:8 + header_len]
        ciphertext = vault_data[8 + header_len:]

        try:
            header = json.loads(header_bytes.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise HermesCryptoError(f"Impossibile interpretare l'header del vault: {exc}") from exc

        salt = base64.b64decode(header["salt_b64"])
        nonce = base64.b64decode(header["nonce_b64"])
        key = self._derive_key(salt)
        aesgcm = AESGCM(key)

        try:
            payload = aesgcm.decrypt(nonce, ciphertext, header_bytes)
        except Exception as exc:
            raise HermesCryptoError(
                "Decifratura fallita: passphrase non corretta o dati manomessi (InvalidTag)."
            ) from exc

        calc_sha = hashlib.sha256(payload).hexdigest()
        if calc_sha != header.get("unencrypted_sha256"):
            raise HermesCryptoError(
                f"Integrità compromessa: SHA256 calcolato ({calc_sha}) diverso da quello atteso ({header.get('unencrypted_sha256')})."
            )

        return header, payload

    @staticmethod
    def read_header(vault_data: bytes) -> Dict[str, Any]:
        """Legge l'header del vault senza decifrare il payload (sicuro per diagnostica)."""
        if len(vault_data) < 8 or vault_data[:4] != VAULT_MAGIC:
            raise HermesCryptoError("File vault non valido.")
        header_len = int.from_bytes(vault_data[4:8], byteorder="big")
        header_bytes = vault_data[8:8 + header_len]
        return json.loads(header_bytes.decode("utf-8"))


# ==============================================================================
# 2. CREAZIONE ED ESTRAZIONE SNAPSHOT BUNDLE
# ==============================================================================

class HermesSnapshotBundle:
    """Compone ed estrae archivi tar.gz contenenti tutte le sorgenti di memoria Hermes."""

    @staticmethod
    def create_bundle(
        hermes_dir: Optional[Union[str, Path]] = None,
        memory_mirror_file: Optional[Union[str, Path]] = None,
        memory_outbox_file: Optional[Union[str, Path]] = None,
        hermes_client_entries: Optional[List[Dict[str, Any]]] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bytes, Dict[str, Any]]:
        """Crea in memoria un tar.gz dei file Hermes e HyperSpace.

        Ritorna (payload_tar_gz_bytes, manifest_info).
        """
        buf = io.BytesIO()
        manifest: Dict[str, Any] = {
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "files": [],
            "entries_count": 0,
            "stats": {},
            "metadata": extra_metadata or {},
        }

        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            # 1. File Hermes da HERMES_HOME (se presenti)
            if hermes_dir:
                h_path = Path(hermes_dir)
                if h_path.exists():
                    # MEMORY.md e USER.md
                    for fname in ("MEMORY.md", "USER.md"):
                        target = h_path / fname
                        if target.is_file():
                            data = target.read_bytes()
                            ti = tarfile.TarInfo(name=f"hermes/{fname}")
                            ti.size = len(data)
                            ti.mtime = int(target.stat().st_mtime)
                            tar.addfile(ti, io.BytesIO(data))
                            manifest["files"].append(f"hermes/{fname}")

                    # Skills directory
                    skills_dir = h_path / "skills"
                    if skills_dir.is_dir():
                        for skill_file in skills_dir.rglob("*"):
                            if skill_file.is_file():
                                rel = skill_file.relative_to(skills_dir)
                                data = skill_file.read_bytes()
                                ti = tarfile.TarInfo(name=f"hermes/skills/{rel}")
                                ti.size = len(data)
                                ti.mtime = int(skill_file.stat().st_mtime)
                                tar.addfile(ti, io.BytesIO(data))
                                manifest["files"].append(f"hermes/skills/{rel}")

                    # state.db (SQLite backup sicuro per evitare lock o corruzioni WAL)
                    db_file = h_path / "state.db"
                    if db_file.is_file():
                        try:
                            # Utilizza SQLite online backup API verso un buffer in memoria
                            src_conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
                            dst_conn = sqlite3.connect(":memory:")
                            src_conn.backup(dst_conn)
                            src_conn.close()

                            db_dump_io = io.BytesIO()
                            for line in dst_conn.iterdump():
                                db_dump_io.write(f"{line}\n".encode("utf-8"))
                            dst_conn.close()
                            db_dump_data = db_dump_io.getvalue()

                            ti = tarfile.TarInfo(name="hermes/state.sql")
                            ti.size = len(db_dump_data)
                            ti.mtime = int(time.time())
                            tar.addfile(ti, io.BytesIO(db_dump_data))
                            manifest["files"].append("hermes/state.sql")
                        except Exception as exc:
                            # Fallback: copia raw del file se iter-dump non riesce
                            data = db_file.read_bytes()
                            ti = tarfile.TarInfo(name="hermes/state.db")
                            ti.size = len(data)
                            ti.mtime = int(db_file.stat().st_mtime)
                            tar.addfile(ti, io.BytesIO(data))
                            manifest["files"].append("hermes/state.db")

            # 2. HyperSpace memory mirror locale (memory.json.gz)
            if memory_mirror_file:
                m_path = Path(memory_mirror_file)
                if m_path.is_file():
                    try:
                        raw = m_path.read_bytes()
                        ti = tarfile.TarInfo(name="hyperspace/memory.json.gz")
                        ti.size = len(raw)
                        ti.mtime = int(m_path.stat().st_mtime)
                        tar.addfile(ti, io.BytesIO(raw))
                        manifest["files"].append("hyperspace/memory.json.gz")
                        # Conta voci nel mirror per il manifest
                        with gzip.open(io.BytesIO(raw), "rt", encoding="utf-8") as gf:
                            dati = json.load(gf)
                            if isinstance(dati, list):
                                manifest["entries_count"] += len(dati)
                    except Exception:
                        pass

            # 3. HyperSpace Outbox (memory-outbox.jsonl)
            if memory_outbox_file:
                o_path = Path(memory_outbox_file)
                if o_path.is_file():
                    raw = o_path.read_bytes()
                    ti = tarfile.TarInfo(name="hyperspace/memory-outbox.jsonl")
                    ti.size = len(raw)
                    ti.mtime = int(o_path.stat().st_mtime)
                    tar.addfile(ti, io.BytesIO(raw))
                    manifest["files"].append("hyperspace/memory-outbox.jsonl")

            # 4. Snapshot da Hermes HTTP Bridge (se passato)
            if hermes_client_entries:
                entries_bytes = json.dumps(hermes_client_entries, ensure_ascii=False).encode("utf-8")
                ti = tarfile.TarInfo(name="hermes/bridge_entries.json")
                ti.size = len(entries_bytes)
                ti.mtime = int(time.time())
                tar.addfile(ti, io.BytesIO(entries_bytes))
                manifest["files"].append("hermes/bridge_entries.json")
                manifest["entries_count"] = max(manifest["entries_count"], len(hermes_client_entries))

            # 5. Inserisce il manifest interno
            manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
            ti = tarfile.TarInfo(name="manifest.json")
            ti.size = len(manifest_bytes)
            ti.mtime = int(time.time())
            tar.addfile(ti, io.BytesIO(manifest_bytes))

        return buf.getvalue(), manifest

    @staticmethod
    def extract_bundle(payload_tar_gz: bytes, target_dir: Union[str, Path]) -> Dict[str, Any]:
        """Estrae in modo sicuro l'archivio tar.gz in una cartella di destinazione."""
        target_path = Path(target_dir)
        target_path.mkdir(parents=True, exist_ok=True)
        extracted_files = []

        with tarfile.open(fileobj=io.BytesIO(payload_tar_gz), mode="r:gz") as tar:
            for member in tar.getmembers():
                # Protezione contro Zip Slip / Path Traversal
                dest = (target_path / member.name).resolve()
                if not str(dest).startswith(str(target_path.resolve())):
                    continue
                if member.isfile():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    f_obj = tar.extractfile(member)
                    if f_obj:
                        dest.write_bytes(f_obj.read())
                        extracted_files.append(member.name)

        manifest_file = target_path / "manifest.json"
        manifest_data = {}
        if manifest_file.exists():
            try:
                manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        return {
            "target_dir": str(target_path),
            "extracted_files": extracted_files,
            "manifest": manifest_data,
        }


# ==============================================================================
# 3. ADATTATORI CLOUD E DECENTRALIZZATI (PLUGGABLE BACKENDS)
# ==============================================================================

class CloudStorageBackend(ABC):
    """Interfaccia astratta per un fornitore di storage cloud o decentralizzato."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def upload(self, filename: str, data: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Carica un file cifrato sul backend."""

    @abstractmethod
    def download(self, filename: str) -> bytes:
        """Scarica i byte del file cifrato."""

    @abstractmethod
    def list_snapshots(self) -> List[Dict[str, Any]]:
        """Elenca i file vault disponibili sul backend."""

    @abstractmethod
    def delete(self, filename: str) -> bool:
        """Elimina un file vault."""

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Verifica connettività, autenticazione e quota senza mutare lo stato."""


# ── 3.1 Filesystem / Local / rclone Mount ──────────────────────────────────────

class FilesystemStorageBackend(CloudStorageBackend):
    """Storage su cartella locale, share di rete, disco esterno o mount rclone (G-Drive, OneDrive)."""

    def __init__(self, base_dir: Union[str, Path], name: str = "filesystem"):
        super().__init__(name)
        self.base_dir = Path(base_dir)

    def _ensure_dir(self):
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def upload(self, filename: str, data: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._ensure_dir()
        target = self.base_dir / filename
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, target)
        return {
            "backend": self.name,
            "filename": filename,
            "size_bytes": len(data),
            "path": str(target),
            "status": "ok",
        }

    def download(self, filename: str) -> bytes:
        target = self.base_dir / filename
        if not target.exists():
            raise FileNotFoundError(f"Vault {filename} non trovato in {self.base_dir}")
        return target.read_bytes()

    def list_snapshots(self) -> List[Dict[str, Any]]:
        if not self.base_dir.exists():
            return []
        items = []
        for file in self.base_dir.glob("*.vault"):
            try:
                stat = file.stat()
                items.append({
                    "filename": file.name,
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "backend": self.name,
                })
            except OSError:
                continue
        items.sort(key=lambda x: x["filename"], reverse=True)
        return items

    def delete(self, filename: str) -> bool:
        target = self.base_dir / filename
        if target.exists():
            target.unlink()
            return True
        return False

    def health_check(self) -> Dict[str, Any]:
        try:
            self._ensure_dir()
            writable = os.access(self.base_dir, os.W_OK)
            return {
                "backend": self.name,
                "type": "filesystem",
                "path": str(self.base_dir),
                "healthy": True,
                "writable": writable,
                "snapshots_count": len(self.list_snapshots()),
            }
        except Exception as exc:
            return {
                "backend": self.name,
                "type": "filesystem",
                "healthy": False,
                "error": str(exc),
            }


# ── 3.2 S3-Compatible Storage (Cloudflare R2, Backblaze B2, AWS, MinIO) ────────

def _sigv4_sign_headers(
    method: str,
    url: str,
    payload_bytes: bytes,
    access_key: str,
    secret_key: str,
    region: str = "auto",
    service: str = "s3",
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Firma una richiesta HTTP secondo lo standard AWS Signature Version 4.

    Implementazione autonoma in puro standard Python, zero dipendenze esterne.
    """
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    parsed = urlparse(url)
    host = parsed.netloc
    canonical_uri = parsed.path or "/"

    payload_hash = hashlib.sha256(payload_bytes).hexdigest()

    headers = {
        "host": host,
        "x-amz-date": amz_date,
        "x-amz-content-sha256": payload_hash,
    }
    if extra_headers:
        for k, v in extra_headers.items():
            headers[k.lower()] = v.strip()

    # Intestazioni canoniche ordinate
    sorted_header_keys = sorted(headers.keys())
    canonical_headers = "".join(f"{k}:{headers[k]}\n" for k in sorted_header_keys)
    signed_headers = ";".join(sorted_header_keys)

    canonical_query = parsed.query or ""

    canonical_request = f"{method}\n{canonical_uri}\n{canonical_query}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"

    def sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    k_date = sign(f"AWS4{secret_key}".encode("utf-8"), date_stamp)
    k_region = sign(k_date, region)
    k_service = sign(k_region, service)
    k_signing = sign(k_service, "aws4_request")

    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    auth_header = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    result_headers = dict(headers)
    result_headers["Authorization"] = auth_header
    return result_headers


class S3StorageBackend(CloudStorageBackend):
    """Storage compatibile S3: Cloudflare R2, Backblaze B2, AWS S3, MinIO, Wasabi."""

    def __init__(
        self,
        endpoint_url: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = "auto",
        prefix: str = "hermes-vault/",
        name: str = "s3",
    ):
        super().__init__(name)
        self.endpoint_url = endpoint_url.rstrip("/")
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region or "auto"
        self.prefix = prefix.lstrip("/")

    def _url_for(self, key: str) -> str:
        clean_key = quote(f"{self.prefix}{key}".lstrip("/"), safe="/-_.~")
        return f"{self.endpoint_url}/{self.bucket}/{clean_key}"

    def upload(self, filename: str, data: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = self._url_for(filename)
        headers = _sigv4_sign_headers(
            "PUT", url, data, self.access_key, self.secret_key, self.region,
            extra_headers={"content-type": "application/octet-stream"}
        )
        resp = requests.put(url, data=data, headers=headers, timeout=30)
        resp.raise_for_status()
        return {
            "backend": self.name,
            "filename": filename,
            "bucket": self.bucket,
            "size_bytes": len(data),
            "status": "ok",
        }

    def download(self, filename: str) -> bytes:
        url = self._url_for(filename)
        headers = _sigv4_sign_headers("GET", url, b"", self.access_key, self.secret_key, self.region)
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.content

    def list_snapshots(self) -> List[Dict[str, Any]]:
        query = f"list-type=2&prefix={quote(self.prefix)}"
        url = f"{self.endpoint_url}/{self.bucket}?{query}"
        headers = _sigv4_sign_headers("GET", url, b"", self.access_key, self.secret_key, self.region)
        resp = requests.get(url, headers=headers, timeout=15)
        if not resp.ok:
            return []
        items = []
        try:
            root = ET.fromstring(resp.content)
            # Namespace handling
            ns = {"s3": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}
            find_str = "s3:Contents" if ns else "Contents"
            for content in root.findall(find_str, ns):
                key_el = content.find("s3:Key" if ns else "Key", ns)
                size_el = content.find("s3:Size" if ns else "Size", ns)
                mtime_el = content.find("s3:LastModified" if ns else "LastModified", ns)
                if key_el is not None and key_el.text:
                    key = key_el.text
                    fname = key[len(self.prefix):] if key.startswith(self.prefix) else key
                    if fname.endswith(".vault"):
                        items.append({
                            "filename": fname,
                            "size_bytes": int(size_el.text) if size_el is not None and size_el.text else 0,
                            "modified_at": mtime_el.text if mtime_el is not None else "",
                            "backend": self.name,
                        })
        except Exception:
            pass
        items.sort(key=lambda x: x["filename"], reverse=True)
        return items

    def delete(self, filename: str) -> bool:
        url = self._url_for(filename)
        headers = _sigv4_sign_headers("DELETE", url, b"", self.access_key, self.secret_key, self.region)
        resp = requests.delete(url, headers=headers, timeout=15)
        return resp.status_code in (200, 204)

    def health_check(self) -> Dict[str, Any]:
        try:
            snapshots = self.list_snapshots()
            return {
                "backend": self.name,
                "type": "s3_compatible",
                "bucket": self.bucket,
                "healthy": True,
                "snapshots_count": len(snapshots),
            }
        except Exception as exc:
            return {
                "backend": self.name,
                "type": "s3_compatible",
                "bucket": self.bucket,
                "healthy": False,
                "error": str(exc),
            }


# ── 3.3 WebDAV Storage (Nextcloud, ownCloud, pCloud, Koofr) ────────────────────

class WebDAVStorageBackend(CloudStorageBackend):
    """Storage WebDAV: compatibile con Nextcloud, ownCloud, pCloud, Koofr, ecc."""

    def __init__(
        self,
        base_url: str,
        username: str = "",
        password: str = "",
        remote_path: str = "/hermes-vault/",
        name: str = "webdav",
    ):
        super().__init__(name)
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.remote_path = f"/{remote_path.strip('/')}/"

    def _auth(self) -> Optional[Tuple[str, str]]:
        if self.username or self.password:
            return (self.username, self.password)
        return None

    def _url_for(self, filename: str = "") -> str:
        if filename:
            return f"{self.base_url}{self.remote_path}{quote(filename)}"
        return f"{self.base_url}{self.remote_path}"

    def upload(self, filename: str, data: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Assicura la cartella
        try:
            requests.request("MKCOL", self._url_for(), auth=self._auth(), timeout=10)
        except Exception:
            pass
        url = self._url_for(filename)
        resp = requests.put(url, data=data, auth=self._auth(), timeout=30)
        resp.raise_for_status()
        return {
            "backend": self.name,
            "filename": filename,
            "size_bytes": len(data),
            "status": "ok",
        }

    def download(self, filename: str) -> bytes:
        url = self._url_for(filename)
        resp = requests.get(url, auth=self._auth(), timeout=30)
        resp.raise_for_status()
        return resp.content

    def list_snapshots(self) -> List[Dict[str, Any]]:
        headers = {"Depth": "1"}
        resp = requests.request("PROPFIND", self._url_for(), auth=self._auth(), headers=headers, timeout=15)
        if not resp.ok:
            return []
        items = []
        try:
            root = ET.fromstring(resp.content)
            for response in root.findall(".//{DAV:}response"):
                href_el = response.find("{DAV:}href")
                if href_el is not None and href_el.text:
                    href = href_el.text
                    fname = Path(href).name
                    if fname.endswith(".vault"):
                        size_el = response.find(".//{DAV:}getcontentlength")
                        items.append({
                            "filename": fname,
                            "size_bytes": int(size_el.text) if size_el is not None and size_el.text else 0,
                            "backend": self.name,
                        })
        except Exception:
            pass
        items.sort(key=lambda x: x["filename"], reverse=True)
        return items

    def delete(self, filename: str) -> bool:
        url = self._url_for(filename)
        resp = requests.delete(url, auth=self._auth(), timeout=15)
        return resp.status_code in (200, 204)

    def health_check(self) -> Dict[str, Any]:
        try:
            snaps = self.list_snapshots()
            return {
                "backend": self.name,
                "type": "webdav",
                "healthy": True,
                "snapshots_count": len(snaps),
            }
        except Exception as exc:
            return {
                "backend": self.name,
                "type": "webdav",
                "healthy": False,
                "error": str(exc),
            }


# ── 3.4 GitHub Gist / Repo Storage (Decentralizzazione Git Gratuita) ──────────

class GitHubStorageBackend(CloudStorageBackend):
    """Storage su GitHub Gist privato o repository releases (gratuito e decentralizzato)."""

    def __init__(
        self,
        token: str,
        gist_id: Optional[str] = None,
        name: str = "github",
    ):
        super().__init__(name)
        self.token = token
        self.gist_id = gist_id

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def upload(self, filename: str, data: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        b64_content = base64.b64encode(data).decode("ascii")
        # Memorizza su Gist come file base64
        payload = {
            "description": "HyperSpace Hermes Encrypted Vault",
            "public": False,
            "files": {
                filename: {"content": b64_content}
            }
        }
        if self.gist_id:
            url = f"https://api.github.com/gists/{self.gist_id}"
            resp = requests.patch(url, headers=self._headers(), json=payload, timeout=25)
        else:
            url = "https://api.github.com/gists"
            resp = requests.post(url, headers=self._headers(), json=payload, timeout=25)
            if resp.ok:
                self.gist_id = resp.json().get("id")

        resp.raise_for_status()
        return {
            "backend": self.name,
            "filename": filename,
            "gist_id": self.gist_id,
            "size_bytes": len(data),
            "status": "ok",
        }

    def download(self, filename: str) -> bytes:
        if not self.gist_id:
            raise FileNotFoundError("Nessun Gist ID configurato.")
        url = f"https://api.github.com/gists/{self.gist_id}"
        resp = requests.get(url, headers=self._headers(), timeout=20)
        resp.raise_for_status()
        files = resp.json().get("files", {})
        if filename not in files:
            raise FileNotFoundError(f"File {filename} non presente nel Gist.")
        file_obj = files[filename]
        raw_b64 = file_obj.get("content")
        if not raw_b64 and file_obj.get("raw_url"):
            raw_b64 = requests.get(file_obj["raw_url"], headers=self._headers(), timeout=20).text
        return base64.b64decode(raw_b64)

    def list_snapshots(self) -> List[Dict[str, Any]]:
        if not self.gist_id:
            return []
        url = f"https://api.github.com/gists/{self.gist_id}"
        resp = requests.get(url, headers=self._headers(), timeout=15)
        if not resp.ok:
            return []
        files = resp.json().get("files", {})
        items = []
        for fname, fmeta in files.items():
            if fname.endswith(".vault"):
                items.append({
                    "filename": fname,
                    "size_bytes": fmeta.get("size", 0),
                    "backend": self.name,
                    "gist_id": self.gist_id,
                })
        items.sort(key=lambda x: x["filename"], reverse=True)
        return items

    def delete(self, filename: str) -> bool:
        if not self.gist_id:
            return False
        url = f"https://api.github.com/gists/{self.gist_id}"
        payload = {"files": {filename: None}}
        resp = requests.patch(url, headers=self._headers(), json=payload, timeout=15)
        return resp.ok

    def health_check(self) -> Dict[str, Any]:
        try:
            url = "https://api.github.com/user"
            resp = requests.get(url, headers=self._headers(), timeout=10)
            return {
                "backend": self.name,
                "type": "github_gist",
                "healthy": resp.ok,
                "user": resp.json().get("login") if resp.ok else "",
                "gist_id": self.gist_id or "",
            }
        except Exception as exc:
            return {
                "backend": self.name,
                "type": "github_gist",
                "healthy": False,
                "error": str(exc),
            }


# ── 3.5 IPFS / Pinata Storage (Decentralizzazione Web3 Content-Addressable) ───

class IPFSStorageBackend(CloudStorageBackend):
    """Storage decentralizzato P2P IPFS: nodo locale (Kubo) o Pinata pinning."""

    def __init__(
        self,
        api_url: str = "http://127.0.0.1:5001",
        pinata_jwt: Optional[str] = None,
        gateway_url: str = "https://ipfs.io/ipfs/",
        name: str = "ipfs",
    ):
        super().__init__(name)
        self.api_url = api_url.rstrip("/")
        self.pinata_jwt = pinata_jwt or os.getenv("PINATA_JWT") or ""
        self.gateway_url = gateway_url.rstrip("/")
        # Indice locale delle CIDs associate ai nomi snapshot
        self._index: Dict[str, str] = {}

    def upload(self, filename: str, data: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        cid = ""
        if self.pinata_jwt:
            # Upload su Pinata
            url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
            headers = {"Authorization": f"Bearer {self.pinata_jwt}"}
            files = {"file": (filename, data, "application/octet-stream")}
            resp = requests.post(url, headers=headers, files=files, timeout=40)
            resp.raise_for_status()
            cid = resp.json().get("IpfsHash", "")
        else:
            # Upload su daemon IPFS locale (API RPC /api/v0/add)
            url = f"{self.api_url}/api/v0/add"
            files = {"file": (filename, data)}
            resp = requests.post(url, files=files, timeout=30)
            resp.raise_for_status()
            cid = resp.json().get("Hash", "")

        if not cid:
            raise RuntimeError("IPFS non ha restituito alcun CID.")

        self._index[filename] = cid
        return {
            "backend": self.name,
            "filename": filename,
            "cid": cid,
            "gateway_url": f"{self.gateway_url}/{cid}",
            "size_bytes": len(data),
            "status": "ok",
        }

    def download(self, filename: str) -> bytes:
        cid = self._index.get(filename)
        if not cid:
            # Se il filename è già un CID
            if filename.startswith("Qm") or filename.startswith("bafy"):
                cid = filename
            else:
                raise FileNotFoundError(f"CID IPFS sconosciuto per {filename}")

        if not self.pinata_jwt and self.api_url:
            try:
                # Prova via API locale /api/v0/cat?arg=CID
                resp = requests.post(f"{self.api_url}/api/v0/cat", params={"arg": cid}, timeout=30)
                if resp.ok:
                    return resp.content
            except Exception:
                pass

        # Fallback via gateway HTTP IPFS
        gw_url = f"{self.gateway_url}/{cid}"
        resp = requests.get(gw_url, timeout=30)
        resp.raise_for_status()
        return resp.content

    def list_snapshots(self) -> List[Dict[str, Any]]:
        items = []
        for fname, cid in self._index.items():
            items.append({
                "filename": fname,
                "cid": cid,
                "backend": self.name,
            })
        return items

    def delete(self, filename: str) -> bool:
        cid = self._index.pop(filename, None)
        if not cid:
            return False
        if self.pinata_jwt:
            try:
                requests.delete(f"https://api.pinata.cloud/pinning/unpin/{cid}",
                                headers={"Authorization": f"Bearer {self.pinata_jwt}"}, timeout=10)
            except Exception:
                pass
        return True

    def health_check(self) -> Dict[str, Any]:
        if self.pinata_jwt:
            try:
                resp = requests.get("https://api.pinata.cloud/data/testAuthentication",
                                    headers={"Authorization": f"Bearer {self.pinata_jwt}"}, timeout=10)
                return {"backend": self.name, "type": "pinata", "healthy": resp.ok}
            except Exception as exc:
                return {"backend": self.name, "type": "pinata", "healthy": False, "error": str(exc)}
        else:
            try:
                resp = requests.post(f"{self.api_url}/api/v0/version", timeout=5)
                return {"backend": self.name, "type": "ipfs_node", "healthy": resp.ok, "version": resp.json().get("Version", "") if resp.ok else ""}
            except Exception as exc:
                return {"backend": self.name, "type": "ipfs_node", "healthy": False, "error": str(exc)}


# ==============================================================================
# 4. COORDINATORE MULTI-CLOUD VAULT (ORCHESTRATORE DI RESILIENZA)
# ==============================================================================

class HermesMultiCloudVault:
    """Orchestratore principale per la resilienza multi-cloud della memoria Hermes."""

    def __init__(
        self,
        cipher: Optional[HermesVaultCipher] = None,
        backends: Optional[List[CloudStorageBackend]] = None,
        retention_count: int = DEFAULT_RETENTION,
    ):
        self.cipher = cipher or HermesVaultCipher()
        self.backends: List[CloudStorageBackend] = backends or []
        self.retention_count = max(1, retention_count)

    @classmethod
    def from_env(cls) -> HermesMultiCloudVault:
        """Inizializza l'orchestratore configurando i provider dalle variabili d'ambiente."""
        cipher = HermesVaultCipher()
        backends: List[CloudStorageBackend] = []

        # 1. Backend Filesystem / Locale / Mount
        local_dir = os.getenv("HERMES_VAULT_LOCAL_DIR", "").strip()
        if local_dir:
            backends.append(FilesystemStorageBackend(local_dir, name="local_vault"))
        else:
            # Default directory locale nel repo se non specificato
            default_backup = Path("data/vault_backups")
            backends.append(FilesystemStorageBackend(default_backup, name="local_default"))

        # 2. Backend S3 / Cloudflare R2 / Backblaze B2
        s3_endpoint = os.getenv("HERMES_VAULT_S3_ENDPOINT", "").strip()
        s3_bucket = os.getenv("HERMES_VAULT_S3_BUCKET", "").strip()
        s3_key = os.getenv("HERMES_VAULT_S3_KEY", "").strip()
        s3_secret = os.getenv("HERMES_VAULT_S3_SECRET", "").strip()
        if s3_endpoint and s3_bucket and s3_key and s3_secret:
            backends.append(S3StorageBackend(
                endpoint_url=s3_endpoint,
                bucket=s3_bucket,
                access_key=s3_key,
                secret_key=s3_secret,
                region=os.getenv("HERMES_VAULT_S3_REGION", "auto"),
                prefix=os.getenv("HERMES_VAULT_S3_PREFIX", "hermes-vault/"),
                name="cloud_s3",
            ))

        # 3. Backend WebDAV (Nextcloud / ownCloud)
        webdav_url = os.getenv("HERMES_VAULT_WEBDAV_URL", "").strip()
        if webdav_url:
            backends.append(WebDAVStorageBackend(
                base_url=webdav_url,
                username=os.getenv("HERMES_VAULT_WEBDAV_USER", ""),
                password=os.getenv("HERMES_VAULT_WEBDAV_PASS", ""),
                remote_path=os.getenv("HERMES_VAULT_WEBDAV_PATH", "/hermes-vault/"),
                name="cloud_webdav",
            ))

        # 4. Backend GitHub Gist
        github_token = os.getenv("HERMES_VAULT_GITHUB_TOKEN", "").strip()
        if github_token:
            backends.append(GitHubStorageBackend(
                token=github_token,
                gist_id=os.getenv("HERMES_VAULT_GITHUB_GIST_ID", ""),
                name="cloud_github",
            ))

        # 5. Backend IPFS
        ipfs_api = os.getenv("HERMES_VAULT_IPFS_API", "").strip()
        pinata_jwt = os.getenv("HERMES_VAULT_PINATA_JWT", "").strip()
        if ipfs_api or pinata_jwt:
            backends.append(IPFSStorageBackend(
                api_url=ipfs_api or "http://127.0.0.1:5001",
                pinata_jwt=pinata_jwt,
                name="p2p_ipfs",
            ))

        retention = int(os.getenv("HERMES_VAULT_RETENTION_COUNT", str(DEFAULT_RETENTION)))
        return cls(cipher=cipher, backends=backends, retention_count=retention)

    def add_backend(self, backend: CloudStorageBackend) -> None:
        self.backends.append(backend)

    def create_and_push_snapshot(
        self,
        hermes_dir: Optional[Union[str, Path]] = None,
        memory_mirror_file: Optional[Union[str, Path]] = None,
        memory_outbox_file: Optional[Union[str, Path]] = None,
        hermes_client_entries: Optional[List[Dict[str, Any]]] = None,
        tag: str = "auto",
    ) -> Dict[str, Any]:
        """Esegue lo snapshot completo, cifra il vault e lo propaga a tutti i provider configurati."""
        if not self.cipher.is_configured():
            raise HermesCryptoError(
                "Impossibile creare snapshot: passphrase/chiave di cifratura non configurata."
            )

        now = datetime.now(timezone.utc)
        now_str = now.strftime("%Y%m%d-%H%M%S-%f")
        snapshot_id = f"hermes-snap-{now_str}-{os.urandom(4).hex()}"
        vault_filename = f"{snapshot_id}.vault"

        # 1. Assembla il bundle tar.gz
        extra_meta = {"tag": tag, "created_by": "HermesMultiCloudVault"}
        tar_gz_bytes, manifest = HermesSnapshotBundle.create_bundle(
            hermes_dir=hermes_dir,
            memory_mirror_file=memory_mirror_file,
            memory_outbox_file=memory_outbox_file,
            hermes_client_entries=hermes_client_entries,
            extra_metadata=extra_meta,
        )

        meta = {
            "snapshot_id": snapshot_id,
            "entries_count": manifest.get("entries_count", 0),
            "files": manifest.get("files", []),
            "tag": tag,
        }

        # 2. Cifra client-side il bundle
        vault_bytes = self.cipher.encrypt_vault(tar_gz_bytes, metadata=meta)

        # 3. Fan-out su tutti i backend disponibili
        results: Dict[str, Any] = {}
        successful_backends = []
        for backend in self.backends:
            try:
                res = backend.upload(vault_filename, vault_bytes, metadata=meta)
                results[backend.name] = {"ok": True, "details": res}
                successful_backends.append(backend.name)
            except Exception as exc:
                results[backend.name] = {"ok": False, "error": str(exc)}

        # 4. Pruning automatico delle versioni più vecchie
        pruned = self.prune_all(keep=self.retention_count)

        return {
            "ok": len(successful_backends) > 0,
            "snapshot_id": snapshot_id,
            "filename": vault_filename,
            "ciphertext_bytes": len(vault_bytes),
            "unencrypted_bytes": len(tar_gz_bytes),
            "entries_count": manifest.get("entries_count", 0),
            "targets_succeeded": successful_backends,
            "targets_results": results,
            "pruned": pruned,
        }

    def pull_and_decrypt_snapshot(
        self,
        snapshot_id_or_filename: Optional[str] = None,
        preferred_backend: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], bytes]:
        """Scarica e decifra uno snapshot provando i backend configurati con fallback trasparente."""
        filename = snapshot_id_or_filename
        if not filename:
            # Trova l'ultimo snapshot disponibile
            all_snaps = self.list_all_snapshots()
            if not all_snaps:
                raise FileNotFoundError("Nessuno snapshot disponibile sui backend configurati.")
            filename = all_snaps[0]["filename"]

        if not filename.endswith(".vault"):
            filename = f"{filename}.vault"

        # Ordina i backend mettendo quello preferito per primo
        ordered_backends = sorted(
            self.backends,
            key=lambda b: 0 if preferred_backend and b.name == preferred_backend else 1
        )

        last_error = ""
        vault_data = None
        source_backend = ""

        for backend in ordered_backends:
            try:
                vault_data = backend.download(filename)
                source_backend = backend.name
                break
            except Exception as exc:
                last_error = str(exc)
                continue

        if vault_data is None:
            raise FileNotFoundError(
                f"Impossibile scaricare {filename} da alcun backend configurato. Ultimo errore: {last_error}"
            )

        header, payload = self.cipher.decrypt_vault(vault_data)
        header["source_backend"] = source_backend
        return header, payload

    def restore_to_directory(
        self,
        target_dir: Union[str, Path],
        snapshot_id_or_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Scarica, decifra ed estrae completamente uno snapshot in una cartella."""
        header, payload = self.pull_and_decrypt_snapshot(snapshot_id_or_filename)
        extraction = HermesSnapshotBundle.extract_bundle(payload, target_dir)
        return {
            "ok": True,
            "snapshot_id": header.get("snapshot_id"),
            "source_backend": header.get("source_backend"),
            "header": header,
            "extraction": extraction,
        }

    def list_all_snapshots(self) -> List[Dict[str, Any]]:
        """Restituisce la lista deduplicata di tutti gli snapshot visibili sui provider."""
        all_items: Dict[str, Dict[str, Any]] = {}
        for backend in self.backends:
            try:
                for item in backend.list_snapshots():
                    fname = item["filename"]
                    if fname not in all_items:
                        all_items[fname] = {
                            "filename": fname,
                            "snapshot_id": fname.replace(".vault", ""),
                            "size_bytes": item.get("size_bytes", 0),
                            "modified_at": item.get("modified_at", ""),
                            "available_on": [backend.name],
                        }
                    else:
                        all_items[fname]["available_on"].append(backend.name)
            except Exception:
                continue
        sorted_list = sorted(all_items.values(), key=lambda x: x["filename"], reverse=True)
        return sorted_list

    def prune_all(self, keep: int = DEFAULT_RETENTION) -> Dict[str, int]:
        """Elimina gli snapshot più vecchi oltre la soglia di retention su tutti i provider."""
        snapshots = self.list_all_snapshots()
        if len(snapshots) <= keep:
            return {b.name: 0 for b in self.backends}

        to_prune = snapshots[keep:]
        pruned_counts: Dict[str, int] = {b.name: 0 for b in self.backends}

        for snap in to_prune:
            fname = snap["filename"]
            for backend in self.backends:
                try:
                    if backend.delete(fname):
                        pruned_counts[backend.name] += 1
                except Exception:
                    continue

        return pruned_counts

    def verify_all_remotes(self) -> Dict[str, Any]:
        """Verifica la salute e raggiungibilità di ciascun backend e testa la crittografia."""
        health_results: Dict[str, Any] = {}
        for backend in self.backends:
            health_results[backend.name] = backend.health_check()

        # Verifica crittografia
        crypto_status = {
            "configured": self.cipher.is_configured(),
            "library_available": _HAS_CRYPTO,
            "algorithm": "AES-256-GCM",
        }

        # Verifica round-trip sull'ultimo snapshot esistente (se presente)
        snaps = self.list_all_snapshots()
        verification_roundtrip = {"tested": False}
        if snaps and self.cipher.is_configured():
            latest = snaps[0]["filename"]
            try:
                hdr, payload = self.pull_and_decrypt_snapshot(latest)
                verification_roundtrip = {
                    "tested": True,
                    "ok": True,
                    "verified_snapshot": latest,
                    "entries_count": hdr.get("metadata", {}).get("entries_count", 0),
                    "unencrypted_bytes": len(payload),
                }
            except Exception as exc:
                verification_roundtrip = {
                    "tested": True,
                    "ok": False,
                    "verified_snapshot": latest,
                    "error": str(exc),
                }

        return {
            "status": "healthy" if any(r.get("healthy") for r in health_results.values()) else "degraded",
            "backends": health_results,
            "crypto": crypto_status,
            "verification": verification_roundtrip,
            "total_snapshots": len(snaps),
        }
