#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# scripts/persona_console.py
"""Console della persona con un tool `shell` locale, eseguito solo su conferma.

Terminale in stile Strix: la persona di HyperSpace risponde dentro pannelli, e
quando vuole eseguire un comando lo mostra in un riquadro ben visibile e parte
SOLO se l'operatore conferma.

Parla con `/v1/chat/completions` del control-plane: la superficie `terminal`
attiva la persona con tono asciutto, e l'header `X-Hyperspace-Tools: off` fa
passare SOLO il tool di questo client (niente web_search/mesh/connettori del CP).

Uso:
  python3 scripts/persona_console.py
  python3 scripts/persona_console.py --model qwen3-8b-abliterated:latest
  echo "che versione di python ho? usa la shell" | python3 scripts/persona_console.py --auto-deny

Sicurezza: ogni comando è fuori dal sandbox e gira sul Mac. Di default ogni
comando chiede conferma (default: NO). `--auto-deny` rifiuta tutto (per i test);
`a` durante una conferma approva il resto della sessione (comodo, ma rischioso).
Solo stdlib: nessuna dipendenza.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request

SHELL_TOOL = {
    "type": "function",
    "function": {
        "name": "shell",
        "description": "Esegue un comando di shell sul computer locale dell'operatore "
                       "e restituisce stdout, stderr e codice di uscita. Ogni comando "
                       "richiede la conferma esplicita dell'operatore prima di partire.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Il comando da eseguire (bash -lc)."},
                "explanation": {"type": "string",
                                "description": "Una riga: a cosa serve questo comando."},
            },
            "required": ["command"],
        },
    },
}

MAX_OUTPUT = 4000      # caratteri di output restituiti al modello
CMD_TIMEOUT = 120      # secondi per comando
MAX_TOOL_HOPS = 8      # tool call consecutive prima di fermarsi
PERSONA_FALLBACK = "persona"

# ── UI: colori e pannelli (ANSI, stdlib) ──────────────────────────────────────
_COLOR = sys.stdout.isatty() and os.getenv("NO_COLOR") is None


def _c(code):
    return code if _COLOR else ""


RESET = _c("\033[0m")
DIM = _c("\033[2m")
BOLD = _c("\033[1m")
CYAN = _c("\033[36m")
MAGENTA = _c("\033[35m")
AMBER = _c("\033[33m")
GREEN = _c("\033[32m")
RED = _c("\033[31m")
GREY = _c("\033[90m")


def _width():
    return max(44, min(shutil.get_terminal_size((100, 24)).columns, 100))


def _panel(title, body, accent=CYAN, foot=""):
    """Disegna un pannello con bordo arrotondato. `body` è testo (può avere \\n)."""
    w = _width()
    inner = w - 4
    top = f"{accent}╭─ {BOLD}{title}{RESET}{accent} " + "─" * max(0, inner - len(title) - 1) + f"╮{RESET}"
    lines = [top]
    for raw in body.split("\n"):
        for seg in (textwrap.wrap(raw, inner) or [""]):
            lines.append(f"{accent}│{RESET} {seg}{' ' * (inner - len(seg))} {accent}│{RESET}")
    if foot:
        lines.append(f"{accent}│ {DIM}{foot}{RESET}{' ' * (inner - len(foot))}{accent} │{RESET}")
    lines.append(f"{accent}╰" + "─" * (w - 2) + f"╯{RESET}")
    print("\n".join(lines))


def _banner(model, cp_url):
    w = _width()
    print(f"{CYAN}{'━' * w}{RESET}")
    print(f"{BOLD}{MAGENTA}  ◢◤ PERSONA CONSOLE{RESET}  {DIM}shell su conferma · stile Strix{RESET}")
    print(f"{GREY}  modello {model} · CP {cp_url}{RESET}")
    print(f"{GREY}  comandi: scrivi e invio · 'exit' esce · ogni shell chiede conferma{RESET}")
    print(f"{CYAN}{'━' * w}{RESET}")


# ── rete: la chiamata al control-plane ────────────────────────────────────────
def _post(url, payload, timeout):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, body, {
        "Content-Type": "application/json",
        "Authorization": "Bearer persona-console",
        "X-Hyperspace-Tools": "off",          # solo il nostro tool, niente builtin del CP
        "X-Hyperspace-Surface": "terminal",   # superficie che attiva la persona
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── la shell locale ───────────────────────────────────────────────────────────
def _run_shell(command):
    """Esegue il comando e torna (riassunto_per_il_modello, exit_code)."""
    try:
        done = subprocess.run(["bash", "-lc", command], capture_output=True,
                              text=True, timeout=CMD_TIMEOUT)
    except subprocess.TimeoutExpired:
        return f"[timeout dopo {CMD_TIMEOUT}s]", None
    except Exception as error:  # noqa: BLE001 — in un prototipo riportiamo e basta
        return f"[errore di esecuzione: {error}]", None
    parti = [f"exit_code: {done.returncode}"]
    if done.stdout.strip():
        parti.append("stdout:\n" + done.stdout.strip())
    if done.stderr.strip():
        parti.append("stderr:\n" + done.stderr.strip())
    testo = "\n".join(parti)
    testo = testo[:MAX_OUTPUT] + ("\n…[troncato]" if len(testo) > MAX_OUTPUT else "")
    return testo, done.returncode


def _confirm(command, explanation, state):
    """True se eseguire. Rispetta --auto-deny e la modalità 'always' di sessione."""
    corpo = (f"scopo: {explanation}\n" if explanation else "") + f"$ {command}"
    _panel("SHELL · conferma richiesta", corpo, accent=AMBER)
    if state["auto_deny"]:
        print(f"{RED}  [--auto-deny] rifiutato.{RESET}")
        return False
    if state["always"]:
        print(f"{GREEN}  [sessione: approva tutto] eseguo.{RESET}")
        return True
    try:
        scelta = input(f"{AMBER}  esegui? [e/N/a (tutto)] » {RESET}").strip().lower()
    except EOFError:
        return False
    if scelta == "a":
        state["always"] = True
        return True
    return scelta in ("e", "s", "y", "yes")


def _persona_name(resp_message):
    """Nome mostrato nel pannello: il modello non lo dà, resta un'etichetta fissa."""
    return resp_message or PERSONA_FALLBACK


