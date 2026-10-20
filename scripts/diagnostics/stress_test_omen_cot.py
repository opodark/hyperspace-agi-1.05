#!/usr/bin/env python3
"""
Stress Test Notturno per HP OMEN 16 (LFM2.5 24B/8B Ibrido su Rete AC).
Valuta la Chain-of-Thought (CoT), la generazione di pagine/servizi sotto le regole di AGENTS.md,
il consumo di token e la validità sintattica del codice prodotto, con carico zero sul Mac.

Uso:
    .venv/bin/python scripts/diagnostics/stress_test_omen_cot.py --cycles 3
    .venv/bin/python scripts/diagnostics/stress_test_omen_cot.py --model hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M --cycles 5
"""

import argparse
import ast
import json
from pathlib import Path
import re
import sys
import time
import urllib.request
import urllib.error

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.identity import generate_or_load_identity, make_request_headers

OMEN_NODE_URL = "http://100.104.238.125:8081"
DEFAULT_MODEL = "hf.co/DuoNeural/LFM2.5-8B-A1B-Abliterated-GGUF:Q4_K_M"
LOG_OUTPUT_PATH = REPO_ROOT / "data" / "stress_test_omen_results.jsonl"

def load_agents_rules() -> str:
    agents_file = REPO_ROOT / "AGENTS.md"
    if agents_file.exists():
        content = agents_file.read_text(encoding="utf-8")
        # Estrai le prime 120 righe (regole essenziali) per mantenere il prompt compatto ed efficace
        lines = content.splitlines()[:120]
        return "\n".join(lines)
    return "Regole HyperSpace: non stampare segreti, salva script in scripts/diagnostics/, rispetta codice esistente."

BENCHMARK_TASKS = [
    {
        "id": "task_1_cli_monitor",
        "name": "Script CLI per Monitoraggio Mesh (Python)",
        "expected_type": "python",
        "prompt": (
            "Sei un assistente per lo sviluppo del repository HyperSpace AGI. Segui rigorosamente le regole di AGENTS.md.\n"
            "Crea uno script Python autonomo `scripts/diagnostics/mesh_live_monitor.py` che:\n"
            "1. Accetta argomenti da riga di comando con argparse (`--timeout`, `--nodes`).\n"
            "2. Interroga via HTTP GET l'endpoint `/status` dei nodi specificati.\n"
            "3. Stampa un resoconto chiaro e sintetico a tabella in console.\n"
            "4. Gestisce correttamente eccezioni di rete e timeout senza crash.\n"
            "Mostra prima il ragionamento e la pianificazione (CoT), poi emetti il codice Python completo all'interno di un blocco ```python ... ```."
        )
    },
    {
        "id": "task_2_fastapi_service",
        "name": "Micro-servizio FastAPI con Metriche (Python)",
        "expected_type": "python",
        "prompt": (
            "Sei un assistente per lo sviluppo del repository HyperSpace AGI. Segui rigorosamente le regole di AGENTS.md.\n"
            "Crea un micro-servizio FastAPI standalone `scripts/diagnostics/service_agent_metrics.py` che:\n"
            "1. Definisce rotte GET `/health`, `/status` e `/metrics`.\n"
            "2. Usa Pydantic per validare i modelli di dati restituiti.\n"
            "3. Raccoglie metriche fittizie di memoria e token elaborati.\n"
            "4. Include docstring conformi e blocco `if __name__ == '__main__':` con uvicorn.\n"
            "Mostra prima il ragionamento e la pianificazione (CoT), poi emetti il codice Python completo all'interno di un blocco ```python ... ```."
        )
    },
    {
        "id": "task_3_html_dashboard",
        "name": "Dashboard Web Reattiva per Nodi (HTML/JS)",
        "expected_type": "html",
        "prompt": (
            "Sei un assistente per lo sviluppo del repository HyperSpace AGI. Segui rigorosamente le regole di AGENTS.md.\n"
            "Crea una pagina HTML5 standalone responsive `scripts/diagnostics/mesh_dashboard.html` che:\n"
            "1. Usa Tailwind CSS via CDN per lo stile dark mode moderno.\n"
            "2. Mostra tre card per i nodi mesh: Mac M5, HP Omen 16, ASUS V16.\n"
            "3. Include badge di stato (Online, Offline, In Esecuzione) e indicatori di memoria/VRAM.\n"
            "4. Include un semplice script JavaScript vanilla per simulare il refresh ogni 5 secondi.\n"
            "Mostra prima il ragionamento e la pianificazione (CoT), poi emetti il codice HTML completo all'interno di un blocco ```html ... ```."
        )
    },
    {
        "id": "task_4_async_audit_tool",
        "name": "Strumento di Audit Token Asincrono (Python)",
        "expected_type": "python",
        "prompt": (
            "Sei un assistente per lo sviluppo del repository HyperSpace AGI. Segui rigorosamente le regole di AGENTS.md.\n"
            "Crea uno script Python asincrono `scripts/diagnostics/audit_token_costs.py` che:\n"
            "1. Usa `asyncio` e `pathlib.Path` per scansionare file JSONL di log.\n"
            "2. Calcola statistiche aggregate: totale prompt token, totale completion token, costo stimato e latenza media.\n"
            "3. Non usa librerie esterne non standard ad eccezione di `json` e `argparse`.\n"
            "Mostra prima il ragionamento e la pianificazione (CoT), poi emetti il codice Python completo all'interno di un blocco ```python ... ```."
        )
    }
]

