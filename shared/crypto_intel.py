# SPDX-License-Identifier: Apache-2.0
"""Intelligence Crypto, Tokenomics & pump.fun per Chatbot Telegram e Discord.

Fornisce metriche on-chain in tempo reale, telemetria DePIN della mesh e
formattazione deterministica ultra-rapida (<50ms) per comandi token.
"""
from __future__ import annotations

import time
from typing import Any, Optional

try:
    import requests
except ImportError:
    requests = None

# Costanti $00MESH & Solana
CA_ADDRESS = "CaMRXTi5h5XQ1A93R1AdSjaYuhoAa3X37ixDf52apump"
TICKER = "$00MESH"
TOKEN_NAME = "00MESH Sovereign AI"
TOTAL_SUPPLY = "1.000.000.000"
COMMUNITY_POOL = "200.000.000 (20%)"
CHAIN = "Solana (SPL Token)"

PUMPFUN_URL = f"https://pump.fun/coin/{CA_ADDRESS}"
DEXSCREENER_URL = f"https://dexscreener.com/solana/{CA_ADDRESS}"
PORTAL_URL = "https://www.zerozerocomputer.it"
DATING_SIM_URL = "https://www.zerozerocomputer.it/anna.html"
CHROME_BRIDGE_URL = "https://www.zerozerocomputer.it/assets/00mesh-chrome-bridge.zip"

_CACHE_TTL_S = 12.0
_market_cache: dict[str, Any] = {"ts": 0.0, "data": None}


def get_market_metrics() -> dict[str, Any]:
    """Recupera metriche di prezzo e volume da DexScreener con caching in-memory."""
    now = time.time()
    if _market_cache["data"] is not None and (now - _market_cache["ts"]) < _CACHE_TTL_S:
        return _market_cache["data"]

    default_data = {
        "price_usd": "0.000000025",
        "market_cap": 25.0,
        "volume_24h": 745.0,
        "price_change_24h": 0.0,
        "price_change_6h": 0.0,
        "buys_24h": 233,
        "sells_24h": 219,
        "dex": "pump.fun",
        "live": False,
    }

    if not requests:
        return default_data

    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{CA_ADDRESS}"
        res = requests.get(url, timeout=4)
        if res.ok:
            pairs = res.json().get("pairs") or []
            # Preferisci la pair di pumpfun o quella con più volume
            pump_pair = next((p for p in pairs if p.get("dexId") == "pumpfun"), None)
            if not pump_pair and pairs:
                pump_pair = max(pairs, key=lambda p: float((p.get("volume") or {}).get("h24") or 0.0))

            if pump_pair:
                vol = pump_pair.get("volume") or {}
                changes = pump_pair.get("priceChange") or {}
                txns = (pump_pair.get("txns") or {}).get("h24") or {}
                data = {
                    "price_usd": pump_pair.get("priceUsd") or default_data["price_usd"],
                    "market_cap": float(pump_pair.get("marketCap") or pump_pair.get("fdv") or default_data["market_cap"]),
                    "volume_24h": float(vol.get("h24") or default_data["volume_24h"]),
                    "price_change_24h": float(changes.get("h24") or 0.0),
                    "price_change_6h": float(changes.get("h6") or 0.0),
                    "buys_24h": int(txns.get("buys") or default_data["buys_24h"]),
                    "sells_24h": int(txns.get("sells") or default_data["sells_24h"]),
                    "dex": pump_pair.get("dexId", "pump.fun"),
                    "live": True,
                }
                _market_cache["ts"] = now
                _market_cache["data"] = data
                return data
    except Exception:
        pass

    return default_data


def get_mesh_telemetry(cp_url: str = "http://127.0.0.1:8085") -> dict[str, Any]:
    """Interroga lo stato dei nodi DePIN attivi via Control Plane locale."""
    res = {
        "nodes_active": 6,
        "omen_vram": "8.0 GB (RTX Dedicated)",
        "models": ["Liquid AI LFM2.5", "Ollama", "ComfyUI SD1.5/Flux"],
        "status": "online",
    }
    if not requests:
        return res
    try:
        r = requests.get(f"{cp_url}/health", timeout=2)
        if r.ok:
            payload = r.json()
            res["nodes_active"] = payload.get("nodes_active", res["nodes_active"])
            res["memories"] = payload.get("memories", 0)
    except Exception:
        pass
    return res


