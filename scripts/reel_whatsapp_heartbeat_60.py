#!/usr/bin/env python3
"""Render recent WhatsApp pole media as a 60-second heartbeat preview."""
from __future__ import annotations

import argparse
import os
import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageOps

APP = Path(__file__).resolve().parents[1] / "integrations" / "tiktok_editor" / "app"
sys.path.insert(0, str(APP))

from autoedit.media import MediaItem  # noqa: E402
from autoedit.overlays import render_cross_light_png  # noqa: E402
from autoedit.person_layers import prepare_person_mask  # noqa: E402
from autoedit.render import (  # noqa: E402
    build_image_segment, build_video_segment,
)

W, H, FPS = 360, 640, 24
FINALE_SOURCE_TIMES = [36 + i * 29 / 21 for i in range(22)]


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def portrait_crop(source: Path, target: Path, mask_cache: Path) -> None:
    """Crop a horizontal WhatsApp still around the detected performer."""
    if target.is_file():
        return
    mask_path = prepare_person_mask(source, mask_cache)
    with Image.open(source) as original, Image.open(mask_path) as mask_image:
        image = ImageOps.exif_transpose(original).convert("RGB")
        mask = mask_image.convert("L")
        bounds = mask.point(lambda value: 255 if value > 100 else 0).getbbox()
        center_x = (bounds[0] + bounds[2]) / 2 if bounds else image.width / 2
        crop_width = min(image.width, round(image.height * W / H))
        left = max(0, min(image.width - crop_width, round(center_x - crop_width / 2)))
        cropped = image.crop((left, 0, left + crop_width, image.height))
        cropped.resize((720, 1280), Image.Resampling.LANCZOS).save(target)


