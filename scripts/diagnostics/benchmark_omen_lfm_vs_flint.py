#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
HyperSpace AGI — Benchmark Comparativo su HP OMEN 16:
Liquid AI LFM2.5 24B MoE vs Flint 40B MoE.

Confronto diretto sullo STESSO hardware (HP OMEN 16: RTX 3070 8GB + 32GB RAM):
- Modello A: Liquid AI LFM2.5 24B MoE (Q4_K_M)
- Modello B: Flint 40B MoE (NVFP4, 256 esperti)

Valutazione:
1. Throughput (tokens/s) e Latenza di generazione.
2. Qualità e correttezza sintattica del codice (validazione AST reale).
3. Profondità del Chain-of-Thought (CoT) e gestione degli edge case (concorrenza, clock skew).

Uso:
    .venv/bin/python scripts/diagnostics/benchmark_omen_lfm_vs_flint.py
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
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import requests
from shared.identity import generate_or_load_identity, make_request_headers
from shared.universal_model_parser import UniversalModelParser

OMEN_NODE_URL = os.getenv("OMEN_NODE_URL", "http://100.104.238.125:8081")

MODEL_LFM24B = "hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M"
MODEL_FLINT40B = "flint:latest"

REPORT_FILE = REPO_ROOT / "data" / "reports" / "omen_lfm24b_vs_flint40b_benchmark.json"


def extract_best_python_code(parsed_resp, raw_text: str) -> str:
    candidates = []
    if parsed_resp:
        for b in getattr(parsed_resp, "code_blocks", []):
            if b.language in ("", "python", "py") and b.code.strip():
                candidates.append(b.code.strip())
    matches = re.findall(r"```(?:python)?\s*(.*?)\s*```", raw_text, re.DOTALL)
    for m in matches:
        if m.strip():
            candidates.append(m.strip())

    valid = []
    for c in candidates:
        try:
            ast.parse(c)
            valid.append(c)
        except Exception:
            pass

    if valid:
        return max(valid, key=lambda s: len(s.splitlines()))
    if candidates:
        return max(candidates, key=lambda s: len(s.splitlines()))
    return raw_text


