# SPDX-License-Identifier: Apache-2.0
"""Test suite per RFC-0043 (Distributed Work-Stealing Task Scheduler) integrato in shared."""

import time
import pytest
from shared.task_scheduler import (
    TaskDAG,
    Task,
    TaskState,
    CycleDetectedError,
    WorkStealingPool,
    WorkStealingDeque,
    ResourceGovernor,
    NodeTelemetry,
    FaultTolerantScheduler,
    DistributedMeshOrchestrator,
)


def test_task_state_and_defaults():
    t = Task("t1", priority=10, dependencies=["t0"])
    assert t.state == TaskState.PENDING
    assert "t0" in t.dependencies
    assert t.priority == 10


def test_ready_execution_linear():
    dag = TaskDAG()
    t1 = Task(task_id="A", priority=1)
    t2 = Task(task_id="B", priority=2, dependencies=["A"])
    t3 = Task(task_id="C", priority=3, dependencies=["B"])
    dag.add_task(t1)
    dag.add_task(t2)
    dag.add_task(t3)

    ready = dag.get_ready_tasks()
    assert [t.task_id for t in ready] == ["A"]

    dag.mark_completed("A")
    ready = dag.get_ready_tasks()
    assert [t.task_id for t in ready] == ["B"]

    dag.mark_completed("B")
    ready = dag.get_ready_tasks()
    assert [t.task_id for t in ready] == ["C"]

    dag.mark_completed("C")
    assert dag.is_complete()


def test_priority_ordering_of_ready_tasks():
    dag = TaskDAG()
    dag.add_task(Task("low", priority=1))
    dag.add_task(Task("high", priority=10))
    dag.add_task(Task("mid", priority=5))

    ready = dag.get_ready_tasks()
    assert [t.task_id for t in ready] == ["high", "mid", "low"]


def test_cycle_detection():
    dag = TaskDAG()
    dag.add_task(Task("A", dependencies=["B"]))
    with pytest.raises(CycleDetectedError):
        dag.add_task(Task("B", dependencies=["A"]))


def test_work_stealing_local_and_steal():
    deque = WorkStealingDeque()
    deque.push_bottom("item1")
    deque.push_bottom("item2")
    assert deque.pop_bottom() == "item2"
    assert deque.steal_top() == "item1"
    assert deque.pop_bottom() is None


def test_resource_governor():
    gov = ResourceGovernor()
    gov.register_node(NodeTelemetry(
        node_id="A",
        vram_free_gb=10.0,
        vram_total_gb=20.0,
        gpu_temp_c=30.0,
        is_thermal_throttling=False,
        load_ratio=0.2
    ))
    gov.register_node(NodeTelemetry(
        node_id="B",
        vram_free_gb=10.0,
        vram_total_gb=20.0,
        gpu_temp_c=85.0,
        is_thermal_throttling=True,
        load_ratio=0.5
    ))

    assert gov.can_admit_task("A", 5.0) is True
    assert gov.can_admit_task("B", 5.0) is False
    assert gov.get_optimal_target_node(5.0) == "A"


def test_fault_tolerant_scheduler():
    sched = FaultTolerantScheduler()
    ok = sched.acquire_lease("task1", "worker1", 2.0)
    assert ok is True
    assert "task1" in sched._leases

    # Zombie reclaim
    now = time.time() + 5.0
    reclaimed = sched.check_and_reclaim_zombies(now)
    assert "task1" in reclaimed
    assert "task1" not in sched._leases


def test_mesh_orchestrator_end_to_end_with_chaos():
    dag = TaskDAG()
    dag.add_task(Task(task_id="extract", priority=10, payload={"result": "EXTRACT_OK"}))
    dag.add_task(Task(task_id="preprocess", priority=8, dependencies=["extract"], payload={"result": "PREPROCESS_OK"}))
    dag.add_task(Task(task_id="feature_a", priority=5, dependencies=["preprocess"], payload={"result": "FEAT_A_OK"}))
    dag.add_task(Task(task_id="feature_b", priority=5, dependencies=["preprocess"], payload={"result": "FEAT_B_OK"}))
    dag.add_task(Task(task_id="ensemble", priority=9, dependencies=["feature_a", "feature_b"], payload={"result": "ENSEMBLE_OK"}))
    dag.add_task(Task(task_id="publish", priority=3, dependencies=["ensemble"], payload={"result": "PUBLISH_OK"}))

    orchestrator = DistributedMeshOrchestrator(nodes=["mac-hub", "omen-root", "asus-builder"])
    orchestrator.submit_dag(dag)

    orchestrator.step_execution_round()
    assert "extract" in orchestrator.results

    orchestrator.step_execution_round()
    assert "preprocess" in orchestrator.results

    orchestrator.simulate_worker_crash("asus-builder")
    summary = orchestrator.get_completion_summary()
    assert summary["workers"]["asus-builder"] == "crashed"

    orchestrator.run_until_complete(max_steps=20)
    assert dag.is_complete()
    assert len(orchestrator.results) == 6
    assert orchestrator.results["publish"] == "PUBLISH_OK"
