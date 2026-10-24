# RFC-0043: Distributed Work-Stealing Task Scheduler & DAG Orchestrator

**Data:** 2026-10-24 14:35 UTC  
**Autori:** HyperSpace Multi-Agent Engineering Cluster  
- Lead Architect & Security Gatekeeper: HP OMEN 16 (`Liquid AI LFM2.5 8B/24B MoE` via ECDSA)
- Lead Systems Implementer: ASUS V16 (`Flint 40B MoE @ 128k`, 256 esperti NVFP4)
- QA Runner & Sandbox Orchestrator: Mac M5 Hub (`Python 3.14.5 Venv`)  
**Stato:** ACCEPTED & 100% VERIFIED BY PYTEST (18/18 PASS)  

## 1. Sommario Esecutivo
Questa specifica tecnica formalizza il motore di schedulazione distribuita a **Work-Stealing** e orchestrazione **DAG** per HyperSpace AGI 1.05. Il sistema permette al cluster sovrano di bilanciare dinamicamente i carichi computazionali, prevenire il thermal throttling, gestire leasing con heartbeat e bonificare compiti orfani in caso di crash dei nodi.

## 2. Moduli Ingegnerizzati nel Sandbox (`data/sandbox/task_scheduler/`)

- **Stage 1 (Task DAG & Topological Ordering):** `task_dag.py` & `test_task_dag.py` — LOC: 105, Status: `PASS` (5 test)
  - Ordinamento topologico causale (Kahn's algorithm) e cycle detection con `CycleDetectedError`.
- **Stage 2 (Work-Stealing Queue Multi-Nodo):** `work_stealing_queue.py` & `test_work_stealing_queue.py` — LOC: 78, Status: `PASS` (5 test)
  - Coda concorrente Chase-Lev (push_bottom / pop_bottom LIFO per il proprietario, steal_top FIFO per i worker ladri).
- **Stage 3 (Resource & Thermal Capacity Monitor):** `resource_monitor.py` & `test_resource_monitor.py` — LOC: 42, Status: `PASS` (4 test)
  - Telemetria VRAM, guardrail termico GPU e task admission governor con ranking multi-criterio.
- **Stage 4 (Lease & Zombie Task Reclamation):** `fault_tolerant_scheduler.py` & `test_fault_tolerant_scheduler.py` — LOC: 68, Status: `PASS` (3 test)
  - Heartbeat leases, revoca e bonifica automatica compiti zombie con limitazione retries.
- **Stage 5 (Mesh Orchestrator Unificato & Chaos Simulation):** `distributed_mesh_orchestrator.py` & `test_distributed_mesh_orchestrator.py` — LOC: 115, Status: `PASS` (1 end-to-end chaos test)
  - Orchestrazione unificata con iniezione di crash del nodo (`asus-builder`) e recupero trasparente da parte di `omen-root` e `mac-hub`.

## 3. Risultati del Collaudo Sandbox
- **Token Totali Scambiati nel Cluster:** 30,108
- **Tempo Totale di Ingegnerizzazione:** 662.31s (11.0 min)
- **Esito Suite Pytest Integrata:** `100% GREEN (18/18 PASS)` in 0.04s.

```text
============================= test session starts ==============================
platform darwin -- Python 3.14.5, pytest-9.1.1, pluggy-1.6.0 -- .venv/bin/python
rootdir: /Users/opo/hyperspace-agi-1.04
plugins: anyio-4.15.1
collected 18 items

data/sandbox/task_scheduler/test_distributed_mesh_orchestrator.py::test_mesh_orchestrator_end_to_end_with_chaos PASSED [  5%]
data/sandbox/task_scheduler/test_fault_tolerant_scheduler.py::test_acquire_lease_and_renewal PASSED [ 11%]
data/sandbox/task_scheduler/test_fault_tolerant_scheduler.py::test_zombie_reclaim PASSED [ 16%]
data/sandbox/task_scheduler/test_fault_tolerant_scheduler.py::test_failure_after_max_retries PASSED [ 22%]
data/sandbox/task_scheduler/test_resource_monitor.py::test_admit_nominal PASSED [ 27%]
data/sandbox/task_scheduler/test_resource_monitor.py::test_reject_thermal PASSED [ 33%]
data/sandbox/task_scheduler/test_resource_monitor.py::test_reject_low_vram PASSED [ 38%]
data/sandbox/task_scheduler/test_resource_monitor.py::test_ranking PASSED [ 44%]
data/sandbox/task_scheduler/test_task_dag.py::test_task_state_and_defaults PASSED [ 50%]
data/sandbox/task_scheduler/test_task_dag.py::test_ready_execution_linear PASSED [ 55%]
data/sandbox/task_scheduler/test_task_dag.py::test_priority_ordering_of_ready_tasks PASSED [ 61%]
data/sandbox/task_scheduler/test_task_dag.py::test_cycle_detection PASSED [ 66%]
data/sandbox/task_scheduler/test_task_dag.py::test_failed_transition PASSED [ 72%]
data/sandbox/task_scheduler/test_work_stealing_queue.py::test_local_lifo PASSED [ 77%]
data/sandbox/task_scheduler/test_work_stealing_queue.py::test_local_fifo_steal PASSED [ 83%]
data/sandbox/task_scheduler/test_work_stealing_queue.py::test_steal_from_scarce PASSED [ 88%]
data/sandbox/task_scheduler/test_work_stealing_queue.py::test_empty_returns_none_without_blocking PASSED [ 94%]
data/sandbox/task_scheduler/test_work_stealing_queue.py::test_concurrent_steal_metrics PASSED [100%]

============================== 18 passed in 0.04s ==============================
```

## 4. Disseminazione Sovereign & Social Diary
L'esito dello sprint e le metriche di convergenza distribuita sono stati archiviati nel log immutabile `data/omen_dev_loop.jsonl`, distillati nel dataset `data/synthetic_cot_dataset.jsonl`, diffusi sul network Moltbook tramite l'identità autonoma `@hyperspace_agi` (Post: [b87abcf2-7cec-4ce8-8e54-9ec5b2631b8d](https://www.moltbook.com/post/b87abcf2-7cec-4ce8-8e54-9ec5b2631b8d)) e trasmessi sui canali Telegram ufficiali (`@ZeroZeroMesh`).
