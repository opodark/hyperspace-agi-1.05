#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Modulo extra Qwenputer (divagr18/qwenputer, MIT): clona a un commit fissato, crea il suo
# ambiente con uv e verifica la CPU RISC-V sulla macchina di riferimento.
#
#   bash scripts/install_qwenputer.sh               # clone + test di riferimento (niente modello)
#   bash scripts/install_qwenputer.sh --in-weight   # anche il modello (~9 GB) e una chat vera in CPU
#
# --in-weight carica il modello intero (14,65 GB in bf16) in RAM: serve una macchina con >= 24 GB.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${QWENPUTER_DIR:-$ROOT/modules/qwenputer}"
REPO="https://github.com/divagr18/qwenputer.git"
COMMIT="${QWENPUTER_COMMIT:-bec1a0c9654ac8151b6f36ed0154a19c53141384}"
MODEL_ID="divagr1925/Qwen3.5-4B-Qwenputer"
IN_WEIGHT=0

for a in "$@"; do
  case "$a" in
    --in-weight) IN_WEIGHT=1 ;;
    *) echo "opzione sconosciuta: $a" >&2; exit 2 ;;
  esac
done

command -v git >/dev/null || { echo "git non trovato" >&2; exit 1; }
command -v uv >/dev/null || { echo "uv non trovato: brew install uv (oppure pip install uv)" >&2; exit 1; }

if [ ! -d "$DEST/.git" ]; then
  mkdir -p "$(dirname "$DEST")"
  git clone "$REPO" "$DEST"
fi
git -C "$DEST" fetch --quiet origin
git -C "$DEST" checkout --quiet --detach "$COMMIT"
echo "[qwenputer] $DEST @ $(git -C "$DEST" rev-parse --short HEAD)"

cd "$DEST/experimental/riscv"
uv sync --extra hf
uv run pytest -q tests/test_rv_ref.py tests/test_rv_core.py tests/test_rv_bridge.py

if [ "$IN_WEIGHT" = 1 ]; then
  ram_gb=$(uv run python -c "import os; print(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') // 2**30)")
  if [ "$ram_gb" -lt 24 ]; then
    echo "[qwenputer] RAM ${ram_gb} GB < 24 GB: il modello in-weight non entra, salto (usa OMEN o ASUS)" >&2
    exit 3
  fi
  MODEL_DIR="${QWENPUTER_MODEL_DIR:-$DEST/qwenputer-rv}"
  uv run hf download "$MODEL_ID" --local-dir "$MODEL_DIR"
  uv run python -m chipformer.rv.chat "$MODEL_DIR" --firmware tests/data/rv/calc-bridge.elf \
    --ask "Use calc: what is 123456789 * 987654321?" --check
fi
echo "[qwenputer] OK"
