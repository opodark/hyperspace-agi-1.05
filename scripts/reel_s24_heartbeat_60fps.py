#!/usr/bin/env python3
"""Make a 60 fps S24 reel with beat stops, subtle zoom and backlit cross."""
from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

APP = Path(__file__).resolve().parents[1] / "integrations" / "tiktok_editor" / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from autoedit.media import MediaItem  # noqa: E402
from autoedit.render import build_video_segment  # noqa: E402
from reel_whatsapp_heartbeat_60 import W, H, ffmpeg  # noqa: E402
from reel_whatsapp_speedramp_finale import video_info  # noqa: E402

FPS = 60


def beat_cut_frames(beats, audio_start: float) -> list[int]:
    times = sorted(float(t) - audio_start for t in beats.beat_times)
    early = [t for t in times if 0.3 <= t < 49.8]
    late = [t for t in times if 50.3 <= t < 59.9]
    return sorted(set(round(t * FPS) for t in [0.0, *early[::2], 50.0, *late, 60.0]))


def silhouette_mask(clip: Path, target: Path) -> None:
    """Estimate the moving centered silhouette from a median background plate."""
    import subprocess

    process = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(clip), "-vf", "fps=12",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
        capture_output=True, check=True)
    data = np.frombuffer(process.stdout, dtype=np.uint8)
    frames = data.reshape(-1, H, W, 3)
    plate = np.median(frames[::3], axis=0).astype(np.int16)
    yy, xx = np.mgrid[:H, :W]
    focus = (((xx - W * 0.5) / (W * 0.35)) ** 2 +
             ((yy - H * 0.38) / (H * 0.40)) ** 2) < 1
    masks = []
    for frame in frames:
        rgb = frame.astype(np.int16)
        difference = np.max(np.abs(rgb - plate), axis=2)
        darker = plate[:, :, 2] - rgb[:, :, 2]
        subject = focus & ((difference > 27) | (darker > 23)) & (rgb[:, :, 2] < 155)
        # The fixed pole also sits in front of the backlight.
        subject |= ((xx > W * 0.49) & (xx < W * 0.53) & (yy < H * 0.82))
        mask = Image.fromarray((subject * 255).astype(np.uint8), "L")
        masks.append(np.asarray(mask.filter(ImageFilter.MaxFilter(7)).filter(
            ImageFilter.GaussianBlur(4))).copy())
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = target.with_suffix(".raw")
    raw.write_bytes(np.stack(masks).tobytes())
    ffmpeg("-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}",
           "-r", "12", "-i", str(raw), "-c:v", "ffv1", str(target))
    raw.unlink(missing_ok=True)


