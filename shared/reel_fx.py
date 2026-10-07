# SPDX-License-Identifier: Apache-2.0
"""Queue local subject FX previews requested by WebUI or native CP tools."""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

from shared.reel_daily import _atomic_json

JOB_ID = re.compile(r"^[0-9a-f]{12}$")
VIDEO_EXT = {".mp4", ".mov"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


def share_root() -> Path:
    return Path(os.getenv("WEBUI_SHARE_DIR", "/app/hyperspace_share")).expanduser().resolve()


def _source(root: Path, name: str, extensions: set[str]) -> Path:
    if not isinstance(name, str) or not name or name != Path(name).name or name in (".", ".."):
        raise ValueError("Indica un nome file presente nella radice di hyperspace_share")
    path = root / name
    if path.is_symlink() or path.suffix.lower() not in extensions or not path.is_file():
        raise ValueError(f"File non trovato o formato non ammesso: {name}")
    resolved = path.resolve(strict=True)
    if resolved.parent != root:
        raise ValueError("Il file deve essere nella radice dell'area condivisa")
    return resolved


def queue_preview(root: Path, video_filename: str, audio_filename: str,
                  karaoke_filename: str = "") -> dict:
    root = root.resolve(strict=True)
    _source(root, video_filename, VIDEO_EXT)
    _source(root, audio_filename, AUDIO_EXT)
    if karaoke_filename:
        _source(root, karaoke_filename, {".mov"})
    job_id = uuid.uuid4().hex[:12]
    directory = root / "reel-fx-jobs"
    request = {
        "job_id": job_id, "video_filename": video_filename,
        "audio_filename": audio_filename, "karaoke_filename": karaoke_filename,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    _atomic_json(directory / "pending" / f"{job_id}.json", request)
    _atomic_json(directory / "status" / f"{job_id}.json", {
        "job_id": job_id, "status": "queued", "created_at": request["created_at"],
    })
    return {"ok": True, "job_id": job_id, "status": "queued",
            "message": "Anteprima con zoom e lampi sulla sagoma accodata sul Mac. Nessuna pubblicazione social."}


def get_status(root: Path, job_id: str) -> dict:
    if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id):
        raise ValueError("job_id non valido")
    path = root.resolve(strict=True) / "reel-fx-jobs" / "status" / f"{job_id}.json"
    if not path.is_file() or path.is_symlink():
        raise ValueError("Job Reel FX non trovato")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("job_id") != job_id:
        raise ValueError("Stato job non valido")
    return data
