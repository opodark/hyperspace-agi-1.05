# SPDX-License-Identifier: Apache-2.0
"""
Dynamic KV Memory Pool per HyperSpace Sovereign Mesh.

Gestore di pooling per la Key-Value (KV) cache di modelli di grandi dimensioni
(Flint 40B MoE a 128k context, LFM 24B a 64k) con ripartizione a blocchi,
reference counting per contesto e liberazione automatica su sessioni inattive.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class ContextKVAllocation:
    """Metadati dell'allocazione di KV cache per uno specifico contesto/task."""
    ctx_id: str
    blocks: List[int] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_accessed_at: float = field(default_factory=time.time)
    total_bytes: int = 0


class DynamicKVMemoryPool:
    """
    Pool di memoria pre-allocata a blocchi per la KV cache multi-contesto.
    Evita la frammentazione della VRAM e previene crash per OOM su sequenze lunghe.
    """

    def __init__(
        self,
        capacity_blocks: int = 128,
        block_size_bytes: int = 1_048_576,  # 1 MB per blocco standard
        idle_timeout_s: float = 300.0        # 5 minuti di inattività per auto-eviction
    ):
        self.capacity_blocks = capacity_blocks
        self.block_size_bytes = block_size_bytes
        self.idle_timeout_s = idle_timeout_s

        self._lock = threading.Lock()
        # Pool di ID dei blocchi fisici disponibili (0 .. capacity-1)
        self._free_blocks: List[int] = list(range(capacity_blocks))
        # Allocazioni attive: ctx_id -> ContextKVAllocation
        self._allocations: Dict[str, ContextKVAllocation] = {}

    def allocate(self, ctx_id: str, num_blocks: int = 1) -> List[int]:
        """
        Prenota uno o più blocchi di KV cache per uno specifico contesto.
        Restituisce gli indici dei blocchi fisici assegnati.
        """
        if num_blocks <= 0:
            return []

        with self._lock:
            # Se la memoria è satura, prova prima a fare eviction dei contesti idle
            if len(self._free_blocks) < num_blocks:
                self._evict_idle_contexts_locked()

            if len(self._free_blocks) < num_blocks:
                available = len(self._free_blocks)
                raise MemoryError(
                    f"DynamicKVMemoryPool esaurito: richiesti {num_blocks} blocchi ({num_blocks * self.block_size_bytes} byte), "
                    f"disponibili solo {available} blocchi."
                )

            allocated_indices = [self._free_blocks.pop(0) for _ in range(num_blocks)]

            alloc = self._allocations.get(ctx_id)
            now = time.time()
            if alloc is None:
                alloc = ContextKVAllocation(ctx_id=ctx_id, created_at=now, last_accessed_at=now)
                self._allocations[ctx_id] = alloc

            alloc.blocks.extend(allocated_indices)
            alloc.last_accessed_at = now
            alloc.total_bytes = len(alloc.blocks) * self.block_size_bytes

            return allocated_indices

    def touch(self, ctx_id: str) -> bool:
        """Aggiorna il timestamp di ultimo accesso di un contesto per evitarne l'eviction."""
        with self._lock:
            alloc = self._allocations.get(ctx_id)
            if alloc:
                alloc.last_accessed_at = time.time()
                return True
            return False

    def deallocate(self, ctx_id: str) -> int:
        """
        Libera tutti i blocchi allocati per uno specifico contesto.
        Restituisce il numero di blocchi restituiti al pool.
        """
        with self._lock:
            alloc = self._allocations.pop(ctx_id, None)
            if not alloc:
                return 0

            freed_count = len(alloc.blocks)
            self._free_blocks.extend(alloc.blocks)
            return freed_count

    def _evict_idle_contexts_locked(self, current_time: Optional[float] = None) -> int:
        """Bonifica i contesti che hanno superato l'idle_timeout."""
        now = current_time if current_time is not None else time.time()
        to_evict: List[str] = []

        for ctx_id, alloc in self._allocations.items():
            if now - alloc.last_accessed_at >= self.idle_timeout_s:
                to_evict.append(ctx_id)

        freed_blocks = 0
        for ctx_id in to_evict:
            alloc = self._allocations.pop(ctx_id)
            freed_blocks += len(alloc.blocks)
            self._free_blocks.extend(alloc.blocks)

        return freed_blocks

    def evict_idle_contexts(self, current_time: Optional[float] = None) -> int:
        """Interfaccia pubblica per lanciare la bonifica dei contesti inattivi."""
        with self._lock:
            return self._evict_idle_contexts_locked(current_time)

    def stats(self) -> Dict[str, Any]:
        """Restituisce le metriche correnti del pool KV."""
        with self._lock:
            total_blocks = self.capacity_blocks
            free_blocks = len(self._free_blocks)
            used_blocks = total_blocks - free_blocks
            utilization_pct = round((used_blocks / total_blocks) * 100, 2) if total_blocks else 0.0

            contexts_summary = {
                ctx_id: {
                    "blocks": len(a.blocks),
                    "bytes": a.total_bytes,
                    "idle_s": round(time.time() - a.last_accessed_at, 1)
                }
                for ctx_id, a in self._allocations.items()
            }

            return {
                "capacity_blocks": total_blocks,
                "block_size_bytes": self.block_size_bytes,
                "total_memory_bytes": total_blocks * self.block_size_bytes,
                "free_blocks": free_blocks,
                "used_blocks": used_blocks,
                "free_bytes": free_blocks * self.block_size_bytes,
                "used_bytes": used_blocks * self.block_size_bytes,
                "utilization_pct": utilization_pct,
                "active_contexts_count": len(self._allocations),
                "contexts": contexts_summary
            }
