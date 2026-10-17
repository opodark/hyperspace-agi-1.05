# SPDX-License-Identifier: Apache-2.0
"""Regole di Tokenomics, Calcolo Reward e Predisposizione Airdrop pump.fun per HyperSpace.

Gestisce la Proof-of-Useful-Work (PoUW) e la disponibilità dei nodi:
- Join Bonus: ricompensa di benvenuto all'onboarding del nodo.
- Task Reward: ricompensa per computazione/inferenza basata sul peso del modello (Bonsai 2, Qwen, MoE).
- Uptime Reward: ricompensa per disponibilità e canale E2EE mantenuto.
- Solana Wallet Linking & pump.fun Snapshot: mappatura dei nodi su indirizzi SPL per il futuro claim.
"""
from __future__ import annotations

import re
from typing import Optional

try:
    from shared import db
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from shared import db

# Assicura inizializzazione tabelle nel DB SQLite
try:
    db.init_db()
except Exception:
    pass

TOKEN_SYMBOL = "$00MESH"
TOKEN_NAME = "00MESH Network Token"

# Supply fissa standard pump.fun (1 Miliardo di token)
TOTAL_SUPPLY = 1_000_000_000.0
# Allocazione pump.fun Bonding Curve & Fair Launch (70%)
TOTAL_BONDING_POOL = 700_000_000.0
# Allocazione per la community e mining mesh Proof-of-Useful-Work (20%)
TOTAL_COMMUNITY_POOL = 200_000_000.0
# Riserva sviluppo core, bridge e sicurezza ecosistema (10%)
TOTAL_ECOSYSTEM_POOL = 100_000_000.0

# Parametri base dei reward
JOIN_BONUS_REWARD = 50.0        # $00MESH erogati al primo joining del nodo
BASE_TASK_REWARD = 2.0          # $00MESH base per task completato con successo
UPTIME_REWARD_PER_HOUR = 5.0    # $00MESH per ora di disponibilità continua nella mesh

# Validatore indirizzo Solana Base58 (lunghezza tipica 32-44 caratteri base58)
_SOLANA_ADDR_REGEX = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


def validate_solana_address(address: str) -> bool:
    """Verifica se una stringa è un indirizzo pubblico Solana valido (formato Base58)."""
    return bool(_SOLANA_ADDR_REGEX.match((address or "").strip()))


def calculate_task_reward(model: str = "", duration_s: float = 0.0, tokens: int = 0) -> float:
    """Calcola il reward per task svolto in base a modello e complessità di calcolo."""
    multiplier = 1.0
    m = (model or "").lower()

    if any(k in m for k in ("bonsai", "27b", "moe", "deepseek", "qwen3.5-abliterated:9b")):
        # Modelli pesanti o quantizzazioni avanzate ad alto valore aggiunto
        multiplier = 3.0
    elif any(k in m for k in ("8b", "7b", "granite", "qwen3:8b", "qwen3-8b")):
        # Modelli intermedi standard da 7-9B
        multiplier = 1.5
    else:
        # Modelli leggeri (es. 4B, 3B, embeddings)
        multiplier = 1.0

    reward = BASE_TASK_REWARD * multiplier

    # Bonus computazionale per sessioni lunghe o molti token (se disponibili)
    if duration_s > 5.0:
        reward += min(2.0, round(duration_s * 0.1, 2))
    if tokens > 500:
        reward += min(3.0, round((tokens / 500) * 0.5, 2))

    return round(reward, 4)


def reward_node_join(node_id: str, tier: str = "leaf") -> dict:
    """Accredita il bonus di benvenuto una tantum a un nodo che si registra nella mesh."""
    nid = (node_id or "").strip()
    if not nid:
        raise ValueError("node_id non può essere vuoto")

    wallet = db.get_token_wallet(nid)
    if wallet and wallet.get("total_earned", 0) > 0:
        # Nodo già ricompensato in precedenza
        return {"ok": False, "reason": "join_already_rewarded", "wallet": wallet}

    db.upsert_token_wallet(nid, tier=tier)
    tx = db.credit_token_balance(
        node_id=nid,
        amount=JOIN_BONUS_REWARD,
        tx_type="join_bonus",
        reference_id=f"join-{nid[:10]}",
        memo=f"Welcome grant for joining HyperSpace mesh ({tier})"
    )
    return {"ok": True, "reward": JOIN_BONUS_REWARD, "tx": tx}


def reward_task_completion(node_id: str, task_id: str, model: str = "", duration_s: float = 0.0, tokens: int = 0) -> dict:
    """Accredita il reward per il completamento con successo di un task di inferenza/calcolo."""
    nid = (node_id or "").strip()
    tid = (task_id or "").strip()
    if not nid:
        return {"ok": False, "error": "node_id mancante"}

    amount = calculate_task_reward(model=model, duration_s=duration_s, tokens=tokens)
    memo = f"Inference task completed (model={model or 'default'})"

    tx = db.credit_token_balance(
        node_id=nid,
        amount=amount,
        tx_type="task_reward",
        reference_id=tid,
        memo=memo
    )
    return {"ok": True, "reward": amount, "tx": tx}


def reward_node_uptime(node_id: str, seconds: int = 3600) -> dict:
    """Accredita il reward proporzionale per l'uptime verificato nella mesh."""
    nid = (node_id or "").strip()
    if not nid or seconds <= 0:
        return {"ok": False, "error": "parametri non validi"}

    hours = seconds / 3600.0
    amount = round(hours * UPTIME_REWARD_PER_HOUR, 4)

    tx = db.credit_token_balance(
        node_id=nid,
        amount=amount,
        tx_type="uptime_reward",
        reference_id=f"uptime-{int(seconds)}s",
        memo=f"Proof-of-Availability reward for {round(hours, 2)}h active"
    )
    return {"ok": True, "reward": amount, "tx": tx}


