#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""tests/test_memory_evidence_e4.py.

Suite di verifica per la Fase E4 dei Livelli di Evidenza della Memoria (docs/memory-evidence-tiers.md):
1. Contraddittore su secondo nodo (shared.mesh_critic):
   - Generazione prompt di Red Team privo di dati sensibili / memorie sorgenti.
   - Selezione peer mesh idoneo (esclusione nodo proponente, nodi degradati, nodi mobile in failover).
   - Chiamata best-effort non bloccante con timeout e fallback fail-open.
2. Contratto di Evidenza (attach_critique):
   - Inserimento in evidence.basis con kind 'critique' e attribuzione 'by'.
   - REGOLA FERREA: Nessun livello sale per effetto di un modello. Il tier resta PLAUSIBLE.
   - validate_evidence() accetta la critica in PLAUSIBLE e la rifiuta come prova per VERIFIED.
3. Integrazione Sogni Notturni (node.dreaming.DreamJournal):
   - add_critique allega la critica a un sogno nel journal.
   - Promozione con fonti: l'insight promosso eredita 'sourced' dalla review E preserva
     la critica Red Team nel basis.
4. Integrazione Dossier di Ricerca (shared.agi_research_engine.AGIResearchEngine):
   - add_dossier_critique allega una critica a uno studio registrato.
5. Visualizzazione Agenti (control-plane.cp.tool._omega_query):
   - _omega_query visualizza le obiezioni del Red Team allegate alle memorie.
