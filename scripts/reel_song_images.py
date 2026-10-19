#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Accoda le scene di una canzone come sogni generici (Pony, nessun volto fisso).

Non è la persona di Anna: nessun reference_image, nessuna vetrina. La famiglia è
`sdxl-turbo` (CyberRealistic Pony, sul Mac), quindi ogni scena esce con un volto
deciso dal seed — un "sogno randomico". Per tenerla vagamente coerente si parte da
un seed base e ogni scena aggiunge il suo indice.

Uso:
    python scripts/reel_song_images.py --prova     # stampa le scene, non accoda
    python scripts/reel_song_images.py             # accoda e basta (per la notte)
    python scripts/reel_song_images.py --solo 1,5,8
    python scripts/reel_song_images.py --seed 20261018 --pausa 90

A coda piena (HTTP 429) dorme `--pausa` secondi e ritenta: non perde scene.
Le immagini escono in HyperSpace/bridge_XXXXX.jpg.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8085"
FAMIGLIA = "sdxl-turbo"
LATO = 1024
PASSI = 30
NEGATIVO = ("low quality, worst quality, bad anatomy, bad hands, extra limbs, "
            "text, watermark, logo, signature, cropped head, out of frame")

# Le dodici scene del viaggio: oppressione → scoperta di sé. Inglese perché CLIP
# legge l'inglese; il volto lo decide il seed (nessun riferimento).
SCENE = (
    ("1-identita", "wide shot, a young woman alone in a vast dim room lined with tall mirrors, distant lost gaze, cool pastel tones, soft haze"),
    ("2-scomparsa", "full body, a woman standing in thin mist, half dissolving into the fog, introspective, muted blue-grey palette, diffused light"),
    ("3-china", "full body, a woman climbing an endless stone staircase up a steep cliff, strained effort, vast pale sky, cool morning light"),
    ("4-perfezione", "medium shot, a woman gazing at one perfect white lily in a wildflower field, longing, golden hour, warm rim light"),
    ("5-distanza", "intimate shot, a woman standing in a doorway gazing at an empty chair by a window, silent emotional distance, warm dim interior"),
    ("6-compagno", "close shot, a woman leaning her head on a man's shoulder, eyes closed in peace, warm candlelight, soft shadows"),
    ("7-solitudine", "seated, a woman alone in a dark room on an old armchair, surrounded by books and memories, deep solitude, single dim lamp"),
    ("8-respiro-luce", "close-up, a woman's face struck by a sudden sunbeam, faint hopeful smile, fleeting light, bright warm glow"),
    ("9-fragilita", "full body, a woman walking under light rain, thin flowing dress dancing in the wind, accepting fragility, overcast soft light"),
    ("10-studio", "full body, a woman in an ancient library, floating sheets of paper and open books around her, doubt and knowledge, warm lamplight"),
    ("11-passato", "a woman lighting a candle for others while staying in shadow, quiet selfless dedication, dim warm candle glow"),
    ("12-risveglio", "close-up, a serene woman's face, eyes closed, gentle smile, holding a warm cup of tea, peaceful acceptance, golden morning light"),
)


def token_canale(nome: str = "") -> str:
    """Il token di canale dal .env (default: 'comfy', poi il primo valido)."""
    env = ROOT / ".env"
    if not env.is_file():
        return ""
    clienti = ""
    for riga in env.read_text(encoding="utf-8", errors="replace").splitlines():
        riga = riga.strip()
        if riga.startswith("CHANNEL_CLIENTS="):
            clienti = riga.partition("=")[2].strip().strip('"').strip("'")
            break
    voci = {}
    for voce in clienti.split(";"):
        if "=" in voce:
            chiave, _, valore = voce.partition("=")
            voci[chiave.strip().lower()] = valore.strip()
    if nome:
        return voci.get(nome.strip().lower(), "")
    return voci.get("comfy") or (next(iter(voci.values()), "") if voci else "")


