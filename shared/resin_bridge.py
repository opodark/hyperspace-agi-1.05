# SPDX-License-Identifier: Apache-2.0
# shared/resin_bridge.py
"""Bridge Sovrano per Resin (HyperSpace 1.06 Inference Substrate).

Integra il substrato modulare in Rust `ekzhang/resin` (Apache-2.0) come fondamenta
del motore d'inferenza di HyperSpace 1.06:
1. [Headless Rust Engine (`resin-core`)]: Scheduler transazionale di batch, admission
   control, chunked prefill e zero-overhead overlap separato dall'esecuzione hardware.
2. [Unified Slab Cache Pool (KV + SWA + Recurrent STATE)]: Allocatore a pagine unificato
   che gestisce sia la KV cache d'attenzione (`CacheGroupFamily.HISTORY`) sia gli stati
   ricorrenti lineari Gated DeltaNet / Qwenputer (`CacheGroupFamily.STATE`) con snapshot
   immutabili di prefisso (LRU block trie).
3. [Multi-Backend Runners]: Supporto nativo per Apple Silicon Metal (`resin_models_mlx`,
   es. Qwen3.5-MoE), NVIDIA CUDA (`resin_models_cuda`, es. DeepSeek-V4.1, GLM-5.3) e
   riferimento PyTorch (`resin_models_torch`).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.memory_schema import REFUTED, VERIFIED, validate_evidence

RESIN_DIR = Path(os.getenv("RESIN_DIR", str(ROOT / "modules" / "resin")))
RESIN_PINNED_COMMIT = "3f68b0a5024859e0f7cef8b7a348adb8c3293c5d"

if RESIN_DIR.exists() and str(RESIN_DIR) not in sys.path:
    sys.path.insert(0, str(RESIN_DIR))

OMEN_NODE_URL = os.getenv("OMEN_NODE_URL", "http://100.104.238.125:8081").rstrip("/")
ASUS_NODE_URL = os.getenv("ASUS_NODE_URL", "http://100.64.31.18:8081").rstrip("/")


class ResinBridge:
    """Interfaccia sovrana verso il substrato d'inferenza Rust `resin` per HyperSpace 1.06."""

    def __init__(self, resin_dir: Optional[Path] = None) -> None:
        self.resin_dir = Path(resin_dir) if resin_dir else RESIN_DIR
        if self.resin_dir.exists() and str(self.resin_dir) not in sys.path:
            sys.path.insert(0, str(self.resin_dir))

    def is_local_runtime_available(self) -> bool:
        """Verifica se il binding nativo Rust `resin._resin` è compilato e importabile."""
        try:
            import resin  # noqa: F401
            return hasattr(resin, "Engine") and hasattr(resin, "CacheLayout")
        except Exception:
            return False

    def get_substrate_info(self) -> Dict[str, Any]:
        """Restituisce i metadati architetturali del substrato Resin 1.06 installato."""
        available = self.is_local_runtime_available()
        version = None
        if available:
            import resin
            version = getattr(resin, "__version__", "0.1.0")

        crates = []
        crates_dir = self.resin_dir / "crates"
        if crates_dir.is_dir():
            crates = sorted(p.name for p in crates_dir.iterdir() if p.is_dir())

        runners = []
        models_dir = self.resin_dir / "models"
        if models_dir.is_dir():
            runners = sorted(p.name for p in models_dir.iterdir() if p.is_dir())

        skills = []
        skills_dir = self.resin_dir / "skills"
        if skills_dir.is_dir():
            skills = sorted(p.name for p in skills_dir.iterdir() if (p / "SKILL.md").exists())

        return {
            "target_release": "HyperSpace 1.06",
            "upstream_repo": "https://github.com/ekzhang/resin",
            "license": "Apache-2.0",
            "pinned_commit": RESIN_PINNED_COMMIT,
            "resin_dir": str(self.resin_dir),
            "native_extension_ready": available,
            "version": version,
            "rust_crates": crates,
            "model_runner_packages": runners,
            "bundled_skills": skills,
        }

    def simulate_hybrid_slab_schedule(
        self,
        shared_prefix_tokens: Optional[Sequence[int]] = None,
        agent_suffixes: Optional[Sequence[Sequence[int]]] = None,
        max_output_tokens: int = 3,
        parent_capacity: int = 16,
        block_tokens: int = 4,
    ) -> Dict[str, Any]:
        """Esegue un ciclo transazionale completo su `resin.Engine` con layout ibrido HISTORY + STATE.

        Verifica:
        1. Allocazione nello slab pool unificato sia per blocchi KV (`CacheGroupFamily.HISTORY`)
           sia per stati ricorrenti Gated DeltaNet / Qwenputer (`CacheGroupFamily.STATE`).
        2. Commit degli snapshot di stato ricorrente (`with_state_checkpoints`) al confine di blocco.
        3. Riuso esatto della prefix cache LRU (`cached_tokens > 0`) per le richieste successive
           che condividono il prompt di sistema.
        """
        if not self.is_local_runtime_available():
            return {
                "success": False,
                "error": "Binding Rust resin._resin non disponibile (esegui: bash scripts/install_resin.sh)",
            }

        import numpy as np
        import resin

        prefix = list(shared_prefix_tokens) if shared_prefix_tokens is not None else [101, 102, 103, 104]
        suffixes = (
            [list(s) for s in agent_suffixes]
            if agent_suffixes is not None
            else [[201, 202], [301, 302], [401]]
        )

        history_group = resin.CacheGroupLayout(
            block_tokens=block_tokens,
            blocks_per_slab=2,
            family=resin.CacheGroupFamily.HISTORY,
            retention=resin.CacheRetention.HISTORY,
        )
        state_group = resin.CacheGroupLayout(
            block_tokens=block_tokens,
            blocks_per_slab=1,
            family=resin.CacheGroupFamily.STATE,
            retention=resin.CacheRetention.HISTORY,
        )
        layout = resin.CacheLayout(
            parent_capacity=parent_capacity,
            groups=[history_group, state_group],
        )

        class HybridDeltaNetRunner:
            runner_config = resin.RunnerConfig(
                cache_layout=layout,
                continuation_prefill=True,
            )

            def __init__(self) -> None:
                self.binding: Optional[resin.ResourceBinding] = None
                self.plans_executed: int = 0
                self.state_checkpoints_committed: List[int] = []
                self.state_restores_executed: int = 0

            def bind_resources(self, binding: resin.ResourceBinding) -> None:
                self.binding = binding

            def forward(self, plan: resin.BatchPlan) -> resin.ForwardOutput:
                self.plans_executed += 1
                next_tokens = [
                    int(plan.token_ids[end - 1]) + 1000
                    for _, end in map(plan.token_range, range(plan.num_sequences))
                ]
                out = resin.ForwardOutput(
                    token_ids=np.asarray(next_tokens, dtype=np.uint32),
                    token_indptr=np.arange(plan.num_sequences + 1, dtype=np.uint32),
                )
                receipts: Dict[int, None] = {}
                for group in plan.cache_groups:
                    if group.state is None:
                        continue
                    self.state_restores_executed += len(group.state.restore_copies)
                    for reservation_id, row, prefix_len, _, _ in group.state.checkpoint_slots:
                        start, end = plan.token_range(row)
                        if int(plan.context_lengths[row]) + (end - start) == prefix_len:
                            receipts[int(reservation_id)] = None
                if receipts:
                    self.state_checkpoints_committed.extend(receipts.keys())
                    out = out.with_state_checkpoints(tuple(receipts.keys()))
                return out

        t0 = time.perf_counter()
        runner = HybridDeltaNetRunner()
        request_records: List[Dict[str, Any]] = []
        trace_hasher = hashlib.sha256()

        with resin.Engine(
            runner,
            context_length=1024,
            max_running_requests=4,
            prefix_cache=True,
            enable_metrics=True,
        ) as engine:
            # 1) Eseguiamo la prima richiesta per popolare il prefisso condiviso e il checkpoint STATE
            first_prompt = prefix + suffixes[0]
            first_lease = engine.submit(
                first_prompt,
                sampling_params=resin.SamplingParams(max_output_tokens=max_output_tokens),
            )
            while engine.has_work():
                engine.step()
            first_out = first_lease.take_result()
            request_records.append({
                "agent_index": 0,
                "prompt_len": len(first_prompt),
                "cached_prefix_tokens": int(first_lease.cached_tokens),
                "output_tokens": list(first_out),
            })
            trace_hasher.update(f"0:{first_prompt}:{first_lease.cached_tokens}:{first_out}".encode("utf-8"))

            # 2) Eseguiamo le richieste successive in batch verificando il riuso del prefisso KV + STATE
            follow_leases: List[Tuple[int, List[int], resin.RequestLease]] = []
            for idx, suf in enumerate(suffixes[1:], start=1):
                prompt = prefix + suf
                lease = engine.submit(
                    prompt,
                    sampling_params=resin.SamplingParams(max_output_tokens=max_output_tokens),
                )
                follow_leases.append((idx, prompt, lease))

            while engine.has_work():
                engine.step()

            for idx, prompt, lease in follow_leases:
                out_tokens = lease.take_result()
                request_records.append({
                    "agent_index": idx,
                    "prompt_len": len(prompt),
                    "cached_prefix_tokens": int(lease.cached_tokens),
                    "output_tokens": list(out_tokens),
                })
                trace_hasher.update(f"{idx}:{prompt}:{lease.cached_tokens}:{out_tokens}".encode("utf-8"))

            prefix_stats = engine.prefix_cache_stats
            free_slabs = engine.cache_free_parent_count
            occupied_blocks = engine.cache_occupied_block_count

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        schedule_hash = trace_hasher.hexdigest()

        # Verifica che le richieste successive abbiano ottenuto un prefix hit
        follow_hits = all(r["cached_prefix_tokens"] >= block_tokens for r in request_records[1:])
        all_valid = (
            follow_hits
            and len(runner.state_checkpoints_committed) >= 1
            and runner.state_restores_executed >= len(suffixes) - 1
        )

        tier = VERIFIED if all_valid else REFUTED
        if all_valid:
            evidence: Dict[str, Any] = {
                "tier": VERIFIED,
                "basis": [
                    {
                        "kind": "check",
                        "command": f"ResinBridge.simulate_hybrid_slab_schedule(requests={len(request_records)})",
                        "exit_code": 0,
                        "output_sha256": schedule_hash,
                        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }
                ],
            }
        else:
            evidence = {
                "tier": REFUTED,
                "basis": [
                    {
                        "kind": "refutation",
                        "reason": f"follow_hits={follow_hits}, checkpoints={len(runner.state_checkpoints_committed)}, restores={runner.state_restores_executed}",
                    }
                ],
            }

        return {
            "success": all_valid,
            "verdict": tier,
            "elapsed_ms": round(elapsed_ms, 3),
            "plans_executed": runner.plans_executed,
            "state_checkpoints_committed": len(runner.state_checkpoints_committed),
            "state_restores_executed": runner.state_restores_executed,
            "prefix_cache_stats": {
                "cached_blocks": prefix_stats[0] if prefix_stats else 0,
                "hits": prefix_stats[1] if prefix_stats else 0,
                "misses": prefix_stats[2] if prefix_stats else 0,
                "evictions": prefix_stats[3] if prefix_stats else 0,
            },
            "cache_pool": {
                "parent_capacity_slabs": parent_capacity,
                "free_slabs_after_run": free_slabs,
                "occupied_blocks_in_prefix_cache": occupied_blocks,
            },
            "requests": request_records,
            "schedule_hash": schedule_hash,
            "evidence": evidence,
            "evidence_errors": validate_evidence(evidence),
        }

    def check_mesh_nodes_readiness(self) -> Dict[str, Any]:
        """Ispeziona i tre nodi della mesh HyperSpace per la transizione a Resin 1.06."""
        local_ok = self.is_local_runtime_available()
        mac_status: Dict[str, Any] = {
            "role": "Master Hub & Apple Silicon MLX Runner (Qwen3.5-MoE / Hybrid Slab Engine)",
            "os": "macOS (Apple Silicon M5)",
            "resin_repo_present": self.resin_dir.exists(),
            "resin_rust_core_ready": local_ok,
            "recommended_runner": "resin_models_mlx (Metal 8-bit affine + FP32 DeltaNet LiveStates)",
            "status": "ready" if local_ok else "install_required",
        }

        omen_status: Dict[str, Any] = {
            "role": "GPU Heavy Engine & CUDA Graph Runner",
            "endpoint": OMEN_NODE_URL,
            "reachable": False,
            "recommended_runner": "resin_models_cuda (CUDA graphs + overlapped decode + Triton)",
            "status": "offline",
        }
        try:
            req = urllib.request.urlopen(f"{OMEN_NODE_URL}/health", timeout=3)
            if req.getcode() == 200:
                data = json.loads(req.read().decode("utf-8"))
                omen_status["reachable"] = True
                omen_status["tier"] = data.get("tier", "unknown")
                omen_status["node_id"] = data.get("node_id", "")
                omen_status["status"] = "ready"
        except Exception as exc:
            omen_status["error"] = str(exc)

        asus_status: Dict[str, Any] = {
            "role": "High Memory Pool & Prefix Cache Slab Tier (48GB DDR5)",
            "endpoint": ASUS_NODE_URL,
            "reachable": False,
            "recommended_runner": "resin_models_torch / MemoryCacheStorage Slab Offload",
            "status": "standby_or_offline",
        }
        try:
            req = urllib.request.urlopen(f"{ASUS_NODE_URL}/health", timeout=2)
            if req.getcode() == 200:
                asus_status["reachable"] = True
                asus_status["status"] = "ready"
        except Exception as exc:
            asus_status["note"] = f"Standby/Timeout: {exc}"

        return {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "target_version": "HyperSpace 1.06 (Resin Substrate)",
            "cluster_ready": local_ok,
            "nodes": {
                "mac_m5_hub": mac_status,
                "hp_omen_16": omen_status,
                "asus_v16": asus_status,
            },
        }
