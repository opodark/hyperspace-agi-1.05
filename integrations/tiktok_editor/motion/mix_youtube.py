#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Unisce a un reel la voce a capitoli e, se c'è, un brano di sottofondo: video + audio in un MP4.

Le voci e i loro istanti d'inizio stanno nella riga `// @meta` del reel (chiave "voice": [{"file", "at"}]),
così il montaggio audio ha una sola fonte di verità. La musica NON è nel reel: si passa a parte.

    python3 mix_youtube.py youtube-presentazione-2026-10-30 --music brano.mp3 --music-license "CC0, https://…"
    python3 mix_youtube.py youtube-presentazione-2026-10-30                  # solo voce
    python3 mix_youtube.py youtube-presentazione-2026-10-30 --music brano.mp3 --draft   # bozza locale

Regola del progetto: nei video da pubblicare vanno solo brani con licenza chiara e registrati in
`integrations/moneyprinter/music/licenze.json`; senza `--music-license` e senza `--draft` lo script si
rifiuta di mixare musica. Con `--draft` il file esce con il suffisso `-BOZZA-NON-PUBBLICARE`.
Il brano sta sotto la voce: abbassato (default −20 dB) e, mentre parla qualcuno, ulteriormente
ridotto (sidechain) perché la voce resti sempre in primo piano.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
META_RE = re.compile(r"^// @meta (\{.*\})\s*$", re.M)


def read_meta(reel_id: str) -> dict:
    js = (HERE / "reels" / f"{reel_id}.js").read_text(encoding="utf-8")
    m = META_RE.search(js)
    if not m:
        raise SystemExit(f"reels/{reel_id}.js: manca la riga `// @meta`")
    return json.loads(m.group(1))


def build_command(video: Path, out: Path, meta: dict, music: Path | None, music_db: float) -> list[str]:
    dur = float(meta["dur"])
    voices = meta.get("voice") or []
    if not voices:
        raise SystemExit("il reel non dichiara voci (@meta \"voice\")")
    inputs, filters, labels = ["-i", str(video)], [], []
    for i, v in enumerate(voices, start=1):
        f = (REPO / v["file"]).resolve()
        if REPO not in f.parents or not f.is_file():
            raise SystemExit(f"voce non trovata nel repository: {v['file']}")
        inputs += ["-i", str(f)]
        ms = int(round(float(v["at"]) * 1000))
        filters.append(f"[{i}:a]aresample=48000,adelay={ms}|{ms}[v{i}]")
        labels.append(f"[v{i}]")
    n = len(voices)
    filters.append("".join(labels) + f"amix=inputs={n}:normalize=0:dropout_transition=0,volume=1.0,apad=whole_dur={dur}[voce]")
    if music:
        mi = n + 1
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        filters.append(f"[{mi}:a]aresample=48000,volume={music_db}dB,atrim=0:{dur},afade=t=in:st=0:d=3,afade=t=out:st={dur - 4}:d=4[mus]")
        filters.append("[voce]asplit=2[vo][sc]")
        filters.append("[mus][sc]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=600[duck]")
        filters.append("[vo][duck]amix=inputs=2:normalize=0[mix]")
        amap = "[mix]"
    else:
        amap = "[voce]"
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(filters),
            "-map", "0:v", "-map", amap, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", str(dur), "-movflags", "+faststart", str(out)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reel_id")
    ap.add_argument("--video", help="MP4 del reel (default: data/reel-projects/motion/<id>/<id>[-16x9].mp4)")
    ap.add_argument("--music", help="brano di sottofondo")
    ap.add_argument("--music-license", help="licenza e fonte del brano (obbligatoria per un video da pubblicare)")
    ap.add_argument("--music-db", type=float, default=-20.0, help="livello del brano in dB (default −20)")
    ap.add_argument("--draft", action="store_true", help="bozza locale: ammette un brano senza licenza, esce marcata come da non pubblicare")
    ap.add_argument("-o", "--output", help="file di uscita")
    a = ap.parse_args()

    meta = read_meta(a.reel_id)
    out_dir = REPO / "data" / "reel-projects" / "motion" / a.reel_id
    video = Path(a.video) if a.video else next((p for p in (out_dir / f"{a.reel_id}.mp4", out_dir / f"{a.reel_id}-16x9.mp4") if p.exists()), None)
    if not video or not video.exists():
        raise SystemExit("MP4 del reel non trovato: rendilo con build.py --render")
    music = Path(a.music).expanduser() if a.music else None
    if music and not music.is_file():
        raise SystemExit(f"brano non trovato: {music}")
    if music and not a.music_license and not a.draft:
        raise SystemExit("brano senza licenza dichiarata: passa --music-license \"licenza, fonte\" (e registralo in "
                         "integrations/moneyprinter/music/licenze.json), oppure usa --draft per una bozza non pubblicabile")
    name = a.reel_id + ("-BOZZA-NON-PUBBLICARE" if music and a.draft and not a.music_license else "") + "-con-audio.mp4"
    out = Path(a.output) if a.output else REPO / "data" / "reels" / "youtube" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(build_command(video, out, meta, music, a.music_db), check=True)
    note = {"reel": a.reel_id, "voci": [v["file"] for v in meta["voice"]], "musica": str(music) if music else None,
            "licenza_musica": a.music_license, "bozza": bool(music and a.draft and not a.music_license), "da_rivedere": True}
    out.with_suffix(".json").write_text(json.dumps(note, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
