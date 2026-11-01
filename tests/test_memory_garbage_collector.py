#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""tests/test_memory_garbage_collector.py.

Suite di verifica per il Garbage Collector delle Allucinazioni (docs/memory-evidence-tiers.md):
1. Scadenza memorie plausible di retention 'project' inattive (access_count == 0, age >= 14d).
2. Protezione ferrea di memorie persistenti, curated (MEMORY.md) e profilo utente (USER.md).
3. Conservazione di memorie consultate (access_count > 0) e recenti (< 14d).
4. Rilevamento collisioni tra ipotesi attive e claim smentiti (refuted) o sogni rifiutati (token_overlap >= 0.8).
5. Ricontrollo a campione dei check deterministici verified: conferma tier se passano, declassamento a plausible se falliscono.
6. Invarianti inviolabili: mai cancellare refuted, mai alzare livelli, mai toccare MEMORY.md o USER.md.
7. Comportamento dry-run vs apply e azione bridge 'downgrade'.
"""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from shared.hermes_memory import HermesMemoryClient
from shared.memory_gc import (
    DEFAULT_REFUTE_OVERLAP_THRESHOLD,
    DEFAULT_UNACCESSED_DAYS,
    MemoryGarbageCollector,
    audit_single_verified_check,
    audit_verified_entries,
    find_expired_plausible_entries,
    find_refuted_collisions,
)
from shared.memory_schema import (
    PERSISTENT,
    PLAUSIBLE,
    PROJECT,
    REFUTED,
    SOURCED,
    VERIFIED,
    evidence_tier,
    validate_entry,
)


class TestMemoryGarbageCollector(unittest.TestCase):
    """Test suite per il modulo shared/memory_gc.py."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.now = 1730455200.0  # Timestamp fisso per test deterministici

    def tearDown(self):
        self.tmp.cleanup()

    def test_expired_plausible_candidate_detection(self):
        """Record plausible di progetto, non consultato e vecchio di 20 giorni va in quarantena."""
        old_epoch = self.now - (20 * 86400.0)
        entries = [
            {
                "id": "exp-1",
                "type": "memory",
                "retention": PROJECT,
                "content": "ipotesi teorica mai verificata né letta",
                "status": "active",
                "access_count": 0,
                "timestamp": old_epoch,
                "evidence": {"tier": PLAUSIBLE, "basis": []},
            }
        ]
        candidates = find_expired_plausible_entries(entries, days_unaccessed=14, now_epoch=self.now)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["id"], "exp-1")
        self.assertEqual(candidates[0]["action"], "quarantine")
        self.assertIn("mai consultato da 20.0 giorni", candidates[0]["reason"])

    def test_persistent_and_curated_memories_are_never_expired(self):
        """Memorie persistenti, note del vault, MEMORY.md e profilo utente non scadono MAI."""
        old_epoch = self.now - (50 * 86400.0)
        entries = [
            {
                "id": "pers-1",
                "type": "dream_insight",  # Persistente di default
                "content": "insight fondamentale sul sistema mesh",
                "status": "active",
                "access_count": 0,
                "timestamp": old_epoch,
            },
            {
                "id": "pers-2",
                "type": "note",
                "retention": PERSISTENT,  # Esplicitamente persistente
                "content": "appunto permanente",
                "status": "active",
                "access_count": 0,
                "timestamp": old_epoch,
            },
            {
                "id": "curated-1",
                "content": "preferenza dell'operatore per fan profile",
                "curated_target": "memory",
                "status": "active",
                "access_count": 0,
                "timestamp": old_epoch,
            },
            {
                "id": "user-1",
                "type": "user_profile",
                "content": "utente preferisce risposte concise in markdown",
                "status": "active",
                "access_count": 0,
                "timestamp": old_epoch,
            },
        ]
        candidates = find_expired_plausible_entries(entries, days_unaccessed=14, now_epoch=self.now)
        self.assertEqual(candidates, [], "Nessun record persistente o utente deve essere candidato alla quarantena!")

    def test_accessed_or_young_plausible_not_expired(self):
        """Memorie consultate (access_count > 0) o recenti (< 14d) non devono scadere."""
        old_epoch = self.now - (20 * 86400.0)
        recent_epoch = self.now - (5 * 86400.0)
        entries = [
            {
                "id": "accessed-1",
                "retention": PROJECT,
                "content": "ipotesi consultata 3 volte dall'agente",
                "status": "active",
                "access_count": 3,
                "timestamp": old_epoch,
            },
            {
                "id": "recent-1",
                "retention": PROJECT,
                "content": "ipotesi generata ieri sera",
                "status": "active",
                "access_count": 0,
                "timestamp": recent_epoch,
            },
        ]
        candidates = find_expired_plausible_entries(entries, days_unaccessed=14, now_epoch=self.now)
        self.assertEqual(candidates, [])

    def test_verified_and_sourced_memories_do_not_expire(self):
        """Memorie con tier verified o sourced non scadono anche se inattive da tempo."""
        old_epoch = self.now - (60 * 86400.0)
        entries = [
            {
                "id": "ver-1",
                "retention": PROJECT,
                "content": "algoritmo validato con test",
                "status": "active",
                "access_count": 0,
                "timestamp": old_epoch,
                "evidence": {
                    "tier": VERIFIED,
                    "basis": [{
                        "kind": "check",
                        "command": "pytest -q",
                        "exit_code": 0,
                        "output_sha256": "0" * 64,
                        "at": "2026-10-01T10:00:00Z"
                    }]
                }
            },
            {
                "id": "src-1",
                "retention": PROJECT,
                "content": "fatto tratto dalla documentazione",
                "status": "active",
                "access_count": 0,
                "timestamp": old_epoch,
                "evidence": {
                    "tier": SOURCED,
                    "basis": [{
                        "kind": "source",
                        "ref": "docs/hermes.md",
                        "content_sha256": "a" * 64
                    }]
                }
            }
        ]
        candidates = find_expired_plausible_entries(entries, days_unaccessed=14, now_epoch=self.now)
        self.assertEqual(candidates, [])

    def test_refuted_collision_detection(self):
        """Rileva collisione con memoria marcata 'refuted' e la candida per la quarantena."""
        refuted_entry = {
            "id": "ref-omen-1",
            "content": "OMEN supporta due slot di inferenza concorrente Ollama su Windows",
            "status": "active",
            "evidence": {
                "tier": REFUTED,
                "basis": [{"kind": "refutation", "reason": "node/main.py impone OLLAMA_NUM_PARALLEL=1", "at": "2026-10-20T10:00:00Z"}],
            },
            "lifecycle": {"action": "refute", "reason": "node/main.py impone OLLAMA_NUM_PARALLEL=1"}
        }

        active_entries = [
            {
                "id": "new-dream-dup",
                "content": "OMEN supporta due slot di inferenza concorrente Ollama su Windows!",
                "status": "active",
                "evidence": {"tier": PLAUSIBLE, "basis": []}
            },
            {
                "id": "legit-different-claim",
                "content": "La cache Voicebox Kokoro su M5 ottimizza la latenza di sintesi vocale",
                "status": "active",
                "evidence": {"tier": PLAUSIBLE, "basis": []}
            }
        ]

        collisions = find_refuted_collisions(active_entries, refuted_entries=[refuted_entry], threshold=0.8)
        self.assertEqual(len(collisions), 1)
        self.assertEqual(collisions[0]["id"], "new-dream-dup")
        self.assertEqual(collisions[0]["refuted_id"], "ref-omen-1")
        self.assertGreaterEqual(collisions[0]["overlap_score"], 0.8)
        self.assertIn("sovrapposizione", collisions[0]["reason"])

    def test_collision_with_rejected_dreams_file(self):
        """Rileva collisione leggendo dal file dream_rejected.jsonl."""
        rejected_file = self.tmp_path / "dream_rejected.jsonl"
        rejected_file.write_text(
            json.dumps({
                "dream_id": "dream-rejected-42",
                "summary": "integrare redis come message broker per la mesh dei nodi",
                "action": "reject",
                "reason": "rifiutato: sovrastruttura non necessaria per 4 nodi"
            }) + "\n",
            encoding="utf-8"
        )

        active_entries = [
            {
                "id": "candidate-dream",
                "content": "integrare redis come message broker per la mesh dei nodi",
                "status": "active",
                "evidence": {"tier": PLAUSIBLE, "basis": []}
            }
        ]

        collisions = find_refuted_collisions(
            active_entries,
            rejected_dreams=None,
            refuted_entries=[],
            threshold=0.8
        )
        # Se chiamato con rejected_dreams_path o caricamento esplicito:
        gc = MemoryGarbageCollector(rejected_dreams_path=rejected_file)
        report = gc.run_gc(entries=active_entries, dry_run=True, audit_verified=False)
        self.assertEqual(report["quarantined_collision_count"], 1)
        self.assertEqual(report["collision_candidates"][0]["refuted_id"], "dream-rejected-42")

    @patch("subprocess.run")
    def test_audit_verified_check_pass(self, mock_run):
        """Un check deterministico che restituisce exit_code 0 conferma lo stato verified."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "15 passed in 0.12s\n"
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        verified_entry = {
            "id": "verified-module-1",
            "content": "modulo prototipo validato",
            "status": "active",
            "evidence": {
                "tier": VERIFIED,
                "basis": [{
                    "kind": "check",
                    "command": "pytest tests/test_hermes_memory.py -q",
                    "exit_code": 0,
                    "output_sha256": "0" * 64,
                    "at": "2026-10-30T10:00:00Z"
                }]
            }
        }

        res = audit_single_verified_check(verified_entry, repo_root=self.tmp_path)
        self.assertFalse(res["downgrade_needed"])
        self.assertEqual(res["checks_passed"], 1)
        self.assertEqual(res["checks_failed"], 0)

    @patch("subprocess.run")
    def test_audit_verified_check_fail_triggers_downgrade(self, mock_run):
        """Un check deterministico che fallisce (exit_code != 0) richiede il declassamento a plausible."""
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = "FAILED tests/test_broken.py::test_foo\n"
        mock_proc.stderr = "AssertionError: regression occurred\n"
        mock_run.return_value = mock_proc

        verified_entry = {
            "id": "verified-broken-1",
            "content": "modulo che ora fallisce i test",
            "status": "active",
            "evidence": {
                "tier": VERIFIED,
                "basis": [{
                    "kind": "check",
                    "command": "pytest tests/test_broken.py -q",
                    "exit_code": 0,
                    "output_sha256": "0" * 64,
                    "at": "2026-10-30T10:00:00Z"
                }]
            }
        }

        res = audit_single_verified_check(verified_entry, repo_root=self.tmp_path)
        self.assertTrue(res["downgrade_needed"])
        self.assertEqual(res["checks_passed"], 0)
        self.assertEqual(res["checks_failed"], 1)
        self.assertIn("Ricontrollo GC: 1 check deterministici falliti", res["reason"])

    def test_inviolable_safety_guarantees(self):
        """Verifica che tutte le garanzie di sicurezza epistemica siano rispettate."""
        gc = MemoryGarbageCollector()
        report = gc.run_gc(entries=[], dry_run=True, audit_verified=False)
        self.assertTrue(report["ok"])
        guarantees = report["guarantees"]
        self.assertTrue(guarantees["never_deleted_refuted"])
        self.assertTrue(guarantees["never_raised_tier"])
        self.assertTrue(guarantees["never_touched_curated_memory"])
        self.assertTrue(guarantees["never_touched_user_profile"])

    def test_dry_run_vs_apply_execution(self):
        """In dry-run non chiama lifecycle; con dry_run=False invoca lifecycle."""
        mock_client = MagicMock(spec=HermesMemoryClient)
        mock_client.lifecycle.return_value = {"ok": True, "changed": ["exp-1"]}

        old_epoch = self.now - (30 * 86400.0)
        entries = [
            {
                "id": "exp-1",
                "retention": PROJECT,
                "content": "vecchia memoria non consultata",
                "status": "active",
                "access_count": 0,
                "timestamp": old_epoch,
                "evidence": {"tier": PLAUSIBLE, "basis": []}
            }
        ]

        gc = MemoryGarbageCollector(client=mock_client)

        # 1. Dry run
        report_dry = gc.run_gc(entries=entries, dry_run=True, audit_verified=False)
        self.assertTrue(report_dry["dry_run"])
        self.assertEqual(report_dry["quarantined_expired_count"], 1)
        self.assertEqual(report_dry["quarantined_applied"], [])
        mock_client.lifecycle.assert_not_called()

        # 2. Apply execution
        report_apply = gc.run_gc(entries=entries, dry_run=False, audit_verified=False)
        self.assertFalse(report_apply["dry_run"])
        self.assertEqual(report_apply["quarantined_applied"], ["exp-1"])
        mock_client.lifecycle.assert_called_once_with(["exp-1"], "quarantine", reason=report_dry["expired_candidates"][0]["reason"])

    def test_hermes_bridge_downgrade_action(self):
        """Testa l'azione di ciclo di vita 'downgrade' sul bridge Hermes."""
        from tests.test_hermes_memory import FakeDB, load_bridge_module

        bridge = load_bridge_module()
        memory = bridge.HermesMemory(FakeDB())

        verified_entry = {
            "id": "claim-downgrade-1",
            "content": "algoritmo con check verificato",
            "evidence": {
                "tier": VERIFIED,
                "basis": [{
                    "kind": "check",
                    "command": "pytest test.py",
                    "exit_code": 0,
                    "output_sha256": "1" * 64,
                    "at": "2026-10-31T12:00:00Z"
                }],
                "assigned_by": "test_promoter",
            }
        }
        memory.store(verified_entry)
        stored_entry = memory.entries()[0]
        self.assertEqual(evidence_tier(stored_entry), VERIFIED)

        # Esecuzione downgrade da GC
        res = memory.lifecycle(["claim-downgrade-1"], "downgrade", reason="Check deterministico fallito nel test di regressione")
        self.assertEqual(res["changed"], ["claim-downgrade-1"])

        updated_entry = memory.entries()[0]
        self.assertEqual(evidence_tier(updated_entry), PLAUSIBLE)
        self.assertEqual(updated_entry.get("status", "active"), "active")
        # Il check deterministico è stato rimosso dalla basis
        self.assertEqual(len(updated_entry["evidence"]["basis"]), 0)
        # La storia contiene la transizione da verified a plausible
        hist = updated_entry["evidence"]["history"]
        self.assertEqual(hist[-1]["from"], VERIFIED)
        self.assertEqual(hist[-1]["to"], PLAUSIBLE)
        self.assertEqual(hist[-1]["by"], "garbage_collector")
        # Entry conforme al validatore di memory_schema
        self.assertEqual(validate_entry(updated_entry), [])


if __name__ == "__main__":
    unittest.main()
