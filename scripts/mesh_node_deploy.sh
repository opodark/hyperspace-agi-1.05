#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Deploy del nodo Git Mesh (Mac/Linux): pull, rebuild container e avvio watcher.
#
# Il nodo (container) ha /repo in sola lettura, quindi riceve e VERIFICA le patch
# ma le deposita in <data>/node-1/mesh-patches/. Questo script ricompila il nodo
# con il codice nuovo e avvia il watcher sull'host, che è l'unico processo
# autorizzato ad applicare le patch al repository.
#
# Uso:
#   bash scripts/mesh_node_deploy.sh                    # rebuild + watcher
#   bash scripts/mesh_node_deploy.sh --pull             # prima: git pull
#   bash scripts/mesh_node_deploy.sh --test http://127.0.0.1:8081   # + test propagazione
set -euo pipefail
cd "$(dirname "$0")/.."

PULL=false
TEST=false
TARGET="http://127.0.0.1:8081"
for arg in "$@"; do
  case "$arg" in
    --pull) PULL=true ;;
    --test) TEST=true ;;
    http*)   TARGET="$arg" ;;
  esac
done

if $PULL; then
  echo "[deploy] git pull..."
  git fetch origin --prune
  git pull --ff-only
fi

echo "[deploy] rebuild container (control-plane + nodo)..."
docker compose up -d --build control-plane node-1

if pgrep -f 'mesh_patch_watcher.py' >/dev/null; then
  echo "[deploy] watcher già attivo"
else
  nohup .venv/bin/python scripts/mesh_patch_watcher.py \
    --patches data/node-1/mesh-patches --repo . > /tmp/mesh-watcher.log 2>&1 &
  echo "[deploy] watcher avviato (pid=$!)"
fi

if $TEST; then
  echo "[deploy] test di propagazione verso $TARGET"
  .venv/bin/python scripts/mesh_distribute.py --files README.md --target "$TARGET"
fi
