#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Cut the original S24 recording to music at 1080x1920/60 without image effects."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "integrations" / "tiktok_editor" / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from reel_s24_heartbeat_60fps import beat_cut_frames  # noqa: E402

W, H, FPS = 1080, 1920, 60


def run(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
         "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True)
    return float(result.stdout.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--audio-start", type=float, default=73.7)
    args = parser.parse_args()
    if not args.video.is_file() or not args.audio.is_file():
        parser.error("Video o audio mancante")
    root = args.out.parent / "s24-clean-speedramp-assets"
    root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NUMBA_CACHE_DIR", str(root / ".numba-cache"))
    from autoedit.beats import detect_beats

    source = root / "portrait-1080x1920-60fps.mp4"
    if not source.is_file():
        print("Preparo il girato S24 a 1080x1920, 60 fps...", flush=True)
        run("-i", str(args.video), "-an", "-vf",
            f"scale={W}:{H}:flags=lanczos,fps={FPS}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "15",
            "-pix_fmt", "yuv420p", str(source))

    beats = detect_beats(args.audio)
    boundaries = beat_cut_frames(beats, args.audio_start)
    slots = list(zip(boundaries, boundaries[1:]))
    finale = next(i for i, (start, _) in enumerate(slots) if start >= 50 * FPS)
    stops = [((8 if i % 2 == 0 else 0) if i < finale
              else (12 if (i - finale) % 2 == 0 else 0)) for i in range(len(slots))]
    moving = [(end - start - stops[i]) / FPS
              for i, (start, end) in enumerate(slots)]
    if min(moving) <= 0:
        parser.error("Battito troppo breve per lo stop previsto")
    speeds = [(0.35 if i % 2 == 0 else 2.4) if i < finale
              else (0.25 if (i - finale) % 2 == 0 else 5.0)
              for i in range(len(slots))]
    available = duration(source) - 0.18
    finale_source = sum(moving[i] * speeds[i] for i in range(finale, len(slots)))
    intro_source = sum(moving[i] * speeds[i] for i in range(finale))
    intro_scale = (available - finale_source) / intro_source
    speeds[:finale] = [speed * intro_scale for speed in speeds[:finale]]
    if not 0.15 <= min(speeds) and max(speeds) <= 5:
        parser.error("Velocità fuori intervallo")
    print(f"{len(slots)} battiti; preparazione {min(speeds[:finale]):.2f}–"
          f"{max(speeds[:finale]):.2f}×, finale 0.25–5.00×; "
          "stop di 8/12 fotogrammi", flush=True)

    cursor = 0.0
    clips = []
    timeline = []
    for i, ((begin, end), hold, motion, speed) in enumerate(zip(slots, stops, moving, speeds)):
        frame_count = end - begin
        source_len = motion * speed
        clip = root / f"beat-{i + 1:02d}.mp4"
        # One encode per cut. No blur, grade, zoom or glow.
        vf = (f"setpts=(PTS-STARTPTS)/{speed:.8f},fps={FPS},"
              f"tpad=start_mode=clone:start={hold}:stop_mode=clone:stop=8,"
              f"trim=end_frame={frame_count},setpts=PTS-STARTPTS")
        run("-ss", f"{cursor:.6f}", "-t", f"{source_len:.6f}", "-i", str(source),
            "-vf", vf, "-frames:v", str(frame_count), "-an", "-c:v", "libx264",
            "-preset", "veryfast", "-crf", "15", "-pix_fmt", "yuv420p", str(clip))
        clips.append(clip)
        timeline.append({"beat": i + 1, "output_start": round(begin / FPS, 3),
                         "output_end": round(end / FPS, 3), "source_start": round(cursor, 3),
                         "source_end": round(cursor + source_len, 3),
                         "speed": round(speed, 3), "hold_frames": hold})
        cursor += source_len
        if (i + 1) % 10 == 0 or i + 1 == len(slots):
            print(f"Montati {i + 1}/{len(slots)} battiti", flush=True)
    (root / "timeline.json").write_text(json.dumps(timeline, indent=2), encoding="utf-8")
    concat = root / "scenes.ffconcat"
    concat.write_text("ffconcat version 1.0\n" + "".join(
        f"file '{clip.resolve()}'\n" for clip in clips), encoding="utf-8")
    run("-f", "concat", "-safe", "0", "-i", str(concat),
        "-ss", f"{args.audio_start:.3f}", "-i", str(args.audio),
        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
        "-b:a", "256k", "-af", "afade=t=in:st=0:d=0.25,afade=t=out:st=59.75:d=0.25",
        "-t", "60", str(args.out))
    print(f"Master pulito: {args.out}", flush=True)


if __name__ == "__main__":
    main()
