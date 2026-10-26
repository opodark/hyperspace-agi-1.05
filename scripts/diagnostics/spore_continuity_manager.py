#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
HyperSpace Bio-Mimetic Spore Continuity Manager & Diagnostic Tool
(`scripts/diagnostics/spore_continuity_manager.py`)

Perimetro operativo:
- Modalità predefinita (SOLA LETTURA): ispeziona i substrati di dispersione
  (MEGA, Dropbox, OneDrive via `rclone` e cartelle sync locali), controlla lo
  stato della Sentinella di Continuità (Dead-Man's Switch) sui nodi della Mesh
  (Mac M5, HP OMEN 16, ASUS V16) e verifica l'integrità dei manifest delle Spore
  esistenti in `data/spores/`.
- Modalità mutanti (richiedono flag esplicito):
  - `--create-spore`: genera una nuova Spora crittografata AES-256-GCM (`.hspore`)
    contenente Git bundle + memoria Hermes + SQLite + bootstrap script e divide
    la Master Key in un Quorum di Shamir (es. 2-su-3 tra Alberto, Guido "Cips"
    e Recovery Kit Offline). Salva i frammenti in un file protetto (`chmod 600`)
    sotto `data/spores/` senza mai stamparli in chiaro nei log.
  - `--disperse <spore.hspore>`: replica la capsula cifrata verso i remote `rclone`
    (MEGA, Dropbox, OneDrive) o cartelle sync specificate.
  - `--verify-germination <spore.hspore>`: esegue un test completo end-to-end
    di ricostruzione del Quorum Shamir e germinazione in una sandbox temporanea.

Uso:
    .venv/bin/python scripts/diagnostics/spore_continuity_manager.py
    .venv/bin/python scripts/diagnostics/spore_continuity_manager.py --create-spore --verify-roundtrip
    .venv/bin/python scripts/diagnostics/spore_continuity_manager.py --disperse data/spores/<id>.hspore --rclone-remote mega:hyperspace-spores
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.spore_protocol import (
    BlockchainBottleBeacon,
    ShamirQuorumVault,
    SporeBuilder,
    SporeCipher,
    SporeDispersalEngine,
    SporeSentinel,
)


def _redact_share(share_str: str) -> str:
    """Redige il payload esadecimale del frammento Shamir per l'output a schermo."""
    parts = share_str.split(":")
    if len(parts) != 7:
        return "<REDACTED-SHARE>"
    prefix, idx, thr, tot, custodian, payload, crc = parts
    masked_payload = f"{payload[:4]}...{payload[-4:]}" if len(payload) > 8 else "****"
    return f"{prefix}:{idx}:{thr}:{tot}:{custodian}:{masked_payload}:{crc}"


def list_existing_spores(spores_dir: Path) -> List[Dict[str, Any]]:
    if not spores_dir.exists():
        return []
    out: List[Dict[str, Any]] = []
    for f in sorted(spores_dir.glob("*.hspore")):
        try:
            manifest = SporeCipher.inspect_spore_manifest(f)
            out.append({
                "spore_id": manifest.spore_id,
                "file": str(f.relative_to(REPO_ROOT)) if str(f).startswith(str(REPO_ROOT)) else str(f),
                "created_at": manifest.created_at,
                "git_head_commit": manifest.git_head_commit[:12],
                "quorum": f"{manifest.quorum_threshold}-of-{manifest.quorum_total_shares}",
                "custodians": manifest.custodians,
                "components_count": len(manifest.included_components),
                "size_bytes": f.stat().st_size,
                "valid_header": True,
            })
        except Exception as exc:
            out.append({
                "file": str(f),
                "valid_header": False,
                "error": str(exc),
            })
    return out


def run_diagnostic_report(
    spores_dir: Path,
    sentinel_state_file: Path,
    failover_hours: float,
) -> Dict[str, Any]:
    substrates = [asdict(s) for s in SporeDispersalEngine.discover_substrates()]
    sentinel = SporeSentinel.evaluate_mesh_continuity(
        state_file=sentinel_state_file,
        failover_threshold_hours=failover_hours,
    )
    existing_spores = list_existing_spores(spores_dir)
    return {
        "status": "ok",
        "mode": "read_only_diagnostic",
        "sentinel": sentinel,
        "substrates": substrates,
        "spores_vault_dir": str(spores_dir),
        "existing_spores_count": len(existing_spores),
        "existing_spores": existing_spores,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="HyperSpace Bio-Mimetic Spore Continuity Manager & Diagnostic"
    )
    parser.add_argument(
        "--spores-dir",
        default=str(REPO_ROOT / "data" / "spores"),
        help="Directory locale delle capsule .hspore (default: data/spores)",
    )
    parser.add_argument(
        "--failover-hours",
        type=float,
        default=72.0,
        help="Finestra Dead-Man's Switch in ore prima di GERMINATION_READY (default: 72.0)",
    )
    parser.add_argument(
        "--create-spore",
        action="store_true",
        help="[MUTANTE] Crea una nuova Spora crittografata (.hspore) e il Quorum Kit di Shamir",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=2,
        help="Soglia K del Quorum di Shamir (default: 2)",
    )
    parser.add_argument(
        "--total-shares",
        type=int,
        default=3,
        help="Totale N frammenti del Quorum di Shamir (default: 3)",
    )
    parser.add_argument(
        "--verify-roundtrip",
        action="store_true",
        help="Verifica immediatamente la germinazione della Spora con 2 frammenti in una directory temporanea",
    )
    parser.add_argument(
        "--disperse",
        metavar="SPORE_PATH",
        help="[MUTANTE] Replica un file .hspore esistente sui substrati indicati",
    )
    parser.add_argument(
        "--rclone-remote",
        action="append",
        default=[],
        help="Remote rclone di destinazione (es. mega:hyperspace-spores, dropbox:hyperspace-spores, onedrive:hyperspace-spores)",
    )
    parser.add_argument(
        "--local-vault",
        action="append",
        default=[],
        help="Cartella locale sincronizzata (es. ~/MEGA/HyperSpace-Spores)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la dispersione senza copiare file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Stampa il report in formato JSON sintetico",
    )
    args = parser.parse_args()

    spores_dir = Path(args.spores_dir).resolve()
    sentinel_state_file = spores_dir / "sentinel_state.json"

    output_payload: Dict[str, Any] = {}

    if args.create_spore:
        created = SporeBuilder.create_spore(
            repo_root=REPO_ROOT,
            output_dir=spores_dir,
            source_node="mac-m5-hub",
            quorum_threshold=args.threshold,
            quorum_total_shares=args.total_shares,
            custodians=["alberto-founder", "guido-cips-partner", "offline-paper-vault"]
            if args.total_shares == 3
            else None,
            include_git_bundle=True,
        )
        spore_id = created["spore_id"]
        # Salva il Quorum Recovery Kit in un file locale con permessi 0600 (gitignored sotto data/)
        kit_path = spores_dir / f"{spore_id}.quorum-kit.secret.json"
        kit_content = {
            "spore_id": spore_id,
            "warning": "CUSTODIRE SEPARATAMENTE: bastano K frammenti per ricostruire la Master Key della Spora.",
            "quorum_threshold": args.threshold,
            "quorum_total_shares": args.total_shares,
            "shares": [
                {
                    "index": s.index,
                    "custodian": s.custodian,
                    "token": s.encode(),
                }
                for s in created["share_objects"]
            ],
            "germination_command_example": (
                f".venv/bin/python shared/spore_protocol.py # oppure:\n"
                f"python3 germinate_spore.py --spore {created['spore_path']} "
                f"--share '<SHARE_1>' --share '<SHARE_2>' --target-dir ./hyperspace-restored"
            ),
        }
        kit_path.write_text(json.dumps(kit_content, indent=2, ensure_ascii=False), encoding="utf-8")
        os.chmod(kit_path, 0o600)

        # Genera automaticamente anche il "Message in a Bottle" per le Blockchain
        master_key_for_bottle = ShamirQuorumVault.recover_secret(created["shares"][: args.threshold])
        bottle = BlockchainBottleBeacon.craft_bottle(
            manifest=created["manifest"],
            spore_sha256=created["spore_sha256"],
            master_key=master_key_for_bottle,
        )
        bottle_path = spores_dir / f"{spore_id}.blockchain-bottle.json"
        bottle_path.write_text(json.dumps(bottle, indent=2, ensure_ascii=False), encoding="utf-8")

        roundtrip_verification = None
        if args.verify_roundtrip:
            # Simula lo scenario "Alberto ha perso le sue credenziali principali":
            # usiamo il frammento #2 (Guido "Cips") + il frammento #3 (Offline Paper Vault)!
            recovery_subset = created["shares"][1 : 1 + args.threshold]
            recovered_key = ShamirQuorumVault.recover_secret(recovery_subset)
            opened_bottle = BlockchainBottleBeacon.open_bottle(
                bottle["evm_calldata"]["data_hex"],
                master_key=recovered_key,
            )
            with tempfile.TemporaryDirectory(prefix="hspore_verify_") as tmp_verify:
                receipt = SporeBuilder.germinate_spore(
                    spore_path=Path(created["spore_path"]),
                    master_key=recovered_key,
                    target_dir=Path(tmp_verify),
                    restore_secrets=False,
                )
                roundtrip_verification = {
                    "verified": True,
                    "used_custodians": [
                        created["share_objects"][i].custodian
                        for i in range(1, 1 + args.threshold)
                    ],
                    "bottle_decrypted_locators": opened_bottle.locators,
                    "restored_components_count": len(receipt["restored_components"]),
                    "restored_components": receipt["restored_components"],
                }

        output_payload["created_spore"] = {
            "spore_id": spore_id,
            "spore_path": created["spore_path"],
            "manifest_path": created["manifest_path"],
            "blockchain_bottle_path": str(bottle_path),
            "quorum_kit_path": str(kit_path),
            "quorum_kit_permissions": "0600",
            "spore_sha256": created["spore_sha256"],
            "spore_size_bytes": created["spore_size_bytes"],
            "redacted_shares": [_redact_share(s) for s in created["shares"]],
            "blockchain_bottle_summary": {
                "evm_calldata_bytes": bottle["evm_calldata"]["byte_length"],
                "bitcoin_op_return_hex": bottle["bitcoin_op_return"]["data_hex"],
                "solana_memo": bottle["solana_spl_memo"]["memo_string"],
            },
            "roundtrip_verification": roundtrip_verification,
        }

    if args.disperse:
        spore_file = Path(args.disperse).resolve()
        manifest_file = spore_file.with_suffix(".manifest.json")
        disp_res = SporeDispersalEngine.disperse_spore(
            spore_path=spore_file,
            manifest_path=manifest_file,
            local_vault_dirs=[Path(os.path.expanduser(p)) for p in args.local_vault],
            rclone_remotes=args.rclone_remote,
            dry_run=args.dry_run,
        )
        output_payload["dispersal"] = disp_res

    diag = run_diagnostic_report(
        spores_dir=spores_dir,
        sentinel_state_file=sentinel_state_file,
        failover_hours=args.failover_hours,
    )
    output_payload["diagnostic"] = diag

    if args.json:
        print(json.dumps(output_payload, indent=2, ensure_ascii=False))
        return 0

    print("=== HYPERSPACE BIO-MIMETIC SPORE CONTINUITY MANAGER ===")
    sent = diag["sentinel"]
    print(f"[SENTINELLA] Stato: {sent['spore_state']} | Nodi online: {sent['online_nodes_count']}/{sent['total_nodes_checked']}")
    for n in sent["nodes"]:
        st = f"ONLINE ({n['latency_ms']} ms)" if n["online"] else "OFFLINE"
        print(f"  - {n['node_id']} ({n['role']}) @ {n['host']}:{n['port']} -> {st}")
    print(f"  Raccomandazione: {sent['recommendation']}")

    print("\n[SUBSTRATI CLOUD & LOCALI RILEVATI]")
    for sub in diag["substrates"]:
        avail = "PRONTO" if sub["available"] else "DA CONFIGURARE"
        print(f"  - [{avail}] {sub['name']} ({sub['kind']}) -> {sub['endpoint']} | {sub['details']}")

    if "created_spore" in output_payload:
        cs = output_payload["created_spore"]
        print("\n[NUOVA SPORA CRITTOGRAFATA CREATA]")
        print(f"  - ID Spora      : {cs['spore_id']}")
        print(f"  - File Capsula  : {cs['spore_path']} ({cs['spore_size_bytes']:,} bytes)")
        print(f"  - SHA-256       : {cs['spore_sha256']}")
        print(f"  - Bottle OnChain: {cs['blockchain_bottle_path']}")
        print(f"      * BTC OP_RETURN (80B): {cs['blockchain_bottle_summary']['bitcoin_op_return_hex'][:32]}...")
        print(f"      * EVM Calldata Size  : {cs['blockchain_bottle_summary']['evm_calldata_bytes']} bytes (Polygon/Base/Arbitrum/ETH)")
        print(f"      * Solana SPL Memo    : {cs['blockchain_bottle_summary']['solana_memo']}")
        print(f"  - Quorum Kit    : {cs['quorum_kit_path']} (permessi {cs['quorum_kit_permissions']})")
        print("  - Frammenti Shamir (redatti a schermo per sicurezza):")
        for rs in cs["redacted_shares"]:
            print(f"      * {rs}")
        if cs.get("roundtrip_verification"):
            rv = cs["roundtrip_verification"]
            print(
                f"  - Verifica Germinazione (senza chiave primaria, usando {rv['used_custodians']}): "
                f"OK ({rv['restored_components_count']} componenti rigenerati)"
            )

    print(f"\n[VAULT SPORE LOCALE ({diag['existing_spores_count']} capsule in {diag['spores_vault_dir']})]")
    for sp in diag["existing_spores"]:
        if sp.get("valid_header"):
            print(
                f"  - {sp['spore_id']} | commit={sp['git_head_commit']} | quorum={sp['quorum']} "
                f"| size={sp['size_bytes']:,} B | custodi={','.join(sp['custodians'])}"
            )
        else:
            print(f"  - [CORROTTA] {sp['file']}: {sp.get('error')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
