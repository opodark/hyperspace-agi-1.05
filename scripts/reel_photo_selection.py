#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build a full-song vertical video from an explicit folder of photos."""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageOps

APP = Path(__file__).resolve().parents[1] / "integrations" / "tiktok_editor" / "app"
sys.path.insert(0, str(APP))
from autoedit.media import MediaItem  # noqa: E402
from autoedit.render import build_image_segment  # noqa: E402

FPS = 30
WIDTH, HEIGHT = 540, 960


def run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "ffmpeg failed")[-1200:])


def audio_duration(path: Path) -> float:
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                            capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photo-dir", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--duration", type=float, help="Exact duration in seconds (default: audio)")
    parser.add_argument("--order-file", type=Path, help="JSON array of photo filenames, each once")
    args = parser.parse_args()
    files = sorted(p for p in args.photo_dir.iterdir()
                   if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    if args.order_file:
        names = json.loads(args.order_file.read_text())
        if (not isinstance(names, list) or len(names) != len(files)
                or set(names) != {p.name for p in files}):
            parser.error("L'ordine deve contenere ogni foto esattamente una volta")
        files = [args.photo_dir / name for name in names]
    if not files or not args.audio.is_file():
        parser.error("Servono foto e audio esistenti")
    duration = args.duration or audio_duration(args.audio)
    total_frames = round(duration * FPS)
    if total_frames < len(files):
        parser.error("La durata deve contenere almeno un frame per foto")
    assets = args.out.parent / f"{args.out.stem}-assets"
    assets.mkdir(parents=True, exist_ok=True)
    frames = [total_frames // len(files) + (i < total_frames % len(files))
              for i in range(len(files))]

    def render(index: int, source: Path) -> Path:
        target = assets / f"scene-{index:03d}.mp4"
        if target.is_file():
            return target
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            width, height = image.size
        item = MediaItem(source, "image", width=width, height=height)
        build_image_segment(item, frames[index] / FPS, WIDTH, HEIGHT, FPS,
                            "none", random.Random(4100 + index), index % 2 == 0,
                            target, motion="kenburns", motion_intensity=0.7)
        return target

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(render, i, path): i for i, path in enumerate(files)}
        for future in as_completed(futures):
            future.result()
            print(f"Rendered {len(files) - len(futures) + 1}/{len(files)}", flush=True)
            futures.pop(future)

    manifest = assets / "sources.json"
    manifest.write_text(json.dumps({"photo_dir": str(args.photo_dir), "duration": duration,
                                    "fps": FPS, "images": [str(p) for p in files]},
                                   indent=2) + "\n")
    concat_file = assets / "concat.txt"
    concat_file.write_text("".join(f"file '{(assets / f'scene-{i:03d}.mp4').resolve()}'\n"
                                   for i in range(len(files))))
    silent = assets / "silent.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat",
         "-safe", "0", "-i", str(concat_file), "-c", "copy", str(silent)])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(silent),
         "-i", str(args.audio), "-vf", "scale=1080:1920:flags=lanczos,fps=30",
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "medium",
         "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
         "-t", f"{duration:.3f}", "-movflags", "+faststart", str(args.out)])
    print(f"Ready: {args.out} ({len(files)} photos, {duration:.3f}s)", flush=True)


if __name__ == "__main__":
    main()
