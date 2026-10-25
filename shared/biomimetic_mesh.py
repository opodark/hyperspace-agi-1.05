#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
shared/biomimetic_mesh.py — Architettura Biomimetica per HyperSpace Sovereign Mesh

Trae ispirazione diretta dai meccanismi biologici della natura per evolvere la mesh decentralizzata:
1. Funghi & Micelio (Slime Mold / Physarum polycephalum):
   Routing adattivo con rinforzo dei canali ad alto flusso e potatura (pruning) delle connessioni inattive.
2. Batteri (Quorum Sensing & Autoinduttori):
   Consenso decentralizzato basato sulla densità molecolare di segnale (autoinduttori)
   prima di attivare fenotipi costosi (MoE 40B, compattazione WAL, consolidamento dei sogni).
3. Virus (Epidemic Gossip & Diffusione Virale con Antigene):
   Propagazione esponenziale di stati immutabili (vector clocks, AST validati) con filtro
   antigenico crittografico e sintattico contro payload maligni.
4. Parassiti & Cleptoparassitismo Simbiotico (Dynamic Work-Stealing):
   Nodi edge leggeri che "rubano" cicli di calcolo idle da host potenti (OMEN 16, ASUS)
   cedendo istantaneamente il passo appena l'host riprende carichi prioritari.
"""

from __future__ import annotations

import hashlib
import heapq
import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


# =====================================================================
# 1. FUNGO & MICELIO: Physarum Polycephalum Adaptive Hyphal Routing
# =====================================================================

@dataclass
class HyphalConduit:
    """Canale/ifa di collegamento tra due nodi del micelio."""
    node_a: str
    node_b: str
    length: float           # Latenza / distanza fisica (costo base)
    conductivity: float     # D_ij: conduttività del canale (diametro dell'ifa)
    last_flux: float = 0.0  # Ultimo flusso transitato
    updated_at: float = field(default_factory=time.time)


class MyceliumNetworkRouter:
    """Router biomimetico basato sulle reti miceliali e il modello di Physarum.

    Rinforza i canali attraversati da traffico dati e ritira (potatura)
    le connessioni con scarsa conduttività o elevata latenza.
    """

    def __init__(self, decay_rate: float = 0.05, reinforcement_factor: float = 0.2, min_conductivity: float = 0.02):
        self.decay_rate = decay_rate
        self.reinforcement_factor = reinforcement_factor
        self.min_conductivity = min_conductivity
        self.conduits: Dict[Tuple[str, str], HyphalConduit] = {}
        self.nodes: Set[str] = set()

    def _edge_key(self, u: str, v: str) -> Tuple[str, str]:
        return (u, v) if u <= v else (v, u)

    def add_node(self, node_id: str) -> None:
        self.nodes.add(node_id)

    def grow_hypha(self, u: str, v: str, latency_ms: float, initial_conductivity: float = 1.0) -> None:
        """Fa crescere una connessione (ifa) tra due nodi."""
        self.nodes.add(u)
        self.nodes.add(v)
        key = self._edge_key(u, v)
        self.conduits[key] = HyphalConduit(
            node_a=key[0],
            node_b=key[1],
            length=max(1.0, float(latency_ms)),
            conductivity=max(0.001, float(initial_conductivity)),
        )

    def reinforce_flux(self, u: str, v: str, flux_amount: float = 1.0) -> None:
        """Rinforza la conduttività dell'ifa quando vi transita un flusso di lavoro/dati."""
        key = self._edge_key(u, v)
        if key in self.conduits:
            c = self.conduits[key]
            c.last_flux += flux_amount
            # D_ij += alpha * flux
            c.conductivity += self.reinforcement_factor * abs(flux_amount)
            c.updated_at = time.time()

    def decay_and_prune(self) -> int:
        """Applica il decadimento temporale e pota (pruning) le ife sotto la soglia minima."""
        pruned_count = 0
        to_remove = []
        for key, conduit in self.conduits.items():
            # D_ij(t+1) = D_ij(t) * (1 - gamma)
            conduit.conductivity *= (1.0 - self.decay_rate)
            conduit.last_flux = 0.0
            if conduit.conductivity < self.min_conductivity:
                to_remove.append(key)

        for k in to_remove:
            del self.conduits[k]
            pruned_count += 1
        return pruned_count

    def find_optimal_path(self, source: str, target: str) -> Optional[List[str]]:
        """Dijkstra pesato per resistenza efficace R_ij = L_ij / D_ij."""
        if source not in self.nodes or target not in self.nodes:
            return None
        if source == target:
            return [source]

        # Adiacenza
        adj: Dict[str, List[Tuple[str, float]]] = {n: [] for n in self.nodes}
        for (u, v), c in self.conduits.items():
            cost = c.length / max(0.001, c.conductivity)
            adj[u].append((v, cost))
            adj[v].append((u, cost))

        distances: Dict[str, float] = {n: math.inf for n in self.nodes}
        previous: Dict[str, Optional[str]] = {n: None for n in self.nodes}
        distances[source] = 0.0

        pq = [(0.0, source)]
        while pq:
            d, curr = heapq.heappop(pq)
            if d > distances[curr]:
                continue
            if curr == target:
                break
            for neighbor, weight in adj.get(curr, []):
                new_dist = d + weight
                if new_dist < distances[neighbor]:
                    distances[neighbor] = new_dist
                    previous[neighbor] = curr
                    heapq.heappush(pq, (new_dist, neighbor))

        if distances[target] == math.inf:
            return None

        # Ricostruzione cammino
        path = []
        curr: Optional[str] = target
        while curr is not None:
            path.append(curr)
            curr = previous[curr]
        path.reverse()
        return path


