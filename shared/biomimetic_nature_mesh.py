#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# shared/biomimetic_nature_mesh.py
# Modulo promosso in produzione da HyperSpace R&D Sovereign Lab
# Prototipo sorgente: proto_biomimetic_nature_mesh_1793534226.py
# Data promozione: 2026-11-01T13:06:10.981942+00:00
# Autore: antigravity_sovereign

import random
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple

# --- Meccanismo 1: Micelio ---
class MyceliumNetwork:
    """
    Rete biomimetica a micelio: rinforza le connessioni ad alto flusso
    e pota i percorsi ad alta latenza o basso throughput.
    """
    def __init__(self, num_nodes: int):
        self.num_nodes = num_nodes
        self.paths: Dict[tuple, float] = {}
        self.latencies: Dict[tuple, float] = {}
        self.flow_strength: List[float] = [random.random() for _ in range(num_nodes)]

    def reinforce(self, path: tuple, amount: float = 1.2) -> float:
        current = self.paths.get(path, 1.0)
        new_weight = current * amount
        self.paths[path] = new_weight
        return new_weight

    def prune(self, latency_threshold: float) -> List[tuple]:
        pruned = []
        for path, lat in list(self.latencies.items()):
            if lat > latency_threshold:
                pruned.append(path)
                self.paths.pop(path, None)
                self.latencies.pop(path, None)
        return pruned


# --- Meccanismo 2: Quorum Sensing ---
class BacterialQuorum:
    """
    Quorum sensing batterico: attiva compiti computazionali pesanti (MoE, WAL compaction)
    solo quando la densità di nodi attivi supera la soglia critica.
    """
    def __init__(self, threshold: float = 0.7, total_nodes: int = 10):
        self.threshold = threshold
        self.active_nodes = 0
        self.total_nodes = max(total_nodes, 1)

    def update_density(self, current: int) -> bool:
        self.active_nodes = current
        return (self.active_nodes / self.total_nodes) >= self.threshold

    def trigger_task(self, task: Any) -> Any:
        if (self.active_nodes / self.total_nodes) >= self.threshold:
            if callable(task):
                return task()
            elif hasattr(task, "execute") and callable(task.execute):
                return task.execute()
            return True
        return None


# --- Meccanismo 3: Virus ed Epidemic Gossip ---
class EpidemicGossip:
    """
    Gossip epidemico con filtro antigenico: propaga payload immutabili
    e rigetta stati alterati o non conformi.
    """
    def __init__(self, antigenic_filter: bool = True):
        self.antigenic_filter = antigenic_filter
        self.state_payloads: List[Any] = []

    def filter_corrupt(self, payload: Any) -> bool:
        if not self.antigenic_filter:
            return True
        if payload is None:
            return False
        if isinstance(payload, dict) and payload.get("corrupted", False):
            return False
        return True

    def replicate(self, payload: Any) -> bool:
        if self.filter_corrupt(payload):
            self.state_payloads.append(payload)
            return True
        return False


# --- Meccanismo 4: Cleptoparassitismo Simbiotico ---
class SymbioticCleptoparasitism:
    """
    Cleptoparassitismo simbiotico: nodi edge leggeri drenano cicli di calcolo
    inutilizzati dai nodi pesanti (host) quando sono idle.
    """
    def __init__(self, steal_rate: float = 0.1):
        self.steal_rate = steal_rate

    def steal_cycles(self, host_capacity: float) -> float:
        if host_capacity > 0.1:
            return host_capacity * self.steal_rate
        return 0.0


# --- Nodi e Connessioni Topologiche ---
class Node:
    def __init__(self, node_id: str, node_type: str = 'heavy', compute_capacity: Optional[float] = None):
        self.id = node_id
        self.type = node_type  # 'heavy' o 'edge'
        self.compute_capacity = compute_capacity if compute_capacity is not None else random.uniform(1.0, 10.0)
        self.active = True
        self.flow_weight = 1.0
        self.state: Optional[Any] = None


class Connection:
    def __init__(self, src: Any, dst: Any, latency: Optional[float] = None, bandwidth: Optional[float] = None, weight: float = 1.0):
        self.src = src.id if isinstance(src, Node) else str(src)
        self.dst = dst.id if isinstance(dst, Node) else str(dst)
        self.latency = latency if latency is not None else random.uniform(1.0, 50.0)
        self.bandwidth = bandwidth if bandwidth is not None else random.uniform(10.0, 100.0)
        self.weight = weight
        self.pruned = False


