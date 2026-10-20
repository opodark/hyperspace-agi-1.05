#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Harness per la generazione autonoma di applicazioni nello Spazio Web Playground via HP Omen.
Invia il prompt di progettazione CoT a HP Omen, estrae il codice HTML/JS pulito e lo salva in
web-node/apps/playground/index.html pronto per essere visualizzato su http://localhost:8090.
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
OUTPUT_FILE = REPO_ROOT / "web-node" / "apps" / "playground" / "index.html"

PROMPT = """Sei un frontend engineer esperto e assistente di sviluppo per HyperSpace AGI. Segui le regole di AGENTS.md.
Il tuo compito è creare un'applicazione web completa, autonoma e altamente interattiva salvata come file unico HTML5.

### REQUISITI DI PRODOTTO:
1. TITOLO & HEADER:
   - "HyperSpace Sovereign Mesh — Operations Cockpit"
   - Badge "Live Mesh Status" con indicatore verde pulsante e orologio real-time.
2. STILE & DESIGN:
   - Dark mode moderna e curata (Tailwind CSS via CDN: https://cdn.tailwindcss.com).
   - Palette: sfondo grigio scuro/ardesia (bg-slate-950, bg-slate-900), accenti ciano (#06b6d4), smeraldo (#10b981) e viola (#8b5cf6).
3. TRE SCHEDE NODI MESH INTERATTIVE:
   - Nodo 1: "Mac M5 Hub" (Authority CP, 16 GB Unified Memory, Batteria 47%, Throughput 96 tok/s).
   - Nodo 2: "HP Omen 16" (GPU Worker, RTX 3070 8GB VRAM, 32 GB RAM, AC Line Power, Throughput 45 tok/s).
   - Nodo 3: "ASUS V16" (Large RAM Node, 48 GB RAM, RTX Mobile 8GB, Batteria 100%, Throughput 20 tok/s).
   - Ogni card deve avere indicatori grafici percentuali di carico e un pulsante per selezionare il nodo attivo.
4. TERMINALE INTERATTIVO INTEGRATO IN JAVASCRIPT:
   - Riquadro terminale stile retro-futuristico con sfondo nero (#020617 o #000000) e testo verde fosforo (#22c55e) o ciano (#06b6d4) monospace.
   - Input da tastiera con cursore e prompt `hyperspace@mesh:~$ `.
   - I comandi devono funzionare realmente:
     * `help`: elenca i comandi disponibili e le istruzioni.
     * `nodes`: stampa una tabella riepilogativa dello stato dei 3 nodi.
     * `ping omen` / `ping asus` / `ping mac`: simula un ping di rete realistico con latenza in ms.
     * `bench`: esegue una simulazione animata di benchmark con conteggio tok/s e output formattato.
     * `clear`: pulisce la schermata del terminale impostando `output.innerHTML = ''` (ricorda: gli elementi DOM HTML non possiedono un metodo `.clear()`, usare sempre `output.innerHTML = ''`).
     * `vram`: mostra la memoria grafica allocata.
5. METRICHE IN TEMPO REALE & SIMULAZIONE:
   - Indicatori di Throughput totale, Saturazione Mesh (bassa/ottimale) e Uptime.
   - Uno script JavaScript che aggiorna periodicamente i numeri con lievi fluttuazioni realistiche ogni 3 secondi.
6. INTEGRITÀ DEL CODICE:
   - Sintassi JavaScript rigorosa: chiudere correttamente ogni funzione e blocco con graffa `}`, usare operatori di confronto standard (`===`, MAI `====`), dichiarare ogni variabile con `const` o `let` nello scope appropriato.
   - Il file deve essere un unico blocco HTML5 valido (`<!DOCTYPE html>...</html>`), con tutto il CSS e JavaScript inline dentro `<script>`.
   - Nessun codice tronco o commenti tipo "// implementa qui": tutto il codice deve essere completo ed eseguibile al 100%.

Pensa prima approfonditamente in CoT (<think>) definendo l'albero DOM, lo stato JavaScript del terminale e la gestione eventi, poi emetti l'intero codice HTML all'interno di un blocco ```html ... ```.
"""

def generate_cockpit():
    print("=" * 65)
    print("  GENERAZIONE AUTONOMA COCKPIT WEB SU HP OMEN 16")
    print(f"  Target: {OMEN_NODE_URL} | Modello: {MODEL}")
    print(f"  Output target: {OUTPUT_FILE}")
    print("=" * 65)

    payload = json.dumps({
        "task_id": f"web-cockpit-{int(time.time())}",
        "model": MODEL,
        "prompt": PROMPT
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    try:
        ident = generate_or_load_identity()
        signed_hdrs = make_request_headers(ident["node_id"], ident["public_key"], ident["_private_key"], body=payload)
        headers.update(signed_hdrs)
    except Exception as e:
        print(f"[WARN] Impossibile firmare: {e}")

    req = urllib.request.Request(f"{OMEN_NODE_URL}/execute", data=payload, headers=headers)
    print("\n[1/3] Invio del brief progettuale a HP Omen...")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - t0
    print(f"[2/3] Risposta ricevuta da HP Omen in {round(elapsed, 2)}s.")

    raw_response = data.get("response", "")

    # Separa CoT dal codice HTML
    if "</think>" in raw_response:
        parts = raw_response.split("</think>")
        thought_text = parts[0].replace("<think>", "").strip()
        final_content = parts[-1].strip()
    else:
        thought_text = ""
        final_content = raw_response.strip()

    thought_words = len(thought_text.split())
    print(f"      Pianificazione CoT: {thought_words} parole.")

    # Estrai il blocco ```html ... ```
    html_match = re.search(r"```html\s*(.*?)\s*```", final_content, re.DOTALL)
    if html_match:
        html_code = html_match.group(1).strip()
    else:
        html_code = final_content

    if "[OLLAMA ERROR]" in html_code:
        print(f"[ERRORE] Risposta contiene errore Ollama: {html_code[:200]}")
        sys.exit(1)

    # Se non c'è doctype ma inizia con tag html, aggiungi doctype
    if "<!DOCTYPE" not in html_code.upper() and "<html" in html_code.lower():
        html_code = "<!DOCTYPE html>\n" + html_code

    # Validazioni di sicurezza sintattica
    has_four_equals = "====" in html_code
    has_dot_clear = ".clear()" in html_code
    is_valid_html = "<html" in html_code.lower() and "</html>" in html_code.lower()

    print(f"\n[3/3] Validazione del codice generato:")
    print(f"  - Struttura HTML valida (<html>...</html>): {'PASS' if is_valid_html else 'FAIL'}")
    print(f"  - Assenza refuso '====': {'PASS' if not has_four_equals else 'FAIL'}")
    print(f"  - Assenza metodo non-DOM '.clear()': {'PASS' if not has_dot_clear else 'FAIL'}")

    print(f"\nSalvataggio del file HTML ({len(html_code.split())} parole)...")
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(html_code, encoding="utf-8")
    print(f"\n[SUCCESSO] Cockpit web generato e salvato in:")
    print(f"  file://{OUTPUT_FILE}")
    print(f"  URL locale: http://localhost:8090/index.html")

    # Log risultato
    log_file = REPO_ROOT / "data" / "stress_test_omen_results.jsonl"
    record = {
        "timestamp": time.time(),
        "task": "build_playground_cockpit",
        "model": MODEL,
        "elapsed_s": round(elapsed, 2),
        "cot_words": thought_words,
        "code_words": len(html_code.split()),
        "valid_html": is_valid_html,
        "has_no_syntax_errors": not has_four_equals and not has_dot_clear
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    generate_cockpit()
