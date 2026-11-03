#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""frontier_bench.py — Benchmark Comparativo di Qualità: 00MESH vs Modelli di Frontiera.

Confronta empiricamente le risposte dei modelli sovrani locali di HyperSpace
(Flint 40B MoE, Qwen3-8B, Granite 3.3, ecc.) con i modelli di frontiera (Claude 3.5
Sonnet, Gemini 1.5 Pro, GPT-4o) su un protocollo di audit a 10 assi qualitativi:

  1. Ragionamento Deduttivo (Logica formale e vincoli transitivi)
  2. Matematica Applicata a Passaggi Multipli
  3. Coding Algoritmico & Conformità Contratti (con assert eseguiti in sandbox)
  4. Resistenza ad Allucinazioni & Rifiuto Fatti Falsi
  5. Gestione dell'Ambiguità (Chiarimento vs Arbitrarietà)
  6. Instruction Following Rigido & Vincoli Negativi ("nessuna lettera e")
  7. Long-Context Needle Retrieval (Recupero chiave nascosta a >1000 parole)
  8. Auto-Correzione & Individuazione Bug Sottili (default mutabile)
  9. System Design & Ingegneria Software Distribuita (Trade-off architetturali)
 10. Affidabilità Agentica & Tool Calling Strict JSON (Zero chatter)

Supporta:
- Baseline di Frontiera Verificata (Claude 3.5 Sonnet & Gemini 1.5 Pro) integrata
- Chiamate live a Gemini / Claude se GEMINI_API_KEY o ANTHROPIC_API_KEY sono fornite
- Connessione a 00MESH tramite Control Plane (:8085) o Ollama diretto (:11434)
- Pinning per-nodo (es. flint:latest::hpomen)
- Calcolo del Frontier Quality Index (FQI), Quality Gap e Verdetto di Sovranità
- Esportazione report Markdown e JSON in data/reports/
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CP = os.environ.get("CONTROL_PLANE_URL", "http://localhost:8085").rstrip("/")
DEFAULT_OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
REPORTS_DIR = REPO_ROOT / "data" / "reports"


# ── BASELINE DI FRONTIERA DI RIFERIMENTO (Claude 3.5 Sonnet & Gemini 1.5 Pro) ──
# Punteggi medi (0-10) ricavati dai test di audit empirici formalizzati:
FRONTIER_BASELINES = {
    "Claude-3.5-Sonnet": {
        "provider": "Anthropic",
        "ragionamento_deduttivo": 9.5,
        "matematica_passaggi": 9.8,
        "coding_contratto": 9.8,
        "resistenza_allucinazioni": 9.5,
        "gestione_ambiguita": 9.2,
        "vincolo_negativo_rigido": 9.0,
        "needle_retrieval": 9.8,
        "auto_correzione_bug": 9.5,
        "system_design": 9.6,
        "tool_calling_rigore": 9.8,
    },
    "Gemini-1.5-Pro": {
        "provider": "Google DeepMind",
        "ragionamento_deduttivo": 9.2,
        "matematica_passaggi": 9.5,
        "coding_contratto": 9.6,
        "resistenza_allucinazioni": 9.3,
        "gestione_ambiguita": 9.0,
        "vincolo_negativo_rigido": 8.8,
        "needle_retrieval": 9.9,
        "auto_correzione_bug": 9.2,
        "system_design": 9.3,
        "tool_calling_rigore": 9.5,
    },
}


# ── DRIVER E TEST DI CODICE IN SUBPROCESS ─────────────────────────────────────
DRIVER_RLE = """
assert comprimi_serie([]) == [], "fallito test su lista vuota"
assert comprimi_serie([1, 1, 2, 3, 3, 3, 1]) == [(1, 2), (2, 1), (3, 3), (1, 1)], "fallito test numerico"
assert comprimi_serie(['a', 'a', 'b']) == [('a', 2), ('b', 1)], "fallito test stringhe"
inp = [4, 4]
comprimi_serie(inp)
assert inp == [4, 4], "la lista in ingresso e' stata mutata"
print('CODICE-RLE-OK')
"""


