# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class RunState:
    run_id: str = "default"
    version: int = 0
    status: str = "running"
    step_index: int = 0
    payload: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    idempotency_keys: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    _lock = threading.RLock()

    @property
    def hash(self) -> str:
        canonical = f"{self.run_id}:{self.version}:{self.status}:{self.step_index}:{sorted(self.payload.items())}"
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "version": self.version,
            "status": self.status,
            "step_index": self.step_index,
            "payload": dict(self.payload),
            "artifacts": list(self.artifacts),
            "idempotency_keys": list(self.idempotency_keys),
            "metadata": dict(self.metadata)
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RunState":
        return cls(
            run_id=data.get("run_id", "default"),
            version=data.get("version", 0),
            status=data.get("status", "running"),
            step_index=data.get("step_index", 0),
            payload=data.get("payload", {}),
            artifacts=data.get("artifacts", []),
            idempotency_keys=set(data.get("idempotency_keys", [])),
            metadata=data.get("metadata", {})
        )

    def clone_with_update(self, status: Optional[str] = None, **kwargs) -> "RunState":
        with self._lock:
            updates = dict(kwargs)
            if status is not None:
                updates["status"] = status
            updates["version"] = self.version + 1
            return replace(self, **updates)
