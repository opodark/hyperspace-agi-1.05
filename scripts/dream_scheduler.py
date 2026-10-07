#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Mac host worker: tiene vivo il sogno notturno quando il control-plane tace.

Perché esiste: il ciclo dei sogni gira in un thread dentro il control-plane, e un
thread può morire senza che nessuno se ne accorga — è già successo, notti senza
sogni con il ciclo acceso. Questo ticchettio non decide niente da sé: chiama
`POST /dreams/nightly/tick`, che applica **le stesse guardie** del loop (finestra
notturna, quota, intervallo minimo). Se il loop è vivo il tick risponde `saltato`
e non produce un secondo sogno; se è morto, sogna.

Come il resto del parco host (`scripts/reel_daily_scheduler.py`): sola libreria
standard, un lock per non sovrapporsi a un tick lento, e nessun fallimento
rumoroso — un control-plane spento o un token assente sono condizioni normali.

Uso:
    python3 scripts/dream_scheduler.py --once
    python3 scripts/dream_scheduler.py --once --url http://127.0.0.1:8085
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATO = ROOT / "data" / "dream-scheduler.json"
LOCK = ROOT / "data" / "dream-scheduler.lock"
# Il tick può far girare il modello locale: qualche decina di secondi è normale.
TIMEOUT = 120


def leggi_env(percorso: Path) -> dict:
    """KEY=VALUE dal .env: virgolette tolte, commenti in coda ignorati."""
    valori: dict[str, str] = {}
    try:
        righe = percorso.read_text(encoding="utf-8").splitlines()
    except OSError:
        return valori
    for linea in righe:
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        chiave, _, valore = linea.partition("=")
        valori[chiave.strip()] = valore.split(" #", 1)[0].strip().strip('"').strip("'")
    return valori


def base_del_control_plane(env: dict, url: str = "") -> str:
    """Dove sta il control-plane: come `scripts/hs.py`, per non avere due convenzioni."""
    porta = str(env.get("CONTROL_PLANE_PORT") or "8085").strip()
    return (url or env.get("HS_CLI_URL") or f"http://127.0.0.1:{porta}").rstrip("/")


def _scrivi_stato(percorso: Path, stato: dict) -> None:
    """Scrittura atomica: lo stato letto dal monitor è sempre intero."""
    percorso.parent.mkdir(parents=True, exist_ok=True)
    fd, nome = tempfile.mkstemp(prefix="." + percorso.name, suffix=".tmp",
                                dir=percorso.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(stato, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(nome, percorso)
    finally:
        Path(nome).unlink(missing_ok=True)


def tick(base: str, token: str, *, timeout: int = TIMEOUT) -> dict:
    """Un POST a `/dreams/nightly/tick`. Ritorna l'esito, o il motivo del no."""
    richiesta = urllib.request.Request(
        f"{base}/dreams/nightly/tick", data=b"{}", method="POST",
        headers={"Content-Type": "application/json",
                 "X-Hyperspace-Network-Token": token})
    try:
        with urllib.request.urlopen(richiesta, timeout=max(5, int(timeout))) as risposta:
            corpo = risposta.read().decode("utf-8", "replace") or "{}"
            return {"ok": True, "http": risposta.status, "risposta": json.loads(corpo)}
    except urllib.error.HTTPError as error:
        return {"ok": False, "http": error.code,
                "errore": _spiega(error.code, error.read().decode("utf-8", "replace"))}
    except (urllib.error.URLError, ValueError, OSError) as error:
        return {"ok": False, "errore": f"{type(error).__name__}: {str(error)[:200]}"}


# I tre modi in cui un tick non riesce *parlano*: senza questa traduzione nel log
# resta l'HTML di Flask, che non dice né cosa fare né a chi.
_RIMEDI = {
    404: ("la rotta /dreams/nightly/tick non esiste su questo control-plane: sta "
          "girando codice precedente, riavvialo"),
    401: "token di rete non valido: controlla NETWORK_ADMIN_TOKEN nel .env",
    503: "il control-plane non ha un NETWORK_ADMIN_TOKEN di almeno 32 caratteri",
}


def _spiega(codice: int, corpo: str) -> str:
    """Il motivo del no in una riga leggibile: il rimedio, o il corpo ripulito."""
    rimedio = _RIMEDI.get(int(codice or 0))
    if rimedio:
        return f"HTTP {codice} — {rimedio}"
    return f"HTTP {codice} — {' '.join((corpo or '').split())[:200]}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--once", action="store_true",
                        help="un tick e termina (è come lo lancia launchd)")
    parser.add_argument("--url", default="", help="base del control-plane (default 127.0.0.1:8085)")
    parser.add_argument("--env", default=str(ROOT / ".env"), help="file .env (token e porta)")
    parser.add_argument("--timeout", type=int, default=TIMEOUT,
                        help="secondi di attesa della risposta")
    args = parser.parse_args(argv)

    env = leggi_env(Path(args.env))
    token = str(env.get("NETWORK_ADMIN_TOKEN") or "").strip()
    base = base_del_control_plane(env, args.url)
    adesso = datetime.now().astimezone().isoformat(timespec="seconds")
    if len(token) < 32:
        print("token di rete assente o troppo corto (.env → NETWORK_ADMIN_TOKEN): nessun tick.")
        _scrivi_stato(STATO, {"ts": adesso, "ok": False, "motivo": "token di rete assente"})
        return 0

    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("un altro tick è in corso: salto questo giro.")
            return 0
        esito = tick(base, token, timeout=args.timeout)

    risposta = esito.get("risposta") or {}
    salute = (risposta.get("stato") or {}).get("salute") or {}
    dettagli = [f"esito: {risposta.get('esito') or esito.get('errore')}"]
    for chiave in ("motivo", "autore", "voce_id"):
        if risposta.get(chiave):
            dettagli.append(f"{chiave}: {risposta[chiave]}")
    print(f"{adesso}  {base}")
    print("  " + " | ".join(dettagli))
    if salute:
        print(f"  salute: {salute.get('verdetto')} — {salute.get('dettaglio')}")
    _scrivi_stato(STATO, {
        "ts": adesso, "ok": bool(esito.get("ok")),
        "esito": risposta.get("esito") or "", "motivo": risposta.get("motivo") or "",
        "autore": risposta.get("autore") or "", "voce_id": risposta.get("voce_id") or "",
        "salute": salute.get("verdetto") or "", "errore": esito.get("errore") or "",
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
