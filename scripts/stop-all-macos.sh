#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Arresto simmetrico dei componenti avviati da start-all-macos.sh.
set -euo pipefail

REPO="${HYPERSPACE_REPO:-/Users/opo/hyperspace-agi-1.04}"
cd "$REPO"

log() { printf '[stop-tutto] %s\n' "$*"; }

log "fermo Telegram"
pkill -TERM -f 'scripts/telegram_bot.py' 2>/dev/null || true

bridge_domain="gui/$(id -u)/com.hyperspace.comfy-bridge"
if launchctl print "$bridge_domain" >/dev/null 2>&1; then
  log "fermo e scarico il bridge ComfyUI"
  launchctl bootout "$bridge_domain" 2>/dev/null || true
fi

log "fermo il web-node"
pkill -TERM -f 'node serve.mjs' 2>/dev/null || true

editor_domain="gui/$(id -u)/com.hyperspace.tiktok-editor"
if launchctl print "$editor_domain" >/dev/null 2>&1; then
  log "fermo TikTok editor"
  launchctl bootout "$editor_domain" 2>/dev/null || true
fi

reel_domain="gui/$(id -u)/com.hyperspace.reel-daily"
if launchctl print "$reel_domain" >/dev/null 2>&1; then
  log "fermo scheduler Reel giornaliero"
  launchctl bootout "$reel_domain" 2>/dev/null || true
fi

log "fermo control-plane, registry e traduttore"
docker compose stop control-plane registry libretranslate 2>/dev/null || true

if pgrep -f '/Applications/Comfy Desktop.app/' >/dev/null 2>&1; then
  log "chiudo Comfy Desktop"
  osascript -e 'tell application "Comfy Desktop" to quit' 2>/dev/null || true
fi

log "fatto"