def call_omen_node(model: str, system_rules: str, prompt: str, timeout_s: int = 240) -> dict:
    url = f"{OMEN_NODE_URL}/execute"
    full_prompt = f"### REGOLE REPOSITORY (AGENTS.MD):\n{system_rules}\n\n### RICHIESTA:\n{prompt}"
    payload = json.dumps({
        "task_id": f"stress-{int(time.time() * 1000)}",
        "model": model,
        "prompt": full_prompt
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    try:
        ident = generate_or_load_identity()
        signed_hdrs = make_request_headers(ident["node_id"], ident["public_key"], ident["_private_key"], body=payload)
        headers.update(signed_hdrs)
    except Exception as e:
        print(f"[WARN] Impossibile firmare la richiesta: {e}")

    req = urllib.request.Request(url, data=payload, headers=headers)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - t0

    response_text = data.get("response", "")
    return {
        "response": response_text,
        "elapsed_s": round(elapsed, 2)
    }

def analyze_output(task_spec: dict, raw_response: str) -> dict:
    has_think_tag = "</think>" in raw_response
    if has_think_tag:
        parts = raw_response.split("</think>")
        thought_text = parts[0].replace("<think>", "").strip()
        final_output = parts[-1].strip()
    else:
        thought_text = ""
        final_output = raw_response.strip()

    thought_words = len(thought_text.split())
    output_words = len(final_output.split())

    # Validazione codice
    code_valid = False
    validation_note = ""
    expected_type = task_spec["expected_type"]

    if expected_type == "python":
        py_match = re.search(r"```python\s*(.*?)\s*```", final_output, re.DOTALL)
        code_to_check = py_match.group(1) if py_match else final_output
        try:
            ast.parse(code_to_check)
            code_valid = True
            validation_note = "Sintassi AST Python valida al 100%"
        except SyntaxError as se:
            code_valid = False
            validation_note = f"Errore sintassi Python alla riga {se.lineno}: {se.msg}"
        except Exception as e:
            code_valid = False
            validation_note = f"Errore generico parse: {e}"

    elif expected_type == "html":
        has_html_tags = "<html" in final_output.lower() and "</html>" in final_output.lower()
        has_tailwind = "cdn.tailwindcss.com" in final_output or "tailwind" in final_output.lower()
        code_valid = has_html_tags
        validation_note = "HTML completo valido (con Tailwind)" if (has_html_tags and has_tailwind) else "HTML parziale o incompleto"

    return {
        "has_cot": has_think_tag or bool(thought_text),
        "thought_words": thought_words,
        "output_words": output_words,
        "code_valid": code_valid,
        "validation_note": validation_note
    }

def log_result(record: dict):
    LOG_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_OUTPUT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def check_omen_health() -> dict:
    try:
        req = urllib.request.Request(f"{OMEN_NODE_URL}/status")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e), "alive": False}

