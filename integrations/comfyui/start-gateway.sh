#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Avvia il gateway WebUI (webui_gateway.py): la porta 8189 da cui Open WebUI chiede
# un'immagine. Prima di inoltrare /prompt a ComfyUI scarica Ollama per liberare la
# scheda («una scheda, un modello»); tutto il resto è inoltrato com'è.
#
# Uso:
#   integrations/comfyui/start-gateway.sh --check   # verifica e basta
#   integrations/comfyui/start-gateway.sh           # in ascolto su 127.0.0.1:8189
set -euo pipefail

REPO="${HYPERSPACE_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$REPO"

export COMFY_URL="${COMFY_URL:-http://127.0.0.1:8188}"
export OLLAMA_RAW_BASE_URL="${OLLAMA_RAW_BASE_URL:-http://127.0.0.1:11434}"
export WEBUI_GATEWAY_PORT="${WEBUI_GATEWAY_PORT:-8189}"

PYTHON=".venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="python3"

echo "[webui-gateway] avvio su 127.0.0.1:${WEBUI_GATEWAY_PORT} (ComfyUI=${COMFY_URL})..." >&2
exec "$PYTHON" integrations/comfyui/webui_gateway.py "$@"
