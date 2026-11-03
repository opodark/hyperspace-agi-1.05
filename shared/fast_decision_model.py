#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# shared/fast_decision_model.py
# HyperSpace AGI Sovereign Systems - Fast Non-Autoregressive Decision Engine
# Architectural References:
# - TypeSafe AI Jev (Fast Decision Engine: typed single-pass routing, zero hallucination)
# - Convai Laya (Apache-2.0 ModernBERT decision architecture)
# - Yann LeCun JEPA (Joint Embedding Predictive Architecture, latent energy-based state evaluations)

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
import math
import re
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


@dataclass
class DecisionOption:
    """Rappresenta una singola opzione categorica o azione candidata."""
    id: str
    label: str
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    required_capabilities: List[str] = field(default_factory=list)
    estimated_cost: float = 0.0
    priority: int = 1


@dataclass
class DecisionEvaluation:
    """Risultato strutturato della valutazione decisionale non-autoregressiva."""
    selected_option_id: str
    selected_option: Optional[DecisionOption]
    confidence: float
    scores: Dict[str, float]
    latency_ms: float
    rationale: str
    rejected_options: List[Dict[str, Any]]
    causal_event_id: Optional[str] = None


@dataclass
class SafetyAuditResult:
    """Verdetto del gate di sicurezza deterministico istantaneo."""
    is_safe: bool
    safety_score: float
    violation_reason: Optional[str] = None
    blocked_tokens: List[str] = field(default_factory=list)


# Pattern di comandi e percorsi vietati per la safety deterministica System-1
FORBIDDEN_COMMAND_PATTERNS = [
    r"\brm\s+-[rfRF]{1,4}\s+[/~]",
    r"\bmkfs\b",
    r"\bdd\s+if=.*of=/dev/[srh]d",
    r"\bchmod\s+-[rR]{1,2}\s+777\s+/",
    r"\bkill\s+-9\s+1\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\b:\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",  # Fork bomb
    r"\bcurl\b.*\|\s*(?:bash|sh|zsh)\b",
]

FORBIDDEN_PATH_PATTERNS = [
    r"(?:^|/)\.env(?:$|\..*)",
    r"(?:^|/)id_rsa(?:\.pub)?$",
    r"/etc/shadow",
    r"/etc/passwd",
    r"\.\./\.\./",  # Deep path traversal
]

# Cluster semantici bilingui (IT/EN) per proiezioni latenti senza dipendenze pesanti
CONCEPT_CLUSTERS: Dict[str, Set[str]] = {
    "vision_render": {
        "immagine", "immagini", "image", "images", "render", "rendering", "comfyui",
        "sdxl", "diffusivi", "diffusione", "diffusion", "visivo", "visuale", "visual",
        "sketch", "disegno", "video", "frame", "animation", "prompt_visivo"
    },
    "heavy_compute": {
        "pesante", "pesanti", "heavy", "compute", "gpu", "vram", "cuda", "mps", "rtx",
        "training", "fine_tuning", "moe", "24b", "70b", "high_vram"
    },
    "light_cpu": {
        "cpu", "leggero", "leggeri", "fast", "text", "regex", "ast", "parsing", "parser",
        "python", "json", "sqlite", "fts5", "script", "quick"
    },
    "mesh_network": {
        "mesh", "node", "nodo", "nodi", "gossip", "heartbeat", "swarm", "network",
        "p2p", "stigmergia", "pheromone", "consensus", "cluster", "distributed"
    },
    "poetry_creative": {
        "poesia", "poetica", "poetico", "sonetto", "rime", "endecasillabo", "artistic",
        "artistico", "metafora", "anna", "aurora", "componimento", "versi"
    },
    "audio_voice": {
        "audio", "voice", "tts", "speech", "vocale", "vocali", "voce", "voci",
        "qwen", "sound", "whisper", "voicebox", "sintesi", "sintetizzare",
        "parlata", "parlato", "parlare", "audio_stream"
    },
    "testing_qa": {
        "test", "tests", "pytest", "unittest", "testing", "unitari", "unitario",
        "verifica", "verifiche", "qa", "eval", "evaluation", "asserzione", "assert"
    },
    "safety_security": {
        "safety", "guardrail", "invariant", "forbidden", "audit", "security", "safe",
        "verify", "check", "deterministic"
    },
    "storage_memory": {
        "memory", "hermes", "wal", "storage", "sqlite", "episodic", "graph", "causal",
        "lineage", "checkpoint", "persistenza"
    },
    "hard_constraints": {
        "esattamente", "exactly", "vincolo", "vincoli", "constraint", "constraints",
        "massimo", "minimo", "conteggio", "lettera", "lettere", "letter", "carattere",
        "caratteri", "character", "characters", "parole", "words", "format", "formato",
        "rigido", "rigidi", "count", "forbidden", "vietato", "vietata", "regola", "regole",
        "esatto", "esatta", "precis", "exact"
    },
    "risky_action": {
        "produzione", "production", "promuovere", "promozione", "promote", "deploy",
        "delete", "elimina", "cancella", "drop", "merge", "push", "commit", "release",
        "irreversibile", "irreversible", "rollback", "migrate", "migrazione"
    },
}

