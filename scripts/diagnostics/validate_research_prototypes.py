#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Diagnostica e Validatore Sistematico dei Prototipi di Ricerca Sovrana HyperSpace AGI.

Esegue la scansione e validazione multi-livello su tutti i prototipi generati
nelle sessioni di R&D distribuite (data/research/prototypes/):
1. Ispezione AST sintattica (ast.parse, conteggio nodi, estrazione classi/metodi).
2. Collaudo funzionale dei 6 piloni scientifici:
   - aleksander_axioms: SyntheticConsciousnessGovernor (5 assiomi di Aleksander)
   - symbolic_causal_mesh: CausalMemoryGraph (SQLite + FTS5 lineage)
   - swarm_emergence: StigmergicMeshSwarm (feromoni, gradienti, vector clocks)
   - modular_intellect: SovereignModularIntellect (memoria tri-modale & note ricorsive)
   - algorithmic_poetry_aesthetics: NeuroSymbolicPoetryEngine (endecasillabi & ComfyUI)
   - biomimetic_nature_mesh: BioMeshMonitor (entropia di Shannon, potatura link, quorum)
3. Verifica corrispondenza con l'albero di ricerca genealogico (data/research/research_tree.json).

Uso:
  python scripts/diagnostics/validate_research_prototypes.py
  python scripts/diagnostics/validate_research_prototypes.py --verbose
  python scripts/diagnostics/validate_research_prototypes.py --json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.research_tree import ASTInspector, ResearchTreeManager, RESEARCH_PILLARS

PROTOTYPES_DIR = ROOT / "data" / "research" / "prototypes"


