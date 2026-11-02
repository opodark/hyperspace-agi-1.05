#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# scripts/diagnostics/resin_mesh_probe.py
"""Strumento diagnostico per il substrato d'inferenza Resin (HyperSpace 1.06).

Esegue:
1. Verifica della prontezza del crate Rust `resin-core` / `resin-py` e dei nodi mesh
   (Mac M5 Hub MLX, HP OMEN 16 CUDA, ASUS V16 48GB Slab Pool).
2. Simulazione transazionale dello scheduler Rust con layout ibrido `HISTORY` (KV cache)
   + `STATE` (Gated DeltaNet / Qwenputer RAM) e verifica di prefix caching LRU.

Istruzioni d'uso:
  .venv/bin/python scripts/diagnostics/resin_mesh_probe.py --all-nodes --simulate-hybrid
  .venv/bin/python scripts/diagnostics/resin_mesh_probe.py --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.resin_bridge import ResinBridge


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnostica del substrato d'inferenza Resin (HyperSpace 1.06)."
    )
    parser.add_argument(
        "--all-nodes",
        action="store_true",
        help="Interroga tutti i nodi della mesh (Mac M5, HP OMEN 16, ASUS V16)",
    )
    parser.add_argument(
        "--simulate-hybrid",
        action="store_true",
        help="Esegue una simulazione reale dello scheduler Rust con cache ibrida HISTORY + STATE e prefix cache",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Stampa l'output completo in formato JSON strutturato",
    )
    args = parser.parse_args()

    bridge = ResinBridge()
    substrate = bridge.get_substrate_info()
    readiness = bridge.check_mesh_nodes_readiness()
    hybrid_sim = bridge.simulate_hybrid_slab_schedule() if (args.simulate_hybrid or not args.all_nodes) else None

    payload = {
        "substrate": substrate,
        "mesh_readiness": readiness,
        "hybrid_slab_simulation": hybrid_sim,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0 if substrate["native_extension_ready"] else 1

    print("=" * 72)
    print("  HYPERSPACE AGI 1.06 - RESIN RUST INFERENCE SUBSTRATE PROBE")
    print(f"  Timestamp: {readiness['timestamp']}")
    print("=" * 72)
    print(
        f"Substrate: resin v{substrate['version']} @ {substrate['pinned_commit'][:10]} "
        f"({'🟢 READY' if substrate['native_extension_ready'] else '🔴 NOT BUILT'})"
    )
    print(f"Crates:    {', '.join(substrate['rust_crates'])}")
    print(f"Runners:   {', '.join(substrate['model_runner_packages'])}")
    print(f"Skills:    {', '.join(substrate['bundled_skills'])}")
    print()

    for node_key, info in readiness["nodes"].items():
        badge = "🟢" if info.get("status") == "ready" else "🟡"
        print(f"[{badge}] {node_key.upper()}: {info.get('role')}")
        for k, v in info.items():
            if k not in ("role", "status"):
                print(f"    • {k}: {v}")
        print()

    if hybrid_sim:
        print("-" * 72)
        print("  HYBRID SLAB POOL (KV HISTORY + DELTANET STATE) & PREFIX CACHE")
        print("-" * 72)
        if hybrid_sim.get("success"):
            pstats = hybrid_sim["prefix_cache_stats"]
            print(f"  Verdict:            {hybrid_sim['verdict']} (in {hybrid_sim['elapsed_ms']} ms)")
            print(f"  Plans executed:     {hybrid_sim['plans_executed']}")
            print(f"  STATE checkpoints:  {hybrid_sim['state_checkpoints_committed']} committed, {hybrid_sim['state_restores_executed']} restored")
            print(
                f"  Prefix Cache LRU:   {pstats['hits']} hits, {pstats['misses']} misses, "
                f"{pstats['cached_blocks']} cached blocks"
            )
            print(f"  Schedule SHA-256:   {hybrid_sim['schedule_hash']}")
        else:
            print(f"  Errore: {hybrid_sim.get('error') or hybrid_sim}")
        print()

    print("=" * 72)
    return 0 if substrate["native_extension_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
