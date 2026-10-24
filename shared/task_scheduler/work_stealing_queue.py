from __future__ import annotations

import collections
import threading
from typing import Any, Dict, List, Optional


class WorkStealingDeque:
    """Coda concorrente ispirata a Chase-Lev.
    
    Il proprietario esegue push_bottom() e pop_bottom() (LIFO).
    Gli altri worker (thieves) rubano dal lato opposto con steal_top() (FIFO).
    """

    def __init__(self) -> None:
        self._deque = collections.deque()
        self._lock = threading.RLock()

    def push_bottom(self, item: Any) -> None:
        with self._lock:
            self._deque.append(item)

    def pop_bottom(self) -> Optional[Any]:
        with self._lock:
            if not self._deque:
                return None
            return self._deque.pop()

    def steal_top(self) -> Optional[Any]:
        with self._lock:
            if not self._deque:
                return None
            return self._deque.popleft()

    def __len__(self) -> int:
        with self._lock:
            return len(self._deque)


class WorkStealingPool:
    """Pool distribuito multi-nodo di code work-stealing."""

    def __init__(self, nodes: Optional[List[str]] = None) -> None:
        self._lock = threading.RLock()
        self._queues: Dict[str, WorkStealingDeque] = {}
        self.tasks_executed: int = 0
        self.tasks_stolen: int = 0

        if nodes:
            for n in nodes:
                self._queues[n] = WorkStealingDeque()

    def _get_or_create_queue(self, node_id: str) -> WorkStealingDeque:
        if node_id not in self._queues:
            self._queues[node_id] = WorkStealingDeque()
        return self._queues[node_id]

    def schedule_local(self, node_id: str, task: Any) -> None:
        with self._lock:
            q = self._get_or_create_queue(node_id)
            q.push_bottom(task)

    def pop_or_steal(self, node_id: Optional[str] = None) -> Optional[Any]:
        with self._lock:
            # 1. Tenta prima esecuzione locale se il nodo è specificato
            if node_id and node_id in self._queues:
                local_task = self._queues[node_id].pop_bottom()
                if local_task is not None:
                    self.tasks_executed += 1
                    return local_task

            # 2. Se vuoto o node_id è None, cerca la coda più carica tra gli altri nodi
            candidates = [
                (nid, q) for nid, q in self._queues.items()
                if (node_id is None or nid != node_id) and len(q) > 0
            ]
            if not candidates:
                return None

            # Ordina per coda più carica (max len)
            candidates.sort(key=lambda pair: len(pair[1]), reverse=True)
            _, victim_queue = candidates[0]

            stolen_task = victim_queue.steal_top()
            if stolen_task is not None:
                self.tasks_stolen += 1
                return stolen_task

            return None
