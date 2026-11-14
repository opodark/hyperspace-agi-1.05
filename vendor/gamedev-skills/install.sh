#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Symlink awesome-gamedev-agent-skills (router by default, plus optional skills/categories)
# into agent skill directories across the system.
#
# Usage:
#   ./install.sh                            # link router into Claude Code, Antigravity, ~/.agents, and workspace .agents
#   ./install.sh --claude                   # link into Claude Code only
#   ./install.sh --antigravity              # link into Antigravity only
#   ./install.sh --agents                   # link into ~/.agents/skills only
#   ./install.sh --workspace                # link into current workspace .agents/skills only
#   ./install.sh --all-agents               # link into Claude, Antigravity, ~/.agents, ~/.codex, and workspace .agents
#   ./install.sh --all-skills               # link router plus all 79 gamedev skills
#   ./install.sh --category <cat>           # link router plus all skills in a category (repeatable)
#   ./install.sh --skill <name>             # link router plus a specific skill by name (repeatable)
#   ./install.sh --uninstall                # remove links created by this installer

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

targets=()
selected_categories=()
selected_skills=()
install_all_skills=false
mode=install

while [[ $# -gt 0 ]]; do
  case "$1" in
    --claude)       targets+=("$HOME/.claude/skills") ;;
    --antigravity)  targets+=("$HOME/.gemini/antigravity/skills") ;;
    --agents)       targets+=("$HOME/.agents/skills") ;;
    --workspace)    targets+=("$(pwd)/.agents/skills") ;;
    --all-agents)
      targets+=(
        "$HOME/.claude/skills"
        "$HOME/.gemini/antigravity/skills"
        "$HOME/.agents/skills"
        "$HOME/.codex/skills"
        "$(pwd)/.agents/skills"
      )
      ;;
    --all-skills)   install_all_skills=true ;;
    --category)
      if [[ $# -lt 2 ]]; then
        echo "Missing argument for --category" >&2
        exit 2
      fi
      selected_categories+=("$2")
      shift
      ;;
    --skill)
      if [[ $# -lt 2 ]]; then
        echo "Missing argument for --skill" >&2
        exit 2
      fi
      selected_skills+=("$2")
      shift
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

if [[ ${#targets[@]} -eq 0 ]]; then
  targets=(
    "$HOME/.claude/skills"
    "$HOME/.gemini/antigravity/skills"
    "$HOME/.agents/skills"
    "$(pwd)/.agents/skills"
  )
fi

skill_sources=("$SCRIPT_DIR/router")

if [[ "$install_all_skills" == true ]]; then
  while IFS= read -r skill_md; do
    skill_sources+=("$(dirname "$skill_md")")
  done < <(find "$SCRIPT_DIR/skills" -mindepth 3 -maxdepth 3 -name "SKILL.md" -type f | sort)
else
  if [[ ${#selected_categories[@]} -gt 0 ]]; then
    for cat in "${selected_categories[@]}"; do
      cat_dir="$SCRIPT_DIR/skills/$cat"
      if [[ ! -d "$cat_dir" ]]; then
        echo "Unknown category: $cat" >&2
        exit 2
      fi
      while IFS= read -r skill_md; do
        skill_sources+=("$(dirname "$skill_md")")
      done < <(find "$cat_dir" -mindepth 2 -maxdepth 2 -name "SKILL.md" -type f | sort)
    done
  fi

  if [[ ${#selected_skills[@]} -gt 0 ]]; then
    for name in "${selected_skills[@]}"; do
      found=""
      while IFS= read -r skill_md; do
        found="$(dirname "$skill_md")"
        break
      done < <(find "$SCRIPT_DIR/skills" -mindepth 3 -maxdepth 3 -path "*/$name/SKILL.md" -type f | sort)
      if [[ -z "$found" ]]; then
        echo "Unknown skill: $name" >&2
        exit 2
      fi
      skill_sources+=("$found")
    done
  fi
fi

# Deduplicate skill_sources while preserving order
unique_sources=()
for src in "${skill_sources[@]}"; do
  seen=false
  for existing in ${unique_sources[@]+"${unique_sources[@]}"}; do
    if [[ "$existing" == "$src" ]]; then
      seen=true
      break
    fi
  done
  if [[ "$seen" == false ]]; then
    unique_sources+=("$src")
  fi
done

if [[ "$mode" == "uninstall" ]]; then
  for target_dir in "${targets[@]}"; do
    [[ -d "$target_dir" ]] || continue
    if [[ "$install_all_skills" == false && ${#selected_categories[@]} -eq 0 && ${#selected_skills[@]} -eq 0 ]]; then
      # Remove router and any symlink pointing inside $SCRIPT_DIR
      for entry in "$target_dir"/*; do
        [[ -L "$entry" ]] || continue
        link_target="$(readlink "$entry" || true)"
        if [[ "$link_target" == "$SCRIPT_DIR/"* ]]; then
          rm "$entry"
          echo "Removed link: $entry"
        fi
      done
    else
      for src in "${unique_sources[@]}"; do
        dest="$target_dir/$(basename "$src")"
        if [[ -L "$dest" ]]; then
          rm "$dest"
          echo "Removed link: $dest"
        fi
      done
    fi
  done
  exit 0
fi

for target_dir in "${targets[@]}"; do
  mkdir -p "$target_dir"
  for src in "${unique_sources[@]}"; do
    name="$(basename "$src")"
    dest="$target_dir/$name"
    if [[ -L "$dest" || -e "$dest" ]]; then
      rm -rf "$dest"
    fi
    ln -s "$src" "$dest"
    echo "Installed $name -> $dest"
  done
done

echo "awesome-gamedev-agent-skills installed successfully (${#unique_sources[@]} skill(s)) for specified agents."
