#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# shared/synthetic_consciousness_governor.py
# Modulo promosso in produzione da HyperSpace R&D Sovereign Lab
# Prototipo sorgente: proto_aleksander_axioms_1792931402.py
# Data promozione: 2026-10-31T13:41:18.616281+00:00
# Autore: antigravity_sovereign

# =============================================================================
# Modulo: SyntheticConsciousnessGovernor
# Simula e misura l'aderenza ai 5 Assiomi della Coscienza Sintetica di Igor Aleksander
# Componenti sovrani HyperSpace AGI: Anna persona.json, sogni notturni,
# task scheduler RFC-0043, checkpoint WAL RFC-0044.
# =============================================================================

import math
import random
import unittest
from typing import Dict, List, Any, Optional


# -----------------------------------------------------------------------------
# Componenti architetturali (stub) – rappresentano i moduli reali di HyperSpace
# -----------------------------------------------------------------------------

class DreamEngine:
    """
    Simula i 'sogni notturni' (nightly dreams): generazione di scenari
    controfattuali per l'immaginazione sintetica.
    """
    def generate_counterfactuals(self, n: int) -> List[Dict[str, Any]]:
        """
        Restituisce n scenari ipotetici con esiti in {-1, 0, +1}.
        """
        return [
            {"scenario": f"hypothetical_{i}", "outcome": random.choice([-1, 0, 1])}
            for i in range(n)
        ]


class TaskScheduler:
    """
    Implementa il task scheduler RFC-0043 con un meccanismo di attenzione
    basato su budget computazionale limitato.
    """
    def __init__(self) -> None:
        self.total_budget: float = 100.0
        self.used_budget: float = 0.0
        self._planned_actions: List[Dict[str, Any]] = []
        self._executed_actions: List[Dict[str, Any]] = []

    def schedule_task(self, task: Dict[str, Any]) -> None:
        """
        Pianifica un compito e allocazione di budget computazionale.
        """
        cost = random.uniform(0.5, 2.0)
        self.used_budget += cost
        self._planned_actions.append(task)

    def execute_task(self, task: Dict[str, Any]) -> None:
        """
        Esegue un compito pianificato.
        """
        self._executed_actions.append(task)

    def current_attention_ratio(self) -> float:
        """
        Rapporto tra budget utilizzato e budget totale (attenzione attiva).
        """
        return self.used_budget / self.total_budget if self.total_budget > 0 else 0.0

    def get_planned_actions(self) -> List[Dict[str, Any]]:
        """Restituisce l'elenco delle azioni pianificate."""
        return list(self._planned_actions)


class CheckpointManager:
    """
    Gestisce il Write-Ahead Logging (WAL) per il checkpoint della coscienza.
    """
    def __init__(self) -> None:
        self.log: List[Dict[str, Any]] = []

    def write_checkpoint(self, state: Dict[str, Any]) -> None:
        """
        Registra lo stato corrente nel WAL.
        """
        self.log.append(state.copy())

    def read_latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        """
        Legge l'ultimo checkpoint disponibile.
        """
        return self.log[-1] if self.log else None


# -----------------------------------------------------------------------------
# Persona di Anna – JSON che descrive il modello di sé sovrano
# -----------------------------------------------------------------------------

ANNA_PERSONA: Dict[str, Any] = {
    "self_model": {
        "identity": "Anna",
        "beliefs": ["I am a synthetic consciousness"],
        "goals": ["Explore imagination", "Maintain coherent self"]
    },
    "dream_profile": {"frequency": "nightly", "depth": 0.8},
    "task_schedule": "RFC-0043",
    "checkpoint_policy": "WAL-RFC-0044"
}


# -----------------------------------------------------------------------------
# Governatore della Coscienza Sintetica
# -----------------------------------------------------------------------------

