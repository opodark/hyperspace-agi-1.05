#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Superficie locale per REA: dare un eseguibile o una libreria da analizzare.

Perche' esiste. REA (`rea-agents`, MIT) legge binari nativi, applicazioni
JavaScript/Electron, assembly .NET e contenitori; il 5 ottobre 2026 e' stato
provato a mano su una fixture e il risultato sta in `docs/rea-pilot.md`. Da
allora il flusso e' quello: un comando da terminale, un file da copiare nella
fixture, il JSON nella directory temporanea, e il verdetto da leggere a occhio.
Questa superficie toglie di mezzo il copia-incolla: si trascina un file, si
sceglie l'operazione, si legge il report.

Cosa NON e'. Non e' un'integrazione di REA nel runtime: niente container, niente
porte nello stack, niente `rea setup`, nessuna registrazione MCP, nessuna skill
installata. E' un utensile da banco: sta su loopback, lavora su una copia del
target e lascia il repository intatto.

Le regole che questa superficie si impone, perche' qui un programma di terze
parti legge file scelti dall'operatore:

- **solo `127.0.0.1`**, come le altre superfici di sviluppo: nessuna
  esposizione, nessun host diverso da loopback di default;
- **whitelist di operazioni**: l'unico argv che parte e' quello costruito da
  `OPERAZIONI`. Niente shell, niente flag liberi. `setup`, `update` e
  `uninstall` **non sono esposti** — cambiano la configurazione degli agenti e
  possono proporre l'installazione di Hopper — e nemmeno
  `import-reference-source`, che legge alberi di sorgenti arbitrari;
- **nessuna esecuzione del target**: niente `capture-process`, niente browser o
  Electron via CDP, niente riconciliazione runtime. Restano le operazioni
  statiche, che e' la decisione presa in `docs/rea-pilot.md`;
- **il provider lo sceglie l'operatore**: le operazioni native partono solo con
  `--provider` esplicito, perche' l'auto-selezione di REA puo' avviare Hopper da
  sola (su macOS: finestra e licenza). Quel percorso non e' mai stato provato;
- **il target e' sempre la copia nella workspace** del job
  (`data/rea/jobs/<id>/target/`): nessun percorso scelto dal client arriva a
  REA. L'unico testo libero (nome di funzione, indirizzo, testo di ricerca) e'
  validato e passato come argv separato, mai concatenato;
- **timeout e tetto di byte**: il processo parte in un gruppo suo e viene
  terminato al timeout; stdout e stderr hanno un limite di raccolta.

Il report non promuove niente a vulnerabilita'. Tre corsie: **osservato**
(quello che misuriamo noi: byte, sha256, codice di uscita, durata), **riferito da
REA** (riduzione del documento: chiavi, conteggi, digest, envelope d'errore) e
**limiti** (cosa questa lettura non prova). Il documento grezzo resta
l'artefatto scaricabile: la riduzione non lo interpreta al posto dell'operatore.

REA non e' installato su questa macchina e la superficie **non lo installa**: se
manca, la pagina stampa i comandi (npm globale, `npx -y rea-agents@latest`, o la
prova isolata in `/private/tmp/rea-pilot`) e si ferma li'.

Uso:
    .venv/bin/python scripts/rea_surface.py --check
    .venv/bin/python scripts/rea_surface.py            # http://127.0.0.1:7872
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue

from flask import Flask, Response, jsonify, request, send_file

ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
PORT = int(os.getenv("REA_SURFACE_PORT", "7872"))

# La workspace e' usa-e-getta e vive sotto `data/`, che e' fuori da git: qui
# finiscono il file caricato, il documento grezzo di REA e il report ridotto.
WORKSPACE = Path(os.getenv("REA_SURFACE_WORKSPACE", str(ROOT / "data" / "rea")))
JOBS_DIR = WORKSPACE / "jobs"

# La prova del 5 ottobre 2026 installo' REA qui, con `--ignore-scripts`, senza
# toccare il PATH: se l'operatore non l'ha reso globale lo si trova ancora la'.
PILOT_BIN = Path("/private/tmp/rea-pilot/node_modules/.bin/rea")

MAX_UPLOAD_BYTES = int(os.getenv("REA_SURFACE_MAX_UPLOAD_MB", "256")) * 1024 * 1024
MAX_OUTPUT_BYTES = int(os.getenv("REA_SURFACE_MAX_OUTPUT_MB", "64")) * 1024 * 1024
MAX_WORKSPACE_BYTES = int(os.getenv("REA_SURFACE_MAX_WORKSPACE_MB", "2048")) * 1024 * 1024
TIMEOUT_S = int(os.getenv("REA_SURFACE_TIMEOUT_S", "900"))
VERSION_TIMEOUT_S = 10
MAX_IN_CODA = 20
MAX_LAVORI_ELENCO = 50
BYTE_AL_COLPO = 65536

_JOB_ID = re.compile(r"^[0-9a-f]{12}$")
_ADDR = re.compile(r"^0x[0-9a-fA-F]{1,16}$")
_NOME_FUNZIONE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_.$@:<>~-]{0,127}$")
_KEY_DIGEST = re.compile(
    r"(sha256|sha1|sha512|md5|digest|hash|checksum|evidence|artifact_id|commit)", re.I)

PROVIDER = ("hopper", "ghidra", "ida")
ARTEFATTI = ("report.json", "job.json", "stdout.json", "stderr.log")

COMANDI_INSTALLAZIONE = (
    ("globale", "npm install --global rea-agents",
     "mette `rea` nel PATH; richiede Node 22.19+ / 24.11+ / 26"),
    ("una tantum", "npx -y rea-agents@latest analyze <target> --json",
     "nessuna installazione: REA gira una volta sola"),
    ("prova isolata", "npm install --prefix /private/tmp/rea-pilot rea-agents --ignore-scripts",
     "come la prova del 5 ottobre 2026: nessuno script di setup, REA resta in /private/tmp"),
)

CATEGORIE_ERRORE = {
    "invalid_input": "REA ha rifiutato l'input: percorso, formato o argomento",
    "unsupported_provider": "il provider scelto non supporta questo tipo di target",
    "unsupported_target": "REA non sa analizzare questo artefatto",
    "integrity_mismatch": "un digest non torna: il contenitore dichiara valori diversi da quelli trovati",
    "truncated": "un limite di REA ha troncato il risultato",
    "cancelled": "operazione annullata",
    "timeout": "REA ha superato il tempo massimo",
    "resource_constraint": "limite di risorse raggiunto: copertura parziale",
    "unavailable": "una risorsa necessaria non c'e' (per esempio il provider non installato)",
    "execution_failure": "errore di esecuzione di REA",
}

LIMITI_FISSI = (
    "Nessuna vulnerabilità è confermata qui. REA produce osservazioni e inferenze "
    "statiche: i suoi *finding* sono elementi strutturali, non difetti dimostrati.",
    "Il target non è stato eseguito. Questa superficie non usa capture-process, "
    "browser/Electron via CDP né riconciliazione runtime.",
    "Le etichette del provider possono non descrivere il runtime reale: nella prova "
    "del 5 ottobre `src/index.js` risultò `electron-main` su una web app "
    "(docs/rea-pilot.md).",
    "Copertura e omissioni stanno nel documento REA (coverage, omitted_count): qui "
    "non sono riassunte, per non dire più di quanto il documento dica.",
    "L'analisi nativa richiede un provider già installato e configurato: `rea doctor` "
    "è il comando che lo dichiara, e nessun setup parte da questa pagina.",
    "Il documento grezzo è l'artefatto: questa riduzione sceglie cosa mostrare, non "
    "interpreta il risultato al posto dell'operatore.",
)

# ── La tabella delle operazioni ──────────────────────────────────────────────
# Ogni voce e' cio' che puo' partire. `esecuzione` distingue le operazioni
# statiche (REA legge e basta) da quelle che aprono un motore nativo: su queste
# ultime l'avviso in pagina dice che Hopper/Ghidra vengono avviati se non lo
# sono gia', con i permessi dell'utente.
#   argomento_tipo: None | "nome" | "indirizzo" | "testo"
#   provider: "non-serve" | "opzionale" | "obbligatorio"


@dataclass(frozen=True)
class Operazione:
    id: str
    comando: str
    titolo: str
    target: str          # "file" | "nessuno"
    argomento: str | None
    argomento_tipo: str | None
    provider: str
    esecuzione: str      # "statica" | "motore"
    descrizione: str

    def as_dict(self) -> dict:
        return asdict(self)