def beat_cut_frames(beats, audio_start: float) -> list[int]:
    """Two beats per shot in the buildup, one beat per shot in the finale."""
    times = sorted(float(t) - audio_start for t in beats.beat_times)
    early = [t for t in times if 0.3 <= t < 49.8]
    late = [t for t in times if 50.3 <= t < 59.9]
    selected = [0.0, *early[::2], 50.0, *late, 60.0]
    frames = sorted(set(round(t * FPS) for t in selected))
    if frames[0] != 0 or frames[-1] != 60 * FPS:
        raise ValueError("Griglia del battito incompleta")
    return frames


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photo-dir", type=Path, required=True)
    parser.add_argument("--photo-pattern", default="WhatsApp Image 2026-10-04 at 11.44.*.jpeg")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--audio-start", type=float, default=73.7)
    args = parser.parse_args()
    photo_sources = sorted(args.photo_dir.glob(args.photo_pattern))
    if not photo_sources:
        parser.error("Nessuna foto corrisponde al pattern")
    for path in [args.video, args.audio, *photo_sources]:
        if not path.is_file():
            parser.error(f"File non trovato: {path}")
    root = args.out.parent / "whatsapp-heartbeat-assets"
    root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NUMBA_CACHE_DIR", str(root / ".numba-cache"))
    from autoedit.beats import detect_beats

    beats = detect_beats(args.audio)
    frames = beat_cut_frames(beats, args.audio_start)
    slots = [(frames[i], frames[i + 1]) for i in range(len(frames) - 1)]
    first_finale = next(i for i, (a, _) in enumerate(slots) if a >= 50 * FPS)
    buildup_count = first_finale
    print(f"Battito {beats.tempo:.1f} BPM; {buildup_count} tagli preparazione, "
          f"{len(slots) - buildup_count} finale", flush=True)

    photos = []
    for index, source in enumerate(photo_sources):
        target = root / f"photo-{index:02d}-vertical.png"
        portrait_crop(source, target, root / "source-photo-masks")
        photos.append(target)
    print(f"Foto WhatsApp incluse: {len(photos)}", flush=True)

    # The new vertical clip's first half supplies motion; later frames supply
    # the fast acrobatic ending.
    source_clips = []
    for index in range((buildup_count + 1) // 2):
        start = 0.5 + index * (31.0 / max(1, (buildup_count + 1) // 2 - 1))
        target = root / f"motion-{index:02d}.mp4"
        if not target.is_file():
            ffmpeg("-ss", f"{start:.3f}", "-t", "1.6", "-i", str(args.video),
                   "-an", "-c:v", "libx264", "-preset", "ultrafast", str(target))
        source_clips.append(target)
    acro = []
    for index, sec in enumerate(FINALE_SOURCE_TIMES):
        target = root / f"acro-{index:02d}.png"
        if not target.is_file():
            ffmpeg("-ss", f"{sec:.3f}", "-i", str(args.video), "-frames:v", "1", str(target))
        acro.append(target)

    mask_cache = root / "person-masks"
    rendered = []
    photo_i = clip_i = 0
    for index, (start_frame, end_frame) in enumerate(slots):
        finale = index >= first_finale
        duration = (end_frame - start_frame) / FPS
        if finale:
            source = acro[(index - first_finale) * len(acro) // (len(slots) - first_finale)]
        elif index % 2 == 0:
            source = photos[photo_i % len(photos)]
            photo_i += 1
        else:
            source = source_clips[clip_i]
            clip_i += 1
        print(f"Scena {index + 1}/{len(slots)} {start_frame / FPS:.2f}s: "
              f"{source.name}", flush=True)
        mask = prepare_person_mask(source, mask_cache)
        raw = root / f"scene-{index + 1:02d}-raw.mp4"
        # Each new beat briefly brings the body forward; the mask confines the
        # light to the person. There are no drawn bolts or outline graphics.
        accent = any(abs((start_frame / FPS + args.audio_start) - float(t)) < 0.08
                     for t in beats.strong_times)
        common = dict(person_mask=mask, subject_style="none", background_style="none",
                      background_blur=0.3, background_dim=0.24 if not finale else 0.12,
                      subject_dim=0.04 if not finale else 0.0,
                      subject_spot=0.14 if accent else (0.07 if finale else 0.03))
        if source.suffix == ".mp4":
            build_video_segment(MediaItem(source, "video", duration=1.6, best_start=0),
                                duration, W, H, FPS, "none", random.Random(index), raw,
                                best_start=0, **common)
        else:
            build_image_segment(MediaItem(source, "image"), duration, W, H, FPS,
                                "none", random.Random(index), False, raw, **common)
        # Quantize every clip to the score's exact frame boundary. This avoids
        # silent padding and frozen final frames when many short scenes join.
        fixed = root / f"scene-{index + 1:02d}.mp4"
        frame_count = end_frame - start_frame
        ffmpeg("-i", str(raw), "-vf",
               f"fps={FPS},tpad=stop_mode=clone:stop_duration=0.25,"
               f"trim=end_frame={frame_count},setpts=PTS-STARTPTS",
               "-frames:v", str(frame_count), "-an", "-c:v", "libx264",
               "-preset", "veryfast", str(fixed))
        rendered.append(fixed)

    concat_file = root / "scenes.ffconcat"
    concat_file.write_text("ffconcat version 1.0\n" +
                           "".join(f"file '{path.resolve()}'\n" for path in rendered),
                           encoding="utf-8")
    silent = root / "silent-heartbeat.mp4"
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(concat_file),
           "-an", "-c", "copy", str(silent))
    cross = root / "cross-light.png"
    render_cross_light_png(W, H, cross)
    pulses = [float(t) - args.audio_start for t in beats.beat_times
              if args.audio_start + 50 <= float(t) < args.audio_start + 60]
    # Encode audio and the cross in two passes. The general overlay muxer can
    # consume concat-demuxer timestamps early and hold the last image.
    with_audio = root / "with-audio.mp4"
    ffmpeg("-i", str(silent), "-ss", f"{args.audio_start:.3f}", "-i", str(args.audio),
           "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-af",
           "afade=t=in:st=0:d=0.25,afade=t=out:st=59.75:d=0.25",
           "-t", "60", str(with_audio))
    enabled = "+".join(f"between(t,{t:.3f},{t + 0.08:.3f})" for t in pulses)
    graph = ("[1:v]format=rgba,colorchannelmixer=aa=0.7[cross];"
             f"[0:v][cross]overlay=0:0:enable='{enabled}':eof_action=pass[v]")
    ffmpeg("-i", str(with_audio), "-loop", "1", "-i", str(cross),
           "-filter_complex", graph, "-map", "[v]", "-map", "0:a",
           "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
           "-c:a", "copy", "-t", "60", str(args.out))
    print(f"Anteprima pronta: {args.out}", flush=True)


if __name__ == "__main__":
    main()
