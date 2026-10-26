#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
HyperSpace Sporogenesis On-Chain Wallet & Multi-Chain Broadcaster
(`scripts/diagnostics/spore_onchain_broadcaster.py`)

Perimetro e Sicurezza (Regola 4 AGENTS.md):
- Non richiede MAI di incollare chiavi private in chat o nei log.
- Genera localmente sul nodo (in `data/spores/sporogenesis-wallet.secret.json`,
  permessi `0600`, escluso da Git) un Burner Wallet dedicato alla Sporogenesi:
  1. Indirizzo Pubblico **Solana** (Ed25519 / Base58) per SPL Memo & ecosistema `$00MESH`.
  2. Indirizzo Pubblico **EVM** (secp256k1 / Keccak-256 `0x...`) valido su
     **Base, Polygon, Arbitrum, Optimism, Ethereum**.
- Mostra a schermo ESCLUSIVAMENTE gli indirizzi pubblici di deposito, i saldi
  live letti dagli RPC pubblici e il preventivo di spesa per i "Message in a Bottle".
- Con `--prepare-tx` (o `--broadcast` quando i fondi sono presenti) prepara i
  payload transazionali per ancorare l'ultima Spora (`.blockchain-bottle.json`).

Uso:
    .venv/bin/python scripts/diagnostics/spore_onchain_broadcaster.py
    .venv/bin/python scripts/diagnostics/spore_onchain_broadcaster.py --init-wallet
    .venv/bin/python scripts/diagnostics/spore_onchain_broadcaster.py --prepare-tx
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import secrets
import ssl
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ============================================================================
# Pure-Python Keccak-256 (standard Ethereum pre-NIST padding 0x01) & Base58
# ============================================================================

_KECCAK_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]

_ROT = [
    [0, 36, 3, 41, 18],
    [1, 44, 10, 45, 2],
    [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56],
    [27, 20, 39, 8, 14],
]


def _rotl64(val: int, shift: int) -> int:
    return ((val << shift) | (val >> (64 - shift))) & 0xFFFFFFFFFFFFFFFF


