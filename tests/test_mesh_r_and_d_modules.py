# SPDX-License-Identifier: Apache-2.0
"""
Test suite per i 4 moduli R&D promossi in produzione per HyperSpace Sovereign Mesh:
- SpeculativeDraftValidator
- DistributedHeartbeatSync
- DynamicKVMemoryPool
- ArcadeStateSyncEngine
"""

import time
import pytest
from shared.speculative_draft_validator import Draft, SpeculativeDraftValidator
from shared.distributed_heartbeat_sync import DistributedHeartbeatSync
from shared.dynamic_kv_memory_pool import DynamicKVMemoryPool
from shared.arcade_state_sync_engine import ArcadeStateSyncEngine


# -------------------------------------------------------------
# 1. SpeculativeDraftValidator Tests
# -------------------------------------------------------------
def test_speculative_draft_validator_accepted():
    validator = SpeculativeDraftValidator(required_constructs=["class", "def"])
    valid_code = """
class FastCalculator:
    def add(self, a: int, b: int) -> int:
        return a + b
"""
    draft = Draft(source=valid_code, model_id="omen_24b", task_id="task-101")
    res = validator.verify(draft)

    assert res.is_accepted is True
    assert res.ast_valid is True
    assert "FastCalculator" in res.classes
    assert "add" in res.functions
    assert res.node_count > 0
    assert not res.errors


def test_speculative_draft_validator_rejected_syntax_error():
    validator = SpeculativeDraftValidator()
    broken_code = "def broken_func(:\n    return 42"
    draft = Draft(source=broken_code, model_id="broken_model")
    res = validator.verify(draft)

    assert res.is_accepted is False
    assert res.ast_valid is False
    assert any("SyntaxError" in err for err in res.errors)


def test_speculative_draft_validator_disallowed_patterns():
    validator = SpeculativeDraftValidator()
    unsafe_code = "import os\n__import__('os').system('ls -la')\n"
    draft = Draft(source=unsafe_code, model_id="unsafe_model")
    res = validator.verify(draft)

    assert res.is_accepted is False
    assert any("Pattern non consentito" in err for err in res.errors)


def test_speculative_draft_validator_select_best():
    validator = SpeculativeDraftValidator()
    draft1 = Draft(source="x = 1\n", model_id="m1")
    draft2 = Draft(source="class ComplexService:\n    def execute(self):\n        return True\n", model_id="m2")
    draft3 = Draft(source="def bad(:\n    pass\n", model_id="m3")

    best = validator.select_best_draft([draft1, draft2, draft3])
    assert best is not None
    assert best.model_id == "m2"


# -------------------------------------------------------------
# 2. DistributedHeartbeatSync Tests
# -------------------------------------------------------------
def test_distributed_heartbeat_sync_flow():
    sync = DistributedHeartbeatSync(timeout_s=1.0, min_quorum_ratio=0.5)

    sync.register_node("omen-16", role="architect")
    sync.register_node("asus-v16", role="coder")
    sync.register_node("mac-hub", role="control_plane")

    now = 1000.0
    sync.record_heartbeat("omen-16", latency_ms=10.5, timestamp=now)
    sync.record_heartbeat("asus-v16", latency_ms=15.2, timestamp=now)
    sync.record_heartbeat("mac-hub", latency_ms=0.5, timestamp=now)

    # Tutti vivi
    parts = sync.detect_partitions(current_time=now + 0.2)
    assert parts["omen-16"] is True
    assert parts["asus-v16"] is True
    assert parts["mac-hub"] is True
    assert sync.has_quorum(current_time=now + 0.2) is True

    # OMEN cade dopo 1.5s (> timeout 1.0s)
    parts_after = sync.detect_partitions(current_time=now + 1.5)
    assert parts_after["omen-16"] is False
    assert parts_after["asus-v16"] is False
    assert sync.has_quorum(current_time=now + 1.5) is False

    # ASUS e Mac mandano heartbeat
    sync.record_heartbeat("asus-v16", latency_ms=14.0, timestamp=now + 1.6)
    sync.record_heartbeat("mac-hub", latency_ms=0.4, timestamp=now + 1.6)

    parts_recovered = sync.detect_partitions(current_time=now + 1.7)
    assert parts_recovered["omen-16"] is False
    assert parts_recovered["asus-v16"] is True
    assert parts_recovered["mac-hub"] is True
    # 2 su 3 vivi -> quorum ok (> 50%)
    assert sync.has_quorum(current_time=now + 1.7) is True

    health = sync.get_cluster_health(current_time=now + 1.7)
    assert health["total_nodes"] == 3
    assert health["alive_nodes"] == 2
    assert health["partitioned_nodes"] == 1


# -------------------------------------------------------------
# 3. DynamicKVMemoryPool Tests
# -------------------------------------------------------------
def test_dynamic_kv_memory_pool_allocation_and_deallocation():
    pool = DynamicKVMemoryPool(capacity_blocks=10, block_size_bytes=1024, idle_timeout_s=60.0)

    # Alloca 4 blocchi per ctx-1
    blocks1 = pool.allocate("ctx-1", num_blocks=4)
    assert len(blocks1) == 4
    stats1 = pool.stats()
    assert stats1["used_blocks"] == 4
    assert stats1["free_blocks"] == 6

    # Alloca 6 blocchi per ctx-2
    blocks2 = pool.allocate("ctx-2", num_blocks=6)
    assert len(blocks2) == 6
    stats2 = pool.stats()
    assert stats2["used_blocks"] == 10
    assert stats2["free_blocks"] == 0

    # Chiedere altri blocchi genera MemoryError
    with pytest.raises(MemoryError):
        pool.allocate("ctx-3", num_blocks=1)

    # Dealloca ctx-1
    freed = pool.deallocate("ctx-1")
    assert freed == 4
    stats3 = pool.stats()
    assert stats3["free_blocks"] == 4
    assert stats3["used_blocks"] == 6


def test_dynamic_kv_memory_pool_auto_eviction():
    pool = DynamicKVMemoryPool(capacity_blocks=4, block_size_bytes=1024, idle_timeout_s=2.0)
    pool.allocate("ctx-idle", num_blocks=4)
    assert pool.stats()["free_blocks"] == 0

    # Simula passaggio del tempo
    simulated_now = time.time() + 3.0
    evicted = pool.evict_idle_contexts(current_time=simulated_now)
    assert evicted == 4
    assert pool.stats()["free_blocks"] == 4


# -------------------------------------------------------------
# 4. ArcadeStateSyncEngine Tests
# -------------------------------------------------------------
def test_arcade_state_sync_engine_movement_and_rollback():
    engine = ArcadeStateSyncEngine(tick_rate_hz=60, rollback_ticks=20)
    engine.register_entity("player-1", x=0.0, y=0.0, vx=10.0, vy=0.0)

    # Avanza di 5 tick
    engine.update(num_ticks=5)
    state = engine.get_state()
    assert state.tick == 5
    pos_x, pos_y = state.positions["player-1"]
    assert pos_x > 0.0  # Si è mosso lungo X

    # Invia input in ritardo per tick 2 (dx = 50.0)
    engine.apply_input("player-1", {"dx": 50.0}, for_tick=2)
    state_after_reconciliation = engine.get_state()
    pos_x_new, _ = state_after_reconciliation.positions["player-1"]

    # Con il rollback deterministico, la coordinata X è aumentata notevolmente
    assert pos_x_new > pos_x

    stats = engine.stats()
    assert stats["current_tick"] == 5
    assert stats["entities_count"] == 1
    assert stats["history_buffer_len"] > 0
