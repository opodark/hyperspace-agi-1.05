#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Add a beat-synced cross eruption and whole-frame strobes to the clean S24 reel."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reel_s24_heartbeat_60fps import silhouette_mask  # noqa: E402

W, H = 1080, 1920


def run(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def cross_png(path: Path) -> None:
    shape = Image.new("L", (W, H), 0)
    draw = ImageDraw.Draw(shape)
    cx = W // 2
    draw.rectangle((cx - 32, 170, cx + 32, 1450), fill=255)
    draw.rectangle((145, 600, W - 145, 680), fill=255)
    broad = shape.filter(ImageFilter.GaussianBlur(145)).point(
        lambda value: round(value * 0.75))
    near = shape.filter(ImageFilter.GaussianBlur(48)).point(
        lambda value: round(value * 0.65))
    core = shape.filter(ImageFilter.GaussianBlur(16)).point(
        lambda value: round(value * 0.42))
    alpha = ImageChops.add(ImageChops.add(broad, near), core)
    image = Image.new("RGBA", (W, H), (255, 247, 235, 0))
    image.putalpha(alpha)
    image.save(path)


def pulse_expression(times: list[float], width: float) -> str:
    return "+".join(f"between(t,{time:.3f},{time + width:.3f})" for time in times)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--timeline", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not args.video.is_file() or not args.timeline.is_file():
        parser.error("Video o timeline mancante")
    root = args.out.parent / "s24-cross-strobe-assets"
    root.mkdir(parents=True, exist_ok=True)
    timeline = json.loads(args.timeline.read_text(encoding="utf-8"))
    beats = [float(item["output_start"]) for item in timeline
             if 50 <= float(item["output_start"]) < 60]
    if not beats or beats[0] != 50.0:
        parser.error("Timeline senza finale al secondo 50")

    finale = root / "finale-360-for-mask.mp4"
    run("-ss", "50", "-i", str(args.video), "-t", "10", "-an",
        "-vf", "scale=360:640:flags=lanczos,fps=12", "-c:v", "libx264",
        "-preset", "veryfast", str(finale))
    finale_mask = root / "finale-silhouette-mask.mkv"
    silhouette_mask(finale, finale_mask)
    full_mask = root / "full-person-mask.mkv"
    run("-f", "lavfi", "-i", "color=black:s=360x640:r=12:d=50",
        "-i", str(finale_mask), "-filter_complex",
        "[0:v]format=gray[blank];[1:v]format=gray[person];"
        "[blank][person]concat=n=2:v=1:a=0,format=gray[m]",
        "-map", "[m]", "-c:v", "ffv1", str(full_mask))

    cross = root / "cross-eruption.png"
    cross_png(cross)
    cross_times = beats
    regular = beats[1:]
    doubles = [(beats[i] + beats[i + 1]) / 2 for i in range(len(beats) - 1)
               if beats[i] >= 57]
    cross_enable = pulse_expression(cross_times, 0.19)
    beat_enable = pulse_expression(regular, 0.075)
    double_enable = pulse_expression(doubles, 0.055)
    graph = (
        "[0:v]split[person_original][background];"
        f"[background][1:v]overlay=0:0:enable='{cross_enable}':"
        "eof_action=pass,format=gbrp[lit];"
        "[person_original]format=gbrp[original];"
        f"[2:v]scale={W}:{H}:flags=bicubic,format=gray,format=gbrp[mask];"
        "[lit][original][mask]maskedmerge,format=yuv420p[backlit];"
        "[3:v]format=rgba,colorchannelmixer=aa=0.88[blast];"
        "[backlit][blast]overlay=0:0:enable='between(t,50.000,50.105)':"
        "eof_action=pass[burst];"
        "[4:v]format=rgba,colorchannelmixer=aa=0.52[whitebeat];"
        f"[burst][whitebeat]overlay=0:0:enable='{beat_enable}':"
        "eof_action=pass[strobed];"
        "[5:v]format=rgba,colorchannelmixer=aa=0.42[whitehalf];"
        f"[strobed][whitehalf]overlay=0:0:enable='{double_enable}':"
        "eof_action=pass,format=yuv420p[v]"
    )
    run("-i", str(args.video), "-loop", "1", "-i", str(cross),
        "-i", str(full_mask),
        "-f", "lavfi", "-i", f"color=white:s={W}x{H}:r=60:d=60",
        "-f", "lavfi", "-i", f"color=white:s={W}x{H}:r=60:d=60",
        "-f", "lavfi", "-i", f"color=white:s={W}x{H}:r=60:d=60",
        "-filter_complex", graph, "-map", "[v]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
        "-pix_fmt", "yuv420p", "-c:a", "copy", "-t", "60", str(args.out))
    print(f"Finale strobo: {args.out}", flush=True)


if __name__ == "__main__":
    main()
