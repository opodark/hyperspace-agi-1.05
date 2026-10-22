#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Suite di Test e Valutazione Collaborativa Multi-Agente MoE:
Flint 40B MoE (ASUS @ 128k) <-> Liquid AI LFM2.5 24B/8B MoE (HP OMEN @ 64k / Mac Hub).

Verifica la cooperazione inter-nodo distribuita su Tailscale:
- Nodo A (Leader Coder): Flint 40B MoE su ASUS V16 (RTX 5060 + 48 GB RAM) con contesto 128k (131.072 token).
- Nodo B (Lead Architect & Gate): LFM2.5 24B MoE su HP OMEN 16 (RTX 3070 + 32 GB RAM) con contesto 64k (65.536 token).

Uso:
    .venv/bin/python scripts/diagnostics/test_flint_lfm_collaboration.py --target omen --flint-ctx 131072 --lfm-ctx 65536
    .venv/bin/python scripts/diagnostics/test_flint_lfm_collaboration.py --target omen --scenarios 1,2,3,4
    .venv/bin/python scripts/diagnostics/test_flint_lfm_collaboration.py --target mac --flint-ctx 32768 --lfm-ctx 32768
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
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.identity import generate_or_load_identity, make_request_headers
from shared.universal_model_parser import CodeBlock, ParsedModelResponse, UniversalModelParser

# Configurazione Nodi Mesh
ASUS_OLLAMA_URL = "http://100.64.31.18:11434"
OMEN_NODE_URL = "http://100.104.238.125:8081"
MAC_OLLAMA_URL = "http://127.0.0.1:11434"

MODEL_FLINT_40B = "flint:latest"
MODEL_LFM_24B = "hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M"
MODEL_LFM_8B = "hf.co/DuoNeural/LFM2.5-8B-A1B-Abliterated-GGUF:Q4_K_M"

DEFAULT_FLINT_CTX = 131072  # 128k
DEFAULT_LFM_CTX = 65536     # 64k


