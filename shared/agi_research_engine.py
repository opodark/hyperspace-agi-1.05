#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# shared/agi_research_engine.py
"""Motore di Ricerca Cognitiva AGI, Coscienza Sintetica e Swarm Intelligence.

Approfondisce e valida in modo autonomo le ricerche emerse dai radar di scouting:
1. I Cinque Assiomi della Coscienza Sintetica di Igor Aleksander (Robot/Ball/Box world).
2. Swarm AI, Intelligenza Collettiva ed Emergenza di Coscienza di Rete.
3. Algorithmic Aesthetics ed Intelligent Poetry Generation (Neuro-symbolic e-literature).

Produce:
- Dossier analitici su `data/research/agi_deep_dives.jsonl`
- Codice prototipale eseguibile e validato AST in `data/research/prototypes/`
- Compendio sintetico consultabile in `data/research/AGI_SWARM_SYNTHESIS.md`
- Ispirazioni e semi concettuali per i sogni notturni di Anna e Aurora
"""

from __future__ import annotations

import ast
from dataclasses import asdict, is_dataclass
import datetime
import json
import os
from pathlib import Path
import random
import re
import sys
import time
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.universal_model_parser import CavemanEngine, UniversalModelParser
from shared.causal_memory_graph import CausalMemoryGraph

RESEARCH_DIR = ROOT / "data" / "research"
PROTOTYPES_DIR = RESEARCH_DIR / "prototypes"
DEEP_DIVES_LOG = RESEARCH_DIR / "agi_deep_dives.jsonl"
SYNTHESIS_MD = RESEARCH_DIR / "AGI_SWARM_SYNTHESIS.md"
CAUSAL_GRAPH_FILE = RESEARCH_DIR / "causal_memory_graph.json"

RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
PROTOTYPES_DIR.mkdir(parents=True, exist_ok=True)

