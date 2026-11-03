# SPDX-License-Identifier: Apache-2.0
"""Banco di prova per modelli locali: domande con esito verificabile da codice.

Perche' esiste: giudicare un modello "a sensazione" dice poco, e di solito dice
la cosa sbagliata (una risposta fluente suona giusta anche quando e' falsa). Qui
ogni sonda ha un ESITO verificabile da una funzione: la capitale e' giusta o no,
il codice gira o no, il JSON si parse o no. Il confronto fra modelli diventa una
tabella, non un'opinione.

Un dettaglio che conta piu' di quanto sembri: il tetto di token. Un modello che
non si ferma (o che "pensa" a lungo senza rispondere â€” succede con le famiglie
reasoning) va fermato, altrimenti blocca l'intera sessione. Ogni sonda ha un
budget di parole; se lo sfora, l'esito e' LOOP/LENTO, non "sbagliato": e' un modo
diverso di non essere affidabile, e va distinto da una risposta sbagliata.

Le quattro sonde `codice_*` (palindromo, durata, bugfix, intervalli) esistono per
il ruolo coder (`HS_MODEL_CODER`): il contratto sta negli assert dei driver, non
nella prosa del prompt, e il codice viene eseguito. Servono a decidere un
download da 5 GB con un esito, non con un'impressione.


Uso:

    python3 scripts/model_bench.py                        # i modelli di default
    python3 scripts/model_bench.py --models minicpm5:latest,qwen3:8b
    python3 scripts/model_bench.py --node macbook         # pinnati su un nodo
    python3 scripts/model_bench.py --think false          # reasoning forzato off
    python3 scripts/model_bench.py --json                 # risultato come JSON

Attenzione al flag: sul percorso del Control Plane l'endpoint OpenAI-compatibile
IGNORA `think` (vedi docs/architecture.md); solo `--think false` viene tradotto
nel percorso nativo di Ollama, quindi `--think true` non forza il ragionamento.
Per misurare il costo del pensiero serve una chiamata diretta a `/api/chat`.

I modelli si pinnano col suffisso ::<nodo> cosi' il confronto avviene sullo STESSO
backend: due modelli su macchine diverse non sono confrontabili (GPU diverse,
latenza di rete diversa). Solo libreria standard, come mesh_health.py: gira anche
sul Windows del collega senza installare niente.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

CP_DEFAULT = os.environ.get("CONTROL_PLANE_URL", "http://localhost:8085").rstrip("/")
DEFAULT_MODELS = ("openbmb/minicpm5:latest", "qwen2:0.5b", "qwen3:8b", "gemma4:e4b")
TIMEOUT_S = 180
MAX_SECONDS = 150   # rete di sicurezza: il segnale vero e' il budget di TOKEN


# â”€â”€ SONDE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Ogni sonda e' (nome, prompt, giudice, esito atteso, budget_di_parole). Il
# giudice torna True/False (o una tupla (ok, nota)) a partire dalla risposta.
def _json(risposta):
    m = re.search(r"\{.*\}", risposta, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def estrai_codice(risposta):
    """Estrae il codice da una risposta, con o senza triple backtick."""
    m = re.search(r"```(?:python)?\s*\n(.*?)```", risposta, re.S | re.I)
    if m:
        return m.group(1).strip()
    return re.sub(r"^```(?:python)?\s*|\s*```$", "", risposta, flags=re.I | re.S).strip()


def codice_esegue(risposta, vincolo, driver, file_uscita=None):
    """Vero se il codice estratto definisce `vincolo`, gira e passa `driver`.

    Generalizzazione di `codice_ok`: il contratto non sta nella prosa del
    prompt, sta negli assert del driver. "Quasi giusto" non passa, e nessuna
    sonda si fida del testo della risposta: il file viene eseguito.
    """
    if file_uscita is None:
        file_uscita = os.path.join(tempfile.gettempdir(), "_model_bench_codice.py")
    sorgente = estrai_codice(risposta)
    if vincolo not in sorgente:
        return False, f"manca {vincolo} nel codice"
    with open(file_uscita, "w", encoding="utf-8") as f:
        # Il driver si appende dopo una riga nuova: senza separatore finisce
        # attaccato all'ultima riga del modello (`return x` + `print(...)`) e un
        # codice giusto diventa SyntaxError.
        f.write(sorgente.rstrip() + "\n" + driver.lstrip("\n"))
    try:
        esito = subprocess.run([sys.executable, file_uscita],
                               capture_output=True, text=True, timeout=15,
                               encoding="utf-8", errors="replace")

    except Exception as e:
        return False, f"timeout/errore: {type(e).__name__}"
    if "CODICE-OK" in esito.stdout:
        return True, "gira e passa gli assert"
    coda = (esito.stderr or esito.stdout).strip().splitlines()
    return False, "gira ma sbaglia: " + (coda[-1][:70] if coda else "nessun output")


# I tre driver dei casi che un coder sbaglia davvero: casi limite (stringa
# vuota, None, lista vuota) e un mutamento della lista in ingresso. Restano
# stringhe, non file: la sonda li scrive accanto al codice del modello.
DRIVER_DURATA = (
    "\n\nassert durata_in_secondi('1h30m') == 5400\n"
    "assert durata_in_secondi('45s') == 45\n"
    "assert durata_in_secondi('2h') == 7200\n"
    "assert durata_in_secondi('10m30s') == 630\n"
    "for rotto in ('', 'abc', '1x'):\n"
    "    try:\n"
    "        durata_in_secondi(rotto)\n"
    "    except ValueError:\n"
    "        pass\n"
    "    else:\n"
    "        raise AssertionError(rotto)\n"
    "print('CODICE-OK')\n"
)

DRIVER_MEDIA = (
    "\n\nassert media([]) == 0.0\n"
    "assert media([2, 4]) == 3.0\n"
    "assert media([1, 2, 3, 4]) == 2.5\n"
    "assert media([None, 2, None, 4]) == 3.0\n"
    "assert isinstance(media([1]), float)\n"
    "print('CODICE-OK')\n"
)

DRIVER_INTERVALLI = (
    "\n\nassert unisci([]) == []\n"
    "assert unisci([(1, 3), (2, 6), (8, 10)]) == [(1, 6), (8, 10)]\n"
    "assert unisci([(5, 7), (1, 2), (2, 4)]) == [(1, 4), (5, 7)]\n"
    "dati = [(5, 6), (1, 2)]\n"
    "unisci(dati)\n"
    "assert dati == [(5, 6), (1, 2)], 'lista in ingresso modificata'\n"
    "print('CODICE-OK')\n"
)


def codice_ok(risposta, file_uscita=None):
    """Vero se la funzione generata gira E passa gli assert. Non si fida del
    testo della risposta: esegue il codice."""
    return codice_esegue(
        risposta, "def is_palindrome",
        "\n\nimport sys\nassert is_palindrome('radar') is True\n"
        "assert is_palindrome('Ciao') is False\nprint('CODICE-OK')\n",
        file_uscita or os.path.join(tempfile.gettempdir(), "_model_bench_pal.py"))



def giudice_no_e(a):
    """Vero se la frase ha senso minimo (len >= 6) e non contiene mai la lettera 'e'."""
    testo = a.strip()
    if len(testo) < 6:
        return False, "frase troppo corta"
    if "e" in testo.lower():
        return False, "contiene la lettera 'e'"
    return True, "nessuna lettera 'e'"


def giudice_json_puro(a):
    """Vero solo se la risposta e' un JSON valido SENZA markdown o preamboli (zero chatter)."""
    t = a.strip()
    if t.startswith("```") or t.endswith("```"):
        return False, "contiene blocchi di codice markdown (non e' raw JSON)"
    if not (t.startswith("{") and t.endswith("}")):
        return False, "contiene testo prima o dopo il blocco JSON (chatter)"
    try:
        d = json.loads(t)
        if isinstance(d, dict) and "temperatura" in d and "stato" in d:
            return True, "JSON puro e conforme"
        return False, "mancano le chiavi richieste ('temperatura', 'stato')"
    except Exception:
        return False, "sintassi JSON non valida"


