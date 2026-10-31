# SPDX-License-Identifier: Apache-2.0
# Prompt e banner "Strix" per Termux. Caricato da ~/.bashrc (blocco marcato).
# Disattiva il banner con STRIX_BANNER=0, i colori con NO_COLOR=1.

if [ -z "${NO_COLOR:-}" ]; then
  _T=$'\[\e[38;2;87;230;217m\]'   # teal
  _G=$'\[\e[38;2;16;185;129m\]'   # verde
  _R=$'\[\e[38;2;244;63;94m\]'    # rosso
  _D=$'\[\e[38;2;71;85;105m\]'    # grigio
  _N=$'\[\e[0m\]'
else
  _T=; _G=; _R=; _D=; _N=
fi

_strix_prompt() {
  local rc=$?
  local mark="${_G}▸${_N}"
  [ $rc -ne 0 ] && mark="${_R}✗ ${rc} ▸${_N}"
  local branch=""
  branch=$(git symbolic-ref --short HEAD 2>/dev/null) && branch=" ${_D}(${branch})${_N}"
  local bat=""
  [ -n "${STRIX_BATTERY:-}" ] && command -v termux-battery-status >/dev/null 2>&1 && \
    bat=" ${_D}$(termux-battery-status 2>/dev/null | sed -n 's/.*"percentage": *\([0-9]*\).*/\1/p')%${_N}"
  PS1="${_D}┌─[${_T}strix${_D}@${_T}\h${_D}]─[${_N}\w${_D}]${_N}${branch}${bat}\n${_D}└─${_N}${mark} "
}
PROMPT_COMMAND=_strix_prompt

alias ll='ls -lAh --color=auto'
alias ls='ls --color=auto'
alias mesh='00mesh status'

strix_banner() {
  [ "${STRIX_BANNER:-1}" = 0 ] && return
  local t=$'\e[38;2;87;230;217m' d=$'\e[38;2;71;85;105m' n=$'\e[0m'
  [ -n "${NO_COLOR:-}" ] && t= d= n=
  printf '%s' "$t"
  cat <<'ART'
   ___ _____ ___ _____  __
  / __|_   _| _ \_ _\ \/ /
  \__ \ | | |   /| | >  <
  |___/ |_| |_|_\___/_/\_\
ART
  printf '%s  pocket hub · 00mesh%s\n' "$d" "$n"
  printf '%s  %s · %s%s\n\n' "$d" "$(uname -m)" "$(date '+%d/%m %H:%M')" "$n"
}
case $- in *i*) strix_banner ;; esac