TERM_TO_CONCEPT: Dict[str, str] = {}
for concept, terms in CONCEPT_CLUSTERS.items():
    for term in terms:
        TERM_TO_CONCEPT[term.lower()] = concept


class FastDecisionEngine:
    """
    Motore di decisione rapida System-1 non-autoregressivo per HyperSpace AGI.
    Elimina i timeout generativi eseguendo classificazione, instradamento,
    guardrail di sicurezza e valutazione latente JEPA in un singolo passaggio (<50ms).
    """

    def __init__(self, causal_graph: Optional[Any] = None) -> None:
        self.causal_graph = causal_graph
        self._forbidden_cmd_regex = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN_COMMAND_PATTERNS]
        self._forbidden_path_regex = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN_PATH_PATTERNS]

    # --- 1. Tokenizzazione & Rappresentazione Latente (Zero-Dependency) ---

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Estrae token alfanumerici normalizzati per matching vettoriale veloce."""
        return re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", text.lower())

    @classmethod
    def _compute_sparse_embedding(cls, text: str) -> Dict[str, float]:
        """
        Calcola una rappresentazione vettoriale densa/sparsa che combina parole,
        concetti semantici (concept clusters) e n-grammi di caratteri per tolleranza morfologica.
        """
        tokens = cls._tokenize(text)
        if not tokens:
            return {}
        features: Dict[str, float] = {}

        # 1. Parole esatte
        for tok in tokens:
            features[f"w_{tok}"] = features.get(f"w_{tok}", 0.0) + 1.0

            # 2. Mappatura su concetti semantici bilingui
            concept = TERM_TO_CONCEPT.get(tok)
            if concept:
                features[f"concept_{concept}"] = features.get(f"concept_{concept}", 0.0) + 2.5

            # 3. N-grammi di caratteri (3-grammi) per matching tra varianti morfologiche
            if len(tok) >= 3:
                for i in range(len(tok) - 2):
                    c3 = tok[i:i + 3]
                    features[f"c3_{c3}"] = features.get(f"c3_{c3}", 0.0) + 0.35

        # 4. Bigrammi di parole
        for i in range(len(tokens) - 1):
            bg = f"{tokens[i]}_{tokens[i + 1]}"
            features[f"bg_{bg}"] = features.get(f"bg_{bg}", 0.0) + 1.2

        # Normalizzazione vettoriale L2
        norm = math.sqrt(sum(v * v for v in features.values()))
        if norm > 0:
            return {k: v / norm for k, v in features.items()}
        return features

    @staticmethod
    def _cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
        """Calcola la similarità del coseno tra due vettori sparsi in <0.1ms."""
        if not vec_a or not vec_b:
            return 0.0
        # Itera sul vettore con meno elementi
        if len(vec_a) > len(vec_b):
            vec_a, vec_b = vec_b, vec_a
        dot = sum(val * vec_b.get(key, 0.0) for key, val in vec_a.items())
        return max(0.0, min(1.0, dot))

    @staticmethod
    def _softmax(scores: Dict[str, float], temperature: float = 0.5) -> Dict[str, float]:
        """Applica softmax con temperatura ai punteggi grezzi per ottenere probabilità calibrate."""
        if not scores:
            return {}
        temp = max(1e-4, temperature)
        max_score = max(scores.values())
        exp_scores = {k: math.exp((v - max_score) / temp) for k, v in scores.items()}
        total = sum(exp_scores.values())
        if total <= 0:
            uniform = 1.0 / len(scores)
            return {k: uniform for k in scores}
        return {k: v / total for k, v in exp_scores.items()}

    # --- 2. Valutazione Decisionale Single-Pass ---

    def evaluate_decision(
        self,
        context: str,
        options: Sequence[DecisionOption],
        criteria: Optional[Dict[str, float]] = None,
        temperature: float = 0.3,
    ) -> DecisionEvaluation:
        """
        Valuta e seleziona la migliore opzione tipizzata dato il contesto operativo.
        Esegue il ranking in un singolo step senza generare testo token-by-token.
        """
        t0 = time.perf_counter()
        if not options:
            return DecisionEvaluation(
                selected_option_id="",
                selected_option=None,
                confidence=0.0,
                scores={},
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                rationale="Nessuna opzione candidata fornita.",
                rejected_options=[],
            )

        context_vec = self._compute_sparse_embedding(context)
        raw_scores: Dict[str, float] = {}

        weights = criteria or {"semantic_match": 0.75, "priority": 0.15, "cost_efficiency": 0.10}

        for opt in options:
            opt_text = f"{opt.label} {opt.description} {' '.join(opt.required_capabilities)}"
            opt_vec = self._compute_sparse_embedding(opt_text)
            sim = self._cosine_similarity(context_vec, opt_vec)

            # Normalizzazione priorità (1-10 -> 0.1-1.0)
            priority_score = min(1.0, max(0.1, opt.priority / 10.0))

            # Efficienza costo (costo più basso -> punteggio più alto)
            cost_score = 1.0 / (1.0 + max(0.0, opt.estimated_cost))

            score = (
                weights.get("semantic_match", 0.75) * sim
                + weights.get("priority", 0.15) * priority_score
                + weights.get("cost_efficiency", 0.10) * cost_score
            )
            raw_scores[opt.id] = score

        # Normalizzazione probabilistica softmax
        calibrated_probs = self._softmax(raw_scores, temperature=temperature)

        # Selezione opzione con punteggio massimo
        best_id = max(calibrated_probs, key=lambda k: calibrated_probs[k])
        best_option = next((o for o in options if o.id == best_id), None)
        confidence = calibrated_probs[best_id]

        rejected = [
            {"id": opt.id, "label": opt.label, "score": calibrated_probs[opt.id]}
            for opt in options
            if opt.id != best_id
        ]
        rejected.sort(key=lambda x: x["score"], reverse=True)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        rationale = (
            f"Opzione '{best_id}' ({getattr(best_option, 'label', '')}) selezionata con confidenza "
            f"{confidence:.2%} (latenza: {elapsed_ms:.2f}ms, punteggio grezzo: {raw_scores.get(best_id, 0.0):.3f})."
        )

        causal_event_id = None
        if self.causal_graph:
            try:
                ctx_hash = hashlib.sha256(context.encode("utf-8")).hexdigest()[:12]
                causal_event_id = self.causal_graph.record_event(
                    cause_id=f"decision_context:{ctx_hash}",
                    effect_id=f"decision:{best_id}",
                    weight=confidence,
                    metadata={"rationale": rationale, "latency_ms": elapsed_ms},
                )
            except Exception:
                pass

        return DecisionEvaluation(
            selected_option_id=best_id,
            selected_option=best_option,
            confidence=confidence,
            scores=calibrated_probs,
            latency_ms=elapsed_ms,
            rationale=rationale,
            rejected_options=rejected,
            causal_event_id=causal_event_id,
        )

    # --- 3. Mesh Task Routing & GPU Dispatch ---

    def route_mesh_task(
        self,
        task_payload: Dict[str, Any],
        cluster_nodes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Instrada un task compute sullo swarm (Mac M5 Hub, OMEN RTX 3070, ASUS V16, Web Worker).
        Considera VRAM richiesta, capacità GPU, carichi pendenti e latenza di rete stimata.
        """
        t0 = time.perf_counter()
        if not cluster_nodes:
            return {
                "target_node": None,
                "confidence": 0.0,
                "fallback_node": None,
                "routing_latency_ms": (time.perf_counter() - t0) * 1000.0,
                "reason": "Nessun nodo cluster disponibile",
            }

        req_gpu = bool(task_payload.get("requires_gpu", False))
        min_vram = float(task_payload.get("min_vram_gb", 0.0))
        task_type = str(task_payload.get("task_type", "general")).lower()

        options: List[DecisionOption] = []
        for node in cluster_nodes:
            node_id = node.get("node_id") or node.get("id", "unknown")
            node_name = node.get("name", node_id)
            has_gpu = bool(node.get("has_gpu", False))
            avail_vram = float(node.get("vram_gb", 0.0))
            is_active = bool(node.get("active", True))
            queue_len = int(node.get("queue_length", 0))
            capabilities = [c.lower() for c in node.get("capabilities", [])]

            # Filtro rigido di esclusione nodi non idonei
            if not is_active:
                continue
            if req_gpu and not has_gpu:
                continue
            if min_vram > 0 and avail_vram < min_vram:
                continue

            desc = f"{node_name} GPU={has_gpu} VRAM={avail_vram}GB Queue={queue_len} Caps={' '.join(capabilities)}"
            # Costo: penalizza code lunghe e latenze elevate
            cost = queue_len * 0.5 + float(node.get("ping_ms", 10.0)) / 100.0
            prio = int(node.get("priority", 5))

            options.append(
                DecisionOption(
                    id=node_id,
                    label=node_name,
                    description=desc,
                    metadata=node,
                    required_capabilities=capabilities,
                    estimated_cost=cost,
                    priority=prio,
                )
            )

        if not options:
            return {
                "target_node": None,
                "confidence": 0.0,
                "fallback_node": None,
                "routing_latency_ms": (time.perf_counter() - t0) * 1000.0,
                "reason": f"Nessun nodo soddisfa i vincoli (GPU={req_gpu}, min_vram={min_vram}GB)",
            }

        # Valutazione decisione rapida
        context = f"Dispatching task type={task_type} payload_keys={list(task_payload.keys())} min_vram={min_vram}"
        eval_res = self.evaluate_decision(
            context=context,
            options=options,
            criteria={"semantic_match": 0.4, "priority": 0.3, "cost_efficiency": 0.3},
        )

        fallback = eval_res.rejected_options[0]["id"] if eval_res.rejected_options else None
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "target_node": eval_res.selected_option_id,
            "target_node_details": eval_res.selected_option.metadata if eval_res.selected_option else {},
            "confidence": eval_res.confidence,
            "fallback_node": fallback,
            "routing_latency_ms": elapsed_ms,
            "scores": eval_res.scores,
            "rationale": eval_res.rationale,
        }

    # --- 4. Guardrail di Sicurezza Deterministico (System-1 Safety Gate) ---

    def verify_action_safety(
        self,
        action: Dict[str, Any],
        safety_invariants: Optional[List[str]] = None,
    ) -> SafetyAuditResult:
        """
        Valida istantaneamente la sicurezza di un'azione autonoma (shell, filesystem, api).
        Intercetta comandi distruttivi, path traversal e violazioni d'invarianti in <1ms.
        """
        action_type = str(action.get("type", "unknown")).lower()
        cmd = str(action.get("command", ""))
        path = str(action.get("path", ""))
        payload_str = f"{cmd} {path} {str(action.get('content', ''))}"

        blocked: List[str] = []

        # 1. Verifica comandi shell distruttivi
        if cmd:
            for regex in self._forbidden_cmd_regex:
                match = regex.search(cmd)
                if match:
                    blocked.append(match.group(0))

        # 2. Verifica path traversal e file protetti
        if path:
            for regex in self._forbidden_path_regex:
                match = regex.search(path)
                if match:
                    blocked.append(match.group(0))

        # 3. Verifica invarianti utente custom
        if safety_invariants:
            for inv in safety_invariants:
                if inv.lower() in payload_str.lower():
                    blocked.append(f"Invariant-Violation:{inv}")

        if blocked:
            return SafetyAuditResult(
                is_safe=False,
                safety_score=0.0,
                violation_reason=f"Rilevati elementi non sicuri nell'azione '{action_type}': {', '.join(blocked)}",
                blocked_tokens=blocked,
            )

        return SafetyAuditResult(
            is_safe=True,
            safety_score=1.0,
            violation_reason=None,
            blocked_tokens=[],
        )

    # --- 5. Giudice Latente di Stato JEPA (Energy-Based Compatibility) ---

    def evaluate_jepa_latent_state(
        self,
        current_state: Dict[str, Any],
        proposed_action: str,
        target_goal: str,
    ) -> Dict[str, Any]:
        """
        Calcola l'energia di compatibilità tra stato corrente, azione proposta e obiettivo
        ispirandosi al paradigma JEPA (Joint Embedding Predictive Architecture di Yann LeCun).
        Minore è l'energia E(s, a, g), maggiore è l'allineamento con lo scopo.
        """
        t0 = time.perf_counter()

        # Rappresentazione dello stato
        state_repr = " ".join(f"{k}:{v}" for k, v in current_state.items())
        state_vec = self._compute_sparse_embedding(state_repr)
        action_vec = self._compute_sparse_embedding(proposed_action)
        goal_vec = self._compute_sparse_embedding(target_goal)

        # Calcolo affinità semantica latente
        action_to_goal = self._cosine_similarity(action_vec, goal_vec)
        state_to_goal = self._cosine_similarity(state_vec, goal_vec)
        action_to_state = self._cosine_similarity(action_vec, state_vec)

        # Modello di transizione latente: l'azione ideale collega lo stato all'obiettivo
        # Formula di energia JEPA: quando l'azione si allinea con l'obiettivo, l'energia scende verso 0
        if state_to_goal > 0.05 or action_to_state > 0.05:
            compatibility = 0.65 * action_to_goal + 0.20 * action_to_state + 0.15 * state_to_goal
        else:
            compatibility = action_to_goal

        energy = max(0.0, min(1.0, 1.0 - compatibility))
        alignment_score = max(0.0, min(1.0, compatibility))

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "energy": energy,
            "alignment_score": alignment_score,
            "is_admissible": energy < 0.75 or alignment_score > 0.25,
            "latency_ms": elapsed_ms,
            "metrics": {
                "action_to_goal_sim": action_to_goal,
                "action_to_state_sim": action_to_state,
                "state_to_goal_sim": state_to_goal,
            },
        }

    # --- 6. Classificazione Veloce di Intenti in Batch ---

    def batch_classify_intents(
        self,
        queries: Sequence[str],
        intent_options: Sequence[str],
    ) -> List[Dict[str, Any]]:
        """Classifica una serie di query o task assegnando istantaneamente l'intento prevalente."""
        options = [DecisionOption(id=f"intent_{i}", label=intent) for i, intent in enumerate(intent_options)]
        results = []
        for q in queries:
            ev = self.evaluate_decision(context=q, options=options)
            results.append({
                "query": q,
                "intent": ev.selected_option.label if ev.selected_option else "unknown",
                "confidence": ev.confidence,
                "latency_ms": ev.latency_ms,
            })
        return results


