#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Interroga i modelli TTS di Voicebox (voci clonate) dal terminale.

Perimetro: parla solo con Voicebox su 127.0.0.1:17493 (VOICEBOX_URL). Legge i
profili; `say` scrive un file audio in locale, non pubblica nulla.

    python scripts/diagnostics/voicebox_tts.py list
    python scripts/diagnostics/voicebox_tts.py say "Albi ita" "Ciao a tutti" -o prova.wav
    python scripts/diagnostics/voicebox_tts.py say "Albi ita" "Ciao" --engine qwen -o qwen.wav
    python scripts/diagnostics/voicebox_tts.py compare "Albi ita" "Testo di prova" --out-dir /tmp/confronto
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared import voicebox_client as vb  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="profili e motori disponibili")
    s = sub.add_parser("say", help="sintetizza un testo con un profilo")
    s.add_argument("profile")
    s.add_argument("text")
    s.add_argument("--engine", choices=vb.ENGINES)
    s.add_argument("--language")
    s.add_argument("-o", "--output", default="voicebox.wav")
    c = sub.add_parser("compare", help="stesso testo con più motori, per confrontarli all'ascolto")
    c.add_argument("profile")
    c.add_argument("text")
    c.add_argument("--engines", default="qwen,chatterbox", help="elenco separato da virgole")
    c.add_argument("--language")
    c.add_argument("--out-dir", default="voicebox-confronto")
    a = ap.parse_args()

    try:
        if a.cmd == "list":
            for p in vb.profiles():
                print(f"{p.get('name')!r:24} lingua={p.get('language')} motore={p.get('default_engine') or '-'} "
                      f"tipo={p.get('voice_type')} id={p.get('id')}")
            print("motori:", ", ".join(vb.ENGINES))
            return 0
        engines = [a.engine] if a.cmd == "say" else [e.strip() for e in a.engines.split(",") if e.strip()]
        for eng in engines:
            t0 = time.monotonic()
            wav = vb.synthesize(f"{vb.PREFIX}{a.profile}" + (f"@{eng}" if eng else ""), a.text, a.language)
            if a.cmd == "say":
                out = Path(a.output)
            else:
                out = Path(a.out_dir) / f"{eng}.wav"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(wav)
            print(f"{eng or 'predefinito'}: {out} ({len(wav) // 1024} KB, {time.monotonic() - t0:.1f}s)")
        return 0
    except vb.VoiceboxError as e:
        print(f"errore: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
