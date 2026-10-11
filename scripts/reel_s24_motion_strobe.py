#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replace the final ten seconds with five stop/jump motion cycles per beat."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

W, H, FPS = 1080, 1920, 60
FRAME_BYTES = W * H * 3 // 2  # yuv420p


def run(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def source_indices(timeline: list[dict]) -> tuple[list[int], float, float]:
    beats = [item for item in timeline if float(item["output_start"]) >= 50]
    if not beats or float(beats[0]["output_start"]) != 50:
        raise ValueError("Il finale deve iniziare al secondo 50")
    source_begin = float(beats[0]["source_start"])
    source_end = float(beats[-1]["source_end"])
    source_span = source_end - source_begin
    indices: list[int] = []
    for beat in beats:
        first = round((float(beat["output_start"]) - 50) * FPS)
        last = round((float(beat["output_end"]) - 50) * FPS)
        count = last - first
        cycles = min(5, count // 4)
        if cycles < 4:
            raise ValueError("Battito troppo breve per gli impulsi di movimento")
        for cycle in range(cycles):
            cycle_first = round(cycle * count / cycles)
            cycle_last = round((cycle + 1) * count / cycles)
            cycle_frames = cycle_last - cycle_first
            if cycle_frames < 4:
                raise ValueError("Impulso di movimento troppo breve")
            for local in range(cycle_frames):
                # Two held frames, then a jump through the next source frames.
                phase = 0.0 if local < 2 else (local - 1) / (cycle_frames - 2)
                output_fraction = (first + (cycle + phase) * count / cycles) / (10 * FPS)
                index = round(output_fraction * source_span * FPS)
                indices.append(index)
    if len(indices) != 10 * FPS or any(b < a for a, b in zip(indices, indices[1:])):
        raise ValueError("Mappa dei fotogrammi non continua")
    return indices, source_begin, source_end


def read_frame(stream) -> bytes:
    chunks = []
    remaining = FRAME_BYTES
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise EOFError("Il girato S24 è finito prima del fotogramma richiesto")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def render_finale(source: Path, indices: list[int], source_begin: float, out: Path) -> None:
    decoder = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-ss", f"{source_begin:.6f}", "-i", str(source),
         "-an", "-frames:v", str(indices[-1] + 1), "-pix_fmt", "yuv420p",
         "-f", "rawvideo", "pipe:1"],
        stdout=subprocess.PIPE)
    encoder = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "yuv420p",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "15",
         "-pix_fmt", "yuv420p", str(out)],
        stdin=subprocess.PIPE)
    assert decoder.stdout is not None and encoder.stdin is not None
    current_index = -1
    frame = b""
    try:
        for output_index, wanted in enumerate(indices):
            while current_index < wanted:
                frame = read_frame(decoder.stdout)
                current_index += 1
            encoder.stdin.write(frame)
            if (output_index + 1) % 120 == 0:
                print(f"Movimento finale: {output_index + 1}/600 fotogrammi", flush=True)
    finally:
        encoder.stdin.close()
        decoder.stdout.close()
        if decoder.wait() != 0:
            raise RuntimeError("Decodifica del girato S24 fallita")
    if encoder.wait() != 0:
        raise RuntimeError("Codifica del finale stroboscopico fallita")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True,
                        help="S24 verticale normalizzato a 1080x1920/60 fps")
    parser.add_argument("--video", type=Path, required=True,
                        help="Reel con lyrics prima del finale")
    parser.add_argument("--timeline", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.source, args.video, args.timeline):
        if not path.is_file():
            parser.error(f"File mancante: {path}")
    root = args.out.parent / "s24-motion-strobe-assets"
    root.mkdir(parents=True, exist_ok=True)
    timeline = json.loads(args.timeline.read_text(encoding="utf-8"))
    indices, source_begin, source_end = source_indices(timeline)
    repeats = sum(b == a for a, b in zip(indices, indices[1:]))
    print(f"Finale sorgente {source_begin:.3f}–{source_end:.3f}s; "
          f"5 cicli stop/scatto per battito, {repeats} frame ripetuti", flush=True)
    (root / "source-frame-map.json").write_text(
        json.dumps({"source_begin": source_begin, "source_end": source_end,
                    "output_fps": FPS, "source_frame_indices": indices}, indent=2),
        encoding="utf-8")
    finale = root / "finale-motion-10s.mp4"
    render_finale(args.source, indices, source_begin, finale)
    graph = ("[0:v]trim=end_frame=3000,setpts=PTS-STARTPTS[intro];"
             "[1:v]trim=end_frame=600,setpts=PTS-STARTPTS[finale];"
             "[intro][finale]concat=n=2:v=1:a=0[v]")
    run("-i", str(args.video), "-i", str(finale), "-filter_complex", graph,
        "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "copy", "-t", "60", str(args.out))
    print(f"Reel con movimento stroboscopico: {args.out}", flush=True)


if __name__ == "__main__":
    main()
