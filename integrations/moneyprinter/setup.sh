#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Prepara MoneyPrinterTurbo per la mesh: config.toml, cartelle, chiave API.
# Si può rilanciare: non sovrascrive un config.toml esistente.
#
#   PEXELS_API_KEY=... integrations/moneyprinter/setup.sh
#
# Variabili facoltative:
#   MPT_OLLAMA_URL    (default: http://100.64.31.18:11434, Ollama sull'ASUS)
#   MPT_OLLAMA_MODEL  (default: flint:latest)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
mkdir -p storage music empty-songs

[ -f music/licenze.json ] || cat > music/licenze.json <<'EOF'
{
  "_come": "Un brano per voce: nome del file in questa cartella, licenza, fonte e obbligo di attribuzione. mpt_bridge.py usa solo i brani elencati qui.",
  "brani": []
}
EOF

if [ -f config.toml ]; then
  echo "config.toml esiste già: lo lascio com'è."
else
  KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  OLLAMA_URL="${MPT_OLLAMA_URL:-http://100.64.31.18:11434}"
  OLLAMA_MODEL="${MPT_OLLAMA_MODEL:-flint:latest}"
  PEXELS="${PEXELS_API_KEY:+\"$PEXELS_API_KEY\"}"
  python3 - "$KEY" "$OLLAMA_URL" "$OLLAMA_MODEL" "$PEXELS" <<'PY'
import sys
key, url, model, pexels = sys.argv[1:5]
s = open("config.template.toml", encoding="utf-8").read()
for k, v in {"API_KEY": key, "OLLAMA_URL": url.rstrip("/"), "OLLAMA_MODEL": model, "PEXELS_KEYS": pexels}.items():
    s = s.replace("{{" + k + "}}", v)
open("config.toml", "w", encoding="utf-8").write(s)
PY
  chmod 600 config.toml
  printf 'MPT_API_URL=http://127.0.0.1:8095\nMPT_API_KEY=%s\n' "$KEY" > .env
  chmod 600 .env
  echo "Creato config.toml (modello: $OLLAMA_MODEL su $OLLAMA_URL)."
  [ -z "$PEXELS" ] && echo "Manca la chiave Pexels: aggiungila in pexels_api_keys dentro config.toml."
fi

echo
echo "Prossimi passi:"
echo "  1. Avvia Kokoro:   .venv/bin/python scripts/kokoro_tts_service.py   (porta 8880)"
echo "  2. Avvia MPT:      docker compose -f integrations/moneyprinter/docker-compose.yml up -d"
echo "     (interfaccia web: aggiungi --profile webui e apri http://127.0.0.1:8501)"
echo "  3. Prova:          .venv/bin/python integrations/moneyprinter/mpt_bridge.py \"Che cos'è una mesh di AI locali\""
