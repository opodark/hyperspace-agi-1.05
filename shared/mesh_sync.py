# SPDX-License-Identifier: Apache-2.0
# shared/mesh_sync.py
# HyperSpace AGI — Sovereign P2P Mesh Code & Artifact Distribution Engine
#
# Permette la distribuzione, sincronizzazione e applicazione atomica di codice,
# patch Git e Knowledge Graph tra i nodi della mesh senza passare da GitHub,
# proteggendo ogni transazione tramite il canale crittografico E2EE (ECDH + AES-256-GCM + ECDSA).

import base64
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fnmatch
import requests

from shared.crypto_channel import (
    CryptoChannelError,
    decrypt_envelope,
    encrypt_envelope,
    pubkey_from_hex,
)
from shared.identity import sign_message, verify_message
from shared.node_telemetry import get_codebase_status


# ── MATRICE RBAC E AMBITI DI SCRITTURA PER RUOLO ──────────────────────────────

ROLE_WRITE_SCOPES: Dict[str, List[str]] = {
    "authority": ["*"],
    "hub": ["*"],
    "root": ["*"],
    "worker-gpu": [
        "integrations/comfyui/**",
        "worker/**",
        "node/**",
        "shared/image_jobs.py",
        "scripts/reel_*.py",
        "scripts/mesh_node_deploy.ps1",
        "tests/test_comfyui*.py",
        "tests/test_image_jobs.py",
        "tests/fixtures/immagini*.json",
        "docs/comfyui.md",
        "docs/windows-node-handoff.md",
    ],
    "worker-leaf": [
        "worker/**",
        "node/**",
        "shared/power_sense.py",
        "shared/mobile_gate.py",
        "tests/test_node*.py",
        "tests/test_mesh*.py",
    ],
    "worker-cpu": [
        "worker/**",
        "node/**",
        "shared/power_sense.py",
        "shared/mobile_gate.py",
        "tests/test_node*.py",
        "tests/test_mesh*.py",
    ],
    "leaf": [
        "worker/**",
        "node/**",
        "shared/power_sense.py",
        "shared/mobile_gate.py",
        "tests/test_node*.py",
        "tests/test_mesh*.py",
    ],
    # Telefono Android in Termux (NODE_TIER=mobile): come un leaf, più il
    # gate di lavoro e il proprio comando di gestione.
    "mobile": [
        "node/**",
        "shared/power_sense.py",
        "shared/mobile_gate.py",
        "scripts/android/**",
        "tests/test_mobile_gate.py",
    ],
    "edge-web": [
        "web-node/**",
        "chat.html",
        "presentation_assets/**",
    ],
}

STRICT_FORBIDDEN_PATTERNS: List[str] = [
    "shared/identity.py",
    "shared/crypto_channel.py",
    "control-plane/**",
    "authority/**",
    "AGENTS.md",
    "docs/licensing.md",
    ".env*",
    "*.pem",
    "*.key",
    "data/persona-*.json",
]


def extract_modified_files_from_diff(diff_text: str) -> List[str]:
    """Estrae l'elenco dei percorsi relativi dei file modificati da una diff unificata Git."""
    files = set()
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                path_b = parts[3]
                if path_b.startswith("b/"):
                    path_b = path_b[2:]
                files.add(path_b)
        elif line.startswith("+++ b/"):
            files.add(line[6:].strip())
        elif line.startswith("--- a/") and not line.startswith("--- a/dev/null"):
            files.add(line[6:].strip())
    return sorted(list(files))


def extract_modified_files_from_payload(payload: Dict[str, Any]) -> List[str]:
    """Raccoglie tutti i file modificati (diff git + file diretti + manifest) da un payload di patch."""
    files = set()
    direct_files = payload.get("direct_files", {})
    files.update(direct_files.keys())

    diff_b64 = payload.get("patch_diff_gz_b64", "")
    if diff_b64:
        try:
            diff_text = gzip.decompress(base64.b64decode(diff_b64)).decode("utf-8", errors="replace")
            files.update(extract_modified_files_from_diff(diff_text))
        except Exception:
            pass

    scope_manifest = payload.get("scope_manifest", [])
    if isinstance(scope_manifest, list):
        files.update(scope_manifest)

    return sorted(list(files))


def verify_patch_rbac(
    origin_role: str,
    modified_files: List[str],
) -> Tuple[bool, List[str]]:
    """Verifica se il ruolo mittente ha i privilegi necessari per modificare i file indicati.

    Restituisce una tupla: (consentito: bool, violazioni: List[str]).
    """
    role = (origin_role or "").lower().strip()
    if role in ("authority", "hub", "root"):
        return True, []

    violations = []
    allowed_patterns = ROLE_WRITE_SCOPES.get(role, [])

    for f_path in modified_files:
        norm_path = f_path.replace("\\", "/").lstrip("/")

        # 1. Controllo rigido file protetti
        is_forbidden = any(fnmatch.fnmatch(norm_path, pat) for pat in STRICT_FORBIDDEN_PATTERNS)
        if is_forbidden:
            violations.append(f"{norm_path} (file core/identità protetto)")
            continue

        # 2. Controllo allowlist per il ruolo
        is_allowed = any(fnmatch.fnmatch(norm_path, pat) for pat in allowed_patterns)
        if not is_allowed:
            violations.append(f"{norm_path} (fuori dall'ambito consentito per ruolo '{role}')")

    return len(violations) == 0, violations


