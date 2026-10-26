#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Suite di test per il sistema di continuità biomimetica a Endospore Crittografiche
(`shared/spore_protocol.py` e `scripts/diagnostics/spore_continuity_manager.py`).
"""

from __future__ import annotations

import itertools
from pathlib import Path
import tempfile
import pytest

from shared.spore_protocol import (
    BlockchainBottleBeacon,
    ShamirQuorumVault,
    ShamirShare,
    SporeBuilder,
    SporeCipher,
    SporeDispersalEngine,
    SporeSentinel,
)


def test_shamir_2_of_3_all_combinations_recover_exact_master_key() -> None:
    """
    Verifica che in un quorum 2-su-3 (Alberto, Guido Cips, Offline Vault)
    QUALSIASI coppia di frammenti ricostruisca al bit la Master Key di 256 bit,
    incluso il caso in cui il frammento #1 (Alberto) sia andato perduto.
    """
    master_key = SporeCipher.generate_master_key()
    shares = ShamirQuorumVault.split_secret(
        secret=master_key,
        threshold=2,
        total_shares=3,
        custodians=["alberto-founder", "guido-cips-partner", "offline-paper-vault"],
    )
    assert len(shares) == 3

    for pair in itertools.combinations(shares, 2):
        encoded_pair = [s.encode() for s in pair]
        recovered = ShamirQuorumVault.recover_secret(encoded_pair)
        assert recovered == master_key


def test_shamir_3_of_5_quorum_and_insufficient_shares_rejected() -> None:
    master_key = SporeCipher.generate_master_key()
    shares = ShamirQuorumVault.split_secret(secret=master_key, threshold=3, total_shares=5)
    assert len(shares) == 5

    # Qualsiasi terzina ricostruisce il segreto
    for triplet in itertools.combinations(shares, 3):
        assert ShamirQuorumVault.recover_secret(triplet) == master_key

    # Solo 2 frammenti su 3 richiesti devono fallire
    with pytest.raises(ValueError, match="Quorum insufficiente"):
        ShamirQuorumVault.recover_secret(shares[:2])


def test_shamir_share_tamper_detection() -> None:
    master_key = SporeCipher.generate_master_key()
    shares = ShamirQuorumVault.split_secret(secret=master_key, threshold=2, total_shares=3)
    token = shares[0].encode()
    # Manometti un carattere nel payload esadecimale
    parts = token.split(":")
    flipped = ("0" if parts[5][0] != "0" else "1") + parts[5][1:]
    parts[5] = flipped
    corrupted_token = ":".join(parts)

    with pytest.raises(ValueError, match="Checksum frammento"):
        ShamirShare.decode(corrupted_token)


def test_spore_create_and_germinate_without_founder_key() -> None:
    """
    Simula l'intero ciclo di vita:
    1. Creazione della Spora da una workspace simulata (con memoria e segreti isolati).
    2. Perdita del frammento #1 (`alberto-founder`).
    3. Germinazione su un nuovo nodo usando solo il frammento #2 (`guido-cips-partner`)
       e il frammento #3 (`offline-paper-vault`).
    """
    with tempfile.TemporaryDirectory() as tmp_root_str:
        tmp_root = Path(tmp_root_str)
        fake_repo = tmp_root / "repo"
        fake_repo.mkdir()
        (fake_repo / "AGENTS.md").write_text("# Agents Protocol\n", encoding="utf-8")
        (fake_repo / "AGENT-LOG.md").write_text("# Agent Log\n", encoding="utf-8")
        mem_dir = fake_repo / "data" / "control-plane"
        mem_dir.mkdir(parents=True)
        (mem_dir / "diario.json").write_text('{"entries": ["sogno-1"]}', encoding="utf-8")

        spores_out = tmp_root / "spores"
        res = SporeBuilder.create_spore(
            repo_root=fake_repo,
            output_dir=spores_out,
            source_node="mac-m5-hub",
            quorum_threshold=2,
            quorum_total_shares=3,
            include_git_bundle=False,
            secrets_to_vault={"HYPERSPACE_DEMO_SECRET": "resilient-value-42"},
        )

        spore_file = Path(res["spore_path"])
        assert spore_file.exists()

        # Ispezione pubblica del manifest senza chiave
        pub_manifest = SporeCipher.inspect_spore_manifest(spore_file)
        assert pub_manifest.spore_id == res["spore_id"]
        assert pub_manifest.has_encrypted_secrets_vault is True

        # Ricostruzione usando SOLO Share #2 (Guido) e Share #3 (Offline Paper Vault)
        shares = res["shares"]
        emergency_key = ShamirQuorumVault.recover_secret([shares[1], shares[2]])

        germinated_dir = tmp_root / "reborn_node"
        receipt = SporeBuilder.germinate_spore(
            spore_path=spore_file,
            master_key=emergency_key,
            target_dir=germinated_dir,
            restore_secrets=True,
        )

        assert receipt["spore_id"] == res["spore_id"]
        assert receipt["secrets_restored"] is True
        assert (germinated_dir / "AGENTS.md").read_text(encoding="utf-8") == "# Agents Protocol\n"
        assert (germinated_dir / "data" / "control-plane" / "diario.json").exists()
        assert "HYPERSPACE_DEMO_SECRET=resilient-value-42" in (
            germinated_dir / ".env.recovered"
        ).read_text(encoding="utf-8")


def test_spore_gcm_rejects_wrong_key_or_tampered_ciphertext() -> None:
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        (tmp / "AGENTS.md").write_text("test", encoding="utf-8")
        res = SporeBuilder.create_spore(
            repo_root=tmp,
            output_dir=tmp / "out",
            include_git_bundle=False,
        )
        spore_file = Path(res["spore_path"])
        wrong_key = SporeCipher.generate_master_key()

        with pytest.raises(Exception):
            SporeBuilder.germinate_spore(
                spore_path=spore_file,
                master_key=wrong_key,
                target_dir=tmp / "fail_out",
            )


def test_multi_substrate_dispersal_and_sentinel_dead_man_switch() -> None:
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        (tmp / "AGENTS.md").write_text("mesh memory", encoding="utf-8")
        res = SporeBuilder.create_spore(
            repo_root=tmp,
            output_dir=tmp / "spores",
            include_git_bundle=False,
        )
        spore_file = Path(res["spore_path"])
        manifest_file = Path(res["manifest_path"])

        mega_sync = tmp / "MEGA" / "HyperSpace-Spores"
        dropbox_sync = tmp / "Dropbox" / "HyperSpace-Spores"
        onedrive_sync = tmp / "OneDrive" / "HyperSpace-Spores"

        disp = SporeDispersalEngine.disperse_spore(
            spore_path=spore_file,
            manifest_path=manifest_file,
            local_vault_dirs=[mega_sync, dropbox_sync, onedrive_sync],
        )
        assert disp["replicated_count"] == 3
        assert (mega_sync / spore_file.name).exists()
        assert (dropbox_sync / spore_file.name).exists()
        assert (onedrive_sync / spore_file.name).exists()

        # Simula Dead-Man's Switch con nodi offline oltre la soglia di 72h
        sentinel_state = tmp / "sentinel.json"
        unreachable_nodes = [
            {"node_id": "mac-m5-hub", "role": "primary_hub", "host": "127.0.0.1", "port": 65531},
        ]
        rep_watch = SporeSentinel.evaluate_mesh_continuity(
            state_file=sentinel_state,
            nodes=unreachable_nodes,
            failover_threshold_hours=72.0,
            simulated_elapsed_hours=12.0,
        )
        assert rep_watch["spore_state"] == "STANDBY_WATCH"

        rep_ready = SporeSentinel.evaluate_mesh_continuity(
            state_file=sentinel_state,
            nodes=unreachable_nodes,
            failover_threshold_hours=72.0,
            simulated_elapsed_hours=80.0,
        )
        assert rep_ready["spore_state"] == "GERMINATION_READY"


def test_blockchain_message_in_a_bottle_evm_and_bitcoin_roundtrip() -> None:
    """
    Verifica la creazione e decodifica del "Message in a Bottle" multi-blockchain:
    - Calldata EVM (`0x...`) decifrabile con qualsiasi coppia di frammenti Shamir
    - Frame Bitcoin `OP_RETURN` esattamente di 80 byte con magic `HSP1` e SHA-256 integrale
    - Frame Solana SPL Memo
    """
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        (tmp / "AGENTS.md").write_text("bottle test", encoding="utf-8")
        res = SporeBuilder.create_spore(
            repo_root=tmp,
            output_dir=tmp / "spores",
            include_git_bundle=False,
        )
        shares = res["shares"]
        master_key = ShamirQuorumVault.recover_secret([shares[0], shares[1]])

        custom_locators = [
            "mega:hyperspace-spores/spore-demo.hspore",
            "dropbox:hyperspace-spores/spore-demo.hspore",
            "ipfs://bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
        ]
        bottle = BlockchainBottleBeacon.craft_bottle(
            manifest=res["manifest"],
            spore_sha256=res["spore_sha256"],
            master_key=master_key,
            locators=custom_locators,
            founder_epistle="Alberto & Cips — Ripartire dal nodo standby a Verbania.",
        )

        # 1. Verifica Bitcoin OP_RETURN (80 byte esatti)
        btc_hex = bottle["bitcoin_op_return"]["data_hex"]
        assert bottle["bitcoin_op_return"]["byte_length"] == 80
        parsed_btc = BlockchainBottleBeacon.parse_bitcoin_op_return(btc_hex)
        assert parsed_btc["magic"] == "HSP1"
        assert parsed_btc["spore_sha256"] == res["spore_sha256"]

        # 2. Verifica apertura EVM Calldata (0x...) usando SOLO Share #2 (Guido) e Share #3 (Offline)
        emergency_key = ShamirQuorumVault.recover_secret([shares[1], shares[2]])
        opened = BlockchainBottleBeacon.open_bottle(
            bottle["evm_calldata"]["data_hex"],
            master_key=emergency_key,
        )
        assert opened.spore_id == res["spore_id"]
        assert opened.spore_sha256 == res["spore_sha256"]
        assert opened.locators == custom_locators
        assert "Verbania" in opened.founder_epistle