OPERAZIONI: tuple[Operazione, ...] = (
    Operazione(
        id="doctor", comando="doctor", titolo="Readiness (doctor)",
        target="nessuno", argomento=None, argomento_tipo=None,
        provider="opzionale", esecuzione="statica",
        descrizione="Cosa REA trova su questa macchina: runtime, parser, provider. "
                    "Di sola lettura, non installa nulla."),
    Operazione(
        id="providers", comando="providers", titolo="Provider disponibili",
        target="nessuno", argomento=None, argomento_tipo=None,
        provider="non-serve", esecuzione="statica",
        descrizione="Quali motori nativi (Hopper, Ghidra, IDA) REA vede e quali "
                    "operazioni dichiarano di supportare."),
    Operazione(
        id="capabilities", comando="capabilities", titolo="Capacità",
        target="nessuno", argomento=None, argomento_tipo=None,
        provider="non-serve", esecuzione="statica",
        descrizione="Le capacità ausiliarie disponibili (analisi JavaScript, "
                    "contenitori, catture) senza aprire un target."),
    Operazione(
        id="analyze", comando="analyze", titolo="Panoramica del target",
        target="file", argomento=None, argomento_tipo=None,
        provider="opzionale", esecuzione="motore",
        descrizione="Il giro largo: su directory e .asar è l'analisi statica "
                    "JavaScript, su un binario chiede un provider nativo."),
    Operazione(
        id="inspect", comando="inspect", titolo="Ispezione del target",
        target="file", argomento=None, argomento_tipo=None,
        provider="opzionale", esecuzione="motore",
        descrizione="Come `analyze`, condivide il flusso di panoramica nativa."),
    Operazione(
        id="analyze-js", comando="analyze-javascript-application",
        titolo="Applicazione JavaScript",
        target="file", argomento=None, argomento_tipo=None,
        provider="non-serve", esecuzione="statica",
        descrizione="Grafo dell'applicazione e moduli, senza eseguire il codice. "
                    "Vuole una directory estratta o un .asar."),
    Operazione(
        id="inspect-artifact", comando="inspect-artifact", titolo="Contenitore / artefatto",
        target="file", argomento=None, argomento_tipo=None,
        provider="non-serve", esecuzione="statica",
        descrizione="Inventario del contenitore (es. .asar): voci, digest, "
                    "integrità dichiarata contro quella calcolata."),
    Operazione(
        id="function", comando="function", titolo="Dossier di una funzione",
        target="file", argomento="nome della funzione", argomento_tipo="nome",
        provider="obbligatorio", esecuzione="motore",
        descrizione="Pseudocodice, chiamanti e riferimenti di una funzione."),
    Operazione(
        id="decompile", comando="decompile", titolo="Decompila un indirizzo",
        target="file", argomento="indirizzo (0x...)", argomento_tipo="indirizzo",
        provider="obbligatorio", esecuzione="motore",
        descrizione="Pseudocodice della funzione che sta a quell'indirizzo."),
    Operazione(
        id="xrefs", comando="xrefs", titolo="Riferimenti a un indirizzo",
        target="file", argomento="indirizzo (0x...)", argomento_tipo="indirizzo",
        provider="obbligatorio", esecuzione="motore",
        descrizione="Chi referenzia quell'indirizzo, in entrata e in uscita."),
    Operazione(
        id="instructions", comando="instructions", titolo="Istruzioni di un indirizzo",
        target="file", argomento="indirizzo (0x...)", argomento_tipo="indirizzo",
        provider="obbligatorio", esecuzione="motore",
        descrizione="Solo assembly, senza pseudocodice."),
    Operazione(
        id="search", comando="search", titolo="Cerca testo nel target",
        target="file", argomento="testo da cercare", argomento_tipo="testo",
        provider="obbligatorio", esecuzione="motore",
        descrizione="Stringhe, simboli e riferimenti che contengono il testo dato."),
    Operazione(
        id="trace", comando="trace", titolo="Percorso verso un testo",
        target="file", argomento="testo da cercare", argomento_tipo="testo",
        provider="obbligatorio", esecuzione="motore",
        descrizione="Il percorso che collega l'obiettivo al resto del programma."),
)

_OPS: dict[str, Operazione] = {op.id: op for op in OPERAZIONI}

# ── Com'e' fatto un comando ──────────────────────────────────────────────────

def valida_argomento(op: Operazione, grezzo: str | None) -> tuple[str | None, str | None]:
    """Il testo libero, validato per tipo. Ritorna (valore, errore)."""
    testo = (grezzo or "").strip()
    if op.argomento_tipo is None:
        if testo:
            return None, f"l'operazione {op.id} non accetta un argomento"
        return None, None
    if not testo:
        return None, f"serve {op.argomento}"
    if len(testo) > 200 or any(carattere < " " for carattere in testo):
        return None, "l'argomento deve stare in una riga sola, al massimo 200 caratteri"
    if testo.startswith("-"):
        return None, "l'argomento non puo' iniziare con '-' (sarebbe un flag)"
    if op.argomento_tipo == "indirizzo" and not _ADDR.match(testo):
        return None, "serve un indirizzo esadecimale, per esempio 0x1000"
    if op.argomento_tipo == "nome" and not _NOME_FUNZIONE.match(testo):
        return None, ("il nome della funzione puo' contenere lettere, cifre e "
                      "_ . $ @ : < > ~ -")
    return testo, None


def valida_provider(op: Operazione, grezzo: str | None) -> tuple[str | None, str | None]:
    """Il provider, se l'operazione lo accetta. Ritorna (valore, errore)."""
    scelto = (grezzo or "").strip().lower()
    if not scelto:
        if op.provider == "obbligatorio":
            return None, ("scegli un provider: l'auto-selezione di REA puo' avviare "
                          "Hopper da sola, e questa superficie non lo fa senza che "
                          "tu lo dica")
        return None, None
    if op.provider == "non-serve":
        return None, f"l'operazione {op.id} non usa un provider nativo"
    if scelto not in PROVIDER:
        return None, "provider sconosciuto: " + " | ".join(PROVIDER)
    return scelto, None


def build_argv(binario: str, op: Operazione, target: Path | None,
               argomento: str | None, provider: str | None) -> list[str]:
    """La riga di comando, come lista: nessuna shell, nessuna interpolazione."""
    argv = [binario, op.comando]
    if target is not None:
        argv.append(str(target))
    if argomento:
        argv.append(argomento)
    if provider:
        argv += ["--provider", provider]
    argv.append("--json")
    return argv


# ── Dove sta REA ─────────────────────────────────────────────────────────────

def rea_binary(env: dict | None = None, pilot: Path = PILOT_BIN) -> dict:
    """Dove sta `rea`: REA_BIN, poi il PATH, poi la prova del 5 ottobre.

    Qui si guarda e basta: questa funzione non installa e non avvia niente.
    """
    ambiente = os.environ if env is None else env
    esplicito = (ambiente.get("REA_BIN") or "").strip()
    if esplicito:
        percorso = Path(esplicito).expanduser()
        if percorso.is_file() and os.access(percorso, os.X_OK):
            return {"found": True, "path": str(percorso), "source": "REA_BIN"}
        return {"found": False, "path": None, "source": "REA_BIN",
                "error": f"REA_BIN={esplicito} non e' un eseguibile"}
    for pezzo in (ambiente.get("PATH") or "").split(os.pathsep):
        if not pezzo:
            continue
        candidato = Path(pezzo) / "rea"
        if candidato.is_file() and os.access(candidato, os.X_OK):
            return {"found": True, "path": str(candidato), "source": "PATH"}
    if pilot.is_file() and os.access(pilot, os.X_OK):
        return {"found": True, "path": str(pilot), "source": "prova-2026-10-05"}
    return {"found": False, "path": None, "source": None,
            "error": "`rea` non e' nel PATH e REA_BIN non e' impostato"}


_VERSIONE: dict[str, tuple[float, dict]] = {}
_VERSIONE_LOCK = threading.Lock()


def rea_version(binario: str, ttl: int = 60) -> dict:
    """`rea --version`, con cache: /api/status non lancia un processo a ogni giro."""
    adesso = time.monotonic()
    with _VERSIONE_LOCK:
        salvato = _VERSIONE.get(binario)
        if salvato and adesso - salvato[0] < ttl:
            return salvato[1]
    try:
        esito = subprocess.run([binario, "--version"], capture_output=True,
                               text=False, timeout=VERSION_TIMEOUT_S)
        testo = (esito.stdout or b"").decode("utf-8", "replace").strip()
        errore = None if esito.returncode == 0 else f"--version ha risposto {esito.returncode}"
    except (OSError, subprocess.SubprocessError) as exc:
        testo, errore = "", f"{type(exc).__name__}: {exc}"
    valore = {"testo": testo[:200], "errore": errore}
    with _VERSIONE_LOCK:
        _VERSIONE[binario] = (adesso, valore)
    return valore

