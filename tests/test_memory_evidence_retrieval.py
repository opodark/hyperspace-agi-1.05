# SPDX-License-Identifier: Apache-2.0
"""Il livello di evidenza arriva all'agente, e i ricordi smentiti restano fuori.

`_omega_query` e `_omega_format_memories` sono estratte dal VERO control-plane con
`ast` (la tecnica di `tests/test_tool_passthrough.py`) ed eseguite contro una
memoria finta: nessun Flask, nessuna rete. Design: docs/memory-evidence-tiers.md.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.memory_schema import REFUTED, evidence_tier  # noqa: E402
from tests import cp_source  # noqa: E402

REFUTATION = {"tier": "refuted", "basis": [{"kind": "refutation", "reason": "smentita"}]}
SOURCED = {"tier": "sourced", "basis": [{"kind": "review", "by": "alice", "sources": ["m-1"]}]}


class FakeHermes:
    def __init__(self, entries):
        self.entries, self.limits = entries, []

    def query(self, query, limit, event_type, mode):
        self.limits.append(limit)
        return list(self.entries)[:limit]


def _carica(entries):
    albero = ast.parse(cp_source.SORGENTE())
    nodi = [n for n in albero.body if isinstance(n, ast.FunctionDef)
            and n.name in ("_omega_query", "_omega_format_memories")]
    hermes = FakeHermes(entries)
    ambiente = {
        "MEMORY_BACKEND": "hermes", "_hermes_memory": hermes,
        "HermesMemoryError": RuntimeError, "REFUTED": REFUTED,
        "evidence_tier": evidence_tier, "_ts_to_iso": lambda value: str(value or ""),
    }
    exec(compile(ast.Module(body=nodi, type_ignores=[]), "cp", "exec"), ambiente)
    return ambiente["_omega_query"], hermes


class OmegaQueryEvidenceTests(unittest.TestCase):
    ENTRIES = [
        {"id": "a", "content": "slot ollama: uno solo", "evidence": SOURCED},
        {"id": "b", "content": "slot ollama: due", "evidence": REFUTATION},
        {"id": "c", "content": "slot ollama: forse tre"},
    ]

    def test_la_ricerca_normale_mostra_il_livello_e_nasconde_i_smentiti(self):
        omega_query, _ = _carica(self.ENTRIES)
        testo = omega_query({"query": "slot ollama"})
        self.assertIn("· sourced]", testo)
        self.assertIn("· plausible]", testo)
        self.assertNotIn("due", testo)

    def test_la_domanda_esplicita_trova_solo_i_smentiti_con_il_bacino_largo(self):
        omega_query, hermes = _carica(self.ENTRIES)
        testo = omega_query({"query": "slot ollama", "limit": 2, "evidence": "refuted"})
        self.assertIn("· refuted]", testo)
        self.assertNotIn("uno solo", testo)
        self.assertEqual(hermes.limits, [100])

    def test_un_refuted_senza_motivo_non_vale_come_smentita(self):
        omega_query, _ = _carica([{"id": "x", "content": "ipotesi", "evidence": {"tier": "refuted"}}])
        self.assertIn("· plausible]", omega_query({"query": "ipotesi"}))


if __name__ == "__main__":
    unittest.main()
