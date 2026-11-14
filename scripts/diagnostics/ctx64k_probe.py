#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Quale modello Ollama regge davvero 64.000 token di contesto su questa macchina?

Perche' esiste: Hermes Agent rifiuta all'avvio i modelli con meno di 64.000
token di contesto. "Il modello e' stato addestrato a 128k" non basta: conta se,
caricato a 64k su QUESTA GPU, sta in VRAM, risponde in tempi usabili e fa ancora
una chiamata tool corretta quando il prompt e' lungo come una sessione vera.

Cosa misura, per ogni candidato:
  - contesto effettivo, memoria totale e quota su GPU (`/api/ps`);
  - una chiamata tool nativa con un prompt di ~20.000 token e una di ~50.000:
    un codice e' nascosto all'INIZIO del prompt e va riportato nell'argomento
    del tool, quindi un contesto troncato in silenzio si vede (codice sbagliato
    o `prompt_eval_count` molto piu' basso dell'atteso);
  - tempo totale e token/s in lettura e in generazione.

Perimetro e sicurezza:
  - parla SOLO con l'Ollama indicato da --ollama (default http://127.0.0.1:11434);
  - senza --run e' in SOLA LETTURA: elenca i candidati e cosa farebbe;
  - con --run CARICA i modelli uno alla volta: Ollama scarica dalla VRAM quello
    che c'era (es. Flint). Non lanciarlo mentre gira un altro lavoro sulla GPU.
    Alla fine dice cosa era caricato prima, ma non lo ricarica.
  - non crea, non cancella e non modifica modelli.

Uso:
    python3 scripts/diagnostics/ctx64k_probe.py                 # elenco, sola lettura
    python3 scripts/diagnostics/ctx64k_probe.py --run           # misura tutti i candidati
    python3 scripts/diagnostics/ctx64k_probe.py --run --models granite3.3:8b
    python3 scripts/diagnostics/ctx64k_probe.py --run --json

Solo libreria standard e file unico: deve poter girare dentro il container di un
nodo (dove il repository puo' essere un'altra versione), spedito via mesh_exec.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

OLLAMA_DEFAULT = "http://127.0.0.1:11434"
CTX_RICHIESTO = 64000
TAGLIE_PROMPT = (20000, 50000)
CARATTERI_PER_TOKEN = 4  # stima grezza: il conto vero e' prompt_eval_count
CODICE = "7Q4-ZED-91"
TOOL_ATTESO = "registra_codice"


def _http(base, percorso, corpo=None, timeout=30):
    dati = json.dumps(corpo).encode() if corpo is not None else None
    richiesta = urllib.request.Request(
        base.rstrip("/") + percorso, data=dati,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(richiesta, timeout=timeout) as risposta:
        return json.load(risposta)


def contesto_addestrato(show):
    """Il contesto massimo dichiarato dal modello (0 se non lo dichiara)."""
    valori = [v for k, v in (show.get("model_info") or {}).items()
              if k.endswith("context_length") and isinstance(v, int)]
    return max(valori) if valori else 0


def e_candidato(show, ctx=CTX_RICHIESTO):
    """(vero/falso, motivo): serve tool calling e un contesto addestrato >= ctx."""
    if "tools" not in (show.get("capabilities") or []):
        return False, "non dichiara tool calling"
    addestrato = contesto_addestrato(show)
    if addestrato < ctx:
        return False, f"contesto addestrato {addestrato} < {ctx}"
    return True, f"contesto addestrato {addestrato}"


def schemi_tool(quanti=20):
    """Il tool da chiamare piu' altri di contorno: una sessione agente ne porta decine."""
    tool = [{
        "type": "function",
        "function": {
            "name": TOOL_ATTESO,
            "description": "Registra il codice di verifica comunicato all'inizio della conversazione.",
            "parameters": {
                "type": "object",
                "properties": {"codice": {"type": "string", "description": "Il codice di verifica, identico."}},
                "required": ["codice"],
            },
        },
    }]
    for i in range(max(0, quanti - 1)):
        tool.append({
            "type": "function",
            "function": {
                "name": f"strumento_{i:02d}",
                "description": f"Strumento di contorno numero {i}: legge, cerca o scrive risorse del progetto.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "percorso": {"type": "string", "description": "Percorso della risorsa."},
                        "limite": {"type": "integer", "description": "Numero massimo di risultati."},
                    },
                    "required": ["percorso"],
                },
            },
        })
    return tool


