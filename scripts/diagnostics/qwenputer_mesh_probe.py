#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# scripts/diagnostics/qwenputer_mesh_probe.py
"""Diagnostica & Monitoraggio per Qwenputer & In-Weight CPU Execution su Mesh Sovrana.

Scansiona e misura la prontezza dei tre nodi del cluster HyperSpace (Mac M5 Hub,
HP OMEN 16 RTX 3070, ASUS V16 48GB) per l'architettura di compilazione di pesi
RISC-V 32-bit (Qwenputer/Chipformer) e memoria Gated DeltaNet.

Uso:
    .venv/bin/python scripts/diagnostics/qwenputer_mesh_probe.py --all-nodes
    .venv/bin/python scripts/diagnostics/qwenputer_mesh_probe.py --node mac
    .venv/bin/python scripts/diagnostics/qwenputer_mesh_probe.py --node omen
    .venv/bin/python scripts/diagnostics/qwenputer_mesh_probe.py --benchmark
    .venv/bin/python scripts/diagnostics/qwenputer_mesh_probe.py --calc "123456789 * 987654321"
    .venv/bin/python scripts/diagnostics/qwenputer_mesh_probe.py --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.qwenputer_bridge import QwenputerBridge


def run_benchmark(bridge: QwenputerBridge) -> dict:
    """Esegue un benchmark sintetico delle operazioni RISC-V supportate."""
    benchmarks = {}

    # 1. Fibonacci iterativo
    fib_src = """
    li a0, 20
    li t0, 0
    li t1, 1
    fib_loop:
        beqz a0, fib_end
        add t2, t0, t1
        mv t0, t1
        mv t1, t2
        addi a0, a0, -1
        j fib_loop
    fib_end:
    mv a0, t0
    li a7, 93
    ecall
    """
    res_fib = bridge.execute_riscv_asm(fib_src)
    benchmarks["fibonacci_20"] = {
        "success": res_fib.get("success"),
        "result": res_fib.get("a0"),
        "expected": 6765,
        "steps": res_fib.get("steps"),
        "elapsed_ms": res_fib.get("elapsed_ms"),
    }

    # 2. Moltiplicazione a precisione estesa (62 cifre)
    expr = "98765432109876543210 * 12345678901234567890"
    res_calc = bridge.execute_calc_expression(expr)
    benchmarks["bignum_calc_62"] = {
        "success": res_calc.get("success"),
        "expression": expr,
        "result": res_calc.get("result"),
        "elapsed_ms": res_calc.get("elapsed_ms"),
    }

    return benchmarks


def print_cli_report(readiness: dict, bench: dict | None = None, calc_res: dict | None = None):
    print("=" * 72)
    print("  HYPERSPACE AGI - QWENPUTER IN-WEIGHT CPU & MESH READINESS PROBE")
    print(f"  Timestamp: {readiness.get('timestamp')}")
    print("=" * 72)

    cluster_ready = readiness.get("cluster_ready", False)
    badge = "🟢 READY / OPERATIONAL" if cluster_ready else "🟡 DEGRADED / STANDBY"
    print(f"Cluster Status: {badge}\n")

    nodes = readiness.get("nodes", {})
    for node_name, info in nodes.items():
        role = info.get("role", "")
        status = info.get("status", "unknown")
        status_ico = "🟢" if status == "ready" else ("🟡" if "standby" in status else "🔴")
        print(f"[{status_ico}] {node_name.upper()}: {role}")
        for k, v in info.items():
            if k not in ("role", "status"):
                print(f"    • {k}: {v}")
        print()

    if bench:
        print("-" * 72)
        print("  RISC-V IN-WEIGHT BENCHMARK SUITE")
        print("-" * 72)
        for name, data in bench.items():
            succ = "✓ PASS" if data.get("success") else "✗ FAIL"
            ms = data.get("elapsed_ms", 0.0)
            print(f"  [{succ}] {name}: result={data.get('result')} ({ms} ms)")
        print()

    if calc_res:
        print("-" * 72)
        print("  CALC-BRIDGE EXACT COMPUTATION")
        print("-" * 72)
        print(f"  Expr:   {calc_res.get('expression')}")
        print(f"  Result: {calc_res.get('result')}")
        print(f"  Time:   {calc_res.get('elapsed_ms')} ms (Deterministic)")
        print()
    print("=" * 72)


def main():
    parser = argparse.ArgumentParser(description="Qwenputer & In-Weight CPU Mesh Probe")
    parser.add_argument("--all-nodes", action="store_true", help="Scansiona tutti i nodi della mesh")
    parser.add_argument("--node", choices=["mac", "omen", "asus"], help="Filtra per nodo specifico")
    parser.add_argument("--benchmark", action="store_true", help="Esegue suite di benchmark RISC-V")
    parser.add_argument("--calc", type=str, help="Calcola espressione esatta (es. '12345*67890')")
    parser.add_argument("--json", action="store_true", help="Stampa output JSON per Cockpit")
    args = parser.parse_args()

    bridge = QwenputerBridge()
    readiness = bridge.check_mesh_nodes_readiness()

    bench = run_benchmark(bridge) if args.benchmark else None
    calc_res = bridge.execute_calc_expression(args.calc) if args.calc else None

    if args.node:
        key_map = {"mac": "mac_m5_hub", "omen": "hp_omen_16", "asus": "asus_v16"}
        target_key = key_map.get(args.node)
        readiness["nodes"] = {target_key: readiness["nodes"].get(target_key, {})}

    if args.json:
        output_payload = {
            "readiness": readiness,
            "benchmark": bench,
            "calc": calc_res,
        }
        print(json.dumps(output_payload, indent=2))
    else:
        print_cli_report(readiness, bench=bench, calc_res=calc_res)


if __name__ == "__main__":
    main()
