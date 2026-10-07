#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Mac worker for WebUI-requested subject FX previews in hyperspace_share."""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from shared.reel_daily import _atomic_json
from shared.reel_fx import _source, AUDIO_EXT, VIDEO_EXT

PYTHON = Path("/Users/opo/Downloads/tiktok_editor/.venv/bin/python")
SHARE = Path(os.getenv("HYPERSPACE_SHARE_DIR", "/Users/opo/hyperspace_share"))


def _probe(path: Path) -> dict:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,width,height", "-of", "json", str(path),
    ], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError("MP4 non verificabile: " + result.stderr[-500:])
    return json.loads(result.stdout)


def tick(root: Path = SHARE) -> dict | None:
    root = root.resolve(strict=True)
    jobs = root / "reel-fx-jobs"
    pending = jobs / "pending"
    if not pending.is_dir():
        return None
    jobs.mkdir(exist_ok=True)
    with (jobs / ".worker.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return None
        requests = sorted(pending.glob("*.json"))
        if not requests:
            return None
        request_path = requests[0]
        running = jobs / "running"
        running.mkdir(exist_ok=True)
        claimed = running / request_path.name
        os.replace(request_path, claimed)
        request = json.loads(claimed.read_text(encoding="utf-8"))
        job_id = request["job_id"]
        status_path = jobs / "status" / f"{job_id}.json"
        final = root / "reel-review" / f"fx-{job_id}.mp4"
        final.parent.mkdir(exist_ok=True)
        partial = final.with_suffix(".partial.mp4")
        state = {"job_id": job_id, "status": "rendering",
                 "started_at": datetime.now().astimezone().isoformat(timespec="seconds")}
        _atomic_json(status_path, state)
        try:
            video = _source(root, request["video_filename"], VIDEO_EXT)
            audio = _source(root, request["audio_filename"], AUDIO_EXT)
            karaoke_name = request.get("karaoke_filename") or ""
            karaoke = _source(root, karaoke_name, {".mov"}) if karaoke_name else None
            before = _probe(video)
            duration = float(before["format"]["duration"])
            if not any(s.get("codec_type") == "video" and s.get("width") == 1080
                       and s.get("height") == 1920 for s in before.get("streams", [])):
                raise ValueError("Il video sorgente deve essere verticale 1080x1920")
            if duration < 2 or duration > 180:
                raise ValueError("Durata video ammessa: 2–180 secondi")
            command = [
                str(PYTHON), str(REPO / "scripts" / "reel_subject_fx.py"),
                "--video", str(video), "--audio", str(audio),
                "--out", str(partial),
                "--assets", str(jobs / "assets" / job_id),
                "--duration", str(duration),
            ]
            if karaoke:
                command += ["--karaoke-alpha", str(karaoke)]
            result = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                                    timeout=4 * 60 * 60)
            if result.returncode:
                raise RuntimeError((result.stderr or result.stdout or "Render FX fallito")[-2000:])
            after = _probe(partial)
            if not any(s.get("codec_type") == "audio" for s in after.get("streams", [])):
                raise RuntimeError("L'anteprima non contiene audio")
            if not any(s.get("codec_type") == "video" and s.get("width") == 1080
                       and s.get("height") == 1920 for s in after.get("streams", [])):
                raise RuntimeError("L'anteprima non è 1080x1920")
            actual = float(after["format"]["duration"])
            if abs(actual - duration) > .25:
                raise RuntimeError("Durata anteprima diversa dalla sorgente")
            os.replace(partial, final)
            effects = json.loads((jobs / "assets" / job_id / "result.json").read_text())
            state.update(status="needs_review", output_rel=f"reel-review/{final.name}",
                         duration_seconds=actual, effects=effects)
        except Exception as exc:
            partial.unlink(missing_ok=True)
            state.update(status="failed", error=str(exc)[-2000:])
        finally:
            claimed.unlink(missing_ok=True)
        state["completed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        _atomic_json(status_path, state)
        return state


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--share", type=Path, default=SHARE)
    args = parser.parse_args()
    result = tick(args.share)
    if result:
        print(json.dumps(result, ensure_ascii=False))
