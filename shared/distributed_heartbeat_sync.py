# SPDX-License-Identifier: Apache-2.0
"""
Distributed Heartbeat Sync per HyperSpace Sovereign Mesh.

Coordinatore asincrono di battito cardiaco e rilevatore di partizioni di rete (Split-Brain)
per la topologia decentralizzata inter-nodo (HP OMEN, ASUS, Mac M5 Hub).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class NodeHeartbeatState:
    """Stato del battito cardiaco di un singolo nodo del cluster."""
    node_id: str
    role: str = "worker"
    last_beat: Optional[float] = None
    last_latency_ms: float = 0.0
    heartbeat_count: int = 0
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class DistributedHeartbeatSync:
    """
    Coordinatore del battito cardiaco del cluster con rilevamento partizioni
    e protezione split-brain tramite quorum.
    """

    def __init__(
        self,
        cluster_name: str = "hyperspace-mesh",
        heartbeat_interval_s: float = 2.0,
        timeout_s: float = 6.0,
        min_quorum_ratio: float = 0.5
    ):
        self.cluster_name = cluster_name
        self.heartbeat_interval_s = heartbeat_interval_s
        self.timeout_s = timeout_s
        self.min_quorum_ratio = min_quorum_ratio
        self._nodes: Dict[str, NodeHeartbeatState] = {}
        self._lock = threading.Lock()

    def register_node(self, node_id: str, role: str = "worker", metadata: Optional[Dict[str, Any]] = None) -> NodeHeartbeatState:
        """Registra un nodo nella topologia di monitoraggio."""
        with self._lock:
            state = NodeHeartbeatState(node_id=node_id, role=role, metadata=metadata or {})
            self._nodes[node_id] = state
            return state

    def unregister_node(self, node_id: str) -> bool:
        """Rimuove un nodo dal monitoraggio."""
        with self._lock:
            return self._nodes.pop(node_id, None) is not None

    def record_heartbeat(self, node_id: str, latency_ms: float = 0.0, timestamp: Optional[float] = None) -> bool:
        """Registra l'avvenuto battito cardiaco da parte di un nodo."""
        now = timestamp if timestamp is not None else time.time()
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                # Registrazione on-the-fly
                node = NodeHeartbeatState(node_id=node_id)
                self._nodes[node_id] = node

            node.last_beat = now
            node.last_latency_ms = latency_ms
            node.heartbeat_count += 1
            node.is_active = True
            return True

    def detect_partitions(self, current_time: Optional[float] = None) -> Dict[str, bool]:
        """
        Verifica quali nodi sono attivi entro la soglia di timeout e quali
        risultano isolati o partizionati.
        Restituisce un dizionario: {node_id: is_alive_boolean}.
        """
        now = current_time if current_time is not None else time.time()
        status: Dict[str, bool] = {}
        with self._lock:
            for node_id, node in self._nodes.items():
                if node.last_beat is None:
                    is_alive = False
                else:
                    is_alive = (now - node.last_beat) <= self.timeout_s
                node.is_active = is_alive
                status[node_id] = is_alive
        return status

    def has_quorum(self, current_time: Optional[float] = None) -> bool:
        """Verifica se la partizione locale possiede il quorum minimo operativo."""
        partitions = self.detect_partitions(current_time)
        if not partitions:
            return True  # Cluster vuoto o singolo
        alive_count = sum(1 for is_alive in partitions.values() if is_alive)
        total_nodes = len(partitions)
        return (alive_count / total_nodes) > self.min_quorum_ratio

    def get_cluster_health(self, current_time: Optional[float] = None) -> Dict[str, Any]:
        """Restituisce un riepilogo globale della salute della mesh."""
        partitions = self.detect_partitions(current_time)
        total = len(partitions)
        alive = sum(1 for is_alive in partitions.values() if is_alive)
        quorum = self.has_quorum(current_time)

        with self._lock:
            nodes_info = {
                nid: {
                    "role": n.role,
                    "is_active": n.is_active,
                    "last_latency_ms": n.last_latency_ms,
                    "heartbeat_count": n.heartbeat_count,
                    "seconds_since_last": round((current_time or time.time()) - (n.last_beat or 0), 2) if n.last_beat else None
                }
                for nid, n in self._nodes.items()
            }

        return {
            "cluster_name": self.cluster_name,
            "total_nodes": total,
            "alive_nodes": alive,
            "partitioned_nodes": total - alive,
            "has_quorum": quorum,
            "nodes": nodes_info
        }