"""

from __future__ import annotations

import ast
import json
import tempfile
import unittest
from pathlib import Path

from node.dreaming import DreamJournal
from shared.agi_research_engine import AGIResearchEngine
from shared.memory_schema import (
    PLAUSIBLE,
    SOURCED,
    VERIFIED,
    evidence_tier,
    validate_evidence,
)
from shared.mesh_critic import (
    MeshCritic,
    attach_critique,
    build_critique_prompt,
    parse_critique_text,
    select_critic_peer,
)
from tests import cp_source


class TestMemoryEvidenceE4MeshCritic(unittest.TestCase):
    """Verifica le funzioni core del modulo Contraddittore (shared/mesh_critic.py)."""

    def test_build_critique_prompt_excludes_private_context(self):
        prompt = build_critique_prompt(
            hypothesis_summary="La stigmergia basata su feromoni digitali riduce il consenso a 0ms.",
            open_questions=["Cosa accade se un nodo cade?", "Come scalano i vector clock?"],
        )
        self.assertIn("La stigmergia basata su feromoni digitali", prompt)
        self.assertIn("Cosa accade se un nodo cade?", prompt)
        self.assertIn("Red Team", prompt)
        self.assertIn("Punti ciechi", prompt)
        # Non deve contenere prompt di chat privata, token o memorie grezze
        self.assertNotIn("source_memory_ids", prompt)
        self.assertNotIn("session_id", prompt)

    def test_parse_critique_text_removes_think_and_fences(self):
        raw = "<think>Questo modello assume troppo.</think>```markdown\n1. Latenza non nulla.\n2. Partizioni di rete.\n```"
        clean = parse_critique_text(raw)
        self.assertNotIn("<think>", clean)
        self.assertNotIn("```", clean)
        self.assertIn("1. Latenza non nulla.", clean)

    def test_select_critic_peer_filters(self):
        active_nodes = [
            {"node_id": "mac-hub", "status": "active", "endpoint": "http://100.1.1.1:8081", "tier": "hub"},
            {"node_id": "node-omen", "status": "active", "endpoint": "http://100.1.1.2:8081", "tier": "worker", "model": "granite3.3:8b"},
            {"node_id": "node-degraded", "status": "degraded", "endpoint": "http://100.1.1.3:8081", "tier": "worker"},
            {"node_id": "node-s24", "status": "active", "endpoint": "http://100.1.1.4:8081", "tier": "mobile", "mobile_role": "failover"},
            {"node_id": "node-browser", "status": "active", "endpoint": "http://100.1.1.5:8081", "tier": "browser"},
        ]

        # Se il proponente è mac-hub, deve selezionare node-omen
        chosen = select_critic_peer(proponent_node_id="mac-hub", active_nodes=active_nodes)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["node_id"], "node-omen")
        self.assertEqual(chosen["model"], "granite3.3:8b")

        # Se il proponente è node-omen, deve selezionare mac-hub
        chosen_omen = select_critic_peer(proponent_node_id="node-omen", active_nodes=active_nodes)
        self.assertIsNotNone(chosen_omen)
        self.assertEqual(chosen_omen["node_id"], "mac-hub")

        # Se non ci sono nodi eleggibili diversi dal proponente
        single_list = [{"node_id": "mac-hub", "status": "active", "endpoint": "http://100.1.1.1:8081"}]
        self.assertIsNone(select_critic_peer(proponent_node_id="mac-hub", active_nodes=single_list))

    def test_attach_critique_never_elevates_evidence_tier(self):
        entry = {
            "content": "Tesi sull'emergenza di rete.",
            "evidence": {"tier": PLAUSIBLE, "basis": []},
        }
        critique = {
            "kind": "critique",
            "by": "node-omen:granite3.3:8b",
            "content": "Presuppone canali privi di jitter; in caso di partizione il consenso fallisce.",
        }

        updated = attach_critique(entry, critique)
        ev = updated["evidence"]
        # IL TIER NON DEVE SALIRE: resta PLAUSIBLE
        self.assertEqual(ev["tier"], PLAUSIBLE)
        self.assertEqual(len(ev["basis"]), 1)
        self.assertEqual(ev["basis"][0]["kind"], "critique")
        self.assertEqual(ev["basis"][0]["by"], "node-omen:granite3.3:8b")

        # Validazione formale del contratto memory_schema
        errors = validate_evidence(ev)
        self.assertEqual(errors, [])

        # Se qualcuno tentasse di dichiarare verified solo con critique, validate_evidence lo boccia
        bad_evidence = {"tier": VERIFIED, "basis": [critique]}
        self.assertTrue(len(validate_evidence(bad_evidence)) > 0)

    def test_mesh_critic_request_with_injected_executor(self):
        def mock_executor(prompt, proponent_node_id, proponent_model):
            return {
                "by": "node-omen:qwen",
                "content": "<think>ragiono</think>Obiezione sui consumi energetici e partizioni CAP.",
            }

        critic = MeshCritic(node_id="mac-hub", peer_executor_fn=mock_executor)
        result = critic.request_critique("Ipotesi sul calcolo quantistico distribuito.")
        self.assertIsNotNone(result)
        self.assertEqual(result["kind"], "critique")
        self.assertEqual(result["by"], "node-omen:qwen")
        self.assertIn("Obiezione sui consumi energetici", result["content"])
        self.assertNotIn("<think>", result["content"])

    def test_mesh_critic_fails_open_on_error(self):
        def failing_executor(prompt, proponent_node_id, proponent_model):
            raise TimeoutError("Node busy")

        critic = MeshCritic(node_id="mac-hub", peer_executor_fn=failing_executor)
        # Non deve sollevare eccezioni, restituisce None
        result = critic.request_critique("Ipotesi.")
        self.assertIsNone(result)


class TestMemoryEvidenceE4DreamJournalIntegration(unittest.TestCase):
    """Verifica l'integrazione di add_critique nel DreamJournal e la promozione."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.journal = DreamJournal(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dream_journal_add_critique_and_preservation_on_promote(self):
        # 1. Crea un sogno ipotesi
        dream_id = "dream-test-01"
        report = {
            "id": dream_id,
            "status": "hypothesis",
            "summary": "Ipotesi sui sogni ricorsivi.",
            "evidence": {"tier": PLAUSIBLE, "basis": []},
        }
        self.journal.append(report)

        # 2. Allega una critica del Red Team
        updated_dream = self.journal.add_critique(
            dream_id=dream_id,
            critique_by="node-omen:granite3.3:8b",
            content="Rischio di divergenza se il feedback loop non ha decadimento.",
        )
        self.assertEqual(updated_dream["evidence"]["tier"], PLAUSIBLE)
        self.assertEqual(len(updated_dream["evidence"]["basis"]), 1)
        self.assertEqual(updated_dream["evidence"]["basis"][0]["kind"], "critique")

        # 3. Promuove il sogno citando fonti (Fase E1 + E4)
        _, insight = self.journal.review(
            dream_id=dream_id,
            action="promote",
            reviewer="operatore_umano",
            rationale="Validato con esperimento pilota.",
            sources=["doc:experiment_wal_01"],
        )
        self.assertIsNotNone(insight)
        # Il tier è 'sourced' grazie alla review umana con fonti
        self.assertEqual(insight["evidence"]["tier"], SOURCED)

        # La base deve contenere SIA la review che la critica precedente!
        basis_kinds = [b["kind"] for b in insight["evidence"]["basis"]]
        self.assertIn("review", basis_kinds)
        self.assertIn("critique", basis_kinds)

        # La validazione del contratto deve passare al 100%
        errors = validate_evidence(insight["evidence"])
        self.assertEqual(errors, [])


