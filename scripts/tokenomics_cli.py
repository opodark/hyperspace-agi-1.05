#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""00MESH Tokenomics CLI — Gestione ricompense nodi PoUW e snapshot pump.fun.

Comandi:
  status                     Panoramica supply emessa, nodi attivi e mining
  leaderboard                Classifica dei nodi lavoratori per $00MESH accumulati
  reward-join <node_id>      Attribuisce il welcome grant a un nodo
  reward-task <node_id>      Attribuisce il reward per task svolto
  link-wallet <node_id> <addr> Collega il wallet Solana per il claim del token
  snapshot                   Genera lo snapshot di allocazione per il lancio su pump.fun
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Assicura import corretti
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared import tokenomics


def cmd_status(args):
    stats = tokenomics.get_tokenomics_overview()
    print("💎 00MESH TOKENOMICS & NODE MINING OVERVIEW")
    print("=" * 55)
    print(f"Token:                   {stats.get('token_symbol')} ({stats.get('token_name')})")
    print(f"Target Launchpad:        {stats.get('target_dex')}")
    print(f"Community Rewards Pool:  {tokenomics.TOTAL_COMMUNITY_POOL:,.0f} {stats.get('token_symbol')}")
    print("-" * 55)
    print(f"Nodi Ricompensati:       {stats.get('total_nodes_rewarded')}")
    print(f"Nodi con Wallet Solana:  {stats.get('nodes_with_solana_wallet')}")
    print(f"Task di Calcolo Pagati:  {stats.get('total_tasks_rewarded')}")
    print(f"Totale {stats.get('token_symbol')} Minati:    {stats.get('total_mined'):,.4f}")
    print(f"Supply Circolante:       {stats.get('total_circulating'):,.4f}")
    print(f"Transazioni Registrate:  {stats.get('total_transactions')}")
    print("=" * 55)


def cmd_leaderboard(args):
    wallets = tokenomics.get_tokenomics_leaderboard(limit=args.limit)
    print(f"🏆 CLASSIFICA MINER / NODI LAVORATORI (Top {len(wallets)})")
    print("=" * 80)
    print(f"{'Node ID':<18} {'Tier':<8} {f'Bilancio ({tokenomics.TOKEN_SYMBOL})':<18} {'Task':<6} {'Solana Wallet':<24}")
    print("-" * 80)
    for w in wallets:
        addr = w.get("solana_address") or "Non collegato"
        if len(addr) > 22:
            addr = addr[:10] + "..." + addr[-8:]
        print(f"{w['node_id'][:16]:<18} {w.get('tier', 'leaf'):<8} {w.get('balance', 0.0):<18.4f} {w.get('tasks_completed', 0):<6} {addr:<24}")
    print("=" * 80)


def cmd_reward_join(args):
    res = tokenomics.reward_node_join(args.node_id, tier=args.tier)
    if res.get("ok"):
        print(f"✅ Welcome grant accreditato con successo a '{args.node_id}': +{res.get('reward')} {tokenomics.TOKEN_SYMBOL}")
        print(f"   Tx ID: {res['tx']['tx_id']} | Nuovo bilancio: {res['tx']['new_balance']}")
    else:
        print(f"⚠️ Errore o già accreditato: {res.get('reason') or res.get('error')}")


def cmd_reward_task(args):
    res = tokenomics.reward_task_completion(
        node_id=args.node_id,
        task_id=args.task_id or f"manual-{args.node_id[:6]}",
        model=args.model or "",
        duration_s=args.duration or 0.0
    )
    if res.get("ok"):
        print(f"✅ Reward computazione accreditato a '{args.node_id}': +{res.get('reward')} {tokenomics.TOKEN_SYMBOL}")
        print(f"   Tx ID: {res['tx']['tx_id']} | Nuovo bilancio: {res['tx']['new_balance']}")
    else:
        print(f"❌ Errore: {res.get('error')}")


def cmd_link_wallet(args):
    res = tokenomics.link_node_solana_wallet(args.node_id, args.solana_address)
    if res.get("ok"):
        print(f"🔗 Wallet Solana collegato al nodo '{args.node_id}' con successo!")
        print(f"   Indirizzo: {args.solana_address}")
        print(f"   Quota claim pump.fun ora associata a questo indirizzo.")
    else:
        print(f"❌ Errore: {res.get('error')}")


def cmd_snapshot(args):
    snapshot = tokenomics.export_pumpfun_snapshot(pool_allocation=args.pool)
    if args.json:
        print(json.dumps(snapshot, indent=2))
        return

    print("🚀 PUMP.FUN TOKEN AIRDROP / CLAIM SNAPSHOT")
    print("=" * 80)
    print(f"Token Network:           {snapshot.get('network')}")
    print(f"Pool da Distribuire:     {snapshot.get('pool_allocation_total'):,.0f} {snapshot.get('token_symbol')}")
    print(f"Nodi Aventi Diritto:     {snapshot.get('total_nodes_eligible')}")
    print(f"Punti Lavoro Minati:     {snapshot.get('total_internal_points_mined'):,.4f}")
    print("-" * 80)
    print(f"{'Node ID':<16} {'Solana Wallet':<26} {'Quota %':<10} {'Token pump.fun Assegnati':<20}")
    print("-" * 80)
    for a in snapshot.get("allocations", []):
        addr = a["solana_address"]
        if len(addr) > 24:
            addr = addr[:10] + "..." + addr[-8:]
        print(f"{a['node_id'][:14]:<16} {addr:<26} {a['share_percentage']:<10.2f}% {a['claimable_spl_tokens']:<20,.2f}")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="HyperSpace Tokenomics & Node Rewards Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    subparsers.add_parser("status", help="Panoramica globale tokenomics")

    # leaderboard
    p_lb = subparsers.add_parser("leaderboard", help="Classifica dei nodi per reward accumulati")
    p_lb.add_argument("--limit", type=int, default=20)

    # reward-join
    p_rj = subparsers.add_parser("reward-join", help="Attribuisce il welcome grant a un nodo")
    p_rj.add_argument("node_id", help="ID del nodo")
    p_rj.add_argument("--tier", default="leaf", choices=["hub", "leaf", "root"])

    # reward-task
    p_rt = subparsers.add_parser("reward-task", help="Attribuisce reward per task completato")
    p_rt.add_argument("node_id", help="ID del nodo")
    p_rt.add_argument("--task-id", default="", help="ID del task completato")
    p_rt.add_argument("--model", default="", help="Nome del modello eseguito")
    p_rt.add_argument("--duration", type=float, default=0.0, help="Durata esecuzione in secondi")

    # link-wallet
    p_lw = subparsers.add_parser("link-wallet", help="Collega un indirizzo Solana al nodo")
    p_lw.add_argument("node_id", help="ID del nodo")
    p_lw.add_argument("solana_address", help="Indirizzo pubblico Solana Base58 (es. Phantom)")

    # snapshot
    p_sn = subparsers.add_parser("snapshot", help="Genera snapshot allocazioni per pump.fun")
    p_sn.add_argument("--pool", type=float, default=tokenomics.TOTAL_COMMUNITY_POOL, help="Totale token pool pump.fun")
    p_sn.add_argument("--json", action="store_true", help="Stampa output in formato JSON puro")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status(args)
    elif args.command == "leaderboard":
        cmd_leaderboard(args)
    elif args.command == "reward-join":
        cmd_reward_join(args)
    elif args.command == "reward-task":
        cmd_reward_task(args)
    elif args.command == "link-wallet":
        cmd_link_wallet(args)
    elif args.command == "snapshot":
        cmd_snapshot(args)


if __name__ == "__main__":
    main()
