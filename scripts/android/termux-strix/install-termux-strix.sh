#!/data/data/com.termux/files/usr/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Installa il tema Strix in Termux.
# Perimetro: ~/.termux/{colors,termux}.properties, ~/.termux/strix-shell.sh,
# ~/.00mesh/{anna,persona-shell}.mjs e un
# blocco marcato in ~/.bashrc. I file esistenti vengono salvati in ~/.termux/strix-backup/.
#   bash install-termux-strix.sh            installa
#   bash install-termux-strix.sh --uninstall  ripristina i backup e toglie il blocco
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
T="$HOME/.termux"; BK="$T/strix-backup"
BEGIN="# >>> strix-shell >>>"; END="# <<< strix-shell <<<"
mkdir -p "$T"

strip_block() {
  [ -f "$HOME/.bashrc" ] || return 0
  local tmp; tmp="$(mktemp)"
  sed "/$BEGIN/,/$END/d" "$HOME/.bashrc" > "$tmp" && cat "$tmp" > "$HOME/.bashrc"
  rm -f "$tmp"
}

if [ "${1:-}" = "--uninstall" ]; then
  strip_block
  rm -f "$T/strix-shell.sh" "$HOME/.00mesh/anna.mjs" "$HOME/.00mesh/persona-shell.mjs"
  for f in colors.properties termux.properties; do
    [ -f "$BK/$f" ] && mv "$BK/$f" "$T/$f" || rm -f "$T/$f"
  done
  termux-reload-settings 2>/dev/null || true
  echo "Tema Strix rimosso."; exit 0
fi

mkdir -p "$BK"
for f in colors.properties termux.properties; do
  [ -f "$T/$f" ] && [ ! -f "$BK/$f" ] && ! cmp -s "$T/$f" "$HERE/$f" && cp "$T/$f" "$BK/$f"
  cp "$HERE/$f" "$T/$f"
done
cp "$HERE/strix-shell.sh" "$T/strix-shell.sh"

# Anna: dashboard dei sogni + chat. persona-shell.mjs sta accanto allo script
# (archivio per Taildrop) oppure nel repository (scripts/persona-shell.mjs).
M="$HOME/.00mesh"; mkdir -p "$M"
cp "$HERE/anna.mjs" "$M/anna.mjs"
for ps in "$HERE/persona-shell.mjs" "$HERE/../../persona-shell.mjs"; do
  [ -f "$ps" ] && { cp "$ps" "$M/persona-shell.mjs"; break; }
done
command -v node >/dev/null 2>&1 || echo "Node manca: pkg install nodejs (serve per il comando 'anna')."
[ -f "$M/persona-shell.mjs" ] || echo "Attenzione: persona-shell.mjs non trovato, 'anna chat' non partirà."
strip_block
printf '%s\n[ -f "$HOME/.termux/strix-shell.sh" ] && . "$HOME/.termux/strix-shell.sh"\n%s\n' "$BEGIN" "$END" >> "$HOME/.bashrc"
termux-reload-settings 2>/dev/null || true
echo "Tema Strix installato. Apri una nuova sessione (o: source ~/.bashrc)."
echo "Font consigliato: un Nerd Font in ~/.termux/font.ttf (facoltativo)."
