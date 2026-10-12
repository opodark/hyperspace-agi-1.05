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

# Copia index.html (join.html)
cp "$REPO_ROOT/web-node/join.html" "$TARGET/index.html"

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

# Copia tutti i sorgenti JS
cp "$REPO_ROOT/web-node/src/"*.js "$TARGET/src/"

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

# Crea archivio ZIP
ZIP_FILE="$TARGET.zip"
rm -f "$ZIP_FILE"
(cd "$TARGET" && zip -r -q "$ZIP_FILE" . -i '*' -i '.*')

echo "Pacchetto Aruba generato con successo: $ZIP_FILE"
