# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import threading
from typing import Dict, List, Optional, Any

try:
    from .task_dag import TaskDAG, Task, TaskState
    from .work_stealing_queue import WorkStealingPool
    from .resource_monitor import ResourceGovernor, NodeTelemetry
    from .fault_tolerant_scheduler import FaultTolerantScheduler
except (ImportError, ValueError):
    from task_dag import TaskDAG, Task, TaskState
    from work_stealing_queue import WorkStealingPool
    from resource_monitor import ResourceGovernor, NodeTelemetry
    from fault_tolerant_scheduler import FaultTolerantScheduler


class DistributedMeshOrchestrator:
    """Orchestratore unificato del cluster distribuito sovereign.
    
    Integra:
    - TaskDAG (ordinamento topologico causale e cycle detection)
    - WorkStealingPool (bilanciamento dinamico Chase-Lev tra nodi)
    - ResourceGovernor (monitoraggio VRAM, carico e guardrail termici)
    - FaultTolerantScheduler (gestione lease, heartbeat e bonifica compiti zombie in caso di crash)
    """

    def __init__(self, nodes: Optional[List[str]] = None) -> None:
        self.nodes = nodes or ["mac-hub", "omen-root", "asus-builder"]
        self._lock = threading.RLock()
        self._dag: Optional[TaskDAG] = None
        self._pool = WorkStealingPool(nodes=self.nodes)
        self._governor = ResourceGovernor()
        self._scheduler = FaultTolerantScheduler(max_retries=3)
        self._worker_states: Dict[str, str] = {n: "online" for n in self.nodes}
        self.results: Dict[str, Any] = {}

        # Inizializza telemetria nominale per ciascun nodo
        for node in self.nodes:
            self._governor.register_node(NodeTelemetry(
                node_id=node,
                vram_free_gb=6.0,
                vram_total_gb=8.0,
                gpu_temp_c=55.0,
                is_thermal_throttling=False,
                load_ratio=0.2
            ))

    def submit_dag(self, dag: TaskDAG) -> None:
        with self._lock:
            self._dag = dag
            # Accoda i compiti immediatamente pronti
            ready = dag.get_ready_tasks()
            for t in ready:
                target = self._governor.get_optimal_target_node(t.cost_weight) or self.nodes[0]
                self._pool.schedule_local(target, t)

    def step_execution_round(self) -> bool:
        """Esegue un ciclo di assegnazione, work-stealing ed esecuzione compiti."""
        with self._lock:
            if not self._dag:
                return False

            if self._dag.is_complete():
                return False

            # 1. Bonifica eventuali task zombie
            reclaimed = self._scheduler.check_and_reclaim_zombies()
            for tid in reclaimed:
                t = self._dag._tasks.get(tid)
                if t and t.state != TaskState.COMPLETED:
                    t.state = TaskState.READY
                    best = self._governor.get_optimal_target_node(t.cost_weight) or self.nodes[0]
                    self._pool.schedule_local(best, t)

            # 2. Ogni nodo attivo tenta di eseguire un compito locale o rubato
            for node in self.nodes:
                if self._worker_states.get(node) == "crashed":
                    continue

                if not self._governor.can_admit_task(node, required_vram_gb=1.0):
                    continue

                task = self._pool.pop_or_steal(node)
                if task:
                    acquired = self._scheduler.acquire_lease(task.task_id, node, duration_s=10.0)
                    if acquired:
                        # Esegue il task
                        task.state = TaskState.RUNNING
                        self._dag.mark_completed(task.task_id)
                        self.results[task.task_id] = task.payload.get("result", f"res_{task.task_id}")

            # 3. Accoda compiti che sono diventati READY a seguito dei completamenti
            for t in self._dag.get_ready_tasks():
                if t.task_id not in self._scheduler._leases and t.task_id not in self.results:
                    best = self._governor.get_optimal_target_node(t.cost_weight) or self.nodes[0]
                    self._pool.schedule_local(best, t)

            return not self._dag.is_complete()

    def simulate_worker_crash(self, worker_id: str) -> None:
        with self._lock:
            self._worker_states[worker_id] = "crashed"
            # Throttling e disattivazione nel governor
            self._governor.register_node(NodeTelemetry(
                node_id=worker_id,
                vram_free_gb=0.0,
                vram_total_gb=8.0,
                gpu_temp_c=99.0,
                is_thermal_throttling=True,
                load_ratio=1.0
            ))
            # Rilascia immediatamente i task del nodo crashato facendone scadere il lease
            for tid, lease in list(self._scheduler._leases.items()):
                if lease.worker_id == worker_id:
                    lease.lease_granted_at = 0.0  # forza scadenza

    def run_until_complete(self, max_steps: int = 50) -> None:
        steps = 0
        while self.step_execution_round() and steps < max_steps:
            steps += 1

    def get_completion_summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "status": "COMPLETED" if (self._dag and self._dag.is_complete()) else "IN_PROGRESS",
                "workers": dict(self._worker_states),
                "tasks_completed": len(self.results),
                "tasks_stolen": self._pool.tasks_stolen,
                "tasks_executed": self._pool.tasks_executed
            }