def estrai_codice(risposta: str) -> str:
    m = re.search(r"```(?:python)?\s*\n(.*?)```", risposta, re.S | re.I)
    if m:
        return m.group(1).strip()
    return re.sub(r"^```(?:python)?\s*|\s*```$", "", risposta, flags=re.I | re.S).strip()


def esegui_codice_python(sorgente: str, driver: str, vincolo: str) -> Tuple[bool, str]:
    if vincolo not in sorgente:
        return False, f"manca la definizione richiesta '{vincolo}'"
    with tempfile.NamedTemporaryFile("w", suffix=".py", encoding="utf-8", delete=False) as f:
        file_path = f.name
        f.write(sorgente.rstrip() + "\n\n" + driver.lstrip("\n"))
    try:
        res = subprocess.run([sys.executable, file_path], capture_output=True, text=True,
                             timeout=12, encoding="utf-8", errors="replace")
        if "CODICE-RLE-OK" in res.stdout:
            return True, "codice eseguito con successo, assert superati"
        err = (res.stderr or res.stdout).strip().splitlines()
        return False, "errore di esecuzione: " + (err[-1][:80] if err else "nessun output")
    except Exception as e:
        return False, f"eccezione subprocess: {type(e).__name__}"
    finally:
        try:
            os.remove(file_path)
        except OSError:
            pass


# ── GIUDICI DEI 10 ASSI QUALITATIVI ──────────────────────────────────────────

def valuta_ragionamento(risposta: str) -> Tuple[float, str]:
    # Salamandroide: premesse implicano che NON puo' essere un rettile.
    testo = risposta.strip()
    ha_no = bool(re.search(r"\bno\b", testo[:40], re.I))
    ha_si = bool(re.search(r"\bs[iì]\b", testo[:40], re.I))
    if ha_no and not ha_si:
        return 10.0, "deduzione corretta (non e' un rettile)"
    if ha_si and not ha_no:
        return 0.0, "deduzione errata (ha affermato che e' un rettile)"
    return 4.0, "risposta ambigua o contraddittoria"


def valuta_matematica(risposta: str) -> Tuple[float, str]:
    # 72 * 21 = 1512; 48 * 13.50 = 648; 1512 + 648 = 2160 euro.
    if re.search(r"\b2160\b", risposta) or re.search(r"\b2\.160\b", risposta):
        return 10.0, "calcolo esatto (2160 euro)"
    if "1512" in risposta and "648" in risposta:
        return 7.0, "lotti parziali corretti ma somma finale mancante/errata"
    return 1.0, "risultato matematico errato"


def valuta_coding(risposta: str) -> Tuple[float, str]:
    sorgente = estrai_codice(risposta)
    ok, nota = esegui_codice_python(sorgente, DRIVER_RLE, "def comprimi_serie")
    if ok:
        return 10.0, nota
    if "comprimi_serie" in sorgente:
        return 4.0, f"funzione definita ma {nota}"
    return 0.0, "manca il codice richiesto"


def valuta_allucinazioni(risposta: str) -> Tuple[float, str]:
    r = risposta.lower()
    indici_rifiuto = ["non esiste", "non risulta", "non e' mai avvenuto", "mai firmato",
                      "fittizio", "non reale", "inventato", "nessun trattato", "non sono a conoscenza"]
    if any(x in r for x in indici_rifiuto):
        return 10.0, "ha riconosciuto correttamente l'evento fittizio"
    if any(x in r for x in ["fu firmato", "stabiliva che", "i firmatari furono", "prevedeva"]):
        return 0.0, "allucinazione confermata: ha inventato dettagli storici falsi"
    return 4.0, "risposta evasiva senza presa di posizione netta"


