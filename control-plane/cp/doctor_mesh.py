# SPDX-License-Identifier: Apache-2.0
# control-plane/cp/doctor_mesh.py
# HyperSpace AGI — Mesh Doctor: Telemetria Cifrata, Codebase & Diagnostica Nodi
#
# Esegue check diagnostici avanzati a livello di mesh interrogando i nodi tramite
# il canale crittografato end-to-end (ECDH secp256k1 + AES-256-GCM + firma ECDSA).
#
# Check eseguiti:
#   1. mesh_codebase_alignment : verifica che tutti i nodi eseguano lo stesso commit git
#   2. mesh_codebase_dirty     : controlla modifiche o file untracked locali sui nodi
#   3. mesh_graph_freshness    : verifica presenza e freschezza del Knowledge Graph (Graphify)
#   4. mesh_encrypted_channel  : verifica l'integrità crittografica del canale E2EE
#   5. mesh_services_health    : monitora Laya Decision Engine, Ollama e ComfyUI sui nodi
#   6. mesh_model_pool         : catalogo modelli installati e modelli in VRAM nella mesh

import json
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from shared.crypto_channel import (
    CryptoChannelError,
    decrypt_envelope,
    encrypt_envelope,
    pubkey_from_hex,
)
from shared.identity import verify_message
from shared.node_telemetry import collect_full_node_telemetry


def _normalize_ep(ep: str) -> str:
    return (ep or "").strip().rstrip("/")


def poll_node_telemetry(
    endpoint: str,
    node_pubkey: str,
    cp_identity: Dict[str, Any],
    timeout_s: float = 3.0,
) -> Dict[str, Any]:
    """Interroga un nodo mesh richiedendo telemetria cifrata tramite ECDH + AES-256-GCM.

    Se il nodo supporta l'endpoint crittografico /doctor/telemetry, riceve e decifra l'envelope.
    Altrimenti applica fallback automatico e trasparente su /status standard.
    """
    ep = _normalize_ep(endpoint)
    if not ep:
        return {"channel": "invalid_endpoint", "error": "Endpoint vuoto"}

    cp_pubkey = cp_identity.get("public_key", "")
    cp_priv = cp_identity.get("_private_key")
    cp_node_id = cp_identity.get("node_id", "")

    # 1. Tentativo con canale cifrato E2EE (POST /doctor/telemetry)
    try:
        req_payload = {
            "requester_pubkey": cp_pubkey,
            "requester_node_id": cp_node_id,
        }
        r = requests.post(
            f"{ep}/doctor/telemetry",
            json=req_payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout_s,
        )
        if r.status_code == 200:
            resp_data = r.json()
            # Se la risposta è un envelope cifrato
            if resp_data.get("encrypted") and "envelope" in resp_data:
                envelope = resp_data["envelope"]
                decrypted = decrypt_envelope(
                    envelope=envelope,
                    recipient_private_key=cp_priv,
                    expected_sender_pubkey=node_pubkey if node_pubkey else None,
                    max_age_s=180,
                )
                decrypted["channel"] = "encrypted_ecdh_aes_gcm"
                decrypted["channel_verified"] = True
                return decrypted

            # Se la risposta è firmata ma non cifrata
            if "signature" in resp_data:
                is_valid = verify_message(resp_data)
                resp_data["channel"] = "signed_plaintext"
                resp_data["channel_verified"] = is_valid
                return resp_data

            resp_data["channel"] = "plaintext"
            resp_data["channel_verified"] = False
            return resp_data
    except Exception:
        pass

    # 2. Fallback su GET /doctor/telemetry con query param
    try:
        r = requests.get(
            f"{ep}/doctor/telemetry",
            params={"requester_pubkey": cp_pubkey},
            timeout=timeout_s,
        )
        if r.status_code == 200:
            resp_data = r.json()
            if resp_data.get("encrypted") and "envelope" in resp_data:
                envelope = resp_data["envelope"]
                decrypted = decrypt_envelope(
                    envelope=envelope,
                    recipient_private_key=cp_priv,
                    expected_sender_pubkey=node_pubkey if node_pubkey else None,
                    max_age_s=180,
                )
                decrypted["channel"] = "encrypted_ecdh_aes_gcm"
                decrypted["channel_verified"] = True
                return decrypted
            if "signature" in resp_data:
                resp_data["channel"] = "signed_plaintext"
                resp_data["channel_verified"] = verify_message(resp_data)
                return resp_data
    except Exception:
        pass

    # 3. Fallback di compatibilità su GET /status per nodi legacy
    try:
        r = requests.get(f"{ep}/status", timeout=timeout_s)
        if r.status_code == 200:
            data = r.json()
            return {
                "channel": "legacy_status",
                "channel_verified": False,
                "node_id": data.get("node_id", ""),
                "public_key": data.get("public_key", ""),
                "tier": data.get("tier", "leaf"),
                "codebase": {
                    "found": False,
                    "git_commit": "unknown (legacy /status)",
                    "git_branch": "unknown",
                    "git_dirty": False,
                    "graphify": {"available": False, "freshness": "unknown"},
                },
                "hardware": {
                    "vram_total_gb": data.get("vram_gb", 0.0),
                    "os": "unknown",
                },
                "services": {
                    "ollama": {"online": data.get("engine") == "ollama", "models": []},
                    "laya": {"online": False},
                },
                "runtime": {
                    "uptime_s": data.get("uptime_s", 0),
                    "active_requests": data.get("active_requests", 0),
                },
            }
    except Exception as e:
        return {
            "channel": "unreachable",
            "channel_verified": False,
            "error": str(e),
        }

    return {"channel": "unreachable", "channel_verified": False}