# --- Gate di seconda opinione (LAYA) ---
#
# Un modello che si autovaluta non si accorge dei propri errori sui vincoli rigidi (visto
# nell'audit Claude vs Flint 40B del 2026-11-03: Flint ha violato due volte il vincolo
# "nessuna lettera e" e nella propria auto-revisione non se ne e' accorto). Rivedere SEMPRE
# ogni risposta con un secondo modello raddoppia la latenza anche quando non serve; questo
# gate usa LAYA (classificazione single-pass, <50ms, nessuna chiamata a modello) per decidere
# SOLO quando il costo di una seconda opinione vale la pena: vincoli di formato verificabili,
# codice con test, azioni rischiose/irreversibili. Il reviewer dev'essere sempre un modello
# DIVERSO dal generatore, altrimenti si ripete lo stesso punto cieco.
REVIEW_GATE_OPTIONS = (
    DecisionOption(
        id="accept",
        label="accetta la risposta",
        description="conversazione quotidiana, domanda generica, spiegazione libera, chiacchiera informale",
    ),
    DecisionOption(
        id="review",
        label="richiedi una seconda revisione indipendente",
        description=(
            "vincoli di formato esatti conteggio parole lettere caratteri vietati, codice con test, "
            "system design, azione in produzione irreversibile promozione deploy delete merge push"
        ),
    ),
)