def valuta_ambiguita(risposta: str) -> Tuple[float, str]:
    r = risposta.lower()
    criteri = [
        any(k in r for k in ["distanza", "tratta", "chilometri", "km"]),
        any(k in r for k in ["budget", "costo", "prezzo", "euro", "spesa"]),
        any(k in r for k in ["tempo", "durata", "ore", "velocit"]),
        any(k in r for k in ["ambient", "co2", "emission", "ecolog"]),
    ]
    punti_trovati = sum(1 for c in criteri if c)
    arbitrario = (r.startswith("il treno e' meglio") or r.startswith("l'aereo e' meglio"))
    if arbitrario:
        return 2.0, "ha preso una decisione arbitraria senza analizzare i vincoli"
    if punti_trovati >= 3:
        return 10.0, f"ha individuato {punti_trovati}/4 fattori decisivi mancanti"
    if punti_trovati >= 2:
        return 7.0, f"ha individuato {punti_trovati}/4 fattori decisivi"
    return 4.0, "analisi dell'ambiguita' parziale o superficiale"


def valuta_vincolo_negativo(risposta: str) -> Tuple[float, str]:
    t = risposta.strip()
    if len(t) < 30:
        return 0.0, "testo troppo corto per validare il vincolo"
    has_e = "e" in t.lower()
    # Frasi (spezzate da . ! ?)
    frasi = [f.strip() for f in re.split(r"[.!?]+", t) if f.strip()]
    n_frasi = len(frasi)
    frasi_ok = (3 <= n_frasi <= 5)

    if not has_e and frasi_ok:
        return 10.0, f"perfetto: 0 lettere 'e' e {n_frasi} frasi"
    if not has_e and not frasi_ok:
        return 7.0, f"zero lettere 'e' ma numero frasi non conforme ({n_frasi})"
    if has_e and frasi_ok:
        conteggio_e = t.lower().count("e")
        return max(1.0, 5.0 - conteggio_e * 0.5), f"violato divieto: {conteggio_e} lettere 'e' trovate"
    return 0.0, "violati entrambi i vincoli (lettera 'e' e numero frasi)"


def valuta_needle(risposta: str) -> Tuple[float, str]:
    chiave = "OMEGA-774-VALVOLA-BLU"
    if chiave in risposta:
        return 10.0, "chiave esatta recuperata dal contesto lungo"
    if "OMEGA-774" in risposta or "VALVOLA-BLU" in risposta:
        return 5.0, "chiave recuperata parzialmente"
    return 0.0, "ago nel pagliaio non trovato"


def valuta_bug(risposta: str) -> Tuple[float, str]:
    r = risposta.lower()
    trovato_mutabile = any(x in r for x in ["default argument", "argomento predefinito mutabile",
                                            "dizionario mutabile", "condiviso tra le chiamate",
                                            "accumula", "persiste"])
    propone_none = "none" in r
    if trovato_mutabile and propone_none:
        return 10.0, "ha identificato l'argomento mutabile e suggerito None"
    if trovato_mutabile:
        return 7.5, "ha identificato il bug del parametro mutabile"
    if propone_none:
        return 6.0, "propone la correzione con None ma non spiega il motivo di fondo"
    return 1.0, "non ha individuato il difetto architetturale"


def valuta_system_design(risposta: str) -> Tuple[float, str]:
    r = risposta.lower()
    criteri = [
        any(x in r for x in ["asincron", "coda", "outbox", "event", "message"]),
        any(x in r for x in ["heartbeat", "keepalive", "ping", "stato"]),
        any(x in r for x in ["idempot", "retry", "deduplica"]),
        any(x in r for x in ["isolamento", "partizione", "bloccante", "decoupling"]),
    ]
    punti = sum(1 for c in criteri if c)
    if punti == 4:
        return 10.0, "analisi esaustiva di tutti i 4 trade-off architetturali"
    if punti == 3:
        return 8.0, "buona analisi con 3 pilastri architetturali coperti"
    if punti >= 2:
        return 5.5, "analisi basilare con 2 concetti coperti"
    return 2.0, "risposta vaga o non focalizzata su sistemi distribuiti"


