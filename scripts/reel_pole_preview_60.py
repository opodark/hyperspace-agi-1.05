#!/usr/bin/env python3
"""Render a 60-second portrait pole preview with many stills and video excerpts."""
from __future__ import annotations

import argparse
import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageOps

APP = Path(__file__).resolve().parents[1] / "integrations" / "tiktok_editor" / "app"
sys.path.insert(0, str(APP))

from autoedit.media import MediaItem  # noqa: E402
from autoedit.person_layers import prepare_person_mask  # noqa: E402
from autoedit.render import (  # noqa: E402
    Segment, build_image_segment, build_video_segment, concat_with_xfade, mux_audio,
)

PHOTO_IDS = [5001, 4997, 4994, 4992, 4984, 4986, 4988, 4989, 4990, 4999]
VIDEO_STARTS = [0, 4, 8, 12, 16, 20, 24, 28, 32]


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def _portrait_photo(source: Path, target: Path) -> None:
    if target.is_file():
        return
    with Image.open(source) as image:
        upright = ImageOps.exif_transpose(image).convert("RGB")
        if upright.height <= upright.width:
            raise ValueError(f"Foto non verticale: {source.name}")
        upright.save(target, "PNG")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photo-dir", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--audio-start", type=float, default=13.7)
    args = parser.parse_args()
    for path in [args.video, args.audio, *(args.photo_dir / f"DSCF{i}.JPG" for i in PHOTO_IDS)]:
        if not path.is_file():
            parser.error(f"File non trovato: {path}")
    root = args.out.parent / "pole-preview-60-assets"
    root.mkdir(parents=True, exist_ok=True)
    photo_paths = []
    for ident in PHOTO_IDS:
        target = root / f"DSCF{ident}-vertical.png"
        _portrait_photo(args.photo_dir / f"DSCF{ident}.JPG", target)
        photo_paths.append(target)
    video_paths = []
    for start in VIDEO_STARTS:
        target = root / f"video-{start:02d}-{start + 4:02d}.mp4"
        if not target.is_file():
            _ffmpeg("-ss", str(start), "-t", "4", "-i", str(args.video),
                    "-an", "-c:v", "libx264", "-preset", "ultrafast", str(target))
        video_paths.append(target)

    storyboard = []
    for index, photo in enumerate(photo_paths):
        storyboard.append((photo, 5.0 if index == 0 else 19.0 / 9.0))
        if index < len(video_paths):
            storyboard.append((video_paths[index], 4.0))
    assert len(storyboard) == 19 and abs(sum(d for _, d in storyboard) - 60) < 1e-6

    mask_cache = root / "person-masks"
    segments = []
    for index, (source, duration) in enumerate(storyboard):
        print(f"Scena {index + 1}/19: {source.name}, {duration:.2f}s", flush=True)
        mask = prepare_person_mask(source, mask_cache)
        output = root / f"scene-{index + 1:02d}.mp4"
        pad = 0.2 if index < len(storyboard) - 1 else 0.0
        progress = index / (len(storyboard) - 1)
        common = dict(person_mask=mask, subject_style="none", background_style="moody",
                      background_blur=1.0, background_dim=0.8,
                      subject_dim=0.48 - 0.15 * progress)
        if source.suffix == ".mp4":
            build_video_segment(MediaItem(source, "video", duration=4, best_start=0),
                                duration, 360, 640, 24, "none", random.Random(index), output,
                                pad=pad, best_start=0, **common)
            item = MediaItem(source, "video", duration=4)
        else:
            build_image_segment(MediaItem(source, "image"), duration, 360, 640, 24,
                                "none", random.Random(index), False, output, pad=pad, **common)
            item = MediaItem(source, "image")
        segments.append(Segment(item, duration, "fade", False, person_mask=mask,
                                clip_path=output, render_duration=duration + pad))

    silent = root / "silent-60.mp4"
    total = concat_with_xfade(segments, 0.2, silent, 24, work_dir=root,
                              chunk_size=5, target_w=360, target_h=640)
    print(f"Video montato: {total:.2f}s; aggiungo l'audio...", flush=True)
    mux_audio(silent, args.audio, args.out, total, fade_in=0.6, fade_out=0.3,
              audio_offset=args.audio_start, target_duration=60)
    print(f"Anteprima pronta: {args.out}", flush=True)


if __name__ == "__main__":
    main()
