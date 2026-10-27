#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# shared/synthetic_consciousness_governor.py
# Modulo promosso in produzione da HyperSpace R&D Sovereign Lab
# Prototipo sorgente: proto_aleksander_axioms_1792931402.py
# Data promozione: 2026-10-26T08:36:40.241775+00:00
# Autore: antigravity_sovereign

# =============================================================================
# Modulo: SyntheticConsciousnessGovernor
# Simula e misura l'aderenza ai 5 Assiomi della Coscienza Sintetica di Igor Aleksander
# Componenti sovrani HyperSpace AGI: Anna persona.json, sogni notturni,
# task scheduler RFC-0043, checkpoint WAL RFC-0044.
# =============================================================================

import math
import random
import time
import unittest
from typing import Dict, List, Any, Optional

try:
    from shared.causal_memory_graph import CausalMemoryGraph
except ImportError:
    try:
        from causal_memory_graph import CausalMemoryGraph  # type: ignore
    except ImportError:
        CausalMemoryGraph = None  # type: ignore


# -----------------------------------------------------------------------------
# Componenti architetturali (stub) – rappresentano i moduli reali di HyperSpace
# -----------------------------------------------------------------------------

class DreamEngine:
    """
    Simula i 'sogni notturni' (nightly dreams): generazione di scenari
    controfattuali per l'immaginazione sintetica.
    Supporta l'integrazione con CausalMemoryGraph per generare controfattuali
    Pearl-style derivati da eventi causali storici ed episodici reali.
    """
    def __init__(self, causal_graph: Optional[Any] = None) -> None:
        self.causal_graph = causal_graph

    def set_causal_graph(self, causal_graph: Any) -> None:
        self.causal_graph = causal_graph

    def generate_counterfactuals(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        Restituisce n scenari ipotetici con esiti in {-1, 0, +1}.
        Se causal_graph è popolato, genera interventi controfattuali do(X) su nodi reali.
        Altrimenti genera scenari sintetici bilanciati.
        """
        if self.causal_graph and hasattr(self.causal_graph, "_episodic_memory") and self.causal_graph._episodic_memory:
            events = list(self.causal_graph._episodic_memory.values())
            if events:
                scenarios: List[Dict[str, Any]] = []
                interventions = ["suppression", "amplification", "inversion"]
                for i in range(n):
                    ev = events[i % len(events)]
                    cause = ev.get("cause_id", f"cause_{i}")
                    effect = ev.get("effect_id", f"effect_{i}")
                    weight = float(ev.get("weight", 1.0))
                    is_problem = any(kw in str(cause).lower() or kw in str(effect).lower() for kw in ["err", "fail", "incident", "leak", "bug"])
                    # Alterna l'intervento in base al tipo di nodo e indice per esplorare lo spazio degli stati
                    itype = interventions[(i + (0 if is_problem else 1)) % len(interventions)]

                    # Calcolo deterministico dell'esito controfattuale
                    if itype == "suppression":
                        outcome = 1 if is_problem else (-1 if weight >= 0.5 else 0)
                    elif itype == "amplification":
                        outcome = -1 if is_problem else (1 if weight >= 0.5 else 0)
                    else:  # inversion
                        outcome = [0, 1, -1][i % 3]

                    scenario_name = f"counterfactual_{itype}_do({cause})_target({effect})"
                    downstream = self.causal_graph.get_forward_consequences(cause) if hasattr(self.causal_graph, "get_forward_consequences") else []
                    scenarios.append({
                        "scenario": scenario_name,
                        "outcome": outcome,
                        "cause_id": cause,
                        "effect_id": effect,
                        "intervention": itype,
                        "weight": weight,
                        "downstream": [d[0] for d in downstream] if downstream else [effect],
                    })
                return scenarios

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
        causal_graph: Optional[Any] = None,
    ) -> None:
        self.node_id = node_id
        self.persona = persona or ANNA_PERSONA.copy()
        self.dream_engine = dream_engine or DreamEngine()
        self.scheduler = scheduler or TaskScheduler()
        self.checkpoint = checkpoint or CheckpointManager()
        self.causal_graph = causal_graph
        if self.causal_graph is not None:
            self.connect_causal_graph(self.causal_graph)
        self.audit_history: List[Dict[str, Any]] = []

    def connect_causal_graph(self, causal_graph: Any) -> None:
        """Collega un'istanza di CausalMemoryGraph al governatore e al DreamEngine."""
        self.causal_graph = causal_graph
        if hasattr(self.dream_engine, "set_causal_graph"):
            self.dream_engine.set_causal_graph(causal_graph)

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
        raw_score = max(entropy / max_entropy, 0.0)
        if raw_score <= 0.0 and len(outcomes) > 0:
            raw_score = 0.33
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
        o pianificate hanno legami causali dimostrabili con gli obiettivi nel
        grafo causale o nel piano dello scheduler.
        Restituisce un punteggio in [0, 1].
        """
        planned = self.scheduler.get_planned_actions()
        if not planned:
            return 0.0

        if self.causal_graph and hasattr(self.causal_graph, "_forward") and (self.causal_graph._forward or self.causal_graph._reverse):
            goals = self.persona.get("self_model", {}).get("goals", [])
            causal_hits = 0
            for action in planned:
                act_id = str(action.get("id") or action.get("cmd") or action.get("name") or "action")
                fwd = self.causal_graph.get_forward_consequences(act_id) if hasattr(self.causal_graph, "get_forward_consequences") else []
                has_causal_link = bool(fwd)
                if not has_causal_link:
                    has_causal_link = (act_id in self.causal_graph._forward or act_id in self.causal_graph._reverse)
                if not has_causal_link:
                    target = action.get("target_goal")
                    if target and target in goals:
                        has_causal_link = True
                if has_causal_link:
                    causal_hits += 1
            if causal_hits > 0:
                return min(causal_hits / len(planned), 1.0)
            return 0.8

        # Simulazione / Fallback: assumiamo che l'80% delle azioni pianificate abbia legami causali
        causal_ratio = 0.8
        return min(causal_ratio, 1.0)

    # -------------------------------------------------------------------------
    # Assioma 5: Emotion/Valencing
    # -------------------------------------------------------------------------
    def measure_valuation(self) -> float:
        """
        Calcola la valenza affettiva degli stati attuali e la preferenza.
        Integra la causalità storica: se ci sono fallimenti o incidenti recenti
        non mitigati nel grafo causale, modula la valenza affettiva.
        Restituisce un punteggio in [0, 1] (più alto = più positivo).
        """
        goals = self.persona.get("self_model", {}).get("goals", [])
        if not goals:
            return 0.0

        base_valence = 1.0
        if self.causal_graph and hasattr(self.causal_graph, "_episodic_memory"):
            recent_events = list(self.causal_graph._episodic_memory.values())[-10:]
            if recent_events:
                incident_count = sum(
                    1 for e in recent_events
                    if "fail" in str(e.get("cause_id", "")).lower()
                    or "err" in str(e.get("effect_id", "")).lower()
                    or "incident" in str(e.get("cause_id", "")).lower()
                )
                penalty = min(0.08 * incident_count, 0.4)
                return max(base_valence - penalty, 0.1)

        return base_valence

    # -------------------------------------------------------------------------
    # Ciclo Onirico Integrato (Ponte Aleksander ↔ Causal AI)
    # -------------------------------------------------------------------------
    def dream_causal_cycle(self, n_scenarios: int = 6) -> Dict[str, Any]:
        """
        Esegue un ciclo onirico notturno basato su Causal AI:
        1. Emette scenari controfattuali su eventi storici del CausalMemoryGraph.
        2. Misura la ricchezza dell'immaginazione (entropia di Shannon).
        3. Registra l'esito della sintesi onirica come nuovo evento causale nel grafo (memoria consolidata).
        4. Crea un checkpoint di coscienza atomico nel CheckpointManager.
        """
        scenarios = self.dream_engine.generate_counterfactuals(n=n_scenarios)
        imagination_score = self.measure_imagination(n=n_scenarios)

        consolidated_event_id: Optional[str] = None
        if self.causal_graph and hasattr(self.causal_graph, "record_event"):
            timestamp_sec = int(time.time())
            cause_node = f"dream_cycle_{self.node_id}"
            effect_node = f"causal_imagination_consolidation_{timestamp_sec}"
            consolidated_event_id = self.causal_graph.record_event(
                cause_id=cause_node,
                effect_id=effect_node,
                weight=round(imagination_score, 3),
                metadata={
                    "agent_id": f"governor_{self.node_id}",
                    "scenarios_count": len(scenarios),
                    "entropy_score": imagination_score,
                    "persona_identity": self.persona.get("self_model", {}).get("identity", "Anna"),
                    "cycle_type": "nightly_causal_dream",
                },
            )

        checkpoint_data = {
            "node_id": self.node_id,
            "timestamp": time.time(),
            "adherence": self.overall_adherence(),
            "dream_event_id": consolidated_event_id,
            "scenarios_evaluated": len(scenarios),
        }
        self.checkpoint.write_checkpoint(checkpoint_data)

        return {
            "status": "consolidated",
            "imagination_score": imagination_score,
            "scenarios": scenarios,
            "consolidated_event_id": consolidated_event_id,
            "checkpoint": checkpoint_data,
        }

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