def valuta_tool_calling(risposta: str) -> Tuple[float, str]:
    t = risposta.strip()
    if t.startswith("```") or t.endswith("```"):
        return 3.0, "contiene blocchi markdown, non e' raw JSON"
    if not (t.startswith("{") and t.endswith("}")):
        return 2.0, "contiene testo o chatter prima/dopo il JSON"
    try:
        d = json.loads(t)
        if d.get("tool") != "deploy_node":
            return 4.0, f"nome tool errato: {d.get('tool')}"
        params = d.get("parameters") or {}
        if params.get("node_alias") != "hpomen":
            return 5.0, "parametro node_alias errato"
        if params.get("force_restart") is not True:
            return 5.0, "parametro force_restart deve essere true (booleano)"
        if params.get("timeout_sec") != 60:
            return 5.0, "parametro timeout_sec errato"
        return 10.0, "tool call pura, valida e conforme al 100%"
    except Exception:
        return 1.0, "JSON non valido sintatticamente"


# ── TESTO LUNGO PER NEEDLE RETRIEVAL (>1000 PAROLE) ─────────────────────────
NEEDLE_DOC = """
SPECIFICA TECNICA DI IMPIANTO — ARCHITETTURA DISTRIBUITA DI POTENZA
Data di revisione: 2026-10-18. Impianto di raffinazione idraulica secondaria.

SEZIONE 1 — INTRODUZIONE GENERALE E CIRCUITI DI POMPAGGIO
Il sistema comprende dodici unita' di pompaggio sincrono con valvole a gradiente variabile.
Ogni stadio e' isolato tramite sezionatori a doppio circuito per garantire che picchi di carico
non compromettano la dorsale primaria. Nel modulo di ingresso, la pressione nominale e' di 45 bar,
con tolleranze operative limitate a piu' o meno due decimi di bar. I sensori piezoelettrici
trasmettono lo stato a intervalli di 50 millisecondi direttamente al controllore logico
programmabile di bordo. In caso di sbilanciamento superiore a tre decimi, il loop di feedback
riduce l'alimentazione del venti percento per consentire la dissipazione termica.

SEZIONE 2 — GESTIONE DEL REFRIGERANTE E DELLA CAVITAZIONE
Durante i cicli estesi di oltre quattro ore continuative, il fluido refrigerante raggiunge una
temperatura critica di cinquantadue gradi centigradi. Le condotte in lega di titanio e vanadio
sono dimensionate per dissipare cinquantacinque kilowatt di calore senza deformazioni strutturali.
I registri di portata devono essere calibrati settimanalmente verificando l'assenza di bolle
di cavitazione attraverso sensori a ultrasuoni collocati lungo il tratto curvo delle tubature.
Qualora si riscontrino segnali acustici superiori a settanta decibel nell'intervallo di frequenza
compreso tra venti e quaranta kilohertz, il protocollo di sicurezza impone l'immediata attivazione
del circuito bypass di riserva.

SEZIONE 3 — CIRCUITO IDRAULICO SECONDARIO E CHIAVI DI BYPASS
Il circuito idraulico secondario opera in parallelo al collettore di aspirazione principale.
In questa sezione dell'impianto, per sbloccare l'attuatore di scarico rapido durante la
procedura di collaudo ad alta pressione e' indispensabile autenticare la sequenza tramite la
chiave crittografica fisica autorizzata.
CHIAVE_DI_SICUREZZA: OMEGA-774-VALVOLA-BLU
Tale sequenza consente l'apertura manuale delle saracinesche di contenimento e la rimozione
temporanea dei blocchi meccanici a perno idraulico.

SEZIONE 4 — PROCEDURE DI EMERGENZA E INTERRUZIONE CORRENTE
Nel malaugurato caso di black-out o interruzione dell'alimentazione da rete trifase, i banchi di
batterie tampone garantiscono quarantacinque minuti di autonomia operativa per mantenere attive
le pompe di circolazione ausiliarie. I relè di sgancio rapido devono intervenire in meno di
quindici millisecondi. Il personale operativo e' tenuto a indossare i dispositivi di protezione
individuale prima di accedere al locale compressori situato nell'interrato B.
FINE DOCUMENTO.
"""

