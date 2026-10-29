#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Prepara MoneyPrinterTurbo per la mesh: config.toml, cartelle, chiave API.
# Si può rilanciare: non sovrascrive un config.toml esistente.
#
#   PIXABAY_API_KEY=... integrations/moneyprinter/setup.sh   (anche PEXELS_API_KEY)
#   Con un config.toml già presente, le chiavi passate così vengono aggiunte ai campi vuoti.
#
# Variabili facoltative:
#   MPT_OLLAMA_URL    (default: http://host.docker.internal:8085, il control-plane del Mac, che sceglie il nodo; da Docker gli IP Tailscale non si raggiungono)
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
  echo "config.toml esiste già: non lo rigenero."
  # Le chiavi passate da ambiente riempiono solo i campi ancora vuoti (mai in argv).
  PIXABAY_API_KEY="${PIXABAY_API_KEY:-}" PEXELS_API_KEY="${PEXELS_API_KEY:-}" python3 - <<'PY'
import os, re
s = open("config.toml", encoding="utf-8").read()
for field, var in (("pixabay_api_keys", "PIXABAY_API_KEY"), ("pexels_api_keys", "PEXELS_API_KEY")):
    v = os.environ.get(var, "").strip()
    if v and re.search(rf"^{field}\s*=\s*\[\s*\]", s, re.M):
        s = re.sub(rf"^{field}\s*=\s*\[\s*\]", f'{field} = ["{v}"]', s, count=1, flags=re.M)
        print(f"{field}: chiave aggiunta.")
open("config.toml", "w", encoding="utf-8").write(s)
PY
else
  KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  OLLAMA_URL="${MPT_OLLAMA_URL:-http://host.docker.internal:8085}"
  OLLAMA_MODEL="${MPT_OLLAMA_MODEL:-flint:latest}"
  PEXELS="${PEXELS_API_KEY:+\"$PEXELS_API_KEY\"}"
  PIXABAY="${PIXABAY_API_KEY:+\"$PIXABAY_API_KEY\"}"
  python3 - "$KEY" "$OLLAMA_URL" "$OLLAMA_MODEL" "$PEXELS" "$PIXABAY" <<'PY'
import sys
key, url, model, pexels, pixabay = sys.argv[1:6]
s = open("config.template.toml", encoding="utf-8").read()
for k, v in {"API_KEY": key, "OLLAMA_URL": url.rstrip("/"), "OLLAMA_MODEL": model, "PEXELS_KEYS": pexels, "PIXABAY_KEYS": pixabay}.items():
    s = s.replace("{{" + k + "}}", v)
open("config.toml", "w", encoding="utf-8").write(s)
PY
  chmod 600 config.toml
  printf 'MPT_API_URL=http://127.0.0.1:8096\nMPT_API_KEY=%s\n' "$KEY" > .env
  chmod 600 .env
  echo "Creato config.toml (modello: $OLLAMA_MODEL su $OLLAMA_URL)."
  [ -z "$PEXELS$PIXABAY" ] && echo "Manca una chiave di repertorio: rilancia con PIXABAY_API_KEY=... (o aggiungila in config.toml)."
fi

echo
echo "Prossimi passi:"
echo "  1. Avvia Kokoro:   .venv/bin/python scripts/kokoro_tts_service.py   (porta 8880)"
echo "  2. Avvia MPT:      docker compose -f integrations/moneyprinter/docker-compose.yml up -d"
echo "     (interfaccia web: aggiungi --profile webui e apri http://127.0.0.1:8501)"
echo "  3. Prova:          .venv/bin/python integrations/moneyprinter/mpt_bridge.py \"Che cos'è una mesh di AI locali\""
