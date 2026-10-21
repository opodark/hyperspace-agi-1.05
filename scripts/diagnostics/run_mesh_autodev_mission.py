#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Missione Distribuita di Autosviluppo Neurale e Validazione CoT su Tutti i Nodi Mesh.
Invia task di ragionamento CoT (<think>) ed emissione codice a:
- HP OMEN 16 (GPU Worker, RTX 3070 8GB)
- ASUS V16 (High-RAM Worker, RTX 8GB / 48GB RAM)
- Mac M5 (Authority Hub, Apple Silicon)

Valida sintatticamente il codice via AST Python, calcola le metriche di velocità
e archivia i campioni approvati in data/synthetic_cot_dataset.jsonl.
"""

from __future__ import annotations

import argparse
import ast
import datetime
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.request
import urllib.error

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.identity import generate_or_load_identity, make_request_headers
from shared.universal_model_parser import CavemanEngine, UniversalModelParser
from shared.codebase_journal import CodebaseJournal

DATA_DIR = REPO_ROOT / "data"
SYNTHETIC_DATASET = DATA_DIR / "synthetic_cot_dataset.jsonl"
MISSIONS_FILE = DATA_DIR / "missions.jsonl"

MODEL = "hf.co/DuoNeural/LFM2.5-8B-A1B-Abliterated-GGUF:Q4_K_M"

NODES = [
    {
        "id": "omen",
        "name": "HP OMEN 16",
        "role": "GPU Worker",
        "url": "http://100.104.238.125:8081",
        "local_fallback": "http://127.0.0.1:8081",
        "task_name": "Routing Neurale VRAM & GPU Allocation",
        "prompt": (
            "Crea una funzione Python `route_task_by_vram(task_requirements, nodes_list)` "
            "che calcola lo score di idoneità in base alla VRAM libera e all'alimentazione AC/Batteria. "
            "Mostra prima un ragionamento conciso in <think> (max 150 parole), poi restituisci il codice completo in un blocco ```python ... ``` con type hinting."
        ),
        "domain": "mesh_routing"
    },
    {
        "id": "asus",
        "name": "ASUS V16",
        "role": "High-RAM Worker",
        "url": "http://100.64.31.18:8081",
        "local_fallback": None,
        "task_name": "Cache Atomica Memory Sync con Eviction",
        "prompt": (
            "Scrivi una classe `ShadowMemoryCache` in Python che salva le ultime N voci di memoria "
            "in un file JSON compresso gzip con scrittura atomica temporanea (.tmp -> rename) e thread lock. "
            "Mostra prima un ragionamento conciso in <think> (max 150 parole), poi restituisci il codice completo in un blocco ```python ... ```."
        ),
        "domain": "memory_sync"
    },
    {
        "id": "mac",
        "name": "Mac M5 Hub",
        "role": "Authority Hub",
        "url": "http://100.81.234.102:8081",
        "local_fallback": None,
        "task_name": "Sanitizzazione Token & Security Filter",
        "prompt": (
            "Crea una funzione Python `sanitize_environment_output(env_dict, sensitive_keys)` "
            "che maschera token, password e chiavi API mostrando solo i primi 4 e ultimi 4 caratteri. "
            "Mostra prima un ragionamento conciso in <think> (max 150 parole), poi restituisci il codice completo in un blocco ```python ... ``` con type hinting."
        ),
        "domain": "security_tokens"
    }
]


def send_node_task(node_spec: dict, timeout_s: int = 120) -> dict:
    url = node_spec["url"]
    compressed_prompt = CavemanEngine.compress(node_spec["prompt"])["compressed"]
    payload_data = {
        "task_id": f"autodev-{node_spec['id']}-{int(time.time() * 1000)}",
        "model": MODEL,
        "prompt": compressed_prompt,
        "max_tokens": 2048,
    }
    payload_bytes = json.dumps(payload_data).encode("utf-8")

    ident = generate_or_load_identity()
    headers = {"Content-Type": "application/json"}
    try:
        signed = make_request_headers(ident["node_id"], ident["public_key"], ident["_private_key"], body=payload_bytes)
        headers.update(signed)
    except Exception as exc:
        print(f"[{node_spec['name']}] Errore firma crittografica: {exc}")

    t0 = time.time()
    resp_text = ""
    target_url = f"{url}/execute"

    # Tentativo primario
    try:
        req = urllib.request.Request(target_url, data=payload_bytes, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            resp_text = data.get("response", "")
    except Exception as primary_err:
        if node_spec.get("local_fallback"):
            fb_url = f"{node_spec['local_fallback']}/execute"
            print(f"[{node_spec['name']}] Riprovo su fallback locale: {fb_url} ({primary_err})")
            req = urllib.request.Request(fb_url, data=payload_bytes, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                resp_text = data.get("response", "")
        else:
            raise primary_err

    elapsed = round(time.time() - t0, 2)
    return {
        "node_id": node_spec["id"],
        "node_name": node_spec["name"],
        "task_name": node_spec["task_name"],
        "domain": node_spec["domain"],
        "prompt": node_spec["prompt"],
        "response": resp_text,
        "elapsed_s": elapsed
    }


def execute_mission():
    print("=" * 70)
    print("  HYPERSPACE AGI — MISSIONE AUTOSVILUPPO DISTRIBUITO SU TUTTI I NODI")
    print(f"  Modello Target: {MODEL}")
    print(f"  Nodi Coinvolti: {', '.join(n['name'] for n in NODES)}")
    print(f"  Data & Ora: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    mission_id = f"mission-autodev-{int(time.time())}"
    mission_record = {
        "id": mission_id,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "objective": "Esecuzione distribuita di test di autosviluppo e distillazione CoT su HP OMEN 16, ASUS V16 e Mac M5",
        "status": "running",
        "nodes": [n["name"] for n in NODES],
        "tasks_results": []
    }

    results = []

    for idx, node in enumerate(NODES, 1):
        print(f"\n[{idx}/3] Invio task '{node['task_name']}' a {node['name']} ({node['url']})...")
        try:
            res = send_node_task(node)
            raw_response = res["response"]
            elapsed = res["elapsed_s"]

            # Parsing CoT e Codice
            parsed = UniversalModelParser.parse(raw_response)
            cot_text = parsed.reasoning_cot or ""
            cot_words = len(cot_text.split())

            # Validazione sintattica AST del primo blocco codice valido
            valid_blocks = [b for b in parsed.code_blocks if b.is_valid_ast]
            ast_ok = len(valid_blocks) > 0
            code_text = valid_blocks[0].code if valid_blocks else (parsed.code_blocks[0].code if parsed.code_blocks else "")

            # Fallback controllo ast diretto
            if not ast_ok and code_text:
                try:
                    ast.parse(code_text)
                    ast_ok = True
                except Exception:
                    ast_ok = False

            code_words = len(code_text.split())

            print(f"  -> Risposta ricevuta in {elapsed}s.")
            print(f"  -> Traccia di Pensiero (CoT): {'PRESENTE (' + str(cot_words) + ' parole)' if cot_words > 0 else 'ASSENTE'}")
            print(f"  -> Validazione Sintattica AST Python: {'PASS (100% Valido)' if ast_ok else 'FAIL'}")
            print(f"  -> Codice estratto: {code_words} parole.")

            # Salvataggio nel dataset sintetico se AST valido
            if ast_ok:
                SYNTHETIC_DATASET.parent.mkdir(parents=True, exist_ok=True)
                dataset_entry = {
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "source_node": node["name"],
                    "domain": node["domain"],
                    "prompt": node["prompt"],
                    "reasoning_cot": cot_text,
                    "code": code_text,
                    "ast_valid": True,
                    "mission_id": mission_id
                }
                with open(SYNTHETIC_DATASET, "a", encoding="utf-8") as f:
                    f.write(json.dumps(dataset_entry, ensure_ascii=False) + "\n")
                print(f"  -> Campione validato aggiunto a data/synthetic_cot_dataset.jsonl")

            node_summary = {
                "node": node["name"],
                "role": node["role"],
                "task": node["task_name"],
                "elapsed_s": elapsed,
                "cot_words": cot_words,
                "code_words": code_words,
                "ast_valid": ast_ok,
                "status": "PASS" if ast_ok else "WARN"
            }
            results.append(node_summary)
            mission_record["tasks_results"].append(node_summary)

        except Exception as exc:
            print(f"  -> ERRORE durante il task su {node['name']}: {exc}")
            err_summary = {
                "node": node["name"],
                "role": node["role"],
                "task": node["task_name"],
                "elapsed_s": 0.0,
                "error": str(exc),
                "ast_valid": False,
                "status": "FAIL"
            }
            results.append(err_summary)
            mission_record["tasks_results"].append(err_summary)

    # Conclusione missione
    all_passed = all(r["status"] == "PASS" for r in results)
    mission_record["status"] = "completed" if all_passed else "completed_with_warnings"
    mission_record["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    MISSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MISSIONS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(mission_record, ensure_ascii=False) + "\n")

    # Registrazione nel diario mutazioni
    journal = CodebaseJournal()
    journal.record_mutation(
        agent="Antigravity-Mesh",
        intent="Esecuzione missione distribuita di autosviluppo e distillazione CoT su tutti i nodi (OMEN, ASUS, MAC)",
        files_touched=["data/synthetic_cot_dataset.jsonl", "data/missions.jsonl"],
        action_type="mission",
        test_status="passed" if all_passed else "warn",
        lessons_learned=f"Missione {mission_id}: {len([r for r in results if r['ast_valid']])}/{len(NODES)} nodi convalidati AST."
    )

    print("\n" + "=" * 70)
    print("  RIASSUNTO FINALE DELLA MISSIONE DI AUTOSVILUPPO MESH")
    print("=" * 70)
    print(f"{'NODO':<16} | {'RUOLO':<16} | {'TEMPO':<7} | {'CoT':<10} | {'AST':<6} | {'ESITO':<6}")
    print("-" * 70)
    for r in results:
        t_str = f"{r.get('elapsed_s', 0.0)}s"
        cot_str = f"{r.get('cot_words', 0)} w" if r.get('cot_words') else "-"
        ast_str = "PASS" if r.get("ast_valid") else "FAIL"
        print(f"{r['node']:<16} | {r['role']:<16} | {t_str:<7} | {cot_str:<10} | {ast_str:<6} | {r['status']:<6}")
    print("=" * 70)
    print(f"\nMissione registrata in: {MISSIONS_FILE}")
    print(f"Stato Finale: {mission_record['status'].upper()}\n")

    return mission_record


if __name__ == "__main__":
    execute_mission()