# ── 1. CREAZIONE PATCH & BUNDLE ──────────────────────────────────────────────

def create_git_patch_payload(
    base_commit: str = "HEAD~1",
    target_commit: str = "HEAD",
    repo_dir: Optional[str] = None,
    include_files: Optional[List[str]] = None,
    origin_role: str = "authority",
    origin_node_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Genera un pacchetto di aggiornamento contenente diff git unificata e metadati.

    Se sono specificati file singoli in include_files, li pacchettizza direttamente
    (utile per file untracked o configurazioni al di fuori dell'albero git formattato).
    """
    root = Path(repo_dir) if repo_dir else Path(".")
    git_bin = shutil.which("git")

    payload: Dict[str, Any] = {
        "type": "git_patch",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "base_commit": base_commit,
        "target_commit": target_commit,
        "patch_diff_gz_b64": "",
        "direct_files": {},
        "commit_metadata": {},
    }

    if git_bin and (root / ".git").exists():
        try:
            # Metadata commit target
            p_meta = subprocess.run(
                [git_bin, "-C", str(root), "log", "-1", target_commit, "--format=%H|%an|%cI|%s"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
            )
            if p_meta.returncode == 0 and "|" in p_meta.stdout:
                parts = p_meta.stdout.strip().split("|", 3)
                payload["commit_metadata"] = {
                    "sha": parts[0],
                    "short_sha": parts[0][:8],
                    "author": parts[1],
                    "date": parts[2],
                    "subject": parts[3] if len(parts) > 3 else "",
                }

            # Git format-patch / diff tra base e target
            p_diff = subprocess.run(
                [git_bin, "-C", str(root), "diff", f"{base_commit}..{target_commit}"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
            )
            if p_diff.returncode == 0 and p_diff.stdout.strip():
                diff_bytes = p_diff.stdout.encode("utf-8")
                compressed = gzip.compress(diff_bytes)
                payload["patch_diff_gz_b64"] = base64.b64encode(compressed).decode("ascii")
        except Exception as e:
            payload["git_error"] = str(e)

    # Inclusione diretta file specificati
    if include_files:
        for rel_path in include_files:
            file_path = root / rel_path
            if file_path.exists() and file_path.is_file():
                try:
                    content = file_path.read_bytes()
                    payload["direct_files"][rel_path] = {
                        "content_gz_b64": base64.b64encode(gzip.compress(content)).decode("ascii"),
                        "size": len(content),
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                except Exception:
                    pass

    payload["origin"] = {
        "role": origin_role,
        "node_id": origin_node_id or "",
    }
    payload["scope_manifest"] = extract_modified_files_from_payload(payload)

    return payload


def create_graphify_bundle_payload(repo_dir: Optional[str] = None) -> Dict[str, Any]:
    """Pacchettizza il grafo compilato di Graphify (graph.json e .graphify_analysis.json).

    Permette ai nodi edge/leaf di ricevere il Knowledge Graph già clusterizzato
    senza dover installare tool di graph analysis o allocare memoria per il clustering.
    """
    root = Path(repo_dir) if repo_dir else Path(".")
    graph_dir = root / "graphify-out"
    graph_json = graph_dir / "graph.json"
    analysis_json = graph_dir / ".graphify_analysis.json"

    bundle: Dict[str, Any] = {
        "type": "graphify_sync",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": {},
    }

    for f_path, label in [(graph_json, "graph.json"), (analysis_json, ".graphify_analysis.json")]:
        if f_path.exists():
            content = f_path.read_bytes()
            compressed = gzip.compress(content)
            bundle["files"][label] = {
                "content_gz_b64": base64.b64encode(compressed).decode("ascii"),
                "raw_size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }

    return bundle


# ── 2. APPLICAZIONE ATOMICA SUL NODO RICEVENTE ───────────────────────────────

def apply_mesh_update(
    update_payload: Dict[str, Any],
    repo_dir: Optional[str] = None,
    backup: bool = True,
    enforce_rbac: bool = True,
) -> Dict[str, Any]:
    """Riceve ed applica atomica una patch di codice o artefatto Graphify.

    Se applicato con successo restituisce lo stato aggiornato del codebase.
    In caso di errore ripristina lo stato precedente e restituisce il dettaglio.
    """
    root = Path(repo_dir) if repo_dir else Path(".")
    update_type = update_payload.get("type", "unknown")
    result: Dict[str, Any] = {
        "success": False,
        "type": update_type,
        "applied_files": [],
        "errors": [],
    }

    # 0. Verifica RBAC se presente origin
    origin_info = update_payload.get("origin", {})
    origin_role = origin_info.get("role") if isinstance(origin_info, dict) else update_payload.get("origin_role")
    if enforce_rbac and origin_role:
        modified_files = extract_modified_files_from_payload(update_payload)
        allowed, violations = verify_patch_rbac(origin_role, modified_files)
        if not allowed:
            result["errors"].append(
                f"RBAC Scope Violation per ruolo '{origin_role}': {', '.join(violations)}"
            )
            result["success"] = False
            result["codebase"] = get_codebase_status(str(root))
            return result

    # 1. Applicazione file diretti
    direct_files = update_payload.get("direct_files", {})
    backups: Dict[Path, Optional[bytes]] = {}

    try:
        for rel_path, f_info in direct_files.items():
            dest = root / rel_path
            # Salva backup per rollback atomico
            if backup:
                backups[dest] = dest.read_bytes() if dest.exists() else None

            dest.parent.mkdir(parents=True, exist_ok=True)
            raw_bytes = gzip.decompress(base64.b64decode(f_info["content_gz_b64"]))

            # Verifica checksum di integrità
            if hashlib.sha256(raw_bytes).hexdigest() != f_info["sha256"]:
                raise ValueError(f"Checksum errato per file {rel_path}")

            dest.write_bytes(raw_bytes)
            result["applied_files"].append(rel_path)

        # 2. Applicazione diff git se presente
        diff_b64 = update_payload.get("patch_diff_gz_b64", "")
        if diff_b64:
            diff_text = gzip.decompress(base64.b64decode(diff_b64)).decode("utf-8")
            git_bin = shutil.which("git")
            if git_bin and (root / ".git").exists():
                p_apply = subprocess.run(
                    [git_bin, "-C", str(root), "apply", "--whitespace=nowarn", "-"],
                    input=diff_text, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                )
                if p_apply.returncode != 0:
                    result["errors"].append(f"Git apply fallito: {p_apply.stderr.strip()}")
                else:
                    result["git_applied"] = True

        # 3. Applicazione bundle Graphify
        if update_type == "graphify_sync":
            graph_files = update_payload.get("files", {})
            graph_out_dir = root / "graphify-out"
            graph_out_dir.mkdir(parents=True, exist_ok=True)

            for label, f_info in graph_files.items():
                dest = graph_out_dir / label
                raw_bytes = gzip.decompress(base64.b64decode(f_info["content_gz_b64"]))
                if hashlib.sha256(raw_bytes).hexdigest() != f_info["sha256"]:
                    raise ValueError(f"Checksum non valido per {label}")
                dest.write_bytes(raw_bytes)
                result["applied_files"].append(f"graphify-out/{label}")

        result["success"] = len(result["errors"]) == 0
    except Exception as e:
        result["errors"].append(str(e))
        result["success"] = False

        # Rollback atomico dei file scritti
        if backup and backups:
            for dest_path, original_content in backups.items():
                try:
                    if original_content is None:
                        if dest_path.exists():
                            dest_path.unlink()
                    else:
                        dest_path.write_bytes(original_content)
                except Exception:
                    pass
            result["rollback_applied"] = True

    result["codebase"] = get_codebase_status(str(root))
    return result


# ── 3. DISTRIBUZIONE DIRETTA VERSO NODO REMOTO ───────────────────────────────

def distribute_payload_to_node(
    node_endpoint: str,
    node_pubkey_hex: str,
    update_payload: Dict[str, Any],
    sender_identity: Dict[str, Any],
    timeout_s: float = 20.0,
) -> Dict[str, Any]:
    """Cifra end-to-end un pacchetto di aggiornamento e lo invia al nodo remoto tramite HTTP POST."""
    ep = (node_endpoint or "").strip().rstrip("/")
    if not ep:
        return {"success": False, "error": "Endpoint nodo vuoto"}

    sender_priv = sender_identity.get("_private_key")
    sender_id = sender_identity.get("node_id", "")
    sender_pub = sender_identity.get("public_key", "")

    # Cifra con ECDH + AES-256-GCM + firma ECDSA
    envelope = encrypt_envelope(
        payload=update_payload,
        recipient_pubkey_hex=node_pubkey_hex,
        sender_private_key=sender_priv,
        sender_node_id=sender_id,
        sender_pubkey_hex=sender_pub,
    )

    try:
        r = requests.post(
            f"{ep}/mesh/sync/patch",
            json={"encrypted": True, "envelope": envelope},
            headers={"Content-Type": "application/json"},
            timeout=timeout_s,
        )
        if r.status_code == 200:
            res_data = r.json()
            # Se la risposta è un envelope cifrato di conferma
            if res_data.get("encrypted") and "envelope" in res_data:
                ack_envelope = res_data["envelope"]
                decrypted_ack = decrypt_envelope(
                    envelope=ack_envelope,
                    recipient_private_key=sender_priv,
                    expected_sender_pubkey=node_pubkey_hex,
                )
                return {"success": True, "ack": decrypted_ack, "encrypted": True}
            return {"success": True, "ack": res_data, "encrypted": False}
        return {
            "success": False,
            "status_code": r.status_code,
            "error": r.text[:200],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