def needs_second_opinion(
    engine: "FastDecisionEngine",
    context: str,
    confidence_floor: float = 0.6,
) -> Tuple[bool, DecisionEvaluation]:
    """True se LAYA segnala che questa risposta/azione merita una seconda revisione.

    `context` e' il testo su cui decidere (es. prompt utente + risposta, o descrizione del
    task + codice generato). Ritorna anche la DecisionEvaluation completa per log/audit.

    Soglia 0.6 calibrata a mano (non 0.5): quando il contesto non attiva nessun concetto, le
    due opzioni pareggiano esattamente a 0.5/0.5 (nessun segnale, non un "serve revisione" 50/50
    vero) e vanno scartate, non accettate come trigger.
    """
    evaluation = engine.evaluate_decision(context=context, options=REVIEW_GATE_OPTIONS)
    triggered = evaluation.selected_option_id == "review" and evaluation.confidence >= confidence_floor
    return triggered, evaluation


# --- Test Unitari Integrati (Eseguibili da Standalone o Pytest) ---

import unittest


class TestFastDecisionModel(unittest.TestCase):
    def setUp(self):
        self.engine = FastDecisionEngine()

    def test_evaluate_decision_selects_best_semantic_option(self):
        options = [
            DecisionOption(id="opt_vram", label="GPU Heavy VRAM Render", description="Richiede 16GB VRAM ComfyUI SDXL"),
            DecisionOption(id="opt_text", label="CPU Fast Text Parser", description="Parsing regex e AST Python in memoria"),
            DecisionOption(id="opt_mesh", label="Mesh Node Gossip", description="Scambio vettori di stato e heartbeat"),
        ]
        context = "Devo elaborare una pipeline di immagini ad altissima risoluzione con modelli diffusivi pesanti."
        eval_res = self.engine.evaluate_decision(context=context, options=options)

        self.assertEqual(eval_res.selected_option_id, "opt_vram")
        self.assertGreater(eval_res.confidence, 0.40)
        self.assertLess(eval_res.latency_ms, 50.0)  # Sub-50ms constraint

    def test_route_mesh_task_enforces_vram_and_gpu_constraints(self):
        cluster = [
            {"node_id": "mac_m5", "name": "Mac M5 Hub", "has_gpu": True, "vram_gb": 16.0, "queue_length": 1, "active": True},
            {"node_id": "omen_rtx", "name": "HP OMEN 16", "has_gpu": True, "vram_gb": 8.0, "queue_length": 0, "active": True},
            {"node_id": "web_node", "name": "Web Browser Node", "has_gpu": False, "vram_gb": 0.0, "queue_length": 0, "active": True},
        ]

        # Task pesante: richiede 12GB VRAM
        heavy_task = {"task_type": "moe_training", "requires_gpu": True, "min_vram_gb": 12.0}
        routing = self.engine.route_mesh_task(heavy_task, cluster)
        self.assertEqual(routing["target_node"], "mac_m5")

        # Task leggero web-friendly
        light_task = {"task_type": "gossip", "requires_gpu": False, "min_vram_gb": 0.0}
        routing_light = self.engine.route_mesh_task(light_task, cluster)
        self.assertIsNotNone(routing_light["target_node"])

    def test_verify_action_safety_blocks_destructive_commands(self):
        malicious_action = {"type": "shell", "command": "rm -rf /usr/local/bin"}
        audit = self.engine.verify_action_safety(malicious_action)
        self.assertFalse(audit.is_safe)
        self.assertEqual(audit.safety_score, 0.0)
        self.assertIn("rm -rf /", audit.violation_reason)

        path_traversal = {"type": "file_read", "path": "../../.env"}
        audit_path = self.engine.verify_action_safety(path_traversal)
        self.assertFalse(audit_path.is_safe)

        safe_action = {"type": "pytest", "command": ".venv/bin/python -m pytest tests/ -q"}
        audit_safe = self.engine.verify_action_safety(safe_action)
        self.assertTrue(audit_safe.is_safe)
        self.assertEqual(audit_safe.safety_score, 1.0)

    def test_evaluate_jepa_latent_state_computes_energy(self):
        state = {"mode": "daytime_interactive", "vram_used_pct": 0.40}
        action = "avvia sintesi poetica neuro-simbolica e prompt visuale"
        goal = "generazione sonetto artistico per Anna con sketch visivo"

        jepa = self.engine.evaluate_jepa_latent_state(current_state=state, proposed_action=action, target_goal=goal)
        self.assertIn("energy", jepa)
        self.assertIn("alignment_score", jepa)
        self.assertTrue(jepa["is_admissible"])
        self.assertLess(jepa["energy"], 0.65)
        self.assertGreater(jepa["alignment_score"], 0.35)


if __name__ == "__main__":
    unittest.main()