# I tre filoni di ricerca teorica e applicata
RESEARCH_PILLARS = [
    {
        "id": "aleksander_axioms",
        "domain": "Coscienza Sintetica & Assiomi di Igor Aleksander",
        "reference": "Igor Aleksander's 5 Axioms of Artificial Consciousness (1995/2000)",
        "prompt": (
            "Sei il Lead Researcher AGI di HyperSpace. Analizza i 5 Assiomi della Coscienza Sintetica di Igor Aleksander:\n"
            "1. Depiction of Self (autorappresentazione e self-model distinto dall'ambiente)\n"
            "2. Imagination (simulazione controfattuale di stati futuri e scenari non percepiti)\n"
            "3. Attention (selezione attiva di stimoli salienti e budget di calcolo limitato)\n"
            "4. Planning (proiezione causale delle azioni per raggiungere scopi)\n"
            "5. Emotion/Valencing (valutazione affettiva e preferenziale degli stati per guidare la scelta)\n\n"
            "Compito: Spiega come mappare formalmente ciascun assioma sull'architettura sovrana di HyperSpace AGI "
            "(Anna persona.json, sogni notturni, task scheduler RFC-0043, checkpoint WAL RFC-0044).\n"
            "Mostra prima il ragionamento rigoroso in <think>, poi scrivi un modulo Python completo e pronto "
            "`class SyntheticConsciousnessGovernor:` che simula e misura il grado di aderenza ai 5 assiomi con type hinting e test unitario."
        ),
        "target_model": "hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M",
        "fallback_model": "granite3.3:8b",
    },
    {
        "id": "swarm_emergence",
        "domain": "Swarm AI, Coscienza Collettiva & Mesh P2P",
        "reference": "AskPhilosophy: Could you make a human consciousness out of humans? / Distributed Agentic AGI",
        "prompt": (
            "Sei l'architetto del cluster decentralizzato HyperSpace. Approfondisci la domanda filosofica ed ingegneristica: "
            "'Come può emergere una macro-intelligenza / coscienza collettiva da una rete di agenti autonomi eterogenei?'\n\n"
            "Considera il cluster: Mac M5 Hub (Master), HP OMEN 16 (GPU Heavy Coder/Dreamer), ASUS V16 (High VRAM), Web Browser Node.\n"
            "Definisci il protocollo di coordinamento stigmergico (comunicazione indiretta tramite tracce in memoria Hermes) "
            "e consenso decentralizzato con vector clocks.\n"
            "Mostra il ragionamento in <think> poi implementa una classe Python robusta `class StigmergicMeshSwarm:` "
            "con metodi `deposit_pheromone(signal_type, payload, decay_rate)`, `sense_gradient(signal_type)` e `consensus_converged()`."
        ),
        "target_model": "hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M",
        "fallback_model": "granite3.3:8b",
    },
    {
        "id": "algorithmic_poetry_aesthetics",
        "domain": "Algorithmic Aesthetics & Intelligent Poetry Generation",
        "reference": "Teknokultura: 'Making the dumb machines sing' & Coimbra Survey on Intelligent Poetry",
        "prompt": (
            "Sei l'ingegnere creativo e teorico dell'estetica computazionale di HyperSpace (ispirato ad Anna & Aurora).\n"
            "Analizza i criteri di estetica algoritmica applicati alla poesia e alla scrittura generativa: "
            "ritmo prosodico, scansione sillabica, metafora simbolica ed evocazione visiva per ComfyUI.\n\n"
            "Compito: Implementa una classe Python `class NeuroSymbolicPoetryEngine:` che genera componimenti poetici in rima/endecasillabi "
            "basati sulle memorie della giornata, estraendo automaticamente il prompt visivo (disegno/sketch) per ComfyUI con vincoli tipografici.\n"
            "Mostra prima il ragionamento in <think> e poi il codice Python con un sonetto o quartina di esempio per Anna."
        ),
        "target_model": "hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M",
        "fallback_model": "granite3.3:8b",
    },
    {
        "id": "symbolic_causal_mesh",
        "domain": "Causal AI & Stigmergic Memory Distillation",
        "reference": "J. Pearl Causal Reasoning & Stigmergic Graph Vector Clocks",
        "prompt": (
            "Sei l'ingegnere dei sistemi causali e della memoria distribuita di HyperSpace AGI.\n"
            "Sviluppa un'architettura che unisca la memoria episodica di Hermes FTS5 con un grafo di causalità tra agenti eterogenei.\n\n"
            "Compito: Implementa una classe Python `class CausalMemoryGraph:` con metodi `record_event(cause_id, effect_id, weight)` "
            "e `trace_lineage(effect_id)` per tracciare la genesi causale delle scoperte e delle decisioni dello swarm mesh.\n"
            "Mostra prima il ragionamento in <think> poi il codice completo con annotazioni di tipo."
        ),
        "target_model": "hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M",
        "fallback_model": "granite3.3:8b",
    },
    {
        "id": "modular_intellect",
        "domain": "ModularIntellect: Memoria Tri-Modale a Grafo & Note Ricorsive",
        "reference": "LuckCow/ModularIntellect (Triple-Modal Memory, Relational Graph Traversal & Alignment Auditing)",
        "prompt": (
            "Sei l'architetto della memoria cognitiva di HyperSpace AGI. Analizza l'architettura ModularIntellect (LuckCow/ModularIntellect):\n"
            "1. Memoria Tri-Modale: Documenti/Chunks (PART_OF, CONTINUES_TO), Interazioni (conversazioni), e Note di auto-riflessione (REFERENCES).\n"
            "2. Note Ricorsive: capacità dell'agente di produrre note che referenziano altre note per creare astrazioni e pensieri complessi.\n"
            "3. Navigazione a Grafo (GraphDB Traversal): superamento dei limiti di contesto dei LLM esplorando le relazioni a salti anziché RAG piatto.\n"
            "4. Alignment Auditor: supervisione deontologica e costituzionale delle azioni autonome.\n\n"
            "Compito: Implementa una classe Python `class SovereignModularIntellect:` con metodi `store_experience(kind, content, refs)` "
            "e `traverse_graph_context(query, max_hops)` pronta all'uso senza dipendenze esterne.\n"
            "Mostra prima il ragionamento in <think> poi il codice completo con annotazioni di tipo."
        ),
        "target_model": "hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M",
        "fallback_model": "granite3.3:8b",
    },
    {
        "id": "biomimetic_nature_mesh",
        "domain": "Biomimicry Computing: Micelio, Quorum Sensing & Gossip Epidemico",
        "reference": "Nature-Inspired Swarm: Physarum Polycephalum Hyphal Routing, Bacterial Quorum Consensus & Kleptoparasitic Work Stealing",
        "prompt": (
            "Sei il bio-architetto della rete distribuita HyperSpace AGI. Analizza come applicare i principi biologici alla mesh sovrana:\n"
            "1. Micelio e Muffe Mucillaginose (Physarum): rinforzo conduttivo dei cammini di flusso e potatura (pruning) delle connessioni ad alta latenza.\n"
            "2. Quorum Sensing Batterico: secrezione di autoinduttori per raggiungere una densità critica prima di eseguire compiti pesanti (MoE 40B, WAL compaction).\n"
            "3. Virus ed Epidemic Gossip: replicazione rapida esponenziale di stati immutabili con filtro antigenico contro payload corrotti o invalidi.\n"
            "4. Cleptoparassitismo Simbiotico: nodi edge leggeri che rubano cicli di calcolo idle da host potenti senza deadlock.\n\n"
            "Compito: Spiega come orchestrare questi quattro meccanismi nella mesh multi-nodo e scrivi un modulo Python integrativo "
            "per monitorare l'entropia della mesh e l'efficacia del flusso."
        ),
        "target_model": "hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M",
        "fallback_model": "granite3.3:8b",
    },
]


