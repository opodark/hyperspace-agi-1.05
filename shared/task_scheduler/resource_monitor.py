# SPDX-License-Identifier: Apache-2.0
import threading
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class NodeTelemetry:
    node_id: str
    vram_free_gb: float
    vram_total_gb: float
    gpu_temp_c: float
    is_thermal_throttling: bool
    load_ratio: float  # 0.0 - 1.0

class ResourceGovernor:
    def __init__(self):
        self._nodes: Dict[str, NodeTelemetry] = {}
        self._lock = threading.RLock()

    def register_node(self, telemetry: NodeTelemetry) -> None:
        with self._lock:
            self._nodes[telemetry.node_id] = telemetry

    def can_admit_task(self, node_id: str, required_vram_gb: float = 1.0) -> bool:
        with self._lock:
            node = self._nodes.get(node_id)
            if not node or node.is_thermal_throttling:
                return False
            return node.vram_free_gb >= required_vram_gb

    def get_optimal_target_node(self, task_cost_gb: float) -> Optional[str]:
        with self._lock:
            best_id: Optional[str] = None
            best_score: float = float("-inf")
            for node in self._nodes.values():
                if node.is_thermal_throttling:
                    continue
                vram_ratio = node.vram_free_gb / node.vram_total_gb
                score = vram_ratio - (node.gpu_temp_c / 100.0) - node.load_ratio
                if score > best_score and node.vram_free_gb >= task_cost_gb:
                    best_score = score
                    best_id = node.node_id
            return best_id