def render_backlight_cross(target: Path) -> None:
    """A broad luminous cross intended for the wall behind the dancer."""
    shape = Image.new("L", (W, H), 0)
    draw = ImageDraw.Draw(shape)
    cx = W // 2
    draw.rectangle((cx - 11, 80, cx + 11, 475), fill=255)
    draw.rectangle((53, 210, W - 53, 231), fill=255)
    broad = shape.filter(ImageFilter.GaussianBlur(29)).point(
        lambda value: round(value * 0.42))
    near = shape.filter(ImageFilter.GaussianBlur(13)).point(
        lambda value: round(value * 0.27))
    alpha = ImageChops.add(broad, near)
    glow = Image.new("RGBA", (W, H), (250, 230, 235, 0))
    glow.putalpha(alpha)
    glow.save(target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--audio-start", type=float, default=73.7)
    args = parser.parse_args()
    for path in (args.video, args.audio):
        if not path.is_file():
            parser.error(f"File non trovato: {path}")
    duration, width, height = video_info(args.video)
    # The S24 stores portrait orientation as a rotation tag on landscape pixels.
    root = args.out.parent / "s24-heartbeat-assets"
    root.mkdir(parents=True, exist_ok=True)
    portrait = root / "s24-portrait-60fps.mp4"
    if not portrait.is_file():
        ffmpeg("-i", str(args.video), "-an", "-vf", f"scale={W}:{H}:flags=lanczos,fps={FPS}",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", str(portrait))
    duration, width, height = video_info(portrait)
    if width >= height:
        parser.error("La rotazione S24 non è stata applicata")
    os.environ.setdefault("NUMBA_CACHE_DIR", str(root / ".numba-cache"))
    from autoedit.beats import detect_beats

    beats = detect_beats(args.audio)
    frames = beat_cut_frames(beats, args.audio_start)
    slots = list(zip(frames, frames[1:]))
    finale_start = next(i for i, (a, _) in enumerate(slots) if a >= 50 * FPS)
    stops = [4 if i % 2 == 0 else 0 for i in range(len(slots))]
    speeds = [((0.6 if i % 2 == 0 else 1.35) if i < finale_start
               else (0.8 if (i - finale_start) % 2 == 0 else 3.0))
              for i in range(len(slots))]
    moving_durations = [(b - a - stop) / FPS
                        for (a, b), stop in zip(slots, stops)]
    if min(moving_durations) <= 0:
        parser.error("Un battito è troppo breve per la pausa prevista")
    finale_source = sum(moving_durations[i] * speeds[i]
                        for i in range(finale_start, len(slots)))
    intro_source = sum(moving_durations[i] * speeds[i] for i in range(finale_start))
    intro_scale = (duration - 0.18 - finale_source) / intro_source
    if not 0.5 < intro_scale < 1.5:
        parser.error("Impossibile adattare il video alla griglia musicale")
    speeds[:finale_start] = [speed * intro_scale for speed in speeds[:finale_start]]
    print(f"S24 60 fps: {len(slots)} intervalli, {finale_start} crescendo + "
          f"{len(slots) - finale_start} finale; nessuna foto", flush=True)
    print(f"Sorgente: 0–{duration - 0.18:.2f}s; fermo immagine di quattro frame "
          "su un battito sì e uno no", flush=True)

    cursor = 0.0
    rendered = []
    for index, ((start_frame, end_frame), stop_frames, speed, moving_duration) in enumerate(
            zip(slots, stops, speeds, moving_durations)):
        source_duration = moving_duration * speed
        print(f"Battito {index + 1}/{len(slots)}: {speed:.2f}×, "
              f"pausa {stop_frames} frame, sorgente {cursor:.2f}–"
              f"{cursor + source_duration:.2f}s", flush=True)
        source = root / f"source-{index + 1:02d}.mp4"
        ffmpeg("-ss", f"{cursor:.4f}", "-t", f"{source_duration:.4f}",
               "-i", str(portrait), "-an", "-c:v", "libx264",
               "-preset", "ultrafast", str(source))
        cursor += source_duration
        raw = root / f"beat-{index + 1:02d}-raw.mp4"
        finale = index >= finale_start
        build_video_segment(
            MediaItem(source, "video", duration=source_duration, best_start=0),
            moving_duration, W, H, FPS, "none", random.Random(index), raw,
            speed=speed, best_start=0, video_motion=False,
            finish="eq=brightness=-0.10" if finale else "eq=brightness=-0.17",
        )
        fixed = root / f"beat-{index + 1:02d}.mp4"
        frame_count = end_frame - start_frame
        # tpad clones the first frame for the musical stop, then moves on.
        ffmpeg("-i", str(raw), "-vf",
               f"fps={FPS},tpad=start_mode=clone:start={stop_frames}:"
               "stop_mode=clone:stop=4,"
               f"trim=end_frame={frame_count},setpts=PTS-STARTPTS,"
               "zoompan=z='1+0.022*exp(-on/6)':"
               "x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':"
               f"d=1:s={W}x{H}:fps={FPS}",
               "-frames:v", str(frame_count), "-an", "-c:v", "libx264",
               "-preset", "veryfast", str(fixed))
        rendered.append(fixed)

    concat_file = root / "scenes.ffconcat"
    concat_file.write_text("ffconcat version 1.0\n" +
                           "".join(f"file '{path.resolve()}'\n" for path in rendered),
                           encoding="utf-8")
    silent = root / "silent-video-only.mp4"
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(concat_file),
           "-an", "-c", "copy", str(silent))
    with_audio = root / "with-audio.mp4"
    ffmpeg("-i", str(silent), "-ss", f"{args.audio_start:.3f}", "-i", str(args.audio),
           "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-af",
           "afade=t=in:st=0:d=0.25,afade=t=out:st=59.75:d=0.25",
           "-t", "60", str(with_audio))
    cross = root / "cross-light-behind.png"
    render_backlight_cross(cross)
    # Vision sees the edited finale, including its held frames and speed ramps.
    finale_clip = root / "finale-for-mask.mp4"
    ffmpeg("-ss", "50", "-i", str(with_audio), "-t", "10", "-an",
           "-c:v", "libx264", "-preset", "veryfast", str(finale_clip))
    finale_mask = root / "finale-silhouette-mask.mkv"
    silhouette_mask(finale_clip, finale_mask)
    mask = root / "full-person-mask.mkv"
    ffmpeg("-f", "lavfi", "-i", f"color=black:s={W}x{H}:r=12:d=50",
           "-i", str(finale_mask), "-filter_complex",
           "[0:v]format=gray[blank];[1:v]format=gray[person];"
           "[blank][person]concat=n=2:v=1:a=0,format=gray[m]",
           "-map", "[m]", "-c:v", "ffv1", str(mask))
    pulses = [float(t) - args.audio_start for t in beats.beat_times
              if args.audio_start + 50 <= float(t) < args.audio_start + 60]
    enabled = "+".join(f"between(t,{t:.3f},{t + 0.08:.3f})" for t in pulses)
    graph = ("[0:v]split[original0][background];"
             f"[background][1:v]overlay=0:0:enable='{enabled}':"
             "eof_action=pass,format=gbrp[lit];"
             "[original0]format=gbrp[original];"
             "[2:v]format=gray,format=gbrp[person];"
             "[lit][original][person]maskedmerge,format=yuv420p[v]")
    ffmpeg("-i", str(with_audio), "-loop", "1", "-i", str(cross),
           "-i", str(mask),
           "-filter_complex", graph, "-map", "[v]", "-map", "0:a",
           "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
           "-c:a", "copy", "-t", "60", str(args.out))
    print(f"Anteprima pronta: {args.out}", flush=True)


if __name__ == "__main__":
    main()
