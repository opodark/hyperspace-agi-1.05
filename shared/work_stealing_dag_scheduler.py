#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
shared/work_stealing_dag_scheduler.py
Modulo promosso in produzione da HyperSpace R&D Sovereign Lab.
Prototipo sorgente: proto_workstealingdagscheduler_1793013138.py
Data promozione: 2026-10-28T12:36:29+00:00
Autore: antigravity_sovereign

Scheduler DAG (Directed Acyclic Graph) decentralizzato con algoritmo di Work-Stealing:
- Distribuisce i task su nodi eterogenei (OMEN, ASUS, Mac)
- Se la coda di un worker supera `steal_threshold`, i worker scarichi "rubano" i task
- Risoluzione dinamica delle dipendenze al completamento (`on_task_done`)
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set


class Task:
    def __init__(self, node_id: int | str, deps: Optional[List[int | str]] = None, name: str = ""):
        self.node_id = node_id
        self.deps = list(deps or [])
        self.name = name or f"task-{node_id}"
        self.completed = False

    def __repr__(self) -> str:
        return f"Task({self.node_id}, deps={self.deps}, done={self.completed})"


class Worker:
    def __init__(self, wid: int | str, capacity: int = 1):
        self.wid = wid
        self.capacity = capacity
        self.queue: List[Task] = []

    def push(self, task: Task) -> None:
        self.queue.append(task)

    def pop(self) -> Optional[Task]:
        return self.queue.pop() if self.queue else None

    def __repr__(self) -> str:
        return f"Worker({self.wid}, queue_len={len(self.queue)})"


class DAG:
    def __init__(self, tasks: List[Task]):
        self.tasks = tasks
        self.dependencies: Dict[int | str, List[int | str]] = {t.node_id: t.deps for t in tasks}


class WorkStealingDAGScheduler:
    def __init__(self, workers: List[Worker], steal_threshold: int = 2):
        self.workers = workers
        self.steal_threshold = steal_threshold
        self.dag: Optional[DAG] = None
        self.ready_tasks: List[Task] = []
        self.completed_task_ids: Set[int | str] = set()
        self.on_steal: Callable[[Task, Worker, Worker], None] = lambda task, src, dst: None

    def submit(self, dag: DAG) -> None:
        self.dag = dag
        self.ready_tasks.clear()
        self.completed_task_ids.clear()
        for task in dag.tasks:
            if not task.deps:
                self.ready_tasks.append(task)

    def _try_steal(self, busy_worker: Worker) -> bool:
        if len(busy_worker.queue) > self.steal_threshold:
            victim = busy_worker.queue.pop()
            for w in self.workers:
                if w is not busy_worker and not w.queue:
                    w.push(victim)
                    self.on_steal(victim, busy_worker, w)
                    return True
            # Se nessun worker libero, rimetti il task
            busy_worker.queue.append(victim)
        return False

    def dispatch_step(self) -> int:
        """Esegue un singolo passo di schedulazione e bilanciamento: restituisce il numero di task assegnati."""
        assigned = 0
        for w in self.workers:
            if not w.queue and self.ready_tasks:
                task = self.ready_tasks.pop(0)
                w.push(task)
                assigned += 1
            if len(w.queue) > self.steal_threshold:
                self._try_steal(w)
        return assigned

    def on_task_done(self, task_id: int | str) -> List[Task]:
        """Notifica il completamento di un task e sblocca i dipendenti pronti nel DAG."""
        self.completed_task_ids.add(task_id)
        newly_ready = []
        if self.dag:
            for task in self.dag.tasks:
                if not task.completed and task.node_id not in self.completed_task_ids:
                    if set(task.deps).issubset(self.completed_task_ids):
                        if task not in self.ready_tasks and not any(task in w.queue for w in self.workers):
                            self.ready_tasks.append(task)
                            newly_ready.append(task)
        return newly_ready

    def is_finished(self) -> bool:
        if not self.dag:
            return True
        total_tasks = len(self.dag.tasks)
        return len(self.completed_task_ids) >= total_tasks and not self.ready_tasks and not any(w.queue for w in self.workers)

    def status(self) -> Dict[str, Any]:
        return {
            "workers_count": len(self.workers),
            "ready_queue_len": len(self.ready_tasks),
            "completed_tasks": len(self.completed_task_ids),
            "workers": [{"wid": w.wid, "queue_len": len(w.queue)} for w in self.workers],
            "finished": self.is_finished(),
        }