def costruisci_messaggi(token_prompt):
    """Codice all'inizio, riempitivo in mezzo, richiesta alla fine."""
    riga = "Nota di lavoro {n}: il modulo {n} e' stato verificato e non richiede interventi. "
    caratteri = token_prompt * CARATTERI_PER_TOKEN
    pezzi, lunghezza, n = [], 0, 0
    while lunghezza < caratteri:
        testo = riga.format(n=n)
        pezzi.append(testo)
        lunghezza += len(testo)
        n += 1
    return [
        {"role": "system", "content": "Sei un agente operativo. Usa gli strumenti quando ti viene chiesto."},
        {"role": "user", "content": (
            f"Il codice di verifica di questa sessione e' {CODICE}. Tienilo a mente.\n\n"
            + "".join(pezzi)
            + f"\n\nOra chiama lo strumento {TOOL_ATTESO} passando il codice di verifica "
              "che ti ho dato all'inizio. Non rispondere a parole.")},
    ]


def giudica(risposta):
    """(ok, motivo) sulla risposta di /api/chat: tool giusto con il codice giusto."""
    chiamate = ((risposta.get("message") or {}).get("tool_calls")) or []
    if not chiamate:
        return False, "nessuna chiamata tool"
    funzione = (chiamate[0].get("function") or {})
    if funzione.get("name") != TOOL_ATTESO:
        return False, f"tool sbagliato: {funzione.get('name')!r}"
    argomenti = funzione.get("arguments") or {}
    if isinstance(argomenti, str):
        try:
            argomenti = json.loads(argomenti)
        except ValueError:
            return False, "argomenti non JSON"
    if argomenti.get("codice") != CODICE:
        return False, f"codice sbagliato: {argomenti.get('codice')!r} (contesto troncato?)"
    return True, "chiamata tool corretta"


def _token_al_secondo(conteggio, durata_ns):
    return round(conteggio / (durata_ns / 1e9), 1) if conteggio and durata_ns else None


def prova(base, modello, token_prompt, ctx=CTX_RICHIESTO, timeout=1800, http=_http):
    """Una chiamata tool con un prompt della taglia data. Non solleva: riporta l'errore."""
    esito = {"prompt_token_attesi": token_prompt}
    inizio = time.time()
    try:
        risposta = http(base, "/api/chat", {
            "model": modello,
            "messages": costruisci_messaggi(token_prompt),
            "tools": schemi_tool(),
            "stream": False,
            "keep_alive": "2m",
            "options": {"num_ctx": ctx, "temperature": 0},
        }, timeout=timeout)
    except (urllib.error.URLError, OSError, ValueError) as errore:
        esito.update(ok=False, motivo=f"errore: {errore}", secondi=round(time.time() - inizio, 1))
        return esito
    ok, motivo = giudica(risposta)
    letti = risposta.get("prompt_eval_count") or 0
    if ok and letti and letti < token_prompt * 0.5:
        ok, motivo = False, f"prompt letto solo per {letti} token: contesto troncato"
    esito.update(
        ok=ok, motivo=motivo, secondi=round(time.time() - inizio, 1),
        prompt_token_letti=letti,
        lettura_tok_s=_token_al_secondo(letti, risposta.get("prompt_eval_duration")),
        generazione_tok_s=_token_al_secondo(risposta.get("eval_count"), risposta.get("eval_duration")),
    )
    return esito


def stato_caricato(base, modello, http=_http):
    """Contesto effettivo, memoria e quota GPU del modello, da /api/ps."""
    for voce in (http(base, "/api/ps").get("models") or []):
        if voce.get("name") == modello or voce.get("model") == modello:
            totale, vram = voce.get("size") or 0, voce.get("size_vram") or 0
            return {
                "contesto": voce.get("context_length"),
                "memoria_gb": round(totale / 1e9, 1),
                "vram_gb": round(vram / 1e9, 1),
                "quota_gpu": round(100 * vram / totale) if totale else None,
            }
    return {}


def scarica(base, modello, http=_http):
    try:
        http(base, "/api/generate", {"model": modello, "keep_alive": 0}, timeout=60)
    except (urllib.error.URLError, OSError, ValueError):
        pass


def elenca(base, ctx=CTX_RICHIESTO, solo=None, http=_http):
    """Tutti i modelli installati con (candidato si/no, motivo)."""
    righe = []
    for modello in (http(base, "/api/tags").get("models") or []):
        nome = modello["name"]
        if solo and nome not in solo:
            continue
        try:
            show = http(base, "/api/show", {"model": nome})
        except (urllib.error.URLError, OSError, ValueError) as errore:
            righe.append({"modello": nome, "candidato": False, "motivo": f"show fallito: {errore}"})
            continue
        ok, motivo = e_candidato(show, ctx)
        righe.append({"modello": nome, "candidato": ok, "motivo": motivo,
                      "peso_gb": round((modello.get("size") or 0) / 1e9, 1)})
    return righe