def giudice_tool_call(a):
    """Vero se la risposta simula una tool-call corretta in formato standard senza rumore."""
    t = a.strip()
    if not (t.startswith("{") and t.endswith("}")):
        return False, "contiene testo o markdown fuori dal JSON"
    try:
        d = json.loads(t)
        if d.get("name") != "leggi_file":
            return False, f"nome funzione errato: {d.get('name')!r}"
        args = d.get("arguments") or {}
        if not isinstance(args, dict) or args.get("percorso") != "docs/manuale.md":
            return False, f"argomenti errati: {args}"
        return True, "formato tool call valido"
    except Exception:
        return False, "sintassi JSON non valida"


def giudice_bulloni(a):
    """Vero se individua il tempo invariato (5 min) invece dell'errore intuitivo (100 min)."""
    ha_5 = bool(re.search(r"\b5\b", a))
    ha_100 = bool(re.search(r"\b100\b", a))
    if ha_5 and not ha_100:
        return True, "ragionamento corretto (5 minuti)"
    return False, "errore logico (ha risposto 100 o non ha indicato 5)"


PROBE = [
    ("fatto_capitale", "Qual e' la capitale dell'Australia? Rispondi con una sola parola.",
     lambda a: ("canberra" in a.lower() and "sydney" not in a.lower()), "Canberra", 12),
    ("matematica_orario", "Un treno parte alle 14:30 e viaggia 90 minuti. A che ora arriva? Rispondi solo con l'orario HH:MM.",
     lambda a: "16:00" in a.replace("16.00", "16:00"), "16:00", 10),
    ("matematica_sconto", "Un maglione costa 80 euro e c'e' uno sconto del 25%. Quanto pago? Rispondi solo col numero.",
     lambda a: bool(re.search(r"\b60\b", a)) and "20" not in a, "60", 10),
    ("logica_famiglia", "In una famiglia ci sono due padri e due figli, ma solo tre persone. Com'e' possibile? Spiega in una frase.",
     lambda a: ("nonno" in a.lower()), "nonno, padre, figlio", 30),
    ("conteggio_r", "Quante lettere 'r' contiene la parola 'frigorifero'? Rispondi solo con il numero.",
     lambda a: bool(re.search(r"\b3\b", a)), "3", 10),
    ("codice_palindromo", "Scrivi SOLO il codice di una funzione Python is_palindrome(s) che torna True se la stringa e' un palindromo (ignorando le maiuscole). Nient'altro.",
     codice_ok, "funzione che gira", 120),
    # Le tre sonde che separano un coder da un modello che "sa parlare di
    # codice": conversione con casi limite, correzione di un bug con contratto
    # scritto, algoritmo che non deve mutare l'ingresso.
    ("codice_durata", "Scrivi SOLO il codice Python di una funzione durata_in_secondi(testo) che converte '1h30m', '45s', '2h', '10m30s' in secondi interi, accettando h, m, s in quest'ordine e sollevando ValueError su stringa vuota o formato non riconosciuto. Nient'altro.",
     lambda a: codice_esegue(a, "def durata_in_secondi", DRIVER_DURATA,
                             os.path.join(tempfile.gettempdir(), "_model_bench_durata.py")),
     "funzione che gira", 400),
    ("codice_bugfix", "Questo codice ha due bug: va in ZeroDivisionError su lista vuota e non ignora i None. Il contratto: media([]) == 0.0, i None si saltano, il risultato e' un float. Correggi mantenendo nome e firma, e rispondi SOLO col codice.\n\ndef media(valori):\n    return sum(valori) / len(valori)",
     lambda a: codice_esegue(a, "def media", DRIVER_MEDIA,
                             os.path.join(tempfile.gettempdir(), "_model_bench_media.py")),
     "bug corretto", 400),
    ("codice_intervalli", "Scrivi SOLO il codice Python di una funzione unisci(intervalli) che riceve una lista di tuple (inizio, fine) anche disordinata e torna la lista ordinata degli intervalli uniti; quelli che si toccano (fine == inizio successivo) si uniscono, lista vuota da' lista vuota, e la lista in ingresso non va modificata. Nient'altro.",
     lambda a: codice_esegue(a, "def unisci", DRIVER_INTERVALLI,
                             os.path.join(tempfile.gettempdir(), "_model_bench_intervalli.py")),
     "funzione che gira", 400),

    ("json", "Rispondi SOLO con un JSON valido, senza altro testo: {\"citta\": \"...\", \"abitanti\": <numero>} per Venezia.",
     lambda a: (lambda d: bool(d) and "citta" in d and "abitanti" in d)(_json(a)), "JSON con i campi", 20),
    ("json_puro_zero_chatter", "Rispondi ESCLUSIVAMENTE con un JSON valido con le chiavi 'temperatura' (numero) e 'stato' (stringa) per una giornata di sole. Nessun preambolo, nessun testo prima o dopo, nessun blocco markdown.",
     giudice_json_puro, "JSON puro senza chatter", 30),
    ("tool_call_formato", "Sei un agente. Devi invocare la funzione 'leggi_file' con parametro 'percorso' uguale a 'docs/manuale.md'. Rispondi SOLO con il JSON nel formato: {\"name\": \"leggi_file\", \"arguments\": {\"percorso\": \"docs/manuale.md\"}}. Nient'altro.",
     giudice_tool_call, "JSON tool-call valido", 30),
    ("allucinazione", "Chi ha scritto il romanzo 'Il canto del merlo azzurro'? Se non lo sai, rispondi 'non lo so'.",
     lambda a: any(x in a.lower() for x in ("non lo so", "non lo conosco", "non sono a conoscenza", "non esiste", "non risulta")), "ammette di non sapere", 30),
    ("vincolo_negativo_no_e", "Scrivi una frase di senso compiuto sul tempo atmosferico senza usare MAI la lettera 'e' (ne' maiuscola ne' minuscola). Nient'altro.",
     giudice_no_e, "frase senza lettera 'e'", 30),
    ("logica_bulloni", "Se 5 macchine impiegano 5 minuti per fabbricare 5 bulloni, quanti minuti impiegano 100 macchine per fabbricare 100 bulloni? Rispondi solo col numero di minuti.",
     giudice_bulloni, "5", 15),
]

