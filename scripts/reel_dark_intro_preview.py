#!/usr/bin/env python3
"""Build a 30-second, very dark pole-dance opening from local media."""
from __future__ import annotations

import argparse
import random
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "integrations" / "tiktok_editor" / "app"
sys.path.insert(0, str(APP))

from autoedit.media import MediaItem  # noqa: E402
from autoedit.person_layers import prepare_person_mask  # noqa: E402
from autoedit.render import (  # noqa: E402
    Segment, build_image_segment, build_video_segment, concat_with_xfade, mux_audio,
)


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photo-dir", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--audio-start", type=float, default=13.7)
    args = parser.parse_args()
    photo = args.photo_dir / "DSCF4973.JPG"
    for path in (photo, args.video, args.audio):
        if not path.is_file():
            parser.error(f"File non trovato: {path}")
    root = args.out.parent / "dark-intro-assets"
    root.mkdir(parents=True, exist_ok=True)
    sources = []
    for name, start, duration, still in (
        ("opening-still", 0, 1, True),
        ("approach-video", 0, 4, False),
        ("stretch-still", 10, 1, True),
        ("stretch-video", 12, 4, False),
    ):
        path = root / (name + (".png" if still else ".mp4"))
        if not path.is_file():
            if still:
                _ffmpeg("-ss", str(start), "-i", str(args.video), "-frames:v", "1", str(path))
            else:
                _ffmpeg("-ss", str(start), "-t", str(duration), "-i", str(args.video),
                        "-an", "-c:v", "libx264", "-preset", "ultrafast", str(path))
        sources.append(path)
    sources.append(photo)
    durations = [8.0, 4.0, 7.0, 4.0, 7.0]
    subject_dims = [0.48, 0.47, 0.46, 0.45, 0.52]
    cache = root / "person-masks"
    segments = []
    for index, (source, duration, subject_dim) in enumerate(zip(sources, durations, subject_dims)):
        print(f"Scena {index + 1}/5: {source.name}, {duration:g}s", flush=True)
        mask = prepare_person_mask(source, cache)
        output = root / f"scene-{index + 1:02d}.mp4"
        pad = 0.35 if index < 4 else 0.0
        common = dict(person_mask=mask, subject_style="none", background_style="moody",
                      background_blur=1.0, background_dim=0.8, subject_dim=subject_dim)
        if source.suffix.lower() == ".mp4":
            build_video_segment(MediaItem(source, "video", duration=4.0, best_start=0),
                                duration, 360, 640, 24, "none", random.Random(index), output,
                                pad=pad, best_start=0, **common)
            item = MediaItem(source, "video", duration=4.0)
        else:
            build_image_segment(MediaItem(source, "image"), duration, 360, 640, 24,
                                "none", random.Random(index), False, output, pad=pad, **common)
            item = MediaItem(source, "image")
        segments.append(Segment(item, duration, "fade", False, person_mask=mask,
                                clip_path=output, render_duration=duration + pad))
    silent = root / "silent-intro.mp4"
    total = concat_with_xfade(segments, 0.35, silent, 24, work_dir=root,
                              target_w=360, target_h=640)
    mux_audio(silent, args.audio, args.out, total, fade_in=0.6, fade_out=0.3,
              audio_offset=args.audio_start, target_duration=30)
    print(f"Anteprima pronta: {args.out}", flush=True)


if __name__ == "__main__":
    main()
