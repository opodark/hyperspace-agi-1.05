#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Symlink last30days skill into agent skill directories across the system.
#
# Usage:
#   ./install.sh                      # link into Claude Code, Antigravity, and .agents
#   ./install.sh --claude             # link into Claude Code only
#   ./install.sh --antigravity        # link into Antigravity only
#   ./install.sh --agents             # link into ~/.agents/skills only
#   ./install.sh --workspace          # link into current workspace .agents/skills only
#   ./install.sh --all-agents         # link everywhere
#   ./install.sh --uninstall          # remove links created by this installer

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="$SCRIPT_DIR/skills/last30days"

targets=()
mode=install

if [[ $# -eq 0 ]]; then
  targets=(
    "$HOME/.claude/skills"
    "$HOME/.gemini/antigravity/skills"
    "$HOME/.agents/skills"
    "$(pwd)/.agents/skills"
  )
else
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --claude)       targets+=("$HOME/.claude/skills") ;;
      --antigravity)  targets+=("$HOME/.gemini/antigravity/skills") ;;
      --agents)       targets+=("$HOME/.agents/skills") ;;
      --workspace)    targets+=("$(pwd)/.agents/skills") ;;
      --all-agents)
        targets=(
          "$HOME/.claude/skills"
          "$HOME/.gemini/antigravity/skills"
          "$HOME/.agents/skills"
          "$HOME/.codex/skills"
          "$(pwd)/.agents/skills"
        )
        ;;
      --uninstall)    mode=uninstall ;;
      -h|--help)
        awk 'NR>1 { if ($0 !~ /^#/) exit; sub(/^# ?/, ""); print }' "${BASH_SOURCE[0]}"
        exit 0
        ;;
      *)
        echo "Unknown flag: $1" >&2
        exit 2
        ;;
    esac
    shift
  done
fi

if [[ "$mode" == "uninstall" ]]; then
  for target_dir in "${targets[@]}"; do
    dest="$target_dir/last30days"
    if [[ -L "$dest" ]]; then
      rm "$dest"
      echo "Removed link: $dest"
    fi
  done
  exit 0
fi

for target_dir in "${targets[@]}"; do
  mkdir -p "$target_dir"
  dest="$target_dir/last30days"
  if [[ -L "$dest" || -e "$dest" ]]; then
    rm -rf "$dest"
  fi
  ln -s "$SKILL_SRC" "$dest"
  echo "Installed last30days skill -> $dest"
done

echo "Last30days skill installed successfully for specified agents."
