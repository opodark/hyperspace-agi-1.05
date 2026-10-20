#!/usr/bin/env python3
"""
Harness per il Self-Healing Loop su HP OMEN 16.
Invia all'Omen il codice generato precedentemente e i report di errore del browser/linter,
misurando la capacità del modello di auto-correggersi mediante CoT (<think>).
"""

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
MODEL = "hf.co/DuoNeural/LFM2.5-8B-A1B-Abliterated-GGUF:Q4_K_M"
INDEX_PATH = REPO_ROOT / "web-node" / "apps" / "playground" / "index.html"
LOG_OUTPUT_PATH = REPO_ROOT / "data" / "stress_test_omen_results.jsonl"

def run_self_healing():
    print("=" * 65)
    print("  SELF-HEALING & AUTO-REPAIR TEST SU HP OMEN 16")
    print(f"  Target: {OMEN_NODE_URL} | Modello: {MODEL}")
    print("=" * 65)

    if not INDEX_PATH.exists():
        print(f"[ERRORE] File {INDEX_PATH} non trovato!")
        return

    current_code = INDEX_PATH.read_text(encoding="utf-8")

    linter_feedback = """### REPORT LINTER / CONSOLE ERRORI RILEVATI SUL BROWSER:
1. SyntaxError:
   - Riga 266: `}()</script>` causa un SyntaxError di chiamata IIFE; la sintassi corretta per invocare la funzione anonima è `})();</script>`.
2. TypeError & Null Pointer in DOM:
   - Riga 121: `clockEl = document.querySelector('#clock')` restituisce `null` perché nell'HTML c'è `<div class="clock">` invece di `id="clock"`.
   - Riga 122: `nodesEl = document.querySelector('#nodes')` restituisce `null` perché manca il container `<div id="nodes">` o `<tbody id="nodes">` nell'HTML! Il layout deve contenere sia la sezione delle 3 card/tabella dei nodi (`#nodes`), sia il terminale (`#terminal`).
   - Di conseguenza `renderNodes()` fallisce con: `TypeError: Cannot set properties of null (setting 'innerHTML')`.
3. ReferenceError:
   - Riga 248: `if (upto > 30000)` usa la variabile non definita `upto` anziché `uptime`.
   - Riga 228: `totalThroughput - n.throughput` usa `n` fuori dal ciclo `for (const n of nodes)`, sollevando ReferenceError.
4. Mismatch ID Event Listener:
   - Riga 99: il pulsante ha `id="cmd-bench"`, ma l'EventListener a riga 221 cerca `cmd-benchmark`.
5. Bug di UX e Sovrascrittura Terminale:
   - Riga 252: la funzione `tick()` ogni 3 secondi sovrascrive `output.innerHTML` con throughput/uptime, cancellando l'output dei comandi del terminale!
   - I contatori di Throughput, Saturation e Uptime devono essere posizionati in elementi dedicati (es. `<span id="metric-throughput">`, `<span id="metric-saturation">`, `<span id="metric-uptime">`), lasciando `output` riservato esclusivamente all'output dei comandi.
6. Design & Layout:
   - Usa Tailwind CSS via CDN (`<script src="https://cdn.tailwindcss.com"></script>`) con le 3 card dei nodi (Mac M5, Omen 16, ASUS V16) visibili in cima, e il terminale sottostante con prompt interattivo e pulsanti comandi.
"""

    prompt = f"""Sei un esperto frontend developer e debugger per HyperSpace AGI. Rispetta le regole di AGENTS.md.
Abbiamo eseguito l'applicazione web che hai generato (`index.html`) e la console del browser ha rilevato alcuni errori sintattici e di runtime.

Ecco il codice attuale:
```html
{current_code}
```

Ecco i dettagli degli errori riscontrati:
{linter_feedback}

### IL TUO COMPITO:
1. Analizza nel blocco di pensiero (<think>) la causa esatta di ciascun errore segnalato.
2. Pianifica le correzioni necessarie al layout DOM (aggiungendo la sezione nodi con le card grafiche) e correggi il JavaScript.
3. Riscrivi il file HTML completo, corretto e pienamente funzionante, racchiuso in un blocco ```html ... ```.
4. Assicurati che tutti i comandi del terminale (`help`, `nodes`, `ping omen`, `ping asus`, `ping mac`, `bench`, `vram`, `clear`) funzionino alla perfezione senza errori in console e senza sovrascrivere il terminale a ogni tick.
"""

    payload = json.dumps({
        "task_id": f"self-heal-{int(time.time())}",
        "model": MODEL,
        "prompt": prompt
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    try:
        ident = generate_or_load_identity()
        signed_hdrs = make_request_headers(ident["node_id"], ident["public_key"], ident["_private_key"], body=payload)
        headers.update(signed_hdrs)
    except Exception as e:
        print(f"[WARN] Impossibile firmare: {e}")

    req = urllib.request.Request(f"{OMEN_NODE_URL}/execute", data=payload, headers=headers)
    print("\n[1/3] Invio del report di debug e del codice a HP Omen...")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - t0
    print(f"[2/3] Risposta ricevuta da HP Omen in {round(elapsed, 2)}s.")

    raw_response = data.get("response", "")

    # Separa CoT dal codice
    if "</think>" in raw_response:
        parts = raw_response.split("</think>")
        thought_text = parts[0].replace("<think>", "").strip()
        final_content = parts[-1].strip()
    else:
        thought_text = ""
        final_content = raw_response.strip()

    thought_words = len(thought_text.split())
    print(f"      Pianificazione CoT di riparazione: {thought_words} parole.")

    # Estrai il blocco ```html ... ```
    html_match = re.search(r"```html\s*(.*?)\s*```", final_content, re.DOTALL)
    if html_match:
        fixed_html = html_match.group(1).strip()
    else:
        fixed_html = final_content

    if "<!DOCTYPE" not in fixed_html.upper() and "<html" in fixed_html.lower():
        fixed_html = "<!DOCTYPE html>\n" + fixed_html

    if "[OLLAMA ERROR]" in fixed_html or not ("<html" in fixed_html.lower()):
        print(f"[ERRORE] Risposta incompleta o errore di rete: {fixed_html[:150]}")
        return

    # Verifica automatica sui vecchi errori
    has_four_equals = "====" in fixed_html
    has_dot_clear = ".clear()" in fixed_html
    has_broken_iife = "}()" in fixed_html
    has_nodes_container = 'id="nodes"' in fixed_html or 'class="nodes"' in fixed_html
    is_valid_repair = not has_four_equals and not has_dot_clear and not has_broken_iife and has_nodes_container

    print(f"\n[3/3] Validazione del codice riparato:")
    print(f"  - Controllo refuso '====': {'ELIMINATO [PASS]' if not has_four_equals else 'ANCORA PRESENTE [FAIL]'}")
    print(f"  - Controllo metodo '.clear()': {'SOSTITUITO CORRETTAMENTE [PASS]' if not has_dot_clear else 'ANCORA PRESENTE [FAIL]'}")
    print(f"  - Controllo IIFE syntax '}})()': {'CORRETTO [PASS]' if not has_broken_iife else 'ANCORA PRESENTE [FAIL]'}")
    print(f"  - Presenza container nodi (#nodes): {'PRESENTE [PASS]' if has_nodes_container else 'MANCANTE [FAIL]'}")

    # Salva il file riparato
    INDEX_PATH.write_text(fixed_html, encoding="utf-8")
    print(f"\n[SUCCESSO] Cockpit v2.0 auto-riparato salvato in:")
    print(f"  file://{INDEX_PATH}")
    print(f"  Visualizza live: http://localhost:8090/index.html")

    # Registra nel log JSONL
    record = {
        "timestamp": time.time(),
        "task": "self_healing_cockpit_v2",
        "model": MODEL,
        "elapsed_s": round(elapsed, 2),
        "cot_words": thought_words,
        "code_words": len(fixed_html.split()),
        "repair_success": is_valid_repair
    }
    with open(LOG_OUTPUT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    run_self_healing()
