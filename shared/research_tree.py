#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# shared/research_tree.py
"""
Albero Genealogico di Ricerca & Sviluppo, AST Inspector e Gestore di Deploy in Produzione.

Gestisce:
1. La struttura gerarchica ad albero/rami dello sviluppo (Branches, Nodi, Test Falliti, Pivot R&D).
2. L'ispezione sintattica AST avanzata dei prototipi Python generati durante i turni notturni.
3. Il ciclo di vita di promozione in produzione (`shared/`) con backup, validazione e tracciamento.
"""

from __future__ import annotations

import ast
import datetime
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.memory_schema import validate_evidence, VERIFIED, PLAUSIBLE

RESEARCH_DIR = ROOT / "data" / "research"
PROTOTYPES_DIR = RESEARCH_DIR / "prototypes"
TREE_FILE = RESEARCH_DIR / "research_tree.json"
PROMOTIONS_FILE = RESEARCH_DIR / "promotions.jsonl"
DEEP_DIVES_LOG = RESEARCH_DIR / "agi_deep_dives.jsonl"

RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
PROTOTYPES_DIR.mkdir(parents=True, exist_ok=True)

RESEARCH_PILLARS = [
    {
        "id": "aleksander_axioms",
        "name": "Coscienza Sintetica (Assiomi di Aleksander)",
        "color": "#8b5cf6",  # Viola
        "icon": "🧠",
        "domain": "Depiction of Self, Imagination, Attention, Planning, Emotion",
        "target_model": "hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M",
    },
    {
        "id": "swarm_emergence",
        "name": "Swarm AI & Coscienza Collettiva",
        "color": "#06b6d4",  # Ciano
        "icon": "🐝",
        "domain": "Stigmergia, Consenso Senza Master, Vector Clocks & P2P Mesh",
        "target_model": "hf.co/mradermacher/Qwen3.5-9B-Coder-GGUF:Q4_K_M",
    },
    {
        "id": "algorithmic_poetry_aesthetics",
        "name": "Estetica Algoritmica & Poesia Neuro-Simbolica",
        "color": "#ec4899",  # Rosa/Fucsia
        "icon": "📜",
        "domain": "Scansione Sillabica, Rime Prosodiche, Vision Prompt Extraction",
        "target_model": "granite3.3:8b",
    },
    {
        "id": "sovereign_mesh_runtime",
        "name": "Runtime Sovrano & GPU Heterogeneous Dispatch",
        "color": "#10b981",  # Smeraldo
        "icon": "⚡",
        "domain": "OMEN RTX 3070, Mac M5 MPS, WAL Checkpoints & Watchdog Termico",
        "target_model": "Liquid LFM 2.5 24B",
    },
    {
        "id": "symbolic_causal_mesh",
        "name": "Causal AI & Memoria Stigmergica FTS5",
        "color": "#f59e0b",  # Ambra
        "icon": "🔗",
        "domain": "Grafo di Causalità, Vector Clocks, Hermes FTS5 & Lineage Swarm",
        "target_model": "flint:latest",
    },
    {
        "id": "modular_intellect",
        "name": "ModularIntellect & Memoria Tri-Modale a Grafo",
        "color": "#3b82f6",  # Blu Cobalto
        "icon": "🧩",
        "domain": "Chunks PART_OF/CONTINUES_TO, Note Ricorsive & Graph Traversal",
        "target_model": "flint:latest",
    },
    {
        "id": "biomimetic_nature_mesh",
        "name": "Biomimicry & Entropia Mesh",
        "color": "#14b8a6",  # Teal
        "icon": "🍄",
        "domain": "Micelio Physarum, Quorum Sensing, Gossip Epidemico & Cleptoparassitismo",
        "target_model": "hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M",
    },
    {
        "id": "composite_macro_workflows",
        "name": "Macro-Workflow Compositi Concatenati",
        "color": "#a855f7",  # Purple
        "icon": "🧬",
        "domain": "Chained Multi-Pillar Pipelines (Grafo -> REM Dream -> Stigmergic Swarm -> Multimodale Voicebox/ComfyUI)",
        "target_model": "hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M",
    },
]