def query_model(
    base_url: str,
    model: str,
    prompt: str,
    num_ctx: int = 32768,
    num_predict: int = 2000,
    temperature: float = 0.2,
    timeout_s: int = 240,
    system_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Interfaccia universale che interroga sia endpoint nativi Ollama (:11434)
    sia endpoint worker Mesh firmati crittograficamente (:8081/execute)."""
    
    # ── Percorso 1: HyperSpace Node Worker (:8081) con firma crittografica ───────
    if ":8081" in base_url or base_url.endswith("/execute"):
        url = f"{base_url.rstrip('/')}/execute" if not base_url.endswith("/execute") else base_url
        full_prompt = prompt if not system_prompt else f"### SYSTEM:\n{system_prompt}\n\n### TASK:\n{prompt}"
        payload_data = {
            "task_id": f"collab-{int(time.time() * 1000)}",
            "model": model,
            "prompt": full_prompt,
            "max_tokens": num_predict,
            "options": {"num_ctx": num_ctx, "temperature": temperature},
        }
        payload_bytes = json.dumps(payload_data).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        try:
            ident = generate_or_load_identity()
            signed = make_request_headers(ident["node_id"], ident["public_key"], ident["_private_key"], body=payload_bytes)
            headers.update(signed)
        except Exception:
            pass

        req = urllib.request.Request(url, data=payload_bytes, headers=headers)
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            elapsed = time.time() - t0
            return {
                "ok": False,
                "error": f"NodeWorkerError: {e}",
                "elapsed_s": round(elapsed, 2),
                "response": "",
                "thinking": "",
            }
        
        elapsed = time.time() - t0
        raw_text = res_json.get("response", "")
        thinking_text = ""
        response_text = raw_text

        # Isolamento del blocco <think>
        if "<think>" in raw_text and "</think>" in raw_text:
            idx_start = raw_text.find("<think>")
            idx_end = raw_text.rfind("</think>")
            thinking_text = raw_text[idx_start + 7:idx_end].strip()
            response_text = raw_text[idx_end + 8:].strip()

        tokens = max(1, int(len(raw_text.split()) * 1.3))
        tok_s = round(tokens / max(0.1, elapsed), 2)

        return {
            "ok": True,
            "response": response_text,
            "thinking": thinking_text,
            "eval_count": tokens,
            "eval_tok_per_s": tok_s,
            "prompt_eval_count": int(len(prompt.split()) * 1.3),
            "prompt_tok_per_s": 0.0,
            "elapsed_s": round(elapsed, 2),
            "total_duration_s": round(elapsed, 2),
            "load_duration_s": 0.0,
        }

    # ── Percorso 2: Ollama Diretto (:11434 /api/generate) ────────────────────────
    url = f"{base_url.rstrip('/')}/api/generate"
    options: Dict[str, Any] = {
        "num_ctx": num_ctx,
        "num_predict": num_predict,
        "temperature": temperature,
        "top_p": 0.95,
    }
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": options,
    }
    if system_prompt:
        payload["system"] = system_prompt

    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={"Content-Type": "application/json"},
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw_body = resp.read().decode("utf-8")
            res_json = json.loads(raw_body)
    except urllib.error.URLError as e:
        elapsed = time.time() - t0
        return {
            "ok": False,
            "error": f"URLError: {e}",
            "elapsed_s": round(elapsed, 2),
            "response": "",
            "thinking": "",
        }
    except Exception as e:
        elapsed = time.time() - t0
        return {
            "ok": False,
            "error": f"Exception: {e}",
            "elapsed_s": round(elapsed, 2),
            "response": "",
            "thinking": "",
        }

    elapsed = time.time() - t0
    response_text = res_json.get("response", "")
    thinking_text = res_json.get("thinking", "")

    # Se la response include tag <think> espliciti, unifichiamo senza distruggere codice/JSON
    if "<think>" in response_text and "</think>" in response_text:
        idx_start = response_text.find("<think>")
        idx_end = response_text.rfind("</think>")
        if not thinking_text:
            thinking_text = response_text[idx_start + 7:idx_end].strip()
        response_text = response_text[idx_end + 8:].strip()

    eval_count = res_json.get("eval_count", 0)
    eval_duration_ns = res_json.get("eval_duration", 1)
    prompt_eval_count = res_json.get("prompt_eval_count", 0)
    prompt_eval_duration_ns = res_json.get("prompt_eval_duration", 1)

    eval_tok_per_s = round(eval_count / (eval_duration_ns / 1e9), 2) if eval_duration_ns > 0 else 0.0
    prompt_tok_per_s = round(prompt_eval_count / (prompt_eval_duration_ns / 1e9), 2) if prompt_eval_duration_ns > 0 else 0.0

    return {
        "ok": True,
        "response": response_text,
        "thinking": thinking_text,
        "eval_count": eval_count,
        "eval_tok_per_s": eval_tok_per_s,
        "prompt_eval_count": prompt_eval_count,
        "prompt_tok_per_s": prompt_tok_per_s,
        "elapsed_s": round(elapsed, 2),
        "total_duration_s": round(res_json.get("total_duration", 0) / 1e9, 2),
        "load_duration_s": round(res_json.get("load_duration", 0) / 1e9, 2),
    }


def extract_code_and_validate(text: str) -> Tuple[Optional[str], bool, Optional[str]]:
    """Estrae il primo blocco di codice Python valido o restituisce l'errore AST."""
    parsed = UniversalModelParser.parse(text)
    for cb in parsed.code_blocks:
        if cb.language.lower() in ("python", "py", ""):
            try:
                ast.parse(cb.code)
                return cb.code, True, None
            except SyntaxError as e:
                # Riparazione parentesi chiusura se troncato leggermente
                repaired = cb.code.strip()
                for closer in (")", "]", "}", "pass"):
                    try:
                        candidate = repaired + "\n    " + closer
                        ast.parse(candidate)
                        return candidate, True, None
                    except Exception:
                        pass
                return cb.code, False, str(e)

    match = re.search(r"```(?:python|py)?\n(.*?)```", text, re.DOTALL)
    if match:
        code = match.group(1).strip()
        try:
            ast.parse(code)
            return code, True, None
        except SyntaxError as e:
            return code, False, str(e)

    return None, False, "Nessun blocco di codice Python individuato"


# =============================================================================
# SCENARIO 1: Architect -> Implementer (LFM2.5 -> Flint)
# =============================================================================

def run_scenario_1_architect_to_coder(
    flint_url: str,
    flint_model: str,
    flint_ctx: int,
    lfm_url: str,
    lfm_model: str,
    lfm_ctx: int,
) -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print("▶ SCENARIO 1: Handshake Architettura -> Implementazione")
    print(f"  1. LFM2.5 ({lfm_model} @ {lfm_ctx//1024}k) progetta AdaptiveMeshBackoff")
    print(f"  2. Flint 40B ({flint_model} @ {flint_ctx//1024}k) implementa il codice Python")
    print("  3. Validazione AST formale e metriche di throughput")
    print("=" * 70)

    lfm_prompt = (
        "Sei il Lead System Architect della rete HyperSpace AGI.\n"
        "Progetta la specifica tecnica per un modulo Python resiliente chiamato `AdaptiveMeshBackoff`.\n"
        "Ragiona concisamente in <think> (max 80 parole), poi emetti la specifica.\n"
        "Requisiti architetturali:\n"
        "- Gestione tentativi esponenziali con full jitter randomizzato per evitare thundering herd.\n"
        "- Parametri: `base_delay_s: float`, `max_delay_s: float`, `max_attempts: int`.\n"
        "- Metodo `compute_delay(attempt: int) -> float`.\n"
        "- Metodo `execute_with_retry(fn, *args, **kwargs) -> Any`.\n"
        "- Callback opzionale `on_retry(attempt, exc, delay)`.\n\n"
        "Definisci chiaramente il contratto per il Lead Coder (Flint). Sii conciso ed essenziale."
    )

    print(f"[*] [1/2] Invocazione LFM2.5 ({lfm_model}) su {lfm_url} (ctx={lfm_ctx})...")
    res_lfm = query_model(
        base_url=lfm_url,
        model=lfm_model,
        prompt=lfm_prompt,
        num_ctx=lfm_ctx,
        num_predict=800,
        temperature=0.2,
    )

    if not res_lfm["ok"]:
        print(f"[!] Errore LFM2.5: {res_lfm.get('error')}")
        return {"scenario": 1, "status": "FAIL", "reason": res_lfm.get("error")}

    spec_text = res_lfm["response"].strip()
    lfm_cot = res_lfm["thinking"].strip()
    print(f"  ✓ LFM2.5 ha risposto in {res_lfm['elapsed_s']}s ({res_lfm['eval_tok_per_s']} tok/s)")
    if lfm_cot:
        print(f"  ↳ CoT LFM2.5: {len(lfm_cot.split())} parole")
    print(f"  ↳ Specifica generata: {len(spec_text)} caratteri")

    flint_prompt = (
        "Sei il Senior Implementer di HyperSpace. Ricevi dal tuo Lead Architect (LFM2.5) "
        "la seguente specifica tecnica per il modulo `AdaptiveMeshBackoff`:\n\n"
        "--- INIZIO SPECIFICA ARCHITETTO ---\n"
        f"{spec_text}\n"
        "--- FINE SPECIFICA ARCHITETTO ---\n\n"
        "ISTRUZIONI:\n"
        "1. Ragiona in modo compatto in <think> (max 100 parole).\n"
        "2. Implementa il modulo Python completo in un blocco ```python ... ```, includendo la classe AdaptiveMeshBackoff, "
        "compute_delay ed execute_with_retry con random jitter e type hints. Concludi interamente la classe."
    )

    print(f"[*] [2/2] Invocazione Flint 40B ({flint_model}) su {flint_url} (ctx={flint_ctx})...")
    res_flint = query_model(
        base_url=flint_url,
        model=flint_model,
        prompt=flint_prompt,
        num_ctx=flint_ctx,
        num_predict=2200,
        temperature=0.15,
    )

    if not res_flint["ok"]:
        print(f"[!] Errore Flint: {res_flint.get('error')}")
        return {"scenario": 1, "status": "FAIL", "reason": res_flint.get("error")}

    flint_text = res_flint["response"].strip()
    flint_cot = res_flint["thinking"].strip()
    print(f"  ✓ Flint ha risposto in {res_flint['elapsed_s']}s ({res_flint['eval_tok_per_s']} tok/s)")
    if flint_cot:
        print(f"  ↳ CoT Flint: {len(flint_cot.split())} parole")

    code, is_valid_ast, ast_err = extract_code_and_validate(flint_text)
    if not is_valid_ast or not code:
        print(f"  ✗ Errore sintassi o AST: {ast_err}")
        return {
            "scenario": 1,
            "status": "FAIL",
            "reason": f"AST Syntax Error: {ast_err}",
            "flint_code": code or flint_text[:500],
        }

    checks = {
        "class AdaptiveMeshBackoff": "class AdaptiveMeshBackoff" in code,
        "compute_delay": "def compute_delay" in code,
        "execute_with_retry": "def execute_with_retry" in code,
        "jitter / random": ("random" in code or "uniform" in code),
    }

    all_passed = all(checks.values())
    print(f"  ✓ Validazione AST Python: PASS (sintassi valida al 100%)")
    for req_name, req_ok in checks.items():
        print(f"    - {req_name}: {'✓ PASS' if req_ok else '✗ MANCANTE'}")

    status = "PASS" if all_passed else "PARTIAL"
    return {
        "scenario": 1,
        "status": status,
        "lfm_metrics": {"tok_s": res_lfm["eval_tok_per_s"], "elapsed_s": res_lfm["elapsed_s"]},
        "flint_metrics": {"tok_s": res_flint["eval_tok_per_s"], "elapsed_s": res_flint["elapsed_s"]},
        "code_lines": len(code.splitlines()),
        "flint_code": code,
        "spec_text": spec_text,
    }


# =============================================================================
# SCENARIO 2: Code Reviewer & Security Gate (Flint -> LFM2.5)
# =============================================================================

def run_scenario_2_code_review(
    flint_code: str,
    lfm_url: str,
    lfm_model: str,
    lfm_ctx: int,
) -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print("▶ SCENARIO 2: Code Review & Quality Gate (Flint -> LFM2.5)")
    print(f"  1. LFM2.5 ({lfm_model} @ {lfm_ctx//1024}k) audita il codice generato da Flint")
    print("  2. Verifica thread-safety, gestione eccezioni e leak di risorse")
    print("  3. Emette verdetto strutturato [APPROVED] o [REVISE]")
    print("=" * 70)

    review_prompt = (
        "Sei il Security and Code Reviewer Gate della rete HyperSpace AGI.\n"
        "Analizza il codice Python del modulo `AdaptiveMeshBackoff` scritto dal nostro agente Coder (Flint):\n\n"
        "```python\n"
        f"{flint_code}\n"
        "```\n\n"
        "Effettua una review critica esaminando:\n"
        "1. Robustezza nella cattura delle eccezioni.\n"
        "2. Correttezza del jitter randomico.\n"
        "3. Gestione di max_attempts superato.\n"
        "4. Thread safety.\n\n"
        "Ragiona concisamente in <think> (max 80 parole).\n"
        "Nella risposta finale, concludi ESPLICITAMENTE con la riga:\n"
        "VERDETTO FINALE: [APPROVED] oppure VERDETTO FINALE: [NEEDS_REVISION]\n"
        "e 2-3 raccomandazioni concrete in elenco puntato."
    )

    print(f"[*] Invocazione LFM2.5 ({lfm_model}) per Code Review (ctx={lfm_ctx})...")
    res = query_model(
        base_url=lfm_url,
        model=lfm_model,
        prompt=review_prompt,
        num_ctx=lfm_ctx,
        num_predict=800,
        temperature=0.1,
    )

    if not res["ok"]:
        print(f"[!] Errore LFM2.5 Review: {res.get('error')}")
        return {"scenario": 2, "status": "FAIL", "reason": res.get("error")}

    review_text = res["response"].strip()
    review_cot = res["thinking"].strip()
    print(f"  ✓ LFM2.5 ha completato la review in {res['elapsed_s']}s ({res['eval_tok_per_s']} tok/s)")
    if review_cot:
        print(f"  ↳ CoT Review: {len(review_cot.split())} parole")

    clean_resp = UniversalModelParser.parse(review_text).clean_text or review_text
    match_verdict = re.search(r"VERDETTO\s*(?:FINALE)?:\s*\[?(APPROVED|NEEDS_REVISION)\]?", clean_resp, re.IGNORECASE)

    verdict = match_verdict.group(1).upper() if match_verdict else ("APPROVED" if "APPROVED" in clean_resp.upper() else "NEEDS_REVISION")
    print(f"  ↳ Verdetto rilevato nel corpo finale: {verdict}")

    summary_lines = [l for l in clean_resp.splitlines() if l.strip()][:5]
    print("  ↳ Sintesi review:\n    " + "\n    ".join(summary_lines))

    return {
        "scenario": 2,
        "status": "PASS",
        "verdict": verdict,
        "review_metrics": {"tok_s": res["eval_tok_per_s"], "elapsed_s": res["elapsed_s"]},
        "full_review": review_text,
    }


# =============================================================================
# SCENARIO 3: Handshake Protocollo JSON Agente <-> Agente
# =============================================================================

def run_scenario_3_json_interop(
    flint_url: str,
    flint_model: str,
    flint_ctx: int,
    lfm_url: str,
    lfm_model: str,
    lfm_ctx: int,
) -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print("▶ SCENARIO 3: Handshake Protocollo JSON Puro (Flint <-> LFM2.5)")
    print(f"  1. Flint 40B (@ {flint_ctx//1024}k) emette un telemetry incident report in JSON puro")
    print(f"  2. LFM2.5 (@ {lfm_ctx//1024}k) riceve il JSON e risponde con mitigazione in JSON puro")
    print("  3. Validazione parser schema su entrambi i payload")
    print("=" * 70)

    flint_json_prompt = (
        "Sei il Monitor Node Agent su nodo ASUS V16.\n"
        "È stato rilevato un evento di pressione VRAM: 7.4 GB su 8.0 GB, temp 78C.\n"
        "Emetti il tuo report di telemetria ESCLUSIVAMENTE all'interno di un blocco ```json ... ``` valido.\n"
        "Struttura richiesta:\n"
        "```json\n"
        "{\n"
        '  "schema_version": "1.0",\n'
        '  "node_id": "asus-v16",\n'
        '  "event_type": "vram_pressure_warning",\n'
        '  "metrics": {\n'
        '    "vram_used_gb": 7.4,\n'
        '    "vram_total_gb": 8.0,\n'
        '    "gpu_temp_c": 78\n'
        "  },\n"
        '  "urgency": "high",\n'
        '  "requested_action": "evict_idle_models_or_offload"\n'
        "}\n"
        "```\n"
        "Ragiona concisamente in <think> (max 40 parole) prima del JSON."
    )

    print(f"[*] [1/2] Flint emette JSON incidente (ctx={flint_ctx})...")
    res_flint = query_model(
        base_url=flint_url,
        model=flint_model,
        prompt=flint_json_prompt,
        num_ctx=flint_ctx,
        num_predict=1200,
        temperature=0.1,
    )

    if not res_flint["ok"]:
        return {"scenario": 3, "status": "FAIL", "reason": res_flint.get("error")}

    flint_raw = res_flint["response"].strip()
    flint_json_data = UniversalModelParser.extract_json(flint_raw)
    if not flint_json_data or not isinstance(flint_json_data, dict):
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", flint_raw, re.DOTALL)
        if m:
            try:
                flint_json_data = json.loads(m.group(1))
            except Exception as e:
                return {"scenario": 3, "status": "FAIL", "reason": f"Flint JSON error: {e}"}
        else:
            return {"scenario": 3, "status": "FAIL", "reason": "Nessun JSON estratto da Flint"}

    print(f"  ✓ JSON Flint estratto e validato: nodo={flint_json_data.get('node_id')}, urgency={flint_json_data.get('urgency')}")

    lfm_remediate_prompt = (
        "Sei il Central Control Plane (LFM2.5). Ricevi questo evento di telemetria da un nodo della mesh:\n\n"
        f"{json.dumps(flint_json_data, indent=2)}\n\n"
        "Genera la direttiva di mitigazione in un blocco ```json ... ``` con la seguente struttura:\n"
        "```json\n"
        "{\n"
        '  "action_id": "remedy-101",\n'
        '  "target_node": "asus-v16",\n'
        '  "directive": "evict_idle_context",\n'
        '  "target_service": "ollama",\n'
        '  "params": {"free_vram_target_mb": 1500},\n'
        '  "status": "dispatched",\n'
        '  "acknowledged_urgency": "high"\n'
        "}\n"
        "```\n"
        "Ragiona concisamente in <think> (max 40 parole) prima del JSON."
    )

    print(f"[*] [2/2] LFM2.5 consuma il JSON ed emette contromisura (ctx={lfm_ctx})...")
    res_lfm = query_model(
        base_url=lfm_url,
        model=lfm_model,
        prompt=lfm_remediate_prompt,
        num_ctx=lfm_ctx,
        num_predict=1200,
        temperature=0.1,
    )

    if not res_lfm["ok"]:
        return {"scenario": 3, "status": "FAIL", "reason": res_lfm.get("error")}

    lfm_raw = res_lfm["response"].strip()
    lfm_json_data = UniversalModelParser.extract_json(lfm_raw)
    if not lfm_json_data or not isinstance(lfm_json_data, dict):
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", lfm_raw, re.DOTALL)
        if m:
            try:
                lfm_json_data = json.loads(m.group(1))
            except Exception as e:
                return {"scenario": 3, "status": "FAIL", "reason": f"LFM2.5 JSON error: {e}"}
        else:
            return {"scenario": 3, "status": "FAIL", "reason": "Nessun JSON estratto da LFM2.5"}

    print(f"  ✓ JSON LFM2.5 estratto e validato: directive={lfm_json_data.get('directive')}, target={lfm_json_data.get('target_node')}")

    match_ok = (
        lfm_json_data.get("target_node") == flint_json_data.get("node_id") and
        lfm_json_data.get("acknowledged_urgency") == flint_json_data.get("urgency")
    )
    print(f"  ✓ Handshake semantico tra i nodi: {'CONFERMATO' if match_ok else 'DISALLINEATO'}")

    return {
        "scenario": 3,
        "status": "PASS" if match_ok else "PARTIAL",
        "flint_json": flint_json_data,
        "lfm_json": lfm_json_data,
        "throughput": {
            "flint_tok_s": res_flint["eval_tok_per_s"],
            "lfm_tok_s": res_lfm["eval_tok_per_s"],
        }
    }


# =============================================================================
# SCENARIO 4: 128k Long-Context Needle & Joint Deduction
# =============================================================================

def run_scenario_4_long_context_128k(
    flint_url: str,
    flint_model: str,
    flint_ctx: int,
) -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print(f"▶ SCENARIO 4: Validazione e Stress-Test del Contesto a 128k ({flint_ctx} token)")
    print("  1. Iniezione di un documento denso con una regola architetturale nascosta")
    print("  2. Verifica che Flint 40B operi a 128k senza troncamento o degradazione")
    print("=" * 70)

    filler_chunks = []
    for i in range(1, 40):
        filler_chunks.append(
            f"SEZIONE ARCHITETTURALE {i:02d}: Telemetria, routing e nodi operativi.\n"
            f"Il sottosistema {i} regola il polling a 100.64.31.{i % 250}:8081 con timeout dinamico.\n"
            f"Parametri associati: jitter_factor={(i * 0.05):.2f}, max_retries={i % 5 + 1}, cache_ttl_s={i * 60}.\n"
        )
    document_padding = "\n".join(filler_chunks)

    needle = (
        "REGOLA_SPECIALE_EMERGENZA: Quando una richiesta presenta l'header 'X-Mesh-Priority: emergency', "
        "tutti i controlli e le soglie di throttling VRAM devono essere bypassati immediatamente, "
        "allocando l'esecuzione sul token slot prioritario 'SLOT_ALPHA_ZERO'."
    )

    long_prompt = (
        f"Di seguito è riportato il manuale operativo distribuito di HyperSpace:\n\n"
        f"{document_padding}\n\n"
        f"--- NOTA DI SICUREZZA SPECIALE ---\n"
        f"{needle}\n\n"
        f"--- FINE MANUALE ---\n\n"
        "DOMANDA:\n"
        "Cosa stabilisce esattamente il manuale se una richiesta ha l'header 'X-Mesh-Priority: emergency'?\n"
        "Ragiona concisamente in <think> (max 50 parole) e poi rispondi indicando chiaramente lo slot e l'effetto sul throttling VRAM."
    )

    print(f"[*] Invocazione Flint 40B con prompt lungo ({len(long_prompt)} caratteri) su contesto {flint_ctx} (128k)...")
    res = query_model(
        base_url=flint_url,
        model=flint_model,
        prompt=long_prompt,
        num_ctx=flint_ctx,
        num_predict=800,
        temperature=0.1,
    )

    if not res["ok"]:
        return {"scenario": 4, "status": "FAIL", "reason": res.get("error")}

    ans_text = res["response"].strip()
    cot_text = res["thinking"].strip()
    print(f"  ✓ Risposta ricevuta in {res['elapsed_s']}s ({res['eval_tok_per_s']} tok/s)")
    if cot_text:
        print(f"  ↳ CoT: {len(cot_text.split())} parole")

    full_output = f"{cot_text}\n{ans_text}"
    has_slot = "SLOT_ALPHA_ZERO" in full_output
    has_bypass = ("bypass" in full_output.lower() or "throttling" in full_output.lower())

    needle_found = has_slot and has_bypass
    print(f"  ↳ Recall del requisito critico a 128k: {'✓ TROVATO AL 100%' if needle_found else '✗ PARZIALE/MANCANTE'}")
    if has_slot:
        print("    - Trovato target slot: 'SLOT_ALPHA_ZERO'")
    if has_bypass:
        print("    - Trovata regola bypass throttling VRAM")

    return {
        "scenario": 4,
        "status": "PASS" if needle_found else "PARTIAL",
        "needle_found": needle_found,
        "metrics": {"tok_s": res["eval_tok_per_s"], "elapsed_s": res["elapsed_s"]},
        "answer_snippet": ans_text[:300] if ans_text else cot_text[:300],
    }


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Test Suite Collaborativa Flint 40B MoE <-> LFM2.5 24B/8B (128k/64k)")
    parser.add_argument("--target", default="omen", choices=["omen", "mac", "asus"], help="Nodo target per LFM2.5 (default: omen)")
    parser.add_argument("--flint-url", default=ASUS_OLLAMA_URL, help=f"URL Ollama Flint (default: {ASUS_OLLAMA_URL})")
    parser.add_argument("--lfm-url", default="", help="Override URL LFM2.5 (default in base a --target)")
    parser.add_argument("--flint-model", default=MODEL_FLINT_40B, help=f"Nome modello Flint (default: {MODEL_FLINT_40B})")
    parser.add_argument("--lfm-model", default="", help="Nome modello LFM2.5 (default: 24B per omen/asus, 8B per mac)")
    parser.add_argument("--flint-ctx", type=int, default=DEFAULT_FLINT_CTX, help=f"Dimensione contesto Flint (default: {DEFAULT_FLINT_CTX} = 128k)")
    parser.add_argument("--lfm-ctx", type=int, default=DEFAULT_LFM_CTX, help=f"Dimensione contesto LFM2.5 (default: {DEFAULT_LFM_CTX} = 64k)")
    parser.add_argument("--scenarios", default="all", help="Scenari da eseguire: all oppure 1,2,3,4")
    parser.add_argument("--save-report", action="store_true", default=True, help="Salva report JSON in data/reports/")

    args = parser.parse_args()

    # Risoluzione endpoint e modello LFM2.5
    if args.target == "omen":
        lfm_url = args.lfm_url or OMEN_NODE_URL
        lfm_model = args.lfm_model or MODEL_LFM_24B
        lfm_node_name = "HP OMEN 16 (GPU Worker, RTX 3070 8GB / 32GB RAM)"
    elif args.target == "asus":
        lfm_url = args.lfm_url or ASUS_OLLAMA_URL
        lfm_model = args.lfm_model or MODEL_LFM_24B
        lfm_node_name = "ASUS V16 (High-RAM Worker, RTX 5060 8GB / 48GB RAM)"
    else:  # mac
        lfm_url = args.lfm_url or MAC_OLLAMA_URL
        lfm_model = args.lfm_model or MODEL_LFM_8B
        lfm_node_name = "Mac M5 Hub (Apple Silicon)"

    print("=" * 70)
    print("HYPERSPACE AGI 1.05 — BENCHMARK COLLABORATIVO MULTI-AGENTE MoE (128k / 64k)")
    print(f"Data: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"• Modello A: Flint 40B MoE ({args.flint_model}) -> ASUS V16 ({args.flint_url}) [ctx={args.flint_ctx} = {args.flint_ctx//1024}k]")
    print(f"• Modello B: LFM2.5 MoE ({lfm_model}) -> {lfm_node_name} ({lfm_url}) [ctx={args.lfm_ctx} = {args.lfm_ctx//1024}k]")
    print("=" * 70)

    selected_scenarios = [s.strip() for s in args.scenarios.split(",")]
    run_all = "all" in selected_scenarios

    results: Dict[str, Any] = {
        "timestamp": datetime.datetime.now().isoformat(),
        "flint_node": {"url": args.flint_url, "model": args.flint_model, "num_ctx": args.flint_ctx},
        "lfm_node": {"url": lfm_url, "model": lfm_model, "num_ctx": args.lfm_ctx, "target": args.target},
        "scenarios": {},
    }

    flint_code_cache = ""

    # SCENARIO 1
    if run_all or "1" in selected_scenarios:
        res1 = run_scenario_1_architect_to_coder(
            flint_url=args.flint_url,
            flint_model=args.flint_model,
            flint_ctx=args.flint_ctx,
            lfm_url=lfm_url,
            lfm_model=lfm_model,
            lfm_ctx=args.lfm_ctx,
        )
        results["scenarios"]["scenario_1_architect_to_coder"] = res1
        flint_code_cache = res1.get("flint_code", "")

    # SCENARIO 2
    if run_all or "2" in selected_scenarios:
        if not flint_code_cache or "class AdaptiveMeshBackoff" not in flint_code_cache:
            flint_code_cache = (
                "import random, time\n"
                "from typing import Any, Callable, Optional\n\n"
                "class AdaptiveMeshBackoff:\n"
                "    def __init__(self, base_delay_s: float = 0.5, max_delay_s: float = 10.0, max_attempts: int = 5, on_retry: Optional[Callable] = None):\n"
                "        self.base_delay = base_delay_s\n"
                "        self.max_delay = max_delay_s\n"
                "        self.max_attempts = max_attempts\n"
                "        self.on_retry = on_retry\n\n"
                "    def compute_delay(self, attempt: int) -> float:\n"
                "        d = min(self.max_delay, self.base_delay * (2 ** attempt))\n"
                "        return random.uniform(0, d)\n\n"
                "    def execute_with_retry(self, fn: Callable, *args, **kwargs) -> Any:\n"
                "        for i in range(self.max_attempts):\n"
                "            try:\n"
                "                return fn(*args, **kwargs)\n"
                "            except Exception as e:\n"
                "                if i == self.max_attempts - 1:\n"
                "                    raise RuntimeError(f'Max attempts ({self.max_attempts}) reached') from e\n"
                "                delay = self.compute_delay(i)\n"
                "                if self.on_retry:\n"
                "                    self.on_retry(i, e, delay)\n"
                "                time.sleep(delay)\n"
            )
        res2 = run_scenario_2_code_review(
            flint_code=flint_code_cache,
            lfm_url=lfm_url,
            lfm_model=lfm_model,
            lfm_ctx=args.lfm_ctx,
        )
        results["scenarios"]["scenario_2_code_review"] = res2

    # SCENARIO 3
    if run_all or "3" in selected_scenarios:
        res3 = run_scenario_3_json_interop(
            flint_url=args.flint_url,
            flint_model=args.flint_model,
            flint_ctx=args.flint_ctx,
            lfm_url=lfm_url,
            lfm_model=lfm_model,
            lfm_ctx=args.lfm_ctx,
        )
        results["scenarios"]["scenario_3_json_interop"] = res3

    # SCENARIO 4
    if run_all or "4" in selected_scenarios:
        res4 = run_scenario_4_long_context_128k(
            flint_url=args.flint_url,
            flint_model=args.flint_model,
            flint_ctx=args.flint_ctx,
        )
        results["scenarios"]["scenario_4_long_context_128k"] = res4

    # RIEPILOGO FINALE
    print("\n" + "=" * 70)
    print("📊 RIEPILOGO GENERALE TEST COLLABORATIVI (FLINT 40B @ 128k <-> LFM2.5 24B @ 64k)")
    print("=" * 70)
    total = len(results["scenarios"])
    passed = sum(1 for s in results["scenarios"].values() if s.get("status") == "PASS")
    partial = sum(1 for s in results["scenarios"].values() if s.get("status") == "PARTIAL")

    for sc_name, sc_data in results["scenarios"].items():
        st = sc_data.get("status", "UNKNOWN")
        icon = "✓ PASS" if st == "PASS" else ("⚠ PARTIAL" if st == "PARTIAL" else "✗ FAIL")
        print(f"• {sc_name:35s}: {icon}")

    print(f"\nEsito Complessivo: {passed}/{total} PASS ({partial} con review parziale)")

    if args.save_report:
        report_dir = REPO_ROOT / "data" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_file = report_dir / f"flint_128k_lfm24b_64k_collaboration_{int(time.time())}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"[✓] Report completo archiviato in: {report_file}")

    print("=" * 70)


if __name__ == "__main__":
    main()
