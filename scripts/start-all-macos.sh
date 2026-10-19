#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Avvio completo HyperSpace su macOS: Docker/CP, ComfyUI, bridge, Telegram e web-node.
set -euo pipefail

REPO="${HYPERSPACE_REPO:-/Users/opo/hyperspace-agi-1.05}"
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
docker compose --profile office up -d libretranslate

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

# ── gateway WebUI (8189): la porta che Open WebUI usa per disegnare ──────────
gateway_label="com.hyperspace.webui-gateway"
gateway_domain="gui/$(id -u)/$gateway_label"
gateway_plist="$REPO/integrations/comfyui/com.hyperspace.webui-gateway.plist"
if launchctl print "$gateway_domain" >/dev/null 2>&1; then
  if launchctl print "$gateway_domain" 2>/dev/null | grep -q 'state = running'; then
    log "gateway WebUI già attivo"
  else
    launchctl kickstart "$gateway_domain"
    log "gateway WebUI avviato"
  fi
else
  launchctl bootstrap "gui/$(id -u)" "$gateway_plist"
  launchctl kickstart "$gateway_domain" 2>/dev/null || true
  log "gateway WebUI caricato e avviato"
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

if running '[i]nfobot_service.py'; then
  log "InfoBot Telegram già attivo"
else
  if [[ -f "$REPO/.venv/bin/python" && -f "$REPO/scripts/infobot_service.py" ]]; then
    nohup "$REPO/.venv/bin/python" -u "$REPO/scripts/infobot_service.py" >data/infobot.log 2>data/infobot.err.log &
    log "InfoBot Telegram avviato (log: data/infobot.log)"
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

graphify_python="$REPO/.venv/bin/python"
if curl -fsS --max-time 3 http://127.0.0.1:7871/health >/dev/null 2>&1; then
  log "superficie graphify già attiva su http://127.0.0.1:7871"
elif [[ -x "$graphify_python" ]] && "$graphify_python" "$REPO/scripts/graphify_surface.py" --check >/dev/null 2>&1; then
  nohup "$graphify_python" "$REPO/scripts/graphify_surface.py" \
    >"$REPO/data/graphify-surface.log" 2>"$REPO/data/graphify-surface.err.log" &
  log "superficie graphify in avvio su http://127.0.0.1:7871"
else
  log "superficie graphify non avviata: genera prima il grafo con ./scripts/graphify.sh"
fi

# Motore nativo facoltativo per la superficie REA: Ghidra piu' il suo JDK.
# Si esporta solo se i percorsi esistono; una variabile gia' impostata vince.
ghidra_dir="${GHIDRA_INSTALL_DIR:-$HOME/ghidra_12.1.4_PUBLIC}"
java_home="${JAVA_HOME:-/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home}"
if [[ -d "$ghidra_dir" && -x "$java_home/bin/java" ]]; then
  export GHIDRA_INSTALL_DIR="$ghidra_dir"
  export JAVA_HOME="$java_home"
  log "motore nativo REA disponibile: Ghidra in $ghidra_dir (JDK in $java_home)"
else
  log "motore nativo REA assente: restano le operazioni statiche (servono Ghidra e un JDK)"
fi

rea_python="$REPO/.venv/bin/python"
if curl -fsS --max-time 3 http://127.0.0.1:7872/health >/dev/null 2>&1; then
  log "superficie REA già attiva su http://127.0.0.1:7872"
elif [[ -x "$rea_python" ]] && "$rea_python" "$REPO/scripts/rea_surface.py" --check >/dev/null 2>&1; then
  nohup "$rea_python" "$REPO/scripts/rea_surface.py" \
    >"$REPO/data/rea-surface.log" 2>"$REPO/data/rea-surface.err.log" &
  log "superficie REA in avvio su http://127.0.0.1:7872"
else
  log "superficie REA non avviata: senza rea nel PATH non c'è niente da analizzare (npm install --global rea-agents)"
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
log "grafo del repository: http://127.0.0.1:7871 (se il grafo è stato generato)"
log "reel editor: http://127.0.0.1:7860 (se installato)"
log "reel scheduler: attivo, output in hyperspace_share/reel-review (revisione manuale)"
log "per ricostruire il CP: start-tutto.command --build"
