#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Add two-line karaoke light to the first 50 seconds of an existing reel."""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

APP = Path(__file__).resolve().parents[1] / "integrations" / "tiktok_editor" / "app"
sys.path.insert(0, str(APP))

W, H, FPS = 360, 640, 24
LYRICS = [
    "All’epoca i medici erano così, frettolosi: era il 1998.",
    "Ma Dio dice: “La verità viene rivelata agli umili e viene nascosta a chi è colto.”",
    "“Noi pregheremo il Signore affinché lo guarisca.”",
    "Il dottore li guardava perplesso.",
    "“In Lui troviamo conforto e solo Lui decide sulla vita e sulla morte.”",
    "“Ma, anche se Dio non volesse guarirlo, sia fatta la sua volontà.”",
    "Uscirono di corsa dallo studio medico e poi andarono subito in chiesa a pregare.",
    "Lì si sfogarono con Mimmo, l’anziano, un membro speciale della comunità.",
    "Mimmo, con una mano alzata e l’altra sulla pancia, pregava con autorità.",
    "E il Signore ascoltò quelle preghiere e disse a Marianna:",
    "“Figlia mia, non preoccuparti.”",
    "Passarono soltanto sei mesi, il bambino nacque, era sano e per questo oggi sono qui.",
    "E non solo, fratello: sono nato sano, ma sono anche il più forte di tutti quanti in questa scena.",
    "Da Milano a Napoli adesso devono farsela sotto tutti quanti, se non vogliono problemi.",
    "Si vede che ho uno scopo importante, per questo il Signore veglia su di me.",
    "Perché, se avessero seguito la sapienza umana, a quest’ora BATTISTA non esisterebbe.",
]
FONT_PATHS = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
)


def chunks(line: str, max_words: int = 4) -> list[str]:
    words = line.split()
    count = math.ceil(len(words) / max_words)
    base, extra = divmod(len(words), count)
    sizes = [base + (i < extra) for i in range(count)]
    result, offset = [], 0
    for size in sizes:
        result.append(" ".join(words[offset:offset + size]))
        offset += size
    return result


def make_cues(beat_times: list[float]) -> list[dict]:
    """Spread each supplied verse across the sampled beats, preserving order."""
    cards = [chunks(line) for line in LYRICS]
    if sum(map(len, cards)) != 52:
        raise ValueError("Numero inatteso di frasi")
    groups = ((cards, 0.0, 50.0),)
    cues = []
    for group, begin, end in groups:
        phrases = [card for line in group for card in line]
        weights = [len(card.split()) for card in phrases]
        beats = [round(t * FPS) for t in beat_times if begin < t < end]
        boundaries = [round(begin * FPS)]
        accumulated = 0
        total = sum(weights)
        for i, weight in enumerate(weights[:-1]):
            accumulated += weight
            target = (begin + (end - begin) * accumulated / total) * FPS
            available = [frame for frame in beats
                         if frame > boundaries[-1] + 8
                         and frame < round(end * FPS) - (len(weights) - i - 1) * 8]
            frame = min(available, key=lambda f: abs(f - target)) if available else round(target)
            boundaries.append(frame)
        boundaries.append(round(end * FPS))
        for phrase, start, stop in zip(phrases, boundaries, boundaries[1:]):
            cues.append({"start_frame": start, "end_frame": stop,
                         "start": round(start / FPS, 3), "end": round(stop / FPS, 3),
                         "text": phrase})
    if any(c["end_frame"] <= c["start_frame"] for c in cues):
        raise ValueError("Una scritta non ha tempo per apparire")
    return cues


def font(size: int) -> ImageFont.ImageFont:
    for path in FONT_PATHS:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def light_card(text: str, next_text: str) -> dict:
    """Two rows with a bright prefix and one active word at a time."""
    if not next_text:
        text = "la sapienza umana, a quest’ora"
        next_text = "BATTISTA non esisterebbe."
    measure = ImageDraw.Draw(Image.new("L", (1, 1)))
    size = 36
    while size > 22:
        chosen_font = font(size)
        if max(measure.textlength(row, font=chosen_font)
               for row in (text, next_text)) <= W - 32:
            break
        size -= 1
    y = H - 163
    rows = []
    highlight = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    active_left = active_width = 0
    for row_index, row in enumerate((text, next_text)):
        mask = Image.new("L", (W, H), 0)
        draw = ImageDraw.Draw(mask)
        width = draw.textlength(row, font=chosen_font)
        if row_index == 0:
            active_left, active_width = round((W - width) / 2), round(width)
        draw.text(((W - width) / 2, y + row_index * 45), row,
                  font=chosen_font, fill=255, stroke_width=1, stroke_fill=180)
        aura = mask.filter(ImageFilter.GaussianBlur(12)).point(
            lambda value: min(255, value * 3))
        cyan = Image.new("RGBA", (W, H), (90, 207, 255, 0))
        cyan.putalpha(aura.point(lambda value: int(value * (0.40 if row_index == 0 else 0.35))))
        core = Image.new("RGBA", (W, H),
                         (175, 225, 255, 0) if row_index == 0 else (155, 218, 255, 0))
        core.putalpha(mask.point(lambda value: int(value * (0.54 if row_index == 0 else 0.48))))
        rows.append(Image.alpha_composite(cyan, core))
        if row_index == 0:
            bright_aura = Image.new("RGBA", (W, H), (112, 222, 255, 0))
            bright_aura.putalpha(aura.point(lambda value: int(value * 0.82)))
            bright_core = Image.new("RGBA", (W, H), (255, 250, 232, 0))
            bright_core.putalpha(mask)
            highlight = Image.alpha_composite(bright_aura, bright_core)
    word_spans = []
    hot_layers = []
    prefix = ""
    for word in text.split():
        before = prefix + (" " if prefix else "")
        x0 = active_left + measure.textlength(before, font=chosen_font)
        x1 = x0 + measure.textlength(word, font=chosen_font)
        prefix = before + word
        word_spans.append((x0, x1, max(1, len(word))))
        word_mask = Image.new("L", (W, H), 0)
        hot_draw = ImageDraw.Draw(word_mask)
        hot_draw.text((x0, y), word, font=chosen_font, fill=255,
                      stroke_width=1, stroke_fill=220)
        underline_y = y + size + 5
        hot_draw.line((x0, underline_y, x1, underline_y), fill=220, width=2)
        glow_mask = word_mask.filter(ImageFilter.GaussianBlur(7)).point(
            lambda value: min(255, value * 3))
        halo = Image.new("RGBA", (W, H), (255, 236, 174, 0))
        halo.putalpha(glow_mask.point(lambda value: int(value * 0.8)))
        core = Image.new("RGBA", (W, H), (255, 255, 245, 0))
        core.putalpha(word_mask.point(lambda value: int(value * 0.8)))
        hot_layers.append(Image.alpha_composite(halo, core))
    return {"base": Image.alpha_composite(rows[0], rows[1]),
            "bright": highlight, "left": active_left, "width": active_width,
            "spans": word_spans, "hot": hot_layers}


