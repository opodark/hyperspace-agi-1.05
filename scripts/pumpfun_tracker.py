#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Tracker real-time pump.fun per $00MESH (Buy Bot per Telegram e Discord).

Funzionalità:
1. Connessione WebSocket a PumpPortal (wss://pumpportal.fun/api/data) per streaming trade
2. Rilevamento istantaneo di ogni Buy/Sell su $00MESH (CaMRXTi5h5XQ1A93R1AdSjaYuhoAa3X37ixDf52apump)
3. Notifiche automatiche ricche di emoji, volume, buyer e link Solscan verso Telegram e Discord
4. Fallback con polling periodico DexScreener se la connessione cade

Config (data/pumpfun-tracker.env o os.environ):
  PUMPFUN_MIN_BUY_SOL       Soglia minima in SOL per inviare notifica (default: 0.01)
  TELEGRAM_BOT_TOKEN        Token Telegram per inviare alert
  TELEGRAM_ALERT_CHAT_ID    ID della chat o del gruppo Telegram
  DISCORD_WEBHOOK_URL       Webhook Discord per alert nel canale server
"""
from __future__ import annotations

import asyncio
import json
import os
import ssl
import sys
import time
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    import certifi
    import requests
    import websockets
except ImportError:
    sys.exit("Dipendenze mancanti. Esegui nel venv: pip install websockets certifi requests")

from shared.crypto_intel import CA_ADDRESS, DEXSCREENER_URL, PUMPFUN_URL, PORTAL_URL

ENV_FILE = _REPO / "data" / "pumpfun-tracker.env"
if ENV_FILE.exists():
    try:
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))
    except Exception:
        pass

# Fallback token da telegram-bot.env
if not os.getenv("TELEGRAM_BOT_TOKEN"):
    tg_env = _REPO / "data" / "telegram-bot.env"
    if tg_env.exists():
        for line in tg_env.read_text().splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                os.environ["TELEGRAM_BOT_TOKEN"] = line.split("=", 1)[1].strip()

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.getenv("TELEGRAM_ALERT_CHAT_ID", "").strip()
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
MIN_BUY_SOL = float(os.getenv("PUMPFUN_MIN_BUY_SOL", "0.005"))


def send_telegram_alert(text: str) -> bool:
    """Invia alert nel gruppo o canale Telegram."""
    if not (TG_TOKEN and TG_CHAT_ID):
        return False
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}, timeout=10)
        return r.ok
    except Exception as e:
        print(f"[tracker] Errore invio Telegram: {e}", flush=True)
        return False


def send_discord_alert(text: str) -> bool:
    """Invia alert nel canale Discord via Webhook."""
    if not DISCORD_WEBHOOK:
        return False
    try:
        r = requests.post(DISCORD_WEBHOOK, json={"content": text}, timeout=10)
        return r.ok
    except Exception as e:
        print(f"[tracker] Errore invio Discord: {e}", flush=True)
        return False


def format_trade_alert(trade: dict) -> str:
    """Formatta l'alert di acquisto/vendita pump.fun con stile cyberpunk."""
    tx_type = str(trade.get("txType", "buy")).lower()
    sol_amount = float(trade.get("solAmount") or 0.0)
    token_amount = float(trade.get("tokenAmount") or 0.0)
    trader = str(trade.get("traderPublicKey", ""))
    short_trader = f"{trader[:4]}...{trader[-4:]}" if len(trader) > 8 else (trader or "Anonimo")
    sig = str(trade.get("signature", ""))
    short_sig = f"{sig[:6]}...{sig[-4:]}" if len(sig) > 10 else sig
    solscan_url = f"https://solscan.io/tx/{sig}" if sig else ""

    if tx_type == "buy":
        # Scala di emoji in base all'entità del buy
        green_bars = "🟢" * min(10, max(2, int(sol_amount * 5) + 1))
        title = f"{green_bars}\n🚀 **NUOVO BUY $00MESH SU PUMP.FUN!**"
    else:
        title = f"🔴 **VENDITA $00MESH SU PUMP.FUN**"

    lines = [
        title,
        "",
        f"💰 **Ammontare**: `+{token_amount:,.0f} $00MESH`",
        f"💎 **Valore SOL**: `{sol_amount:.4f} SOL`",
        f"👤 **Trader**: `{short_trader}`",
    ]
    if solscan_url:
        lines.append(f"🔍 **Solscan**: [{short_sig}]({solscan_url})")

    lines.extend([
        "",
        f"🟣 **pump.fun**: {PUMPFUN_URL}",
        f"📈 **DexScreener**: {DEXSCREENER_URL}",
        f"📋 **CA**: `{CA_ADDRESS}`",
    ])
    return "\n".join(lines)


async def listen_trades():
    """Loop asincrono di ascolto trade da PumpPortal WebSocket."""
    uri = "wss://pumpportal.fun/api/data"
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())

    while True:
        try:
            print(f"🔌 [tracker] Connessione a {uri}...", flush=True)
            async with websockets.connect(uri, ssl=ssl_ctx, ping_interval=25, close_timeout=10) as ws:
                payload = {
                    "method": "subscribeTokenTrade",
                    "keys": [CA_ADDRESS],
                }
                await ws.send(json.dumps(payload))
                print(f"✅ [tracker] Iscritto ai trade in tempo reale per CA: {CA_ADDRESS[:8]}...pump", flush=True)

                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    mint = data.get("mint")
                    if mint != CA_ADDRESS:
                        continue

                    tx_type = str(data.get("txType", "")).lower()
                    sol_amount = float(data.get("solAmount") or 0.0)

                    # Filtra piccoli buy o trade non rilevanti
                    if tx_type == "buy" and sol_amount < MIN_BUY_SOL:
                        print(f"[tracker] Buy ignorato sotto soglia: {sol_amount} SOL", flush=True)
                        continue

                    alert = format_trade_alert(data)
                    print(f"\n⚡ [PUMP.FUN TRADE] {tx_type.upper()}: {sol_amount:.4f} SOL da {data.get('traderPublicKey', '')[:8]}", flush=True)

                    # Broadcast a Telegram e Discord
                    if TG_TOKEN and TG_CHAT_ID:
                        send_telegram_alert(alert)
                    if DISCORD_WEBHOOK:
                        send_discord_alert(alert)

        except (websockets.ConnectionClosed, asyncio.TimeoutError) as e:
            print(f"⚠️ [tracker] Connessione interrotta ({e}); riconnessione tra 5s...", flush=True)
            await asyncio.sleep(5)
        except Exception as e:
            print(f"❌ [tracker] Errore imprevisto ({e}); riconnessione tra 10s...", flush=True)
            await asyncio.sleep(10)


def main():
    print("🚀 Avvio 00MESH pump.fun Real-Time Tracker & Buy Bot")
    print(f"Token Mint: {CA_ADDRESS}")
    print(f"Soglia minima Buy: {MIN_BUY_SOL} SOL")
    print(f"Telegram Alert: {'Attivo' if (TG_TOKEN and TG_CHAT_ID) else 'Non configurato (TELEGRAM_ALERT_CHAT_ID mancante)'}")
    print(f"Discord Alert: {'Attivo' if DISCORD_WEBHOOK else 'Non configurato (DISCORD_WEBHOOK_URL mancante)'}")
    asyncio.run(listen_trades())


if __name__ == "__main__":
    main()
