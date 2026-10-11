#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Sync the first 50 seconds of S24 movement to estimated harmonic note edges."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

import numpy as np

from reel_s24_motion_strobe import FPS, H, W, read_frame, run


def note_edges(audio: Path, audio_start: float, prominence: float,
               min_gap: float, cqt_out: Path | None = None) -> tuple[list[int], list[float]]:
    import librosa
    from scipy.ndimage import gaussian_filter1d
    from scipy.signal import find_peaks

    audio_bytes = subprocess.check_output(
        ["ffmpeg", "-v", "error", "-ss", f"{audio_start:.3f}", "-t", "50",
         "-i", str(audio), "-ac", "1", "-ar", "22050", "-f", "f32le", "pipe:1"])
    samples = np.frombuffer(audio_bytes, dtype=np.float32)
    stft = librosa.stft(samples, n_fft=2048, hop_length=256)
    harmonic = librosa.decompose.hpss(stft)[0]
    harmonic_audio = librosa.istft(harmonic, hop_length=256, length=len(samples))
    cqt = np.abs(librosa.cqt(harmonic_audio, sr=22050, hop_length=256,
                             fmin=librosa.note_to_hz("G3"), n_bins=36,
                             bins_per_octave=12))
    if cqt_out is not None:
        np.savez_compressed(cqt_out, cqt=cqt)
    features = np.log1p(cqt * 4)
    features = (features - np.median(features, axis=1, keepdims=True)) / (
        np.std(features, axis=1, keepdims=True) + 0.15)
    features = gaussian_filter1d(features, 8, axis=1)
    features /= np.linalg.norm(features, axis=0, keepdims=True) + 1e-9
    lag = 18
    novelty = np.zeros(features.shape[1], dtype=np.float32)
    novelty[lag:-lag] = np.linalg.norm(features[:, lag * 2:] -
                                        features[:, :-lag * 2], axis=0)
    novelty = gaussian_filter1d(novelty, 6)
    peaks, _ = find_peaks(novelty,
                          distance=round(min_gap * 22050 / 256),
                          prominence=prominence)
    boundaries = [0, *(round(float(index) * 256 / 22050 * FPS) for index in peaks),
                  50 * FPS]
    boundaries = sorted(set(frame for frame in boundaries if 0 <= frame <= 50 * FPS))
    strengths = [round(float(novelty[index]), 3) for index in peaks]
    return boundaries, strengths


def frame_map(boundaries: list[int], source_seconds: float,
              hold_frames: int = 3) -> list[int]:
    indices = []
    for begin, end in zip(boundaries, boundaries[1:]):
        length = end - begin
        if length < hold_frames * 2 + 2:
            raise ValueError("Note troppo ravvicinate per i fermi richiesti")
        for offset in range(length):
            if offset < hold_frames:
                progress = 0.0
            elif offset >= length - hold_frames:
                progress = 1.0
            else:
                position = (offset - hold_frames) / (length - 2 * hold_frames - 1)
                progress = position * position * (3 - 2 * position)
            output_fraction = (begin + progress * length) / (50 * FPS)
            indices.append(round(output_fraction * source_seconds * FPS))
    if len(indices) != 50 * FPS or any(b < a for a, b in zip(indices, indices[1:])):
        raise ValueError("Mappa delle note non continua")
    return indices


def render_intro(source: Path, indices: list[int], target: Path) -> None:
    decoder = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(source), "-an",
         "-frames:v", str(indices[-1] + 1), "-pix_fmt", "yuv420p",
         "-f", "rawvideo", "pipe:1"], stdout=subprocess.PIPE)
    encoder = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "yuv420p",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "15",
         "-pix_fmt", "yuv420p", str(target)], stdin=subprocess.PIPE)
    assert decoder.stdout is not None and encoder.stdin is not None
    current = -1
    frame = b""
    try:
        for output_index, wanted in enumerate(indices):
            while current < wanted:
                frame = read_frame(decoder.stdout)
                current += 1
            encoder.stdin.write(frame)
            if (output_index + 1) % 600 == 0:
                print(f"Movimento sulle note: {output_index + 1}/3000 frame", flush=True)
    finally:
        encoder.stdin.close()
        decoder.stdout.close()
        if decoder.wait() != 0:
            raise RuntimeError("Decodifica del video S24 fallita")
    if encoder.wait() != 0:
        raise RuntimeError("Codifica del movimento sulle note fallita")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--final-video", type=Path, required=True)
    parser.add_argument("--lyrics-alpha", type=Path, required=True)
    parser.add_argument("--timeline", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--audio-start", type=float, default=73.7)
    parser.add_argument("--note-prominence", type=float, default=0.10)
    parser.add_argument("--minimum-note-gap", type=float, default=0.48)
    args = parser.parse_args()
    for path in (args.source, args.audio, args.final_video,
                 args.lyrics_alpha, args.timeline):
        if not path.is_file():
            parser.error(f"File mancante: {path}")
    root = args.out.parent / "s24-note-experiments"
    root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NUMBA_CACHE_DIR", str(root / ".numba-cache"))
    timeline = json.loads(args.timeline.read_text(encoding="utf-8"))
    source_end = next(float(item["source_start"]) for item in timeline
                      if float(item["output_start"]) >= 50)
    boundaries, strengths = note_edges(args.audio, args.audio_start,
                                       args.note_prominence, args.minimum_note_gap,
                                       root / "bagpipe-cqt.npz")
    indices = frame_map(boundaries, source_end)
    intervals = [{"start": round(a / FPS, 3), "end": round(b / FPS, 3)}
                 for a, b in zip(boundaries, boundaries[1:])]
    (root / "note-cues.json").write_text(json.dumps({
        "method": "harmonic CQT novelty; approximate bagpipe note changes amid vocals",
        "audio_start": args.audio_start, "prominence": args.note_prominence,
        "minimum_gap": args.minimum_note_gap, "intervals": intervals,
        "boundary_strengths": strengths}, indent=2), encoding="utf-8")
    (root / "intro-frame-map.json").write_text(json.dumps({
        "source_end": source_end, "source_frame_indices": indices}, indent=2),
        encoding="utf-8")
    print(f"{len(intervals)} intervalli armonici stimati; "
          f"sorgente iniziale 0–{source_end:.3f}s", flush=True)
    intro = root / "intro-note-motion-50s.mp4"
    render_intro(args.source, indices, intro)
    graph = (f"[2:v]scale={W}:{H}:flags=lanczos[lyrics];"
             "[0:v][lyrics]overlay=0:0:eof_action=pass,"
             "trim=end_frame=3000,setpts=PTS-STARTPTS[intro];"
             "[1:v]trim=start_frame=3000:end_frame=3600,"
             "setpts=PTS-STARTPTS[finale];"
             "[intro][finale]concat=n=2:v=1:a=0[v]")
    run("-i", str(intro), "-i", str(args.final_video),
        "-i", str(args.lyrics_alpha), "-filter_complex", graph,
        "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "copy", "-t", "60",
        str(args.out))
    print(f"Anteprima note + finale beat: {args.out}", flush=True)


if __name__ == "__main__":
    main()