# ── La workspace e i suoi job ────────────────────────────────────────────────

def ora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scarica_json(percorso: Path) -> dict | None:
    try:
        return json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def scrivi_json(percorso: Path, dato: dict) -> None:
    """Scrittura atomica: il worker e le rotte leggono lo stesso file."""
    temporaneo = percorso.with_name(percorso.name + ".tmp")
    temporaneo.write_text(json.dumps(dato, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporaneo, percorso)


def sanifica_nome(grezzo: str) -> str:
    """Il nome del file caricato, ridotto a una foglia innocua."""
    base = Path((grezzo or "").replace("\\", "/")).name.strip()
    base = re.sub(r"[^A-Za-z0-9._+-]", "_", base).lstrip(".")
    return (base or "target")[:120]


def job_dir(jobs_dir: Path, job_id: str) -> Path | None:
    """La cartella di un job, solo se l'id ha la forma che diamo noi."""
    if not _JOB_ID.match(job_id or ""):
        return None
    return jobs_dir / job_id


def riassunto(record: dict) -> dict:
    """Quel tanto di job che basta all'elenco in pagina."""
    return {chiave: record.get(chiave) for chiave in
            ("id", "op", "titolo", "status", "esito", "created_at", "started_at",
             "finished_at", "exit_code", "duration_s", "target", "provider", "argomento")}


def elenca_lavori(jobs_dir: Path, limite: int = MAX_LAVORI_ELENCO) -> list[dict]:
    if not jobs_dir.is_dir():
        return []
    voci = []
    for figlio in jobs_dir.iterdir():
        if not figlio.is_dir() or not _JOB_ID.match(figlio.name):
            continue
        record = scarica_json(figlio / "job.json")
        if record:
            voci.append(riassunto(record))
    voci.sort(key=lambda voce: voce.get("created_at") or "", reverse=True)
    return voci[:limite]


def peso_workspace(jobs_dir: Path) -> int:
    totale = 0
    if not jobs_dir.is_dir():
        return 0
    for percorso in jobs_dir.rglob("*"):
        try:
            if percorso.is_file():
                totale += percorso.stat().st_size
        except OSError:
            continue
    return totale


def sha256_file(percorso: Path) -> str:
    """Il digest del file caricato: lo misuriamo noi, non lo prendiamo da REA."""
    digest = hashlib.sha256()
    with percorso.open("rb") as manico:
        while True:
            blocco = manico.read(1024 * 1024)
            if not blocco:
                break
            digest.update(blocco)
    return digest.hexdigest()

# ── La riduzione del documento ───────────────────────────────────────────────
# Niente di quello che segue promuove un campo a conclusione: si prende il
# documento di REA, se ne dichiara la forma, si tirano fuori i digest e si
# riporta l'eventuale envelope d'errore. Il resto si legge in `stdout.json`.

def _forma(documento) -> list[dict]:
    """I campi di primo livello, con il tipo e la dimensione."""
    if not isinstance(documento, dict):
        return [{"chiave": "documento", "tipo": type(documento).__name__, "n": None}]
    fuori = []
    for chiave in sorted(documento)[:40]:
        valore = documento[chiave]
        if isinstance(valore, dict):
            fuori.append({"chiave": chiave, "tipo": "oggetto", "n": len(valore)})
        elif isinstance(valore, list):
            fuori.append({"chiave": chiave, "tipo": "elenco", "n": len(valore)})
        elif valore is None:
            fuori.append({"chiave": chiave, "tipo": "nullo", "n": None})
        else:
            fuori.append({"chiave": chiave, "tipo": type(valore).__name__, "n": None})
    return fuori


def _collezioni(documento, percorso: str = "", profondita: int = 0) -> list[dict]:
    """Gli elenchi di oggetti: sono le collezioni semantiche del documento."""
    if profondita > 6:
        return []
    fuori: list[dict] = []
    if isinstance(documento, dict):
        for chiave in sorted(documento):
            figlio = documento[chiave]
            cammino = f"{percorso}.{chiave}" if percorso else chiave
            if isinstance(figlio, list) and figlio and isinstance(figlio[0], dict):
                fuori.append({"per": cammino, "n": len(figlio)})
            elif isinstance(figlio, (dict, list)):
                fuori += _collezioni(figlio, cammino, profondita + 1)
    elif isinstance(documento, list):
        for indice, figlio in enumerate(documento[:5]):
            if isinstance(figlio, (dict, list)):
                fuori += _collezioni(figlio, f"{percorso}[{indice}]", profondita + 1)
    return fuori[:40]


def _digest_riferiti(documento, fuori: list | None = None, percorso: str = "",
                     profondita: int = 0, limite: int = 20) -> list[dict]:
    """I valori che sembrano un digest o un identificatore, con la provenienza."""
    if fuori is None:
        fuori = []
    if profondita > 6 or len(fuori) >= limite:
        return fuori
    if isinstance(documento, dict):
        for chiave in sorted(documento):
            figlio = documento[chiave]
            cammino = f"{percorso}.{chiave}" if percorso else chiave
            if isinstance(figlio, (dict, list)):
                _digest_riferiti(figlio, fuori, cammino, profondita + 1, limite)
            elif figlio is not None and not isinstance(figlio, bool) \
                    and _KEY_DIGEST.search(chiave):
                fuori.append({"per": cammino, "valore": str(figlio)[:120]})
    elif isinstance(documento, list):
        for indice, figlio in enumerate(documento[:5]):
            _digest_riferiti(figlio, fuori, f"{percorso}[{indice}]", profondita + 1, limite)
    return sorted(fuori, key=lambda voce: voce["per"])[:limite]


def _progresso(testo: str, limite: int = 200) -> list[dict]:
    """Le righe `rea_progress` che REA scrive su stderr mentre lavora.

    REA 6.1.0 le annida: `{"rea_progress": {phase, message, completed, total,
    sequence}}`, una riga JSON per passo. Le forme piatte restano accettate
    perche' non tutti i comandi le annidano allo stesso modo.
    """
    fuori = []
    for riga in (testo or "").splitlines():
        riga = riga.strip()
        if not riga.startswith("{") or "rea_progress" not in riga:
            continue
        try:
            dato = json.loads(riga)
        except ValueError:
            continue
        if not isinstance(dato, dict):
            continue
        dentro = dato.get("rea_progress")
        if isinstance(dentro, dict):
            dato = dentro
        fase = (dato.get("phase") or dato.get("step") or dato.get("event")
                or dato.get("kind"))
        messaggio = dato.get("message") or dato.get("detail") or ""
        fuori.append({
            "fase": str(fase)[:80] if fase else "?",
            "messaggio": str(messaggio)[:300],
            "file": str(dato.get("file") or dato.get("source_file") or "")[:200],
        })
        if len(fuori) >= limite:
            break
    return fuori


def _oggetti_json(testo: str, limite: int = 500) -> list:
    """Gli oggetti JSON di un testo: tutto il testo, poi riga per riga."""
    candidati = []
    testo = (testo or "").strip()
    if testo:
        try:
            candidati.append(json.loads(testo))
        except ValueError:
            pass
    for numero, riga in enumerate(testo.splitlines()):
        if numero >= limite:
            break
        riga = riga.strip()
        if not riga.startswith("{"):
            continue
        try:
            candidati.append(json.loads(riga))
        except ValueError:
            continue
    return candidati


def _envelope_errore(stdout_testo: str, stderr_testo: str) -> dict | None:
    """L'errore tipizzato di REA: `code`, `category`, `message`, `remediation`."""
    for testo in (stdout_testo, stderr_testo):
        for candidato in _oggetti_json(testo):
            if not isinstance(candidato, dict):
                continue
            if "code" not in candidato or "category" not in candidato:
                continue
            rimedio = candidato.get("remediation")
            azione = rimedio.get("action") if isinstance(rimedio, dict) else None
            categoria = str(candidato.get("category"))
            return {
                "code": str(candidato.get("code")),
                "category": categoria,
                "message": str(candidato.get("message") or "")[:400],
                "retryable": bool(candidato.get("retryable")),
                "remediation": str(azione)[:300] if azione else None,
                "spiegazione": CATEGORIE_ERRORE.get(categoria, "categoria non documentata"),
            }
    return None

def riduci(stdout: bytes, stderr: bytes, exit_code: int | None, durata_s: float,
           comando: list[str], target: dict | None,
           troncato: dict | None = None) -> dict:
    """Le tre corsie: quello che abbiamo misurato, quello che REA riferisce, i limiti."""
    testo_stdout = stdout.decode("utf-8", "replace")
    testo_stderr = stderr.decode("utf-8", "replace")
    try:
        documento = json.loads(testo_stdout)
        json_valido = True
    except ValueError:
        documento, json_valido = None, False
    if exit_code is None:
        esito = "timeout"
    elif exit_code == 0:
        esito = "completato"
    elif exit_code > 128:
        esito = f"segnale {exit_code - 128}"
    else:
        esito = "non completato"
    errore = _envelope_errore(testo_stdout, testo_stderr)
    if not json_valido:
        nota = ("REA non ha stampato JSON su stdout: la riduzione si ferma qui, "
                "il testo grezzo sta in stderr.log.")
    elif exit_code not in (0, None) and errore is None:
        nota = (f"Il documento c'e' e si legge, ma REA e' uscito con codice "
                f"{exit_code} senza un envelope d'errore: l'esito sta nel "
                "documento stesso (per esempio `doctor` risponde `healthy: "
                "false` quando manca il motore di analisi).")
    else:
        nota = "Documento JSON letto e ridotto."
    verdetto = None
    if json_valido and isinstance(documento, dict) \
            and isinstance(documento.get("healthy"), bool):
        salute = documento.get("environment_healthy")
        verdetto = {
            "healthy": documento["healthy"],
            "environment_healthy": salute if isinstance(salute, bool) else None,
        }
    riferito = {
        "json_valido": json_valido,
        "chiavi": _forma(documento) if json_valido else [],
        "collezioni": _collezioni(documento) if json_valido else [],
        "digest": _digest_riferiti(documento) if json_valido else [],
        "verdetto": verdetto,
        "nota": nota,
    }
    return {
        "osservato": {
            "esito": esito,
            "exit_code": exit_code,
            "durata_s": round(durata_s, 2),
            "stdout_bytes": len(stdout),
            "stderr_bytes": len(stderr),
            "troncato": troncato or {"stdout": False, "stderr": False},
            "comando": list(comando),
            "target": target,
        },
        "riferito": riferito,
        "errore": errore,
        "progresso": _progresso(testo_stderr),
        "limiti": list(LIMITI_FISSI),
    }

# ── Il runner: un job alla volta, in una copia del target ────────────────────

class Runner:
    """Esegue `rea` sui job in coda, uno per volta.

    Una coda sola perche' due analisi native in parallelo vorrebbero dire due
    motori aperti insieme su questa macchina, e perche' un errore si spiega
    meglio se c'e' un ordine. Ogni processo parte nel suo gruppo
    (`start_new_session`), cosi' al timeout si termina anche quello che ha
    aperto: nessun `rea` orfano resta vivo dopo la scadenza.
    """

    def __init__(self, binario: str, jobs_dir: Path, timeout: int = TIMEOUT_S,
                 env: dict | None = None, massimo_output: int = MAX_OUTPUT_BYTES):
        self.binario = binario
        self.jobs_dir = jobs_dir
        self.timeout = timeout
        self.env = dict(os.environ) if env is None else env
        self.massimo_output = massimo_output
        self.coda: Queue = Queue()
        self.in_coda = 0
        self._in_coda_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._fermo = threading.Event()

    # — ciclo di vita —
    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="rea-runner", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._fermo.set()
        self.coda.put(None)
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _loop(self) -> None:
        while not self._fermo.is_set():
            try:
                job_id = self.coda.get(timeout=0.5)
            except Empty:
                continue
            if job_id is None:
                break
            with self._in_coda_lock:
                self.in_coda = max(0, self.in_coda - 1)
            try:
                self._esegui(job_id)
            except Exception as exc:  # un job rotto non deve fermare la coda
                self._segna_errore(job_id, f"{type(exc).__name__}: {exc}")

    # — la coda —
    def accoda(self, record: dict) -> None:
        with self._in_coda_lock:
            self.in_coda += 1
        self.coda.put(record["id"])

    def posti_liberi(self) -> bool:
        with self._in_coda_lock:
            return self.in_coda < MAX_IN_CODA

    # — l'esecuzione —
    def _esegui(self, job_id: str) -> None:
        cartella = self.jobs_dir / job_id
        record = scarica_json(cartella / "job.json")
        if not record:
            return
        record["status"] = "running"
        record["started_at"] = ora()
        scrivi_json(cartella / "job.json", record)
        comando = list(record.get("comando") or [])
        inizio = time.monotonic()
        raccolta = {"stdout": bytearray(), "stderr": bytearray()}
        troncato = {"stdout": False, "stderr": False}
        try:
            processo = subprocess.Popen(
                comando, cwd=str(cartella), env=self.env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        except OSError as exc:
            raccolta["stderr"] = bytearray(str(exc).encode("utf-8"))
            self._chiudi(record, cartella, None, 0.0, raccolta, troncato, "non avviato")
            return
        fili = [
            threading.Thread(target=_leggi, args=(
                processo.stdout, raccolta["stdout"], troncato, "stdout", self.massimo_output),
                daemon=True),
            threading.Thread(target=_leggi, args=(
                processo.stderr, raccolta["stderr"], troncato, "stderr", self.massimo_output),
                daemon=True),
        ]
        for filo in fili:
            filo.start()
        scaduto = False
        try:
            exit_code = processo.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            scaduto, exit_code = True, None
            _termina_gruppo(processo)
        for filo in fili:
            filo.join(timeout=5)  # i lettori finiscono sull'EOF, non sul processo
        self._chiudi(record, cartella, exit_code, time.monotonic() - inizio,
                     raccolta, troncato, "timeout" if scaduto else None)

    def _chiudi(self, record: dict, cartella: Path, exit_code: int | None,
                durata_s: float, raccolta: dict, troncato: dict,
                esito_esterno: str | None) -> None:
        report = riduci(bytes(raccolta["stdout"]), bytes(raccolta["stderr"]),
                        exit_code, durata_s, list(record.get("comando") or []),
                        record.get("target"), troncato)
        if esito_esterno:
            report["osservato"]["esito"] = esito_esterno
        (cartella / "stdout.json").write_bytes(bytes(raccolta["stdout"]))
        (cartella / "stderr.log").write_bytes(bytes(raccolta["stderr"]))
        scrivi_json(cartella / "report.json", report)
        record["esito"] = report["osservato"]["esito"]
        record["status"] = "completed" if record["esito"] == "completato" else "failed"
        record["exit_code"] = exit_code
        record["duration_s"] = report["osservato"]["durata_s"]
        record["finished_at"] = ora()
        scrivi_json(cartella / "job.json", record)

    def _segna_errore(self, job_id: str, messaggio: str) -> None:
        cartella = self.jobs_dir / job_id
        record = scarica_json(cartella / "job.json") or {"id": job_id}
        record["status"] = "failed"
        record["esito"] = "errore del runner"
        record["finished_at"] = ora()
        try:
            (cartella / "stderr.log").write_text(messaggio + "\n", encoding="utf-8")
            scrivi_json(cartella / "job.json", record)
        except OSError:
            return

def _leggi(flusso, accumulatore: bytearray, troncato: dict, quale: str,
           massimo: int) -> None:
    """Legge un tubo fino in fondo, ma raccoglie solo i primi `massimo` byte."""
    if flusso is None:
        return
    try:
        while True:
            blocco = flusso.read(BYTE_AL_COLPO)
            if not blocco:
                break
            spazio = massimo - len(accumulatore)
            if spazio > 0:
                accumulatore.extend(blocco[:spazio])
            if len(blocco) > spazio:
                troncato[quale] = True
    except (OSError, ValueError):
        return
    finally:
        try:
            flusso.close()
        except OSError:
            pass


def _termina_gruppo(processo) -> None:
    """SIGTERM al gruppo, poi SIGKILL: niente `rea` orfano dopo il timeout.

    I motori nativi aprono processi propri (Hopper, Ghidra): terminarli dal
    gruppo e' l'unico modo di non lasciarne uno vivo a consumare la macchina.
    """
    try:
        gruppo = os.getpgid(processo.pid)
    except OSError:
        gruppo = None
    for segnale in (signal.SIGTERM, signal.SIGKILL):
        if processo.poll() is not None:
            return
        try:
            if gruppo is not None:
                os.killpg(gruppo, segnale)
            else:
                processo.kill()
        except OSError:
            return
        try:
            processo.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            continue

# ── La pagina ────────────────────────────────────────────────────────────────
# Una pagina sola, senza build, senza CDN: parla solo con le rotte qui sopra.
# Tre colonne: a sinistra cosa si da' da analizzare, in mezzo l'elenco dei
# lavori, a destra il report del lavoro scelto.
_PAGE = r"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Analisi artefatti — REA</title>
<style>
:root{--bg:#0f0f1a;--surface:#171727;--surface2:#1e1e33;--border:#2a2a44;
--text:#e6e6f0;--muted:#9a9ab5;--faint:#6c6c88;--primary:#7c6cff;--ok:#3ecf8e;
--warn:#f5a623;--err:#ff5c5c;--evid:#5cc8ff;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;height:100vh;display:flex;flex-direction:column}
header{display:flex;align-items:center;gap:10px;padding:8px 12px;background:var(--surface);border-bottom:1px solid var(--border);flex-wrap:wrap}
.brand{font-weight:600;display:flex;align-items:center;gap:8px}
.tag{font:10px var(--mono);text-transform:uppercase;color:var(--faint);border:1px solid var(--border);border-radius:99px;padding:1px 6px}
select,input,button{background:var(--surface2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:4px 8px;font:12px inherit}
button{cursor:pointer}
button:hover{border-color:var(--primary)}
button.primary{background:var(--primary);border-color:var(--primary);color:#0f0f1a;font-weight:600;padding:6px}
.spacer{flex:1}
.pill{font:10px var(--mono);border:1px solid var(--border);border-radius:99px;padding:2px 8px;color:var(--muted)}
.pill.ok{color:var(--ok);border-color:var(--ok)}
.pill.warn{color:var(--warn);border-color:var(--warn)}
.pill.err{color:var(--err);border-color:var(--err)}
#banner{padding:7px 12px;font-size:12px;border-bottom:1px solid var(--border);background:#221b0f;color:#f0d9a8;display:none}
#banner.ok{background:#0f221a;color:#b8efd4}
#banner code{font-family:var(--mono);background:#00000038;padding:1px 5px;border-radius:4px}
main{flex:1;display:grid;grid-template-columns:330px 1fr 400px;min-height:0}
aside,section{overflow:auto;background:var(--surface);padding:10px}
aside{border-right:1px solid var(--border)}
#detail{border-right:none;border-left:1px solid var(--border)}
#jobs{background:var(--bg)}
.side-title{font:11px var(--mono);text-transform:uppercase;color:var(--faint);margin:2px 0 8px;display:flex;justify-content:space-between}
#form{display:grid;gap:5px;margin-bottom:14px}
#form label{font:10px var(--mono);text-transform:uppercase;color:var(--faint)}
#form input,#form select{width:100%;min-width:0}
.hint,.msg{color:var(--muted);font-size:11px}
.msg{color:var(--warn);min-height:16px}
.op{padding:5px 7px;border:1px solid transparent;border-radius:6px;cursor:pointer;margin-bottom:2px}
.op:hover{background:var(--surface2)}
.op .t{font-size:12px}
.op .d{font-size:10px;color:var(--faint);display:block}
.op .w{font-size:10px;color:var(--warn);display:block}
.job{display:flex;justify-content:space-between;gap:6px;padding:5px 7px;border:1px solid transparent;border-radius:6px;cursor:pointer}
.job:hover{background:var(--surface2)}
.job.sel{border-color:var(--primary);background:var(--surface2)}
.job .nm{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.job .st{font:10px var(--mono);color:var(--faint);white-space:nowrap}
.lane{border:1px solid var(--border);border-radius:8px;padding:8px;margin-bottom:8px;background:var(--surface2)}
.lane.osservato{border-color:#24405c}
.lane.osservato h3{color:var(--evid)}
.lane.limiti{border-color:#5c4a24}
.lane.limiti h3{color:var(--warn)}
.lane h3{margin:0 0 6px;font:10px var(--mono);text-transform:uppercase;color:var(--faint)}
table.mini{width:100%;border-collapse:collapse;font:11px var(--mono)}
table.mini td{padding:2px 4px;border-bottom:1px solid var(--border);word-break:break-all;vertical-align:top}
table.mini td.k{color:var(--muted);white-space:nowrap;width:38%}
ol.timeline{margin:0;padding-left:16px;font:11px var(--mono);color:var(--muted)}
ul.limiti{margin:0;padding-left:16px;font-size:11px;color:var(--muted)}
ul.limiti li{margin-bottom:3px}
.box-err{border:1px solid var(--err);background:#2a1418;border-radius:8px;padding:8px;margin-bottom:8px;font-size:12px}
.box-err .code{font:11px var(--mono);color:var(--err)}
.arts{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.arts a{font:11px var(--mono);border:1px solid var(--border);border-radius:6px;padding:3px 7px;color:var(--text);text-decoration:none}
.arts a:hover{border-color:var(--primary)}
pre.cmd{font:11px var(--mono);background:#0b0b14;border:1px solid var(--border);border-radius:6px;padding:6px;white-space:pre-wrap;word-break:break-all;margin:0 0 8px}
.kv{display:grid;grid-template-columns:96px 1fr;gap:2px 8px;font-size:12px;margin-bottom:8px}
.kv b{font-weight:600;color:var(--muted);font-size:10px;text-transform:uppercase}
.kv span{word-break:break-word}
.mono{font-family:var(--mono);font-size:11px}
.empty{color:var(--faint);padding:12px;font-size:12px}
footer{font:11px var(--mono);color:var(--faint);padding:4px 12px;border-top:1px solid var(--border);background:var(--surface);display:flex;gap:14px;flex-wrap:wrap}
</style>
</head>
<body>
<header>
  <div class="brand">&#128300; Analisi artefatti <span class="tag">rea</span></div>
  <span class="pill" id="pillRea">&hellip;</span>
  <span class="spacer"></span>
  <button id="btnDoctor" title="Cosa REA trova su questa macchina">Readiness</button>
  <button id="btnRefresh">Aggiorna</button>
</header>
<div id="banner"></div>
<main>
  <aside id="side">
    <div class="side-title"><span>Da analizzare</span></div>
    <div id="form">
      <label for="fileInp">File (exe, libreria, .asar, .dll)</label>
      <input type="file" id="fileInp">
      <label for="opSel">Operazione</label>
      <select id="opSel"></select>
      <div class="hint" id="opInfo"></div>
      <label for="argInp" id="argLbl">Argomento</label>
      <input id="argInp">
      <label for="provSel">Provider nativo</label>
      <select id="provSel"></select>
      <div class="msg" id="formMsg"></div>
      <button class="primary" id="btnRun">Analizza</button>
      <div class="hint">Il file viene copiato in <code>data/rea/jobs/</code> e analizzato
      lì: l'originale non si tocca e non viene eseguito.</div>
    </div>
    <div class="side-title"><span>Operazioni esposte</span></div>
    <div id="opsList"></div>
  </aside>
  <section id="jobs">
    <div class="side-title"><span>Lavori</span><span id="jobsCount"></span></div>
    <div id="jobList"><div class="empty">Caricamento&hellip;</div></div>
  </section>
  <aside id="detail"><div class="empty">Scegli un lavoro per leggerne il report.</div></aside>
</main>
<footer>
  <span id="foot">loopback &middot; solo analisi statica &middot; nessun setup automatico</span>
</footer>
<script>
// La pagina: stato di REA, form, elenco lavori, report del lavoro scelto.
var ST=null, OPS=[], JOBS=[], SEL=null, POLL=null;
function el(id){ return document.getElementById(id); }
function escH(v){ return String(v==null?'':v).replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
async function j(url,opzioni){
  var r=await fetch(url,opzioni), d=await r.json().catch(function(){ return {}; });
  if(!r.ok){ var e=new Error(d.error||('HTTP '+r.status)); e.corpo=d; throw e; }
  return d;
}
function lane(classe,titolo,corpo){
  return '<div class="lane '+classe+'"><h3>'+escH(titolo)+'</h3>'+corpo+'</div>';
}
function rigaMini(k,v){ return '<tr><td class="k">'+escH(k)+'</td><td>'+escH(v)+'</td></tr>'; }

// ── avvio ───────────────────────────────────────────────────────────────────
async function boot(){
  try{ ST=await j('/api/status'); }
  catch(e){
    el('pillRea').textContent='superficie non raggiungibile';
    el('jobList').innerHTML='<div class="empty">'+escH(e.message)+'</div>';
    return;
  }
  OPS=(ST.ops||[]);
  popolaOperazioni(); popolaProvider();
  renderStato(); renderOps(); renderForm(); renderPie();
  el('btnRun').onclick=function(){ invia(null); };
  el('btnRefresh').onclick=function(){ caricaLavori(); };
  el('btnDoctor').onclick=function(){ invia('doctor'); };
  el('opSel').onchange=renderForm;
  el('provSel').onchange=renderForm;
  el('fileInp').onchange=renderForm;
  caricaLavori();
}

function renderStato(){
  var rea=(ST&&ST.rea)||{}, pill=el('pillRea'), banner=el('banner');
  if(rea.found){
    var versione=rea.version&&rea.version.testo?rea.version.testo:'trovato';
    pill.textContent='rea '+versione+' · '+rea.source;
    pill.className='pill ok';
    banner.className='ok'; banner.style.display='block';
    banner.innerHTML='Solo analisi statica: il target non viene eseguito e nessun setup '
      +'parte da qui. <code>'+escH(rea.path)+'</code> &middot; un lavoro alla volta '
      +'&middot; timeout '+escH((ST.limits||{}).timeout_s)+' s'
      +(rea.version&&rea.version.errore?' &middot; <b>'+escH(rea.version.errore)+'</b>':'');
    return;
  }
  pill.textContent='rea non trovato'; pill.className='pill warn';
  banner.className=''; banner.style.display='block';
  var comandi=(ST.install||[]).map(function(c){
    var cmd=(c&&(c.comando||c[1]))||'', nota=(c&&(c.nota||c[2]))||'';
    return '<div><code>'+escH(cmd)+'</code> &mdash; '+escH(nota)+'</div>';
  }).join('');
  banner.innerHTML='<b>REA non è installato</b> (o non è nel PATH): questa superficie non lo '
    +'installa da sola e non lancia <code>rea setup</code>. '+escH(rea.error||'')
    +comandi+'<div>Installalo tu, poi premi <b>Readiness</b>: senza <code>rea</code> non '
    +'c\'è niente da analizzare.</div>';
}

function popolaOperazioni(){
  el('opSel').innerHTML=OPS.map(function(op){
    return '<option value="'+escH(op.id)+'">'+escH(op.titolo)+'</option>';
  }).join('');
  if(OPS.length) el('opSel').value=OPS[0].id;
}

function popolaProvider(){
  var voci=['<option value="">- automatico -</option>'];
  ((ST&&ST.providers)||[]).forEach(function(p){
    voci.push('<option value="'+escH(p)+'">'+escH(p)+'</option>');
  });
  el('provSel').innerHTML=voci.join('');
}

function opCorrente(){
  var id=el('opSel').value;
  for(var i=0;i<OPS.length;i++){ if(OPS[i].id===id) return OPS[i]; }
  return OPS.length?OPS[0]:null;
}

function renderOps(){
  el('opsList').innerHTML=OPS.map(function(op,i){
    var avviso=(op.esecuzione==='motore')
      ?'<span class="w">apre un motore nativo: '+(op.provider==='obbligatorio'
        ?'il provider lo scegli tu':'provider facoltativo')+'</span>'
      :'';
    return '<div class="op" data-i="'+i+'" title="'+escH(op.descrizione)+'">'
      +'<span class="t">'+escH(op.titolo)+'</span>'
      +'<span class="d">rea '+escH(op.comando)+' &middot; '
      +(op.target==='nessuno'?'senza file':'con un file')+'</span>'+avviso+'</div>';
  }).join('');
}

// scegliOp esiste anche per chi non puo' cliccare (test): l'elenco resta cliccabile
function scegliOp(indice){
  var op=OPS[indice]; if(!op) return;
  el('opSel').value=op.id;
  renderForm();
}

function renderForm(){
  var op=opCorrente();
  var conFile=!!(op&&op.target==='file');
  var conArgomento=!!(op&&op.argomento);
  el('fileInp').style.display=conFile?'':'none';
  el('fileInp').disabled=!conFile;
  el('argLbl').textContent=conArgomento?op.argomento:'Argomento (non serve)';
  el('argInp').disabled=!conArgomento;
  el('argInp').placeholder=conArgomento?op.argomento:'';
  el('provSel').disabled=!(op&&op.provider!=='non-serve');
  el('btnRun').textContent=op&&op.target==='nessuno'?'Esegui':'Analizza';
  var info=op?escH(op.descrizione):'';
  if(op&&op.esecuzione==='motore'){
    info+='<br><b>Provider:</b> '+(op.provider==='obbligatorio'
      ?'da scegliere (la selezione automatica può avviare Hopper da sola)'
      :'facoltativo, meglio indicarlo');
  }
  if(op&&op.target==='file'&&op.comando==='analyze-javascript-application'){
    info+='<br>Serve un <code>.asar</code> o una directory: qui si caricano file singoli.';
  }
  el('opInfo').innerHTML=info;
  el('formMsg').textContent='';
}

function renderPie(){
  var jobs=(ST&&ST.jobs)||{};
  el('foot').innerHTML='loopback &middot; solo analisi statica &middot; nessun setup automatico '
    +'&middot; workspace <code>'+escH((ST&&ST.workspace)||'')+'</code>'
    +' &middot; lavori '+escH(jobs.n||0)+' ('+escH(jobs.bytes||0)+' B)';
}
// ── mandare un lavoro ───────────────────────────────────────────────────────
function trovaOp(id){
  for(var i=0;i<OPS.length;i++){ if(OPS[i].id===id) return OPS[i]; }
  return null;
}

async function invia(opForzata){
  var op=(typeof opForzata==='string')?trovaOp(opForzata):opCorrente();
  if(!op) return;
  var msg=el('formMsg');
  msg.textContent=''; msg.style.color='';
  var scelti=el('fileInp').files;
  var file=scelti&&scelti[0]?scelti[0]:null;
  if(op.target==='file'&&!file){
    msg.textContent='serve un file da analizzare'; return;
  }
  var provider=(op.provider==='non-serve')?'':(el('provSel').value||'');
  if(op.provider==='obbligatorio'&&!provider){
    msg.textContent="scegli un provider: la selezione automatica può avviare Hopper"; return;
  }
  var argomento=(el('argInp').value||'').trim();
  if(op.argomento&&!argomento){
    msg.textContent='serve: '+op.argomento; return;
  }
  var dati=new FormData();
  dati.append('op',op.id);
  if(provider) dati.append('provider',provider);
  if(argomento) dati.append('argomento',argomento);
  if(file) dati.append('file',file,file.name);
  el('btnRun').disabled=true;
  msg.textContent='Invio…';
  try{
    var creato=await j('/api/jobs',{method:'POST',body:dati});
    msg.textContent='Lavoro in coda: '+creato.job.id;
    await caricaLavori();
    await apri(creato.job.id);
  }catch(e){
    msg.textContent=e.message||'richiesta rifiutata';
  }finally{
    el('btnRun').disabled=false;
  }
}

// ── elenco dei lavori ───────────────────────────────────────────────────────
async function caricaLavori(){
  try{
    var d=await j('/api/jobs');
    JOBS=(d.jobs||[]);
  }catch(e){
    el('jobList').innerHTML='<div class="empty">'+escH(e.message)+'</div>';
    return JOBS;
  }
  renderLavori();
  return JOBS;
}

function statoEtichetta(job){
  if(job.status==='running') return 'in corso';
  if(job.status==='queued') return 'in coda';
  if(job.status==='completed') return (job.durata_s!=null?job.durata_s+' s':'fatto');
  if(job.status==='failed') return job.esito||'fallito';
  return job.status||'?';
}

function renderLavori(){
  el('jobsCount').textContent=String(JOBS.length);
  if(!JOBS.length){
    el('jobList').innerHTML='<div class="empty">Nessun lavoro. Scegli un file e '
      +'un\'operazione a sinistra.</div>';
    return;
  }
  el('jobList').innerHTML=JOBS.map(function(job){
    var nome=(job.target&&job.target.nome)?job.target.nome:'(nessun file)';
    return '<div class="job'+(SEL===job.id?' sel':'')+'" data-id="'+escH(job.id)+'" '
      +'title="'+escH(job.id)+'">'
      +'<span class="nm">'+escH(job.titolo||job.op)+' &middot; '+escH(nome)+'</span>'
      +'<span class="st">'+escH(statoEtichetta(job))+'</span></div>';
  }).join('');
}

function trovaLavoro(id){
  for(var i=0;i<JOBS.length;i++){ if(JOBS[i].id===id) return JOBS[i]; }
  return null;
}

function serve(id){
  var job=trovaLavoro(id);
  return !!job&&(job.status==='running'||job.status==='queued');
}

function avviaPolling(id){
  if(POLL){ clearTimeout(POLL); POLL=null; }
  if(!serve(id)) return;
  POLL=setTimeout(async function(){
    POLL=null;
    await apri(id,true);
  },1200);
}

async function apri(id,soloAggiorna){
  SEL=id;
  if(!soloAggiorna) renderLavori();
  await mostra(id);
  await caricaLavori();
  avviaPolling(id);
}

async function mostra(id){
  try{
    var d=await j('/api/jobs/'+encodeURIComponent(id));
    renderDettaglio(d);
    return d;
  }catch(e){
    el('detail').innerHTML='<div class="empty">'+escH(e.message)+'</div>';
    return null;
  }
}
// ── il report: tre corsie ───────────────────────────────────────────────────
function renderDettaglio(d){
  var job=d.job||{}, rep=d.report||null;
  if(!job.id){ el('detail').innerHTML='<div class="empty">Report non leggibile.</div>'; return; }
  var oss=(rep&&rep.osservato)||null;
  var target=job.target||{};
  var testa='<div class="side-title"><span>'+escH(job.titolo||job.op)+'</span>'
    +'<span class="mono">'+escH(job.id)+'</span></div>';
  var righe=[];
  righe.push(['operazione','rea '+((oss&&oss.comando&&oss.comando.length>1)
    ?oss.comando.slice(1).join(' ') : job.op)]);
  righe.push(['esito',(oss?oss.esito:null)||job.esito||job.status||'—']);
  if(job.exit_code!=null||(oss&&oss.exit_code!=null)){
    var codice=(job.exit_code!=null)?job.exit_code:oss.exit_code;
    righe.push(['codice di uscita',codice]);
  }
  if(job.duration_s!=null||(oss&&oss.durata_s!=null)){
    righe.push(['durata',((job.duration_s!=null)?job.duration_s:oss.durata_s)+' s']);
  }
  righe.push(['target',target.nome||'(nessun file)']);
  if(target.bytes!=null) righe.push(['peso',target.bytes+' B']);
  righe.push(['sha256 del target',target.sha256||'—']);
  righe.push(['provider',job.provider||'automatico']);
  if(job.argomento) righe.push(['argomento',job.argomento]);
  var html=testa
    +'<div class="kv">'+righe.map(function(r){ return '<b>'+escH(r[0])+'</b><span>'
      +escH(r[1])+'</span>'; }).join('')+'</div>';
  if(oss&&oss.comando&&oss.comando.length){
    html+='<pre class="cmd">'+escH(oss.comando.join(' '))+'</pre>';
  }
  html+=boxErrore(rep&&rep.errore);
  html+=laneOsservato(oss);
  html+=laneRiferito(rep&&rep.riferito);
  html+=timeline(rep&&rep.progresso);
  html+=laneLimiti((rep&&rep.limiti)||null);
  html+='<div class="side-title"><span>Documenti grezzi</span></div>'+artefatti(job.id);
  el('detail').innerHTML=html;
}

function laneOsservato(oss){
  if(!oss){
    return lane('osservato','Osservato qui',
      '<div class="empty">REA non ha ancora chiuso questo lavoro.</div>');
  }
  var tronco=!!(oss.troncato&&(oss.troncato.stdout||oss.troncato.stderr));
  var righe=[
    ['esito',oss.esito],
    ['codice di uscita',oss.exit_code==null?'— (timeout)':oss.exit_code],
    ['durata',oss.durata_s+' s'],
    ['stdout raccolto',oss.stdout_bytes+' B'],
    ['stderr raccolto',oss.stderr_bytes+' B'],
    ['troncato',tronco?'sì: tetto di raccolta raggiunto':'no'],
  ];
  return lane('osservato','Osservato qui','<table class="mini">'
    +righe.map(function(r){ return rigaMini(r[0],r[1]); }).join('')+'</table>'
    +'<div class="hint">Byte, codice di uscita, durata e sha256 sono misurati da questa '
    +'superficie sulla copia del file: non sono dichiarazioni di REA.</div>');
}

function laneRiferito(rif){
  if(!rif) return '';
  var corpo='<div class="hint">'+escH(rif.nota||'')+'</div>';
  if(rif.verdetto){
    corpo+='<table class="mini">'+rigaMini('verdetto di REA',
      (rif.verdetto.healthy?'healthy: true':'healthy: false')
      +(rif.verdetto.environment_healthy==null?''
        :' &middot; environment_healthy: '+(rif.verdetto.environment_healthy?'true':'false')))
      +'</table>';
  }
  if(rif.chiavi&&rif.chiavi.length){
    corpo+='<table class="mini">'+rif.chiavi.map(function(c){
      return rigaMini(c.chiave,(c.tipo||'?')+(c.n==null?'':' · '+c.n));
    }).join('')+'</table>';
  }
  if(rif.collezioni&&rif.collezioni.length){
    corpo+='<h3>Collezioni di oggetti</h3><table class="mini">'+rif.collezioni.map(function(c){
      return rigaMini(c.per,c.n);
    }).join('')+'</table>';
  }
  if(rif.digest&&rif.digest.length){
    corpo+='<h3>Digest e identificatori riferiti</h3><table class="mini">'+rif.digest.map(function(c){
      return rigaMini(c.per,c.valore);
    }).join('')+'</table>';
  }
  return lane('riferito','Riferito da REA',corpo);
}

function boxErrore(err){
  if(!err) return '';
  return '<div class="box-err"><div class="code">'+escH(err.code)+' · '+escH(err.category)
    +'</div><div>'+escH(err.spiegazione||'')+'</div>'
    +(err.message?'<div class="mono">'+escH(err.message)+'</div>':'')
    +(err.remediation?'<div class="hint">rimedio indicato: '+escH(err.remediation)+'</div>':'')
    +'<div class="hint">'+(err.retryable
      ?'REA segnala che si può ritentare.'
      :'REA segnala che ritentare non cambia l\'esito.')+'</div></div>';
}

function timeline(progresso){
  if(!progresso||!progresso.length) return '';
  return lane('progresso','Progresso dichiarato da REA','<ol class="timeline">'
    +progresso.map(function(p){
      return '<li>'+escH(p.fase)+(p.file?' '+escH(p.file):'')
        +(p.messaggio?' — '+escH(p.messaggio):'')+'</li>';
    }).join('')+'</ol>');
}

function laneLimiti(limiti){
  if(!limiti||!limiti.length) return '';
  return lane('limiti','Limiti di questa lettura','<ul class="limiti">'
    +limiti.map(function(l){ return '<li>'+escH(l)+'</li>'; }).join('')+'</ul>');
}

function artefatti(id){
  var voci=(ST&&ST.artifacts)||['report.json','job.json','stdout.json','stderr.log'];
  return '<div class="arts">'+voci.map(function(n){
    return '<a href="/api/jobs/'+encodeURIComponent(id)+'/artifact/'+encodeURIComponent(n)
      +'">'+escH(n)+'</a>';
  }).join('')+'</div>';
}

boot();
</script>
</body>
</html>
"""
# ── L'applicazione ───────────────────────────────────────────────────────────

def salva_copia(flusso, destinazione: Path, massimo: int = MAX_UPLOAD_BYTES) -> int:
    """Copia un upload a blocchi, contando i byte; oltre il tetto si ferma."""
    scritti = 0
    with destinazione.open("wb") as uscita:
        while True:
            blocco = flusso.read(BYTE_AL_COLPO)
            if not blocco:
                break
            scritti += len(blocco)
            if scritti > massimo:
                raise ValueError(f"il file supera il tetto di {massimo // (1024 * 1024)} MB")
            uscita.write(blocco)
    return scritti


def stato_rea(trovato: dict, con_versione: bool = True) -> dict:
    """Il blocco `rea` di /api/status: dove sta e cosa risponde."""
    fuori = dict(trovato)
    if fuori.get("found") and con_versione:
        fuori["version"] = rea_version(fuori["path"])
    return fuori


def installazione_richiesta() -> list[dict]:
    """I comandi che l'operatore puo' eseguire lui: qui non parte niente."""
    return [{"nome": nome, "comando": comando, "nota": nota}
            for nome, comando, nota in COMANDI_INSTALLAZIONE]


def build_app(workspace: Path | None = None, trovato: dict | None = None,
              avvia_runner: bool = True) -> Flask:
    """L'app della superficie: legge, accoda un lavoro, mostra il report.

    Nessuna rotta accetta un percorso scelto dal client e nessuna esegue `rea`
    da sola: l'unico punto che lancia un processo e' il `Runner`, con l'argv
    costruito da `build_argv` e il target sempre dentro la workspace del job.
    """
    ws = Path(workspace) if workspace is not None else WORKSPACE
    jobs_dir = ws / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    rea = stato_rea(trovato if trovato is not None else rea_binary())
    runner = Runner(rea["path"], jobs_dir) if rea.get("found") else None
    if runner is not None and avvia_runner:
        runner.start()

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    app.config["REA_RUNNER"] = runner

    def _errore(messaggio: str, codice: int, dettaglio: str = "",
                extra: dict | None = None):
        corpo = {"error": messaggio}
        if dettaglio:
            corpo["detail"] = dettaglio
        if extra:
            corpo.update(extra)
        return jsonify(corpo), codice

    @app.route("/health")
    def health():
        return jsonify({"ok": True, "service": "rea-surface", "static_only": True,
                        "host": HOST, "rea": bool(rea.get("found")),
                        "jobs": len(elenca_lavori(jobs_dir))})

    @app.route("/api/status")
    def api_status():
        return jsonify({
            "workspace": str(ws),
            "jobs": {"n": len(elenca_lavori(jobs_dir)), "bytes": peso_workspace(jobs_dir)},
            "rea": rea,
            "ops": [op.as_dict() for op in OPERAZIONI],
            "providers": list(PROVIDER),
            "artifacts": list(ARTEFATTI),
            "install": installazione_richiesta(),
            "limits": {
                "timeout_s": TIMEOUT_S,
                "upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
                "output_mb": MAX_OUTPUT_BYTES // (1024 * 1024),
                "workspace_mb": MAX_WORKSPACE_BYTES // (1024 * 1024),
                "queued_max": MAX_IN_CODA,
            },
            "note": LIMITI_FISSI[1],
        })

    @app.route("/api/operations")
    def api_operations():
        return jsonify({"operations": [op.as_dict() for op in OPERAZIONI],
                        "providers": list(PROVIDER),
                        "artifacts": list(ARTEFATTI)})


    @app.route("/api/jobs", methods=["GET"])
    def api_jobs():
        return jsonify({"jobs": elenca_lavori(jobs_dir), "workspace": str(ws)})

    @app.route("/api/jobs", methods=["POST"])
    def api_jobs_nuovo():
        """Accoda un lavoro: e' l'unica rotta che scrive nella workspace."""
        if runner is None:
            return _errore("REA non e' disponibile su questa macchina", 503,
                           rea.get("error") or "", {"install": installazione_richiesta()})
        modulo = request.form
        op = _OPS.get((modulo.get("op") or "").strip())
        if op is None:
            return _errore("operazione non esposta", 400,
                           "scegli una voce di /api/operations")
        argomento, errore = valida_argomento(op, modulo.get("argomento"))
        if errore:
            return _errore(errore, 400)
        provider, errore = valida_provider(op, modulo.get("provider"))
        if errore:
            return _errore(errore, 400)
        if not runner.posti_liberi():
            return _errore(f"la coda e' piena ({MAX_IN_CODA} lavori)", 429,
                           "aspetta che finiscano o svuota data/rea/jobs a mano")
        occupato = peso_workspace(jobs_dir)
        if occupato >= MAX_WORKSPACE_BYTES:
            return _errore("la workspace e' piena", 507,
                           f"{occupato} B su {MAX_WORKSPACE_BYTES} B: "
                           "cancella i lavori vecchi in data/rea/jobs")

        job_id = uuid.uuid4().hex[:12]
        cartella = jobs_dir / job_id
        (cartella / "target").mkdir(parents=True, exist_ok=False)
        target = None
        percorso_target: Path | None = None
        try:
            if op.target == "file":
                caricato = request.files.get("file")
                if caricato is None or not (caricato.filename or "").strip():
                    raise ValueError("serve un file da analizzare")
                nome = sanifica_nome(caricato.filename)
                percorso_target = cartella / "target" / nome
                byte_scritti = salva_copia(caricato.stream, percorso_target)
                if byte_scritti == 0:
                    raise ValueError("il file caricato e' vuoto")
                target = {"nome": nome, "bytes": byte_scritti,
                          "sha256": sha256_file(percorso_target)}
        except ValueError as exc:
            shutil.rmtree(cartella, ignore_errors=True)
            codice = 413 if "tetto" in str(exc) else 400
            return _errore(str(exc), codice)

        record = {
            "id": job_id, "op": op.id, "titolo": op.titolo, "status": "queued",
            "esito": None, "created_at": ora(), "started_at": None, "finished_at": None,
            "exit_code": None, "duration_s": None, "argomento": argomento,
            "provider": provider, "target": target,
            "comando": build_argv(rea["path"], op, percorso_target, argomento, provider),
        }
        scrivi_json(cartella / "job.json", record)
        runner.accoda(record)
        return jsonify({"job": riassunto(record)}), 202

    @app.route("/api/jobs/<job_id>")
    def api_job(job_id: str):
        cartella = job_dir(jobs_dir, job_id)
        if cartella is None or not cartella.is_dir():
            return _errore("lavoro sconosciuto", 404, f"id non valido: {job_id!r}")
        record = scarica_json(cartella / "job.json")
        if not record:
            return _errore("job.json illeggibile", 500, str(cartella / "job.json"))
        return jsonify({"job": record, "report": scarica_json(cartella / "report.json")})

    @app.route("/api/jobs/<job_id>/artifact/<name>")
    def api_artefatto(job_id: str, name: str):
        """Il documento grezzo: e' quello che la riduzione non sostituisce."""
        cartella = job_dir(jobs_dir, job_id)
        if cartella is None:
            return _errore("lavoro sconosciuto", 404, f"id non valido: {job_id!r}")
        if name not in ARTEFATTI:
            return _errore("documento non esposto", 404, " | ".join(ARTEFATTI))
        percorso = cartella / name
        if not percorso.is_file():
            return _errore(f"{name} non c'e' per questo lavoro", 404,
                           "il documento compare quando il lavoro e' finito")
        tipo = "application/json" if name.endswith(".json") else "text/plain"
        return send_file(percorso, mimetype=tipo + "; charset=utf-8",
                         as_attachment=False, download_name=f"{job_id}-{name}")

    @app.errorhandler(413)
    def troppo_grande(_errore_flask):
        return _errore("file troppo grande", 413,
                       f"il tetto di caricamento e' {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")

    @app.route("/")
    def index():
        return Response(_PAGE, mimetype="text/html; charset=utf-8")

    return app


# ── L'avvio ──────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Superficie locale per REA: dare un artefatto da analizzare "
                    "e leggere il report (solo loopback, solo analisi statica)")
    parser.add_argument("--check", action="store_true",
                        help="verifica dove sta `rea` e cosa esporrebbe, "
                             "senza avviare il servizio")
    parser.add_argument("--host", default=HOST,
                        help=f"interfaccia (default {HOST}: solo loopback)")
    parser.add_argument("--port", type=int, default=PORT, help=f"porta (default {PORT})")
    args = parser.parse_args(argv)

    rea = rea_binary()
    if args.check:
        print(f"workspace: {WORKSPACE}", flush=True)
        print(f"operazioni esposte ({len(OPERAZIONI)}): "
              + ", ".join(op.id for op in OPERAZIONI), flush=True)
        print("non esposte per scelta: setup, update, uninstall, import-reference-source, "
              "capture-process, browser/Electron via CDP, riconciliazione runtime", flush=True)
        if not rea.get("found"):
            print(f"rea: NON trovato — {rea.get('error')}", flush=True)
            for nome, comando, _nota in COMANDI_INSTALLAZIONE:
                print(f"  [{nome}] {comando}", flush=True)
            print("La pagina mostrera' questi comandi e non installera' niente.", flush=True)
            return 1
        versione = (rea_version(rea["path"]).get("testo") or "?").splitlines()
        print(f"rea: {rea['path']} ({rea['source']}) — {versione[0] if versione else '?'}",
              flush=True)
        print("Superficie pronta.", flush=True)
        return 0

    if args.host != HOST:
        print(f"avviso: questa superficie e' pensata per loopback; host={args.host}", flush=True)
    print(f"Analisi artefatti (REA): http://{args.host}:{args.port}", flush=True)
    if not rea.get("found"):
        print("`rea` non e' nel PATH: la pagina mostrera' i comandi di installazione.",
              flush=True)
    build_app().run(host=args.host, port=args.port, debug=False, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