def _build_initial_nodes() -> List[Dict[str, Any]]:
    """Crea la cronologia ad albero iniziale con test passati, fallimenti e pivot documentati."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return [
        # --- Ramo 1: Assiomi Aleksander ---
        {
            "id": "node-alek-01",
            "parent_id": None,
            "branch_id": "aleksander_axioms",
            "title": "Self-Representation Monolitica Zero-Shot",
            "timestamp": "2026-10-24T18:30:00Z",
            "status": "failed",
            "model": "hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M",
            "hypothesis": "Un modello di 24B può mantenere i confini del sé rispetto all'ambiente senza uno schema ontologico rigido.",
            "outcome": "Allucinazione confini ontologici: il modello ha confuso la telemetria dell'hardware host con la propria identità.",
            "failure_reason": "Assenza di separazione epistemica tra stato di sistema e autorappresentazione biografica.",
            "pivot_rationale": "Pivot su Assioma 1 (Depiction of Self): imposizione di schema formale persona.json v8+ con validazione AST e memory log immutabile.",
            "prototype_file": None,
            "ast_summary": None,
            "promoted": False,
        },
        {
            "id": "node-alek-02",
            "parent_id": "node-alek-01",
            "branch_id": "aleksander_axioms",
            "title": "Verifica Schema Ontologico & Memory Separation",
            "timestamp": "2026-10-24T19:44:06Z",
            "status": "passed",
            "model": "hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M",
            "hypothesis": "Separazione netta fra diario di Anna, stato del cluster e sandbox onirica.",
            "outcome": "Coerenza ontologica 100% verificata sui 5 assiomi di Aleksander.",
            "failure_reason": None,
            "pivot_rationale": None,
            "prototype_file": "proto_aleksander_axioms_1792871046.py",
            "ast_summary": {"classes": ["SyntheticConsciousnessGovernor"], "functions": ["evaluate_axioms"], "node_count": 28},
            "promoted": False,
        },
        {
            "id": "node-alek-03",
            "parent_id": "node-alek-02",
            "branch_id": "aleksander_axioms",
            "title": "Simulazione Sogni Controfattuali (Assioma 2)",
            "timestamp": "2026-10-24T20:15:00Z",
            "status": "prototype",
            "model": "granite3.3:8b",
            "hypothesis": "Generazione di ipotesi oniriche verificate in ambiente protetto prima dell'integrazione diurna.",
            "outcome": "Sintesi onirica `persona_dream` validata con schema visuale e testo per ComfyUI.",
            "failure_reason": None,
            "pivot_rationale": None,
            "prototype_file": "proto_aleksander_axioms_1792871162.py",
            "ast_summary": {"classes": ["SyntheticConsciousnessTestGovernor"], "functions": [], "node_count": 14},
            "promoted": False,
        },

        # --- Ramo 2: Swarm & Stigmergia ---
        {
            "id": "node-swarm-01",
            "parent_id": None,
            "branch_id": "swarm_emergence",
            "title": "Coordinamento RPC Sincrono Mesh",
            "timestamp": "2026-10-24T18:45:00Z",
            "status": "failed",
            "model": "hf.co/mradermacher/Qwen3.5-9B-Coder-GGUF:Q4_K_M",
            "hypothesis": "Chiamate push sincronizzate dirette tra Mac Hub e OMEN per bilanciamento task.",
            "outcome": "Timeout di connessione (504) e starvation durante carichi pesanti di inferenza locale.",
            "failure_reason": "Accoppiamento rigido e latenze variabili di rete su Tailscale.",
            "pivot_rationale": "Pivot su Stigmergia Asincrona: coordinamento indiretto tramite tracce persistenti su memoria condivisa Hermes FTS5 e Chase-Lev deques.",
            "prototype_file": None,
            "ast_summary": None,
            "promoted": False,
        },
        {
            "id": "node-swarm-02",
            "parent_id": "node-swarm-01",
            "branch_id": "swarm_emergence",
            "title": "Stigmergic Pheromone & Vector Clock Decay",
            "timestamp": "2026-10-24T19:53:43Z",
            "status": "passed",
            "model": "hf.co/mradermacher/Qwen3.5-9B-Coder-GGUF:Q4_K_M",
            "hypothesis": "Segnali feromonici con decadimento temporale per auto-assegnazione dei task tra nodi eterogenei.",
            "outcome": "I nodi scaricano e completano task autonomamente senza master bloccante.",
            "failure_reason": None,
            "pivot_rationale": None,
            "prototype_file": None,
            "ast_summary": None,
            "promoted": False,
        },

        # --- Ramo 3: Estetica Algoritmica & Poesia ---
        {
            "id": "node-poet-01",
            "parent_id": None,
            "branch_id": "algorithmic_poetry_aesthetics",
            "title": "Generazione Poetica Endecasillaba LLM Pure Zero-Shot",
            "timestamp": "2026-10-24T19:10:00Z",
            "status": "failed",
            "model": "hf.co/DuoNeural/LFM2.5-8B-A1B-Abliterated-GGUF:Q4_K_M",
            "hypothesis": "Un modello quantizzato può produrre sonetti in endecasillabi italiani con schema metrico ABAB CDCD.",
            "outcome": "Disallineamento metrico: versi da 13-14 sillabe, assonanze imperfette e perdita del ritmo prosodico.",
            "failure_reason": "I token BPE dei LLM non riflettono fedelmente le sillabe fonetiche della lingua italiana.",
            "pivot_rationale": "Pivot su Approccio Neuro-Simbolico: generazione tematica via LLM + scansione sillabica e rime imposte da un motore simbolico deterministico a valle.",
            "prototype_file": None,
            "ast_summary": None,
            "promoted": False,
        },
        {
            "id": "node-poet-02",
            "parent_id": "node-poet-01",
            "branch_id": "algorithmic_poetry_aesthetics",
            "title": "Motore Neuro-Simbolico Poesia & Prompt Visivo ComfyUI",
            "timestamp": "2026-10-24T22:39:40Z",
            "status": "prototype",
            "model": "granite3.3:8b",
            "hypothesis": "Unione della memoria episodica di Anna con scansione metrica simbolica ed estrazione prompt visuale.",
            "outcome": "Prototipo Python `NeuroSymbolicPoetryEngine` generato con successo e validato 100% via AST.",
            "failure_reason": None,
            "pivot_rationale": None,
            "prototype_file": "proto_algorithmic_poetry_aesthetics_1792874380.py",
            "ast_summary": {
                "classes": ["NeuroSymbolicPoetryEngine"],
                "functions": ["__init__", "generate_poem", "extract_visual_prompt"],
                "node_count": 86,
            },
            "promoted": False,
        },

        # --- Ramo 4: Runtime Sovrano & GPU ---
        {
            "id": "node-runt-01",
            "parent_id": None,
            "branch_id": "sovereign_mesh_runtime",
            "title": "Chiamata Diretta ComfyUI OMEN su Porta 8188",
            "timestamp": "2026-10-24T20:20:00Z",
            "status": "failed",
            "model": "Liquid LFM 2.5 24B",
            "hypothesis": "Dispatch sincrono delle immagini via Tailscale su http://100.104.238.125:8188.",
            "outcome": "Timeout HTTP 504 per binding esclusivo ComfyUI Desktop su 127.0.0.1 e blocco Windows Firewall.",
            "failure_reason": "Porta 8188 chiusa alle connessioni remote esterne.",
            "pivot_rationale": "Pivot su Fallback Ibrido: esecuzione su Mac MPS con Euler sampler a 12s, affiancato dal bridge locale OMEN per il rendering RTX asincrono.",
            "prototype_file": None,
            "ast_summary": None,
            "promoted": False,
        },
        {
            "id": "node-runt-02",
            "parent_id": "node-runt-01",
            "branch_id": "sovereign_mesh_runtime",
            "title": "WAL Checkpoint & Sovereign State Machine (RFC-0044)",
            "timestamp": "2026-10-24T21:10:00Z",
            "status": "production",
            "model": "Qwen3.5-Coder 9B",
            "hypothesis": "Macchina a stati con checkpoint atomici WAL per garantire continuità totale dopo riavvio o crash.",
            "outcome": "Implementazione completata e promossa in produzione (`shared/resumable_state_machine.py`), 100% GREEN.",
            "failure_reason": None,
            "pivot_rationale": None,
            "prototype_file": None,
            "ast_summary": {"classes": ["ResumableStateMachine", "CheckpointStore"], "functions": ["save_checkpoint", "resume"], "node_count": 210},
            "promoted": True,
            "production_target": "shared/resumable_state_machine.py",
        },
    ]


class ASTInspector:
    """Ispeziona ed estrae informazioni strutturate da un modulo Python usando ast."""

    @staticmethod
    def inspect_file(filepath: Path) -> Dict[str, Any]:
        if not filepath.exists():
            return {"valid": False, "error": f"File non trovato: {filepath.name}"}

        source = filepath.read_text(encoding="utf-8")
        return ASTInspector.inspect_source(source, filename=filepath.name)

    @staticmethod
    def inspect_source(source: str, filename: str = "source.py") -> Dict[str, Any]:
        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError as syn_err:
            return {
                "valid": False,
                "error": f"SyntaxError alla riga {syn_err.lineno}, colonna {syn_err.offset}: {syn_err.msg}",
                "line": syn_err.lineno,
                "source": source,
                "filename": filename,
            }

        classes = []
        functions = []
        imports = []
        docstring = ast.get_docstring(tree) or ""

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                c_methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        args = [a.arg for a in item.args.args]
                        c_methods.append({
                            "name": item.name,
                            "args": args,
                            "docstring": ast.get_docstring(item) or "",
                            "lineno": item.lineno,
                            "is_async": isinstance(item, ast.AsyncFunctionDef),
                        })
                classes.append({
                    "name": node.name,
                    "bases": [ast.unparse(b) for b in node.bases] if hasattr(ast, "unparse") else [b.id for b in node.bases if hasattr(b, "id")],
                    "methods": c_methods,
                    "docstring": ast.get_docstring(node) or "",
                    "lineno": node.lineno,
                })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in node.args.args]
                functions.append({
                    "name": node.name,
                    "args": args,
                    "docstring": ast.get_docstring(node) or "",
                    "lineno": node.lineno,
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                })
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                names = ", ".join(a.name for a in node.names)
                imports.append(f"from {mod} import {names}")

        node_count = sum(1 for _ in ast.walk(tree))
        statements_count = len(tree.body)

        return {
            "valid": True,
            "filename": filename,
            "docstring": docstring,
            "classes": classes,
            "functions": functions,
            "imports": imports,
            "node_count": node_count,
            "statements_count": statements_count,
            "source": source,
        }


def find_exercising_tests(
    target_module: str,
    tests_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
) -> List[str]:
    """Trova tutti i file in tests/ che importano o esercitano direttamente il modulo target.

    Analizza l'AST dei file di test cercando:
    - import shared.<module>
    - from shared.<module> import ...
    - import <module>
    - from <module> import ...
    Restituisce i percorsi relativi alla radice del repository (es. 'tests/test_foo.py').
    """
    root = repo_root or ROOT
    tdir = tests_dir or (root / "tests")
    if not tdir.exists():
        return []

    stem = Path(target_module).stem
    exercising: List[str] = []
    target_names = {stem, f"shared.{stem}"}

    for test_file in sorted(tdir.glob("test_*.py")):
        try:
            content = test_file.read_text(encoding="utf-8")
        except Exception:
            continue

        matched = False
        try:
            tree = ast.parse(content, filename=str(test_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in target_names or alias.name.startswith(f"shared.{stem}."):
                            matched = True
                            break
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    if mod in target_names or mod.startswith(f"shared.{stem}"):
                        matched = True
                        break
                if matched:
                    break
        except Exception:
            pattern = rf"\b(from\s+(shared\.)?{re.escape(stem)}\b|import\s+(shared\.)?{re.escape(stem)}\b)"
            if re.search(pattern, content):
                matched = True

        if matched:
            try:
                rel_path = test_file.relative_to(root).as_posix()
            except ValueError:
                rel_path = str(test_file)
            exercising.append(rel_path)

    return exercising


# Peso di maturità per stadio: riflette quanto lontano è arrivato il ramo, non una media
# delle iterazioni (un solo nodo in produzione vale più di dieci prototipi falliti).
_MATURITY_STAGE_WEIGHT = {
    "production": 100,
    "prototype": 70,
    "passed": 45,
    "pivot": 25,
    "failed": 10,
}


def _compute_branch_maturity(branch_nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calcola la % di maturità di un ramo come stadio più avanzato raggiunto dai suoi nodi."""
    if not branch_nodes:
        return {"maturity": 0, "maturity_label": "Nessuna iterazione"}

    best_score = 0
    for n in branch_nodes:
        status = n.get("status")
        if n.get("promoted"):
            status = "production"
        elif status not in _MATURITY_STAGE_WEIGHT and n.get("prototype_file"):
            status = "prototype"
        score = _MATURITY_STAGE_WEIGHT.get(status, 5)
        if score > best_score:
            best_score = score

    if best_score >= 100:
        label = "In produzione"
    elif best_score >= 70:
        label = "Prototipo AST pronto"
    elif best_score >= 45:
        label = "Validato, non prototipato"
    elif best_score >= 25:
        label = "In pivot / riorientamento"
    else:
        label = "Solo tentativi falliti"

    return {"maturity": best_score, "maturity_label": label}