# =====================================================================
# 2. BATTERI: Bacterial Quorum Sensing Consensus
# =====================================================================

@dataclass
class AutoinducerMolecule:
    """Segnale chimico/digitale secreto dai nodi batterici."""
    sender_id: str
    phenotype: str          # es. "activate_40b_inference", "compact_wal", "dream_cycle"
    concentration: float    # Intensità del segnale
    created_at: float = field(default_factory=time.time)


class BacterialQuorumGovernor:
    """Governatore basato sul Quorum Sensing dei batteri.

    I nodi secernono autoinduttori nell'ambiente comune. Quando la concentrazione
    aggregata supera la soglia critica di quorum, si attiva un fenotipo collettivo.
    """

    def __init__(self, half_life_seconds: float = 300.0):
        self.half_life_seconds = half_life_seconds
        self.signals: List[AutoinducerMolecule] = []

    def emit_autoinducer(self, sender_id: str, phenotype: str, concentration: float = 1.0) -> None:
        """Il nodo secerne un autoinduttore per richiedere o segnalare un fenotipo."""
        self.signals.append(AutoinducerMolecule(
            sender_id=sender_id,
            phenotype=phenotype,
            concentration=max(0.1, float(concentration)),
        ))

    def get_concentration(self, phenotype: str) -> float:
        """Calcola la concentrazione efficace attuale considerando il decadimento temporale."""
        now = time.time()
        total = 0.0
        active_signals = []
        decay_constant = math.log(2) / max(0.001, self.half_life_seconds)

        for sig in self.signals:
            if sig.phenotype != phenotype:
                active_signals.append(sig)
                continue
            elapsed = now - sig.created_at
            # C(t) = C0 * exp(-lambda * dt)
            effective = sig.concentration * math.exp(-decay_constant * elapsed)
            if effective > 0.01:
                total += effective
                active_signals.append(sig)

        self.signals = active_signals
        return round(total, 4)

    def check_quorum(self, phenotype: str, threshold: float = 2.5) -> bool:
        """Verifica se la concentrazione supera la soglia di consenso biologico."""
        return self.get_concentration(phenotype) >= threshold


# =====================================================================
# 3. VIRUS: Epidemic Gossip Dissemination & Antigen Validation
# =====================================================================

@dataclass
class ViralPayload:
    """Genoma virale (stato immutabile) trasmesso tra i nodi."""
    payload_id: str
    gene_type: str         # "ast_prototype", "vector_clock", "model_signature"
    content: str
    sha256_hash: str
    reproduction_rate: int = 3   # R0: fan-out per ogni salto
    hops: int = 0
    max_hops: int = 6


class ViralGossipDisseminator:
    """Diffusione epidemica/virale rapida di payload immutabili con filtro antigenico."""

    def __init__(self, known_nodes: Optional[List[str]] = None):
        self.known_nodes = list(known_nodes or [])
        self.infected_nodes: Dict[str, Set[str]] = {}  # payload_id -> set di nodi infetti
        self.antigen_blacklist: Set[str] = set()

    def package_payload(self, gene_type: str, content: str, max_hops: int = 6) -> ViralPayload:
        """Incapsula un contenuto in un virione immutabile con firma crittografica."""
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        pid = f"vir-{sha[:12]}"
        return ViralPayload(
            payload_id=pid,
            gene_type=gene_type,
            content=content,
            sha256_hash=sha,
            max_hops=max_hops,
        )

    def verify_antigen(self, virion: ViralPayload) -> bool:
        """Controllo immunitario/antigenico: verifica integrità hash e assenza di codice maligno."""
        if virion.payload_id in self.antigen_blacklist:
            return False
        # 1. Verifica crittografica
        actual_hash = hashlib.sha256(virion.content.encode("utf-8")).hexdigest()
        if actual_hash != virion.sha256_hash:
            self.antigen_blacklist.add(virion.payload_id)
            return False

        # 2. Se è codice Python, verifica validità sintattica AST
        if virion.gene_type in ("ast_prototype", "python_code"):
            import ast
            try:
                ast.parse(virion.content)
            except SyntaxError:
                self.antigen_blacklist.add(virion.payload_id)
                return False
        return True

    def infect_peer(self, virion: ViralPayload, recipient_node: str) -> bool:
        """Tenta di infettare un peer con il virione verificato."""
        if not self.verify_antigen(virion):
            return False
        if virion.payload_id not in self.infected_nodes:
            self.infected_nodes[virion.payload_id] = set()
        self.infected_nodes[virion.payload_id].add(recipient_node)
        return True

    def calculate_epidemic_spread(self, virion: ViralPayload) -> float:
        """Percentuale di nodi infettati rispetto al cluster totale."""
        if not self.known_nodes:
            return 1.0
        infected = len(self.infected_nodes.get(virion.payload_id, set()))
        return round(infected / len(self.known_nodes), 4)


