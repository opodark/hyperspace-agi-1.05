# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import tempfile
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional

try:
    from .state_schema import RunState, ExecutionStatus
    from .checkpoint_store import CheckpointStore
    from .idempotent_executor import IdempotentGateway
except (ImportError, ValueError):
    from state_schema import RunState, ExecutionStatus
    from checkpoint_store import CheckpointStore
    from idempotent_executor import IdempotentGateway


class CrashTriggeredError(Exception):
    """Sollevata per simulare un crash forzato del processo durante uno step."""
    pass


class MissionState:
    def __init__(self, mission_id: str, steps: List[str]) -> None:
        self.mission_id = mission_id
        self.all_steps = list(steps)
        self.completed_steps: List[str] = []
        self.status: str = ExecutionStatus.PENDING.value
        self.step_idx: int = 0

    @property
    def current_step(self) -> Optional[str]:
        if self.step_idx < len(self.all_steps):
            return self.all_steps[self.step_idx]
        return None

    def to_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "all_steps": self.all_steps,
            "completed_steps": self.completed_steps,
            "status": self.status,
            "step_idx": self.step_idx
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MissionState":
        s = cls(data["mission_id"], data["all_steps"])
        s.completed_steps = list(data.get("completed_steps", []))
        s.status = data.get("status", ExecutionStatus.PENDING.value)
        s.step_idx = data.get("step_idx", 0)
        return s


class DistributedResumableEngine:
    """Motore distribuito resiliente con Write-Ahead Log e ripresa trasparente post-crash."""

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        if storage_dir is None:
            self._temp_dir = tempfile.TemporaryDirectory()
            self.storage_dir = Path(self._temp_dir.name)
        else:
            self.storage_dir = Path(storage_dir)
            self._temp_dir = None

        self.store = CheckpointStore(self.storage_dir)
        self.gateway = IdempotentGateway()
        self._lock = RLock()
        self._missions: Dict[str, MissionState] = {}
        self._crash_on_step: Optional[str] = None
        self.notifications: List[str] = []

    def create_mission(self, mission_id: str, steps: List[str]) -> None:
        with self._lock:
            state = MissionState(mission_id, steps)
            state.status = ExecutionStatus.RUNNING.value
            self._missions[mission_id] = state
            self.store.save_checkpoint(state.to_dict())

    def crash_at_next(self, step_name: str) -> None:
        with self._lock:
            self._crash_on_step = step_name

    def run_next(self, mission_id: str) -> MissionState:
        with self._lock:
            state = self._missions.get(mission_id)
            if not state:
                state = self.resume_crashed_mission(mission_id)

            curr = state.current_step
            if not curr:
                state.status = ExecutionStatus.COMPLETED.value
                return state

            # Simulazione iniezione di crash
            if self._crash_on_step and curr == self._crash_on_step:
                self._crash_on_step = None
                # Salva stato di fallimento/interruzione prima del crash
                state.status = ExecutionStatus.FAILED.value
                self.store.save_checkpoint(state.to_dict())
                raise CrashTriggeredError(f"Simulated process crash at step '{curr}'")

            # Esecuzione idempotente dell'azione
            action_key = f"{mission_id}:{curr}"

            def do_action():
                if curr == "external_notify":
                    self.notifications.append("external_notify")
                return f"result_of_{curr}"

            self.gateway.execute_action(action_key, do_action)

            # Transizione e salvataggio checkpoint atomico
            state.completed_steps.append(curr)
            state.step_idx += 1
            if state.step_idx >= len(state.all_steps):
                state.status = ExecutionStatus.COMPLETED.value
            else:
                state.status = ExecutionStatus.RUNNING.value

            self.store.save_checkpoint(state.to_dict())
            return state

    def resume_crashed_mission(self, mission_id: str) -> MissionState:
        with self._lock:
            # Ricarica dall'ultimo checkpoint WAL
            latest_id = self.store.get_latest_checkpoint()
            raw_data = self.store.load_checkpoint(latest_id)
            data = raw_data if isinstance(raw_data, dict) else raw_data.__dict__

            state = MissionState.from_dict(data)
            state.status = ExecutionStatus.RUNNING.value
            self._missions[mission_id] = state
            return state
