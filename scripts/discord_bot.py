#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Driver Discord per HyperSpace — Bot sovrano per community $00MESH e pump.fun.

Gestisce:
1. Comandi crypto istantanei (<50ms): /ca, /price, /chart, /mesh, /pouw, /anna, /help
2. Dialogo neurale via Control Plane HyperSpace (/channel/reply) con CoT e personalità
3. Supporto canali server (su menzione) e Direct Message privati (PM)
4. Lucchetto di istanza singola (data/discord-driver.lock)

Config (data/discord-bot.env o os.environ):
  DISCORD_BOT_TOKEN       Token del bot da Discord Developer Portal
  CHANNEL_URL             URL Control Plane (default http://127.0.0.1:8085)
  CHANNEL_TOKEN           Token HyperSpace per il canale "discord"
  DISCORD_REQUIRE_MENTION 1 = nei server risponde solo se menzionato (default: 1)
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from collections import deque
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    import discord
    from discord.ext import commands
except ImportError:
    sys.exit("discord.py non trovato nel venv. Esegui: pip install discord.py")

import requests
from shared.crypto_intel import handle_crypto_command
from shared.single_instance import AlreadyRunning, SingleInstance

# Carica config da data/discord-bot.env se presente
ENV_FILE = _REPO / "data" / "discord-bot.env"
if ENV_FILE.exists():
    try:
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))
    except Exception:
        pass

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
CHANNEL_URL = os.getenv("CHANNEL_URL", "http://127.0.0.1:8085").rstrip("/")
CHANNEL_TOKEN = os.getenv("CHANNEL_TOKEN", "discord-local-token").strip()
REQUIRE_MENTION = os.getenv("DISCORD_REQUIRE_MENTION", "1").strip() == "1"
LOCK_FILE = str(_REPO / "data" / "discord-driver.lock")

HEADERS = {"X-Hyperspace-Channel-Token": CHANNEL_TOKEN}
MAX_CONTEXT = 15


def cp_post(path: str, payload: dict, timeout: int = 35) -> dict:
    """Invia richiesta al Control Plane locale."""
    try:
        r = requests.post(f"{CHANNEL_URL}{path}", json=payload, headers=HEADERS, timeout=timeout)
        if r.status_code >= 400:
            return {"ok": False, "error": f"HTTP {r.status_code}"}
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.dm_messages = True

bot = commands.Bot(command_prefix=["/", "!"], intents=intents, help_command=None)
chats_context: dict[int, deque] = {}


@bot.event
async def on_ready():
    print(f"🤖 [discord] Bot connesso come: {bot.user.name} ({bot.user.id})", flush=True)
    print(f"🌐 [discord] Control Plane: {CHANNEL_URL} | Mention required: {REQUIRE_MENTION}", flush=True)
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="$00MESH on pump.fun | /help"
    )
    await bot.change_presence(status=discord.Status.online, activity=activity)


@bot.event
async def on_message(message: discord.Message):
    # Ignora i messaggi inviati dal bot stesso
    if message.author == bot.user or message.author.bot:
        return

    content = message.content.strip()
    if not content:
        return

    # 1. Comandi crypto istantanei (<50ms)
    crypto_resp = handle_crypto_command(content)
    if crypto_resp:
        await message.reply(crypto_resp, mention_author=False)
        print(f"[discord] Comando crypto eseguito per {message.author}: {content[:30]}", flush=True)
        return

    # 2. Verifica menzione se in server
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mentioned = bot.user in message.mentions

    if not is_dm and REQUIRE_MENTION and not is_mentioned:
        # Se non menzionato in un canale pubblico, registra solo l'evento per contesto e taci
        return

    # Pulisci eventuale menzione dal testo
    clean_text = content
    if is_mentioned:
        clean_text = clean_text.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()

    # 3. Invio a Control Plane per risposta neurale
    surface = "pm" if is_dm else "chat"
    history = chats_context.setdefault(message.channel.id, deque(maxlen=MAX_CONTEXT))
    history.append({"author": str(message.author.name), "text": clean_text})

    async with message.channel.typing():
        loop = asyncio.get_running_loop()
        payload = {
            "surface": surface,
            "chat": str(message.channel.id),
            "context": list(history),
            "pending": 1,
            "oldest_age_s": 0.0,
            "force": True,
            "max_chars": 900,
        }
        res = await loop.run_in_executor(None, lambda: cp_post("/channel/reply", payload, timeout=30))

        if res.get("action") == "reply" and res.get("text"):
            reply_text = res["text"]
            # Discord ha limite di 2000 caratteri
            if len(reply_text) > 1950:
                reply_text = reply_text[:1940] + "..."
            await message.reply(reply_text, mention_author=False)
            history.append({"author": bot.user.name, "text": reply_text})
            print(f"[discord] Risposta inviata a {message.author} su {message.channel}", flush=True)


def main():
    if not DISCORD_TOKEN:
        print("⚠️ [discord] DISCORD_BOT_TOKEN non configurato.")
        print("Crea 'data/discord-bot.env' con:")
        print("  DISCORD_BOT_TOKEN=il_tuo_token_qui")
        print("  CHANNEL_TOKEN=token_hyperspace")
        sys.exit(1)

    try:
        lock = SingleInstance(LOCK_FILE, label="driver Discord").acquire()
    except AlreadyRunning as e:
        sys.exit(f"[discord] {e}: istanza già attiva.")

    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
