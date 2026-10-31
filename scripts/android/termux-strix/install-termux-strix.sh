#!/data/data/com.termux/files/usr/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Installa il tema Strix in Termux.
# Perimetro: ~/.termux/{colors,termux}.properties, ~/.termux/strix-shell.sh e un
# blocco marcato in ~/.bashrc. I file esistenti vengono salvati in ~/.termux/strix-backup/.
#   bash install-termux-strix.sh            installa
#   bash install-termux-strix.sh --uninstall  ripristina i backup e toglie il blocco
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
T="$HOME/.termux"; BK="$T/strix-backup"
BEGIN="# >>> strix-shell >>>"; END="# <<< strix-shell <<<"
mkdir -p "$T"

strip_block() { [ -f "$HOME/.bashrc" ] && sed -i "/$BEGIN/,/$END/d" "$HOME/.bashrc" || true; }

if [ "${1:-}" = "--uninstall" ]; then
  strip_block
  rm -f "$T/strix-shell.sh"
  for f in colors.properties termux.properties; do
    [ -f "$BK/$f" ] && mv "$BK/$f" "$T/$f" || rm -f "$T/$f"
  done
  termux-reload-settings 2>/dev/null || true
  echo "Tema Strix rimosso."; exit 0
fi

mkdir -p "$BK"
for f in colors.properties termux.properties; do
  [ -f "$T/$f" ] && [ ! -f "$BK/$f" ] && cp "$T/$f" "$BK/$f"
  cp "$HERE/$f" "$T/$f"
done
cp "$HERE/strix-shell.sh" "$T/strix-shell.sh"
strip_block
printf '%s\n[ -f "$HOME/.termux/strix-shell.sh" ] && . "$HOME/.termux/strix-shell.sh"\n%s\n' "$BEGIN" "$END" >> "$HOME/.bashrc"
termux-reload-settings 2>/dev/null || true
echo "Tema Strix installato. Apri una nuova sessione (o: source ~/.bashrc)."
echo "Font consigliato: un Nerd Font in ~/.termux/font.ttf (facoltativo)."
