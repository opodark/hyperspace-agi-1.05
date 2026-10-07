#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Add beat-synced subject zoom, silhouette light and short electric arcs.

Runs on macOS because foreground masks use Apple Vision. The video and audio
are local; the output is an MP4 for review, with optional karaoke alpha layer.
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

REPO = Path(__file__).resolve().parents[1]
EDITOR = REPO / "integrations" / "tiktok_editor" / "app"
HELPER_SOURCE = Path(__file__).with_name("reel_foreground_mask.swift")
W, H, FPS = 360, 640, 30


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "command failed")[-1600:])


def beats(audio: Path) -> list[float]:
    sys.path.insert(0, str(EDITOR))
    from autoedit.beats import detect_beats
    info = detect_beats(audio)
    pulses = [float(t) for t in info.downbeat_times if 1.0 < float(t) < info.duration - 1.0]
    return pulses


def helper_binary(assets: Path) -> Path:
    binary = assets / "foreground_mask"
    if not binary.is_file() or binary.stat().st_mtime < HELPER_SOURCE.stat().st_mtime:
        cmd = ["swiftc"]
        sdk = Path("/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk")
        if sdk.is_dir():
            cmd += ["-sdk", str(sdk)]
        run(cmd + [str(HELPER_SOURCE), "-o", str(binary)])
    return binary


def sample_frames(video: Path, pulses: list[float], assets: Path) -> list[tuple[float, Path, Path]]:
    frames, masks = assets / "frames", assets / "masks"
    frames.mkdir(parents=True, exist_ok=True)
    masks.mkdir(parents=True, exist_ok=True)
    pairs = []
    for index, t in enumerate(pulses):
        frame = frames / f"pulse-{index:03}.png"
        mask = masks / f"pulse-{index:03}.png"
        if not frame.is_file():
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.3f}",
                 "-i", str(video), "-frames:v", "1", "-vf", f"scale={W}:{H}", str(frame)])
        pairs.append((t, frame, mask))
    return pairs


def make_masks(pairs: list[tuple[float, Path, Path]], helper: Path) -> None:
    pending = [(frame, mask) for _, frame, mask in pairs if not mask.is_file()]
    for offset in range(0, len(pending), 12):
        batch = pending[offset:offset + 12]
        args = [str(value) for pair in batch for value in pair]
        result = subprocess.run([str(helper), *args], capture_output=True, text=True)
        if result.returncode:
            # One difficult frame must not discard the other mask candidates.
            for frame, mask in batch:
                subprocess.run([str(helper), str(frame), str(mask)],
                               capture_output=True, text=True)


def usable_mask(path: Path) -> Image.Image | None:
    if not path.is_file():
        return None
    mask = Image.open(path).convert("L")
    if mask.size != (W, H):
        mask = mask.resize((W, H), Image.Resampling.BILINEAR)
    binary = mask.point(lambda v: 255 if v >= 128 else 0)
    box = binary.getbbox()
    if box is None:
        return None
    area = sum(binary.histogram()[128:]) / (W * H)
    if area < 0.07 or area > 0.74 or box[2] - box[0] < 75 or box[3] - box[1] < 170:
        return None
    if box[0] <= 2 and box[2] >= W - 2 and area > 0.38:
        # Usually the foreground request has swallowed furniture/background.
        return None
    return mask


def electric_layer(mask: Image.Image, seed: int) -> Image.Image:
    rng = random.Random(seed)
    binary = mask.point(lambda v: 255 if v >= 128 else 0)
    outline = ImageChops.subtract(binary.filter(ImageFilter.MaxFilter(9)), binary)
    outer = outline.filter(ImageFilter.GaussianBlur(7))
    glow = Image.new("RGBA", (W, H), (71, 226, 255, 0))
    glow.putalpha(outer.point(lambda v: min(155, round(v * .62))))
    line = Image.new("RGBA", (W, H), (154, 245, 255, 0))
    line.putalpha(outline.point(lambda v: min(210, round(v * .70))))
    result = Image.alpha_composite(glow, line)
    arcs = Image.new("L", (W, H))
    draw = ImageDraw.Draw(arcs)
    pixels = binary.load()
    box = binary.getbbox()
    assert box is not None
    for side in ("left", "right"):
        for _ in range(2):
            middle = rng.randint(max(20, box[1] + 20), min(H - 25, box[3] - 20))
            points = []
            for step in range(7):
                y = min(H - 2, max(1, middle - 30 + step * 10))
                xs = [x for x in range(W) if pixels[x, y] > 0]
                if not xs:
                    continue
                edge = min(xs) if side == "left" else max(xs)
                x = max(2, min(W - 3, edge + (-1 if side == "left" else 1) * rng.randint(11, 24)))
                points.append((x, y))
            if len(points) >= 2:
                draw.line(points, fill=245, width=2)
                for branch in (2, 4):
                    if branch < len(points):
                        bx, by = points[branch]
                        tip = (max(2, min(W - 3, bx + (-14 if side == "left" else 14))), by - 10)
                        draw.line(((bx, by), tip), fill=220, width=1)
    halo = arcs.filter(ImageFilter.GaussianBlur(6))
    arc_light = Image.new("RGBA", (W, H), (96, 202, 255, 0))
    arc_light.putalpha(halo.point(lambda v: min(180, v)))
    core = Image.new("RGBA", (W, H), (225, 252, 255, 0))
    core.putalpha(arcs)
    return Image.alpha_composite(Image.alpha_composite(result, arc_light), core)