class MeshOrchestrator:
    def __init__(self, num_nodes: int = 10, nodes: Optional[List[Node]] = None):
        if nodes is not None:
            self.nodes = list(nodes)
        else:
            self.nodes = [Node(f'n{i}', 'heavy' if i % 2 == 0 else 'edge') for i in range(num_nodes)]
        self.connections: List[Connection] = []
        self._init_connections()

    def _init_connections(self):
        for i in range(len(self.nodes)):
            for j in range(i + 1, len(self.nodes)):
                if random.random() < 0.4:
                    conn = Connection(self.nodes[i], self.nodes[j])
                    self.connections.append(conn)

    def reinforce_and_prune(self, threshold: float = 0.5):
        node_map = {n.id: n for n in self.nodes}
        for conn in self.connections:
            if conn.pruned:
                continue
            src_node = node_map.get(conn.src)
            dst_node = node_map.get(conn.dst)
            src_cap = src_node.compute_capacity if src_node else 1.0
            dst_cap = dst_node.compute_capacity if dst_node else 1.0
            traffic = (src_cap + dst_cap) / 2.0
            flow_score = traffic / (conn.latency + 1.0)
            if flow_score > threshold:
                conn.weight *= 1.2
            else:
                conn.weight *= 0.8
                if conn.weight < 0.2:
                    conn.pruned = True

    def check_quorum(self, threshold: int = 5) -> bool:
        active_nodes = sum(1 for n in self.nodes if n.active)
        autoinducer = active_nodes / len(self.nodes) if self.nodes else 0.0
        return autoinducer >= (threshold / len(self.nodes)) if self.nodes else False

    def gossip_state(self, state_payload: Any) -> int:
        accepted = 0
        for node in self.nodes:
            if self._antigenic_filter(state_payload):
                node.state = state_payload
                accepted += 1
        return accepted

    def _antigenic_filter(self, payload: Any) -> bool:
        if payload is None:
            return False
        if isinstance(payload, dict) and payload.get("corrupted", False):
            return False
        return True

    def steal_compute(self) -> List[Dict[str, Any]]:
        edge_nodes = [n for n in self.nodes if n.type == 'edge']
        heavy_nodes = [n for n in self.nodes if n.type == 'heavy']
        stolen_records = []
        for edge in edge_nodes:
            if not heavy_nodes:
                break
            idle_heavy = min(heavy_nodes, key=lambda h: h.compute_capacity)
            if idle_heavy.compute_capacity > 0.5:
                steal_amount = min(0.5, idle_heavy.compute_capacity * 0.2)
                idle_heavy.compute_capacity -= steal_amount
                edge.compute_capacity += steal_amount
                stolen_records.append({
                    "edge_id": edge.id,
                    "host_id": idle_heavy.id,
                    "stolen": steal_amount,
                })
        return stolen_records


# --- Moduli di Monitoraggio Avanzato ---
class MeshEntropyMonitor:
    def __init__(self, orchestrator: MeshOrchestrator):
        self.orchestrator = orchestrator

    def calculate_entropy(self) -> float:
        degrees = [
            len([c for c in self.orchestrator.connections if not c.pruned and (c.src == n.id or c.dst == n.id)])
            for n in self.orchestrator.nodes
        ]
        total = sum(degrees)
        if total == 0:
            return 0.0
        probs = [d / total for d in degrees]
        entropy = -sum(p * math.log2(p) for p in probs if p > 0)
        return entropy


class FlowEffectivenessMonitor:
    def __init__(self, orchestrator: MeshOrchestrator):
        self.orchestrator = orchestrator

    def compute_metrics(self) -> Dict[str, float]:
        active_conns = [c for c in self.orchestrator.connections if not c.pruned and c.weight > 0]
        if not active_conns:
            return {
                'avg_latency': 0.0,
                'throughput': 0.0,
                'efficiency': 0.0,
            }
        avg_latency = sum(c.latency for c in active_conns) / len(active_conns)
        throughput = sum(c.bandwidth * c.weight for c in active_conns)
        efficiency = throughput / (avg_latency + 1.0)
        return {
            'avg_latency': avg_latency,
            'throughput': throughput,
            'efficiency': efficiency,
        }


# --- Mesh Metrics & Monitor Legacy ---
@dataclass
class MeshMetrics:
    entropy: float = 0.0
    flow_effectiveness: float = 0.0


class HyperSpaceMeshMonitor:
    def __init__(self, num_nodes: int):
        self.num_nodes = num_nodes
        self.latencies = [random.uniform(1.0, 100.0) for _ in range(num_nodes)]
        self.throughput = 0.0
        self.successful_messages = 0

    def compute_entropy(self) -> float:
        if not self.latencies:
            return 0.0
        probs = [1 / len(self.latencies)] * len(self.latencies)
        return -sum(p * math.log2(p) for p in probs if p > 0)

    def compute_flow_effectiveness(self) -> float:
        if self.throughput == 0:
            return 0.0
        return self.successful_messages / self.throughput

    def update_metrics(self, latencies: List[float], throughput: float, success: int):
        self.latencies = latencies
        self.throughput = throughput
        self.successful_messages = success