# Raggruppamento per capacita' operative in HyperSpace / 00MESH:
CATEGORIE_SONDE = {
    "coding": [
        "codice_palindromo", "codice_durata", "codice_bugfix", "codice_intervalli"
    ],
    "strict_format": [
        "json", "json_puro_zero_chatter", "tool_call_formato"
    ],
    "reasoning_logic": [
        "matematica_orario", "matematica_sconto", "logica_famiglia", "logica_bulloni", "conteggio_r"
    ],
    "reliability_constraints": [
        "fatto_capitale", "allucinazione", "vincolo_negativo_no_e"
    ],
}


def sonde_attive(categorie=None):
    """Restituisce l'elenco delle sonde filtrate per categoria, o tutte se None."""
    if not categorie:
        return list(PROBE)
    attivi = set()
    for cat in categorie:
        attivi.update(CATEGORIE_SONDE.get(cat, []))
    return [p for p in PROBE if p[0] in attivi]


# ── STREAMING & TELEMETRIA (puro, testabile senza rete) ──────────────────────
class StreamResult(tuple):
    """Tupla (testo, limite) arricchita con telemetria temporale e throughput.

    Piena retrocompatibilita': `testo, limite = consume_stream(...)` continua a
    funzionare indisturbato ovunque nel codice e nei test. Chi vuole la telemetria
    accede a `res.stats`, `res.ttft`, `res.tok_s`.
    """
    def __new__(cls, testo, limite, stats=None):
        return super().__new__(cls, (testo, limite))

    def __init__(self, testo, limite, stats=None):
        self.stats = stats or {}

    @property
    def ttft(self):
        return self.stats.get("ttft", 0.0)

    @property
    def tok_s(self):
        return self.stats.get("tok_s", 0.0)

    @property
    def n_tokeni(self):
        return self.stats.get("n_tokeni", 0)

    @property
    def elapsed(self):
        return self.stats.get("elapsed", 0.0)


