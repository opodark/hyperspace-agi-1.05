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

# Copia ads.txt per Google AdSense
if [[ -f "$REPO_ROOT/web-node/ads.txt" ]]; then
  cp "$REPO_ROOT/web-node/ads.txt" "$TARGET/ads.txt"
fi

# Copia tutti i sorgenti JS
cp "$REPO_ROOT/web-node/src/"*.js "$TARGET/src/"

# Copia asset della presentazione (diagrammi PNG e PDF usati da progetto.html)
if [[ -d "$REPO_ROOT/web-node/assets" ]]; then
  mkdir -p "$TARGET/assets"
  cp -R "$REPO_ROOT/web-node/assets/." "$TARGET/assets/"
fi

# Copia PDF pubblici (tokenomics, presentazione) per il download
mkdir -p "$TARGET/docs"
cp "$REPO_ROOT/docs/"*.pdf "$TARGET/docs/" 2>/dev/null || true

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

# Genera cartelle per URL puliti senza estensione (es. /privacy-policy/, /cookie-policy/, /terms/, /deletion/, /chat/, /ai/, /join/)
for ep in privacy-policy privacy cookie-policy terms deletion data-deletion chat ai join; do
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