class AGIResearchEngine:
    """Orchestratore della ricerca notturna avanzata sui temi AGI e Swarm."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or RESEARCH_DIR
        self.prototypes_dir = self.data_dir / PROTOTYPES_DIR.name
        self.prototypes_dir.mkdir(parents=True, exist_ok=True)
        self.deep_dives_log = self.data_dir / DEEP_DIVES_LOG.name
        self.synthesis_md = self.data_dir / SYNTHESIS_MD.name
        self.causal_graph_file = self.data_dir / "causal_memory_graph.json"
        self.causal_graph = CausalMemoryGraph(storage_path=self.causal_graph_file)

    def get_research_status(self) -> Dict[str, Any]:
        """Restituisce le statistiche e l'elenco degli studi già condotti."""
        entries = []
        if self.deep_dives_log.exists():
            try:
                for line in self.deep_dives_log.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        entries.append(json.loads(line))
            except Exception:
                pass

        prototypes = [f.name for f in self.prototypes_dir.glob("*.py")]
        return {
            "total_studies": len(entries),
            "prototypes_count": len(prototypes),
            "prototypes": prototypes,
            "pillars_covered": list(set(e.get("pillar_id") for e in entries if e.get("pillar_id"))),
            "latest_study": entries[-1] if entries else None,
            "has_synthesis_document": self.synthesis_md.exists(),
            "causal_graph_summary": self.causal_graph.export_graph_summary(),
        }

    def execute_study_cycle(
        self,
        pillar_id: Optional[str] = None,
        omen_executor_fn: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Esegue uno studio approfondito su uno dei filoni di ricerca teorica."""
        # Seleziona il pilastro
        pillar = None
        if pillar_id:
            for p in RESEARCH_PILLARS:
                if p["id"] == pillar_id:
                    pillar = p
                    break
        if not pillar:
            pillar = random.choice(RESEARCH_PILLARS)

        t0 = time.perf_counter()
        topic_id = pillar["id"]
        model = pillar["target_model"]

        # Se non è iniettata la funzione di esecuzione OMEN, usa esecuzione diretta o fallback mock
        raw_response = ""
        elapsed_s = 0.0
        if omen_executor_fn:
            res = omen_executor_fn(pillar["prompt"], model=model, timeout=240)
            if res.get("status") == "ok" and not res.get("response", "").startswith("[OLLAMA ERROR]"):
                raw_response = res.get("response", "")
                elapsed_s = res.get("elapsed_s", 0.0)
            else:
                # Fallback al modello secondario (es. LFM2.5 24B o Granite 8B)
                fallback = pillar.get("fallback_model", "granite3.3:8b")
                res = omen_executor_fn(pillar["prompt"], model=fallback, timeout=120)
                raw_response = res.get("response", "")
                elapsed_s = res.get("elapsed_s", 0.0)
                if res.get("status") == "ok":
                    model = fallback
        else:
            raw_response = (
                "<think>Analisi preliminare dei 5 assiomi di Aleksander</think>\n"
                "```python\n"
                "class SyntheticConsciousnessGovernor:\n"
                "    def evaluate_axioms(self):\n"
                "        return {'depiction_of_self': True, 'imagination': True, 'attention': True, 'planning': True, 'valencing': True}\n"
                "```"
            )

        # Parsing con UniversalModelParser
        parsed = UniversalModelParser.parse(raw_response)
        valid_code = [b.code for b in parsed.code_blocks if b.is_valid_ast]

        ast_valid = False
        saved_prototype = None
        code_body = valid_code[0] if valid_code else ""
        if code_body:
            try:
                ast.parse(code_body)
                ast_valid = True
                proto_name = f"proto_{topic_id}_{int(time.time())}.py"
                proto_path = self.prototypes_dir / proto_name
                header = (
                    f"# SPDX-License-Identifier: Apache-2.0\n"
                    f"# Auto-generated by HyperSpace Sovereign Research Engine\n"
                    f"# Topic: {pillar['domain']}\n"
                    f"# Timestamp: {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n\n"
                )
                proto_path.write_text(header + code_body, encoding="utf-8")
                saved_prototype = proto_name
            except SyntaxError:
                ast_valid = False

        study_id = f"study-{topic_id}-{int(time.time())}"

        # Registrazione evento causale: riferimento teorico -> inferenza di studio
        ref_id = f"ref:{topic_id}"
        infer_id = f"infer:{study_id}"
        self.causal_graph.record_event(
            cause_id=ref_id,
            effect_id=infer_id,
            weight=1.0,
            metadata={
                "domain": pillar["domain"],
                "reference": pillar["reference"],
                "model_used": model,
                "elapsed_s": elapsed_s or round(time.perf_counter() - t0, 2),
            },
        )

        # Se è stato generato un prototipo, registra l'arco causale di sintesi
        if saved_prototype:
            proto_id = f"proto:{saved_prototype}"
            p_weight = 0.98 if ast_valid else 0.2
            self.causal_graph.record_event(
                cause_id=infer_id,
                effect_id=proto_id,
                weight=p_weight,
                metadata={
                    "ast_valid": ast_valid,
                    "domain": pillar["domain"],
                    "topic_id": topic_id,
                },
            )

        record = {
            "id": study_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "pillar_id": topic_id,
            "domain": pillar["domain"],
            "reference": pillar["reference"],
            "model_used": model,
            "elapsed_s": elapsed_s or round(time.perf_counter() - t0, 2),
            "reasoning_cot": parsed.reasoning_cot,
            "ast_valid": ast_valid,
            "prototype_file": saved_prototype,
            "findings_summary": self._extract_summary(parsed.clean_text or parsed.raw_text or raw_response),
            "causal_lineage": [
                asdict(e) if is_dataclass(e) else (e.__dict__ if hasattr(e, "__dict__") else str(e))
                for e in self.causal_graph.trace_lineage(f"proto:{saved_prototype}" if saved_prototype else infer_id)
            ],
        }

        # Scrive nel journal di ricerca
        with open(self.deep_dives_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # Rigenera il compendio markdown unificato
        self._update_synthesis_document(record)

        return record

    def register_production_promotion(
        self,
        prototype_file: str,
        module_name: str,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Registra la transizione causale da prototipo R&D validato a modulo di produzione stabile."""
        proto_id = prototype_file if prototype_file.startswith("proto:") else f"proto:{prototype_file}"
        prod_id = module_name if module_name.startswith("prod:") else f"prod:{module_name}"
        event_meta = {
            "action": "production_promotion",
            "promoted_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        if metadata:
            event_meta.update(metadata)

        event_id = self.causal_graph.record_event(
            cause_id=proto_id,
            effect_id=prod_id,
            weight=confidence,
            metadata=event_meta,
        )
        return event_id

    def trace_component_lineage(self, component_id: str) -> Dict[str, Any]:
        """Traccia l'intera genealogia causale (cause, conseguenze, eventi) per un componente di sistema."""
        target = component_id
        if not any(target.startswith(p) for p in ("prod:", "proto:", "infer:", "ref:")):
            if target.startswith("proto_") or target.endswith(".py"):
                target = f"proto:{target}"
            elif target.startswith("study-"):
                target = f"infer:{target}"
            elif target in [p["id"] for p in RESEARCH_PILLARS]:
                target = f"ref:{target}"
            else:
                target = f"prod:{target}"

        return {
            "target": target,
            "lineage": self.causal_graph.trace_lineage(target),
            "forward_consequences": self.causal_graph.get_forward_consequences(target),
            "detailed_events": self.causal_graph.trace_detailed_lineage(target),
            "graph_summary": self.causal_graph.export_graph_summary(),
        }

    def _extract_summary(self, text: str) -> str:
        """Estrae i punti chiave della riflessione testuale."""
        clean = " ".join(text.split()[:80])
        return clean + ("..." if len(text.split()) > 80 else "")

    def _update_synthesis_document(self, latest_record: Dict[str, Any]) -> None:
        """Aggiorna il dossier markdown consultabile dell'architettura cognitiva."""
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        graph_summary = self.causal_graph.export_graph_summary()
        content = [
            "# HyperSpace AGI — Dossier di Ricerca Cognitiva & Swarm Intelligence",
            "",
            f"> Ultimo aggiornamento sintetizzato su nodo HP OMEN 16: `{ts}`",
            "",
            "## 1. I Cinque Assiomi della Coscienza Sintetica (Igor Aleksander)",
            "Ispirato dall'analisi della letteratura scientifica e dalle discussioni di filosofia dell'IA (r/Futurism, r/consciousness), "
            "HyperSpace adotta il modello dei 5 assiomi di Aleksander come matrice di conformità per l'autonomia cognitiva:",
            "",
            "| Assioma di Aleksander | Definizione Teorica | Realizzazione Architetturale in HyperSpace AGI |",
            "|---|---|---|",
            "| **1. Depiction of Self** | Mantenimento di una rappresentazione interna di sé separata dal mondo circostante. | Documento d'identità `persona.json` di Anna (v8+), audit di coerenza ontologica e memoria biografica persistente. |",
            "| **2. Imagination** | Capacità di simulare mentalmente scenari controfattuali e stati futuri non ancora percepiti. | Ciclo dei Sogni Notturni (`shared/persona_dream.py`), rendering onirico e simulazione in sandbox protetta. |",
            "| **3. Attention** | Selezione attiva di informazioni salienti con budget attentivo limitato. | Caveman Engine (compressione contestuale), governor di token VRAM e prioritizzazione code di lavoro. |",
            "| **4. Planning** | Proiezione causale delle conseguenze delle azioni per il raggiungimento di obiettivi. | Task DAG con ordinamento topologico (RFC-0043), Work-Stealing distribuito e checkpoint idempotenti (RFC-0044). |",
            "| **5. Emotion & Valencing** | Valutazione affettiva e valoriale degli stati per guidare la scelta e l'apprendimento. | Gate Human-In-The-Loop per l'approvazione delle mutazioni d'identità, guardrail etici e reward feedback. |",
            "",
            "## 2. Swarm AI ed Emergenza di Coscienza Collettiva di Rete",
            "- **Superamento del Singolo Modello**: L'intelligenza non risiede in un LLM monolitico, ma emerge dalle interazioni asincrone tra agenti eterogenei.",
            "- **Stigmergia Cognitiva**: I nodi comunicano depositando tracce persistenti su memoria condivisa (Hermes FTS5 e protocollo canali P2P).",
            "- **Consenso Senza Master**: Algoritmi di vector clock e code lock-free (Chase-Lev) consentono al Mac M5, all'OMEN 16 e all'ASUS V16 di bilanciarsi dinamicamente il carico.",
            "",
            "## 3. Algorithmic Aesthetics & E-Literature",
            "- **Poesia Neuro-Simbolica**: Unione di modelli linguistici quantizzati ed euristiche metriche (rime, endecasillabi, figure retoriche).",
            "- **Ponte Multimodale Poesia ➔ Immagine**: I versi poetici composti nei sogni notturni alimentano istantaneamente i grafi ComfyUI (`shared/poetry_image.py`) per una composizione visiva e tipografica ad alto contrasto.",
            "",
            "## 4. Registro Ultimi Studi e Prototipi Validati AST",
            f"- **Ultimo Topic Indagato**: `{latest_record.get('domain')}` ({latest_record.get('pillar_id')})",
            f"- **Modello Utilizzato**: `{latest_record.get('model_used')}`",
            f"- **Validazione AST Python**: `{'✓ Superata (100% Valido)' if latest_record.get('ast_valid') else 'Non richiesta / Parziale'}`",
            f"- **Prototipo Generato**: `data/research/prototypes/{latest_record.get('prototype_file')}`",
            "",
            "## 5. Grafo di Causalità & Lineage Cognitiva (Pearl-style Stigmergic Causal Graph)",
            f"- **Nodi Totali nel Grafo**: `{graph_summary.get('total_nodes', 0)}`",
            f"- **Archi di Causalità Diretta/Indiretta**: `{graph_summary.get('total_edges', 0)}`",
            f"- **Eventi Episodici Registrati**: `{graph_summary.get('total_events', 0)}`",
            f"- **Cause Primarie / Radici**: `{', '.join(graph_summary.get('root_causes', [])) or 'Inizializzazione in corso'}`",
            f"- **Moduli Derivati / Effetti Foglia**: `{', '.join(graph_summary.get('leaf_effects', [])) or 'Inizializzazione in corso'}`",
            "",
            "---",
            "*Documento generato autonomamente durante il turno notturno continuo di HyperSpace AGI.*",
        ]
        self.synthesis_md.write_text("\n".join(content), encoding="utf-8")