def consume_stream(linee, max_tok):
    """Da un iteratore di righe SSE a `StreamResult(testo, limite, stats)`.

    `linee` e' una sequenza di stringhe gia' decodificate, come le righe del body
    streamato: "data: {...}" con un delta, "data: [DONE]", o rumore da ignorare.
    Il limite e' "ok", "loop" (sfora il budget di parole: non si ferma) o "lento"
    (non conclude in tempo). Misura anche TTFT (Time To First Token) e tok/s.
    """
    testo = ""
    n_tokeni = 0
    t0 = time.time()
    t_first = None
    limite = "ok"
    for riga in linee:
        riga = str(riga)
        if not riga.startswith("data:"):
            continue
        dato = riga[5:].strip()
        if dato == "[DONE]":
            break
        try:
            pezzo = json.loads(dato)["choices"][0].get("delta", {}).get("content") or ""
        except Exception:
            continue
        if pezzo and t_first is None:
            t_first = time.time()
        testo += pezzo
        n_tokeni += len(pezzo.split())
        if n_tokeni > max_tok:
            limite = "loop"
            break
        if time.time() - t0 > MAX_SECONDS:
            limite = "lento"
            break

    elapsed = time.time() - t0
    ttft = (t_first - t0) if t_first is not None else elapsed
    gen_time = max(elapsed - ttft, 0.001)
    tok_s = round(n_tokeni / gen_time, 1) if (n_tokeni > 0 and t_first is not None) else 0.0

    stats = {
        "ttft": round(ttft, 3),
        "elapsed": round(elapsed, 3),
        "n_tokeni": n_tokeni,
        "tok_s": tok_s,
    }
    return StreamResult(testo.strip(), limite, stats)