# =====================================================================
# 4. PARASSITI: Symbiotic Kleptoparasitism (Adaptive Work-Stealing)
# =====================================================================

@dataclass
class HostCapacity:
    """Stato energetico e di calcolo del nodo ospitante."""
    host_id: str
    cpu_usage_pct: float
    gpu_usage_pct: float
    ram_usage_pct: float
    priority_task_active: bool = False
    updated_at: float = field(default_factory=time.time)


class SymbioticParasiteStealer:
    """Cleptoparassitismo simbiotico per nodi edge e worker leggeri.

    Ruba cicli di calcolo idle da host ad alte prestazioni (OMEN 16, ASUS)
    quando l'host è a riposo, disimpegnandosi all'istante appena l'host
    dichiara un compito prioritario locale.
    """

    def __init__(self, idle_cpu_threshold: float = 35.0, idle_gpu_threshold: float = 40.0):
        self.idle_cpu_threshold = idle_cpu_threshold
        self.idle_gpu_threshold = idle_gpu_threshold
        self.hosts: Dict[str, HostCapacity] = {}
        self.active_parasites: Dict[str, str] = {}  # task_id -> host_id

    def update_host_telemetry(self, host_id: str, cpu: float, gpu: float, ram: float, priority: bool = False) -> None:
        """Aggiorna le condizioni vitali dell'host ospitante."""
        self.hosts[host_id] = HostCapacity(
            host_id=host_id,
            cpu_usage_pct=cpu,
            gpu_usage_pct=gpu,
            ram_usage_pct=ram,
            priority_task_active=priority,
        )

    def can_parasitize(self, host_id: str) -> bool:
        """Verifica se l'host ha surplus energetico idoneo al prelievo simbiotico."""
        host = self.hosts.get(host_id)
        if not host:
            return False
        if host.priority_task_active:
            return False
        return host.cpu_usage_pct <= self.idle_cpu_threshold and host.gpu_usage_pct <= self.idle_gpu_threshold

    def acquire_stolen_slot(self, task_id: str, host_id: str) -> bool:
        """Tenta di allocare un task parassita sull'host."""
        if self.can_parasitize(host_id):
            self.active_parasites[task_id] = host_id
            return True
        return False

    def yield_host(self, host_id: str) -> List[str]:
        """Disimpegno immediato: rilascia tutti i task parassiti per non intralciare l'host."""
        evicted = [t for t, h in self.active_parasites.items() if h == host_id]
        for t in evicted:
            del self.active_parasites[t]
        return evicted


# =====================================================================
# 5. METRICHE BIOMIMETICHE DI FLUSSO ED ENTROPIA (Shannon & Flow Score)
# =====================================================================

def calculate_mesh_entropy(loads: List[float]) -> float:
    """Calcola l'entropia informativa di Shannon sulla distribuzione del carico nei nodi.

    Un'entropia elevata indica una distribuzione uniforme e bilanciata del carico.
    """
    positive = [v for v in loads if v > 0]
    total = sum(positive)
    if total <= 0:
        return 0.0
    probs = [v / total for v in positive]
    return -sum(p * math.log2(p) for p in probs if p > 0)


def calculate_flow_effectiveness(
    latency_ms: float,
    throughput_gbps: float,
    threshold_latency_ms: float = 50.0,
    max_throughput_gbps: float = 10.0,
) -> float:
    """Valuta l'efficacia del flusso ifale combinando punteggio di latenza e throughput."""
    latency_score = max(0.0, 1.0 - (latency_ms / threshold_latency_ms))
    throughput_score = min(1.0, throughput_gbps / max_throughput_gbps) if throughput_gbps > 0 else 0.0
    return round(latency_score * throughput_score, 4)

