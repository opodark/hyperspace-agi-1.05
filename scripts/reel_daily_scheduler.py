#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Mac host worker: render scheduled Reel drafts into a local review queue."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
EDITOR = REPO / "integrations" / "tiktok_editor" / "app"
PYTHON = Path("/Users/opo/Downloads/tiktok_editor/.venv/bin/python")
SHARE = Path(os.getenv("HYPERSPACE_SHARE_DIR", "/Users/opo/hyperspace_share")).expanduser()
sys.path.insert(0, str(REPO))
from shared.reel_daily import _project, _schedule_lock


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="." + path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def _due(config: dict, now: datetime) -> tuple[bool, str]:
    local = now.astimezone(ZoneInfo(config["timezone"]))
    due_minute = config["daily_time"]
    return (local.strftime("%H:%M") >= due_minute and
            config.get("last_run_date") != local.date().isoformat(), local.date().isoformat())


def _arguments(config: dict, audio: Path, output: Path, duration: int, seed: int,
               root: Path = SHARE) -> list[str]:
    media = root / config["project_rel"] / "media"
    return [str(PYTHON), str(EDITOR / "run.py"), "--media-dir", str(media),
            "--audio", str(audio), "--out", str(output), "--aspect", "9:16", "--fps", "30",
            "--style", "vivid", "--edit-style", "custom", "--motion", "bounce",
            "--motion-intensity", "1.35", "--cuts-per-beat", "2", "--dynamic-pacing",
            "--transitions", "chaos", "--impact", "flash", "glitch", "shake",
            "--variety", "0.7", "--grain", "0.08", "--vignette", "--chromatic",
            "--target-duration", str(duration), "--seed", str(seed), "--shuffle", "--jobs", "2", "--separate-person",
            "--subject-style", "neon", "--background-style", "moody",
            "--background-blur", "0.5", "--background-dim", "0.18", "--subject-spot", "0.08",
            "--outline-color", "cyan", "--outline-strength", "0.8", "--outline-width", "4"]


def render(config: dict, day: str, manual: bool = False, root: Path = SHARE) -> dict:
    root = root.resolve(strict=True)
    queue = root / "reel-review"
    queue.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:12]
    final = queue / f"{day}-{config['creator'].lower().replace(' ', '-')}-{run_id}.mp4"
    partial = final.with_suffix(".partial.mp4")
    status_path = root / "reel-schedules" / "status.json"
    state = {"status": "rendering", "run_id": run_id, "project_id": config["project_id"],
             "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
             "output": str(final), "manual": manual}
    _write_json(status_path, state)
    try:
        project, _, _, audio = _project(root, config["project_id"])
        config = dict(config, project_rel=str(project.relative_to(root)))
        editor_python = PYTHON
        if not editor_python.is_file():
            raise RuntimeError(f"Ambiente editor non trovato: {editor_python}")
        result = subprocess.run(_arguments(config, audio, partial, int(config["duration"]),
                                           int(day.replace("-", "")), root), cwd=EDITOR,
                               capture_output=True, text=True, timeout=4 * 60 * 60)
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout or f"autoedit exit {result.returncode}")[-5000:])
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
                                "-of", "json", str(partial)],
                               capture_output=True, text=True, timeout=30)
        if probe.returncode or not partial.is_file():
            raise RuntimeError("Render completato senza un MP4 verificabile: " + probe.stderr[-1000:])
        metadata = json.loads(probe.stdout)
        streams = metadata.get("streams", [])
        if not any(s.get("codec_type") == "audio" for s in streams):
            raise RuntimeError("Il render non contiene audio")
        if not any(s.get("codec_type") == "video" and s.get("width") == 1080
                   and s.get("height") == 1920 for s in streams):
            raise RuntimeError("Il render non contiene video verticale 1080x1920")
        actual = float(metadata["format"]["duration"])
        if abs(actual - int(config["duration"])) > 0.25:
            raise RuntimeError(f"Durata render non valida: {actual:.3f}s")
        os.replace(partial, final)
        state.update(status="needs_review", completed_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                     duration_seconds=actual)
    except Exception as exc:
        partial.unlink(missing_ok=True)
        state.update(status="failed", completed_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                     error=str(exc)[-5000:])
    _write_json(status_path, state)
    _write_json(queue / f"{run_id}.json", state)
    return state


def tick(root: Path | None = None, now: datetime | None = None) -> dict | None:
    root = (root or SHARE).resolve()
    directory = root / "reel-schedules"
    config_path = directory / "current.json"
    if not config_path.is_file():
        return None
    with (directory / ".scheduler.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return None
        # Short shared lock: cancellation/replacement cannot be overwritten by a claim.
        with _schedule_lock(directory):
            config = json.loads(config_path.read_text(encoding="utf-8"))
            if not config.get("enabled"):
                return None
            now = now or datetime.now().astimezone()
            manual_path = directory / "render-now.json"
            manual = manual_path.is_file()
            due, day = _due(config, now)
            if not manual and not due:
                return None
            if manual:
                request = json.loads(manual_path.read_text(encoding="utf-8"))
                manual_path.unlink()
                if request.get("schedule_id") != config["schedule_id"]:
                    return None
            # A manual render also supplies today's Reel, avoiding a second daily run.
            config["last_run_date"] = day
            _write_json(config_path, config)
        return render(config, day, manual, root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Esegue un singolo tick e termina")
    parser.add_argument("--share", type=Path, default=SHARE)
    args = parser.parse_args()
    tick(args.share)
    from scripts.reel_fx_worker import tick as fx_tick
    fx_tick(args.share)
    return 0


if __name__ == "__main__":
    sys.exit(main())