def render_alpha_video(cues: list[dict], target: Path) -> None:
    cards = [light_card(c["text"], cues[i + 1]["text"] if i + 1 < len(cues) else "")
             for i, c in enumerate(cues)]
    blank = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
           "-s:v", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0",
           "-an", "-c:v", "qtrle", "-pix_fmt", "argb", str(target)]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert process.stdin is not None
    try:
        cue_index = 0
        for frame in range(60 * FPS):
            while cue_index + 1 < len(cues) and frame >= cues[cue_index]["end_frame"]:
                cue_index += 1
            cue = cues[cue_index]
            if not cue["start_frame"] <= frame < cue["end_frame"]:
                process.stdin.write(blank.tobytes())
                continue
            age = (frame - cue["start_frame"]) / FPS
            left = (cue["end_frame"] - frame) / FPS
            card = cards[cue_index]
            layer = card["base"].copy()
            progress = (frame - cue["start_frame"] + 1) / max(
                1, cue["end_frame"] - cue["start_frame"])
            spans = card["spans"]
            total_weight = sum(span[2] for span in spans)
            word_position = progress * total_weight
            consumed = 0
            word_index = len(spans) - 1
            fraction = 1.0
            for i, (_, _, weight) in enumerate(spans):
                if word_position <= consumed + weight:
                    word_index = i
                    fraction = max(0.0, min(1.0, (word_position - consumed) / weight))
                    break
                consumed += weight
            word_start, word_end, _ = spans[word_index]
            revealed_to = max(0, min(W, round(word_start + (word_end - word_start) * fraction)))
            if revealed_to > 0:
                layer.alpha_composite(card["bright"].crop((0, 0, revealed_to, H)), (0, 0))
            layer.alpha_composite(card["hot"][word_index])
            opacity = min(1.0, age / 0.12)
            if cue_index == len(cues) - 1:
                opacity = min(opacity, left / 0.12)
            if cue_index > 0 and age < 0.12:
                previous = cards[cue_index - 1]
                outgoing = Image.alpha_composite(previous["base"], previous["bright"])
                outgoing_alpha = outgoing.getchannel("A").point(
                    lambda value: round(value * (1 - age / 0.12)))
                outgoing.putalpha(outgoing_alpha)
                incoming_alpha = layer.getchannel("A").point(
                    lambda value: round(value * opacity))
                layer.putalpha(incoming_alpha)
                outgoing.alpha_composite(layer)
                layer = outgoing
                opacity = 1.0
            opacity = max(0.0, opacity)
            alpha = layer.getchannel("A").point(lambda value: round(value * opacity))
            layer.putalpha(alpha)
            process.stdin.write(layer.tobytes())
    finally:
        process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError("Creazione delle scritte luminose fallita")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--audio-start", type=float, default=73.7)
    args = parser.parse_args()
    if not args.video.is_file() or not args.audio.is_file():
        parser.error("Video o audio mancante")
    root = args.out.parent / "lyrics-light-assets"
    root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NUMBA_CACHE_DIR", str(root / ".numba-cache"))
    from autoedit.beats import detect_beats

    beat_info = detect_beats(args.audio)
    beat_times = [float(t) - args.audio_start for t in beat_info.beat_times
                  if args.audio_start <= float(t) < args.audio_start + 60]
    cues = make_cues(beat_times)
    cue_path = root / "lyrics-cues.json"
    cue_path.write_text(json.dumps({"audio_start": args.audio_start,
                                    "alignment": "beat-based preview, not word-accurate",
                                    "cues": [{k: v for k, v in cue.items()
                                              if k not in ("start_frame", "end_frame")}
                                             for cue in cues]},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
    alpha_video = root / "lyrics-alpha.mov"
    print(f"Creo {len(cues)} scritte luminose e la traccia di trasparenza...", flush=True)
    render_alpha_video(cues, alpha_video)
    print("Sovrappongo le lyrics al reel...", flush=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(args.video),
                    "-i", str(alpha_video), "-filter_complex",
                    "[0:v][1:v]overlay=0:0:eof_action=pass[v]",
                    "-map", "[v]", "-map", "0:a", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
                    "-c:a", "copy", "-t", "60", str(args.out)], check=True)
    print(f"Anteprima pronta: {args.out}", flush=True)
    print(f"Tempi modificabili: {cue_path}", flush=True)


if __name__ == "__main__":
    main()
