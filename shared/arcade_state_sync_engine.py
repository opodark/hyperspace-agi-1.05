# SPDX-License-Identifier: Apache-2.0
"""
Arcade State Sync Engine per HyperSpace Sovereign Mesh.

Motore di sincronizzazione di stato real-time con buffer di rollback deterministico,
riconciliazione immediata degli input e zero-lag per applicazioni interattive,
simulazioni e minigiochi multiplayer distribuiti tra nodi della mesh.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ArcadeState:
    """Stato immutabile o snapshot di un tick di simulazione."""
    tick: int
    timestamp: float
    positions: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    velocities: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    scores: Dict[str, int] = field(default_factory=dict)
    phase: str = "running"  # "lobby", "running", "paused", "completed"
    inputs: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def clone(self) -> ArcadeState:
        """Copia profonda dello stato per il buffer di rollback."""
        return ArcadeState(
            tick=self.tick,
            timestamp=self.timestamp,
            positions=copy.deepcopy(self.positions),
            velocities=copy.deepcopy(self.velocities),
            scores=copy.deepcopy(self.scores),
            phase=self.phase,
            inputs=copy.deepcopy(self.inputs)
        )


class ArcadeStateSyncEngine:
    """
    Motore deterministico a tick fisso con buffer circolare di rollback.
    Implementa l'algoritmo di riconciliazione Client-Side Prediction / Rollback.
    """

    def __init__(
        self,
        tick_rate_hz: int = 60,
        rollback_ticks: int = 30,
        snapshot_interval: int = 1
    ):
        self.tick_rate_hz = max(1, tick_rate_hz)
        self.dt = 1.0 / self.tick_rate_hz
        self.rollback_ticks = rollback_ticks
        self.snapshot_interval = snapshot_interval

        self.current_state: ArcadeState = ArcadeState(
            tick=0,
            timestamp=time.time(),
            positions={},
            velocities={},
            scores={},
            phase="running",
            inputs={}
        )

        # Buffer storico ordinato degli snapshot per il rollback
        self._history: List[ArcadeState] = [self.current_state.clone()]
        # Registro di tutti gli input storici per riproduzione nel rollback: tick -> {player_id: input_data}
        self._input_journal: Dict[int, Dict[str, Any]] = {}

    def register_entity(self, entity_id: str, x: float = 0.0, y: float = 0.0, vx: float = 0.0, vy: float = 0.0):
        """Aggiunge una nuova entità/nodo alla simulazione."""
        self.current_state.positions[entity_id] = (x, y)
        self.current_state.velocities[entity_id] = (vx, vy)
        self.current_state.scores.setdefault(entity_id, 0)

    def apply_input(self, entity_id: str, input_data: Dict[str, Any], for_tick: Optional[int] = None):
        """
        Registra l'input proveniente da un nodo/giocatore.
        Se l'input appartiene a un tick passato, è necessario un rollback per riconciliarlo.
        """
        target_tick = for_tick if for_tick is not None else self.current_state.tick
        if target_tick not in self._input_journal:
            self._input_journal[target_tick] = {}
        self._input_journal[target_tick][entity_id] = input_data

        if target_tick < self.current_state.tick:
            # Input arrivato in ritardo (lag di rete): trigger del rollback deterministico
            self.rollback_and_replay(target_tick)
        else:
            self.current_state.inputs[entity_id] = input_data

    def _step_simulation(self, state: ArcadeState, dt: float) -> ArcadeState:
        """Esegue un singolo passo deterministico della fisica e delle regole."""
        next_state = state.clone()
        next_state.tick += 1
        next_state.timestamp += dt

        # Recupera gli input programmati per questo tick
        tick_inputs = self._input_journal.get(state.tick, state.inputs)
        next_state.inputs = copy.deepcopy(tick_inputs)

        # Aggiorna posizioni in base a velocità e input direzionali
        for entity_id, (x, y) in state.positions.items():
            vx, vy = state.velocities.get(entity_id, (0.0, 0.0))
            inp = tick_inputs.get(entity_id, {})
            # Modificatori da input
            ax = float(inp.get("dx", 0.0))
            ay = float(inp.get("dy", 0.0))
            new_vx = vx + ax
            new_vy = vy + ay
            new_x = x + new_vx * dt
            new_y = y + new_vy * dt

            next_state.positions[entity_id] = (round(new_x, 4), round(new_y, 4))
            next_state.velocities[entity_id] = (round(new_vx, 4), round(new_vy, 4))

        return next_state

    def update(self, num_ticks: int = 1) -> ArcadeState:
        """Avanza la simulazione del numero specificato di tick."""
        for _ in range(num_ticks):
            self.current_state = self._step_simulation(self.current_state, self.dt)

            if self.current_state.tick % self.snapshot_interval == 0:
                self._history.append(self.current_state.clone())

            # Mantieni solo gli ultimi rollback_ticks nella storia
            while len(self._history) > self.rollback_ticks + 1:
                oldest = self._history.pop(0)
                # Bonifica il giornale degli input per i tick non più raggiungibili
                self._input_journal.pop(oldest.tick, None)

        return self.current_state

    def rollback_and_replay(self, target_tick: int) -> bool:
        """
        Riavvolge lo stato al tick target e riesegue tutti gli step fino al tick corrente
        incorporando i nuovi input ricevuti.
        """
        snapshot_idx = -1
        for i, snap in enumerate(self._history):
            if snap.tick == target_tick:
                snapshot_idx = i
                break

        if snapshot_idx == -1:
            # Target fuori dal buffer di rollback
            return False

        current_target_tick = self.current_state.tick
        reconstructed = self._history[snapshot_idx].clone()

        # Rigioca tutti i tick intermedi fino a ritornare al presente
        while reconstructed.tick < current_target_tick:
            reconstructed = self._step_simulation(reconstructed, self.dt)

        self.current_state = reconstructed
        return True

    def get_state(self) -> ArcadeState:
        """Restituisce lo stato attuale della simulazione."""
        return self.current_state

    def stats(self) -> Dict[str, Any]:
        """Restituisce le statistiche operative dell'engine."""
        return {
            "current_tick": self.current_state.tick,
            "tick_rate_hz": self.tick_rate_hz,
            "entities_count": len(self.current_state.positions),
            "history_buffer_len": len(self._history),
            "rollback_window_ticks": self.rollback_ticks,
            "journal_entries": len(self._input_journal),
            "phase": self.current_state.phase
        }
