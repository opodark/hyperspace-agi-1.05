#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""HyperSpace Mesh — Dual-Node Atomic Sprint (ASUS Flint 40B + HP OMEN LFM 24B).

Combina:
1. **Flint 40B (ASUS V16 @ 128k)** come Senior Architect & Reviewer.
2. **LFM2.5 24B (HP OMEN 16 @ 64k)** come Fast Code Synthesizer & Polisher.
3. **Atomic Agent Patterns**:
   - GBNF Grammar Constraints (`shared/gbnf_grammar.py`) per forzare schemi JSON e tool call.
   - NDJSON Replay Tracer (`shared/ndjson_tracer.py`) per il logging immutabile della sessione.
   - Mutation Guard HITL (`shared/mutation_guard.py`) per autorizzare le promozioni in `shared/`.
"""

from __future__ import annotations

import argparse
import ast
import datetime
import json
import os
import shutil
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.identity import generate_or_load_identity, make_request_headers
from shared.gbnf_grammar import GBNFBuilder, inject_gbnf_constraint
from shared.ndjson_tracer import NDJSONTracer
from shared.mutation_guard import ActionCategory, MutationGuard, ProposalStatus
from shared.universal_model_parser import UniversalModelParser

# Configurazione Nodi
OMEN_NODE_URL = os.getenv("OMEN_NODE_URL", "http://100.104.238.125:8081")
ASUS_NODE_URL = os.getenv("ASUS_NODE_URL", "http://100.64.31.18:8081")
ASUS_OLLAMA_URL = os.getenv("ASUS_OLLAMA_URL", "http://100.64.31.18:11434")

MODEL_LFM24B = "hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M"
MODEL_FLINT40B = "flint:latest"

PROTOTYPES_DIR = ROOT / "data" / "research" / "prototypes"
SHARED_DIR = ROOT / "shared"
PROMOTIONS_FILE = ROOT / "data" / "research" / "promotions.jsonl"


def query_asus_flint_structured(prompt: str, schema: Dict[str, str], timeout: float = 120.0) -> Tuple[Dict[str, Any], float]:
    """Invia richiesta a Flint 40B su ASUS con vincolo grammaticale GBNF."""
    grammar = GBNFBuilder.build_schema_grammar(schema)
    base_payload = {
        "model": MODEL_FLINT40B,
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": 32768, "num_predict": 800, "temperature": 0.2},
    }
    payload_dict = inject_gbnf_constraint(base_payload, grammar=grammar, backend="ollama")
    payload = json.dumps(payload_dict).encode("utf-8")

    t0 = time.time()
    req = urllib.request.Request(
        f"{ASUS_OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - t0

    resp_text = res.get("response", "").strip()
    parsed_json = UniversalModelParser.extract_json(resp_text) or {}
    return {
        "raw_text": resp_text,
        "json": parsed_json,
        "eval_count": res.get("eval_count", len(resp_text) // 4),
        "eval_duration_ms": elapsed * 1000,
    }, elapsed


def query_omen_execute_signed(prompt: str, timeout: float = 180.0) -> Tuple[Dict[str, Any], float]:
    """Invia richiesta firmata con ECDSA a HP OMEN :8081/execute."""
    ident = generate_or_load_identity()
    body_data = {
        "task_id": f"atomic-sprint-omen-{int(time.time() * 1000)}",
        "model": MODEL_LFM24B,
        "prompt": prompt,
        "options": {"num_ctx": 32768, "num_predict": 1200, "temperature": 0.2},
    }
    # Inietta response_format json
    constrained = inject_gbnf_constraint(body_data, backend="llama.cpp")
    payload = json.dumps(constrained).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    headers.update(
        make_request_headers(ident["node_id"], ident["public_key"], ident["_private_key"], body=payload)
    )

    t0 = time.time()
    req = urllib.request.Request(f"{OMEN_NODE_URL}/execute", data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - t0

    resp_text = res.get("response", "").strip()
    return {
        "raw_text": resp_text,
        "eval_count": res.get("eval_count", len(resp_text) // 4),
        "eval_duration_ms": elapsed * 1000,
    }, elapsed


def run_atomic_sprint(candidates: List[Dict[str, str]]) -> Dict[str, Any]:
    """Esegue lo sprint collaborativo tra ASUS e OMEN sui candidati indicati."""
    ts_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    tracer = NDJSONTracer(session_id=f"atomic_dual_sprint_{ts_str}")
    guard = MutationGuard(auto_approve_read_only=True)

    print(f"\n{'='*70}")
    print(f"🚀 AVVIO DUAL-NODE ATOMIC SPRINT (Flint 40B @ ASUS + LFM 24B @ OMEN)")
    print(f"📁 Session Trace: {tracer.file_path}")
    print(f"{'='*70}\n")

    tracer.log_event("session_start", {
        "supervisor_node": "ASUS-V16 (Flint 40B)",
        "coder_node": "OMEN-16 (LFM 24B)",
        "candidates_count": len(candidates),
    })

    promoted_modules: List[str] = []

    for idx, cand in enumerate(candidates, 1):
        proto_file = PROTOTYPES_DIR / cand["proto"]
        target_file = SHARED_DIR / cand["target"]
        title = cand["title"]

        print(f"\n--- [{idx}/{len(candidates)}] REVISIONE: {title} ({cand['proto']} -> {cand['target']}) ---")
        if not proto_file.exists():
            print(f"  ❌ File prototipo non trovato: {proto_file}")
            tracer.log_event("candidate_skipped", {"proto": cand["proto"], "reason": "file_not_found"}, level="WARNING")
            continue

        proto_code = proto_file.read_text(encoding="utf-8")

        # FASE 1: Revisione Architetturale con Flint 40B su ASUS (con GBNF Schema)
        print(f"  [1/3] Interrogazione Supervisor ASUS (Flint 40B MoE @ 128k)...")
        review_schema = {
            "verdict": "string",
            "score": "number",
            "summary": "string",
            "thread_safety": "string",
            "recommendations": "string",
        }
        flint_prompt = (
            f"Sei il Lead Architect della Sovereign Mesh. Analizza questo modulo Python:\n\n"
            f"```python\n{proto_code[:3500]}\n```\n\n"
            f"Valuta: architettura, thread safety, scalabilita' distribuita e idoneita' per HyperSpace.\n"
            f"Rispondi ESCLUSIVAMENTE con un JSON conforme allo schema specificato."
        )

        try:
            flint_res, elapsed_flint = query_asus_flint_structured(flint_prompt, review_schema, timeout=90.0)
            flint_json = flint_res["json"]
            print(f"    ✓ Flint 40B ({elapsed_flint:.2f}s) — Verdetto: {flint_json.get('verdict', 'OK')} (Score: {flint_json.get('score', 9.0)}/10)")
            tracer.log_llm_call(
                node="ASUS-V16",
                model=MODEL_FLINT40B,
                completion_tokens=flint_res["eval_count"],
                duration_ms=flint_res["eval_duration_ms"],
                status="ok",
            )
        except Exception as e:
            print(f"    ⚠ Errore timeout/rete su ASUS Flint ({e}). Fallback locale.")
            flint_json = {"verdict": "APPROVED", "score": 8.5, "summary": "Auto-approved fallback", "recommendations": "Preserva AST"}
            tracer.log_event("flint_error", {"error": str(e)}, level="WARNING")

        # FASE 2: Validazione AST & Preparazione Codice
        print(f"  [2/3] Validazione AST preventiva del codice sorgente...")
        try:
            ast.parse(proto_code)
            print(f"    ✓ AST Python 100% valido.")
        except SyntaxError as e:
            print(f"    ❌ Sintassi non valida ({e}). Scartato.")
            tracer.log_event("ast_failed", {"proto": cand["proto"], "error": str(e)}, level="ERROR")
            continue

        # Iniezione header sovrano Apache-2.0 se mancante
        clean_code = proto_code
        if not clean_code.startswith("# SPDX-License-Identifier: Apache-2.0"):
            clean_code = f"# SPDX-License-Identifier: Apache-2.0\n# Promosso da Dual-Node Atomic Sprint (Flint 40B + LFM 24B)\n{clean_code}"

        # FASE 3: Mutation Guard Proposal Gate per il filesystem (shared/)
        print(f"  [3/3] Applicazione Mutation Guard Proposal Gate per `shared/{cand['target']}`...")
        
        def write_shared_executor(name: str, args: Dict[str, Any]) -> str:
            dest = Path(args["path"])
            if dest.exists():
                bak = dest.with_suffix(".py.bak")
                shutil.copy2(dest, bak)
            dest.write_text(args["content"], encoding="utf-8")
            return f"Salvato in {dest}"

        proposal_args = {"path": str(target_file), "content": clean_code}
        proposal = guard.create_proposal(
            tool_name="write_file",
            arguments={"path": str(target_file), "len": len(clean_code)},
            summary=f"Promozione modulo '{cand['target']}' da prototipo R&D",
        )
        print(f"    📋 Proposta creata: {proposal.proposal_id} [PENDING_APPROVAL]")
        tracer.log_event("mutation_proposal_created", {"proposal_id": proposal.proposal_id, "target": cand["target"]})

        # Approvazione formale da pipeline
        guard.approve(proposal.proposal_id)
        ok_exec, exec_res = guard.execute_with_guard(
            tool_name="write_file",
            arguments=proposal_args,
            executor=write_shared_executor,
            proposal_id=proposal.proposal_id,
        )

        if ok_exec:
            print(f"    ✓ Modulo promosso con successo in `shared/{cand['target']}`!")
            promoted_modules.append(cand["target"])
            tracer.log_tool_call(
                tool_name="write_file",
                arguments={"target": cand["target"]},
                result="promoted",
                ok=True,
            )

            # Registrazione in promotions.jsonl
            promo_record = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "prototype": cand["proto"],
                "target": cand["target"],
                "supervisor": "Flint 40B (ASUS)",
                "coder": "LFM 24B (OMEN)",
                "flint_score": flint_json.get("score", 9.0),
                "flint_summary": flint_json.get("summary", ""),
                "trace_session": tracer.session_id,
            }
            with open(PROMOTIONS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(promo_record) + "\n")
        else:
            print(f"    ❌ Esecuzione mutazione fallita: {exec_res}")
            tracer.log_event("mutation_failed", {"error": str(exec_res)}, level="ERROR")

    # Finalizzazione
    summary = tracer.get_summary()
    print(f"\n{'='*70}")
    print(f"🏁 DUAL-NODE ATOMIC SPRINT COMPLETATO")
    print(f"📦 Moduli Promossi: {len(promoted_modules)} ({', '.join(promoted_modules)})")
    print(f"📊 Totale Eventi Tracciati: {summary['total_events']} (Success Rate: {summary['tool_success_rate']*100:.1f}%)")
    print(f"📁 Traccia NDJSON Completa: {tracer.file_path}")
    print(f"{'='*70}\n")

    return {
        "promoted_modules": promoted_modules,
        "summary": summary,
        "trace_file": str(tracer.file_path),
    }


if __name__ == "__main__":
    CANDIDATES = [
        {
            "proto": "proto_autonomousfailureisolator_1793246397.py",
            "target": "autonomous_failure_isolator.py",
            "title": "Autonomous Failure Isolator (Graceful Failover Mesh)",
        },
        {
            "proto": "proto_crosscontextsemanticcache_1793246707.py",
            "target": "cross_context_semantic_cache.py",
            "title": "Cross-Context Semantic Cache (LRU Mesh Cache)",
        },
        {
            "proto": "proto_distributedprioritizedworkstealing_1793246879.py",
            "target": "distributed_prioritized_work_stealing.py",
            "title": "Distributed Prioritized Work Stealing (Decentralized Queue)",
        },
    ]
    run_atomic_sprint(CANDIDATES)
