#!/usr/bin/env python3
"""Pulse violet and green costume light for two estimated bagpipe tones."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

from reel_s24_note_aura import H, MASK_FPS, W, extract_frames, run

VIOLET = (215, 40, 255)
GREEN = (50, 255, 105)
OUTPUT_FPS = 60


def pulse_strength(age: float, remaining: float) -> float:
    """Two crisp flashes per note, separated by darkness."""
    if age < 0 or remaining <= 0:
        return 0.0
    onset = min(1.0, max(0.0, age / 0.025), max(0.0, (0.13 - age) / 0.035))
    ending = min(1.0, max(0.0, (0.18 - remaining) / 0.035),
                 max(0.0, (remaining - 0.04) / 0.025))
    return max(onset, ending)


def classify_tones(intervals: list[dict], cqt_path: Path) -> list[dict]:
    cqt = np.load(cqt_path)["cqt"]
    tones = []
    for cue in intervals:
        start, end = float(cue["start"]), float(cue["end"])
        first = max(0, round((start + 0.07) * 22050 / 256))
        last = min(cqt.shape[1], round((end - 0.07) * 22050 / 256))
        spectrum = np.median(cqt[:, first:max(first + 1, last)], axis=1)
        lower = spectrum[6] + 0.7 * spectrum[18] + 0.4 * spectrum[30]
        upper = spectrum[7] + 0.7 * spectrum[19] + 0.4 * spectrum[31]
        ratio = float(np.log((upper + 0.05) / (lower + 0.05)))
        duration = end - start
        score = 0.7 * ((ratio + 0.315) / 0.30) + 0.3 * ((duration - 0.85) / 0.60)
        tones.append({"start": start, "end": end,
                      "tone": "naaa" if score > 0 else "no",
                      "color": "green" if score > 0 else "violet",
                      "score": round(score, 3), "pitch_ratio": round(ratio, 3)})
    return tones


def render_alpha(frames: np.memmap, tones: list[dict], target: Path,
                 preview_root: Path) -> None:
    yy, xx = np.mgrid[:H, :W]
    focus = ((((xx - W * 0.5) / (W * 0.32)) ** 2 +
              ((yy - H * 0.38) / (H * 0.43)) ** 2) < 1) & (yy < 450)
    command = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
               "-s", f"{W}x{H}", "-r", str(OUTPUT_FPS), "-i", "pipe:0",
               "-an", "-c:v", "qtrle", "-pix_fmt", "argb", str(target)]
    encoder = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert encoder.stdin is not None
    history: list[np.ndarray] = []
    cue_index = 0
    previews = set()
    try:
        glow = np.zeros((H, W), dtype=np.float32)
        for index in range(len(frames) * (OUTPUT_FPS // MASK_FPS)):
            time = index / OUTPUT_FPS
            while cue_index + 1 < len(tones) and time >= tones[cue_index]["end"]:
                cue_index += 1
            cue = tones[cue_index]
            if index % (OUTPUT_FPS // MASK_FPS) == 0:
                rgb = frames[index // (OUTPUT_FPS // MASK_FPS)].astype(np.float32)
                red = focus & (rgb[:, :, 0] > 58) & (
                    rgb[:, :, 0] > rgb[:, :, 1] * 1.55) & (
                    rgb[:, :, 0] > rgb[:, :, 2] * 0.70)
                green = focus & (rgb[:, :, 1] > 47) & (
                    rgb[:, :, 1] > rgb[:, :, 0] * 1.45) & (
                    rgb[:, :, 1] > rgb[:, :, 2] * 0.55)
                history.append(np.maximum(red, green).astype(np.float32))
                history[:] = history[-3:]
                weights = [0.35, 0.60, 1.0][-len(history):]
                trail = np.maximum.reduce([mask * weight
                                           for mask, weight in zip(history, weights)])
                glow = np.clip(gaussian_filter(trail, 11) * 2.8 +
                               gaussian_filter(trail, 4) * 0.7, 0, 1)
            age = time - cue["start"]
            remaining = cue["end"] - time
            strength = pulse_strength(age, remaining)
            color = GREEN if cue["tone"] == "naaa" else VIOLET
            layer = np.zeros((H, W, 4), dtype=np.uint8)
            layer[:, :, :3] = color
            layer[:, :, 3] = np.uint8(np.clip(glow * 210 * strength, 0, 210))
            if cue["color"] not in previews and strength > 0.75 and np.max(layer[:, :, 3]) > 35:
                Image.fromarray(layer, "RGBA").save(
                    preview_root / f"tone-{cue['color']}-preview.png")
                previews.add(cue["color"])
            encoder.stdin.write(layer.tobytes())
    finally:
        encoder.stdin.close()
    if encoder.wait() != 0:
        raise RuntimeError("Creazione dei bagliori viola/verdi fallita")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--notes", type=Path, required=True)
    parser.add_argument("--cqt", type=Path, required=True)
    parser.add_argument("--tones", type=Path,
                        help="JSON modificabile; viene creato se non esiste")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.video, args.notes, args.cqt):
        if not path.is_file():
            parser.error(f"File mancante: {path}")
    root = args.out.parent / "s24-note-experiments"
    root.mkdir(parents=True, exist_ok=True)
    intervals = json.loads(args.notes.read_text(encoding="utf-8"))["intervals"]
    tones_path = args.tones or root / "tone-cues.json"
    if tones_path.is_file():
        tones = json.loads(tones_path.read_text(encoding="utf-8"))["tones"]
        if len(tones) != len(intervals) or any(
            abs(float(tone["start"]) - float(cue["start"])) > 0.02 or
            abs(float(tone["end"]) - float(cue["end"])) > 0.02
            for tone, cue in zip(tones, intervals)):
            parser.error("I cue dei toni non corrispondono agli intervalli delle note")
        if any(tone.get("tone") not in {"no", "naaa"} for tone in tones):
            parser.error("Ogni tono deve essere 'no' oppure 'naaa'")
        for tone in tones:
            tone["color"] = "green" if tone["tone"] == "naaa" else "violet"
    else:
        tones = classify_tones(intervals, args.cqt)
        tones_path.write_text(json.dumps({
            "method": "two relative harmonic profiles; 'no' lower/shorter, 'naaa' higher/longer; editable",
            "tones": tones}, ensure_ascii=False, indent=2), encoding="utf-8")
    raw = root / "intro-lowres.rgb"
    frames = extract_frames(args.video, raw)
    alpha = root / "dual-tone-staccato-alpha.mov"
    render_alpha(frames, tones, alpha, root)
    run("-i", str(args.video), "-i", str(alpha), "-filter_complex",
        "[1:v]scale=1080:1920:flags=bicubic[light];"
        "[0:v][light]overlay=0:0:eof_action=pass[v]",
        "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "copy", "-t", "60",
        str(args.out))
    violet = sum(tone["tone"] == "no" for tone in tones)
    green = sum(tone["tone"] == "naaa" for tone in tones)
    print(f"Bagliori sui toni: viola {violet}, verde {green}; {args.out}", flush=True)


if __name__ == "__main__":
    main()
