#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# scripts/nightly_omen_orchestrator.py
"""Orchestratore Notturno Autonomo per HP OMEN 16 (HyperSpace AGI).

Coordina i compiti a calcolo intensivo durante la finestra notturna (23:00 - 08:00),
sfruttando l'alimentazione da rete elettrica continua (AC) e la GPU RTX 3070 dell'OMEN 16:
1. Verifica sicurezza termica (check `data/thermal_pause.flag`).
2. Consolidamento memorie e tick dei sogni notturni.
3. Refresh incrementale del grafo di conoscenza (Graphify).
4. Cicli di stress test CoT con generazione di codice e validazione AST Python.

Uso:
    python scripts/nightly_omen_orchestrator.py --once
    python scripts/nightly_omen_orchestrator.py --dry-run
    python scripts/nightly_omen_orchestrator.py --daemon --interval 600
"""

import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, Optional

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OMEN_NODE = "http://100.104.238.125:8081"
DEFAULT_OMEN_CP = "http://100.104.238.125:8085"
THERMAL_FLAG = ROOT / "data" / "thermal_pause.flag"
RUNS_LOG = ROOT / "data" / "nightly_omen_runs.jsonl"


def is_night_window(start_hour: int = 23, end_hour: int = 8) -> bool:
    """Verifica se l'ora locale corrente cade nella finestra notturna (23:00 - 08:00)."""
    current_hour = datetime.datetime.now().hour
    if start_hour > end_hour:
        return current_hour >= start_hour or current_hour < end_hour
    return start_hour <= current_hour < end_hour


def check_thermal_safety() -> bool:
    """Restituisce False se la macchina è in allerta termica (GPU > 82°C)."""
    if THERMAL_FLAG.exists():
        try:
            flag_info = THERMAL_FLAG.read_text(encoding="utf-8").strip()
            print(f"[NIGHTLY] ⚠️ Allerta termica rilevata ({flag_info}). Task notturni in pausa.")
        except Exception:
            pass
        return False
    return True


def check_omen_node_readiness(node_url: str = DEFAULT_OMEN_NODE) -> Optional[Dict[str, Any]]:
    """Verifica lo stato di alimentazione e disponibilità dell'OMEN."""
    try:
        r = requests.get(f"{node_url.rstrip('/')}/status", timeout=4)
        if r.status_code == 200:
            data = r.json()
            is_ac = data.get("power", {}).get("ac_line", True)
            if not is_ac:
                print("[NIGHTLY] ⚠️ OMEN sta operando a batteria! I task pesanti vengono congelati.")
                return None
            return data
    except Exception as e:
        print(f"[NIGHTLY] Impossibile contattare l'OMEN a {node_url}: {e}")
    return None


def run_dream_tick(cp_url: str = DEFAULT_OMEN_CP) -> Dict[str, Any]:
    print("[NIGHTLY] 🌙 Esecuzione Tick Sogno Notturno...")
    try:
        r = requests.post(f"{cp_url.rstrip('/')}/dreams/nightly/tick", timeout=15)
        return {"status_code": r.status_code, "response": r.text[:120]}
    except Exception as e:
        return {"status_code": None, "error": str(e)}


def run_graphify_refresh() -> Dict[str, Any]:
    print("[NIGHTLY] 🕸️ Aggiornamento Knowledge Graph (Graphify)...")
    graphify_script = ROOT / "scripts" / "graphify_surface.py"
    if not graphify_script.exists():
        return {"skipped": True, "reason": "script assente"}
    python_bin = sys.executable
    cmd = [python_bin, str(graphify_script), "--incremental", "--quiet"]
    try:
        start = time.perf_counter()
        res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=180)
        elapsed = round(time.perf_counter() - start, 1)
        return {"returncode": res.returncode, "elapsed_s": elapsed}
    except subprocess.TimeoutExpired:
        return {"timeout": True}
    except Exception as e:
        return {"error": str(e)}


def run_cot_stress_benchmarks(cycles: int = 2) -> Dict[str, Any]:
    print(f"[NIGHTLY] ⚡ Esecuzione {cycles} cicli CoT Stress Test su OMEN RTX 3070...")
    bench_script = ROOT / "scripts" / "diagnostics" / "stress_test_omen_cot.py"
    if not bench_script.exists():
        return {"skipped": True, "reason": "stress_test_omen_cot.py non trovato"}
    python_bin = sys.executable
    cmd = [python_bin, str(bench_script), "--cycles", str(cycles)]
    try:
        start = time.perf_counter()
        res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=300)
        elapsed = round(time.perf_counter() - start, 1)
        return {"returncode": res.returncode, "elapsed_s": elapsed, "output_snippet": res.stdout[-200:] if res.stdout else ""}
    except subprocess.TimeoutExpired:
        return {"timeout": True}
    except Exception as e:
        return {"error": str(e)}


def execute_nightly_pipeline(node_url: str, cp_url: str, force: bool = False, cycles: int = 2) -> Dict[str, Any]:
    run_record: Dict[str, Any] = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "node_url": node_url,
        "completed": False,
        "results": {},
    }

    if not force and not is_night_window():
        print("[NIGHTLY] Fuori dalla finestra notturna (23:00 - 08:00). Usa --force per eseguire subito.")
        run_record["skipped"] = "outside_night_window"
        return run_record

    if not check_thermal_safety():
        run_record["skipped"] = "thermal_pause_active"
        return run_record

    node_status = check_omen_node_readiness(node_url)
    if not node_status:
        run_record["skipped"] = "node_not_ready_or_battery"
        return run_record

    print(f"[NIGHTLY] Inizio sessione autonoma su OMEN (Tier: {node_status.get('tier')}, VRAM: {node_status.get('vram_gb')} GB)")

    # 1. Sogno Notturno
    run_record["results"]["dream_tick"] = run_dream_tick(cp_url)

    # 2. Graphify Knowledge Graph
    run_record["results"]["graphify"] = run_graphify_refresh()

    # 3. CoT Stress Test & AST Code Verification
    run_record["results"]["cot_benchmark"] = run_cot_stress_benchmarks(cycles=cycles)

    run_record["completed"] = True
    print(f"[NIGHTLY] ✅ Sessione notturna completata con successo at {run_record['timestamp']}.")

    # Registra log
    RUNS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUNS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(run_record) + "\n")

    return run_record


def main():
    parser = argparse.ArgumentParser(description="Orchestratore Notturno per HP OMEN 16")
    parser.add_argument("--node-url", default=DEFAULT_OMEN_NODE, help=f"URL del nodo (default: {DEFAULT_OMEN_NODE})")
    parser.add_argument("--cp-url", default=DEFAULT_OMEN_CP, help=f"URL del Control Plane (default: {DEFAULT_OMEN_CP})")
    parser.add_argument("--force", "--once", action="store_true", help="Esegui subito ignorando la finestra oraria")
    parser.add_argument("--cycles", type=int, default=2, help="Cicli CoT da eseguire per benchmark (default: 2)")
    parser.add_argument("--daemon", action="store_true", help="Esegui in loop continuo da demone notturno")
    parser.add_argument("--interval", type=int, default=1800, help="Intervallo fra i cicli in daemon mode (default: 1800s)")
    args = parser.parse_args()

    while True:
        execute_nightly_pipeline(args.node_url, args.cp_url, force=args.force, cycles=args.cycles)
        if args.daemon:
            time.sleep(args.interval)
        else:
            break


if __name__ == "__main__":
    main()