def query_omen_model(
    model: str,
    prompt: str,
    num_ctx: int = 4096,
    num_predict: int = 450,
    temperature: float = 0.2,
    timeout: float = 240.0
) -> Dict[str, Any]:
    """Invia richiesta firmata con ECDSA al nodo OMEN (:8081/execute)."""
    ident = generate_or_load_identity()
    time.sleep(2.0)  # Cooling pause per consentire lo swap del modello in VRAM se necessario

    for attempt in range(1, 4):
        try:
            body_data = {
                "task_id": f"bench-{model[:8]}-{int(time.time()*1000)}",
                "model": model,
                "prompt": prompt,
                "options": {
                    "num_ctx": num_ctx,
                    "num_predict": num_predict,
                    "temperature": temperature
                }
            }
            payload = json.dumps(body_data).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            headers.update(make_request_headers(ident["node_id"], ident["public_key"], ident["_private_key"], body=payload))

            t0 = time.time()
            r = requests.post(f"{OMEN_NODE_URL}/execute", data=payload, headers=headers, timeout=timeout)
            r.raise_for_status()
            elapsed = time.time() - t0
            res = r.json()

            resp_text = res.get("response", "")
            if resp_text.strip().startswith("[OLLAMA ERROR]"):
                raise RuntimeError(f"Ollama error: {resp_text[:120]}")

            eval_count = res.get("eval_count") or (len(resp_text) // 4)
            eval_dur = res.get("eval_duration") or int(elapsed * 1e9)
            tok_s = (eval_count / (eval_dur / 1e9)) if eval_dur > 0 else (eval_count / max(0.1, elapsed))

            parsed = UniversalModelParser.parse(resp_text)
            extracted_code = extract_best_python_code(parsed, resp_text)

            ast_valid = False
            try:
                ast.parse(extracted_code)
                ast_valid = True
            except Exception:
                ast_valid = False

            return {
                "model": model,
                "elapsed_s": round(elapsed, 2),
                "tok_s": round(tok_s, 2),
                "eval_count": eval_count,
                "raw_text": resp_text,
                "cot": parsed.reasoning_cot,
                "cot_len": len(parsed.reasoning_cot),
                "code": extracted_code,
                "code_lines": len(extracted_code.splitlines()),
                "ast_valid": ast_valid
            }
        except Exception as exc:
            wait_s = 6 * attempt
            print(f"  [Tentativo {attempt}/3 per {model} fallito: {exc} — attesa {wait_s}s...]")
            if attempt == 3:
                raise
            time.sleep(wait_s)


def run_benchmark():
    print("\n" + "=" * 76)
    print("⚔️  BENCHMARK QUALITÀ vs VELOCITÀ SU HP OMEN 16 (RTX 3070 8GB + 32GB RAM)")
    print("   LFM2.5 24B MoE  VS  FLINT 40B MoE")
    print("=" * 76)

    # SCENARIO 1: Ingegneria Concorrente (Token Bucket Rate Limiter)
    prompt_s1 = (
        "Sei un Senior Staff Distributed Systems Engineer.\n"
        "Implementa in Python una classe `DistributedTokenBucketRateLimiter` ad altissime prestazioni.\n"
        "Requisiti tecnici stringenti:\n"
        "1. Token bucket con refill continuo float basato su timestamp.\n"
        "2. Gestione edge case di clock skew (se time.time() retrocede, non svuotare o corrompere il bucket).\n"
        "3. Supporto a burst dinamico: metodo `allow_request(key: str, tokens: int = 1) -> bool`.\n"
        "4. Metodo `time_until_available(key: str, tokens: int = 1) -> float` (ritorna 0.0 se disponibile).\n"
        "5. Thread-safety assoluta tramite `threading.RLock()`.\n"
        "Ragiona attentamente in <think> evidenziando i potenziali race condition e come evitarli. "
        "Emetti poi il codice Python completo in blocco ```python ... ```."
    )

    # SCENARIO 2: Audit di Sicurezza & Risoluzione Deadlock
    buggy_code = (
        "class CacheManager:\n"
        "    def __init__(self):\n"
        "        self._lock = threading.Lock()\n"
        "        self._data = {}\n"
        "    def get_or_compute(self, key, fn):\n"
        "        with self._lock:\n"
        "            if key not in self._data:\n"
        "                self._data[key] = self._compute_internal(key, fn)\n"
        "            return self._data[key]\n"
        "    def _compute_internal(self, key, fn):\n"
        "        with self._lock:\n"
        "            return fn(key)\n"
    )
    prompt_s2 = (
        "Sei il Lead Security & Concurrency Auditor.\n"
        "Analizza il seguente snippet Python con race condition e deadlock non-reentrante:\n\n"
        f"```python\n{buggy_code}\n```\n\n"
        "1. Identifica il bug critico di concorrenza e spiega formalmente perché va in deadlock.\n"
        "2. Fornisci la versione corretta e blindata con `threading.RLock()` e gestione eccezioni se `fn` fallisce.\n"
        "Ragiona in <think>. Emetti il codice corretto in blocco ```python ... ```."
    )

    scenarios = [
        ("Scenario 1: Algoritmica Concorrente (Token Bucket)", prompt_s1, 450),
        ("Scenario 2: Deep Bug Audit (Deadlock Detection)", prompt_s2, 400),
    ]

    results = []

    for sc_name, prompt, max_tokens in scenarios:
        print("\n" + "#" * 76)
        print(f"▶ {sc_name.upper()}")
        print("#" * 76)

        # 1. Test LFM2.5 24B
        print(f"\n[1/2] Esecuzione su Liquid AI LFM2.5 24B MoE...")
        res_lfm = query_omen_model(MODEL_LFM24B, prompt, num_predict=max_tokens)
        print(f"  ✓ LFM2.5 24B: {res_lfm['tok_s']} tok/s ({res_lfm['eval_count']} token in {res_lfm['elapsed_s']}s) | AST: {'PASS' if res_lfm['ast_valid'] else 'FAIL'} ({res_lfm['code_lines']} righe)")

        # 2. Test Flint 40B MoE
        print(f"\n[2/2] Esecuzione su Flint 40B MoE (256 esperti)...")
        res_flint = query_omen_model(MODEL_FLINT40B, prompt, num_predict=max_tokens)
        print(f"  ✓ Flint 40B:  {res_flint['tok_s']} tok/s ({res_flint['eval_count']} token in {res_flint['elapsed_s']}s) | AST: {'PASS' if res_flint['ast_valid'] else 'FAIL'} ({res_flint['code_lines']} righe)")

        results.append({
            "scenario": sc_name,
            "lfm24b": res_lfm,
            "flint40b": res_flint
        })

    # Analisi aggregata e tabella comparativa
    print("\n" + "=" * 76)
    print("📊 MATRICE COMPARATIVA DEFINITIVA SU HP OMEN 16")
    print("=" * 76)

    avg_lfm_speed = round(sum(r["lfm24b"]["tok_s"] for r in results) / len(results), 2)
    avg_flint_speed = round(sum(r["flint40b"]["tok_s"] for r in results) / len(results), 2)
    speed_ratio = round(avg_lfm_speed / max(0.1, avg_flint_speed), 2)

    total_lfm_lines = sum(r["lfm24b"]["code_lines"] for r in results)
    total_flint_lines = sum(r["flint40b"]["code_lines"] for r in results)

    lfm_ast_all = all(r["lfm24b"]["ast_valid"] for r in results)
    flint_ast_all = all(r["flint40b"]["ast_valid"] for r in results)

    avg_lfm_cot = int(sum(r["lfm24b"]["cot_len"] for r in results) / len(results))
    avg_flint_cot = int(sum(r["flint40b"]["cot_len"] for r in results) / len(results))

    print(f"{'CRITERIO DI VALUTAZIONE':<30} | {'LFM2.5 24B MoE':<20} | {'FLINT 40B MoE':<20}")
    print("-" * 76)
    print(f"{'Throughput Medio (Velocità)':<30} | {str(avg_lfm_speed) + ' tok/s':<20} | {str(avg_flint_speed) + ' tok/s':<20}")
    print(f"{'Vantaggio Velocità (Speedup)':<30} | {str(speed_ratio) + 'x più veloce':<20} | {'1.00x (Baseline)':<20}")
    print(f"{'Validità Sintattica AST':<30} | {'100% PASS' if lfm_ast_all else 'PARZIALE':<20} | {'100% PASS' if flint_ast_all else 'PARZIALE':<20}")
    print(f"{'Righe di Codice Prodotte':<30} | {str(total_lfm_lines) + ' righe':<20} | {str(total_flint_lines) + ' righe':<20}")
    print(f"{'Profondità Reasoning CoT':<30} | {str(avg_lfm_cot) + ' caratteri':<20} | {str(avg_flint_cot) + ' caratteri':<20}")
    print(f"{'Comportamento su RTX 3070':<30} | {'VRAM + CPU RAM':<20} | {'VRAM + CPU RAM (FP4)':<20}")
    print("=" * 76)

    # Salva report
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    report_data = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "hardware": "HP OMEN 16 (RTX 3070 8GB VRAM + 32GB RAM)",
        "endpoint": OMEN_NODE_URL,
        "summary": {
            "avg_tok_s_lfm24b": avg_lfm_speed,
            "avg_tok_s_flint40b": avg_flint_speed,
            "speedup_lfm_vs_flint": speed_ratio,
            "ast_valid_lfm24b": lfm_ast_all,
            "ast_valid_flint40b": flint_ast_all,
            "total_code_lines_lfm24b": total_lfm_lines,
            "total_code_lines_flint40b": total_flint_lines,
            "avg_cot_length_lfm24b": avg_lfm_cot,
            "avg_cot_length_flint40b": avg_flint_cot
        },
        "scenarios": results
    }
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    print(f"\n✓ Report salvato in: {REPORT_FILE}")


if __name__ == "__main__":
    run_benchmark()
