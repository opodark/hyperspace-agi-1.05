#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Avvio del driver Telegram per macOS con token e canali configurati

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR" || exit 1

ENV_FILE="data/telegram-bot.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Errore: file $ENV_FILE non trovato."
    exit 1
fi

# Carica TELEGRAM_BOT_TOKEN da data/telegram-bot.env
export $(grep -v '^#' "$ENV_FILE" | xargs)

# Estrai CHANNEL_TOKEN per 'telegram' da .env
if [ -f ".env" ]; then
    CLIENTS=$(grep '^CHANNEL_CLIENTS=' .env | cut -d '=' -f2- | tr -d '"'\')
    for pair in $(echo "$CLIENTS" | tr ";" "\n"); do
        case "$pair" in
            telegram=*)
                export CHANNEL_TOKEN="${pair#telegram=}"
                ;;
        esac
    done
fi

export CHANNEL_URL="${CHANNEL_URL:-http://127.0.0.1:8085}"
export TELEGRAM_REQUIRE_MENTION="${TELEGRAM_REQUIRE_MENTION:-0}"

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ Errore: TELEGRAM_BOT_TOKEN mancante in $ENV_FILE"
    exit 1
fi

if [ -z "$CHANNEL_TOKEN" ]; then
    echo "❌ Errore: CHANNEL_TOKEN per telegram non trovato in .env (CHANNEL_CLIENTS)"
    exit 1
fi

echo "🚀 Avvio driver Telegram con $ROOT_DIR/.venv/bin/python"
echo "   URL Control Plane: $CHANNEL_URL"
echo "   Token Telegram: OK (redatto)"
echo "   Token Canale: OK (redatto)"

exec "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/telegram_bot.py"
