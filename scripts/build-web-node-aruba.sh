#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

GATEWAY_URL="${1:-https://mesh.zerozerocomputer.it}"
OUTPUT_DIR="${2:-dist/web-node-aruba}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$REPO_ROOT/$OUTPUT_DIR"
DIST_ROOT="$REPO_ROOT/dist"

mkdir -p "$TARGET/src"
mkdir -p "$DIST_ROOT"

# Copia index.html e join.html
cp "$REPO_ROOT/web-node/index.html" "$TARGET/index.html"
cp "$REPO_ROOT/web-node/join.html" "$TARGET/join.html"

# Copia pagine ausiliarie (policy, deletion, debug, ecc.)
for page in "$REPO_ROOT/web-node/"*.html; do
  name="$(basename "$page")"
  if [[ "$name" != "join.html" && "$name" != "index.html" ]]; then
    cp "$page" "$TARGET/$name"
  fi
done

# Copia .htaccess per Apache / Aruba Linux
if [[ -f "$REPO_ROOT/web-node/.htaccess" ]]; then
  cp "$REPO_ROOT/web-node/.htaccess" "$TARGET/.htaccess"
fi

# Copia ads.txt per Google AdSense, sitemap.xml e file di discovery per Agenti AI (llms.txt, robots.txt, ai-agent.json, sitemap.xml)
for root_file in ads.txt llms.txt robots.txt ai-agent.json sitemap.xml; do
  if [[ -f "$REPO_ROOT/web-node/$root_file" ]]; then
    cp "$REPO_ROOT/web-node/$root_file" "$TARGET/$root_file"
  fi
done
if [[ -d "$REPO_ROOT/web-node/.well-known" ]]; then
  mkdir -p "$TARGET/.well-known"
  cp -R "$REPO_ROOT/web-node/.well-known/." "$TARGET/.well-known/"
elif [[ -f "$REPO_ROOT/web-node/ai-agent.json" ]]; then
  mkdir -p "$TARGET/.well-known"
  cp "$REPO_ROOT/web-node/ai-agent.json" "$TARGET/.well-known/ai-agent.json"
fi

if [[ -d "$REPO_ROOT/web-node/ai" ]]; then
  mkdir -p "$TARGET/ai"
  cp -R "$REPO_ROOT/web-node/ai/." "$TARGET/ai/"
fi

if [[ -d "$REPO_ROOT/web-node/apps" ]]; then
  mkdir -p "$TARGET/apps"
  cp -R "$REPO_ROOT/web-node/apps/." "$TARGET/apps/"
  # Sicurezza: rimuovi console di amministrazione e sviluppo riservate esclusivamente al Creatore locale
  rm -f "$TARGET/apps/playground/devstudio.html"
fi

# Copia tutti i sorgenti JS
cp "$REPO_ROOT/web-node/src/"*.js "$TARGET/src/"

# Copia asset della presentazione (diagrammi PNG e PDF usati da progetto.html)
if [[ -d "$REPO_ROOT/web-node/assets" ]]; then
  mkdir -p "$TARGET/assets"
  cp -R "$REPO_ROOT/web-node/assets/." "$TARGET/assets/"
fi

# Copia PDF pubblici (tokenomics, presentazione, guida rapida) per il download
mkdir -p "$TARGET/docs"
cp "$REPO_ROOT/docs/"*.pdf "$TARGET/docs/" 2>/dev/null || true
cp "$REPO_ROOT/web-node/docs/"*.pdf "$TARGET/docs/" 2>/dev/null || true

# Genera join-config.js
ESCAPED_URL="${GATEWAY_URL%/}"
cat <<EOF > "$TARGET/join-config.js"
// SPDX-License-Identifier: Apache-2.0
window.HYPERSPACE_JOIN = Object.freeze({
  gatewayUrl: "$ESCAPED_URL",
  siteName: "ZeroZeroComputer",
  meshName: "HyperSpace",
});
EOF

# Genera cartelle per URL puliti senza estensione (es. /privacy-policy/, /cookie-policy/, /terms/, /deletion/, /chat/, /ai/, /join/, /anna/, /token/)
for ep in privacy-policy privacy cookie-policy terms deletion data-deletion chat ai join anna token; do
  if [[ -f "$TARGET/$ep.html" ]]; then
    mkdir -p "$TARGET/$ep"
    cp "$TARGET/$ep.html" "$TARGET/$ep/index.html"
  fi
done

# Crea archivio ZIP
ZIP_FILE="$TARGET.zip"
rm -f "$ZIP_FILE"
(cd "$TARGET" && zip -r -q "$ZIP_FILE" . -i '*' -i '.*')

echo "Pacchetto Aruba generato con successo: $ZIP_FILE"
