#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Avvio completo HyperSpace su macOS: Docker/CP, ComfyUI, bridge, Telegram e web-node.
set -euo pipefail

REPO="${HYPERSPACE_REPO:-/Users/opo/hyperspace-agi-1.04}"
BUILD=0
[[ "${1:-}" == "--build" ]] && BUILD=1
cd "$REPO"
mkdir -p data

log() { printf '[start-tutto] %s\n' "$*"; }
warn() { printf '[start-tutto] AVVISO: %s\n' "$*" >&2; }
running() { pgrep -f "$1" >/dev/null 2>&1; }

log "avvio HyperSpace su macOS"

if ! docker info >/dev/null 2>&1; then
  log "avvio Docker Desktop"
  open -a Docker
  for _ in $(seq 1 60); do
    docker info >/dev/null 2>&1 && break
    sleep 2
  done
fi
docker info >/dev/null 2>&1 || { warn "Docker Desktop non è pronto"; exit 1; }

log "avvio traduttore offline"
docker compose up -d libretranslate

log "avvio registry e control-plane"
cp_args=(up -d --no-deps)
[[ "$BUILD" -eq 1 ]] && cp_args+=(--build)
docker compose "${cp_args[@]}" registry control-plane

log "attendo il control-plane"
cp_ready=0
for _ in $(seq 1 60); do
  if curl -fsS --max-time 3 http://127.0.0.1:8085/health >/dev/null 2>&1; then
    cp_ready=1
    break
  fi
  sleep 2
done
[[ "$cp_ready" -eq 1 ]] || { warn "control-plane non raggiungibile su :8085"; exit 1; }

if ! curl -fsS --max-time 3 http://127.0.0.1:8188/system_stats >/dev/null 2>&1; then
  log "avvio Comfy Desktop"
  open -a "Comfy Desktop"
  for _ in $(seq 1 60); do
    curl -fsS --max-time 3 http://127.0.0.1:8188/system_stats >/dev/null 2>&1 && break
    sleep 2
  done
fi
if curl -fsS --max-time 3 http://127.0.0.1:8188/system_stats >/dev/null 2>&1; then
  log "ComfyUI pronto"
else
  warn "ComfyUI non risponde su :8188; il bridge partirà ma aspetterà"
fi

bridge_label="com.hyperspace.comfy-bridge"
bridge_domain="gui/$(id -u)/$bridge_label"
bridge_plist="$REPO/integrations/comfyui/com.hyperspace.comfy-bridge.plist"
if launchctl print "$bridge_domain" >/dev/null 2>&1; then
  if launchctl print "$bridge_domain" 2>/dev/null | grep -q 'state = running'; then
    log "bridge ComfyUI già attivo"
  else
    launchctl kickstart "$bridge_domain"
    log "bridge ComfyUI avviato"
  fi
else
  launchctl bootstrap "gui/$(id -u)" "$bridge_plist"
  launchctl kickstart "$bridge_domain" 2>/dev/null || true
  log "bridge ComfyUI caricato e avviato"
fi

if running '[t]elegram_bot.py'; then
  log "Telegram già attivo"
else
  telegram_launcher="/Users/opo/anna-mac/scripts/start-telegram.sh"
  if [[ -x "$telegram_launcher" || -f "$telegram_launcher" ]]; then
    nohup bash "$telegram_launcher" >data/telegram-driver.log 2>data/telegram-driver.err.log &
    log "Telegram avviato (log: data/telegram-driver.log)"
  else
    warn "launcher Telegram non trovato: $telegram_launcher"
  fi
fi

if running '[n]ode serve.mjs'; then
  log "web-node locale già attivo"
else
  (
    cd "$REPO/web-node"
    nohup node serve.mjs >"$REPO/data/web-node.log" 2>"$REPO/data/web-node.err.log" &
  )
  log "web-node locale avviato su http://127.0.0.1:8790"
fi

editor_app_dir="$REPO/integrations/tiktok_editor/app"
editor_python="/Users/opo/Downloads/tiktok_editor/.venv/bin/python"
editor_domain="gui/$(id -u)/com.hyperspace.tiktok-editor"
editor_plist="$REPO/integrations/tiktok_editor/com.hyperspace.tiktok-editor.plist"
if curl -fsS --max-time 3 http://127.0.0.1:7860/ >/dev/null 2>&1; then
  log "TikTok editor già attivo su http://127.0.0.1:7860"
elif [[ -x "$editor_python" ]] && "$editor_python" "$REPO/scripts/tiktok_editor_service.py" --check >/dev/null 2>&1; then
  if launchctl print "$editor_domain" >/dev/null 2>&1; then
    launchctl kickstart -k "$editor_domain"
  else
    launchctl bootstrap "gui/$(id -u)" "$editor_plist"
  fi
  log "TikTok editor in avvio su http://127.0.0.1:7860"
else
  warn "TikTok editor opzionale non pronto in $editor_app_dir (ambiente Python: $editor_python)"
fi

reel_domain="gui/$(id -u)/com.hyperspace.reel-daily"
reel_plist="$REPO/integrations/tiktok_editor/com.hyperspace.reel-daily.plist"
if launchctl print "$reel_domain" >/dev/null 2>&1; then
  log "scheduler Reel giornaliero già caricato"
else
  launchctl bootstrap "gui/$(id -u)" "$reel_plist"
  log "scheduler Reel giornaliero caricato (idle finché non configuri una schedulazione)"
fi

sleep 2
log "PRONTO: dashboard http://127.0.0.1:8085/dashboard"
log "web-node: http://127.0.0.1:8790"
log "reel editor: http://127.0.0.1:7860 (se installato)"
log "reel scheduler: attivo, output in hyperspace_share/reel-review (revisione manuale)"
log "per ricostruire il CP: start-tutto.command --build"
