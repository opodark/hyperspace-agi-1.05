from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


class TaskState(Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CycleDetectedError(Exception):
    """Sollevata quando viene rilevata una dipendenza circolare nel DAG."""
    pass


@dataclass
class Task:
    task_id: str
    priority: int = 0
    dependencies: Set[str] = field(default_factory=set)
    cost_weight: float = 1.0
    state: TaskState = TaskState.PENDING
    payload: dict = field(default_factory=dict)
    last_error: Optional[Exception] = None

    def __post_init__(self):
        if isinstance(self.dependencies, (list, tuple)):
            self.dependencies = set(self.dependencies)


class TaskDAG:
    def __init__(self) -> None:
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.RLock()

    def add_task(self, task: Task) -> None:
        with self._lock:
            if task.task_id in self._tasks:
                raise ValueError(f"Task {task.task_id} already exists")
            self._tasks[task.task_id] = task
            self.validate_acyclic()
            self._update_readiness()

    def _update_readiness(self) -> None:
        for task in self._tasks.values():
            if task.state == TaskState.PENDING:
                if all(
                    dep in self._tasks and self._tasks[dep].state == TaskState.COMPLETED
                    for dep in task.dependencies
                ):
                    task.state = TaskState.READY

    def get_ready_tasks(self) -> List[Task]:
        with self._lock:
            self._update_readiness()
            ready = [t for t in self._tasks.values() if t.state == TaskState.READY]
            return sorted(ready, key=lambda t: (-t.priority, t.task_id))

    def mark_completed(self, task_id: str) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(f"Task {task_id} not found")
            task.state = TaskState.COMPLETED
            self._update_readiness()

    def mark_failed(self, task_id: str, error: Optional[Exception] = None) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(f"Task {task_id} not found")
            task.state = TaskState.FAILED
            task.last_error = error

    def is_complete(self) -> bool:
        with self._lock:
            return all(
                t.state in (TaskState.COMPLETED, TaskState.FAILED)
                for t in self._tasks.values()
            )

    def validate_acyclic(self) -> None:
        with self._lock:
            # Calcola grado entrante considerando solo nodi presenti
            indegree: Dict[str, int] = {
                tid: sum(1 for d in t.dependencies if d in self._tasks)
                for tid, t in self._tasks.items()
            }
            dependents: Dict[str, List[str]] = {tid: [] for tid in self._tasks}
            for tid, task in self._tasks.items():
                for dep in task.dependencies:
                    if dep in dependents:
                        dependents[dep].append(tid)

            queue = [tid for tid, deg in indegree.items() if deg == 0]
            processed = 0
            while queue:
                curr = queue.pop(0)
                processed += 1
                for nxt in dependents.get(curr, []):
                    indegree[nxt] -= 1
                    if indegree[nxt] == 0:
                        queue.append(nxt)

            if processed != len(self._tasks):
                raise CycleDetectedError("Cycle detected in task DAG")
