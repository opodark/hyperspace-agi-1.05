# SPDX-License-Identifier: Apache-2.0
"""Test suite per la Tokenomics, Node Rewards e pump.fun Snapshot di HyperSpace."""

import uuid

import pytest

from shared import db, tokenomics


def test_calculate_task_reward_multipliers():
    # Modello leggero
    r_light = tokenomics.calculate_task_reward(model="qwen3.5:4b")
    assert r_light == 2.0

    # Modello medio (7B-9B)
    r_med = tokenomics.calculate_task_reward(model="qwen3:8b")
    assert r_med == 3.0

    # Modello pesante / quantizzazione ternaria / MoE
    r_bonsai = tokenomics.calculate_task_reward(model="Ternary-Bonsai-2-27B")
    assert r_bonsai == 6.0

    # Con bonus durata (>5s)
    r_dur = tokenomics.calculate_task_reward(model="qwen3:8b", duration_s=10.0)
    assert r_dur > 3.0


def test_solana_address_validation():
    # Indirizzi Base58 validi (32-44 caratteri base58)
    assert tokenomics.validate_solana_address("7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU") is True
    assert tokenomics.validate_solana_address("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v") is True

    # Indirizzi invalidi
    assert tokenomics.validate_solana_address("invalid-address") is False
    assert tokenomics.validate_solana_address("") is False
    assert tokenomics.validate_solana_address("0x1234567890abcdef1234567890abcdef12345678") is False  # Ethereum address, non Solana


def test_node_join_and_double_reward_prevention():
    test_node = f"test-node-alpha-{uuid.uuid4().hex[:8]}"

    # Primo join: successo
    res1 = tokenomics.reward_node_join(test_node, tier="leaf")
    assert res1["ok"] is True
    assert res1["reward"] == 50.0

    wallet = db.get_token_wallet(test_node)
    assert wallet is not None
    assert wallet["balance"] >= 50.0

    # Secondo join: deve essere respinto senza accreditare doppio bonus (anti double-claim)
    res2 = tokenomics.reward_node_join(test_node, tier="leaf")
    assert res2["ok"] is False
    assert res2["reason"] == "join_already_rewarded"


def test_task_reward_and_transaction_audit():
    test_node = f"test-node-worker-{uuid.uuid4().hex[:8]}"
    task_id = f"task-audit-{uuid.uuid4().hex[:8]}"

    res = tokenomics.reward_task_completion(test_node, task_id, model="granite3.3:8b", duration_s=2.0)
    assert res["ok"] is True
    assert res["reward"] == 3.0

    wallet = db.get_token_wallet(test_node)
    assert wallet["tasks_completed"] >= 1
    assert wallet["balance"] >= 3.0

    txs = db.list_token_transactions(node_id=test_node, limit=10)
    assert len(txs) >= 1
    assert txs[0]["type"] == "task_reward"
    assert txs[0]["reference_id"] == task_id


def test_solana_wallet_linking():
    test_node = "test-node-solana-01"
    sol_addr = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"

    # Link valido
    link_res = tokenomics.link_node_solana_wallet(test_node, sol_addr)
    assert link_res["ok"] is True
    assert link_res["solana_address"] == sol_addr

    wallet = db.get_token_wallet(test_node)
    assert wallet["solana_address"] == sol_addr

    # Link con indirizzo errato
    bad_res = tokenomics.link_node_solana_wallet(test_node, "non_un_indirizzo_solana")
    assert bad_res["ok"] is False


def test_pumpfun_snapshot_allocation():
    # Verifica che lo snapshot calcoli le quote corrette
    snapshot = tokenomics.export_pumpfun_snapshot(pool_allocation=1_000_000.0)
    assert snapshot["token_symbol"] == "$00MESH"
    assert "allocations" in snapshot
    assert snapshot["pool_allocation_total"] == 1_000_000.0

    # Se ci sono nodi con guadagni, la somma delle percentuali deve essere vicina al 100%
    if snapshot["allocations"]:
        tot_pct = sum(a["share_percentage"] for a in snapshot["allocations"])
        assert 99.0 <= tot_pct <= 101.0


@pytest.fixture(autouse=True)
def _cleanup_test_wallets():
    yield
    db.delete_test_token_wallets()


def test_solana_wallet_anti_farming_and_hijacking():
    import secrets
    b58_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    uid = "".join(secrets.choice(b58_chars) for _ in range(8))
    test_node_a = f"test-node-farm-{uid}-a"
    test_node_b = f"test-node-farm-{uid}-b"
    sol_addr = "9xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRu"[:34] + uid

    # Primo nodo riceve il welcome bonus
    res_a = tokenomics.link_node_solana_wallet(test_node_a, sol_addr)
    assert res_a["ok"] is True
    assert res_a["bonus_granted"] is True

    # Secondo nodo con STESSO indirizzo Solana non riceve un secondo bonus
    res_b = tokenomics.link_node_solana_wallet(test_node_b, sol_addr)
    assert res_b["ok"] is True
    assert res_b["bonus_granted"] is False
    assert res_b["join_reward"] is None

    # Anti-hijacking: tentativo di sovrascrivere l'indirizzo del nodo A con un altro indirizzo viene respinto
    other_addr = "8xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsW"
    hijack_res = tokenomics.link_node_solana_wallet(test_node_a, other_addr)
    assert hijack_res["ok"] is False
    assert "già associato" in hijack_res["error"]


def test_mandatory_ed25519_signature_and_leaderboard_masking():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    priv = Ed25519PrivateKey.generate()
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    sol_addr = tokenomics.b58encode(pub_bytes)
    node_id = f"test-node-sig-{uuid.uuid4().hex[:8]}"
    ts = "1729180000"

    # Senza firma con require_signature=True deve fallire
    unsigned = tokenomics.link_node_solana_wallet(node_id, sol_addr, require_signature=True)
    assert unsigned["ok"] is False
    assert "obbligatoria" in unsigned["error"]

    # Con firma valida Ed25519 deve passare
    msg = f"00MESH-auth:{node_id}:{ts}".encode("utf-8")
    sig_b58 = tokenomics.b58encode(priv.sign(msg))
    signed = tokenomics.link_node_solana_wallet(
        node_id, sol_addr, signature=sig_b58, timestamp=ts, require_signature=True
    )
    assert signed["ok"] is True

    # Mascheramento indirizzo Solana
    masked = tokenomics.mask_solana_address(sol_addr)
    assert masked == f"{sol_addr[:4]}...{sol_addr[-4:]}"
    assert len(masked) < len(sol_addr)

    # La classifica pubblica esclude i test-node-*
    board = tokenomics.get_tokenomics_leaderboard(limit=100)
    assert all(not item["node_id"].startswith("test-node-") for item in board)
    for item in board:
        if item.get("solana_address"):
            assert "..." in item["solana_address"]