def effect_frame(source: Image.Image, mask: Image.Image, lightning: Image.Image,
                 age: int) -> Image.Image:
    # A short dark pulse separates the enlarged person from the original frame.
    alpha = [76, 66, 52, 37, 24, 9][age]
    canvas = Image.new("RGBA", (W, H), (6, 9, 19, alpha))
    zoom = [1.07, 1.16, 1.14, 1.10, 1.05, 1.01][age]
    box = mask.point(lambda v: 255 if v >= 128 else 0).getbbox()
    assert box is not None
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    subject = source.copy().convert("RGBA")
    subject.putalpha(mask.filter(ImageFilter.GaussianBlur(1.2)))
    subject = subject.resize((round(W * zoom), round(H * zoom)), Image.Resampling.BICUBIC)
    x, y = round(cx - cx * zoom), round(cy - cy * zoom)
    canvas.alpha_composite(subject, (x, y))
    if age < 4:
        lit = lightning.copy()
        fade = [1.0, .85, .56, .26][age]
        lit.putalpha(lit.getchannel("A").point(lambda v: round(v * fade)))
        lit = lit.resize((round(W * zoom), round(H * zoom)), Image.Resampling.BICUBIC)
        canvas.alpha_composite(lit, (x, y))
    return canvas


def ambient_flash() -> Image.Image:
    """A restrained edge flash for beats where Vision cannot isolate Anna."""
    strokes = Image.new("RGBA", (W, H))
    draw = ImageDraw.Draw(strokes)
    draw.line([(0, 80), (22, 120), (8, 156), (35, 200)],
              fill=(151, 236, 255, 125), width=3)
    draw.line([(W - 1, 360), (W - 24, 401), (W - 8, 430), (W - 34, 476)],
              fill=(151, 236, 255, 125), width=3)
    halo = strokes.filter(ImageFilter.GaussianBlur(15))
    halo.putalpha(halo.getchannel("A").point(lambda value: min(95, value * 2)))
    return Image.alpha_composite(halo, strokes)


def alpha_video(pairs: list[tuple[float, Path, Path]], target: Path, duration: float) -> dict:
    prepared = {}
    ambient = set()
    for index, (time, frame_path, mask_path) in enumerate(pairs):
        mask = usable_mask(mask_path)
        if mask is None:
            ambient.add(round(time * FPS))
            continue
        source = Image.open(frame_path).convert("RGB")
        prepared[round(time * FPS)] = (source, mask, electric_layer(mask, 8100 + index))
    process = subprocess.Popen([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
        "-pix_fmt", "rgba", "-s:v", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0",
        "-an", "-c:v", "qtrle", "-pix_fmt", "argb", str(target),
    ], stdin=subprocess.PIPE)
    assert process.stdin is not None
    blank = Image.new("RGBA", (W, H)).tobytes()
    edge_flash = ambient_flash().tobytes()
    active_start = -10
    try:
        for frame in range(round(duration * FPS)):
            if frame in prepared:
                active_start = frame
            age = frame - active_start
            if 0 <= age < 6 and active_start in prepared:
                source, mask, lightning = prepared[active_start]
                process.stdin.write(effect_frame(source, mask, lightning, age).tobytes())
            elif frame in ambient:
                process.stdin.write(edge_flash)
            else:
                process.stdin.write(blank)
    finally:
        process.stdin.close()
    if process.wait():
        raise RuntimeError("Could not encode subject FX alpha video")
    return {"pulses": len(pairs), "subject_pulses": len(prepared),
            "ambient_pulses": len(ambient), "rejected_masks": len(ambient)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--karaoke-alpha", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--assets", type=Path)
    parser.add_argument("--pulses", type=Path, help="JSON list of beat times for repeatable runs")
    parser.add_argument("--duration", type=float, default=111.2)
    args = parser.parse_args()
    assets = args.assets or args.out.parent / (args.out.stem + "-assets")
    assets.mkdir(parents=True, exist_ok=True)
    pulse_times = json.loads(args.pulses.read_text()) if args.pulses else beats(args.audio)
    pulse_times = [float(t) for t in pulse_times if 0 <= float(t) < args.duration - .2]
    print(f"Preparing {len(pulse_times)} beat frames", flush=True)
    pairs = sample_frames(args.video, pulse_times, assets)
    make_masks(pairs, helper_binary(assets))
    alpha = assets / "subject-fx-alpha.mov"
    stats = alpha_video(pairs, alpha, args.duration)
    (assets / "result.json").write_text(json.dumps(stats, indent=2) + "\n")
    print(stats, flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(args.video),
               "-i", str(alpha)]
    graph = ("[1:v]scale=1080:1920:flags=lanczos[fx];"
             "[0:v][fx]overlay=0:0:eof_action=pass[lit]")
    output = "[lit]"
    if args.karaoke_alpha:
        command += ["-i", str(args.karaoke_alpha)]
        graph += (";[2:v]scale=1080:1920:flags=lanczos[lyrics];"
                  "[lit][lyrics]overlay=0:0:eof_action=pass[v]")
        output = "[v]"
    command += ["-filter_complex", graph, "-map", output, "-map", "0:a:0",
                "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
                str(args.out)]
    run(command)


if __name__ == "__main__":
    main()
