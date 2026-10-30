#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# scripts/persona_console.py
"""Console della persona con un tool `shell` locale, eseguito solo su conferma.

Prototipo. Parla con `/v1/chat/completions` del control-plane, dove vive la
persona di HyperSpace: la superficie `terminal` la attiva con un tono asciutto, e
l'header `X-Hyperspace-Tools: off` fa passare SOLO il tool di questo client (niente
web_search/mesh/connettori del CP). Il modello può chiedere di eseguire un comando
di shell: la console lo mostra e lo lancia **solo** se l'operatore conferma.

Uso:
  python3 scripts/persona_console.py
  python3 scripts/persona_console.py --model qwen3-8b-abliterated:latest
  echo "che versione di python ho? usa la shell" | python3 scripts/persona_console.py --auto-deny

Sicurezza: ogni comando è fuori dal sandbox e gira sul Mac. Di default ogni
comando chiede conferma (default: NO). `--auto-deny` rifiuta tutto (per i test);
`a` durante una conferma approva il resto della sessione (comodo, ma rischioso).
"""

import argparse
import json
import os
import subprocess
import sys
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


def _run_shell(command):
    """Esegue il comando e torna un riassunto testuale (stdout/stderr/rc)."""
    try:
        done = subprocess.run(["bash", "-lc", command], capture_output=True,
                              text=True, timeout=CMD_TIMEOUT)
    except subprocess.TimeoutExpired:
        return f"[timeout dopo {CMD_TIMEOUT}s]"
    except Exception as error:  # noqa: BLE001 — in un prototipo riportiamo e basta
        return f"[errore di esecuzione: {error}]"
    parti = [f"exit_code: {done.returncode}"]
    if done.stdout.strip():
        parti.append("stdout:\n" + done.stdout.strip())
    if done.stderr.strip():
        parti.append("stderr:\n" + done.stderr.strip())
    testo = "\n".join(parti)
    return testo[:MAX_OUTPUT] + ("\n…[troncato]" if len(testo) > MAX_OUTPUT else "")


def _confirm(command, explanation, state):
    """True se eseguire. Rispetta --auto-deny e la modalità 'always' di sessione."""
    print("\n  \033[1mLa persona vuole eseguire:\033[0m")
    if explanation:
        print(f"    scopo: {explanation}")
    print(f"    $ {command}")
    if state["auto_deny"]:
        print("  [--auto-deny] rifiutato.")
        return False
    if state["always"]:
        print("  [sessione: approva tutto] eseguo.")
        return True
    try:
        scelta = input("  [e]segui / [n]o / [a] approva tutto » ").strip().lower()
    except EOFError:
        return False
    if scelta == "a":
        state["always"] = True
        return True
    return scelta in ("e", "s", "y", "yes")


def main():
    ap = argparse.ArgumentParser(description="Console della persona con tool shell su conferma.")
    ap.add_argument("--cp-url", default=os.getenv("CP_URL", "http://localhost:8085"))
    ap.add_argument("--model", default=os.getenv("PERSONA_CONSOLE_MODEL", "qwen3-8b-abliterated:latest"))
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--auto-deny", action="store_true", help="rifiuta ogni comando (per i test)")
    args = ap.parse_args()

    url = args.cp_url.rstrip("/") + "/v1/chat/completions"
    state = {"always": False, "auto_deny": args.auto_deny}
    messages = []
    interactive = sys.stdin.isatty()

    print(f"Persona console · modello {args.model} · CP {args.cp_url}")
    print("Scrivi un messaggio (Ctrl-D o 'exit' per uscire). I comandi shell chiedono conferma.\n")

    while True:
        try:
            testo = input("› ").strip() if interactive else sys.stdin.readline()
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
            payload = {"model": args.model, "messages": messages, "tools": [SHELL_TOOL],
                       "stream": False}
            try:
                resp = _post(url, payload, args.timeout)
            except urllib.error.HTTPError as error:
                print(f"  [errore HTTP {error.code}] {error.read().decode('utf-8', 'ignore')[:300]}")
                break
            except Exception as error:  # noqa: BLE001
                print(f"  [errore di connessione] {error}")
                break

            try:
                message = resp["choices"][0]["message"]
            except (KeyError, IndexError):
                print(f"  [risposta inattesa] {json.dumps(resp)[:300]}")
                break

            tool_calls = message.get("tool_calls") or []
            messages.append({"role": "assistant",
                             "content": message.get("content") or "",
                             **({"tool_calls": tool_calls} if tool_calls else {})})

            if not tool_calls:
                contenuto = (message.get("content") or "").strip()
                print(f"\n{contenuto}\n" if contenuto else "\n[nessun testo]\n")
                break

            for call in tool_calls:
                fn = call.get("function", {})
                if fn.get("name") != "shell":
                    risultato = f"[tool sconosciuto: {fn.get('name')}]"
                else:
                    try:
                        args_json = json.loads(fn.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args_json = {}
                    command = str(args_json.get("command", "")).strip()
                    explanation = str(args_json.get("explanation", "")).strip()
                    if not command:
                        risultato = "[nessun comando fornito]"
                    elif _confirm(command, explanation, state):
                        risultato = _run_shell(command)
                        print(f"  → exit {risultato.splitlines()[0].split(': ')[-1]}")
                    else:
                        risultato = "[comando rifiutato dall'operatore]"
                messages.append({"role": "tool",
                                 "tool_call_id": call.get("id", ""),
                                 "content": risultato})
        else:
            print("  [troppe tool call consecutive: mi fermo]")

    print("\nChiuso.")


if __name__ == "__main__":
    main()
