import time
import threading
from dataclasses import dataclass
from typing import Dict, Optional, List

@dataclass
class TaskLease:
    task_id: str
    worker_id: str
    lease_granted_at: float
    lease_duration_s: float
    heartbeat_at: Optional[float] = None

class FaultTolerantScheduler:
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self._leases: Dict[str, TaskLease] = {}
        self._retry_counts: Dict[str, int] = {}
        self._lock = threading.RLock()
        self.lease_granted_at = 0.0

    def acquire_lease(self, task_id: str, worker_id: str, duration_s: float = 2.0) -> bool:
        with self._lock:
            if task_id in self._leases:
                return False
            granted = time.time()
            self.lease_granted_at = granted
            self._leases[task_id] = TaskLease(
                task_id=task_id,
                worker_id=worker_id,
                lease_granted_at=granted,
                lease_duration_s=duration_s,
                heartbeat_at=granted,
            )
            return True

    def renew_lease(self, task_id: str, worker_id: str) -> bool:
        with self._lock:
            lease = self._leases.get(task_id)
            if not lease or lease.worker_id != worker_id:
                return False
            lease.heartbeat_at = time.time()
            retries = self._retry_counts.get(task_id, 0) + 1
            self._retry_counts[task_id] = retries
            if retries > self.max_retries:
                del self._leases[task_id]
                return False
            return True

    def check_and_reclaim_zombies(self, now: Optional[float] = None) -> List[str]:
        if now is None:
            now = time.time()
        reclaimed = []
        with self._lock:
            expired = [
                task_id
                for task_id, lease in self._leases.items()
                if lease.heartbeat_at is None or (lease.lease_granted_at + lease.lease_duration_s) < now
            ]
            for task_id in expired:
                del self._leases[task_id]
                reclaimed.append(task_id)
                retries = self._retry_counts.get(task_id, 0) + 1
                self._retry_counts[task_id] = retries
                if retries > self.max_retries:
                    # permanent failure handling
                    continue
        return reclaimed