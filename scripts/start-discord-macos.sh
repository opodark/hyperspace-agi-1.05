#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Avvio del driver Discord per macOS con token e canali configurati

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR" || exit 1

ENV_FILE="data/discord-bot.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Errore: file $ENV_FILE non trovato."
    exit 1
fi

# Carica DISCORD_BOT_TOKEN da data/discord-bot.env
export $(grep -v '^#' "$ENV_FILE" | xargs)

# Estrai CHANNEL_TOKEN per 'discord' da .env
if [ -f ".env" ]; then
    CLIENTS=$(grep '^CHANNEL_CLIENTS=' .env | cut -d '=' -f2- | tr -d '"'\')
    for pair in $(echo "$CLIENTS" | tr ";" "\n"); do
        case "$pair" in
            discord=*)
                export CHANNEL_TOKEN="${pair#discord=}"
                ;;
        esac
    done
fi

export CHANNEL_URL="${CHANNEL_URL:-http://127.0.0.1:8085}"
export DISCORD_REQUIRE_MENTION="${DISCORD_REQUIRE_MENTION:-1}"

if [ -z "$DISCORD_BOT_TOKEN" ]; then
    echo "⚠️ Avviso: DISCORD_BOT_TOKEN vuoto in $ENV_FILE."
    echo "   Inserisci il token del bot ottenuto dal Discord Developer Portal:"
    echo "   https://discord.com/developers/applications"
    exit 1
fi

if [ -z "$CHANNEL_TOKEN" ]; then
    echo "❌ Errore: CHANNEL_TOKEN per discord non trovato in .env (CHANNEL_CLIENTS)"
    exit 1
fi

echo "🤖 Avvio driver Discord con $ROOT_DIR/.venv/bin/python"
echo "   URL Control Plane: $CHANNEL_URL"
echo "   Token Discord: OK (redatto)"
echo "   Token Canale: OK (redatto)"

exec "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/discord_bot.py"
