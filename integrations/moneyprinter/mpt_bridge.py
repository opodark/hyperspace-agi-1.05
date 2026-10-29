#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Ponte tra la mesh e MoneyPrinterTurbo: da un tema a un video da rivedere.

    python integrations/moneyprinter/mpt_bridge.py "Che cos'è una mesh di AI locali"
    python integrations/moneyprinter/mpt_bridge.py "Tema" --script-file testo.txt --voice kokoro:im_nicola
    python integrations/moneyprinter/mpt_bridge.py "Tema" --dry-run

Il video finisce in data/reels/mpt/ con un file .json accanto (tema, voce,
musica e relativa licenza). Non pubblica nulla: "da_rivedere" resta vero
finché una persona non lo guarda.

Musica: solo brani presenti in integrations/moneyprinter/music/ e registrati
in music/licenze.json. Se non ce ne sono, il video esce senza musica.
Solo libreria standard: gira con il Python della mesh o con python3 di sistema.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT_DIR = REPO / "data" / "reels" / "mpt"
MUSIC_DIR = HERE / "music"
STORAGE_TASKS = HERE / "storage" / "tasks"
KOKORO_URL = os.getenv("KOKORO_URL", "http://127.0.0.1:8880")
STATE_DONE, STATE_FAILED = 1, -1
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac")


def load_env() -> dict:
    env = {}
    f = HERE / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items() if k.startswith("MPT_")})
    return env


def slugify(text: str, limit: int = 48) -> str:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return (s[:limit].rstrip("-") or "video")


def licensed_tracks(music_dir: Path = MUSIC_DIR) -> list[dict]:
    """Brani utilizzabili: elencati in licenze.json, con licenza indicata, e presenti su disco."""
    try:
        data = json.loads((music_dir / "licenze.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for b in data.get("brani") or []:
        if not isinstance(b, dict):
            continue
        name = os.path.basename(str(b.get("file") or ""))
        if not name or not name.lower().endswith(AUDIO_EXT) or not str(b.get("licenza") or "").strip():
            continue
        if (music_dir / name).is_file():
            out.append({**b, "file": name})
    return out


def choose_music(choice: str, tracks: list[dict]) -> dict | None:
    if choice == "none" or not tracks:
        return None
    if choice == "auto":
        return random.choice(tracks)
    for t in tracks:
        if t["file"] == os.path.basename(choice):
            return t
    raise SystemExit(f"Il brano '{choice}' non è registrato in music/licenze.json (o manca il file).")


def build_payload(args, music: dict | None) -> dict:
    script = ""
    if args.script_file:
        script = Path(args.script_file).read_text(encoding="utf-8").strip()
    return {
        "video_subject": args.subject,
        "video_script": script,
        "video_language": args.language,
        "video_aspect": args.aspect,
        "video_source": "pexels",
        "video_clip_duration": args.clip_duration,
        "video_count": 1,
        "voice_name": args.voice,
        "voice_rate": 1.0,
        "bgm_type": "custom" if music else "",
        "bgm_file": music["file"] if music else "",
        "bgm_volume": 0.15,
        "subtitle_enabled": True,
        "paragraph_number": args.paragraphs,
    }


def http(method: str, url: str, key: str, body: dict | None = None, timeout: float = 30) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", "x-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise SystemExit(f"MoneyPrinterTurbo ha risposto {e.code}: {detail}") from None
    except urllib.error.URLError as e:
        raise SystemExit(f"MoneyPrinterTurbo non raggiungibile su {url} ({e.reason}). "
                         "Avvialo con: docker compose -f integrations/moneyprinter/docker-compose.yml up -d") from None


def check_kokoro() -> None:
    try:
        with urllib.request.urlopen(KOKORO_URL + "/health", timeout=5):
            return
    except Exception:
        raise SystemExit(f"Kokoro non risponde su {KOKORO_URL}: avvialo con "
                         ".venv/bin/python scripts/kokoro_tts_service.py") from None


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera un video con MoneyPrinterTurbo e lo mette da parte per la revisione.")
    ap.add_argument("subject", help="tema del video")
    ap.add_argument("--script-file", help="testo già scritto (altrimenti lo scrive il modello locale)")
    ap.add_argument("--voice", default="kokoro:if_sara", help="voce, es. kokoro:if_sara, kokoro:im_nicola, kokoro:documentarista")
    ap.add_argument("--language", default="it-IT")
    ap.add_argument("--aspect", default="9:16", choices=["9:16", "16:9", "1:1"])
    ap.add_argument("--clip-duration", type=int, default=4)
    ap.add_argument("--paragraphs", type=int, default=1)
    ap.add_argument("--music", default="auto", help="auto | none | nome del file in music/")
    ap.add_argument("--timeout", type=int, default=1800, help="secondi massimi di attesa")
    ap.add_argument("--dry-run", action="store_true", help="mostra la richiesta senza inviarla")
    args = ap.parse_args()

    env = load_env()
    api = env.get("MPT_API_URL", "http://127.0.0.1:8095").rstrip("/")
    key = env.get("MPT_API_KEY", "")
    music = choose_music(args.music, licensed_tracks())
    payload = build_payload(args, music)

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if not key:
        raise SystemExit("Manca MPT_API_KEY: lancia prima integrations/moneyprinter/setup.sh")
    if args.voice.startswith("kokoro:"):
        check_kokoro()

    task_id = (http("POST", f"{api}/api/v1/videos", key, payload).get("data") or {}).get("task_id")
    if not task_id:
        raise SystemExit("MoneyPrinterTurbo non ha restituito un task_id.")
    print(f"Video in preparazione (task {task_id})…", flush=True)

    deadline, last = time.time() + args.timeout, -1
    task = {}
    while time.time() < deadline:
        task = http("GET", f"{api}/api/v1/tasks/{task_id}", key).get("data") or {}
        state, progress = task.get("state"), int(task.get("progress") or 0)
        if progress != last:
            print(f"  {progress}%", flush=True)
            last = progress
        if state == STATE_DONE:
            break
        if state == STATE_FAILED:
            raise SystemExit(f"Generazione fallita: {task.get('error_key') or task.get('error') or 'motivo non indicato'}")
        time.sleep(10)
    else:
        raise SystemExit(f"Tempo scaduto dopo {args.timeout} s; il task {task_id} può essere ancora in corso.")

    finals = sorted((STORAGE_TASKS / task_id).glob("final-*.mp4"))
    if not finals:
        raise SystemExit(f"Task completato ma nessun final-*.mp4 in {STORAGE_TASKS / task_id}.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{time.strftime('%Y%m%d-%H%M')}-{slugify(args.subject)}"
    dest = OUT_DIR / f"{stem}.mp4"
    shutil.copy2(finals[0], dest)
    meta = {
        "tema": args.subject, "task_id": task_id, "voce": args.voice, "formato": args.aspect,
        "testo": task.get("script") or payload["video_script"] or None,
        "musica": music, "fonte_video": "Pexels (licenza Pexels, attribuzione non obbligatoria)",
        "generato_il": time.strftime("%Y-%m-%dT%H:%M:%S"), "da_rivedere": True, "pubblicato": False,
    }
    (OUT_DIR / f"{stem}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Pronto: {dest.relative_to(REPO)} (da rivedere prima di pubblicare)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
