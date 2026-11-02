#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Modulo extra Resin 1.06 (ekzhang/resin, Apache-2.0): clona a un commit fissato,
# compila ed esegue i test dei crate Rust (resin-core, resin-recipe, resin-http)
# e compila l'estensione nativa Python (_resin) per HyperSpace.
#
#   bash scripts/install_resin.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${RESIN_DIR:-$ROOT/modules/resin}"
REPO="https://github.com/ekzhang/resin.git"
COMMIT="${RESIN_COMMIT:-3f68b0a5024859e0f7cef8b7a348adb8c3293c5d}"
PY_BIN="${PY_BIN:-$ROOT/.venv/bin/python}"

command -v git >/dev/null || { echo "git non trovato" >&2; exit 1; }
command -v cargo >/dev/null || { echo "cargo (Rust) non trovato: https://rustup.rs" >&2; exit 1; }

if [ ! -d "$DEST/.git" ]; then
  mkdir -p "$(dirname "$DEST")"
  git clone "$REPO" "$DEST"
fi
git -C "$DEST" fetch --quiet origin
git -C "$DEST" checkout --quiet --detach "$COMMIT"
echo "[resin] $DEST @ $(git -C "$DEST" rev-parse --short HEAD)"

cd "$DEST"
cargo test --quiet -p resin-core -p resin-recipe -p resin-http

if [ -x "$PY_BIN" ]; then
  export PYO3_PYTHON="$PY_BIN"
fi
if [ "$(uname -s)" = "Darwin" ]; then
  export RUSTFLAGS="${RUSTFLAGS:-} -C link-arg=-undefined -C link-arg=dynamic_lookup"
fi
cargo build --release -p resin-py

if [ -f "$DEST/target/release/lib_resin.dylib" ]; then
  cp "$DEST/target/release/lib_resin.dylib" "$DEST/resin/_resin.so"
elif [ -f "$DEST/target/release/lib_resin.so" ]; then
  cp "$DEST/target/release/lib_resin.so" "$DEST/resin/_resin.so"
fi

if [ -x "$PY_BIN" ]; then
  "$PY_BIN" -c "import sys; sys.path.insert(0, '$DEST'); import resin; print('[resin] Python binding OK, version:', resin.__version__)"
fi
echo "[resin] OK"