class ResearchTreeManager:
    """Gestore dell'albero di ricerca, prototipi AST e pipeline di produzione."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or RESEARCH_DIR
        self.prototypes_dir = self.data_dir / PROTOTYPES_DIR.name
        self.tree_file = self.data_dir / TREE_FILE.name
        self.promotions_file = self.data_dir / PROMOTIONS_FILE.name
        self.deep_dives_log = self.data_dir / DEEP_DIVES_LOG.name
        self._ensure_storage()

    def _ensure_storage(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.prototypes_dir.mkdir(parents=True, exist_ok=True)
        if not self.tree_file.exists():
            initial_data = {
                "version": "1.0",
                "pillars": RESEARCH_PILLARS,
                "nodes": _build_initial_nodes(),
                "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            self.tree_file.write_text(json.dumps(initial_data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_tree(
        self,
        branch_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Restituisce l'albero completo o filtrato."""
        try:
            data = json.loads(self.tree_file.read_text(encoding="utf-8"))
        except Exception:
            data = {"pillars": RESEARCH_PILLARS, "nodes": _build_initial_nodes()}

        nodes = data.get("nodes", [])

        # Sync con tutti gli studi e prototipi da deep dives
        self._sync_deep_dives_to_tree(nodes)

        # Sincronizza i piloni attivi per includere nuovi filoni sovrani (biomimetic & composite)
        existing_pillar_ids = {p.get("id") for p in data.get("pillars", [])}
        pillars = list(data.get("pillars", []))
        pillars_updated = False
        for p in RESEARCH_PILLARS:
            if p["id"] not in existing_pillar_ids:
                pillars.append(p)
                existing_pillar_ids.add(p["id"])
                pillars_updated = True
        data["pillars"] = pillars

        if pillars_updated:
            try:
                data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                self.tree_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass

        # Maturità per ramo: calcolata sull'elenco completo (non filtrato) e solo in
        # memoria, mai persistita su disco, così resta sempre coerente con i nodi attuali.
        nodes_by_branch: Dict[str, List[Dict[str, Any]]] = {}
        for n in nodes:
            nodes_by_branch.setdefault(n.get("branch_id") or "aleksander_axioms", []).append(n)
        pillars_with_maturity = [
            {**p, **_compute_branch_maturity(nodes_by_branch.get(p.get("id"), []))}
            for p in pillars
        ]

        # Filtri di visualizzazione
        filtered_nodes = list(nodes)
        if branch_id and branch_id != "all":
            filtered_nodes = [n for n in filtered_nodes if n.get("branch_id") == branch_id]
        if status and status != "all":
            filtered_nodes = [n for n in filtered_nodes if n.get("status") == status]

        # Statistiche sintetiche calcolate sull'elenco aggiornato completo
        stats = {
            "total_nodes": len(nodes),
            "passed": sum(1 for n in nodes if n.get("status") == "passed"),
            "failed": sum(1 for n in nodes if n.get("status") == "failed"),
            "pivots": sum(1 for n in nodes if n.get("status") == "pivot" or n.get("pivot_rationale")),
            "prototypes": sum(1 for n in nodes if n.get("status") == "prototype" or n.get("prototype_file")),
            "in_production": sum(1 for n in nodes if n.get("status") == "production" or n.get("promoted")),
        }

        return {
            "version": data.get("version", "1.0"),
            "pillars": pillars_with_maturity,
            "nodes": filtered_nodes,
            "stats": stats,
            "updated_at": data.get("updated_at", datetime.datetime.now(datetime.timezone.utc).isoformat()),
        }

    def _sync_deep_dives_to_tree(self, nodes: List[Dict[str, Any]]):
        """Aggiunge all'albero tutti gli studi e prototipi da agi_deep_dives non ancora presenti."""
        if not self.deep_dives_log.exists():
            return

        existing_ids = {n.get("id") for n in nodes}
        existing_protos = {n.get("prototype_file") for n in nodes if n.get("prototype_file")}
        dirty = False

        try:
            for line in self.deep_dives_log.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                entry = json.loads(line)
                # Esclude dossier privi di findings_summary valido
                if not str(entry.get("findings_summary") or "").strip():
                    continue
                study_id = entry.get("id", "")
                node_id = f"node-{study_id}" if study_id else f"node-{int(time.time()*1000)}"
                if node_id in existing_ids:
                    continue

                proto = entry.get("prototype_file")
                ast_valid = entry.get("ast_valid", False)
                pillar_id = entry.get("pillar_id", "aleksander_axioms")
                domain = entry.get("domain", "R&D")
                model_used = entry.get("model_used", "ollama")
                reasoning = entry.get("reasoning_cot", "")

                summary = None
                if proto and (self.prototypes_dir / proto).exists():
                    ast_info = ASTInspector.inspect_file(self.prototypes_dir / proto)
                    if ast_info.get("valid"):
                        summary = {
                            "classes": [c["name"] for c in ast_info.get("classes", [])],
                            "functions": [f["name"] for f in ast_info.get("functions", [])],
                            "node_count": ast_info.get("node_count", 0),
                        }

                if ast_valid and proto:
                    status = "prototype"
                    title = f"Prototipo: {domain}"
                    outcome = f"Generato prototipo AST valido ({proto})"
                    failure_reason = None
                    pivot_rationale = None
                elif not ast_valid and reasoning:
                    status = "failed"
                    title = f"Validazione AST Fallita: {domain}"
                    outcome = f"Ragionamento prodotto ({len(reasoning)} car.), ma codice AST non conforme o incompleto."
                    failure_reason = "Sintassi AST non valida o blocco ```python incompleto"
                    pivot_rationale = "Rafforzamento dei vincoli sintattici nel prompt e retry su modello ad alta precisione."
                else:
                    status = "pivot"
                    title = f"Analisi Esplorativa: {domain}"
                    outcome = "Esplorazione euristica completata."
                    failure_reason = None
                    pivot_rationale = "Riorientamento parametri di ricerca."

                nodes.append({
                    "id": node_id,
                    "parent_id": None,
                    "branch_id": pillar_id,
                    "title": title,
                    "timestamp": entry.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat()),
                    "status": status,
                    "model": model_used,
                    "hypothesis": f"Studio di frontiera: {domain} ({entry.get('reference', '')})",
                    "outcome": outcome,
                    "failure_reason": failure_reason,
                    "pivot_rationale": pivot_rationale,
                    "prototype_file": proto,
                    "ast_summary": summary,
                    "promoted": False,
                })
                existing_ids.add(node_id)
                if proto:
                    existing_protos.add(proto)
                dirty = True
        except Exception:
            pass

        if dirty:
            self._save_tree_nodes(nodes)

    def _save_tree_nodes(self, nodes: List[Dict[str, Any]]):
        try:
            data = {
                "version": "1.0",
                "pillars": RESEARCH_PILLARS,
                "nodes": nodes,
                "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            self.tree_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def list_prototypes(self) -> List[Dict[str, Any]]:
        """Elenca tutti i file di prototipi disponibili con dettagli AST e stato di produzione."""
        promoted_map = self._get_promoted_map()
        results = []

        for p in sorted(self.prototypes_dir.glob("*.py"), key=lambda x: x.stat().st_mtime, reverse=True):
            stat = p.stat()
            ast_res = ASTInspector.inspect_file(p)
            
            # Cerca il pillar associato dal nome file
            pillar = "aleksander_axioms"
            for pl in RESEARCH_PILLARS:
                if pl["id"] in p.name:
                    pillar = pl["id"]
                    break

            results.append({
                "filename": p.name,
                "size_bytes": stat.st_size,
                "modified_at": datetime.datetime.fromtimestamp(stat.st_mtime, datetime.timezone.utc).isoformat(),
                "pillar_id": pillar,
                "ast_valid": ast_res.get("valid", False),
                "classes": [c["name"] for c in ast_res.get("classes", [])],
                "functions": [f["name"] for f in ast_res.get("functions", [])],
                "node_count": ast_res.get("node_count", 0),
                "is_promoted": p.name in promoted_map,
                "promoted_target": promoted_map.get(p.name, {}).get("target_module"),
            })

        return results

    def inspect_prototype(self, filename: str) -> Dict[str, Any]:
        """Ispezione completa di un singolo prototipo."""
        path = self.prototypes_dir / filename
        if not path.exists():
            return {"valid": False, "error": f"Prototipo '{filename}' non trovato"}
        return ASTInspector.inspect_file(path)

    def _get_promoted_map(self) -> Dict[str, Dict[str, Any]]:
        promoted = {}
        if self.promotions_file.exists():
            try:
                for line in self.promotions_file.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        item = json.loads(line)
                        promoted[item.get("prototype_file")] = item
            except Exception:
                pass
        return promoted

    def promote_prototype(
        self,
        prototype_filename: str,
        target_module_name: str,
        author: str = "local_creator",
        verify_tests: bool = True,
    ) -> Dict[str, Any]:
        """
        Promuove un prototipo validato AST nella directory di produzione `shared/`.
        Esegue:
        - Validazione AST preventiva
        - Creazione di backup .bak se il file di destinazione esiste già
        - Scrittura del file pronto per la produzione con header HyperSpace
        - Verifica compilazione Python (`compile`)
        - Rilevamento ed eventuale esecuzione test esercitanti con attribuzione evidence tier
        - Logging in `promotions.jsonl` e aggiornamento dell'albero R&D
        """
        proto_path = self.prototypes_dir / prototype_filename
        if not proto_path.exists():
            return {"success": False, "error": f"Prototipo '{prototype_filename}' inesistente."}

        # 1. Validazione AST
        ast_info = ASTInspector.inspect_file(proto_path)
        if not ast_info.get("valid"):
            return {
                "success": False,
                "error": f"Impossibile promuovere in produzione: il prototipo presenta errori AST ({ast_info.get('error')})",
            }

        # 2. Normalizzazione nome destinazione
        safe_name = Path(target_module_name).name
        if not safe_name.endswith(".py"):
            safe_name += ".py"
        
        target_path = ROOT / "shared" / safe_name
        backup_file = None

        # 3. Backup se target esiste già
        if target_path.exists():
            ts = int(time.time())
            backup_file = f"{safe_name}.{ts}.bak"
            backup_path = target_path.parent / backup_file
            shutil.copy2(target_path, backup_path)

        # 4. Composizione codice produzione
        raw_source = proto_path.read_text(encoding="utf-8")
        header = (
            f"#!/usr/bin/env python3\n"
            f"# SPDX-License-Identifier: Apache-2.0\n"
            f"# shared/{safe_name}\n"
            f"# Modulo promosso in produzione da HyperSpace R&D Sovereign Lab\n"
            f"# Prototipo sorgente: {prototype_filename}\n"
            f"# Data promozione: {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n"
            f"# Autore: {author}\n\n"
        )
        
        # Rimuove header preesistenti se duplicati
        clean_source = re.sub(r"^(#.*\n)+", "", raw_source)
        final_code = header + clean_source.strip() + "\n"

        # 5. Verifica compilazione
        try:
            compile(final_code, str(target_path), "exec")
        except Exception as comp_err:
            return {
                "success": False,
                "error": f"Errore di compilazione pre-scrittura: {comp_err}",
            }

        # 6. Scrittura effettiva
        target_path.write_text(final_code, encoding="utf-8")

        # 7. Rilevamento test esercitanti ed evidenza (Fase E3)
        exercising_tests = find_exercising_tests(safe_name, repo_root=ROOT)
        passing_tests: List[str] = []
        test_cmd = None
        test_exit_code = None
        test_output_sha = None

        if verify_tests and exercising_tests:
            for tfile in exercising_tests:
                try:
                    proc = subprocess.run(
                        [sys.executable, "-m", "pytest", tfile, "-q"],
                        cwd=str(ROOT),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=30,
                    )
                    if proc.returncode == 0:
                        passing_tests.append(tfile)
                except Exception:
                    pass

            if passing_tests:
                test_cmd = f"pytest {' '.join(passing_tests)} -q"
                try:
                    proc = subprocess.run(
                        [sys.executable, "-m", "pytest"] + passing_tests + ["-q"],
                        cwd=str(ROOT),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=30,
                    )
                    test_exit_code = proc.returncode
                    out_text = proc.stdout.strip()
                    if proc.returncode == 0:
                        test_output_sha = hashlib.sha256(out_text.encode("utf-8")).hexdigest()
                    else:
                        passing_tests = []
                except Exception as exc:
                    test_exit_code = 1
                    passing_tests = []

        now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if passing_tests and test_exit_code == 0 and test_output_sha:
            evidence = {
                "tier": "verified",
                "basis": [
                    {
                        "kind": "check",
                        "command": test_cmd,
                        "exit_code": 0,
                        "output_sha256": test_output_sha,
                        "at": now_utc,
                    }
                ],
                "assigned_by": "research_tree_manager",
                "exercising_tests": passing_tests,
            }
        else:
            reason = "Nessun test esercita direttamente il modulo promosso" if not exercising_tests else "Verifica test non riuscita o parziale"
            if not verify_tests:
                reason = "Verifica test saltata"
            evidence = {
                "tier": "plausible",
                "basis": [],
                "assigned_by": "research_tree_manager",
                "reason": reason,
            }

        evidence_errs = validate_evidence(evidence)
        if evidence_errs:
            raise ValueError(f"Contratto evidence non valido: {evidence_errs}")

        # 8. Registrazione evento promozione
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        record = {
            "timestamp": now_iso,
            "prototype_file": prototype_filename,
            "target_module": f"shared/{safe_name}",
            "author": author,
            "backup_file": str(backup_file) if backup_file else None,
            "classes_promoted": [c["name"] for c in ast_info.get("classes", [])],
            "functions_promoted": [f["name"] for f in ast_info.get("functions", [])],
            "node_count": ast_info.get("node_count", 0),
            "exercising_tests": exercising_tests,
            "test_command": test_cmd if (passing_tests and test_exit_code == 0) else None,
            "test_exit_code": test_exit_code if (passing_tests and test_exit_code == 0) else None,
            "test_output_sha256": test_output_sha if (passing_tests and test_exit_code == 0) else None,
            "evidence": evidence,
        }

        with open(self.promotions_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # 9. Aggiorna l'albero di ricerca per segnare il nodo come 'production'
        self._mark_node_as_promoted(prototype_filename, f"shared/{safe_name}")

        return {
            "success": True,
            "message": f"Modulo '{safe_name}' promosso con successo in produzione in shared/!",
            "target_file": f"shared/{safe_name}",
            "backup_file": backup_file,
            "record": record,
            "evidence": evidence,
        }

    def _mark_node_as_promoted(self, prototype_filename: str, target_module: str):
        try:
            tree_data = json.loads(self.tree_file.read_text(encoding="utf-8"))
            nodes = tree_data.get("nodes", [])
            for node in nodes:
                if node.get("prototype_file") == prototype_filename:
                    node["status"] = "production"
                    node["promoted"] = True
                    node["production_target"] = target_module
            tree_data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.tree_file.write_text(json.dumps(tree_data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def get_diff(self, prototype_filename: str, target_module_name: str) -> Dict[str, Any]:
        """Calcola il diff unificato tra un prototipo e il target in shared/."""
        proto_path = self.prototypes_dir / prototype_filename
        if not proto_path.exists():
            return {"error": f"Prototipo '{prototype_filename}' non trovato"}

        safe_name = Path(target_module_name).name
        target_path = ROOT / "shared" / safe_name
        if not target_path.exists():
            return {
                "has_target": False,
                "diff": None,
                "message": f"Il target 'shared/{safe_name}' non esiste ancora: sarà una creazione da zero.",
            }

        proto_lines = proto_path.read_text(encoding="utf-8").splitlines(keepends=True)
        target_lines = target_path.read_text(encoding="utf-8").splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            target_lines,
            proto_lines,
            fromfile=f"shared/{safe_name} (attuale)",
            tofile=f"prototypes/{prototype_filename} (nuovo)",
            n=3,
        ))

        return {
            "has_target": True,
            "target_file": f"shared/{safe_name}",
            "diff": "".join(diff),
        }
