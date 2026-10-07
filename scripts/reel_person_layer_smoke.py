#!/usr/bin/env python3
"""Render a five-second local preview of person/background grading."""
from __future__ import annotations

import argparse
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "integrations" / "tiktok_editor" / "app"
sys.path.insert(0, str(APP))

from autoedit.media import MediaItem  # noqa: E402
from autoedit.overlays import render_cross_light_png  # noqa: E402
from autoedit.person_layers import prepare_person_mask  # noqa: E402
from autoedit.render import Segment, concat_with_xfade, mux_audio, render_segments  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--video-start", type=float, default=3.0)
    parser.add_argument("--audio-start", type=float, default=123.7)
    args = parser.parse_args()
    for path in (args.image, args.video, args.audio):
        if not path.is_file():
            parser.error(f"File non trovato: {path}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NUMBA_CACHE_DIR", str(args.out.parent / ".numba-cache"))
    from autoedit.beats import detect_beats

    beat_info = detect_beats(args.audio)
    pulses = [float(t) - args.audio_start for t in beat_info.beat_times
              if args.audio_start + 3 <= float(t) < args.audio_start + 5]
    print("Lampi sui beat:", ", ".join(f"{t:.2f}s" for t in pulses), flush=True)
    clip = args.out.parent / f"pole-source-{round(args.video_start * 10):04d}-3s.mp4"
    if not clip.is_file():
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(args.video_start),
                        "-t", "3", "-i", str(args.video), "-an", "-c:v", "libx264",
                        "-preset", "ultrafast", str(clip)], check=True)
    cache = args.out.parent / "person-masks"
    print("Preparo la maschera della foto...", flush=True)
    image_mask = prepare_person_mask(args.image, cache)
    print("Preparo la maschera del video...", flush=True)
    video_mask = prepare_person_mask(clip, cache)
    with tempfile.TemporaryDirectory(prefix="reel_smoke_", dir=args.out.parent) as tmp:
        work = Path(tmp)
        segments = [
            Segment(MediaItem(clip, "video", duration=3.0, best_start=0), 3.0,
                    "fade", False, person_mask=video_mask),
            Segment(MediaItem(args.image, "image"), 2.0, "fade", False,
                    person_mask=image_mask),
        ]
        print("Renderizzo i due livelli...", flush=True)
        render_segments(segments, 360, 640, 24, "vivid", random.Random(3), work,
                        jobs=2, xfade_duration=0, subject_style="warm",
                        background_style="moody", background_blur=1.5,
                        background_dim=0.62, subject_spot=0.02)
        silent = work / "silent.mp4"
        duration = concat_with_xfade(segments, 0, silent, 24, target_w=360, target_h=640)
        cross = work / "cross-light.png"
        render_cross_light_png(360, 640, cross)
        mux_audio(silent, args.audio, args.out, duration, fade_in=0.1,
                  fade_out=0.2, audio_offset=args.audio_start,
                  overlays=[{"png": cross, "x": 0, "y": 0,
                             "pulse_times": pulses or [3.0, 3.5, 4.0, 4.5],
                             "pulse_width": 0.11}])
    print(f"Anteprima pronta: {args.out}", flush=True)


if __name__ == "__main__":
    main()
