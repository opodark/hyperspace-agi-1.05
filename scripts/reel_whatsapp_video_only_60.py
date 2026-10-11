#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Make a 60-second music video from one vertical WhatsApp clip, with beat stops."""
from __future__ import annotations

import argparse
import os
import random
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
from reel_whatsapp_speedramp_finale import video_info  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
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
        parser.error("La sorgente deve essere il video verticale")
    root = args.out.parent / "whatsapp-video-only-assets"
    root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NUMBA_CACHE_DIR", str(root / ".numba-cache"))
    from autoedit.beats import detect_beats

    beats = detect_beats(args.audio)
    frames = beat_cut_frames(beats, args.audio_start)
    slots = list(zip(frames, frames[1:]))
    finale_start = next(i for i, (a, _) in enumerate(slots) if a >= 50 * FPS)
    stops = [2 if i % 2 == 0 else 0 for i in range(len(slots))]
    speeds = [((0.6 if i % 2 == 0 else 1.35) if i < finale_start
               else (0.8 if (i - finale_start) % 2 == 0 else 3.0))
              for i in range(len(slots))]
    moving_durations = [(b - a - stop) / FPS
                        for (a, b), stop in zip(slots, stops)]
    if min(moving_durations) <= 0:
        parser.error("Un battito è troppo breve per la pausa prevista")
    finale_source = sum(moving_durations[i] * speeds[i]
                        for i in range(finale_start, len(slots)))
    intro_source = sum(moving_durations[i] * speeds[i] for i in range(finale_start))
    intro_scale = (duration - 0.18 - finale_source) / intro_source
    if not 0.5 < intro_scale < 1.5:
        parser.error("Impossibile adattare il video alla griglia musicale")
    speeds[:finale_start] = [speed * intro_scale for speed in speeds[:finale_start]]
    print(f"Solo video: {len(slots)} intervalli, {finale_start} crescendo + "
          f"{len(slots) - finale_start} finale; nessuna foto", flush=True)
    print(f"Sorgente: 0–{duration - 0.18:.2f}s; fermo immagine di due frame "
          "su un battito sì e uno no", flush=True)

    cursor = 0.0
    rendered = []
    mask_cache = root / "person-masks"
    for index, ((start_frame, end_frame), stop_frames, speed, moving_duration) in enumerate(
            zip(slots, stops, speeds, moving_durations)):
        source_duration = moving_duration * speed
        print(f"Battito {index + 1}/{len(slots)}: {speed:.2f}×, "
              f"pausa {stop_frames} frame, sorgente {cursor:.2f}–"
              f"{cursor + source_duration:.2f}s", flush=True)
        source = root / f"source-{index + 1:02d}.mp4"
        ffmpeg("-ss", f"{cursor:.4f}", "-t", f"{source_duration:.4f}",
               "-i", str(args.video), "-an", "-c:v", "libx264",
               "-preset", "ultrafast", str(source))
        cursor += source_duration
        mask = prepare_person_mask(source, mask_cache, fps=8)
        raw = root / f"beat-{index + 1:02d}-raw.mp4"
        finale = index >= finale_start
        build_video_segment(
            MediaItem(source, "video", duration=source_duration, best_start=0),
            moving_duration, W, H, FPS, "none", random.Random(index), raw,
            speed=speed, best_start=0, person_mask=mask,
            subject_style="none", background_style="none",
            background_blur=0.3, background_dim=0.12 if finale else 0.24,
            subject_dim=0.0 if finale else 0.04,
            subject_spot=0.13 if stop_frames else (0.06 if finale else 0.02),
        )
        fixed = root / f"beat-{index + 1:02d}.mp4"
        frame_count = end_frame - start_frame
        # tpad clones the first frame for the musical stop, then moves on.
        ffmpeg("-i", str(raw), "-vf",
               f"fps={FPS},tpad=start_mode=clone:start={stop_frames}:"
               "stop_mode=clone:stop=4,"
               f"trim=end_frame={frame_count},setpts=PTS-STARTPTS",
               "-frames:v", str(frame_count), "-an", "-c:v", "libx264",
               "-preset", "veryfast", str(fixed))
        rendered.append(fixed)

    concat_file = root / "scenes.ffconcat"
    concat_file.write_text("ffconcat version 1.0\n" +
                           "".join(f"file '{path.resolve()}'\n" for path in rendered),
                           encoding="utf-8")
    silent = root / "silent-video-only.mp4"
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