def b58decode(s: str) -> bytes:
    """Decodifica una stringa Base58 in bytes."""
    num = 0
    for char in s:
        idx = BASE58_ALPHABET.find(char)
        if idx == -1:
            raise ValueError(f"Carattere Base58 non valido: {char}")
        num = num * 58 + idx
    combined = num.to_bytes((num.bit_length() + 7) // 8, "big") if num > 0 else b""
    pad = 0
    for char in s:
        if char == "1":
            pad += 1
        else:
            break
    return b"\x00" * pad + combined


def verify_solana_signature(solana_address: str, message: str | bytes, signature_b58: str) -> bool:
    """Verifica crittograficamente la firma Ed25519 generata da un wallet Solana (Phantom/Solflare)."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        pub_bytes = b58decode(solana_address)
        sig_bytes = b58decode(signature_b58)
        if len(pub_bytes) != 32 or len(sig_bytes) != 64:
            return False
        pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
        msg_bytes = message.encode("utf-8") if isinstance(message, str) else message
        pub_key.verify(sig_bytes, msg_bytes)
        return True
    except Exception:
        return False


def link_node_solana_wallet(node_id: str, solana_address: str, signature: str = "", timestamp: str = "") -> dict:
    """Collega l'indirizzo wallet Solana (es. Phantom) al node_id per il futuro claim pump.fun.

    Protezioni attive:
    - Verifica formato crittografico Base58 dell'indirizzo Solana.
    - Se fornita firma Ed25519, convalida crittografica dell'indirizzo proprietario.
    - Anti-hijacking: rifiuta la sovrascrittura di un wallet già configurato su un nodo diverso.
    - Anti-farming: il welcome bonus (+50 $00MESH) è erogabile una sola volta per indirizzo Solana su tutta la rete.
    """
    nid = (node_id or "").strip()
    addr = (solana_address or "").strip()
    sig = (signature or "").strip()
    ts = (timestamp or "").strip()

    if not nid:
        return {"ok": False, "error": "node_id mancante"}
    if not validate_solana_address(addr):
        return {"ok": False, "error": "Indirizzo Solana non valido (richiesto formato Base58 32-44 caratteri)"}

    # Se viene fornita una firma crittografica, verificala rigorosamente
    if sig:
        expected_msg = f"00MESH-auth:{nid}:{ts}"
        if not verify_solana_signature(addr, expected_msg, sig):
            return {"ok": False, "error": "Firma crittografica non valida per l'indirizzo Solana fornito"}

    # Protezione anti-hijacking: se il nodo ha già un wallet associato diverso, rifiuta
    current_wallet = db.get_token_wallet(nid)
    if current_wallet and current_wallet.get("solana_address"):
        if current_wallet["solana_address"] != addr:
            return {"ok": False, "error": "Wallet già associato a questo nodo con un indirizzo diverso"}

    db.upsert_token_wallet(nid)

    # Protezione anti-farming: un indirizzo Solana può ricevere il bonus di benvenuto una sola volta
    # su tutta la rete, indipendentemente da quanti nodi tenta di registrare.
    wallets_for_addr = db.get_wallets_by_solana_address(addr)
    addr_already_has_reward = any(w.get("total_earned", 0) > 0 for w in wallets_for_addr if w.get("node_id") != nid)

    join_reward = None
    if (not current_wallet or current_wallet.get("total_earned", 0) <= 0) and not addr_already_has_reward:
        join_reward = reward_node_join(nid, tier="web")

    success = db.set_node_solana_address(nid, addr)
    wallet = db.get_token_wallet(nid)
    return {
        "ok": success,
        "node_id": nid,
        "solana_address": addr,
        "wallet": wallet,
        "join_reward": join_reward,
        "bonus_granted": join_reward is not None and join_reward.get("ok", False)
    }


def get_tokenomics_leaderboard(limit: int = 20) -> list[dict]:
    """Restituisce la classifica dei nodi più attivi e ricompensati nella rete."""
    return db.list_token_wallets(limit=limit)


def get_tokenomics_overview() -> dict:
    """Restituisce la panoramica globale della tokenomics e dello stato di mining mesh."""
    return db.get_tokenomics_stats()


def export_pumpfun_snapshot(pool_allocation: float = TOTAL_COMMUNITY_POOL) -> dict:
    """Genera lo snapshot crittografico per la distribuzione/airdrop dei token su Solana/pump.fun."""
    wallets = db.list_token_wallets(limit=1000)
    stats = db.get_tokenomics_stats()
    total_mined = stats.get("total_mined", 0.0)

    allocations = []
    total_claimable_tokens = 0.0

    for w in wallets:
        earned = float(w.get("total_earned", 0.0))
        if earned <= 0 or total_mined <= 0:
            continue

        ratio = earned / total_mined
        allocated_tokens = round(ratio * pool_allocation, 2)
        total_claimable_tokens += allocated_tokens

        allocations.append({
            "node_id": w["node_id"],
            "tier": w.get("tier", "leaf"),
            "solana_address": w.get("solana_address") or "UNLINKED",
            "hyper_points_earned": earned,
            "tasks_completed": w.get("tasks_completed", 0),
            "share_percentage": round(ratio * 100, 4),
            "claimable_spl_tokens": allocated_tokens
        })

    return {
        "network": "Solana (pump.fun standard)",
        "token_symbol": TOKEN_SYMBOL,
        "token_name": TOKEN_NAME,
        "pool_allocation_total": pool_allocation,
        "total_nodes_eligible": len(allocations),
        "total_internal_points_mined": total_mined,
        "total_claimable_tokens_distributed": round(total_claimable_tokens, 2),
        "allocations": allocations
    }