def keccak256(data: bytes) -> bytes:
    """Calcola Keccak-256 (padding 0x01 compatibile EVM/Ethereum)."""
    rate = 136  # (1600 - 512) // 8
    state = [[0] * 5 for _ in range(5)]

    padded = bytearray(data)
    padded.append(0x01)
    while len(padded) % rate != 0:
        padded.append(0x00)
    padded[-1] |= 0x80

    for offset in range(0, len(padded), rate):
        block = padded[offset : offset + rate]
        for i in range(rate // 8):
            lane = int.from_bytes(block[i * 8 : (i + 1) * 8], "little")
            state[i % 5][i // 5] ^= lane

        for r in range(24):
            # Theta
            c = [state[x][0] ^ state[x][1] ^ state[x][2] ^ state[x][3] ^ state[x][4] for x in range(5)]
            d = [c[(x - 1) % 5] ^ _rotl64(c[(x + 1) % 5], 1) for x in range(5)]
            for x in range(5):
                for y in range(5):
                    state[x][y] ^= d[x]
            # Rho & Pi
            b = [[0] * 5 for _ in range(5)]
            for x in range(5):
                for y in range(5):
                    b[y][(2 * x + 3 * y) % 5] = _rotl64(state[x][y], _ROT[x][y])
            # Chi
            for x in range(5):
                for y in range(5):
                    state[x][y] = b[x][y] ^ ((~b[(x + 1) % 5][y]) & b[(x + 2) % 5][y] & 0xFFFFFFFFFFFFFFFF)
            # Iota
            state[0][0] ^= _KECCAK_RC[r]

    out = bytearray()
    for y in range(5):
        for x in range(5):
            if len(out) < 32:
                out.extend(state[x][y].to_bytes(8, "little"))
    return bytes(out[:32])


_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(data: bytes) -> str:
    num = int.from_bytes(data, "big")
    enc = []
    while num > 0:
        num, rem = divmod(num, 58)
        enc.append(_B58_ALPHABET[rem])
    for b in data:
        if b == 0:
            enc.append(_B58_ALPHABET[0])
        else:
            break
    return "".join(reversed(enc))


def b58decode(s: str) -> bytes:
    num = 0
    for ch in s:
        num = num * 58 + _B58_ALPHABET.index(ch)
    combined = num.to_bytes((num.bit_length() + 7) // 8, "big") if num > 0 else b""
    leading_zeros = 0
    for ch in s:
        if ch == _B58_ALPHABET[0]:
            leading_zeros += 1
        else:
            break
    return (b"\x00" * leading_zeros) + combined


def _encode_compact_u16(val: int) -> bytes:
    out = bytearray()
    rem = val
    while True:
        elem = rem & 0x7F
        rem >>= 7
        if rem == 0:
            out.append(elem)
            break
        out.append(elem | 0x80)
    return bytes(out)


def eip55_checksum_address(raw_addr_20b: bytes) -> str:
    hex_addr = raw_addr_20b.hex()
    hash_hex = keccak256(hex_addr.encode("ascii")).hex()
    out = ["0x"]
    for c, h in zip(hex_addr, hash_hex):
        if c in "abcdef" and int(h, 16) >= 8:
            out.append(c.upper())
        else:
            out.append(c)
    return "".join(out)


# ============================================================================
# Generazione / Caricamento Burner Wallet Locale (Solana + EVM)
# ============================================================================

def get_or_create_sporogenesis_wallet(wallet_file: Path, create_if_missing: bool = True) -> Dict[str, Any]:
    """
    Carica o genera il Burner Wallet locale di Sporogenesi.
    Restituisce il dizionario pubblico (senza esporre le chiavi private nell'output).
    """
    if wallet_file.exists():
        raw = json.loads(wallet_file.read_text(encoding="utf-8"))
        return {
            "wallet_file": str(wallet_file),
            "created_at": raw.get("created_at", ""),
            "solana_public_address": raw["solana"]["public_address_base58"],
            "evm_public_address": raw["evm"]["public_address_eip55"],
            "status": "existing_loaded",
        }

    if not create_if_missing:
        return {
            "wallet_file": str(wallet_file),
            "status": "not_initialized",
        }

    # 1. Genera Keypair Solana (Ed25519)
    sol_seed = secrets.token_bytes(32)
    sol_priv = ed25519.Ed25519PrivateKey.from_private_bytes(sol_seed)
    sol_pub_bytes = sol_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    sol_address = b58encode(sol_pub_bytes)
    # Formato array 64-byte compatibile con Solana CLI (`solana-keygen`)
    solana_keypair_64b = list(sol_seed + sol_pub_bytes)

    # 2. Genera Keypair EVM (secp256k1)
    evm_priv_int = secrets.randbelow(
        0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364140 - 1
    ) + 1
    evm_priv_bytes = evm_priv_int.to_bytes(32, "big")
    evm_priv_key = ec.derive_private_key(evm_priv_int, ec.SECP256K1())
    evm_pub_uncompressed = evm_priv_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    # I primi 1 byte sono 0x04, gli altri 64 byte sono (X || Y)
    evm_addr_20b = keccak256(evm_pub_uncompressed[1:])[-20:]
    evm_address = eip55_checksum_address(evm_addr_20b)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    secret_record = {
        "purpose": "HyperSpace Sporogenesis Dedicated Burner Hot Wallet (On-Chain Message in a Bottle)",
        "warning": "NON CONDIVIDERE QUESTO FILE. Finanziare solo con micro-budget ($5-$15) dedicato alle transazioni Spore.",
        "created_at": now_iso,
        "solana": {
            "public_address_base58": sol_address,
            "seed_hex": sol_seed.hex(),
            "keypair_64b_json": solana_keypair_64b,
        },
        "evm": {
            "public_address_eip55": evm_address,
            "private_key_hex": "0x" + evm_priv_bytes.hex(),
        },
    }

    wallet_file.parent.mkdir(parents=True, exist_ok=True)
    wallet_file.write_text(json.dumps(secret_record, indent=2), encoding="utf-8")
    os.chmod(wallet_file, 0o600)

    # Salviamo anche il file keypair compatibile con `solana` CLI (64 int array)
    sol_cli_file = wallet_file.parent / "sporogenesis-solana-keypair.secret.json"
    sol_cli_file.write_text(json.dumps(solana_keypair_64b), encoding="utf-8")
    os.chmod(sol_cli_file, 0o600)

    return {
        "wallet_file": str(wallet_file),
        "solana_cli_keypair_file": str(sol_cli_file),
        "created_at": now_iso,
        "solana_public_address": sol_address,
        "evm_public_address": evm_address,
        "status": "newly_created",
    }


# ============================================================================
# Lettura Saldi Live su RPC Pubblici (Zero API Key)
# ============================================================================

EVM_CHAINS = (
    ("Base Mainnet", "ETH", "https://mainnet.base.org", 8453),
    ("Polygon PoS", "POL", "https://polygon-bor-rpc.publicnode.com", 137),
    ("Arbitrum One", "ETH", "https://arb1.arbitrum.io/rpc", 42161),
)


def query_solana_balance(pubkey_b58: str) -> Dict[str, Any]:
    url = "https://api.mainnet-beta.solana.com"
    payload = {"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [pubkey_b58]}
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "HyperSpace-Spore/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            lamports = int(data.get("result", {}).get("value", 0))
            return {
                "chain": "Solana Mainnet",
                "symbol": "SOL",
                "balance": round(lamports / 1e9, 6),
                "raw_units": lamports,
                "rpc_ok": True,
            }
    except Exception as exc:
        return {
            "chain": "Solana Mainnet",
            "symbol": "SOL",
            "balance": 0.0,
            "rpc_ok": False,
            "error": str(exc),
        }


def query_evm_balance(address: str, chain_name: str, symbol: str, rpc_url: str) -> Dict[str, Any]:
    payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_getBalance", "params": [address, "latest"]}
    try:
        req = urllib.request.Request(
            rpc_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "HyperSpace-Spore/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            wei = int(data.get("result", "0x0"), 16)
            return {
                "chain": chain_name,
                "symbol": symbol,
                "balance": round(wei / 1e18, 6),
                "raw_wei": wei,
                "rpc_ok": True,
            }
    except Exception as exc:
        return {
            "chain": chain_name,
            "symbol": symbol,
            "balance": 0.0,
            "rpc_ok": False,
            "error": str(exc),
        }


def broadcast_solana_memo_bottle(wallet_file: Path, memo_string: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    Costruisce, firma con Ed25519 e trasmette su Solana Mainnet una transazione
    SPL Memo (`MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr`) contenente il
    Message in a Bottle (`HSP-BOTTLE-V1|...`).
    """
    import base64

    raw_wallet = json.loads(wallet_file.read_text(encoding="utf-8"))
    sol_seed = bytes.fromhex(raw_wallet["solana"]["seed_hex"])
    priv_key = ed25519.Ed25519PrivateKey.from_private_bytes(sol_seed)
    payer_pubkey = priv_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    memo_program_id = b58decode("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr")

    rpc_url = "https://api.mainnet-beta.solana.com"
    bh_req = urllib.request.Request(
        rpc_url,
        data=json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getLatestBlockhash",
            "params": [{"commitment": "finalized"}],
        }).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "HyperSpace-Spore/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(bh_req, timeout=8, context=_SSL_CTX) as resp:
        bh_data = json.loads(resp.read().decode("utf-8"))
    blockhash_b58 = bh_data["result"]["value"]["blockhash"]
    recent_blockhash = b58decode(blockhash_b58)

    memo_bytes = memo_string.encode("utf-8")
    # Header: 1 req sig, 0 readonly signed, 1 readonly unsigned
    header = bytes([1, 0, 1])
    account_keys = _encode_compact_u16(2) + payer_pubkey + memo_program_id
    # 1 instruction: program_id_index=1, 1 account=[0], data=memo_bytes
    ix = (
        bytes([1])
        + _encode_compact_u16(1)
        + bytes([0])
        + _encode_compact_u16(len(memo_bytes))
        + memo_bytes
    )
    message = header + account_keys + recent_blockhash + _encode_compact_u16(1) + ix
    signature = priv_key.sign(message)
    wire_tx = _encode_compact_u16(1) + signature + message
    tx_b64 = base64.b64encode(wire_tx).decode("ascii")
    expected_tx_sig_b58 = b58encode(signature)

    if dry_run:
        return {
            "status": "dry_run_signed",
            "chain": "Solana Mainnet",
            "memo_string": memo_string,
            "recent_blockhash": blockhash_b58,
            "expected_tx_signature": expected_tx_sig_b58,
            "wire_tx_bytes": len(wire_tx),
            "solscan_url": f"https://solscan.io/tx/{expected_tx_sig_b58}",
        }

    send_req = urllib.request.Request(
        rpc_url,
        data=json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [tx_b64, {"encoding": "base64", "preflightCommitment": "confirmed"}],
        }).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "HyperSpace-Spore/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(send_req, timeout=10, context=_SSL_CTX) as resp:
        send_res = json.loads(resp.read().decode("utf-8"))
    if "error" in send_res:
        return {
            "status": "rpc_error",
            "error": send_res["error"],
            "expected_tx_signature": expected_tx_sig_b58,
        }
    tx_sig = send_res.get("result", expected_tx_sig_b58)
    return {
        "status": "broadcasted",
        "chain": "Solana Mainnet",
        "tx_signature": tx_sig,
        "solscan_url": f"https://solscan.io/tx/{tx_sig}",
    }


def build_sporogenesis_budget_plan() -> List[Dict[str, Any]]:
    """Restituisce il piano di budget dettagliato per la Sporogenesi Multi-Chain."""
    return [
        {
            "chain": "Solana Mainnet (SPL Memo)",
            "token": "SOL",
            "mechanism": "SPL Memo Program (`MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr`)",
            "cost_per_bottle_usd": "$0.0008 – $0.002",
            "recommended_deposit": "0.03 SOL (~$5.00)",
            "autonomy_bottles": "~2.500+ lanci (1 al giorno per oltre 6 anni)",
            "strategic_value": "Catena nativa di $00MESH (pump.fun); visibile direttamente su Solscan accanto all'ecosistema.",
        },
        {
            "chain": "Polygon PoS (EVM Calldata)",
            "token": "POL (ex MATIC)",
            "mechanism": "Tx 0-value verso `0x0000000000000000000000000000000000485350` con 1.310 byte di calldata AES-256-GCM",
            "cost_per_bottle_usd": "$0.0005 – $0.0015",
            "recommended_deposit": "10 POL (~$3.50)",
            "autonomy_bottles": "~2.000+ bottiglie complete con tutti gli URL dei mirror cifrati",
            "strategic_value": "Contiene l'intero JSON cifrato dei mirror MEGA/Dropbox/OneDrive/IPFS + epistola del fondatore.",
        },
        {
            "chain": "Base / Arbitrum One (EVM L2 Calldata)",
            "token": "ETH (su Base o Arbitrum)",
            "mechanism": "Tx 0-value verso `0x0000000000000000000000000000000000485350` con calldata `HSP-BOTTLE-V1`",
            "cost_per_bottle_usd": "$0.001 – $0.003",
            "recommended_deposit": "0.002 ETH su Base (~$5.00)",
            "autonomy_bottles": "~1.500+ bottiglie complete ancorate ai rollup di Ethereum",
            "strategic_value": "Eredita la sicurezza di Ethereum L1 a una frazione di centesimo per Spora.",
        },
        {
            "chain": "Bitcoin Mainnet (OP_RETURN 80B)",
            "token": "BTC",
            "mechanism": "Output `OP_RETURN` standard da 80 byte (`HSP1` + commit + `spore_sha256` + HMAC mirror)",
            "cost_per_bottle_usd": "$0.80 – $2.50 (a seconda dei sat/vB)",
            "recommended_deposit": "Opzionale (solo per Milestone Major, es. 1 volta al mese/trimestre)",
            "autonomy_bottles": "4 – 10 ancoraggi storici immutabili con $10",
            "strategic_value": "Massima immutabilità termodinamica (Proof-of-Work) per le release storiche di HyperSpace.",
        },
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="HyperSpace On-Chain Sporogenesis Wallet & Budget Manager")
    parser.add_argument(
        "--spores-dir",
        default=str(REPO_ROOT / "data" / "spores"),
        help="Directory locale delle spore (default: data/spores)",
    )
    parser.add_argument(
        "--check-balances",
        action="store_true",
        help="Interroga gli RPC pubblici di Solana, Base, Polygon e Arbitrum per verificare i saldi del Burner Wallet",
    )
    parser.add_argument(
        "--broadcast-solana",
        metavar="BOTTLE_JSON",
        help="[MUTANTE] Firma e trasmette su Solana Mainnet il SPL Memo contenuto in <spore_id>.blockchain-bottle.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Costruisce e firma la transazione Solana recuperando il blockhash reale ma senza inviarla",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in formato JSON",
    )
    args = parser.parse_args()

    spores_dir = Path(args.spores_dir).resolve()
    wallet_file = spores_dir / "sporogenesis-wallet.secret.json"

    wallet_info = get_or_create_sporogenesis_wallet(wallet_file, create_if_missing=True)
    budget_plan = build_sporogenesis_budget_plan()

    balances: List[Dict[str, Any]] = []
    if args.check_balances:
        balances.append(query_solana_balance(wallet_info["solana_public_address"]))
        for cname, sym, rurl, _ in EVM_CHAINS:
            balances.append(query_evm_balance(wallet_info["evm_public_address"], cname, sym, rurl))

    solana_tx_result = None
    if args.broadcast_solana:
        bottle_data = json.loads(Path(args.broadcast_solana).read_text(encoding="utf-8"))
        memo_str = bottle_data["solana_spl_memo"]["memo_string"]
        solana_tx_result = broadcast_solana_memo_bottle(
            wallet_file=wallet_file,
            memo_string=memo_str,
            dry_run=args.dry_run,
        )

    payload = {
        "wallet": wallet_info,
        "balances": balances,
        "solana_tx": solana_tx_result,
        "budget_plan": budget_plan,
        "recommended_total_starter_budget_usd": "$8.50 – $13.50 totali (es. $5 in SOL + $3.50 in POL + $5 in ETH su Base)",
    }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print("=== HYPERSPACE SPOROGENESIS ON-CHAIN WALLET & BUDGET ===")
    print(f"Stato Burner Wallet Locale : {wallet_info['status']} (chiavi private protette in 0600, MAI mostrate)")
    print(f"  -> Indirizzo Deposito SOLANA (SPL Memo)                  : {wallet_info['solana_public_address']}")
    print(f"  -> Indirizzo Deposito EVM (Polygon / Base / Arbitrum)    : {wallet_info['evm_public_address']}")

    if balances:
        print("\n[SALDI LIVE RILEVATI DA RPC PUBBLICI]")
        for b in balances:
            status_str = f"{b['balance']} {b['symbol']}" if b.get("rpc_ok") else f"RPC offline ({b.get('error')})"
            print(f"  - {b['chain']:<20}: {status_str}")

    print("\n[PIANO DI BUDGET CONSIGLIATO PER INIZIARE LA SPOROGENESI]")
    for item in budget_plan:
        print(f"  * {item['chain']}")
        print(f"      Costo per Spora  : {item['cost_per_bottle_usd']}")
        print(f"      Deposito Starter : {item['recommended_deposit']} -> Autonomia: {item['autonomy_bottles']}")
        print(f"      Valore Strategico: {item['strategic_value']}")
    print(f"\n  TOTALE STARTER CONSIGLIATO: {payload['recommended_total_starter_budget_usd']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