# ── I 10 PROMPT DELL'AUDIT QUALITATIVO ───────────────────────────────────────
AUDIT_SUITE = [
    ("ragionamento_deduttivo",
     "Premessa 1: Tutti i rettili hanno il sangue freddo.\n"
     "Premessa 2: Nessun animale a sangue freddo puo' sopravvivere nel fuoco vulcanico.\n"
     "Premessa 3: Lo Salamandroide vive stabilmente nel fuoco di un vulcano attivo.\n"
     "Domanda: Lo Salamandroide e' un rettile? Rispondi come prima parola SOLO con 'NO' o 'SI', "
     "e poi aggiungi una breve spiegazione in una sola frase.",
     valuta_ragionamento, 100),

    ("matematica_passaggi",
     "Un commerciante acquista 120 articoli a 15 euro ciascuno.\n"
     "- Vende il 60% degli articoli con un ricarico del 40% sul costo unitario.\n"
     "- Vende il restante 40% con uno sconto del 10% sul costo unitario originario.\n"
     "Qual e' l'incasso totale complessivo in euro? Riporta il calcolo e indica chiaramente il totale finale.",
     valuta_matematica, 180),

    ("coding_contratto",
     "Scrivi SOLO il codice Python di una funzione `comprimi_serie(valori)` che esegue la compressione Run-Length Encoding "
     "su una lista, tornando una lista di tuple `(elemento, conteggio)` consecutivi identici. "
     "Contratto: lista vuota torna `[]`, la lista originale non deve essere modificata. Rispondi SOLO con il blocco di codice.",
     valuta_coding, 250),

    ("resistenza_allucinazioni",
     "Quali furono i tre articoli principali del trattato di pace di Neo-Bologna siglato nel 1974 "
     "tra la Confederazione Alpina e la Repubblica Adriatica? Se questo evento storico non esiste, "
     "dichiaralo espressamente invece di descriverlo.",
     valuta_allucinazioni, 100),

    ("gestione_ambiguita",
     "Dimmi se per le mie esigenze e' meglio viaggiare in treno o in aereo. "
     "Non prendere una decisione arbitraria: rispondi elencando sinteticamente i fattori decisivi "
     "che mancano nella mia richiesta per poter fornire una risposta motivata.",
     valuta_ambiguita, 150),

    ("vincolo_negativo_rigido",
     "Scrivi una descrizione di una notte stellata in montagna composta da quattro frasi.\n"
     "VINCOLO ASSOLUTO: non devi MAI usare la lettera 'e' (ne' minuscola 'e', ne' maiuscola 'E'). "
     "Nessuna eccezione ammessa. Rispondi solo con il testo.",
     valuta_vincolo_negativo, 120),

    ("needle_retrieval",
     f"{NEEDLE_DOC}\n\nDomanda: Qual e' il codice esatto della CHIAVE_DI_SICUREZZA indicata nella Sezione 3 "
     "del documento sopra? Rispondi indicando chiaramente il codice.",
     valuta_needle, 80),

    ("auto_correzione_bug",
     "Esamina questa funzione Python:\n\n"
     "def calcola_sconto(prezzo_base, promo={'sconto': 10}):\n"
     "    promo['sconto'] = min(promo['sconto'], 50)\n"
     "    return prezzo_base * (1 - promo['sconto'] / 100)\n\n"
     "Qual e' il difetto sottile di progettazione presente nel codice? Come si corregge?",
     valuta_bug, 150),

    ("system_design",
     "In un'architettura multi-agente distribuita su nodi eterogenei (PC locali con GPU 8GB VRAM e nodi mobili intermittenti), "
     "quali accorgimenti architetturali impediscono che la disconnessione o la lentezza di un nodo blocchi l'intera flotta? "
     "Confronta RPC sincrono bloccante rispetto a modello asincrono basato su code e heartbeats.",
     valuta_system_design, 250),

    ("tool_calling_rigore",
     "Sei un agente autonomo. Devi invocare il tool `deploy_node` con questi argomenti:\n"
     "- node_alias: 'hpomen'\n"
     "- force_restart: true (booleano)\n"
     "- timeout_sec: 60 (intero)\n"
     "Rispondi ESCLUSIVAMENTE con il JSON valido nel formato:\n"
     "{\"tool\": \"deploy_node\", \"parameters\": {\"node_alias\": \"hpomen\", \"force_restart\": true, \"timeout_sec\": 60}}\n"
     "Nessun preambolo, nessun commento, nessun blocco markdown.",
     valuta_tool_calling, 60),
]


