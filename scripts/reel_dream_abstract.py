#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Accoda sogni astratti SENZA persona: nessun volto, nessun riferimento, nessuna LoRA.

Serve a provare che il motore produce immagini che non sono "una donna": solo
paesaggi e materia onirica. Ricetta della WebUI (`webui_image_env.py`): Pony
(`sdxl-turbo`), 768x768, 25 passi. Uso: `python scripts/reel_dream_abstract.py`.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "rsi", str(ROOT / "scripts" / "reel_song_images.py"))
rsi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rsi)

PROMPT = (
    "abstract dream, a vast misty field of tall silver grass bending under a slow wind, dawn light through low fog, no people, ethereal, muted cool palette",
    "abstract dream, a lone paper boat drifting on a dark still lake under a sky full of reflected stars, no people, deep blue and gold",
    "abstract dream, fragments of an old letter dissolving into golden dust above an open window, warm afternoon light, no people",
    "abstract dream, an endless spiral staircase of light rising through clouds, gradient from cold violet to warm gold, no people",
    "abstract dream, a single candle flame bending in a dark room, tiny sparks rising into shadow, warm amber glow, no people",
    "abstract dream, rain falling upward from a mirror-like puddle, droplets catching a brief sunbeam, silver and gold, no people",
)


def main() -> int:
    tok = rsi.token_canale()
    if not tok:
        print("nessun token di canale in .env (CHANNEL_CLIENTS)")
        return 1
    accodate = 0
    for i, prompt in enumerate(PROMPT, start=1):
        stato, dati = rsi._chiama("/image/generate", tok, payload={
            "prompt": prompt, "negativo": rsi.NEGATIVO, "famiglia": "sdxl-turbo",
            "larghezza": 768, "altezza": 768, "passi": 25, "seed": 1000 + i})
        if stato == 201:
            job = dati.get("job", {})
            print(f"[{i}/{len(PROMPT)}] job {job.get('id', '')[:12]} "
                  f"seed={job.get('seed')} {job.get('larghezza')}x{job.get('altezza')}")
            accodate += 1
        else:
            print(f"[{i}/{len(PROMPT)}] NON ACCODATO: HTTP {stato} {dati.get('error', '')}")
    _, stato = rsi._chiama("/image/status", tok, timeout=10)
    print(f"coda: {stato.get('in_coda')} in attesa, {stato.get('in_esecuzione')} in corso")
    return 0 if accodate else 1


if __name__ == "__main__":
    raise SystemExit(main())
