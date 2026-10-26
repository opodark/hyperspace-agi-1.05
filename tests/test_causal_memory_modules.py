# SPDX-License-Identifier: Apache-2.0
"""
Test unitari per i moduli R&D di Memoria Causale e Distribuita promossi in shared/:
1. SovereignModularIntellect (shared/modular_intellect.py)
2. VectorClockStateReplication (shared/vector_clock_replication.py)
3. SemanticMemoryDecayController (shared/semantic_memory_decay.py)
"""

import math
import pytest


def test_sovereign_modular_intellect():
    pytest.importorskip("shared.modular_intellect")
    from shared.modular_intellect import SovereignModularIntellect

    mem = SovereignModularIntellect()

    # 1. Memorizzazione interazione
    act_id = mem.store_experience(kind="interaction", content="Comando di analisi architettura causale")
    assert act_id == 0

    # 2. Memorizzazione documento
    doc_id = mem.store_experience(kind="document", content="Specifiche RFC-0044 checkpoint WAL")
    # Collega il documento con legame strutturale
    mem.experiences[doc_id]["parent_id"] = act_id
    assert mem.experiences[doc_id]["parent_id"] == 0

    # 3. Creazione nota ricorsiva
    note_id = mem.create_recursive_note(parent_note_id=doc_id, content="Riflessione: integrare SQLite WAL con vector clocks")
    assert note_id == 2
    assert mem.experiences[note_id]["refs"] == [doc_id]

    # 4. Traversal a grafo BFS
    traversed = mem.traverse_graph_context(query="Specifiche", max_hops=2)
    assert len(traversed) >= 1
    found_ids = [e["id"] for e in traversed]
    assert doc_id in found_ids

    # 5. Verifica Alignment Auditor
    # Nota senza referenze -> violazione
    invalid_note_id = mem.store_experience(kind="note", content="Nota orfana senza citazione", refs=[])
    audit = mem.get_audit_log()
    invalid_entry = [entry for entry in audit if entry["id"] == invalid_note_id][0]
    assert invalid_entry["aligned"] is False
    assert invalid_entry["violation"] is True


def test_vector_clock_state_replication():
    pytest.importorskip("shared.vector_clock_replication")
    from shared.vector_clock_replication import VectorClockStateReplication

    node_mac = VectorClockStateReplication(node_id="mac-m5")
    node_omen = VectorClockStateReplication(node_id="omen-16")
    node_asus = VectorClockStateReplication(node_id="asus-v16")

    # 1. Applicazione stato locale Mac
    node_mac.apply({"active_mission": "rd_causal_mesh", "status": "running"})
    assert node_mac.get_vector_clock() == {"mac-m5": 1}
    assert node_mac.get_state()["active_mission"] == "rd_causal_mesh"

    # 2. Applicazione stato OMEN
    node_omen.apply({"last_checkpoint_wal": "wal_0044_ckpt_9", "gpu_vram_free_mb": 6144})
    assert node_omen.get_vector_clock() == {"omen-16": 1}

    # 3. Merge tra Mac e OMEN
    node_mac.merge(node_omen)
    clock_mac = node_mac.get_vector_clock()
    assert clock_mac["mac-m5"] == 1
    assert clock_mac["omen-16"] == 1

    # 4. Mutazione successiva su OMEN e propagazione ad ASUS
    node_omen.apply({"gpu_vram_free_mb": 5800})
    assert node_omen.get_vector_clock()["omen-16"] == 2

    node_asus.merge(node_mac)
    node_asus.merge(node_omen)
    clock_asus = node_asus.get_vector_clock()
    assert clock_asus["mac-m5"] == 1
    assert clock_asus["omen-16"] == 2


def test_semantic_memory_decay_controller():
    pytest.importorskip("shared.semantic_memory_decay")
    from shared.semantic_memory_decay import SemanticMemoryDecayController

    controller = SemanticMemoryDecayController(base=1.0, alpha=0.5, beta=0.2)

    item_urgent = "concept:distributed_consensus"
    item_transient = "temp:latency_probe_23"

    # 1. Assegna salienza
    controller.update_salience(item_urgent, value=3.0)
    controller.update_salience(item_transient, value=0.1)

    # 2. Registra richiami
    for _ in range(5):
        controller.record_recall(item_urgent)

    rate_urgent = controller.get_decay_rate(item_urgent)
    rate_transient = controller.get_decay_rate(item_transient)

    # Verifica formula esponenziale: base * exp(-alpha * sal + beta * rec)
    expected_urgent = 1.0 * math.exp(-0.5 * 3.0 + 0.2 * 5)
    assert math.isclose(rate_urgent, expected_urgent, rel_tol=1e-5)

    expected_transient = 1.0 * math.exp(-0.5 * 0.1 + 0.2 * 0)
    assert math.isclose(rate_transient, expected_transient, rel_tol=1e-5)

    # Verifica salienza
    controller.update_salience("test_item", 2.0)
    assert controller.salience["test_item"] == 2.0
    assert controller.recall_freq.get("test_item", 0) == 0