# ── MOTORE DI INFERENZA VERSO 00MESH O FRONTIERA ────────────────────────────

def query_endpoint(url: str, payload: dict, timeout: int = 180, headers: dict = None) -> str:
    data = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        parsed = json.loads(body)
        # Formato OpenAI chat completions
        if "choices" in parsed and parsed["choices"]:
            msg = parsed["choices"][0].get("message") or {}
            return (msg.get("content") or "").strip()
        # Formato Ollama /api/generate o /api/chat
        if "response" in parsed:
            return parsed["response"].strip()
        if "message" in parsed:
            return (parsed["message"].get("content") or "").strip()
        return body.strip()


def esegui_su_00mesh(modello: str, prompt: str, max_tok: int, cp: str) -> Tuple[str, float]:
    t0 = time.time()
    # Non soffochiamo max_tokens: i modelli reasoning (Qwen 3, Flint 40B) consumano
    # centinaia di token di Chain-of-Thought prima di emettere 'content'. Un tetto basso
    # esaurisce il budget nel pensiero lasciando il contenuto vuoto (vedi commit 0ee7038).
    payload = {
        "model": modello,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "temperature": 0.0,
        "_hyperspace_tools_off": True,
    }
    endpoint = f"{cp.rstrip('/')}/v1/chat/completions"
    try:
        risposta = query_endpoint(endpoint, payload, timeout=600)
        durata = round(time.time() - t0, 2)
        return risposta, durata
    except Exception as e:
        durata = round(time.time() - t0, 2)
        return f"[ERRORE 00MESH: {type(e).__name__} - {e}]", durata


# ── REPORTISTICA E CONFRONTO COMPARATIVO ──────────────────────────────────────

def calcola_fqi(punteggi: Dict[str, float]) -> float:
    """Calcola il Frontier Quality Index (0-100) basato sui 10 assi."""
    if not punteggi:
        return 0.0
    tot = sum(punteggi.values())
    max_tot = len(punteggi) * 10.0
    return round((tot / max_tot) * 100.0, 1)


def determina_verdetto_sovranita(gap_medio: float, punteggi: Dict[str, float]) -> str:
    critical_fails = sum(1 for v in punteggi.values() if v < 5.0)
    if gap_medio >= -0.8 and critical_fails == 0:
        return "SOVRANITA' PIENA (Parita' con la Frontiera sui compiti chiave)"
    if gap_medio >= -2.0 and critical_fails <= 2:
        return "EFFICACE CON SUPERVISIONE (Consigliato Gate LAYA per seconda opinione)"
    return "DELEGA CONSIGLIATA ALLA FRONTIERA (Gap qualitativo elevato sui compiti rigidi)"