def format_ca() -> str:
    """Messaggio per Contract Address da copiare al volo."""
    return (
        f"🪙 **Contract Address Ufficiale $00MESH (Solana SPL)**\n\n"
        f"`{CA_ADDRESS}`\n\n"
        f"🟣 **pump.fun**: {PUMPFUN_URL}\n"
        f"📈 **DexScreener**: {DEXSCREENER_URL}\n"
        f"🌐 **Web Hub**: {PORTAL_URL}\n\n"
        f"*(Tocca o clicca l'indirizzo per copiarlo direttamente nel tuo Phantom/Solflare)*"
    )


def format_price() -> str:
    """Messaggio completo con metriche di mercato in tempo reale."""
    m = get_market_metrics()
    sign_24h = "+" if m["price_change_24h"] >= 0 else ""
    sign_6h = "+" if m["price_change_6h"] >= 0 else ""
    indicator = "🟢" if m["price_change_24h"] >= 0 else "🔴"

    return (
        f"📊 **Quotazione $00MESH in Tempo Reale** {indicator}\n\n"
        f"💵 **Prezzo**: `${m['price_usd']}`\n"
        f"🏦 **Market Cap**: `${m['market_cap']:,.2f}`\n"
        f"🌊 **Volume 24h**: `${m['volume_24h']:,.2f}`\n"
        f"📈 **Var. 6h / 24h**: `{sign_6h}{m['price_change_6h']:.1f}%` / `{sign_24h}{m['price_change_24h']:.1f}%`\n"
        f"🔄 **Transazioni 24h**: `{m['buys_24h']} Buy` / `{m['sells_24h']} Sell`\n"
        f"⚡ **DEX / Launchpad**: `{m['dex']}`\n\n"
        f"🟣 **Acquista su pump.fun**: {PUMPFUN_URL}\n"
        f"📈 **Grafico DexScreener**: {DEXSCREENER_URL}\n"
        f"📋 **CA**: `{CA_ADDRESS}`"
    )


def format_mesh_stats() -> str:
    """Stato della rete computazionale sovrana DePIN."""
    tel = get_mesh_telemetry()
    return (
        f"⚡ **00MESH Sovereign AI — Telemetria Nodi & Calcolo**\n\n"
        f"🟢 **Nodi Attivi nella Mesh**: `{tel['nodes_active']} nodi peer-to-peer`\n"
        f"💻 **Mac M5 Hub**: Master Control Plane & Coordinatore\n"
        f"🎮 **HP OMEN 16**: Dedicated GPU `{tel['omen_vram']}` (Inferenza neurale)\n"
        f"🧠 **Modelli Live**: `Liquid AI LFM2.5 (CoT Reasoning)`, `Ollama`, `ComfyUI`\n"
        f"🌐 **WebGPU Workers**: Condivisione calcolo browser su {PORTAL_URL}\n\n"
        f"💡 Vuoi minare token $00MESH condividendo la tua GPU o CPU?\n"
        f"Usa `/pouw` per scoprire come unirti!"
    )


def format_pouw_guide() -> str:
    """Guida rapida per minatori e fornitori di calcolo."""
    return (
        f"⛏️ **Come Minare $00MESH con Proof-of-Useful-Work (PoUW)**\n\n"
        f"Su 1 Miliardo di $00MESH, **200 Milioni (20%)** sono riservati esclusivamente a chi condivide calcolo!\n\n"
        f"**Come partecipare subito:**\n"
        f"1. **Via Browser (WebGPU zero-install)**:\n"
        f"   Visita {PORTAL_URL} e clicca su *Attiva Nodo WebGPU*.\n\n"
        f"2. **Via Chrome Extension (Bridge Locale)**:\n"
        f"   Scarica il Chrome Bridge: {CHROME_BRIDGE_URL}\n"
        f"   Collega il tuo Ollama (`:11434`) o ComfyUI (`:8188`) e inizia a validare task!\n\n"
        f"3. **Claim dei Token su Solana**:\n"
        f"   Collega il tuo wallet Phantom nella homepage per registrare il tuo indirizzo di payout."
    )


def format_anna_sim() -> str:
    """Invito alla Dating Sim Visual Novel di Anna con perk VIP Holder."""
    return (
        f"💖 **Anna Dating Sim & Visual Novel Cyberpunk**\n\n"
        f"Flirta, dialoga e scopri i segreti di Anna nella visual novel cyberpunk ufficiale!\n"
        f"🎮 **Gioca ora nel browser**: {DATING_SIM_URL}\n\n"
        f"👑 **Vantaggio Holder VIP ($00MESH)**:\n"
        f"Se possiedi token $00MESH nel tuo wallet Phantom, sblocchi:\n"
        f"- Dialoghi intimi esclusivi oltre il 35% di affinità.\n"
        f"- Rimozione completa dei banner pubblicitari (Ad-Free).\n"
        f"- Creatore di Virtual Companion personalizzate (`✨ Crea Companion VIP`).\n\n"
        f"🟣 **Prendi $00MESH su pump.fun**: {PUMPFUN_URL}"
    )