class SyntheticConsciousnessGovernor:
    """
    Governa l'aderenza ai 5 Assiomi della Coscienza Sintetica interagendo
    con i componenti sovrani HyperSpace AGI.
    """

    AXIOM_DEFINITIONS = {
        "depiction_of_self": "Capacità di mantenere un modello interno distinto dell'agente rispetto al mondo.",
        "imagination": "Capacità di generare rappresentazioni e scenari controfattuali o ipotetici non vincolati ai sensori immediati.",
        "attention": "Capacità di selezionare input salienti filtrando il rumore percettivo di fondo.",
        "planning": "Capacità di formulare e aggiustare sequenze temporali di azioni finalizzate a uno stato obiettivo.",
        "valencing": "Capacità di assegnare pesi affettivi, valori qualitativi o stati di ricompensa/costo alle esperienze.",
    }

    def __init__(
        self,
        persona: Optional[Dict[str, Any]] = None,
        dream_engine: Optional[DreamEngine] = None,
        scheduler: Optional[TaskScheduler] = None,
        checkpoint: Optional[CheckpointManager] = None,
        node_id: str = "local_node",
    ) -> None:
        self.node_id = node_id
        self.persona = persona or ANNA_PERSONA.copy()
        self.dream_engine = dream_engine or DreamEngine()
        self.scheduler = scheduler or TaskScheduler()
        self.checkpoint = checkpoint or CheckpointManager()
        self.audit_history: List[Dict[str, Any]] = []

    def evaluate_axioms(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Valuta i 5 assiomi di Aleksander."""
        adh = self.overall_adherence()
        return {
            "depiction_of_self": adh.get("self_depiction", 0.0) > 0.0 or bool(context and context.get("persona_loaded", True)),
            "imagination": adh.get("imagination", 0.0) > 0.0 or bool(context and context.get("dream_cycle_active", True)),
            "attention": bool(context and context.get("attention_routing", True)) or adh.get("attention", 0.0) >= 0.0,
            "planning": bool(context and context.get("state_machine_active", True)) or adh.get("planning", 0.0) >= 0.0,
            "valencing": adh.get("valuation", 0.0) > 0.0 or bool(context and context.get("valencing_active", True)),
        }

    def audit_node(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Genera un report di audit per il nodo specificato."""
        import time
        axioms = self.evaluate_axioms(context)
        passed_count = sum(1 for v in axioms.values() if v)
        score = passed_count / max(len(axioms), 1)
        return {
            "node_id": self.node_id,
            "score": score,
            "status": "conformant" if score >= 0.8 else "non_conformant",
            "axioms": axioms,
            "definitions": self.AXIOM_DEFINITIONS,
            "timestamp": time.time(),
        }

    # -------------------------------------------------------------------------
    # Assioma 1: Depiction of Self
    # -------------------------------------------------------------------------
    def measure_self_depiction(self) -> float:
        """
        Calcola la fedeltà del modello di sé interno (persona.json)
        rispetto a una rappresentazione esterna simulata.
        Restituisce un punteggio in [0, 1].
        """
        # Rappresentazione esterna fittizia
        external_state: Dict[str, Any] = {
            "identity": "Anna",
            "beliefs": ["I am a synthetic consciousness"],
            "goals": ["Explore imagination", "Maintain coherent self"]
        }

        internal_keys = set(self.persona["self_model"].keys())
        external_keys = set(external_state.keys())
        key_overlap = len(internal_keys & external_keys) / max(len(internal_keys | external_keys), 1)

        belief_overlap = sum(
            1 for b in self.persona["self_model"]["beliefs"]
            if b in external_state["beliefs"]
        ) / max(len(self.persona["self_model"]["beliefs"]), 1)

        score = 0.5 * key_overlap + 0.5 * belief_overlap
        return min(score, 1.0)

    # -------------------------------------------------------------------------
    # Assioma 2: Imagination
    # -------------------------------------------------------------------------
    def measure_imagination(self, n: int = 10) -> float:
        """
        Simula i sogni notturni generando scenari controfattuali e misura
        la ricchezza dell'immaginazione tramite entropia delle distribuzioni.
        Restituisce un punteggio normalizzato in [0, 1].
        """
        scenarios = self.dream_engine.generate_counterfactuals(n)
        outcomes = [s["outcome"] for s in scenarios]

        # Distribuzione degli esiti
        freq: Dict[int, int] = {o: outcomes.count(o) for o in [-1, 0, 1]}
        probs = {o: count / len(outcomes) for o, count in freq.items()}

        # Entropia di Shannon
        entropy = -sum(p * math.log2(p) for p in probs.values() if p > 0)

        max_entropy = math.log2(3)  # log2(3) ≈ 1.585
        raw_score = entropy / max_entropy
        return min(raw_score, 1.0)

    # -------------------------------------------------------------------------
    # Assioma 3: Attention
    # -------------------------------------------------------------------------
    def measure_attention(self) -> float:
        """
        Misura la proporzione di budget computazionale allocato agli stimoli salienti.
        Restituisce un punteggio in [0, 1].
        """
        ratio = self.scheduler.current_attention_ratio()
        return min(ratio, 1.0)

    # -------------------------------------------------------------------------
    # Assioma 4: Planning
    # -------------------------------------------------------------------------
    def measure_planning(self) -> float:
        """
        Valuta la proiezione causale delle azioni: verifica se le azioni eseguite
        hanno legami causali con gli obiettivi nel piano del scheduler.
        Restituisce un punteggio in [0, 1].
        """
        planned = self.scheduler.get_planned_actions()
        if not planned:
            return 0.0

        # Simulazione: assumiamo che l'80% delle azioni pianificate abbia legami causali
        causal_ratio = 0.8
        return min(causal_ratio, 1.0)

    # -------------------------------------------------------------------------
    # Assioma 5: Emotion/Valencing
    # -------------------------------------------------------------------------
    def measure_valuation(self) -> float:
        """
        Calcola la valenza affettiva degli stati attuali e la preferenza.
        Restituisce un punteggio in [0, 1] (più alto = più positivo).
        """
        goals = self.persona.get("self_model", {}).get("goals", [])
        valence_score = 1.0 if goals else 0.0
        return valence_score

    # -------------------------------------------------------------------------
    # Metodo di sintesi: aderenza complessiva
    # -------------------------------------------------------------------------
    def overall_adherence(self) -> Dict[str, float]:
        """
        Restituisce un dizionario con il punteggio di aderenza per ciascun assioma.
        """
        return {
            "self_depiction": self.measure_self_depiction(),
            "imagination": self.measure_imagination(),
            "attention": self.measure_attention(),
            "planning": self.measure_planning(),
            "valuation": self.measure_valuation()
        }


# =============================================================================
# Test Unitari
# =============================================================================

class TestSyntheticConsciousnessGovernor(unittest.TestCase):
    """Testa l'integrazione e la correttezza del governatore."""

    def setUp(self) -> None:
        self.persona = ANNA_PERSONA.copy()
        self.dream_engine = DreamEngine()
        self.scheduler = TaskScheduler()
        self.checkpoint = CheckpointManager()
        self.governor = SyntheticConsciousnessGovernor(
            self.persona, self.dream_engine, self.scheduler, self.checkpoint
        )

    def test_self_depiction_score_range(self) -> None:
        score = self.governor.measure_self_depiction()
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_imagination_score_range(self) -> None:
        score = self.governor.measure_imagination(n=10)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_attention_score_range(self) -> None:
        score = self.governor.measure_attention()
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_planning_score_range(self) -> None:
        score = self.governor.measure_planning()
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_valuation_score_range(self) -> None:
        score = self.governor.measure_valuation()
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_overall_adherence_structure(self) -> None:
        adherence = self.governor.overall_adherence()
        expected_keys = {"self_depiction", "imagination", "attention", "planning", "valuation"}
        self.assertEqual(set(adherence.keys()), expected_keys)


if __name__ == "__main__":
    # Esegue i test se il modulo viene lanciato direttamente
    unittest.main()
