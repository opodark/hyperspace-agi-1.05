#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# scripts/diagnostics/qwenputer_mesh_probe.py
"""Diagnostica & Monitoraggio per Qwenputer, Ispezione ELF32 RV32IM & Clean-Room REA.

Scansiona e misura la prontezza dei tre nodi del cluster HyperSpace (Mac M5 Hub,
HP OMEN 16 RTX 3070, ASUS V16 48GB), ispeziona staticamente binari ELF32 RV32IM
soft-float e collauda il ciclo Clean-Room REA -> Qwenputer.

Uso:
    .venv/bin/python scripts/diagnostics/qwenputer_mesh_probe.py --all-nodes
    .venv/bin/python scripts/diagnostics/qwenputer_mesh_probe.py --benchmark
    .venv/bin/python scripts/diagnostics/qwenputer_mesh_probe.py --calc "123456789 * 987654321"
    .venv/bin/python scripts/diagnostics/qwenputer_mesh_probe.py --inspect-elf scratch/qwenputer/experimental/riscv/tests/data/rv/c-crc32.elf
    .venv/bin/python scripts/diagnostics/qwenputer_mesh_probe.py --disassemble scratch/qwenputer/experimental/riscv/tests/data/rv/c-crc32.elf:main
    .venv/bin/python scripts/diagnostics/qwenputer_mesh_probe.py --rea-cleanroom-demo
    .venv/bin/python scripts/diagnostics/qwenputer_mesh_probe.py --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.qwenputer_bridge import QwenputerBridge


def run_benchmark(bridge: QwenputerBridge) -> dict:
    """Esegue un benchmark sintetico delle operazioni RISC-V supportate."""
    benchmarks = {}

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
        "trace_hash": res_fib.get("trace_hash"),
        "elapsed_ms": res_fib.get("elapsed_ms"),
    }

    expr = "98765432109876543210 * 12345678901234567890"
    res_calc = bridge.execute_calc_expression(expr)
    benchmarks["bignum_calc_62"] = {
        "success": res_calc.get("success"),
        "expression": expr,
        "result": res_calc.get("result"),
        "steps_executed": res_calc.get("steps_executed"),
        "trace_hash": res_calc.get("trace_hash"),
        "elapsed_ms": res_calc.get("elapsed_ms"),
    }

    return benchmarks


def run_rea_cleanroom_demo(bridge: QwenputerBridge) -> dict:
    """Dimostra la verifica Clean-Room partendo dal job reale Ghidra 4c8555419121 di REA."""
    parse_input_rv32 = """
        mv t0, a0
        li a0, 0
        lb t1, 0(t0)
        beqz t1, done
    loop:
        addi t0, t0, 1
        addi t1, t1, 6
        add a0, a0, t1
        lb t1, 0(t0)
        bnez t1, loop
    done:
        li a7, 93
        ecall
    """
    vectors = [
        {
            "name": "string_ciao",
            "initial_regs": {"a0": 0x100},
            "initial_mem": {0x100: b"ciao\x00"},
            "expected_regs": {"a0": 436},
            "expected_exit_code": 436,
        },
        {
            "name": "empty_string",
            "initial_regs": {"a0": 0x100},
            "initial_mem": {0x100: b"\x00"},
            "expected_regs": {"a0": 0},
            "expected_exit_code": 0,
        },
        {
            "name": "single_char_A",
            "initial_regs": {"a0": 0x100},
            "initial_mem": {0x100: b"A\x00"},
            "expected_regs": {"a0": 71},
            "expected_exit_code": 71,
        },
    ]
    job_path = ROOT / "data" / "rea" / "jobs" / "4c8555419121"
    if job_path.exists():
        return bridge.prepare_rea_cleanroom_bundle(
            job_path, asm_source=parse_input_rv32, test_vectors=vectors
        )
    return bridge.verify_cleanroom_equivalence(parse_input_rv32, vectors)


def print_cli_report(
    readiness: dict,
    bench: dict | None = None,
    calc_res: dict | None = None,
    elf_info: dict | None = None,
    disasm_info: dict | None = None,
    cleanroom_info: dict | None = None,
):
    print("=" * 72)
    print("  HYPERSPACE AGI - QWENPUTER IN-WEIGHT CPU & REA CLEAN-ROOM PROBE")
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
            th = (data.get("trace_hash") or "")[:16]
            print(f"  [{succ}] {name}: result={data.get('result')} ({ms} ms, trace={th}...)")
        print()

    if calc_res:
        print("-" * 72)
        print("  CALC-BRIDGE RV32IM + BIGNUM EXECUTION")
        print("-" * 72)
        print(f"  Expr:   {calc_res.get('expression')}")
        print(f"  Result: {calc_res.get('result')}")
        print(f"  Steps:  {calc_res.get('steps_executed')} RV32IM instructions")
        print(f"  Trace:  {calc_res.get('trace_hash')}")
        print(f"  Time:   {calc_res.get('elapsed_ms')} ms")
        print()

    if elf_info:
        print("-" * 72)
        print("  STATIC ELF32 RV32IM INSPECTION")
        print("-" * 72)
        t = elf_info.get("target", {})
        h = elf_info.get("elf_header", {})
        aud = elf_info.get("instruction_audit", {})
        print(f"  File:        {t.get('name')} ({t.get('bytes')} B, sha256={t.get('sha256', '')[:16]}...)")
        print(f"  Entry:       {h.get('entry_point')} | Float ABI: {h.get('float_abi')}")
        print(f"  REA Ghidra:  {h.get('rea_ghidra_lane_admitted')} | Qwenputer ROM-map: {h.get('qwenputer_rom_map_compatible')}")
        print(f"  Symbols:     {elf_info.get('symbols', {}).get('functions_count')} functions, {elf_info.get('symbols', {}).get('objects_count')} objects")
        print(f"  Instr count: {aud.get('total_non_zero_instructions')} (illegal={aud.get('illegal_instructions_count')}, bignum={aud.get('custom_bignum_instructions_count')})")
        print()

    if disasm_info and disasm_info.get("success"):
        print("-" * 72)
        print(f"  RV32IM DISASSEMBLY: {disasm_info.get('function')} @ {disasm_info.get('start_addr')}")
        print("-" * 72)
        for ins in disasm_info.get("instructions", [])[:25]:
            print(f"  {ins['addr']}: {ins['word']}  {ins['mnemonic']}")
        print()

    if cleanroom_info:
        print("-" * 72)
        print("  REA x QWENPUTER CLEAN-ROOM VERIFICATION")
        print("-" * 72)
        prov = cleanroom_info.get("static_provenance", {})
        ver = cleanroom_info.get("cleanroom_verification") or cleanroom_info
        if prov:
            print(f"  REA Job:     {prov.get('rea_job_id')} ({prov.get('operation')} {prov.get('argument')})")
            print(f"  Target SHA:  {prov.get('target_sha256')}")
            print(f"  Evidence ID: {prov.get('rea_evidence_id')}")
        print(f"  Verdict:     {cleanroom_info.get('verdict')} ({ver.get('vectors_passed')}/{ver.get('vectors_total')} vectors)")
        print(f"  Trace Hash:  {ver.get('composite_trace_hash')}")
        print()
    print("=" * 72)


def main():
    parser = argparse.ArgumentParser(description="Qwenputer & In-Weight CPU Mesh Probe")
    parser.add_argument("--all-nodes", action="store_true", help="Scansiona tutti i nodi della mesh")
    parser.add_argument("--node", choices=["mac", "omen", "asus"], help="Filtra per nodo specifico")
    parser.add_argument("--benchmark", action="store_true", help="Esegue suite di benchmark RISC-V")
    parser.add_argument("--calc", type=str, help="Calcola espressione esatta su calc-bridge.elf")
    parser.add_argument("--inspect-elf", type=str, help="Ispeziona staticamente un binario ELF32 RV32IM")
    parser.add_argument("--disassemble", type=str, help="Disassembla <elf_path>:<func_or_addr>")
    parser.add_argument("--rea-cleanroom-demo", action="store_true", help="Esegue demo Clean-Room REA -> Qwenputer")
    parser.add_argument("--json", action="store_true", help="Stampa output JSON per Cockpit")
    args = parser.parse_args()

    bridge = QwenputerBridge()
    readiness = bridge.check_mesh_nodes_readiness()

    bench = run_benchmark(bridge) if args.benchmark else None
    calc_res = bridge.execute_calc_expression(args.calc) if args.calc else None
    elf_info = bridge.inspect_rv32_elf(args.inspect_elf) if args.inspect_elf else None
    disasm_info = None
    if args.disassemble and ":" in args.disassemble:
        elf_p, sym = args.disassemble.rsplit(":", 1)
        disasm_info = bridge.disassemble_rv32_function(elf_p, sym)
    cleanroom_info = run_rea_cleanroom_demo(bridge) if args.rea_cleanroom_demo else None

    if args.node:
        key_map = {"mac": "mac_m5_hub", "omen": "hp_omen_16", "asus": "asus_v16"}
        target_key = key_map.get(args.node)
        readiness["nodes"] = {target_key: readiness["nodes"].get(target_key, {})}

    if args.json:
        output_payload = {
            "readiness": readiness,
            "benchmark": bench,
            "calc": calc_res,
            "elf_inspection": elf_info,
            "disassembly": disasm_info,
            "cleanroom": cleanroom_info,
        }
        print(json.dumps(output_payload, indent=2))
    else:
        print_cli_report(
            readiness,
            bench=bench,
            calc_res=calc_res,
            elf_info=elf_info,
            disasm_info=disasm_info,
            cleanroom_info=cleanroom_info,
        )


if __name__ == "__main__":
    main()