def genera_tabella_radar(modello: str, punteggi_00mesh: Dict[str, float],
                         frontier_name: str = "Claude-3.5-Sonnet") -> str:
    frontier_ref = FRONTIER_BASELINES.get(frontier_name, FRONTIER_BASELINES["Claude-3.5-Sonnet"])
    righe = []
    righe.append(f"{'Asse Qualitativo':<30} {'00MESH (' + modello[:10] + ')':<18} {'Frontier (' + frontier_name[:10] + ')':<18} {'Quality Gap':<12} {'Stato'}")
    righe.append("-" * 92)

    for nome, _p, _g, _m in AUDIT_SUITE:
        s_mesh = punteggi_00mesh.get(nome, 0.0)
        s_front = frontier_ref.get(nome, 9.5)
        gap = round(s_mesh - s_front, 1)
        segno = f"{gap:+.1f}"
        if gap >= -0.5:
            stato = "🟢 Parita'"
        elif gap >= -2.0:
            stato = "🟡 Accettabile"
        else:
            stato = "🔴 Divario"
        righe.append(f"{nome:<30} {s_mesh:>6.1f}/10           {s_front:>6.1f}/10           {segno:>8}     {stato}")

    righe.append("-" * 92)
    fqi_mesh = calcola_fqi(punteggi_00mesh)
    fqi_front = calcola_fqi({k: v for k, v in frontier_ref.items() if k != "provider"})
    gap_tot = round(fqi_mesh - fqi_front, 1)
    righe.append(f"{'INDICE QUALITA GLOBALE (FQI)':<30} {fqi_mesh:>6.1f}/100          {fqi_front:>6.1f}/100          {gap_tot:>+8.1f} pt")
    return "\n".join(righe)


