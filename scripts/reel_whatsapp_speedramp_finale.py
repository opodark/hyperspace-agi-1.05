#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replace the last 10s of the WhatsApp heartbeat reel with rhythmic video speed ramps."""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "integrations" / "tiktok_editor" / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from autoedit.media import MediaItem  # noqa: E402
from autoedit.overlays import render_cross_light_png  # noqa: E402
from autoedit.person_layers import prepare_person_mask  # noqa: E402
from autoedit.render import build_video_segment  # noqa: E402
from reel_whatsapp_heartbeat_60 import W, H, FPS, beat_cut_frames, ffmpeg  # noqa: E402


def video_info(path: Path) -> tuple[float, int, int]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-show_entries", "stream=width,height", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    info = json.loads(result.stdout)
    stream = next(s for s in info["streams"] if s.get("width"))
    return float(info["format"]["duration"]), int(stream["width"]), int(stream["height"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True,
                        help="Asset del reel WhatsApp già renderizzato; servono le prime 56 scene")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--audio-start", type=float, default=73.7)
    args = parser.parse_args()
    for path in (args.video, args.audio):
        if not path.is_file():
            parser.error(f"File non trovato: {path}")
    duration, width, height = video_info(args.video)
    if width >= height:
        parser.error("Il finale richiede il video verticale")
    root = args.out.parent / "whatsapp-speedramp-assets"
    root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NUMBA_CACHE_DIR", str(root / ".numba-cache"))
    from autoedit.beats import detect_beats

    beats = detect_beats(args.audio)
    frames = beat_cut_frames(beats, args.audio_start)
    first_finale = next(i for i, frame in enumerate(frames[:-1]) if frame >= 50 * FPS)
    intro = [args.assets / f"scene-{i + 1:02d}.mp4" for i in range(first_finale)]
    for path in intro:
        if not path.is_file():
            parser.error(f"Manca la scena già renderizzata: {path}")
    finale_slots = [(frames[i], frames[i + 1]) for i in range(first_finale, len(frames) - 1)]
    # Slow and fast states alternate at each musical beat. All source spans
    # follow each other, so this remains one continuous performance.
    speeds = [0.8 if i % 2 == 0 else 3.0 for i in range(len(finale_slots))]
    source_needed = sum((b - a) / FPS * speed for (a, b), speed in zip(finale_slots, speeds))
    cursor = duration - 0.18 - source_needed
    if cursor < 0:
        parser.error("Il video non è abbastanza lungo per la sequenza di velocità")
    print(f"Finale: {len(finale_slots)} battiti, sorgente {cursor:.2f}–"
          f"{cursor + source_needed:.2f}s; velocità alternate 0,8× e 3×", flush=True)

    rendered = list(intro)
    mask_cache = root / "person-masks"
    for index, ((start_frame, end_frame), speed) in enumerate(zip(finale_slots, speeds)):
        output_duration = (end_frame - start_frame) / FPS
        source_duration = output_duration * speed
        print(f"Battito {index + 1}/{len(finale_slots)}: {speed:g}×, "
              f"sorgente {cursor:.2f}–{cursor + source_duration:.2f}s", flush=True)
        source = root / f"source-{index + 1:02d}.mp4"
        ffmpeg("-ss", f"{cursor:.4f}", "-t", f"{source_duration:.4f}",
               "-i", str(args.video), "-an", "-c:v", "libx264",
               "-preset", "ultrafast", str(source))
        cursor += source_duration
        mask = prepare_person_mask(source, mask_cache, fps=8)
        raw = root / f"beat-{index + 1:02d}-raw.mp4"
        # Masked lighting stays tied to the body; no illustrated bolts.
        build_video_segment(
            MediaItem(source, "video", duration=source_duration, best_start=0),
            output_duration, W, H, FPS, "none", random.Random(index), raw,
            speed=speed, best_start=0, person_mask=mask,
            subject_style="none", background_style="none",
            background_blur=0.3, background_dim=0.12,
            subject_dim=0.0, subject_spot=0.13 if speed == 0.8 else 0.04,
        )
        fixed = root / f"beat-{index + 1:02d}.mp4"
        frame_count = end_frame - start_frame
        ffmpeg("-i", str(raw), "-vf",
               f"fps={FPS},tpad=stop_mode=clone:stop_duration=0.25,"
               f"trim=end_frame={frame_count},setpts=PTS-STARTPTS",
               "-frames:v", str(frame_count), "-an", "-c:v", "libx264",
               "-preset", "veryfast", str(fixed))
        rendered.append(fixed)

    concat_file = root / "scenes.ffconcat"
    concat_file.write_text("ffconcat version 1.0\n" +
                           "".join(f"file '{path.resolve()}'\n" for path in rendered),
                           encoding="utf-8")
    silent = root / "silent-speedramp.mp4"
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(concat_file),
           "-an", "-c", "copy", str(silent))
    with_audio = root / "with-audio.mp4"
    ffmpeg("-i", str(silent), "-ss", f"{args.audio_start:.3f}", "-i", str(args.audio),
           "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-af",
           "afade=t=in:st=0:d=0.25,afade=t=out:st=59.75:d=0.25",
           "-t", "60", str(with_audio))
    cross = root / "cross-light.png"
    render_cross_light_png(W, H, cross)
    pulses = [float(t) - args.audio_start for t in beats.beat_times
              if args.audio_start + 50 <= float(t) < args.audio_start + 60]
    enabled = "+".join(f"between(t,{t:.3f},{t + 0.08:.3f})" for t in pulses)
    graph = ("[1:v]format=rgba,colorchannelmixer=aa=0.7[cross];"
             f"[0:v][cross]overlay=0:0:enable='{enabled}':eof_action=pass[v]")
    ffmpeg("-i", str(with_audio), "-loop", "1", "-i", str(cross),
           "-filter_complex", graph, "-map", "[v]", "-map", "0:a",
           "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
           "-c:a", "copy", "-t", "60", str(args.out))
    print(f"Anteprima pronta: {args.out}", flush=True)


if __name__ == "__main__":
    main()
