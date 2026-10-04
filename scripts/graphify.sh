#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# =============================================================
# HyperSpace AGI — graphify.sh
#
# Wrapper per graphify, il knowledge graph del repository. E' uno
# strumento di SVILUPPO: non fa parte dello stack di runtime, non
# gira in un container e non apre porte sullo stack (docker-compose.yml
# non cambia). Vedi docs/graphify.md.
#
# Cosa fa:
#   - verifica che graphify sia installato;
#   - si posiziona sulla root del repository, così l'output finisce in
#     graphify-out/ (ignorato da git);
#   - inoltra ogni argomento a graphify così com'e': non indovina flag e
#     non riscrive i comandi. La fonte autorevole è `graphify --help`;
#   - senza argomenti indicizza il solo codice (`extract . --code-only`):
#     AST locale, nessuna chiave, nessuna rete.
#
# Uso:
#   ./scripts/graphify.sh                              # solo codice, offline, zero chiavi
#   ./scripts/graphify.sh extract . --backend ollama   # anche i documenti, in locale
#   ./scripts/graphify.sh cluster-only .               # report + HTML (+ naming community)
#   ./scripts/graphify.sh god-nodes --top 15           # hub architetturali
#   ./scripts/graphify.sh explain "v1_chat_completions" # spiegazione di un simbolo
#   ./scripts/graphify.sh query "..." --budget 800     # BFS sul grafo
#   ./scripts/graphify.sh path "A" "B"                 # cammino tra due nodi
#   ./scripts/graphify.sh update .                     # re-indicizza il codice (no LLM)
#   ./scripts/graphify.sh --mcp                        # server MCP stdio per il coding agent
#   ./scripts/graphify.sh hook install                 # post-commit + merge driver
#
# Il comando `graphify` nudo stampa la guida, non esegue la pipeline.
#
# Prerequisito: Python >= 3.10 (verificato anche su 3.14) e, per estrarre i
# documenti con un modello locale, l'extra `[ollama]`. Installazione
# consigliata, con versione pinnata:
#   uv tool install "graphifyy[ollama]==0.9.74"
# alternativa:
#   pipx install "graphifyy[ollama]==0.9.74"
# =============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIN="0.9.74"

if ! command -v graphify >/dev/null 2>&1; then
    cat >&2 <<EOF
graphify non trovato.
Installa (Python >= 3.10), preferendo la versione pinnata:
  uv tool install "graphifyy[ollama]==${PIN}"
oppure:
  pipx install "graphifyy[ollama]==${PIN}"
Nota: l'extra [ollama] serve per estrarre i documenti con un modello locale.
EOF
    exit 1
fi

cd "$ROOT"

if [ "$#" -eq 0 ]; then
    echo "[graphify] repo: $ROOT"
    echo "[graphify] out:  $ROOT/graphify-out   (ignorato da git)"
    echo "[graphify] nessun argomento: indicizzo il solo codice (AST locale, zero"
    echo "[graphify] chiavi, zero rete). Per i documenti serve un backend esplicito:"
    echo "[graphify]   ./scripts/graphify.sh extract . --backend ollama"
    exec graphify extract . --code-only
fi

exec graphify "$@"
