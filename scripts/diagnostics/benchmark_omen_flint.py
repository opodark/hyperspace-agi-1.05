#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
HyperSpace AGI — Benchmark Comparativo Head-to-Head:
Flint 40B MoE (HP OMEN 16 vs ASUS V16).

Confronta le prestazioni di inferenza del modello Flint 40B MoE:
- HP OMEN 16: RTX 3070 8GB VRAM + 32GB RAM (via Node API :8081 con firma ECDSA)
- ASUS V16: RTX 5060 8GB VRAM + 48GB RAM (via Ollama API :11434)

Uso:
    .venv/bin/python scripts/diagnostics/benchmark_omen_flint.py --watch
    .venv/bin/python scripts/diagnostics/benchmark_omen_flint.py --prompt "Spiega il pattern Circuit Breaker in Python"
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import requests
from shared.identity import generate_or_load_identity, make_request_headers

OMEN_NODE_URL = os.getenv("OMEN_NODE_URL", "http://100.104.238.125:8081")
ASUS_OLLAMA_URL = os.getenv("ASUS_OLLAMA_URL", "http://100.64.31.18:11434")
MODEL_FLINT = "flint:latest"
REPORT_FILE = REPO_ROOT / "data" / "reports" / "flint_omen_vs_asus_benchmark.json"


def check_omen_flint_installed() -> bool:
    """Interroga OMEN per verificare se flint:latest è pronto."""
    ident = generate_or_load_identity()
    body_data = {
        "task_id": f"ping-flint-{int(time.time()*1000)}",
        "model": MODEL_FLINT,
        "prompt": "ping",
        "options": {"num_ctx": 1024, "num_predict": 2}
    }
    payload = json.dumps(body_data).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    headers.update(make_request_headers(ident["node_id"], ident["public_key"], ident["_private_key"], body=payload))

    try:
        r = requests.post(f"{OMEN_NODE_URL}/execute", data=payload, headers=headers, timeout=15)
        if r.status_code == 200:
            resp_text = r.json().get("response", "")
            if "404 Not Found" not in resp_text and "[OLLAMA ERROR]" not in resp_text:
                return True
            if "pulling" in resp_text.lower() or "downloading" in resp_text.lower():
                return False
        return False
    except Exception:
        return False


def wait_for_omen_flint(poll_interval: int = 15, timeout: int = 1800) -> bool:
    """Attende che il download/installazione di flint su OMEN sia completato."""
    print(f"[*] Monitoraggio installazione `{MODEL_FLINT}` su HP OMEN ({OMEN_NODE_URL})...")
    t0 = time.time()
    while time.time() - t0 < timeout:
        ready = check_omen_flint_installed()
        elapsed_m = round((time.time() - t0) / 60.0, 1)
        if ready:
            print(f"\n✓ Flint 40B MoE è pronto su HP OMEN dopo {elapsed_m} minuti!")
            return True
        print(f"  ... in attesa del completamento del pull su OMEN ({elapsed_m} min trascorsi)...", end="\r")
        time.sleep(poll_interval)
    print("\n⚠ Timeout attesa installazione OMEN superato.")
    return False


