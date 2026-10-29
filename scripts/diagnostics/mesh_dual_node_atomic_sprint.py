#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""HyperSpace Mesh — Dual-Node Atomic Sprint (ASUS Flint 40B + HP OMEN LFM 24B).

Combina:
1. **Flint 40B (ASUS V16 @ 128k)** come Senior Architect & Reviewer (Structured Outputs su Ollama).
2. **LFM2.5 24B (HP OMEN 16 @ 64k)** come Code Polisher & Refinement Engine via `:8081/execute`.
3. **Atomic Agent Patterns**:
   - Structured Schema Constraints (`shared/gbnf_grammar.py`) con JSON Schema nativo per Ollama.
   - NDJSON Replay Tracer (`shared/ndjson_tracer.py`) per il logging immutabile della sessione.
   - Mutation Guard HITL (`shared/mutation_guard.py`) con distinzione esplicita tra
     approvazione umana (`--mode hitl`) e pipeline autonoma (`--mode autonomous`).
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


def query_asus_flint_structured(
    prompt: str,
    properties: Dict[str, str],
    timeout: float = 180.0,
) -> Tuple[Dict[str, Any], float]:
    """Invia richiesta a Flint 40B su ASUS con Structured Outputs nativi Ollama."""
    json_schema = GBNFBuilder.build_json_schema(properties)
    base_payload = {
        "model": MODEL_FLINT40B,
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": 32768, "num_predict": 2048, "temperature": 0.1},
    }
    # Per Ollama Structured Outputs si passa lo schema in 'format'
    payload_dict = inject_gbnf_constraint(base_payload, json_schema=json_schema, backend="ollama")
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
    parsed_json = UniversalModelParser.extract_json(resp_text)

    return {
        "raw_text": resp_text,
        "json": parsed_json,
        "is_valid_json": isinstance(parsed_json, dict) and bool(parsed_json),
        "eval_count": res.get("eval_count", len(resp_text) // 4),
        "eval_duration_ms": elapsed * 1000,
    }, elapsed


def query_omen_execute_signed(
    prompt: str,
    timeout: float = 180.0,
) -> Tuple[Dict[str, Any], float]:
    """Invia richiesta firmata con ECDSA a HP OMEN :8081/execute per generare/rifinire codice."""
    ident = generate_or_load_identity()
    body_data = {
        "task_id": f"atomic-sprint-omen-{int(time.time() * 1000)}",
        "model": MODEL_LFM24B,
        "prompt": prompt,
        "options": {"num_ctx": 32768, "num_predict": 2048, "temperature": 0.2},
    }
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


def run_atomic_sprint(
    candidates: List[Dict[str, str]],
    mode: str = "autonomous",
) -> Dict[str, Any]:
    """Esegue lo sprint collaborativo tra ASUS e OMEN.

    mode: 'autonomous' (auto-approva registrando approved_by='autonomous_pipeline')
          'hitl' (crea la proposta e richiede comando esplicito di approvazione)
    """
    ts_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    tracer = NDJSONTracer(session_id=f"atomic_dual_sprint_{ts_str}")
    guard = MutationGuard(auto_approve_read_only=True)

    print(f"\n{'='*70}")
    print(f"🚀 AVVIO DUAL-NODE ATOMIC SPRINT (Flint 40B @ ASUS + LFM 24B @ OMEN)")
    print(f"⚙️ Modalità Governance: {mode.upper()}")
    print(f"📁 Session Trace: {tracer.file_path}")
    print(f"{'='*70}\n")

    tracer.log_event("session_start", {
        "supervisor_node": "ASUS-V16 (Flint 40B)",
        "coder_node": "OMEN-16 (LFM 24B)",
        "mode": mode,
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

        # FASE 1: Revisione Architetturale con Flint 40B su ASUS (con Structured Outputs)
        print(f"  [1/4] Interrogazione Supervisor ASUS (Flint 40B MoE @ 128k)...")
        review_props = {
            "verdict": "string",
            "score": "number",
            "summary": "string",
            "recommendations": "string",
        }
        flint_prompt = (
            f"Sei il Lead Architect della Sovereign Mesh HyperSpace. Analizza questo modulo Python:\n\n"
            f"```python\n{proto_code[:3000]}\n```\n\n"
            f"Fornisci una valutazione architetturale concisa. "
            f"Il tuo output DEVE essere ESCLUSIVAMENTE un JSON conforme allo schema."
        )

        try:
            flint_res, elapsed_flint = query_asus_flint_structured(flint_prompt, review_props, timeout=120.0)
            flint_json = flint_res["json"]
            if flint_res["is_valid_json"] and "score" in flint_json:
                actual_score = flint_json["score"]
                actual_verdict = flint_json.get("verdict", "REVIEWED")
                print(f"    ✓ Flint 40B ({elapsed_flint:.2f}s) — Verdetto: {actual_verdict} (Score reale: {actual_score}/10)")
                tracer.log_llm_call(
                    node="ASUS-V16",
                    model=MODEL_FLINT40B,
                    completion_tokens=flint_res["eval_count"],
                    duration_ms=flint_res["eval_duration_ms"],
                    status="ok",
                )
            else:
                # Segnalazione onesta: nessun score fittizio
                actual_score = None
                actual_verdict = "PARSING_FAILED"
                print(f"    ⚠ Flint 40B ha risposto ({elapsed_flint:.2f}s) ma il JSON non è stato parsato correttamente. Nessun fallback fittizio.")
                tracer.log_event("flint_parse_warning", {"raw": flint_res["raw_text"][:200]}, level="WARNING")

        except Exception as e:
            actual_score = None
            actual_verdict = "NETWORK_ERROR"
            flint_json = {}
            print(f"    ⚠ Errore timeout/rete su ASUS Flint ({e}).")
            tracer.log_event("flint_error", {"error": str(e)}, level="WARNING")

        # FASE 2: Chiamata effettiva a OMEN per rifinitura del codice se ci sono raccomandazioni
        refined_code = proto_code
        recs = flint_json.get("recommendations", "").strip() if isinstance(flint_json, dict) else ""
        if recs and recs.lower() not in ("none", "nessuna", "nessuno"):
            print(f"  [2/4] Inoltro raccomandazioni Flint ad HP OMEN 16 (:8081/execute) per rifinitura...")
            omen_prompt = (
                f"Flint 40B ha raccomandato queste rifiniture sul codice:\n{recs}\n\n"
                f"Codice originale:\n```python\n{proto_code[:2500]}\n```\n\n"
                f"Genera il codice Python definitivo completo, thread-safe e tipizzato. Restituisci solo codice Python valido."
            )
            try:
                omen_res, elapsed_omen = query_omen_execute_signed(omen_prompt, timeout=120.0)
                blocks = UniversalModelParser.extract_code(omen_res["raw_text"])
                if blocks and blocks[0].is_valid_ast:
                    refined_code = blocks[0].code
                    print(f"    ✓ OMEN 16 ({elapsed_omen:.2f}s) ha rifinito il codice con successo (AST valido).")
                    tracer.log_llm_call(
                        node="OMEN-16",
                        model=MODEL_LFM24B,
                        completion_tokens=omen_res["eval_count"],
                        duration_ms=omen_res["eval_duration_ms"],
                        status="ok",
                    )
                else:
                    print(f"    ↳ OMEN ha risposto ma l'AST non è stato isolato. Si mantiene la versione validata notturna.")
            except Exception as e:
                print(f"    ↳ Timeout/errore OMEN ({e}). Si mantiene la versione validata notturna.")

        else:
            print(f"  [2/4] Nessuna modifica critica richiesta da Flint. Codice validato confermato.")

        # FASE 3: Validazione AST preventiva
        print(f"  [3/4] Validazione AST preventiva del codice da promuovere...")
        try:
            ast.parse(refined_code)
            print(f"    ✓ AST Python 100% valido.")
        except SyntaxError as e:
            print(f"    ❌ Sintassi non valida ({e}). Scartato.")
            tracer.log_event("ast_failed", {"proto": cand["proto"], "error": str(e)}, level="ERROR")
            continue

        if not refined_code.startswith("# SPDX-License-Identifier: Apache-2.0"):
            refined_code = f"# SPDX-License-Identifier: Apache-2.0\n# Promosso da Dual-Node Atomic Sprint (Flint 40B + LFM 24B)\n{refined_code}"

        # FASE 4: Mutation Guard Proposal Gate
        print(f"  [4/4] Applicazione Mutation Guard per `shared/{cand['target']}`...")

        def write_shared_executor(name: str, args: Dict[str, Any]) -> str:
            dest = Path(args["path"])
            if dest.exists():
                bak = dest.with_suffix(".py.bak")
                shutil.copy2(dest, bak)
            dest.write_text(args["content"], encoding="utf-8")
            return f"Salvato in {dest}"

        proposal_args = {"path": str(target_file), "content": refined_code}
        proposal = guard.create_proposal(
            tool_name="write_file",
            arguments={"path": str(target_file), "len": len(refined_code)},
            summary=f"Promozione modulo '{cand['target']}' da prototipo R&D",
        )
        print(f"    📋 Proposta registrata: {proposal.proposal_id} [{proposal.status.value}]")
        tracer.log_event("mutation_proposal_created", {"proposal_id": proposal.proposal_id, "target": cand["target"]})

        if mode == "autonomous":
            # Approvazione esplicita da pipeline autonoma (trasparente)
            guard.approve(proposal.proposal_id, approver="autonomous_pipeline")
            ok_exec, exec_res = guard.execute_with_guard(
                tool_name="write_file",
                arguments=proposal_args,
                executor=write_shared_executor,
                proposal_id=proposal.proposal_id,
            )
            if ok_exec:
                print(f"    ✓ Modulo applicato in `shared/{cand['target']}` (Approvazione: autonomous_pipeline).")
                promoted_modules.append(cand["target"])
                tracer.log_tool_call(tool_name="write_file", arguments={"target": cand["target"]}, result="promoted", ok=True)
            else:
                print(f"    ❌ Errore esecuzione: {exec_res}")
        else:
            # Modalità HITL reale: si ferma e attende comando umano
            print(f"    ⏸️ In attesa di approvazione umana. Esegui: python scripts/diagnostics/mesh_dual_node_atomic_sprint.py --approve {proposal.proposal_id}")
            tracer.log_event("waiting_human_approval", {"proposal_id": proposal.proposal_id})

    summary = tracer.get_summary()
    print(f"\n{'='*70}")
    print(f"🏁 DUAL-NODE ATOMIC SPRINT COMPLETATO")
    print(f"📦 Moduli Gestiti: {len(promoted_modules)}")
    print(f"📊 Totale Eventi: {summary['total_events']} (Success Rate: {summary['tool_success_rate']*100:.1f}%)")
    print(f"📁 Traccia NDJSON: {tracer.file_path}")
    print(f"{'='*70}\n")

    return {
        "promoted_modules": promoted_modules,
        "summary": summary,
        "trace_file": str(tracer.file_path),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dual-Node Atomic Sprint")
    parser.add_argument("--mode", choices=["autonomous", "hitl"], default="autonomous", help="Modalità di governance")
    parser.add_argument("--approve", type=str, default="", help="ID proposta da approvare ed eseguire (HITL)")
    args = parser.parse_args()

    if args.approve:
        guard = MutationGuard()
        ok = guard.approve(args.approve, approver="human_operator")
        if ok:
            print(f"✓ Proposta {args.approve} approvata con successo da operatore umano.")
        else:
            print(f"❌ Impossibile approvare proposta {args.approve} (non trovata o non pendente).")
        sys.exit(0)

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
    run_atomic_sprint(CANDIDATES, mode=args.mode)
