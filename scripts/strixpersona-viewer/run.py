#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# scripts/strixpersona-viewer/run.py
"""Fork fedele del viewer live di Strix: stessa SPA, stesso container sandbox,
rotte dietro il nostro CP + persona invece del motore di Strix.

Stesso stile di comando di `strix`/`strixpersona.mjs` (-t, -m, --max-turns), ma
qui la conferma di ogni comando shell arriva DAL BROWSER: il box "Send a live
prompt to the running pentest…" del viewer reale è il canale di conferma
(scrivi sì/no lì). Il comando, una volta confermato, gira con `docker exec`
dentro un container `strix-sandbox` dedicato — isolato dall'host, con Caido e
i certificati già pronti, come nel vero Strix.

Uso:
  python3 scripts/strixpersona-viewer/run.py -t /Users/opo/hyperspace-agi-1.04/infra-ui -m quick --max-turns 20
  python3 scripts/strixpersona-viewer/run.py -t ./app --instruction "Cerca secret in chiaro" -m deep

Sicurezza: il bundle è lo stesso di Strix ma la verifica email non serve a
nulla qui (sempre "non verificato": non blocca il run live). Il link stampato
contiene il token di sessione — non condividerlo.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from live_view import TuiLiveView  # noqa: E402
from server import ViewerState, serve  # noqa: E402

SANDBOX_IMAGE = "ghcr.io/usestrix/strix-sandbox:latest"
SHELL_TOOL = {
    "type": "function",
    "function": {
        "name": "shell",
        "description": "Esegue un comando di shell dentro il container sandbox, sul "
                       "bersaglio montato. Ogni comando richiede conferma dell'operatore "
                       "nel browser prima di partire.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "explanation": {"type": "string"},
            },
            "required": ["command"],
        },
    },
}
MODES = {
    "quick": "Giro rapido: concentrati sui difetti più evidenti, poche verifiche mirate.",
    "standard": "Giro standard: esplora con ordine, verifica le ipotesi principali prima di concludere.",
    "deep": "Giro approfondito: esplora a fondo, verifica più ipotesi, non fermarti al primo indizio.",
}
MAX_OUTPUT = 4000
ROOT_AGENT = "root"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-t", "--target", action="append", required=True, dest="targets")
    ap.add_argument("-m", "--mode", choices=sorted(MODES), default="quick")
    ap.add_argument("--max-turns", type=int, default=20)
    ap.add_argument("--instruction", default="")
    ap.add_argument("--model", default="qwen3-8b-abliterated:latest")
    ap.add_argument("--persona", default="persona")
    ap.add_argument("--cp-url", default="http://localhost:8085")
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--no-browser", action="store_true")
    return ap.parse_args()


# ── control-plane ─────────────────────────────────────────────────────────
def post_chat(cp_url: str, model: str, messages: list, timeout: int) -> dict:
    body = json.dumps({"model": model, "messages": messages, "tools": [SHELL_TOOL],
                       "stream": False}).encode("utf-8")
    req = urllib.request.Request(cp_url.rstrip("/") + "/v1/chat/completions", body, {
        "Content-Type": "application/json",
        "Authorization": "Bearer strixpersona-viewer",
        "X-Hyperspace-Tools": "off",
        "X-Hyperspace-Surface": "terminal",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── container sandbox ────────────────────────────────────────────────────
def start_sandbox(target: str) -> str:
    name = f"strixpersona-{int(time.time())}"
    cmd = ["docker", "run", "-d", "--name", name]
    local = Path(target)
    if local.exists() and local.is_dir():
        cmd += ["-v", f"{local.resolve()}:/workspace"]
    cmd += [SANDBOX_IMAGE, "sleep", "infinity"]
    subprocess.run(cmd, check=True, capture_output=True)
    for _ in range(30):
        probe = subprocess.run(["docker", "exec", "-u", "pentester", name, "true"],
                               capture_output=True)
        if probe.returncode == 0:
            return name
        time.sleep(1)
    raise RuntimeError(f"sandbox {name} non è diventato pronto in tempo")


def stop_sandbox(name: str) -> None:
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def run_in_sandbox(container: str, command: str) -> tuple[str, int | None]:
    try:
        done = subprocess.run(
            ["docker", "exec", "-u", "pentester", "-w", "/workspace", container, "bash", "-lc", command],
            capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        return "[timeout dopo 120s]", None
    parts = [f"exit_code: {done.returncode}"]
    if done.stdout.strip():
        parts.append("stdout:\n" + done.stdout.strip())
    if done.stderr.strip():
        parts.append("stderr:\n" + done.stderr.strip())
    text = "\n".join(parts)
    return (text[:MAX_OUTPUT] + "\n…[troncato]" if len(text) > MAX_OUTPUT else text), done.returncode


def build_objective(targets: list[str], mode: str, max_turns: int, instruction: str) -> str:
    righe = "\n".join(f"- {t}" for t in targets)
    istruzione = instruction or (
        "Analizza il bersaglio con il tool shell: cerca difetti di sicurezza, errori "
        "evidenti o comportamenti sospetti. Guarda solo dentro il bersaglio indicato."
    )
    return (
        f"Bersaglio(i):\n{righe}\n\nModalità: {mode}. {MODES[mode]}\n"
        f"Hai al massimo {max_turns} passi di tool a disposizione: usali con criterio.\n\n"
        f"{istruzione}\n\n"
        "Quando hai finito, o hai raccolto abbastanza per un verdetto, scrivi una sintesi "
        "finale in italiano SENZA richiedere altri tool: cosa hai trovato, dove, e la gravità."
    )


def main() -> None:
    args = parse_args()
    print(f"Avvio sandbox ({SANDBOX_IMAGE}) su {args.targets[0]}…")
    container = start_sandbox(args.targets[0])
    print(f"Sandbox pronta: {container}")

    view = TuiLiveView()
    view.upsert_agent(ROOT_AGENT, name=args.persona, status="running")
    run_record = {
        "run_name": container,
        "targets_info": [{"original": t} for t in args.targets],
        "scan_mode": args.mode,
        "status": "running",
        "start_time": datetime.now(UTC).isoformat(),
        "end_time": None,
        "finished": False,
    }
    state = ViewerState(view, run_record)
    httpd, link = serve(state, open_browser=not args.no_browser)
    print(f"Viewer: {link}")
    print("La conferma di ogni comando shell arriva dal box 'Send a live prompt' nel browser (sì/no).\n")

    objective = build_objective(args.targets, args.mode, args.max_turns, args.instruction)
    view.record_user_message(ROOT_AGENT, objective)
    messages = [{"role": "user", "content": objective}]

    status = "completed"
    try:
        for turno in range(1, args.max_turns + 1):
            print(f"[passo {turno}/{args.max_turns}] chiedo al modello…")
            try:
                resp = post_chat(args.cp_url, args.model, messages, args.timeout)
            except (urllib.error.URLError, TimeoutError) as error:
                view.record_agent_error(ROOT_AGENT, str(error))
                status = "failed"
                break
            message = resp.get("choices", [{}])[0].get("message", {})
            tool_calls = message.get("tool_calls") or []
            messages.append({"role": "assistant", "content": message.get("content") or "",
                            **({"tool_calls": tool_calls} if tool_calls else {})})

            if not tool_calls:
                verdetto = (message.get("content") or "").strip() or "[nessun testo]"
                view.record_assistant_message(ROOT_AGENT, verdetto)
                print(f"[sintesi] {verdetto}")
                break

            for call in tool_calls:
                fn = call.get("function", {})
                call_id = call.get("id", f"call_{turno}")
                if fn.get("name") != "shell":
                    result = f"[tool sconosciuto: {fn.get('name')}]"
                    view.record_tool_call(ROOT_AGENT, call_id, fn.get("name", "?"), {})
                    view.record_tool_output(ROOT_AGENT, call_id, fn.get("name", "?"), result, status="failed")
                else:
                    try:
                        call_args = json.loads(fn.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        call_args = {}
                    command = str(call_args.get("command", "")).strip()
                    explanation = str(call_args.get("explanation", "")).strip()
                    view.record_tool_call(ROOT_AGENT, call_id, "shell", call_args)
                    view.record_assistant_message(
                        ROOT_AGENT,
                        f"Vuoi che esegua questo comando?\n`$ {command}`\n"
                        f"({explanation or 'nessuna spiegazione fornita'})\n"
                        "Rispondi sì o no nel campo qui sotto.",
                    )
                    print(f"[conferma] in attesa nel browser per: $ {command}")
                    approvato = state.ask_confirmation(ROOT_AGENT, command, explanation)
                    if approvato and command:
                        print(f"[eseguo] $ {command}")
                        result, rc = run_in_sandbox(container, command)
                        view.record_tool_output(ROOT_AGENT, call_id, "shell", result,
                                                status="completed" if rc == 0 else "failed")
                    else:
                        result = "[comando rifiutato dall'operatore o nessuna risposta in tempo]"
                        view.record_tool_output(ROOT_AGENT, call_id, "shell", result, status="failed")
                        print("[rifiutato] comando non eseguito.")
                messages.append({"role": "tool", "tool_call_id": call_id, "content": result})
        else:
            view.record_assistant_message(ROOT_AGENT, f"max-turns ({args.max_turns}) raggiunto senza una sintesi finale.")
            status = "stopped"
    finally:
        view.upsert_agent(ROOT_AGENT, status=status)
        state.run_record["status"] = status
        state.run_record["end_time"] = datetime.now(UTC).isoformat()
        state.run_record["finished"] = True
        print(f"\nRun terminata ({status}). Il viewer resta aperto; Ctrl-C per chiudere e smontare la sandbox.")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
        httpd.shutdown()
        stop_sandbox(container)
        print("Sandbox smontata.")


if __name__ == "__main__":
    main()