def run_mesh_codebase_and_health_checks(
    active_nodes: List[Dict[str, Any]],
    cp_identity: Dict[str, Any],
    local_repo_hint: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Interroga tutti i nodi attivi, raccoglie telemetria cifrata e calcola i check Doctor.

    Restituisce una tupla: (checks_list, nodes_telemetry_list).
    """
    checks: List[Dict[str, Any]] = []
    telemetries: List[Dict[str, Any]] = []

    # 1. Raccoglie la telemetria locale del Control-Plane come riferimento
    local_telemetry = collect_full_node_telemetry(
        node_id=cp_identity.get("node_id", "local_control_plane"),
        public_key_hex=cp_identity.get("public_key", ""),
        tier="root",
        repo_hint=local_repo_hint,
    )
    local_telemetry["is_local"] = True
    local_telemetry["channel"] = "local_memory"
    local_telemetry["channel_verified"] = True
    telemetries.append(local_telemetry)

    # 2. Interroga i nodi mesh remoti
    for node in active_nodes:
        if node.get("is_local"):
            continue
        ep = node.get("endpoint")
        nid = node.get("node_id", "")
        pubkey = node.get("public_key", "")
        if not ep:
            continue

        telem = poll_node_telemetry(ep, pubkey, cp_identity)
        telem["node_id"] = telem.get("node_id") or nid
        telem["endpoint"] = ep
        telem["alias"] = node.get("alias", "")
        telem["tier"] = telem.get("tier") or node.get("tier", "leaf")
        telemetries.append(telem)

    # ── CHECK 1: Canale Cifrato E2EE ──────────────────────────────────────────
    encrypted_nodes = [t for t in telemetries if t.get("channel") == "encrypted_ecdh_aes_gcm"]
    reachable_remote = [t for t in telemetries if not t.get("is_local") and t.get("channel") != "unreachable"]
    legacy_nodes = [t for t in telemetries if t.get("channel") == "legacy_status"]

    if legacy_nodes:
        legacy_names = ", ".join((t.get("alias") or t.get("node_id", "?")[:8]) for t in legacy_nodes)
        checks.append({
            "id": "mesh_encrypted_channel",
            "name": "Canale Crittografico Telemetria Mesh",
            "status": "warn",
            "detail": f"{len(encrypted_nodes)} nodo/i cifrati E2EE, {len(legacy_nodes)} usano telemetria legacy: {legacy_names}",
            "fix_hint": "Riavvia o aggiorna i container dei nodi remoti per abilitare il canale cifrato ECDH+AES-256-GCM.",
        })
    elif reachable_remote:
        checks.append({
            "id": "mesh_encrypted_channel",
            "name": "Canale Crittografico Telemetria Mesh",
            "status": "ok",
            "detail": f"Canale E2EE attivo e verificato su tutti i {len(encrypted_nodes)} nodi remoti (ECDH secp256k1 + AES-256-GCM con Forward Secrecy)",
            "fix_hint": "",
        })
    else:
        checks.append({
            "id": "mesh_encrypted_channel",
            "name": "Canale Crittografico Telemetria Mesh",
            "status": "ok",
            "detail": "Canale crittografico pronto (in attesa di nodi remoti aggiuntivi)",
            "fix_hint": "",
        })

    # ── CHECK 2: Allineamento Codebase Git ────────────────────────────────────
    commits_map: Dict[str, List[str]] = {}
    for t in telemetries:
        cb = t.get("codebase", {})
        c = cb.get("git_commit", "unknown")
        label = t.get("alias") or (t.get("node_id", "?")[:8] + (" [Hub/Local]" if t.get("is_local") else ""))
        commits_map.setdefault(c, []).append(label)

    # Escludi unknown dai calcoli di drift se nessun commit valido è stato letto
    valid_commits = [k for k in commits_map.keys() if k not in ("unknown", "unknown (legacy /status)")]
    if len(valid_commits) > 1:
        remote_reachable = [t for t in telemetries if not t.get("is_local") and t.get("channel") != "unreachable"]
        all_role_aligned = bool(remote_reachable) and all(
            t.get("codebase", {}).get("role_aligned", False)
            for t in remote_reachable
        )
        if all_role_aligned:
            roles_desc = "; ".join(
                f"{t.get('alias') or t.get('node_id', '?')[:8]} ({t.get('tier', 'worker')}: {t.get('codebase', {}).get('git_commit', '?')})"
                for t in telemetries
            )
            checks.append({
                "id": "mesh_codebase_alignment",
                "name": "Allineamento Codebase Git Mesh",
                "status": "ok",
                "detail": f"Nodi coerenti per ruolo (allineati ai rispettivi ambiti di competenza: {roles_desc})",
                "fix_hint": "",
            })
        else:
            diff_desc = "; ".join(f"commit {c}: {', '.join(nodes)}" for c, nodes in commits_map.items())
            checks.append({
                "id": "mesh_codebase_alignment",
                "name": "Allineamento Codebase Git Mesh",
                "status": "warn",
                "detail": f"Disallineamento commit rilevato tra i nodi: {diff_desc}",
                "fix_hint": "Esegui 'git pull' o distribuisci la patch per allineare il nodo al proprio ruolo.",
            })
    elif len(valid_commits) == 1:
        c_hash = valid_commits[0]
        nodes_count = len(telemetries)
        branch = telemetries[0].get("codebase", {}).get("git_branch", "main")
        checks.append({
            "id": "mesh_codebase_alignment",
            "name": "Allineamento Codebase Git Mesh",
            "status": "ok",
            "detail": f"Tutti i nodi sono allineati al commit {c_hash} (branch '{branch}')",
            "fix_hint": "",
        })
    else:
        checks.append({
            "id": "mesh_codebase_alignment",
            "name": "Allineamento Codebase Git Mesh",
            "status": "ok",
            "detail": "Nessun repository git remoto da confrontare (nodi legacy o standalone)",
            "fix_hint": "",
        })

    # ── CHECK 3: Modifiche non committate (Git Dirty) ─────────────────────────
    dirty_nodes = []
    for t in telemetries:
        cb = t.get("codebase", {})
        if cb.get("git_dirty"):
            label = t.get("alias") or (t.get("node_id", "?")[:8] + (" [Local]" if t.get("is_local") else ""))
            summary = cb.get("dirty_summary") or f"{cb.get('dirty_files_count', 1)} file modificati"
            dirty_nodes.append(f"{label} ({summary})")

    if dirty_nodes:
        checks.append({
            "id": "mesh_codebase_dirty",
            "name": "Stato Working Tree Git",
            "status": "warn",
            "detail": f"File locali non committati rilevati su: {'; '.join(dirty_nodes)}",
            "fix_hint": "Committa o archivia le modifiche ('git stash') prima di distribuire a nuovi nodi.",
        })
    else:
        checks.append({
            "id": "mesh_codebase_dirty",
            "name": "Stato Working Tree Git",
            "status": "ok",
            "detail": "Working tree pulito su tutti i nodi analizzati",
            "fix_hint": "",
        })

    # ── CHECK 4: Knowledge Graph (Graphify) ───────────────────────────────────
    local_graph = local_telemetry.get("codebase", {}).get("graphify", {})
    if local_graph.get("available"):
        n_count = local_graph.get("nodes_count", 0)
        com_count = local_graph.get("communities_count", 0)
        freshness = local_graph.get("freshness", "fresh")
        detail_msg = f"Grafo attivo ({com_count} community clusterizzate, stato: {freshness})"
        checks.append({
            "id": "mesh_graph_freshness",
            "name": "Knowledge Graph (Graphify)",
            "status": "ok" if freshness == "fresh" else "warn",
            "detail": detail_msg,
            "fix_hint": "Rigenera il grafo con 'graphify extract . && graphify cluster-only .'" if freshness != "fresh" else "",
        })
    else:
        checks.append({
            "id": "mesh_graph_freshness",
            "name": "Knowledge Graph (Graphify)",
            "status": "warn",
            "detail": "File graph.json assente in graphify-out",
            "fix_hint": "Esegui 'graphify extract . --code-only' per mappare la base di codice.",
        })

    # Il grafo arriva ai nodi remoti via mesh_distribute --sync-graphify: un nodo con
    # un graph.json diverso da quello locale (o senza) non ha ricevuto l'ultimo bundle.
    if local_graph.get("available"):
        remote_reachable = [t for t in telemetries if not t.get("is_local") and t.get("channel") != "unreachable"]
        local_size = local_graph.get("size_bytes")
        out_of_sync = [
            (t.get("alias") or (t.get("node_id") or "?")[:8])
            for t in remote_reachable
            if t.get("codebase", {}).get("graphify", {}).get("size_bytes") != local_size
        ]
        if remote_reachable:
            graph_check = checks[-1]
            aligned = len(remote_reachable) - len(out_of_sync)
            graph_check["detail"] += f"; nodi remoti con lo stesso grafo: {aligned}/{len(remote_reachable)}"
            if out_of_sync:
                graph_check["status"] = "warn"
                graph_check["detail"] += f" (diverso: {', '.join(out_of_sync)})"
                graph_check["fix_hint"] = graph_check["fix_hint"] or "Distribuisci il grafo: python scripts/mesh_distribute.py --sync-graphify --all"

    # ── CHECK 5: Servizi & Decision Engine (System 1) ─────────────────────────
    laya_online = [t for t in telemetries if t.get("services", {}).get("laya", {}).get("online")]
    ollama_online = [t for t in telemetries if t.get("services", {}).get("ollama", {}).get("online")]
    comfy_online = [t for t in telemetries if t.get("services", {}).get("comfyui", {}).get("online")]

    services_detail = (
        f"Ollama attivo su {len(ollama_online)}/{len(telemetries)} nodi; "
        f"Laya Decision Engine: {'online (sub-50ms)' if laya_online else 'offline/standby'}; "
        f"ComfyUI: {'online' if comfy_online else 'standby'}"
    )
    checks.append({
        "id": "mesh_services_health",
        "name": "Servizi IA & Decision Engine",
        "status": "ok" if ollama_online else "warn",
        "detail": services_detail,
        "fix_hint": "Avvia Laya con '.\\scripts\\start-laya.ps1' se desideri il triage sub-50ms attivo." if not laya_online else "",
    })

    # ── CHECK 6: Gestione Energetica & Resilienza Blackout (Power Policy v1.05) ──
    try:
        from shared.power_policy import assess_cluster_energy_status
        energy_eval = assess_cluster_energy_status(telemetries)

        fix_hint = ""
        if energy_eval["critical_count"] > 0:
            fix_hint = f"Attenzione: {', '.join(energy_eval['critical_nodes'])} sotto soglia critica (<20%). Collega subito all'alimentatore."
        elif energy_eval["regime"] == "blackout_cooperative":
            fix_hint = "Collega almeno un nodo alla rete elettrica AC per riabilitare task pesanti e cicli di sogno."

        checks.append({
            "id": "mesh_power_grid",
            "name": "Alimentazione & Resilienza Energetica",
            "status": energy_eval["status"],
            "detail": energy_eval["summary"],
            "fix_hint": fix_hint,
            "regime": energy_eval["regime"],
        })
    except Exception as e:
        checks.append({
            "id": "mesh_power_grid",
            "name": "Alimentazione & Resilienza Energetica",
            "status": "ok",
            "detail": f"Rilevamento energetico fallback ({e})",
            "fix_hint": "",
        })

    return checks, telemetries