def query_omen_flint(prompt: str, num_ctx: int = 4096, num_predict: int = 300, timeout: float = 180.0) -> Dict[str, Any]:
    """Invia prompt a Flint su HP OMEN via :8081 con firma crittografica."""
    ident = generate_or_load_identity()
    body_data = {
        "task_id": f"bench-flint-omen-{int(time.time()*1000)}",
        "model": MODEL_FLINT,
        "prompt": prompt,
        "options": {"num_ctx": num_ctx, "num_predict": num_predict, "temperature": 0.2}
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
    eval_count = res.get("eval_count") or (len(resp_text) // 4)
    eval_dur = res.get("eval_duration") or int(elapsed * 1e9)
    tok_s = (eval_count / (eval_dur / 1e9)) if eval_dur > 0 else (eval_count / max(0.1, elapsed))

    return {
        "node": "HP OMEN 16",
        "hardware": "RTX 3070 8GB VRAM + 32GB RAM",
        "text": resp_text,
        "elapsed_s": round(elapsed, 2),
        "tok_s": round(tok_s, 2),
        "eval_count": eval_count,
        "num_ctx": num_ctx
    }


def query_asus_flint(prompt: str, num_ctx: int = 4096, num_predict: int = 300, timeout: float = 180.0) -> Dict[str, Any]:
    """Invia prompt a Flint su ASUS V16 via :11434."""
    payload = json.dumps({
        "model": MODEL_FLINT,
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": num_ctx, "num_predict": num_predict, "temperature": 0.2}
    }).encode("utf-8")

    t0 = time.time()
    r = requests.post(f"{ASUS_OLLAMA_URL}/api/generate", data=payload, headers={"Content-Type": "application/json"}, timeout=timeout)
    r.raise_for_status()
    elapsed = time.time() - t0
    res = r.json()

    resp_text = res.get("response", "")
    thinking_text = res.get("thinking", "")
    full_text = resp_text if resp_text.strip() else thinking_text

    eval_count = res.get("eval_count") or (len(full_text) // 4)
    eval_dur = res.get("eval_duration") or int(elapsed * 1e9)
    tok_s = (eval_count / (eval_dur / 1e9)) if eval_dur > 0 else (eval_count / max(0.1, elapsed))

    return {
        "node": "ASUS V16",
        "hardware": "RTX 5060 8GB VRAM + 48GB RAM",
        "text": full_text,
        "elapsed_s": round(elapsed, 2),
        "tok_s": round(tok_s, 2),
        "eval_count": eval_count,
        "num_ctx": num_ctx
    }


def run_head_to_head_benchmark(prompt: str, num_predict: int = 350):
    print("\n" + "=" * 76)
    print("🚀 BENCHMARK COMPARATIVO FLINT 40B MoE: HP OMEN 16 vs ASUS V16")
    print("=" * 76)
    print(f"Prompt di test: \"{prompt[:80]}...\"")
    print(f"Token target: {num_predict}\n")

    # 1. Test ASUS V16
    print("[1/2] Esecuzione benchmark su ASUS V16 (RTX 5060 + 48GB)...")
    res_asus = query_asus_flint(prompt, num_ctx=4096, num_predict=num_predict)
    print(f"  ✓ ASUS: {res_asus['tok_s']} tok/s ({res_asus['eval_count']} token in {res_asus['elapsed_s']}s)")

    # 2. Test HP OMEN 16
    print("\n[2/2] Esecuzione benchmark su HP OMEN 16 (RTX 3070 + 32GB)...")
    res_omen = query_omen_flint(prompt, num_ctx=4096, num_predict=num_predict)
    print(f"  ✓ OMEN: {res_omen['tok_s']} tok/s ({res_omen['eval_count']} token in {res_omen['elapsed_s']}s)")

    # Tabella Comparativa
    speedup = round(res_omen['tok_s'] / max(0.1, res_asus['tok_s']), 2)
    delta_s = round(res_omen['elapsed_s'] - res_asus['elapsed_s'], 2)

    print("\n" + "#" * 76)
    print("📊 RISULTATI COMPARATIVI HEAD-TO-HEAD")
    print("#" * 76)
    print(f"{'PARAMETRO':<28} | {'ASUS V16 (RTX 5060)':<22} | {'HP OMEN 16 (RTX 3070)':<22}")
    print("-" * 76)
    print(f"{'Throughput (tok/s)':<28} | {str(res_asus['tok_s']) + ' tok/s':<22} | {str(res_omen['tok_s']) + ' tok/s':<22}")
    print(f"{'Tempo Totale':<28} | {str(res_asus['elapsed_s']) + ' s':<22} | {str(res_omen['elapsed_s']) + ' s':<22}")
    print(f"{'Token Generati':<28} | {str(res_asus['eval_count']):<22} | {str(res_omen['eval_count']):<22}")
    print(f"{'Hardware':<28} | {'RTX 5060 + 48GB':<22} | {'RTX 3070 + 32GB':<22}")
    print(f"{'Rapporto Velocità OMEN/ASUS':<28} | {'1.00x (Baseline)':<22} | {str(speedup) + 'x':<22}")
    print("#" * 76)

    # Salva report
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    report_data = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model": MODEL_FLINT,
        "prompt": prompt,
        "asus": res_asus,
        "omen": res_omen,
        "comparison": {
            "omen_speedup_vs_asus": speedup,
            "delta_seconds": delta_s
        }
    }
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    print(f"\n✓ Report dettagliato salvato in: {REPORT_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flint 40B MoE OMEN vs ASUS Benchmark")
    parser.add_argument("--watch", action="store_true", help="Attende che il download su OMEN sia completato prima del benchmark")
    parser.add_argument("--check-only", action="store_true", help="Controlla solo se Flint è già pronto su OMEN")
    parser.add_argument("--prompt", type=str, default="Scrivi una classe ThreadSafeCache con eviction LRU e locking rientrante in Python.", help="Prompt per il test")
    parser.add_argument("--tokens", type=int, default=300, help="Numero di token da generare")
    args = parser.parse_args()

    if args.check_only:
        installed = check_omen_flint_installed()
        print(f"Flint 40B MoE su HP OMEN: {'PRONTO' if installed else 'NON ANCORA PRONTO (DOWNLOAD IN CORSO)'}")
        sys.exit(0 if installed else 1)

    if args.watch:
        ready = wait_for_omen_flint()
        if not ready:
            sys.exit(1)

    if not check_omen_flint_installed():
        print(f"⚠ `{MODEL_FLINT}` non è ancora disponibile su HP OMEN. Usa l'opzione `--watch` per attendere la fine del download.")
        sys.exit(1)

    run_head_to_head_benchmark(prompt=args.prompt, num_predict=args.tokens)