def _chiama(path: str, token: str, *, payload: dict | None = None,
            timeout: float = 30.0) -> tuple[int, dict]:
    """GET/POST verso il control-plane. Non solleva: ritorna (0, errore)."""
    corpo = json.dumps(payload).encode("utf-8") if payload is not None else None
    richiesta = urllib.request.Request(
        BASE + path, data=corpo,
        headers={"X-Hyperspace-Channel-Token": token,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(richiesta, timeout=timeout) as risposta:
            dati = json.loads(risposta.read().decode("utf-8", "replace") or "{}")
            return risposta.status, dati
    except urllib.error.HTTPError as errore:
        try:
            dati = json.loads(errore.read().decode("utf-8", "replace") or "{}")
        except ValueError:
            dati = {"errore": str(errore)}
        return errore.code, dati
    except urllib.error.URLError as errore:
        return 0, {"errore": str(errore)[:160]}


def accoda(token: str, scena: str, seed: int, pausa_s: float,
           pazienza_s: float) -> tuple[dict | None, str, float]:
    """Accoda una scena, aspettando se la coda è piena. (job|None, motivo, atteso)."""
    scadenza = time.monotonic() + pazienza_s
    atteso = 0.0
    while True:
        stato, dati = _chiama("/image/generate", token, payload={
            "prompt": scena, "negativo": NEGATIVO, "famiglia": FAMIGLIA,
            "larghezza": LATO, "altezza": LATO, "passi": PASSI, "seed": seed})
        if stato == 201 and dati.get("job"):
            return dati["job"], "", atteso
        motivo = dati.get("error") or f"HTTP {stato}"
        if stato == 429 and time.monotonic() < scadenza:
            time.sleep(pausa_s)
            atteso += pausa_s
            continue
        return None, motivo, atteso


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--prova", action="store_true",
                        help="stampa le scene e i prompt, non accoda")
    parser.add_argument("--solo", default="",
                        help="numeri separati da virgola (es. 1,5,8)")
    parser.add_argument("--seed", type=int, default=0,
                        help="seed base (ogni scena aggiunge il suo indice)")
    parser.add_argument("--pausa", type=float, default=60.0,
                        help="attesa fra due tentativi a coda piena")
    parser.add_argument("--pazienza", type=float, default=7200.0,
                        help="tetto per OGNI scena, oltre si dichiara non accodata")
    args = parser.parse_args()

    scelte = list(SCENE)
    if args.solo:
        numeri = {int(n) for n in args.solo.split(",") if n.strip().isdigit()}
        scelte = [(nome, p) for i, (nome, p) in enumerate(SCENE, start=1)
                  if i in numeri]

    if args.prova:
        for indice, (nome, scena) in enumerate(scelte, start=1):
            print(f"[{indice}/{len(scelte)}] {nome}\n  {scena}\n")
        return 0

    token = token_canale()
    if not token:
        print("nessun token di canale in .env (CHANNEL_CLIENTS): la coda non è raggiungibile")
        return 1
    stato, dati = _chiama("/image/status", token, timeout=15)
    if stato != 200:
        print(f"control-plane {BASE}: non raggiungibile ({stato or dati.get('errore', '')})")
        return 1
    print(f"control-plane {BASE}: ok")

    accodate, non_accodate, attese = 0, 0, 0.0
    for indice, (nome, scena) in enumerate(scelte, start=1):
        seed = args.seed + indice
        job, motivo, atteso = accoda(token, scena, seed, args.pausa, args.pazienza)
        attese += atteso
        if job is None:
            non_accodate += 1
            print(f"[{indice}/{len(scelte)}] {nome}: NON ACCODATA — {motivo}")
            continue
        accodate += 1
        print(f"[{indice}/{len(scelte)}] {nome}: job {job['id']} seed={job['seed']}"
              + (f" · in coda dopo {int(atteso)}s" if atteso >= 1 else ""))

    print("")
    print(f"accodate {accodate} scene su {len(scelte)}"
          + (f" · {non_accodate} non accodate" if non_accodate else "")
          + (f" · {int(attese)}s passati ad aspettare la coda" if attese >= 1 else ""))
    stato, dati = _chiama("/image/status", token, timeout=15)
    if stato == 200:
        print(f"coda: {dati.get('in_coda', 0)} in attesa, "
              f"{dati.get('in_esecuzione', 0)} in corso")
    return 0 if accodate else 1


if __name__ == "__main__":
    raise SystemExit(main())