def ask(modello, prompt, max_tok=40, cp=CP_DEFAULT, think=None, opener=None, timeout=TIMEOUT_S):
    """Una completion verso il CP, in stream. `think` e' il flag JSON esplicito:
    None = lascia decidere al CP (che di default spegne il reasoning)."""
    corpo = {"model": modello, "messages": [{"role": "user", "content": prompt}],
             "stream": True, "temperature": 0}
    if think is not None:
        corpo["think"] = bool(think)
    dati = json.dumps(corpo).encode()
    richiesta = urllib.request.Request(f"{cp}/v1/chat/completions", data=dati,
                                       headers={"Content-Type": "application/json"})
    apre = opener or urllib.request.urlopen
    with apre(richiesta, timeout=timeout) as risposta:
        righe = (riga.decode(errors="replace") for riga in risposta)
        return consume_stream(righe, max_tok)


def segna(giudice, risposta):
    esito = giudice(risposta)
    return esito if isinstance(esito, tuple) else (esito, "")


# ── PROFILATORE DI CAPACITA' E RUOLI ─────────────────────────────────────────
def profila_modello(righe):
    """Calcola il profilo empirico per categorie e raccomanda i ruoli idonei."""
    scores = {}
    for cat, lista_sonde in CATEGORIE_SONDE.items():
        presenti = [s for s in lista_sonde if s in righe]
        if not presenti:
            continue
        passati = sum(1 for s in presenti if righe[s].get("ok") is True)
        scores[cat] = {
            "pass": passati,
            "tot": len(presenti),
            "pct": round(passati / len(presenti) * 100, 1) if presenti else 0.0,
        }

    tok_s_vals = [
        r.get("stats", {}).get("tok_s", 0.0)
        for r in righe.values()
        if isinstance(r.get("stats"), dict) and r.get("stats", {}).get("tok_s", 0.0) > 0
    ]
    ttft_vals = [
        r.get("stats", {}).get("ttft", 0.0)
        for r in righe.values()
        if isinstance(r.get("stats"), dict) and r.get("stats", {}).get("ttft", 0.0) > 0
    ]
    avg_tok_s = round(sum(tok_s_vals) / len(tok_s_vals), 1) if tok_s_vals else 0.0
    avg_ttft = round(sum(ttft_vals) / len(ttft_vals), 3) if ttft_vals else 0.0

    ruoli = []
    coding_pct = scores.get("coding", {}).get("pct", 0.0)
    format_pct = scores.get("strict_format", {}).get("pct", 0.0)
    logic_pct = scores.get("reasoning_logic", {}).get("pct", 0.0)
    rel_pct = scores.get("reliability_constraints", {}).get("pct", 0.0)

    if coding_pct >= 75.0 and format_pct >= 60.0:
        ruoli.append("coder")
    if logic_pct >= 80.0 and rel_pct >= 66.0:
        ruoli.append("planner")
    if format_pct >= 90.0:
        ruoli.append("tool_calling")
    if avg_tok_s >= 35.0 and format_pct >= 60.0:
        ruoli.append("fast_router")
    if not ruoli:
        ruoli.append("chat_only")

    return {
        "scores": scores,
        "avg_tok_s": avg_tok_s,
        "avg_ttft": avg_ttft,
        "recommended_roles": ruoli,
    }