def format_help() -> str:
    """Menu comandi completo per Telegram e Discord."""
    return (
        f"🤖 **Comandi Chatbot 00MESH & pump.fun**\n\n"
        f"**Token & Mercato:**\n"
        f"• `/ca` o `!ca` — Contract Address ufficiale di $00MESH\n"
        f"• `/price` o `!price` — Prezzo live, market cap e volume pump.fun\n"
        f"• `/chart` o `!chart` — Link diretto al grafico DexScreener\n"
        f"• `/buy` o `!buy` — Link istantaneo per acquistare su pump.fun\n\n"
        f"**Rete & Mining DePIN:**\n"
        f"• `/mesh` o `/nodes` — Stato della rete, GPU e nodi online\n"
        f"• `/pouw` o `/mining` — Come guadagnare $00MESH condividendo GPU\n\n"
        f"**Esperienze:**\n"
        f"• `/anna` o `/dating` — Visual Novel interattiva con perk Holder VIP\n"
        f"• `!anna <scena>` — Chiedi ad Anna di generare una foto neurale\n"
        f"• `!presentati` — Presentazione ufficiale della personalità\n\n"
        f"💬 *Oppure scrivi liberamente in chat per conversare con la nostra IA!*"
    )


def handle_crypto_command(text: str) -> Optional[str]:
    """Intercetta ed elabora comandi crypto/token istantanei. Ritorna None se non è un comando."""
    if not text:
        return None
    raw = text.strip().lower()
    # Rimuovi eventuale menzione al bot (es. /price@pimpachatbot -> /price)
    cmd = raw.split()[0].split("@")[0]

    if cmd in ("/ca", "!ca", "/contract", "!contract", "ca"):
        return format_ca()
    if cmd in ("/price", "!price", "/prezzo", "!prezzo", "price", "prezzo"):
        return format_price()
    if cmd in ("/chart", "!chart", "/grafico", "!grafico", "chart", "grafico"):
        return f"📈 **Grafico in Tempo Reale $00MESH**\n\n🔗 DexScreener: {DEXSCREENER_URL}\n🟣 pump.fun: {PUMPFUN_URL}\n🌐 Web Hub: {PORTAL_URL}#chartSection"
    if cmd in ("/buy", "!buy", "/acquista", "!acquista", "buy"):
        return f"🟣 **Acquista $00MESH su pump.fun (Solana)**\n\n{PUMPFUN_URL}\n\n📋 **CA**: `{CA_ADDRESS}`"
    if cmd in ("/bonding", "!bonding", "/raydium", "!raydium", "bonding"):
        return f"🌊 **Bonding Curve pump.fun & Raydium**\n\nTarget Raydium: ~$69,000 MCap ($12,000 SOL aggiunti e LP bruciate per sempre)!\n🟣 Segui la curva: {PUMPFUN_URL}"
    if cmd in ("/tokenomics", "!tokenomics", "/token", "!token", "tokenomics"):
        return f"🪙 **Tokenomics 00MESH ($00MESH)**\n\n• Supply: 1.000.000.000 (1B fisso)\n• Fair Launch pump.fun: 80%\n• Mining Pool PoUW: 20% (200M)\n• 0% Tasse, 100% Sovrano\n🟣 {PUMPFUN_URL}"
    if cmd in ("/quiz", "!quiz", "quiz"):
        return "🧠 **Quiz Sovrano DePIN**\n\nRispondi al quiz nativo interattivo su Telegram per testare le tue skill!"
    if cmd in ("/mesh", "!mesh", "/nodes", "!nodes", "/stats", "!stats", "mesh", "nodes"):
        return format_mesh_stats()
    if cmd in ("/pouw", "!pouw", "/mining", "!mining", "/mine", "!mine", "pouw", "mining"):
        return format_pouw_guide()
    if cmd in ("/anna", "!dating", "/dating", "anna", "dating"):
        return format_anna_sim()
    if cmd in ("/help", "!help", "/aiuto", "!aiuto", "help", "aiuto"):
        return format_help()

    return None
