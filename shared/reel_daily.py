# SPDX-License-Identifier: Apache-2.0
"""Safe schedule handoff from HyperSpace tools to the local Reel Editor."""
from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


PROJECT_ID = re.compile(r"^reel-[0-9a-f]{12}$")
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


def share_root() -> Path:
    return Path(os.getenv("WEBUI_SHARE_DIR", "/app/hyperspace_share")).expanduser().resolve()


def schedule_dir(root: Path) -> Path:
    return root / "reel-schedules"


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def _project(root: Path, project_id: str) -> tuple[Path, dict, Path, Path]:
    if not isinstance(project_id, str) or not PROJECT_ID.fullmatch(project_id):
        raise ValueError("project_id deve essere il codice reel-<12 caratteri esadecimali>")
    project = root / "reel-projects" / project_id
    manifest_path = project / "manifest.json"
    resolved_project = project.resolve()
    if (project.is_symlink() or not resolved_project.is_relative_to(root)
            or not manifest_path.is_file()):
        raise ValueError("Progetto Reel non trovato nell'area condivisa")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("Manifest progetto non valido")
    media = project / "media"
    usable = [p for p in media.iterdir() if p.is_file() and not p.is_symlink()
              and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".m4v"}] if media.is_dir() else []
    if media.is_symlink() or not usable:
        raise ValueError("Il progetto non contiene media utilizzabili")
    audio_rel = manifest.get("audio_file")
    if not isinstance(audio_rel, str):
        raise ValueError("Il progetto non ha una traccia audio; preparalo indicando audio_filename")
    rel = PurePosixPath(audio_rel)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise ValueError("Percorso audio nel manifest non valido")
    raw_audio = project / Path(*rel.parts)
    if raw_audio.is_symlink():
        raise ValueError("La traccia audio non può essere un collegamento simbolico")
    audio = raw_audio.resolve(strict=True)
    if not audio.is_relative_to(resolved_project) or audio.suffix.lower() not in AUDIO_EXT:
        raise ValueError("Traccia audio fuori dal progetto o formato non ammesso")
    if not audio.is_file():
        raise ValueError("Traccia audio non trovata")
    return project, manifest, media, audio


def validate_schedule(root: Path, project_id: str, daily_time: str,
                      timezone_name: str, duration: int) -> dict:
    root = root.resolve(strict=True)
    if not isinstance(daily_time, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", daily_time):
        raise ValueError("daily_time deve essere HH:MM, per esempio 09:00")
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, TypeError, ValueError) as exc:
        raise ValueError("Fuso orario IANA non riconosciuto") from exc
    if isinstance(duration, bool) or duration not in (30, 60):
        raise ValueError("duration deve essere 30 oppure 60")
    project, manifest, _, audio = _project(root, project_id)
    creator = manifest.get("creator", "Altro progetto")
    if creator not in ("Anna", "Aurora", "Altro progetto"):
        raise ValueError("Profilo creator nel manifest non valido")
    return {
        "version": 1,
        "enabled": True,
        "schedule_id": uuid.uuid4().hex[:12],
        "project_id": project_id,
        "project_rel": str(project.resolve().relative_to(root)),
        "creator": creator,
        "audio_rel": str(audio.relative_to(root)),
        "daily_time": daily_time,
        "timezone": timezone_name,
        "duration": duration,
        "profile": "psychedelic_outline",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def create_schedule(root: Path, project_id: str, daily_time: str = "09:00",
                    timezone_name: str = "Europe/Rome", duration: int = 30,
                    replace_existing: bool = False) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Area condivisa non disponibile")
    directory = schedule_dir(root)
    lock = _schedule_lock(directory)
    path = directory / "current.json"
    try:
        candidate = validate_schedule(root, project_id, daily_time, timezone_name, duration)
        if path.exists():
            current = json.loads(path.read_text(encoding="utf-8"))
            if current.get("enabled") and not replace_existing:
                raise ValueError("Esiste già una schedulazione attiva. Imposta replace_existing=true per sostituirla.")
        _atomic_json(path, candidate)
        (directory / "render-now.json").unlink(missing_ok=True)
    finally:
        lock.close()
    return {"ok": True, "schedule_id": candidate["schedule_id"],
            "creator": candidate["creator"], "daily_time": daily_time,
            "timezone": timezone_name, "duration": duration,
            "message": "Schedulazione attiva: ogni giorno il Reel sarà generato nella coda locale di revisione; non verrà pubblicato."}


def cancel_schedule(root: Path) -> dict:
    directory = schedule_dir(root)
    lock = _schedule_lock(directory)
    path = directory / "current.json"
    try:
        if not path.is_file():
            return {"ok": True, "enabled": False, "message": "Nessuna schedulazione Reel attiva."}
        current = json.loads(path.read_text(encoding="utf-8"))
        current["enabled"] = False
        current["cancelled_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        _atomic_json(path, current)
        (directory / "render-now.json").unlink(missing_ok=True)
    finally:
        lock.close()
    return {"ok": True, "enabled": False, "schedule_id": current.get("schedule_id"),
            "message": "Schedulazione disattivata; i Reel già in revisione restano disponibili."}


def request_render_now(root: Path) -> dict:
    directory = schedule_dir(root)
    lock = _schedule_lock(directory)
    try:
        config_path = directory / "current.json"
        config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
        if not config.get("enabled"):
            raise ValueError("Attiva prima una schedulazione Reel")
        request_path = directory / "render-now.json"
        if request_path.exists():
            raise ValueError("È già in coda una richiesta di render immediato")
        request_id = uuid.uuid4().hex[:12]
        _atomic_json(request_path, {"request_id": request_id, "schedule_id": config["schedule_id"],
                                    "created_at": datetime.now().astimezone().isoformat(timespec="seconds")})
    finally:
        lock.close()
    return {"ok": True, "request_id": request_id,
            "message": "Render aggiunto alla coda locale; l'MP4 sarà consegnato per revisione."}


def _schedule_lock(directory: Path):
    """Serialize tool writes to the single active schedule on the shared volume."""
    import fcntl
    directory.mkdir(parents=True, exist_ok=True)
    stream = (directory / ".schedule-write.lock").open("a+")
    fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
    return stream


def get_status(root: Path) -> dict:
    directory = schedule_dir(root)
    config_path = directory / "current.json"
    state_path = directory / "status.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else None
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else None
    return {"schedule": config, "latest_run": state,
            "queued_now": (directory / "render-now.json").is_file()}
