#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Sintesi vocale ed automazione audio per HyperSpace (Kokoro TTS / Telegram / Playback).

Permette a qualsiasi agente o utente di generare voce naturale, riprodurla
immediatamente dagli altoparlanti, salvarla in file o inviarla come nota vocale
su Telegram.

Uso da riga di comando:
  python scripts/speak.py "Mi piace pensare a un prato cibernetico..."
  python scripts/speak.py --file poesia.txt --voice if_sara
  python scripts/speak.py "Allarme completato" --out alert.wav --no-play
  python scripts/speak.py "Ecco l'aggiornamento" --telegram 12345678
"""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = os.getenv("KOKORO_URL", "http://127.0.0.1:8880")
DEFAULT_VOICE = os.getenv("KOKORO_VOICE", "if_sara")


def synthesize_speech(
    text: str,
    *,
    voice: str = DEFAULT_VOICE,
    speed: float = 1.0,
    server_url: str = DEFAULT_URL,
    fmt: str = "wav"
) -> bytes:
    """Sintetizza il testo chiamando il servizio Kokoro TTS locale."""
    endpoint = f"{server_url.rstrip('/')}/v1/audio/speech"
    payload = json.dumps({
        "input": text,
        "voice": voice,
        "speed": speed,
        "response_format": fmt
    }).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except Exception as exc:
        # Se il server non risponde, prova fallback locale o errore chiaro
        raise RuntimeError(f"Impossibile raggiungere il servizio Kokoro su {endpoint}: {exc}") from exc


def play_audio(audio_path: str | Path) -> bool:
    """Riproduce il file audio sugli altoparlanti di sistema."""
    path = str(audio_path)
    if sys.platform == "darwin":
        try:
            subprocess.run(["afplay", path], check=True)
            return True
        except Exception as e:
            print(f"[speak] Errore riproduzione afplay: {e}", file=sys.stderr)
            return False
    elif sys.platform.startswith("win"):
        try:
            cmd = f"(New-Object Media.SoundPlayer '{path}').PlaySync()"
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], check=True)
            return True
        except Exception as e:
            print(f"[speak] Errore riproduzione Windows: {e}", file=sys.stderr)
            return False
    else:
        for player in ("paplay", "aplay", "ffplay"):
            try:
                subprocess.run([player, path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:
                continue
    return False


def send_telegram_voice(audio_bytes: bytes, chat_id: str | int, *, bot_token: str = "", caption: str = "") -> bool:
    """Invia una nota vocale via Telegram Bot API."""
    if not bot_token:
        # Cerca token in data/telegram-bot.env se presente
        env_file = ROOT / "data" / "telegram-bot.env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    bot_token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")

    if not bot_token:
        print("[speak] Errore Telegram: token del bot non configurato", file=sys.stderr)
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendVoice"
    boundary = "----HyperSpaceSpeechBoundary" + os.urandom(8).hex()

    body = io.BytesIO()
    # chat_id field
    body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}\r\n".encode())
    if caption:
        body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n".encode())
    # voice file
    body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"voice\"; filename=\"voice.ogg\"\r\nContent-Type: audio/ogg\r\n\r\n".encode())
    body.write(audio_bytes)
    body.write(f"\r\n--{boundary}--\r\n".encode())

    data = body.getvalue()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            res = json.loads(resp.read().decode())
            return bool(res.get("ok"))
    except Exception as e:
        print(f"[speak] Errore invio Telegram sendVoice: {e}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="HyperSpace Voice Automator (Kokoro TTS)")
    parser.add_argument("text", nargs="?", help="Testo da leggere ad alta voce (oppure da stdin)")
    parser.add_argument("-f", "--file", help="File di testo da leggere")
    parser.add_argument("-v", "--voice", default=DEFAULT_VOICE, help=f"Voce Kokoro (default: {DEFAULT_VOICE}, es. if_sara, im_nicola, af_heart)")
    parser.add_argument("-s", "--speed", type=float, default=1.0, help="Velocità di lettura (default: 1.0)")
    parser.add_argument("-o", "--out", help="Percorso del file audio in cui salvare l'output (WAV)")
    parser.add_argument("--no-play", action="store_true", help="Non riprodurre l'audio dagli altoparlanti")
    parser.add_argument("-t", "--telegram", help="Chat ID Telegram a cui inviare l'audio come nota vocale")
    parser.add_argument("--server", default=DEFAULT_URL, help=f"URL del servizio Kokoro TTS (default: {DEFAULT_URL})")

    args = parser.parse_args()

    # Risoluzione testo
    content = ""
    if args.file:
        p = Path(args.file)
        if not p.exists():
            print(f"[speak] File non trovato: {p}", file=sys.stderr)
            return 1
        content = p.read_text(encoding="utf-8")
    elif args.text:
        content = args.text
    elif not sys.stdin.isatty():
        content = sys.stdin.read()

    content = content.strip()
    if not content:
        print("[speak] Nessun testo specificato da leggere.", file=sys.stderr)
        return 1

    print(f"[speak] Sintesi in corso con voce '{args.voice}' ({len(content)} caratteri)...")
    try:
        audio_data = synthesize_speech(content, voice=args.voice, speed=args.speed, server_url=args.server)
    except Exception as e:
        print(f"[speak] {e}", file=sys.stderr)
        return 1

    # Salvataggio su file
    out_path = args.out
    temp_used = False
    if not out_path:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            out_path = tf.name
            temp_used = True

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(audio_data)

    print(f"[speak] Audio pronto: {out_path} ({len(audio_data)} byte)")

    # Invia a Telegram se richiesto
    if args.telegram:
        print(f"[speak] Invio nota vocale a Telegram chat {args.telegram}...")
        ok = send_telegram_voice(audio_data, args.telegram, caption=content[:100] + ("..." if len(content) > 100 else ""))
        if ok:
            print("[speak] Nota vocale Telegram inviata con successo!")
        else:
            print("[speak] Invio nota vocale Telegram fallito.", file=sys.stderr)

    # Riproduzione
    if not args.no_play:
        print(f"[speak] Riproduzione audio in corso...")
        play_audio(out_path)

    if temp_used and args.no_play:
        # Se era temporaneo e non lo abbiamo riprodotto né salvato altrove, lascialo per riferimento
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
