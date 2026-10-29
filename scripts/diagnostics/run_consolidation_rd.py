#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Runner per la Sessione di Consolidamento e R&D HyperSpace Mesh.

1. Esegue verifiche preliminari su nodi e contratti di rete.
2. Invia i prototipi selezionati al Dual-Node Atomic Sprint (Flint 40B @ ASUS + LFM 24B @ OMEN).
3. Esegue la revisione con Structured Outputs nativi e inoltra le raccomandazioni a OMEN.
4. Esegue il deployment sicuro tramite Mutation Guard.
5. Esegue la suite Pytest post-deploy.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.diagnostics.mesh_dual_node_atomic_sprint import run_atomic_sprint

CANDIDATES = [
    {
        "proto": "proto_dynamicmeshtopologyoptimizer_1793244200.py",
        "target": "dynamic_mesh_topology_optimizer.py",
        "title": "Dynamic Mesh Topology Optimizer (Heuristic P2P Adjacency Matrix)",
    },
    {
        "proto": "proto_zeroknowledgetaskattestation_1793246506.py",
        "target": "zero_knowledge_task_attestation.py",
        "title": "Zero-Knowledge Task Attestation (Cryptographic Task Proofs)",
    },
]

if __name__ == "__main__":
    print(f"\n{'='*70}")
    print(f"🔥 INIZIO SESSIONE DI CONSOLIDAMENTO E R&D SOVRANA")
    print(f"{'='*70}\n")

    t0 = time.time()
    result = run_atomic_sprint(CANDIDATES, mode="autonomous")
    elapsed = time.time() - t0

    print(f"\n{'='*70}")
    print(f"🧪 ESECUZIONE SUITE DI VERIFICA TEST")
    print(f"{'='*70}\n")

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_mesh_consolidation_rd.py",
        "tests/test_promoted_atomic_sprint_modules.py",
        "tests/test_atomic_agent_patterns.py",
        "tests/test_licensing.py",
        "-v",
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        print(f"❌ Test falliti con exit code {proc.returncode}:\n{proc.stderr}")
        sys.exit(proc.returncode)

    print(f"\n✅ CONSOLIDAMENTO E R&D COMPLETATI CON SUCCESSO IN {elapsed:.2f}s!")
