#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Il monitor dei sogni da terminale: la stessa fotografia di /dreams/nightly/status.

Perché esiste: il ciclo dei sogni muore in silenzio. È già successo — notti senza
sogni con `DREAM_LOOP_ENABLED=true` e nessuno se n'è accorto, perché "nessun
sogno" e "nessun errore" si assomigliano. Questo comando risponde in una
schermata: quand'è stato l'ultimo sogno, che fine ha fatto lo sketch, il post è
finito su Instagram e — se non ha sognato — perché.

Legge i file del control-plane (diario, coda immagini, registro dettagliato) e il
`.env` con le stesse soglie del ciclo: nessuna rete, nessun container, sola
lettura.

Uso:
    python3 scripts/dream_monitor.py                 # ultimi sogni + salute
    python3 scripts/dream_monitor.py --json          # il payload di /dreams/nightly/status
    python3 scripts/dream_monitor.py --watch 60      # come sopra, ogni minuto
    python3 scripts/dream_monitor.py --limite 24

Esce con codice 1 quando il verdetto è `muto`: un monitor che esce sempre 0 non
sveglia nessuno (cron, launchd, una catena di comandi).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.dream_log import RegistroSogni  # noqa: E402
from shared.dream_monitor import sintesi  # noqa: E402

VERDETTI = {"ok": "OK", "attenzione": "ATTENZIONE", "muto": "MUTO", "spento": "SPENTO"}


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


def fuso_di(nome: str):
    """Il fuso del ciclo, o UTC: un fuso scritto male non deve fermare il monitor."""
    try:
        return ZoneInfo(str(nome or "Europe/Rome"))
    except Exception:
        return timezone.utc


def _intero(env: dict, chiave: str, default: int) -> int:
    try:
        return int(str(env.get(chiave, "")).strip())
    except (TypeError, ValueError):
        return int(default)


def _acceso(env: dict, chiave: str) -> bool:
    return str(env.get(chiave, "false")).strip().lower() == "true"


def _leggi_json(percorso: Path) -> dict:
    try:
        return json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def config_del_ciclo(env: dict) -> dict:
    """Le soglie del ciclo lette dal `.env`: le stesse che legge il control-plane."""
    return {
        "abilitato": _acceso(env, "DREAM_LOOP_ENABLED"),
        "finestra": (_intero(env, "DREAM_NIGHT_START_HOUR", 0),
                     _intero(env, "DREAM_NIGHT_END_HOUR", 8)),
        "quota_per_autrice": max(1, _intero(env, "DREAM_PER_AUTHOR_PER_DAY", 2)),
        "intervallo_s": max(900, _intero(env, "DREAM_LOOP_INTERVAL_S", 7200)),
        "controllo_s": max(60, _intero(env, "DREAM_LOOP_CHECK_S", 300)),
        "fuso": env.get("DREAM_TIMEZONE") or "Europe/Rome",
        "pubblica_su_instagram": _acceso(env, "INSTAGRAM_DREAM_PUBLISH_ENABLED"),
    }


def stato(directory: Path, env: dict, *, adesso: datetime, limite: int = 12) -> dict:
    """La fotografia del ciclo: gli stessi campi di `/dreams/nightly/status`."""
    diario = _leggi_json(directory / "diario.json")
    try:
        eventi = RegistroSogni(str(directory / "dream-log.jsonl")).read(400)
    except OSError:
        eventi = []
    return sintesi(voci=(diario.get("voci") or []), adesso=adesso,
                   jobs=_leggi_json(directory / "image-jobs.json"), eventi=eventi,
                   config=config_del_ciclo(env), limit=max(1, int(limite)))


def _breve(valore, fuso) -> str:
    """`06/10 02:58` nel fuso del ciclo, o un trattino se non c'è."""
    testo = str(valore or "").strip()
    if not testo:
        return "—"
    try:
        momento = datetime.fromisoformat(testo.replace("Z", "+00:00"))
    except ValueError:
        return testo[:16]
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(fuso).strftime("%d/%m %H:%M")


