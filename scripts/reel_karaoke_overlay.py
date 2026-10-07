#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Render reviewed, timed karaoke cues over a vertical Reel."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 360, 640, 30
FONT = "/System/Library/Fonts/Supplemental/Bodoni 72.ttc"


def words_for(cue: dict) -> list[tuple[str, float, float]]:
    start, end = float(cue["start"]), float(cue["end"])
    if not 0 <= start < end <= 111.25:
        raise ValueError("Tempi cue non validi")
    if cue.get("words"):
        words = [(str(w["text"]).strip(), float(w["start"]), float(w["end"]))
                 for w in cue["words"]]
    else:
        tokens = cue["text"].split()
        weights = [max(1, len(re.sub(r"\W", "", token))) for token in tokens]
        total = sum(weights)
        pos, words = start, []
        for token, weight in zip(tokens, weights):
            stop = pos + (end - start) * weight / total
            words.append((token, pos, stop))
            pos = stop
    if not words or any(not start - .02 <= a < b <= end + .02 for _, a, b in words):
        raise ValueError("Parole o tempi parola non validi")
    return words


def make_card(cue: dict):
    words = words_for(cue)
    tokens = [word for word, _, _ in words]
    font = ImageFont.truetype(FONT, 29)
    measure = ImageDraw.Draw(Image.new("L", (1, 1)))
    rows = [[]]
    for i, _ in enumerate(tokens):
        proposed = rows[-1] + [i]
        if rows[-1] and measure.textlength(" ".join(tokens[j] for j in proposed), font) > W - 34:
            rows.append([i])
        else:
            rows[-1] = proposed
    if len(rows) > 2:
        raise ValueError(f"Frase troppo lunga, dividila: {cue['text']}")
    base = Image.new("RGBA", (W, H))
    draw = ImageDraw.Draw(base)
    top = 490 if len(rows) == 2 else 510
    draw.rounded_rectangle((12, top - 18, W - 12, top + len(rows) * 39 + 16),
                           radius=13, fill=(18, 15, 22, 155))
    active = [Image.new("RGBA", (W, H)) for _ in words]
    bounds = []
    for row_index, row in enumerate(rows):
        x = (W - measure.textlength(" ".join(tokens[i] for i in row), font)) / 2
        y = top + row_index * 39
        for i in row:
            token = tokens[i]
            draw.text((x, y), token, font=font, fill=(241, 236, 226, 255),
                      stroke_width=1, stroke_fill=(24, 20, 27, 255))
            hot = ImageDraw.Draw(active[i])
            hot.text((x, y), token, font=font, fill=(242, 165, 103, 255),
                     stroke_width=1, stroke_fill=(55, 28, 24, 255))
            width = measure.textlength(token, font)
            hot.line((x, y + 31, x + width, y + 31), fill=(255, 195, 126, 230), width=2)
            bounds.append((i, x, x + width))
            x += width + measure.textlength(" ", font)
    return base, active, words, dict((i, (a, b)) for i, a, b in bounds)


def render_alpha(cues: list[dict], target: Path, duration: float) -> None:
    cards = [make_card(cue) for cue in cues]
    blank = Image.new("RGBA", (W, H))
    process = subprocess.Popen([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
        "-pix_fmt", "rgba", "-s:v", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0",
        "-an", "-c:v", "qtrle", "-pix_fmt", "argb", str(target),
    ], stdin=subprocess.PIPE)
    assert process.stdin is not None
    cue_i = 0
    try:
        for frame in range(round(duration * FPS)):
            t = frame / FPS
            while cue_i < len(cues) and t >= float(cues[cue_i]["end"]):
                cue_i += 1
            if cue_i >= len(cues) or t < float(cues[cue_i]["start"]):
                process.stdin.write(blank.tobytes())
                continue
            base, active, words, bounds = cards[cue_i]
            layer = base.copy()
            for i, (_, start, end) in enumerate(words):
                if t < start:
                    break
                if t >= end:
                    layer.alpha_composite(active[i])
                else:
                    left, right = bounds[i]
                    reveal = round(left + (right - left) * (t - start) / (end - start))
                    if reveal > left:
                        layer.alpha_composite(active[i].crop((0, 0, reveal, H)), (0, 0))
                    break
            process.stdin.write(layer.tobytes())
    finally:
        process.stdin.close()
    if process.wait():
        raise RuntimeError("Creazione grafica karaoke fallita")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--cues", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=111.2)
    args = parser.parse_args()
    cues = json.loads(args.cues.read_text(encoding="utf-8"))
    if not isinstance(cues, list) or not cues:
        raise ValueError("Il file cue deve contenere una lista non vuota")
    last = 0.0
    for cue in cues:
        if float(cue["start"]) < last - .02:
            raise ValueError("Cue sovrapposti o fuori ordine")
        last = float(cue["end"])
    assets = args.out.parent / (args.out.stem + "-assets")
    assets.mkdir(parents=True, exist_ok=True)
    alpha = assets / "karaoke-alpha.mov"
    render_alpha(cues, alpha, args.duration)
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(args.video), "-i", str(alpha),
        "-filter_complex", "[1:v]scale=1080:1920:flags=lanczos[lyrics];"
                           "[0:v][lyrics]overlay=0:0:eof_action=pass[v]",
        "-map", "[v]", "-map", "0:a:0", "-c:v", "libx264", "-preset", "medium",
        "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "copy",
        "-movflags", "+faststart", str(args.out),
    ], check=True)


if __name__ == "__main__":
    main()
