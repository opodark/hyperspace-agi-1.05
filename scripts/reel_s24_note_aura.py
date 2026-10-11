#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Render subtle performer-following note lights in two experimental styles."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import (binary_closing, binary_dilation, binary_opening,
                           distance_transform_edt, gaussian_filter)

W, H, MASK_FPS = 360, 640, 12


def run(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def extract_frames(video: Path, raw: Path) -> np.memmap:
    run("-i", str(video), "-t", "50", "-vf",
        f"fps={MASK_FPS},scale={W}:{H}:flags=lanczos",
        "-an", "-pix_fmt", "rgb24", "-f", "rawvideo", str(raw))
    frame_bytes = W * H * 3
    count = raw.stat().st_size // frame_bytes
    if count != 50 * MASK_FPS:
        raise ValueError(f"Attesi 600 fotogrammi della preparazione, trovati {count}")
    return np.memmap(raw, dtype=np.uint8, mode="r", shape=(count, H, W, 3))


def alpha_layer(mask: np.ndarray, color: tuple[int, int, int],
                intensity: float) -> np.ndarray:
    layer = np.zeros((H, W, 4), dtype=np.uint8)
    layer[:, :, :3] = color
    layer[:, :, 3] = np.uint8(np.clip(mask * intensity, 0, 255))
    return layer


def halo_frame(frame: np.ndarray, plate: np.ndarray, focus: np.ndarray,
               pulse: float) -> np.ndarray:
    rgb = frame.astype(np.int16)
    difference = np.max(np.abs(rgb - plate), axis=2)
    darker = plate[:, :, 2] - rgb[:, :, 2]
    person = focus & (((darker > 14) & (rgb[:, :, 2] < 135)) |
                      ((difference > 42) & (rgb[:, :, 2] < 155)))
    led = focus & (((rgb[:, :, 0] > 58) &
                    (rgb[:, :, 0] > rgb[:, :, 1] * 1.55) &
                    (rgb[:, :, 0] > rgb[:, :, 2] * 0.70)) |
                   ((rgb[:, :, 1] > 47) &
                    (rgb[:, :, 1] > rgb[:, :, 0] * 1.45) &
                    (rgb[:, :, 1] > rgb[:, :, 2] * 0.55)))
    if np.count_nonzero(led) > 12:
        person &= distance_transform_edt(~led) < 70
    person = binary_closing(binary_opening(person, iterations=1), iterations=2)
    outer = gaussian_filter(binary_dilation(person, iterations=8).astype(np.float32), 7)
    inner = gaussian_filter(person.astype(np.float32), 3)
    rim = np.maximum(0, outer - inner * 0.92)
    broad = gaussian_filter(binary_dilation(person, iterations=15).astype(np.float32), 14)
    return alpha_layer(np.clip(rim * 0.95 + broad * 0.12, 0, 1) * 255,
                       (255, 211, 155), 0.17 + 0.29 * pulse)


def neon_frame(frame: np.ndarray, focus: np.ndarray, pulse: float,
               history: list[tuple[np.ndarray, np.ndarray]], style: str) -> np.ndarray:
    rgb = frame.astype(np.float32)
    red = focus & (rgb[:, :, 0] > 58) & (rgb[:, :, 0] > rgb[:, :, 1] * 1.55) & (
        rgb[:, :, 0] > rgb[:, :, 2] * 0.70)
    green = focus & (rgb[:, :, 1] > 47) & (rgb[:, :, 1] > rgb[:, :, 0] * 1.45) & (
        rgb[:, :, 1] > rgb[:, :, 2] * 0.55)
    history.append((red.astype(np.float32), green.astype(np.float32)))
    history[:] = history[-3:]
    weights = [0.35, 0.60, 1.0][-len(history):]
    red_trail = np.maximum.reduce([mask[0] * weight
                                   for mask, weight in zip(history, weights)])
    green_trail = np.maximum.reduce([mask[1] * weight
                                     for mask, weight in zip(history, weights)])
    red_glow = gaussian_filter(red_trail, 11) * 2.8 + gaussian_filter(red_trail, 4) * 0.7
    green_glow = gaussian_filter(green_trail, 11) * 2.8 + gaussian_filter(green_trail, 4) * 0.7
    red_glow = np.clip(red_glow * (0.6 + 0.8 * pulse), 0, 1)
    green_glow = np.clip(green_glow * (0.6 + 0.8 * pulse), 0, 1)
    layer = np.zeros((H, W, 4), dtype=np.uint8)
    total = np.maximum(red_glow, green_glow)
    if style == "ivory":
        layer[:, :, :3] = (255, 234, 205)
        layer[:, :, 3] = np.uint8(np.clip(total * 88, 0, 110))
    else:
        layer[:, :, 0] = np.uint8(90 + red_glow * 165)
        layer[:, :, 1] = np.uint8(40 + green_glow * 205)
        layer[:, :, 2] = np.uint8(95 + total * 90)
        layer[:, :, 3] = np.uint8(np.clip(total * 125, 0, 150))
    return layer


def render_alpha(frames: np.memmap, cues: list[dict], style: str,
                 target: Path, preview: Path) -> None:
    plate = np.median(frames[::4], axis=0).astype(np.int16)
    yy, xx = np.mgrid[:H, :W]
    focus = ((((xx - W * 0.5) / (W * 0.32)) ** 2 +
              ((yy - H * 0.38) / (H * 0.43)) ** 2) < 1) & (yy < 450)
    boundaries = np.array([float(cue["start"]) for cue in cues[1:]] + [50.0])
    command = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
               "-s", f"{W}x{H}", "-r", str(MASK_FPS), "-i", "pipe:0",
               "-an", "-c:v", "qtrle", "-pix_fmt", "argb", str(target)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    history: list[tuple[np.ndarray, np.ndarray]] = []
    try:
        for index, frame in enumerate(frames):
            time = index / MASK_FPS
            distance = float(np.min(np.abs(boundaries - time)))
            pulse = float(np.exp(-(distance / 0.17) ** 2))
            layer = (halo_frame(frame, plate, focus, pulse) if style == "halo"
                     else neon_frame(frame, focus, pulse, history, style))
            if index == 120:
                Image.fromarray(layer, "RGBA").save(preview)
            process.stdin.write(layer.tobytes())
    finally:
        process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError("Creazione della luce sulle note fallita")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--notes", type=Path, required=True)
    parser.add_argument("--style", choices=("halo", "neon", "ivory"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not args.video.is_file() or not args.notes.is_file():
        parser.error("Video o cue delle note mancante")
    root = args.out.parent / "s24-note-experiments"
    root.mkdir(parents=True, exist_ok=True)
    raw = root / "intro-lowres.rgb"
    frames = extract_frames(args.video, raw)
    cues = json.loads(args.notes.read_text(encoding="utf-8"))["intervals"]
    alpha = root / f"note-{args.style}-alpha.mov"
    render_alpha(frames, cues, args.style, alpha,
                 root / f"note-{args.style}-preview.png")
    run("-i", str(args.video), "-i", str(alpha), "-filter_complex",
        "[1:v]scale=1080:1920:flags=bicubic[light];"
        "[0:v][light]overlay=0:0:eof_action=pass[v]",
        "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "copy", "-t", "60",
        str(args.out))
    print(f"Variante {args.style}: {args.out}", flush=True)


if __name__ == "__main__":
    main()
