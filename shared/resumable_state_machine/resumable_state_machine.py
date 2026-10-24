from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional

try:
    from .state_schema import RunState, ExecutionStatus
    from .checkpoint_store import CheckpointStore
    from .idempotent_executor import IdempotentGateway
except (ImportError, ValueError):
    from state_schema import RunState, ExecutionStatus
    from checkpoint_store import CheckpointStore
    from idempotent_executor import IdempotentGateway


class ResumableStateMachine:
    """Motore a stati resiliente a passi sequenziali con confini transazionali di checkpoint."""

    def __init__(
        self,
        store: CheckpointStore,
        gateway: Optional[IdempotentGateway] = None
    ) -> None:
        self.store = store
        self.gateway = gateway or IdempotentGateway()
        self._lock = threading.RLock()
        self._steps: Dict[int, tuple[str, Callable[[RunState], Any]]] = {}
        self.current_state: Optional[RunState] = None

    def register_step(self, step_index: int, name: str, fn: Callable[[RunState], Any]) -> None:
        with self._lock:
            self._steps[step_index] = (name, fn)

    def start_or_resume(self, run_id: str, initial_payload: Optional[dict] = None) -> RunState:
        with self._lock:
            latest_id = None
            try:
                latest_id = self.store.get_latest_checkpoint()
            except (FileNotFoundError, ValueError):
                latest_id = None

            if latest_id:
                try:
                    loaded = self.store.load_checkpoint(latest_id)
                    # Supporta sia dizionario sia dataclass RunState
                    if isinstance(loaded, dict):
                        self.current_state = RunState.from_dict(loaded)
                    else:
                        self.current_state = loaded
                except Exception:
                    self.current_state = None

            if not self.current_state or self.current_state.run_id != run_id:
                self.current_state = RunState(
                    run_id=run_id,
                    version=1,
                    status=ExecutionStatus.RUNNING.value,
                    step_index=0,
                    payload=initial_payload or {}
                )
                self.store.save_checkpoint(self.current_state.to_dict())

            return self.current_state

    def step(self) -> RunState:
        with self._lock:
            if not self.current_state:
                raise RuntimeError("Macchina a stati non avviata. Chiama start_or_resume() prima.")

            if self.current_state.status != ExecutionStatus.RUNNING.value:
                return self.current_state

            idx = self.current_state.step_index
            if idx not in self._steps:
                # Tutti i passi completati
                self.current_state = self.current_state.clone_with_update(status=ExecutionStatus.COMPLETED.value)
                self.store.save_checkpoint(self.current_state.to_dict())
                return self.current_state

            step_name, fn = self._steps[idx]
            action_key = f"{self.current_state.run_id}:step_{idx}:{step_name}"

            # Esecuzione protetta da gateway idempotente
            result, cached = self.gateway.execute_action(action_key, fn, self.current_state)

            new_payload = dict(self.current_state.payload)
            if isinstance(result, dict):
                new_payload.update(result)
            else:
                new_payload[step_name] = result

            next_idx = idx + 1
            next_status = ExecutionStatus.COMPLETED.value if next_idx >= len(self._steps) else ExecutionStatus.RUNNING.value

            self.current_state = self.current_state.clone_with_update(
                status=next_status,
                step_index=next_idx,
                payload=new_payload
            )
            # Salva checkpoint atomico al confine del passo
            self.store.save_checkpoint(self.current_state.to_dict())
            return self.current_state

    def pause(self, reason: str = "human_review") -> RunState:
        with self._lock:
            if not self.current_state:
                raise RuntimeError("Stato assente")
            meta = dict(self.current_state.metadata)
            meta["pause_reason"] = reason
            self.current_state = self.current_state.clone_with_update(
                status=ExecutionStatus.PAUSED.value,
                metadata=meta
            )
            self.store.save_checkpoint(self.current_state.to_dict())
            return self.current_state

    def resume(self) -> RunState:
        with self._lock:
            if not self.current_state:
                raise RuntimeError("Stato assente")
            self.current_state = self.current_state.clone_with_update(status=ExecutionStatus.RUNNING.value)
            self.store.save_checkpoint(self.current_state.to_dict())
            return self.current_state
