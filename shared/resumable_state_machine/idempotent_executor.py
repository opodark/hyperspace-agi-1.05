# SPDX-License-Identifier: Apache-2.0
from typing import Any, Callable, Dict, Set, Tuple
import threading

class IdempotentGateway:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._executed_keys: Set[str] = set()
        self._cache: Dict[str, Any] = {}

    def execute_action(
        self, key: str, action_fn: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Tuple[Any, bool]:
        with self._lock:
            if key in self._executed_keys:
                return self._cache[key], True
            result = action_fn(*args, **kwargs)
            self._executed_keys.add(key)
            self._cache[key] = result
            return result, False

    def has_executed(self, key: str) -> bool:
        with self._lock:
            return key in self._executed_keys

    def get_executed_keys(self) -> Set[str]:
        with self._lock:
            return set(self._executed_keys)