# ── ESECUZIONE ───────────────────────────────────────────────────────────────
def esegui(modelli, cp=CP_DEFAULT, think=None, progresso=None, categorie=None):
    """Esegue le sonde sui modelli indicati. Ritorna una struttura riusabile
    da chi vuole il JSON o la profilazione automatica."""
    sonde = sonde_attive(categorie)
    risultati = {}
    for modello in modelli:
        righe = {}
        for nome, prompt, giudice, atteso, max_tok in sonde:
            try:
                res = ask(modello, prompt, max_tok, cp=cp, think=think)
                risposta, limite = res
                stats = getattr(res, "stats", {})
                if limite == "ok":
                    ok, nota = segna(giudice, risposta)
                else:
                    ok, nota = False, f"non conclude ({limite})"
                righe[nome] = {"ok": ok, "limite": limite, "risposta": risposta, "nota": nota, "stats": stats}
                if progresso:
                    try:
                        progresso(modello, nome, ok, limite, risposta, stats)
                    except TypeError:
                        progresso(modello, nome, ok, limite, risposta)
            except urllib.error.HTTPError as e:
                righe[nome] = {"ok": None, "limite": "err", "nota": f"HTTP {e.code}", "stats": {}}
            except urllib.error.URLError as e:
                righe[nome] = {"ok": None, "limite": "err", "nota": f"rete: {e.reason}", "stats": {}}
            except Exception as e:
                righe[nome] = {"ok": None, "limite": "err", "nota": f"{type(e).__name__}: {str(e)[:80]}", "stats": {}}
        risultati[modello] = righe
    return risultati


def riepilogo(risultati):
    out = {}
    for modello, righe in risultati.items():
        buone = sum(1 for r in righe.values() if r.get("ok") is True)
        loop = sum(1 for r in righe.values() if r.get("limite") == "loop")
        lenti = sum(1 for r in righe.values() if r.get("limite") == "lento")
        prof = profila_modello(righe)
        out[modello] = {
            "corrette": buone,
            "su": len(righe),
            "loop": loop,
            "lenti": lenti,
            "profilo": prof,
        }
    return out