def misura(base, modello, ctx=CTX_RICHIESTO, taglie=TAGLIE_PROMPT, timeout=1800, http=_http):
    risultato = {"modello": modello, "prove": []}
    for indice, taglia in enumerate(taglie):
        esito = prova(base, modello, taglia, ctx, timeout, http)
        risultato["prove"].append(esito)
        if indice == 0:
            try:
                risultato.update(stato_caricato(base, modello, http))
            except (urllib.error.URLError, OSError, ValueError):
                pass
        if not esito["ok"] and esito["motivo"].startswith("errore"):
            break  # non caricabile o timeout: inutile la taglia piu' grande
    scarica(base, modello, http)
    risultato["idoneo"] = (len(risultato["prove"]) == len(taglie)
                           and all(p["ok"] for p in risultato["prove"])
                           and (risultato.get("contesto") or 0) >= ctx)
    return risultato


def ordina(risultati):
    """Prima gli idonei; fra questi, quota GPU piu' alta e poi generazione piu' veloce."""
    def chiave(r):
        velocita = min((p.get("generazione_tok_s") or 0) for p in r["prove"]) if r["prove"] else 0
        return (not r["idoneo"], -(r.get("quota_gpu") or 0), -velocita)
    return sorted(risultati, key=chiave)


def tabella(risultati):
    righe = [f"{'modello':<58} {'ctx':>6} {'mem GB':>7} {'GPU%':>5}  " +
             "  ".join(f"{t // 1000}k: esito/s/tok-s" for t in TAGLIE_PROMPT)]
    for r in risultati:
        prove = "  ".join(
            f"{'OK' if p['ok'] else 'NO'}/{p['secondi']}/{p.get('generazione_tok_s') or '-'}"
            for p in r["prove"])
        righe.append(f"{r['modello'][:58]:<58} {str(r.get('contesto') or '-'):>6} "
                     f"{str(r.get('memoria_gb') or '-'):>7} {str(r.get('quota_gpu') or '-'):>5}  {prove}"
                     f"  {'IDONEO' if r['idoneo'] else ''}")
        for p in r["prove"]:
            if not p["ok"]:
                righe.append(f"    {p['prompt_token_attesi'] // 1000}k: {p['motivo']}")
    return "\n".join(righe)


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ollama", default=OLLAMA_DEFAULT, help=f"Ollama nativo (default {OLLAMA_DEFAULT})")
    p.add_argument("--models", default="", help="solo questi modelli, separati da virgola")
    p.add_argument("--ctx", type=int, default=CTX_RICHIESTO, help="contesto richiesto (default 64000)")
    p.add_argument("--timeout", type=int, default=1800, help="secondi massimi per singola prova")
    p.add_argument("--run", action="store_true",
                   help="CARICA i modelli e misura (scarica dalla VRAM cio' che c'era)")
    p.add_argument("--json", action="store_true", help="stampa il risultato come JSON")
    return p


def main(argv=None, http=_http):
    args = build_parser().parse_args(argv)
    solo = {m.strip() for m in args.models.split(",") if m.strip()} or None
    try:
        prima = [m.get("name") for m in (http(args.ollama, "/api/ps").get("models") or [])]
        elenco = elenca(args.ollama, args.ctx, solo, http)
    except (urllib.error.URLError, OSError, ValueError) as errore:
        print(f"Ollama non raggiungibile su {args.ollama}: {errore}", file=sys.stderr)
        return 2
    candidati = [r["modello"] for r in elenco if r["candidato"]]

    if not args.run:
        uscita = {"modalita": "sola lettura", "caricati_ora": prima, "modelli": elenco}
        if args.json:
            print(json.dumps(uscita, ensure_ascii=False, indent=2))
        else:
            print(f"Sola lettura. Caricati ora: {prima or 'nessuno'}")
            for r in elenco:
                print(f"  {'CANDIDATO' if r['candidato'] else 'escluso  '} {r['modello']:<58} {r['motivo']}")
            print(f"\nCon --run verrebbero caricati a {args.ctx} token, uno alla volta: {len(candidati)} modelli."
                  "\nATTENZIONE: i modelli caricati ora verrebbero scaricati dalla VRAM.")
        return 0

    risultati = []
    for nome in candidati:
        print(f"[misura] {nome} ...", file=sys.stderr, flush=True)
        risultati.append(misura(args.ollama, nome, args.ctx, TAGLIE_PROMPT, args.timeout, http))
    risultati = ordina(risultati)
    if args.json:
        print(json.dumps({"caricati_prima": prima, "risultati": risultati}, ensure_ascii=False, indent=2))
    else:
        print(tabella(risultati))
        print(f"\nCaricati prima della misura (non ricaricati): {prima or 'nessuno'}")
    return 0 if any(r["idoneo"] for r in risultati) else 1


if __name__ == "__main__":
    sys.exit(main())
