# SPDX-License-Identifier: Apache-2.0
"""Test suite per RFC-0044 (Distributed Resumable State Machine & Checkpoint Engine) integrato in shared."""

import time
import pytest
from shared.resumable_state_machine import (
    RunState,
    ExecutionStatus,
    CheckpointStore,
    IdempotentGateway,
    ResumableStateMachine,
    DistributedResumableEngine,
)
from shared.resumable_state_machine.distributed_resumable_engine import CrashTriggeredError


def test_runstate_creation_default():
    state = RunState()
    assert state is not None
    data = state.to_dict()
    restored = RunState.from_dict(data)
    assert restored.to_dict() == data


def test_hash_sha256_immutable_and_changes():
    state = RunState(version=1)
    original_hash = state.hash
    updated = state.clone_with_update(status="failed")
    assert updated.hash != original_hash
    assert updated.version == 2
    assert updated.status == "failed"


def test_checkpoint_store_atomic_save_and_wal(tmp_path):
    store = CheckpointStore(tmp_path)
    state = RunState(run_id="run-test")
    checkpoint_id = store.save_checkpoint(state)
    assert checkpoint_id is not None

    loaded = store.load_checkpoint(checkpoint_id)
    assert loaded is not None

    latest_id = store.get_latest_checkpoint()
    assert latest_id == checkpoint_id

    assert store.wal_path.exists()
    lines = store.wal_path.read_text().strip().splitlines()
    assert len(lines) == 1


def test_idempotent_executor():
    calls = {"count": 0}
    gateway = IdempotentGateway()

    def action(val: int) -> int:
        calls["count"] += 1
        return val * 2

    res1, cached1 = gateway.execute_action("key-1", action, 2)
    assert res1 == 4
    assert cached1 is False
    assert calls["count"] == 1

    res2, cached2 = gateway.execute_action("key-1", action, 2)
    assert res2 == 4
    assert cached2 is True
    assert calls["count"] == 1


def test_resumable_state_machine_steps(tmp_path):
    store = CheckpointStore(tmp_path)
    gateway = IdempotentGateway()
    sm = ResumableStateMachine(store, gateway)

    sm.register_step(0, "fetch", lambda s: {"data": "ok"})
    sm.register_step(1, "process", lambda s: {"processed": True})

    state = sm.start_or_resume("run-1")
    assert state.step_index == 0

    state1 = sm.step()
    assert state1.step_index == 1
    assert state1.payload["data"] == "ok"

    state2 = sm.step()
    assert state2.step_index == 2
    assert state2.status == ExecutionStatus.COMPLETED.value
    assert state2.payload["processed"] is True


def test_distributed_resumable_engine_crash_resume_no_dup():
    engine = DistributedResumableEngine()
    mission_id = "mission-4step"
    steps = ["fetch_data", "expensive_analysis", "external_notify", "finalize"]
    engine.create_mission(mission_id, steps)

    engine.run_next(mission_id)
    engine.run_next(mission_id)
    engine.crash_at_next("external_notify")
    with pytest.raises(CrashTriggeredError):
        engine.run_next(mission_id)

    state = engine.resume_crashed_mission(mission_id)
    assert state.completed_steps == ["fetch_data", "expensive_analysis"]
    assert state.current_step == "external_notify"

    engine.run_next(mission_id)
    assert engine.notifications.count("external_notify") == 1
    engine.run_next(mission_id)

    assert state.status == "COMPLETED"
    assert state.completed_steps == ["fetch_data", "expensive_analysis", "external_notify", "finalize"]