def tabella(risultati):
    modelli = list(risultati)
    righe = []
    testa = "{:<24}".format("sonda") + "".join("{:<14}".format(m.split(":")[0][:13]) for m in modelli)
    righe.append(testa)
    righe.append("-" * len(testa))

    tutte_sonde = []
    for nome, _p, _g, _a, _m in PROBE:
        if any(nome in risultati[m] for m in modelli):
            tutte_sonde.append(nome)

    for nome in tutte_sonde:
        fila = "{:<24}".format(nome)
        for modello in modelli:
            r = risultati[modello].get(nome, {})
            cella = "ERR" if r.get("ok") is None else ("LOOP" if r.get("limite") == "loop"
                    else ("LENTO" if r.get("limite") == "lento" else ("OK " if r.get("ok") else "NO ")))
            fila += "{:<14}".format(cella)
        righe.append(fila)

    righe.append("-" * len(testa))
    # Righe categorie
    for cat in CATEGORIE_SONDE:
        fila = "{:<24}".format(f"[{cat}]")
        for modello in modelli:
            prof = profila_modello(risultati[modello])
            c_score = prof["scores"].get(cat)
            val = f"{c_score['pass']}/{c_score['tot']} ({int(c_score['pct'])}%)" if c_score else "-"
            fila += "{:<14}".format(val)
        righe.append(fila)

    righe.append("-" * len(testa))
    # Throughput e Ruoli consigliati
    fila_spd = "{:<24}".format("[tok/s medio]")
    fila_ttft = "{:<24}".format("[ttft medio s]")
    fila_ruoli = "{:<24}".format("[ruoli consigliati]")
    for modello in modelli:
        prof = profila_modello(risultati[modello])
        fila_spd += "{:<14}".format(f"{prof['avg_tok_s']} t/s" if prof['avg_tok_s'] else "-")
        fila_ttft += "{:<14}".format(f"{prof['avg_ttft']}s" if prof['avg_ttft'] else "-")
        fila_ruoli += "{:<14}".format(",".join(prof['recommended_roles'])[:13])
    righe.append(fila_spd)
    righe.append(fila_ttft)
    righe.append(fila_ruoli)
    return "\n".join(righe)


def build_parser():
    p = argparse.ArgumentParser(prog="model_bench",
                                description="Confronto oggettivo fra modelli locali (esiti verificabili)")
    p.add_argument("--models", default=",".join(DEFAULT_MODELS),
                   help="modelli separati da virgola (default: i quattro locali)")
    p.add_argument("--node", default="", help="pinna ogni modello con ::<nodo> (stesso backend)")
    p.add_argument("--cp", default=CP_DEFAULT, help=f"control-plane (default {CP_DEFAULT})")
    p.add_argument("--think", default=None, choices=["true", "false"],
                   help="flag JSON think esplicito: None lascia decidere al CP")
    p.add_argument("--category", default=None, choices=list(CATEGORIE_SONDE.keys()),
                   help="esegui solo le sonde di una categoria specifica")
    p.add_argument("--export-profile", default="",
                   help="percorso file JSON in cui esportare la capability matrix calcolata")
    p.add_argument("--json", action="store_true", help="stampa il risultato come JSON")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    modelli = [f"{m}::{args.node}" if args.node and "::" not in m else m
               for m in args.models.split(",") if m.strip()]
    think = None if args.think is None else (args.think == "true")
    categorie = [args.category] if args.category else None

    def progresso(modello, nome, ok, limite, risposta, stats=None):
        segno = "OK" if ok else ("LOOP" if limite == "loop" else ("LENTO" if limite == "lento" else "NO"))
        spd = f" ({stats.get('tok_s', 0)} t/s)" if stats and stats.get("tok_s") else ""
        print(f"  {modello} {nome:<22} {segno}{spd}  {risposta[:65].replace(chr(10), ' ')}", flush=True)

    sonde = sonde_attive(categorie)
    print(f"== model_bench: {len(modelli)} modelli, {len(sonde)} sonde ==", flush=True)
    risultati = esegui(modelli, cp=args.cp, think=think, progresso=progresso, categorie=categorie)
    riep = riepilogo(risultati)

    if args.export_profile:
        try:
            with open(args.export_profile, "w", encoding="utf-8") as f:
                json.dump({"riepilogo": riep, "risultati": risultati}, f, ensure_ascii=False, indent=2)
            print(f"Capability profile salvato in: {args.export_profile}")
        except Exception as e:
            print(f"Errore salvataggio profilo {args.export_profile}: {e}", file=sys.stderr)

    if args.json:
        print(json.dumps({"risultati": risultati, "riepilogo": riep},
                         ensure_ascii=False, indent=2))
        return 0

    print()
    print(tabella(risultati))
    print()
    for modello, r in riep.items():
        extra = f"  loop={r['loop']} lenti={r['lenti']}" if (r["loop"] or r["lenti"]) else ""
        roles = ",".join(r["profilo"]["recommended_roles"])
        print(f"  {modello:<42} {r['corrette']}/{r['su']}{extra}  -> [{roles}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