def rendi(fotografia: dict, *, fuso) -> str:
    """La schermata: salute, soglie, poi un sogno per riga con la sua fase."""
    config = fotografia.get("config") or {}
    salute = fotografia.get("salute") or {}
    quota = fotografia.get("quota") or {}
    inizio, fine = tuple(config.get("finestra") or (0, 8))[:2]
    verdetto = str(salute.get("verdetto") or "")
    righe = [
        f"Sogni — {VERDETTI.get(verdetto, verdetto.upper())}: {salute.get('dettaglio', '')}",
        f"  ciclo: {'acceso' if config.get('abilitato') else 'spento'}"
        f" | finestra {int(inizio):02d}–{int(fine):02d} ({config.get('fuso', '')})"
        f" | quota {config.get('quota_per_autrice')}/autrice"
        f" | intervallo {int(config.get('intervallo_s') or 0) // 60} min"
        f" | instagram {'sì' if config.get('pubblica_su_instagram') else 'no'}",
        f"  adesso {_breve(fotografia.get('adesso'), fuso)}"
        f" | finestra aperta: {'sì' if fotografia.get('finestra_aperta') else 'no'}"
        + (f" | si riapre {_breve(fotografia.get('prossima_finestra'), fuso)}"
           if fotografia.get("prossima_finestra") else ""),
        f"  quota oggi: anna {quota.get('anna', 0)}, aurora {quota.get('aurora', 0)}"
        f" | ultimo sogno: {_breve(fotografia.get('ultimo_sogno'), fuso)}",
        "",
    ]
    sogni = fotografia.get("sogni") or []
    if not sogni:
        righe.append("  (nessun sogno nel diario)")
    else:
        righe.append("  quando        autrice  fase                       instagram  voce")
        for sogno in sogni:
            righe.append("  {:<13} {:<8} {:<26} {:<10} {}".format(
                _breve(sogno.get("ts"), fuso), str(sogno.get("autore", "")),
                str(sogno.get("fase", "")), str(sogno.get("instagram", "")),
                str(sogno.get("voce_id", ""))))
            if sogno.get("testo"):
                righe.append(f"      «{str(sogno['testo'])[:96]}»")
    salti = fotografia.get("salti") or []
    if salti:
        righe.append("")
        righe.append("  ultimi giri a vuoto (perché non ha sognato):")
        for salto in salti:
            righe.append(f"    {_breve(salto.get('ts'), fuso)}  {salto.get('motivo', '')}")
    return "\n".join(righe)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", default=str(ROOT / "data" / "control-plane"),
                        help="cartella dati del control-plane (diario, coda, registro)")
    parser.add_argument("--env", default=str(ROOT / ".env"),
                        help="file .env con le soglie del ciclo")
    parser.add_argument("--limite", type=int, default=12, help="quanti sogni mostrare")
    parser.add_argument("--json", action="store_true", help="stampa il payload JSON")
    parser.add_argument("--watch", type=int, default=0, metavar="SECONDI",
                        help="ripete la lettura ogni N secondi (0 = una volta sola)")
    args = parser.parse_args(argv)

    directory = Path(args.dir)
    env = leggi_env(Path(args.env))
    fuso = fuso_di(env.get("DREAM_TIMEZONE") or "Europe/Rome")
    verdetto = ""
    while True:
        fotografia = stato(directory, env, adesso=datetime.now(fuso), limite=args.limite)
        verdetto = str((fotografia.get("salute") or {}).get("verdetto") or "")
        print(json.dumps(fotografia, ensure_ascii=False, indent=2)
              if args.json else rendi(fotografia, fuso=fuso))
        if args.watch <= 0:
            break
        sys.stdout.flush()
        time.sleep(max(5, args.watch))
    return 1 if verdetto == "muto" else 0


if __name__ == "__main__":
    raise SystemExit(main())