class TestMemoryEvidenceE4ResearchEngineIntegration(unittest.TestCase):
    """Verifica l'allegato di critiche ai dossier di ricerca (AGIResearchEngine)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.engine = AGIResearchEngine(data_dir=self.data_dir)
        self.engine.prototypes_dir = self.data_dir / "prototypes"
        self.engine.prototypes_dir.mkdir(parents=True, exist_ok=True)
        self.engine.deep_dives_log = self.data_dir / "agi_deep_dives.jsonl"
        self.engine.synthesis_md = self.data_dir / "AGI_SWARM_SYNTHESIS.md"

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_dossier_critique_attaches_and_preserves_contract(self):
        # 1. Esegue uno studio
        record = self.engine.execute_study_cycle(pillar_id="aleksander_axioms")
        study_id = record["id"]

        # 2. Allega critica da nodo OMEN
        updated = self.engine.add_dossier_critique(
            study_id=study_id,
            critique_by="omen:granite3.3:8b",
            content="Manca analisi di robustezza in caso di saturazione memoria.",
        )
        self.assertIsNotNone(updated)
        ev = updated["evidence"]
        self.assertEqual(ev["tier"], PLAUSIBLE)
        self.assertEqual(len(ev["basis"]), 1)
        self.assertEqual(ev["basis"][0]["kind"], "critique")
        self.assertEqual(validate_evidence(ev), [])


class TestMemoryEvidenceE4OmegaQuery(unittest.TestCase):
    """Verifica la visualizzazione delle critiche Red Team in _omega_query."""

    def test_omega_query_displays_red_team_critiques(self):
        albero = ast.parse(cp_source.SORGENTE())
        nodi = [n for n in albero.body if isinstance(n, ast.FunctionDef)
                and n.name in ("_omega_query", "_omega_format_memories")]

        entry_with_critique = {
            "id": "mem-crit-1",
            "content": "Proposta di architettura a micro-servizi mesh",
            "type": "decision",
            "evidence": {
                "tier": PLAUSIBLE,
                "basis": [
                    {
                        "kind": "critique",
                        "by": "omen:granite",
                        "content": "Aumenta la superficie di attacco di rete e la latenza.",
                    }
                ],
            },
        }

        class FakeHermes:
            def query(self, query, limit, event_type, mode):
                return [entry_with_critique]

        ambiente = {
            "MEMORY_BACKEND": "hermes",
            "_hermes_memory": FakeHermes(),
            "HermesMemoryError": RuntimeError,
            "REFUTED": "refuted",
            "evidence_tier": evidence_tier,
            "_ts_to_iso": lambda value: str(value or ""),
        }
        exec(compile(ast.Module(body=nodi, type_ignores=[]), "cp", "exec"), ambiente)
        omega_query = ambiente["_omega_query"]

        testo = omega_query({"query": "micro-servizi"})
        self.assertIn("· plausible]", testo)
        self.assertIn("obiezioni red-team:", testo)
        self.assertIn("(omen:granite): Aumenta la superficie di attacco", testo)


if __name__ == "__main__":
    unittest.main()
