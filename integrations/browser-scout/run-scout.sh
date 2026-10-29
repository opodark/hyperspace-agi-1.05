#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Avvia lo scout notturno nel container isolato. Pensato per launchd
# (com.hyperspace.browser-scout.plist), ma si può lanciare a mano.
#
#   integrations/browser-scout/run-scout.sh             # giro normale
#   integrations/browser-scout/run-scout.sh --dry-run   # mostra solo le pagine scelte
#
# Configurazione (variabili d'ambiente o integrations/browser-scout/scout.env):
#   SCOUT_LLM_PROVIDER  ollama | openai            (default: ollama)
#   SCOUT_LLM_URL       endpoint del modello        (default: Ollama sull'ASUS)
#   SCOUT_LLM_MODEL     nome del modello            (default: flint:latest)
#   SCOUT_LIMIT         pagine per notte            (default: 6)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
IMAGE="hyperspace/browser-scout:0.13.14"
IN_FILE="$REPO/data/control-plane/trend_inspirations.json"
OUT_DIR="$REPO/data/scout"
LOG="$OUT_DIR/scout.log"

export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
mkdir -p "$OUT_DIR"
[ -f "$HERE/scout.env" ] && set -a && . "$HERE/scout.env" && set +a

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [browser-scout] $*" | tee -a "$LOG"; }

if ! docker info >/dev/null 2>&1; then
  log "Docker non è in esecuzione: salto il giro di stanotte."
  exit 0
fi
if [ ! -f "$IN_FILE" ]; then
  log "Manca $IN_FILE (lo produce trend_scout_reach): niente da approfondire."
  exit 0
fi
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  log "Costruisco l'immagine $IMAGE (solo la prima volta)…"
  docker build -q -t "$IMAGE" "$HERE" >>"$LOG" 2>&1
fi

log "Avvio (modello: ${SCOUT_LLM_MODEL:-flint:latest} su ${SCOUT_LLM_URL:-http://100.64.31.18:11434})"
# Isolamento del container:
# - vede solo il file d'ingresso (sola lettura) e data/scout;
# - file system di sistema in sola lettura, /tmp in memoria e cancellata a fine giro;
# - nessun privilegio, nessuna capability, limiti di memoria, CPU e processi;
# - nessun accesso a Docker, al portachiavi, ai file o alle sessioni del Mac.
docker run --rm --name hyperspace-browser-scout \
  --read-only --tmpfs /tmp:rw,size=1g,mode=1777 --shm-size=1g \
  --cap-drop ALL --security-opt no-new-privileges \
  --memory 3g --cpus 2 --pids-limit 512 \
  --add-host host.docker.internal:host-gateway \
  -v "$IN_FILE:/in/trend_inspirations.json:ro" \
  -v "$OUT_DIR:/out:rw" \
  -e SCOUT_LLM_PROVIDER="${SCOUT_LLM_PROVIDER:-ollama}" \
  -e SCOUT_LLM_URL="${SCOUT_LLM_URL:-http://100.64.31.18:11434}" \
  -e SCOUT_LLM_MODEL="${SCOUT_LLM_MODEL:-flint:latest}" \
  -e SCOUT_LLM_KEY="${SCOUT_LLM_KEY:-local}" \
  -e SCOUT_LIMIT="${SCOUT_LIMIT:-6}" \
  -e SCOUT_MAX_STEPS="${SCOUT_MAX_STEPS:-8}" \
  -e SCOUT_URL_TIMEOUT="${SCOUT_URL_TIMEOUT:-600}" \
  -e SCOUT_BUDGET_S="${SCOUT_BUDGET_S:-5400}" \
  "$IMAGE" "$@" 2>&1 | tee -a "$LOG"
status=${PIPESTATUS[0]}
log "Fine (exit $status)"
exit "$status"