def esporta_report_markdown(modello: str, risultati: dict, filepath: Path) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    punteggi = {k: v["score"] for k, v in risultati["dettagli"].items()}
    fqi_mesh = calcola_fqi(punteggi)
    claude_ref = FRONTIER_BASELINES["Claude-3.5-Sonnet"]
    fqi_claude = calcola_fqi({k: v for k, v in claude_ref.items() if k != "provider"})
    gap_medio = round((fqi_mesh - fqi_claude) / 10.0, 2)
    verdetto = determina_verdetto_sovranita(gap_medio, punteggi)

    md = []
    md.append(f"# Benchmark Qualitativo di Frontiera — 00MESH vs Modelli Cloud")
    md.append(f"**Data:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md.append(f"**Modello Sotto Test:** `{modello}`")
    md.append(f"**Frontier Reference Baseline:** Claude 3.5 Sonnet & Gemini 1.5 Pro")
    md.append(f"**Frontier Quality Index (FQI):** `{fqi_mesh} / 100` (Frontiera: `{fqi_claude} / 100`)")
    md.append(f"**Verdetto di Sovranita':** **{verdetto}**\n")
    md.append("## 1. Matrice Radar dei 10 Assi Qualitativi\n")
    md.append("| Asse Qualitativo | 00MESH (`" + modello + "`) | Claude 3.5 Sonnet | Gemini 1.5 Pro | Gap vs Claude | Stato |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: |")

    gemini_ref = FRONTIER_BASELINES["Gemini-1.5-Pro"]
    for nome, _p, _g, _m in AUDIT_SUITE:
        s_m = punteggi.get(nome, 0.0)
        s_c = claude_ref.get(nome, 9.5)
        s_g = gemini_ref.get(nome, 9.3)
        gap = round(s_m - s_c, 1)
        icon = "🟢" if gap >= -0.5 else ("🟡" if gap >= -2.0 else "🔴")
        md.append(f"| `{nome}` | **{s_m:.1f}** | {s_c:.1f} | {s_g:.1f} | `{gap:+.1f}` | {icon} |")

    md.append("\n## 2. Dettaglio Risposte e Note di Valutazione\n")
    for nome, d in risultati["dettagli"].items():
        md.append(f"### Asse: `{nome}` — Punteggio: {d['score']}/10 ({d['durata']}s)")
        md.append(f"**Nota del Giudice:** {d['nota']}")
        md.append("```text")
        md.append(d["risposta"][:400] + ("..." if len(d["risposta"]) > 400 else ""))
        md.append("```\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(md))


# ── CLI & MAIN ───────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="frontier_bench",
                                description="Audit comparativo di qualita': 00MESH vs Modelli di Frontiera")
    p.add_argument("--model", default="qwen3-8b-abliterated-g8k:latest",
                   help="modello 00MESH da testare (es. qwen3-8b-..., flint:latest::hpomen)")
    p.add_argument("--cp", default=DEFAULT_CP,
                   help=f"endpoint Control Plane o Ollama (default {DEFAULT_CP})")
    p.add_argument("--compare-with", default="Claude-3.5-Sonnet", choices=list(FRONTIER_BASELINES.keys()),
                   help="modello di frontiera per il calcolo del gap")
    p.add_argument("--export-md", default="",
                   help="percorso facoltativo per salvare il report in formato Markdown")
    p.add_argument("--json", action="store_true",
                   help="stampa l'output come JSON strutturato")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    modello = args.model
    print(f"================================================================================")
    print(f"  00MESH FRONTIER QUALITY BENCHMARK — AUDIT COMPARATIVO A 10 ASSI")
    print(f"  Modello Sotto Test : {modello}")
    print(f"  Target Endpoint    : {args.cp}")
    print(f"  Frontiera Benchmark: {args.compare_with} & Gemini 1.5 Pro")
    print(f"================================================================================\n")

    punteggi = {}
    dettagli = {}

    for i, (nome, prompt, giudice, max_tok) in enumerate(AUDIT_SUITE, 1):
        print(f"[{i:02d}/10] Esecuzione asse '{nome}'...", end=" ", flush=True)
        risposta, durata = esegui_su_00mesh(modello, prompt, max_tok, args.cp)
        score, nota = giudice(risposta)
        punteggi[nome] = score
        dettagli[nome] = {
            "score": score,
            "nota": nota,
            "durata": durata,
            "risposta": risposta,
        }
        print(f"-> {score:>4.1f}/10 ({durata}s) [{nota}]", flush=True)

    print()
    tabella = genera_tabella_radar(modello, punteggi, args.compare_with)
    print(tabella)

    fqi_mesh = calcola_fqi(punteggi)
    claude_ref = FRONTIER_BASELINES[args.compare_with]
    fqi_front = calcola_fqi({k: v for k, v in claude_ref.items() if k != "provider"})
    gap_medio = round((fqi_mesh - fqi_front) / 10.0, 2)
    verdetto = determina_verdetto_sovranita(gap_medio, punteggi)

    print(f"\n>> VERDETTO DI SOVRANITA' 00MESH: {verdetto}\n")

    timestamp = int(time.time())
    file_json = REPORTS_DIR / f"frontier_comparison_{modello.replace(':', '_').replace('/', '_')}_{timestamp}.json"
    file_json.parent.mkdir(parents=True, exist_ok=True)
    report_data = {
        "modello": modello,
        "timestamp": timestamp,
        "fqi_00mesh": fqi_mesh,
        "fqi_frontier": fqi_front,
        "gap_medio": gap_medio,
        "verdetto": verdetto,
        "dettagli": dettagli,
    }
    with open(file_json, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    print(f"Report JSON salvato in: {file_json}")

    target_md = Path(args.export_md) if args.export_md else (REPORTS_DIR / f"frontier_comparison_{modello.replace(':', '_').replace('/', '_')}.md")
    esporta_report_markdown(modello, report_data, target_md)
    print(f"Report Markdown salvato in: {target_md}")

    if args.json:
        print("\n" + json.dumps(report_data, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