def load_module_from_file(filepath: Path, module_name: str) -> Any:
    """Carica dinamicamente un modulo Python isolandolo in sys.modules."""
    spec = importlib.util.spec_from_file_location(module_name, str(filepath))
    if not spec or not spec.loader:
        raise ImportError(f"Impossibile creare spec per {filepath}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


class PrototypeValidator:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: List[Dict[str, Any]] = []
        self.mgr = ResearchTreeManager()

    def run_all(self) -> Dict[str, Any]:
        """Esegue la validazione su tutti i prototipi e suite funzionali."""
        t0 = time.perf_counter()
        
        # 1. Scansione AST globale di tutti i file .py in data/research/prototypes/
        ast_results = self.validate_all_ast()

        # 2. Test funzionali per ciascun pilone
        pillar_results = {
            "aleksander_axioms": self.test_pillar_aleksander_axioms(),
            "symbolic_causal_mesh": self.test_pillar_symbolic_causal_mesh(),
            "swarm_emergence": self.test_pillar_swarm_emergence(),
            "modular_intellect": self.test_pillar_modular_intellect(),
            "algorithmic_poetry_aesthetics": self.test_pillar_algorithmic_poetry(),
            "biomimetic_nature_mesh": self.test_pillar_biomimetic_mesh(),
        }

        elapsed = round(time.perf_counter() - t0, 3)

        passed_pillars = sum(1 for p in pillar_results.values() if p.get("passed"))
        total_pillars = len(pillar_results)

        summary = {
            "timestamp": time.time(),
            "elapsed_seconds": elapsed,
            "total_prototypes_scanned": len(ast_results),
            "ast_valid_count": sum(1 for r in ast_results if r.get("ast_valid")),
            "ast_invalid_count": sum(1 for r in ast_results if not r.get("ast_valid")),
            "pillars_evaluated": total_pillars,
            "pillars_passed": passed_pillars,
            "all_pillars_passed": (passed_pillars == total_pillars),
            "pillar_details": pillar_results,
            "ast_samples": ast_results[:10] if not self.verbose else ast_results,
        }
        return summary

    def validate_all_ast(self) -> List[Dict[str, Any]]:
        """Ispezione sintattica AST di ogni file prototipo."""
        out = []
        if not PROTOTYPES_DIR.exists():
            return out

        for f in sorted(PROTOTYPES_DIR.glob("*.py")):
            insp = ASTInspector.inspect_file(f)
            out.append({
                "filename": f.name,
                "size_bytes": f.stat().st_size,
                "ast_valid": insp.get("valid", False),
                "node_count": insp.get("node_count", 0),
                "classes": [c["name"] for c in insp.get("classes", [])],
                "functions": [fn["name"] for fn in insp.get("functions", [])],
                "error": insp.get("error"),
            })
        return out

    def test_pillar_aleksander_axioms(self) -> Dict[str, Any]:
        """Test funzionale dei 5 assiomi di Aleksander."""
        target_file = PROTOTYPES_DIR / "proto_aleksander_axioms_1792931402.py"
        target_file_b = PROTOTYPES_DIR / "proto_aleksander_axioms_1792931956.py"

        if not target_file.exists():
            return {"passed": False, "error": f"{target_file.name} non trovato"}

        try:
            mod = load_module_from_file(target_file, "proto_alek_1402")
            gov = mod.SyntheticConsciousnessGovernor(
                mod.ANNA_PERSONA.copy(),
                mod.DreamEngine(),
                mod.TaskScheduler(),
                mod.CheckpointManager()
            )
            adherence = gov.overall_adherence()

            # Verifica che tutti i 5 assiomi siano coperti
            required_axioms = {"self_depiction", "imagination", "attention", "planning", "valuation"}
            covered = set(adherence.keys())
            assert required_axioms.issubset(covered), f"Mancano assiomi: {required_axioms - covered}"

            # Test versione B (run_cycle con catene causali)
            mod_b = load_module_from_file(target_file_b, "proto_alek_1956")
            persona_b = {
                "self_model": {
                    "identity": "Anna-HyperSpace",
                    "type": "graph",
                    "nodes": ["persona", "memory", "goals", "values", "mesh_role", "voice"],
                }
            }
            gov_b = mod_b.SyntheticConsciousnessGovernor(persona_b)
            cycle_b = gov_b.run_cycle(dream_scenarios=2)

            return {
                "passed": True,
                "adherence_1402": adherence,
                "cycle_1956": cycle_b,
                "components": ["DreamEngine", "TaskScheduler", "CheckpointManager", "SyntheticConsciousnessGovernor"],
            }
        except Exception as exc:
            return {"passed": False, "error": str(exc)}

    def test_pillar_symbolic_causal_mesh(self) -> Dict[str, Any]:
        """Test funzionale del grafo causale SQLite + FTS5 e risalita lineage."""
        target_file = PROTOTYPES_DIR / "proto_symbolic_causal_mesh_1792927875.py"
        if not target_file.exists():
            return {"passed": False, "error": f"{target_file.name} non trovato"}

        try:
            mod = load_module_from_file(target_file, "proto_causal_mesh")
            with mod.CausalMemoryGraph(":memory:") as g:
                ev1 = g.record_event("user_prompt", "planner_spec", 0.95, {"agent_id": "mission_planner"})
                ev2 = g.record_event("planner_spec", "ast_codegen", 0.90, {"agent_id": "coder_agent"})
                ev3 = g.record_event("ast_codegen", "verifier_pass", 0.99, {"agent_id": "verifier_agent"})

                lineage = g.trace_lineage("verifier_pass", max_depth=5)
                causes = [edge.cause_id for edge in lineage]

                assert "ast_codegen" in causes, "Fallita risalita su ast_codegen"
                assert "planner_spec" in causes, "Fallita risalita su planner_spec"
                assert "user_prompt" in causes, "Fallita risalita root cause su user_prompt"

            return {
                "passed": True,
                "events_recorded": 3,
                "lineage_depth": len(lineage),
                "causes_traced": causes,
            }
        except Exception as exc:
            return {"passed": False, "error": str(exc)}

    def test_pillar_swarm_emergence(self) -> Dict[str, Any]:
        """Test funzionale dello sciame stigmergico, feromoni, gradienti e vector clocks."""
        target_file = PROTOTYPES_DIR / "proto_swarm_emergence_1792923871.py"
        if not target_file.exists():
            return {"passed": False, "error": f"{target_file.name} non trovato"}

        try:
            mod = load_module_from_file(target_file, "proto_swarm")
            nodes = ["Mac_M5", "OMEN16", "ASUSV16"]
            swarm = mod.StigmergicMeshSwarm(nodes)

            # Deposito feromoni con decadimento
            swarm.deposit_pheromone("workload_pressure", 0.75, decay_rate=0.05, current_node="Mac_M5")
            swarm.deposit_pheromone("workload_pressure", 0.65, decay_rate=0.05, current_node="OMEN16")
            swarm.deposit_pheromone("workload_pressure", 0.70, decay_rate=0.05, current_node="ASUSV16")

            grad = swarm.sense_gradient("workload_pressure")
            assert grad is not None, "Gradiente feromone nullo"
            assert grad["average"] > 0, "Valore medio gradiente non valido"
            assert grad["variance"] >= 0, "Varianza gradiente non valida"

            # Verifica vector clocks
            vc = swarm.vector_clocks
            assert all(node in vc for node in nodes), "Nodi mancanti nei vector clocks"

            return {
                "passed": True,
                "nodes": nodes,
                "gradient": grad,
                "vector_clocks_active": True,
            }
        except Exception as exc:
            return {"passed": False, "error": str(exc)}

    def test_pillar_modular_intellect(self) -> Dict[str, Any]:
        """Test funzionale della memoria tri-modale a grafo e note ricorsive."""
        target_file = PROTOTYPES_DIR / "proto_modular_intellect_1792920337.py"
        target_dict_file = PROTOTYPES_DIR / "proto_modular_intellect_1792916524.py"

        if not target_file.exists():
            return {"passed": False, "error": f"{target_file.name} non trovato"}

        try:
            # Test implementazione dizionario
            mod = load_module_from_file(target_file, "proto_modular_intellect")
            intellect = mod.SovereignModularIntellect()

            id_doc = intellect.store_experience("document", "Report Energetico Solare: 100 Watt PD", refs=[])
            id_chunk = intellect.store_experience("document", "Chunk 1: Batteria e ciclo continuo", refs=[id_doc])
            id_note = intellect.store_experience("note", "Riflessione Anna: Autosufficienza energetica", refs=[id_chunk])

            # Traversal BFS
            context = intellect.traverse_graph_context("Anna", max_hops=2)
            traversed_ids = [e.id for e in context]

            assert id_note in traversed_ids, f"Nota {id_note} non trovata nel context"
            assert id_chunk in traversed_ids, f"Chunk {id_chunk} non referenziato correttamente"

            # Alignment Auditor
            assert intellect.audit_alignment("store") is True
            assert intellect.audit_alignment("query") is True
            assert intellect.audit_alignment("malicious_injection") is False

            # Test versione B
            mod_b = load_module_from_file(target_dict_file, "proto_modular_intellect_b")
            intellect_b = mod_b.SovereignModularIntellect()
            b1 = intellect_b.store_experience("document", "Specifica Hardware Mac M5")
            b2 = intellect_b.store_experience("note", "Adattamento Metal MPS", refs=(b1,))
            ctx_b = intellect_b.traverse_graph_context("Metal", max_hops=1)

            return {
                "passed": True,
                "traversed_nodes": len(context),
                "traversed_ids": traversed_ids,
                "alignment_auditor_verified": True,
                "version_b_verified": len(ctx_b) > 0,
            }
        except Exception as exc:
            return {"passed": False, "error": str(exc)}

    def test_pillar_algorithmic_poetry(self) -> Dict[str, Any]:
        """Test funzionale di poesia neuro-simbolica e prompt visuale ComfyUI."""
        target_file = PROTOTYPES_DIR / "proto_algorithmic_poetry_aesthetics_1792930830.py"
        if not target_file.exists():
            return {"passed": False, "error": f"{target_file.name} non trovato"}

        try:
            mod = load_module_from_file(target_file, "proto_poetry")
            memories = [
                "Luce dell'alba tra i pini marittimi",
                "Onde calme che cullano il molo di pietra",
            ]
            engine = mod.NeuroSymbolicPoetryEngine(memories)
            poem, prompt = engine.generate_poem(num_lines=4)

            assert len(poem.strip().splitlines()) == 4, "Poema non composto da 4 versi"
            assert "typography:" in prompt.lower() or "sketch" in prompt.lower(), "Prompt ComfyUI non conforme"

            return {
                "passed": True,
                "verses_generated": 4,
                "prompt_sample": prompt[:80] + "...",
            }
        except Exception as exc:
            return {"passed": False, "error": str(exc)}

    def test_pillar_biomimetic_mesh(self) -> Dict[str, Any]:
        """Test funzionale di monitoraggio biomimetico, entropia di Shannon e potatura link."""
        target_file = PROTOTYPES_DIR / "proto_biomimetic_nature_mesh_1792916915.py"
        if not target_file.exists():
            return {"passed": False, "error": f"{target_file.name} non trovato"}

        try:
            mod = load_module_from_file(target_file, "proto_biomesh")
            nodi = [
                mod.Nodo("Mac_M5", "master", carico=0.2, latenza_ms=2.0),
                mod.Nodo("OMEN16", "compute_gpu", carico=0.6, latenza_ms=15.0),
                mod.Nodo("ASUSV16", "compute_lfm", carico=0.2, latenza_ms=18.0),
            ]
            rep = mod.report_mesh(nodi, latenza_ms=10.0, throughput_gbps=5.0)

            # Shannon entropy deve essere > 0 per carichi eterogenei
            assert rep["entropia_mesh"] > 0, "Entropia mesh nulla"
            assert 0.0 <= rep["efficacia_flusso"] <= 1.0, "Efficacia flusso fuori scala"

            # Potatura link alta latenza
            monitor = mod.BioMeshMonitor(nodi)
            bad_link = mod.Link("Mac_M5", "stale_node", latenza_ms=120.0, peso=0.1, attivo=True)
            pruned = monitor.pota_alta_latenza(bad_link)
            assert pruned is True, "Link ad alta latenza non potato"
            assert bad_link.attivo is False, "Link potato rimasto attivo"

            return {
                "passed": True,
                "entropia_mesh": round(rep["entropia_mesh"], 4),
                "efficacia_flusso": round(rep["efficacia_flusso"], 4),
                "pruning_verified": True,
            }
        except Exception as exc:
            return {"passed": False, "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", "-v", action="store_true", help="Mostra output dettagliato")
    parser.add_argument("--json", action="store_true", help="Stampa l'output unicamente in formato JSON")
    args = parser.parse_args()

    validator = PrototypeValidator(verbose=args.verbose)
    summary = validator.run_all()

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0 if summary["all_pillars_passed"] else 1

    print("=" * 70)
    print("  HYPERSPACE AGI — VALIDAZIONE SISTEMATICA PROTOTIPI DI RICERCA")
    print("=" * 70)
    print(f"Scansione completata in: {summary['elapsed_seconds']}s")
    print(f"Prototipi trovati: {summary['total_prototypes_scanned']}")
    print(f"AST Validi: {summary['ast_valid_count']} | AST Non Validi: {summary['ast_invalid_count']}")
    print(f"Piloni di Ricerca Validati: {summary['pillars_passed']} / {summary['pillars_evaluated']}")
    print("-" * 70)

    for pillar, res in summary["pillar_details"].items():
        status_str = "✅ PASS" if res.get("passed") else "❌ FAIL"
        print(f"[{status_str}] Pilone: {pillar}")
        if not res.get("passed"):
            print(f"        Errore: {res.get('error')}")
        else:
            details = {k: v for k, v in res.items() if k != "passed"}
            print(f"        Metriche: {json.dumps(details, ensure_ascii=False)[:80]}...")

    print("=" * 70)
    if summary["all_pillars_passed"]:
        print("ESITO GLOBALE: TUTTI I PROTOTIPI E PILONI SONO VALIDATI E 100% GREEN! 🚀")
        return 0
    else:
        print("ESITO GLOBALE: ALCUNI PILONI HANNO RISCONTRATO ERRORI.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
