#!/usr/bin/env python3
"""Experimental 60s pole reel: dense stills, mixed transitions, electric finale."""
from __future__ import annotations

import argparse
import os
import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

APP = Path(__file__).resolve().parents[1] / "integrations" / "tiktok_editor" / "app"
sys.path.insert(0, str(APP))

from autoedit.effects import pick_transition  # noqa: E402
from autoedit.media import MediaItem  # noqa: E402
from autoedit.overlays import render_cross_light_png  # noqa: E402
from autoedit.person_layers import prepare_person_mask  # noqa: E402
from autoedit.render import (  # noqa: E402
    Segment, build_image_segment, build_video_segment, concat_with_xfade, mux_audio,
)

W, H, FPS = 360, 640, 24
PHOTO_IDS = [5001, 4999, 4998, 4997, 4996, 4995, 4994, 4993,
             4992, 4991, 4990, 4989, 4988, 4987, 4986]
VIDEO_STARTS = [0, 4, 8, 12, 16, 20, 24]
FINALE_TIMES = [35, 42, 48, 54, 60, 67, 74, 80, 86, 92, 98, 105, 111, 117, 122, 127]


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def make_electric(mask_path: Path, target: Path, seed: int) -> None:
    """Place branching blue arcs near this still's detected person silhouette."""
    with Image.open(mask_path) as image:
        mask = ImageOps.fit(image.convert("L"), (W, H), method=Image.Resampling.BILINEAR)
    bbox = mask.point(lambda v: 255 if v > 90 else 0).getbbox()
    if not bbox:
        bbox = (W // 4, H // 5, W * 3 // 4, H * 4 // 5)
    rng = random.Random(seed)
    arcs = Image.new("L", (W, H), 0)
    draw = ImageDraw.Draw(arcs)
    left, top, right, bottom = bbox
    for side in (-1, 1):
        for n in range(2):
            x = (left if side < 0 else right) + side * (9 + n * 13)
            y0 = max(10, top + rng.randint(0, max(1, (bottom - top) // 4)))
            y1 = min(H - 10, bottom - rng.randint(0, max(1, (bottom - top) // 4)))
            pts = [(x, y0)]
            for step in range(1, 8):
                pts.append((max(2, min(W - 3, x + rng.randint(-19, 19))),
                            int(y0 + (y1 - y0) * step / 7)))
            draw.line(pts, fill=180, width=2)
    glow = arcs.filter(ImageFilter.GaussianBlur(7)).point(lambda v: min(255, v * 2))
    alpha = ImageChops.add(glow, arcs)
    electric = Image.new("RGBA", (W, H), (115, 205, 255, 0))
    electric.putalpha(alpha)
    electric.save(target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photo-dir", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--audio-start", type=float, default=73.7)
    args = parser.parse_args()
    for path in [args.video, args.audio, *(args.photo_dir / f"DSCF{i}.JPG" for i in PHOTO_IDS)]:
        if not path.is_file():
            parser.error(f"File non trovato: {path}")
    root = args.out.parent / "pole-preview-60-fx-assets"
    root.mkdir(parents=True, exist_ok=True)
    photos = []
    for ident in PHOTO_IDS:
        target = root / f"DSCF{ident}-vertical.png"
        if not target.is_file():
            with Image.open(args.photo_dir / f"DSCF{ident}.JPG") as image:
                upright = ImageOps.exif_transpose(image).convert("RGB")
                if upright.height <= upright.width:
                    raise ValueError(f"Foto non verticale: DSCF{ident}.JPG")
                upright.save(target)
        photos.append(target)
    video_clips = []
    for start in VIDEO_STARTS:
        target = root / f"video-{start:02d}-{start + 5:02d}.mp4"
        if not target.is_file():
            ffmpeg("-ss", str(start), "-t", "5", "-i", str(args.video),
                   "-an", "-c:v", "libx264", "-preset", "ultrafast", str(target))
        video_clips.append(target)
    finale = []
    for index, sec in enumerate(FINALE_TIMES):
        target = root / f"acro-{index:02d}-{sec:03d}.png"
        if not target.is_file():
            ffmpeg("-ss", str(sec), "-i", str(args.video), "-frames:v", "1", str(target))
        finale.append(target)

    # 15 x 1.4 + 7 x (29/7) = 50 seconds; 16 x .625 = 10 seconds.
    buildup = []
    for index, photo in enumerate(photos):
        buildup.append((photo, 1.4, False))
        if index < len(video_clips):
            buildup.append((video_clips[index], 29.0 / 7.0, False))
    storyboard = buildup + [(path, 0.625, True) for path in finale]
    assert len(storyboard) == 38
    assert abs(sum(duration for _, duration, _ in storyboard) - 60) < 1e-6

    rng = random.Random(20261004)
    mask_cache = root / "person-masks"
    segments = []
    for index, (source, duration, is_finale) in enumerate(storyboard):
        print(f"Scena {index + 1}/{len(storyboard)}: {source.name} ({duration:.3f}s)", flush=True)
        mask = prepare_person_mask(source, mask_cache)
        output = root / f"scene-{index + 1:02d}.mp4"
        pad = 0.15 if index < len(storyboard) - 1 else 0.0
        transition = pick_transition(rng, accented=is_finale, mode="chaos")
        common = dict(person_mask=mask, subject_style="none", background_style="moody",
                      background_blur=0.7, background_dim=0.62 if is_finale else 0.8,
                      subject_dim=0.03 if is_finale else 0.46 - 0.24 * index / len(buildup),
                      subject_spot=0.12 if is_finale else 0.0)
        if source.suffix == ".mp4":
            build_video_segment(MediaItem(source, "video", duration=5, best_start=0),
                                duration, W, H, FPS, "none", random.Random(index), output,
                                pad=pad, best_start=0, **common)
            item = MediaItem(source, "video", duration=5)
        else:
            build_image_segment(MediaItem(source, "image"), duration, W, H, FPS,
                                "none", random.Random(index), False, output, pad=pad, **common)
            item = MediaItem(source, "image")
        if is_finale:
            electric = root / f"electric-{index:02d}.png"
            make_electric(mask, electric, index + 141)
            effected = root / f"scene-{index + 1:02d}-electric.mp4"
            ffmpeg("-i", str(output), "-loop", "1", "-i", str(electric),
                   "-filter_complex", "[0:v]eq=brightness=0.19:enable='lt(t,0.08)'[base];"
                   "[base][1:v]overlay=0:0:shortest=1,format=yuv420p[out]",
                   "-map", "[out]", "-an", "-t", f"{duration + pad:.3f}",
                   "-c:v", "libx264", "-preset", "veryfast", str(effected))
            output = effected
        segments.append(Segment(item, duration, transition, is_finale,
                                person_mask=mask, clip_path=output,
                                render_duration=duration + pad))

    # FFmpeg xfade needs frame-exact core and overlap lengths. Fractional scene
    # durations otherwise accumulate drift and can truncate a long chain.
    fixed_segments = []
    cumulative = 0.0
    previous_frame = 0
    for index, segment in enumerate(segments):
        cumulative += segment.duration
        boundary_frame = round(cumulative * FPS)
        core_frames = boundary_frame - previous_frame
        previous_frame = boundary_frame
        pad_frames = 4 if index < len(segments) - 1 else 0
        frame_count = core_frames + pad_frames
        fixed = root / f"fixed-{index + 1:02d}.mp4"
        ffmpeg("-i", str(segment.clip_path), "-vf",
               f"fps={FPS},tpad=stop_mode=clone:stop_duration=1,"
               f"trim=end_frame={frame_count},setpts=PTS-STARTPTS",
               "-frames:v", str(frame_count), "-an", "-c:v", "libx264",
               "-preset", "veryfast", str(fixed))
        fixed_segments.append(Segment(segment.item, core_frames / FPS,
                                      segment.transition, segment.accented,
                                      clip_path=fixed, render_duration=frame_count / FPS))
    assert previous_frame == 60 * FPS
    silent = root / "silent-60-fx.mp4"
    total = concat_with_xfade(fixed_segments, 4 / FPS, silent, FPS,
                              work_dir=root, chunk_size=len(fixed_segments),
                              target_w=W, target_h=H)
    print(f"Video montato: {total:.2f}s; sincronizzo strobo e audio...", flush=True)
    os.environ.setdefault("NUMBA_CACHE_DIR", str(root / ".numba-cache"))
    from autoedit.beats import detect_beats
    beats = detect_beats(args.audio)
    pulses = [float(t) - args.audio_start for t in beats.beat_times
              if args.audio_start + 50 <= float(t) < args.audio_start + 60]
    pulses = [t for i, t in enumerate(pulses) if i == 0 or t - pulses[i - 1] >= 0.28]
    if not pulses:
        pulses = [50 + i * 0.5 for i in range(20)]
    cross = root / "cross-light.png"
    render_cross_light_png(W, H, cross)
    mux_audio(silent, args.audio, args.out, total, fade_in=0.25, fade_out=0.25,
              audio_offset=args.audio_start, target_duration=60,
              overlays=[{"png": cross, "x": 0, "y": 0,
                         "pulse_times": pulses, "pulse_width": 0.11}])
    print(f"Anteprima pronta: {args.out}", flush=True)


if __name__ == "__main__":
    main()