def run_stress_test(model: str, cycles: int, timeout_s: int):
    print("=" * 65)
    print("  STRESS TEST NOTTURNO CO-T SU HP OMEN 16 (RETE AC)")
    print(f"  Target: {OMEN_NODE_URL} | Modello: {model}")
    print(f"  Cicli previsti: {cycles} | Carico locale Mac: ~0% (HTTP Orchestration)")
    print("=" * 65)

    system_rules = load_agents_rules()
    print(f"[PREFLIGHT] Caricate regole AGENTS.md: {len(system_rules)} caratteri (~{len(system_rules.split())} parole).")

    initial_health = check_omen_health()
    if initial_health.get("running"):
        print(f"[PREFLIGHT] HP Omen ONLINE | AC Power: {initial_health.get('ac_line')} | VRAM: {initial_health.get('vram_gb')} GB")
    else:
        print(f"[PREFLIGHT WARN] Stato iniziale Omen: {initial_health}")

    total_tasks = 0
    passed_tasks = 0

    for c in range(1, cycles + 1):
        print(f"\n>>>>>>>>>>>>>>> INIZIO CICLO {c}/{cycles} <<<<<<<<<<<<<<<")
        for task in BENCHMARK_TASKS:
            total_tasks += 1
            print(f"\n--- [Ciclo {c}] Task: {task['name']} ({task['id']}) ---")
            try:
                res = call_omen_node(model, system_rules, task["prompt"], timeout_s=timeout_s)
                metrics = analyze_output(task, res["response"])
                elapsed = res["elapsed_s"]

                status_str = "PASS" if metrics["code_valid"] else "FAIL"
                if metrics["code_valid"]:
                    passed_tasks += 1

                print(f"Esito: [{status_str}] in {elapsed}s | CoT: {metrics['thought_words']} parole | Output: {metrics['output_words']} parole")
                print(f"Dettaglio: {metrics['validation_note']}")

                record = {
                    "timestamp": time.time(),
                    "iso_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "cycle": c,
                    "task_id": task["id"],
                    "model": model,
                    "elapsed_s": elapsed,
                    "metrics": metrics
                }
                log_result(record)

            except Exception as e:
                print(f"[ERRORE TASK] {task['id']}: {e}")
                log_result({
                    "timestamp": time.time(),
                    "cycle": c,
                    "task_id": task["id"],
                    "error": str(e)
                })

            # Piccola pausa di 5 secondi tra un task e l'altro per consentire la pulizia della cache
            time.sleep(5)

        omen_status = check_omen_health()
        print(f"[CHECKPOINT CICLO {c}] Omen running: {omen_status.get('running', False)} | Saturation: {omen_status.get('saturation')} | VRAM: {omen_status.get('vram_gb')} GB")

    print("\n" + "=" * 65)
    print(f"  STRESS TEST COMPLETATO: {passed_tasks}/{total_tasks} task validati con successo.")
    print(f"  Report dettagliato salvato in: {LOG_OUTPUT_PATH}")
    print("=" * 65)

def main():
    parser = argparse.ArgumentParser(description="Stress Test Notturno CoT su HP Omen")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Modello target su HP Omen")
    parser.add_argument("--cycles", type=int, default=3, help="Numero di cicli da eseguire")
    parser.add_argument("--timeout", type=int, default=240, help="Timeout in secondi per task (default 240s)")
    args = parser.parse_args()

    run_stress_test(args.model, args.cycles, args.timeout)

if __name__ == "__main__":
    main()