def main():
    ap = argparse.ArgumentParser(description="Console della persona con tool shell su conferma.")
    ap.add_argument("--cp-url", default=os.getenv("CP_URL", "http://localhost:8085"))
    ap.add_argument("--model", default=os.getenv("PERSONA_CONSOLE_MODEL", "qwen3-8b-abliterated:latest"))
    ap.add_argument("--persona", default=os.getenv("PERSONA_CONSOLE_NAME", "persona"),
                    help="etichetta mostrata nei pannelli delle risposte")
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--auto-deny", action="store_true", help="rifiuta ogni comando (per i test)")
    args = ap.parse_args()

    url = args.cp_url.rstrip("/") + "/v1/chat/completions"
    state = {"always": False, "auto_deny": args.auto_deny}
    messages = []
    interactive = sys.stdin.isatty()

    _banner(args.model, args.cp_url)

    while True:
        try:
            testo = input(f"\n{BOLD}{CYAN}› {RESET}") if interactive else sys.stdin.readline()
        except EOFError:
            break
        if not interactive and not testo:
            break
        testo = testo.strip()
        if not testo:
            continue
        if testo.lower() in ("exit", "quit", ":q"):
            break

        messages.append({"role": "user", "content": testo})

        for _ in range(MAX_TOOL_HOPS):
            if interactive:
                print(f"{DIM}  … la persona sta pensando{RESET}", end="\r")
            payload = {"model": args.model, "messages": messages, "tools": [SHELL_TOOL],
                       "stream": False}
            try:
                resp = _post(url, payload, args.timeout)
            except urllib.error.HTTPError as error:
                _panel("errore HTTP", f"{error.code}\n{error.read().decode('utf-8', 'ignore')[:400]}", accent=RED)
                break
            except Exception as error:  # noqa: BLE001
                _panel("errore di connessione", str(error), accent=RED)
                break
            if interactive:
                print(" " * 40, end="\r")

            try:
                message = resp["choices"][0]["message"]
            except (KeyError, IndexError):
                _panel("risposta inattesa", json.dumps(resp)[:400], accent=RED)
                break

            tool_calls = message.get("tool_calls") or []
            messages.append({"role": "assistant",
                             "content": message.get("content") or "",
                             **({"tool_calls": tool_calls} if tool_calls else {})})

            if not tool_calls:
                contenuto = (message.get("content") or "").strip()
                _panel(args.persona, contenuto or "[nessun testo]", accent=MAGENTA)
                break

            for call in tool_calls:
                fn = call.get("function", {})
                if fn.get("name") != "shell":
                    risultato, rc = f"[tool sconosciuto: {fn.get('name')}]", None
                else:
                    try:
                        args_json = json.loads(fn.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args_json = {}
                    command = str(args_json.get("command", "")).strip()
                    explanation = str(args_json.get("explanation", "")).strip()
                    if not command:
                        risultato, rc = "[nessun comando fornito]", None
                    elif _confirm(command, explanation, state):
                        risultato, rc = _run_shell(command)
                        colore = GREEN if rc == 0 else AMBER
                        _panel(f"output · exit {rc}", risultato, accent=colore)
                    else:
                        risultato, rc = "[comando rifiutato dall'operatore]", None
                        print(f"{GREY}  comando non eseguito.{RESET}")
                messages.append({"role": "tool",
                                 "tool_call_id": call.get("id", ""),
                                 "content": risultato})
        else:
            _panel("stop", "troppe tool call consecutive: mi fermo.", accent=RED)

    print(f"\n{GREY}Chiuso.{RESET}")


if __name__ == "__main__":
    main()
