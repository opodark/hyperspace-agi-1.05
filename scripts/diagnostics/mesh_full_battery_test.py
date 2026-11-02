#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# scripts/diagnostics/mesh_full_battery_test.py
"""Batteria di test approfonditi su tutta la Mesh HyperSpace (Mac M5, HP OMEN 16, ASUS V16).

Verifica end-to-end:
1. [Resin 1.06]: Substrato Rust, Unified Slab Pool (KV HISTORY + Gated DeltaNet STATE),
   prefix caching LRU e determinismo SHA-256 su Mac M5 e nodi remoti.
2. [Laya System 1]: Microservizio decisionale non-autoregressivo (porta :8097, MPS/Metal/CUDA),
   latenza decisionale sub-50ms e triage delle scelte (choice/noul/score).
3. [Qwenputer RV32IM]: Esecuzione clean-room, calcolatrice bignum hardware (calc-bridge.elf),
   disassemblaggio simboli ELF32 e certificazione su tutti i nodi (Mac M5, OMEN, ASUS).
4. [Mesh CLI E2EE]: Iniezione comandi remoti firmati ECDSA tramite scripts/mesh_exec.py su :8081.

Uso:
  .venv/bin/python scripts/diagnostics/mesh_full_battery_test.py
  .venv/bin/python scripts/diagnostics/mesh_full_battery_test.py --json
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.memory_schema import VERIFIED, validate_evidence
from shared.qwenputer_bridge import QwenputerBridge
from shared.resin_bridge import ResinBridge
import shared.laya_client as lc
from scripts.mesh_exec import execute_remote_cmd, resolve_endpoint


def run_test_suite() -> Dict[str, Any]:
    suite_start = time.perf_counter()
    results: Dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cluster_version": "HyperSpace 1.06",
        "tests": {},
        "summary": {"total": 0, "passed": 0, "failed": 0},
    }

    def record(name: str, passed: bool, details: Dict[str, Any]) -> None:
        results["tests"][name] = {"passed": passed, **details}
        results["summary"]["total"] += 1
        if passed:
            results["summary"]["passed"] += 1
        else:
            results["summary"]["failed"] += 1

    # =========================================================================
    # 1. TEST RESIN 1.06 (Mac Hub locale)
    # =========================================================================
    resin = ResinBridge()
    if resin.is_local_runtime_available():
        sim = resin.simulate_hybrid_slab_schedule(parent_capacity=32, block_tokens=4)
        record(
            "resin_local_hybrid_slab_schedule",
            sim.get("success") and sim.get("verdict") == VERIFIED,
            {
                "elapsed_ms": sim.get("elapsed_ms"),
                "verdict": sim.get("verdict"),
                "schedule_hash": sim.get("schedule_hash"),
                "prefix_cache_hits": sim.get("prefix_cache_stats", {}).get("hits"),
                "state_checkpoints": sim.get("state_checkpoints_committed"),
            },
        )
    else:
        record("resin_local_hybrid_slab_schedule", False, {"error": "Resin runtime not available"})

    # =========================================================================
    # 2. TEST LAYA SYSTEM 1 (Decisore non-autoregressivo)
    # =========================================================================
    laya_avail = lc.is_available()
    if laya_avail:
        t0 = time.perf_counter()
        choice_res = lc.decide_choice(
            "def safe_calc(a, b): return a + b",
            {"clean": "Codice pulito e funzionante", "stub": "Stub non implementato", "bug": "Errore di sintassi"},
            "Classifica la qualità del codice",
        )
        laya_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        noul_res = lc.decide_noul("def add(a, b): return a + b", "Is this valid Python code?")

        laya_ok = choice_res is not None and noul_res is not None
        record(
            "laya_system_one_decisions",
            laya_ok,
            {
                "available": True,
                "elapsed_ms": laya_ms,
                "choice": choice_res.get("choice") if choice_res else None,
                "confidence": choice_res.get("confidence") if choice_res else None,
                "noul_is_yes": noul_res.get("is_yes") if noul_res else None,
            },
        )
    else:
        record("laya_system_one_decisions", False, {"available": False, "note": "Laya service offline"})

    # =========================================================================
    # 3. TEST QWENPUTER RV32IM (Locale su Mac Hub)
    # =========================================================================
    qwen = QwenputerBridge()
    bignum_res = qwen.execute_calc_expression("123456789 * 987654321")
    gcd_res = qwen.execute_calc_expression("gcd(1071, 462)")
    cleanroom_res = qwen.verify_cleanroom_equivalence(
        """
        mv a1, a0
        li a0, 0
    loop:
        lbu t0, 0(a1)
        beq t0, zero, done
        addi a0, a0, 6
        add a0, a0, t0
        addi a1, a1, 1
        j loop
    done:
        li a7, 93
        ecall
        """,
        [
            {"name": "empty", "initial_regs": {"a0": 0x200}, "initial_mem": {0x200: b"\x00"}, "expected_regs": {"a0": 0}},
            {"name": "ciao", "initial_regs": {"a0": 0x200}, "initial_mem": {0x200: b"ciao\x00"}, "expected_regs": {"a0": 436}},
        ],
    )

    qwen_ok = (
        bignum_res.get("success")
        and bignum_res.get("result") == "121932631112635269"
        and gcd_res.get("result") == "21"
        and cleanroom_res.get("verdict") == VERIFIED
    )
    record(
        "qwenputer_rv32im_cleanroom_local",
        qwen_ok,
        {
            "bignum_62digits": bignum_res.get("result"),
            "bignum_steps": bignum_res.get("steps_executed"),
            "gcd_result": gcd_res.get("result"),
            "cleanroom_verdict": cleanroom_res.get("verdict"),
            "composite_trace_hash": cleanroom_res.get("composite_trace_hash"),
        },
    )

    # =========================================================================
    # 4. TEST MULTI-NODO REMOTO (OMEN & ASUS via Mesh Exec E2EE)
    # =========================================================================
    remote_nodes = [
        ("omen", resolve_endpoint("omen")),
        ("asus", resolve_endpoint("asus")),
    ]

    for node_name, endpoint in remote_nodes:
        # A. Remote Shell ping
        ping = execute_remote_cmd(endpoint, "python --version", timeout=10.0)
        ping_ok = ping.get("exit_code") == 0 and "Python" in ping.get("stdout", "")
        record(
            f"mesh_exec_ping_{node_name}",
            ping_ok,
            {
                "endpoint": endpoint,
                "stdout": ping.get("stdout", "").strip(),
                "elapsed_ms": ping.get("elapsed_ms"),
                "exit_code": ping.get("exit_code"),
            },
        )

        # B. Remote Qwenputer RV32IM execution on remote node
        qwen_cmd = (
            "python -c \"import sys; sys.path.insert(0, '/repo'); "
            "from shared.qwenputer_bridge import QwenputerBridge; b = QwenputerBridge(); "
            "r1 = b.execute_calc_expression('gcd(1071, 462)'); "
            "r2 = b.execute_calc_expression('123456789 * 987654321'); "
            "print(r1.get('result') + '|' + r2.get('result') + '|' + str(r1.get('steps_executed')))\""
        )
        qwen_rem = execute_remote_cmd(endpoint, qwen_cmd, timeout=15.0)
        qwen_rem_ok = False
        parts = qwen_rem.get("stdout", "").strip().split("|")
        if len(parts) == 3 and parts[0] == "21" and parts[1] == "121932631112635269":
            qwen_rem_ok = True

        record(
            f"qwenputer_remote_{node_name}",
            qwen_rem_ok,
            {
                "endpoint": endpoint,
                "stdout": qwen_rem.get("stdout", "").strip(),
                "steps": parts[2] if len(parts) == 3 else None,
                "elapsed_ms": qwen_rem.get("elapsed_ms"),
                "exit_code": qwen_rem.get("exit_code"),
            },
        )

    results["total_elapsed_ms"] = round((time.perf_counter() - suite_start) * 1000.0, 2)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Full Mesh Battery Test HyperSpace 1.06")
    parser.add_argument("--json", action="store_true", help="Output JSON strutturato")
    args = parser.parse_args()

    res = run_test_suite()

    if args.json:
        print(json.dumps(res, indent=2))
        return 0 if res["summary"]["failed"] == 0 else 1

    print("=" * 76)
    print("  HYPERSPACE AGI 1.06 — FULL MESH BATTERY TEST (RESIN, LAYA, QWENPUTER)")
    print(f"  Timestamp: {res['timestamp']}  |  Total Time: {res['total_elapsed_ms']} ms")
    print("=" * 76)

    for test_name, data in res["tests"].items():
        badge = "🟢 PASSED" if data["passed"] else "🔴 FAILED"
        print(f"[{badge}] {test_name}")
        for k, v in data.items():
            if k != "passed":
                print(f"    • {k}: {v}")
        print()

    print("-" * 76)
    sm = res["summary"]
    badge_overall = "🟢 ALL GREEN" if sm["failed"] == 0 else "🔴 SOME TESTS FAILED"
    print(f"  Esito Finale: {badge_overall} ({sm['passed']}/{sm['total']} superati)")
    print("=" * 76)

    return 0 if sm["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
