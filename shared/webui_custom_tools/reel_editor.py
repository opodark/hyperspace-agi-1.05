# SPDX-License-Identifier: Apache-2.0
"""Stage explicitly chosen media for the host-only Reel Editor."""

import json
import os
import shutil
import uuid
from pathlib import Path

from shared.webui_tool_registry import tool

MEDIA_EXT = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".m4v"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


@tool(description="Prepara un progetto Reel Editor da immagini Anna già approvate o da file in hyperspace_share. Può precompilare il profilo creator e il brief creativo. Non genera né pubblica il video. Indica nomi esatti, massimo 30; per Anna verifica la selezione visiva.")
def prepare_reel_project(source: str, filenames: list[str],
                         creator: str = "Altro progetto", brief: str = "",
                         audio_filename: str = "") -> dict:
    if source not in ("anna", "share"):
        raise ValueError("source deve essere anna o share")
    if creator not in ("Anna", "Aurora", "Altro progetto"):
        raise ValueError("creator deve essere Anna, Aurora o Altro progetto")
    if not isinstance(brief, str) or len(brief) > 4000:
        raise ValueError("brief deve essere testo di massimo 4000 caratteri")
    if not filenames or len(filenames) > 30:
        raise ValueError("Scegli da 1 a 30 file")
    share_root = Path(os.getenv("WEBUI_SHARE_DIR", "/app/hyperspace_share"))
    image_root = Path(os.getenv("WEBUI_ANNA_IMAGES_DIR", "/app/anna-images"))
    root = image_root if source == "anna" else share_root
    root = root.resolve(strict=True)
    approved = set()
    if source == "anna":
        for env, fallback in (("ANNA_REVIEW_STATE_FILE", "/app/data/anna-selection.json"),
                              ("ANNA_SECOND_PASS_STATE_FILE", "/app/data/anna-second-pass.json")):
            path = Path(os.getenv(env, fallback))
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                approved.update(name for name, result in data.get("results", {}).items()
                                if isinstance(result, dict) and result.get("esito") == "ok")
    sources = []
    for name in filenames:
        if not isinstance(name, str) or name != Path(name).name or name in (".", ".."):
            raise ValueError(f"Nome file non valido: {name!r}")
        if source == "anna" and name not in approved:
            raise ValueError(f"Immagine Anna non approvata: {name}")
        path = root / name
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in MEDIA_EXT:
            raise ValueError(f"Media non trovato o non ammesso: {name}")
        sources.append(path)
    audio_source = None
    if audio_filename:
        if (not isinstance(audio_filename, str) or audio_filename != Path(audio_filename).name
                or audio_filename in (".", "..")):
            raise ValueError("Nome file audio non valido")
        candidate = share_root.resolve(strict=True) / audio_filename
        if candidate.is_symlink() or not candidate.is_file() or candidate.suffix.lower() not in AUDIO_EXT:
            raise ValueError(f"Audio non trovato o formato non ammesso: {audio_filename}")
        audio_source = candidate
    projects = share_root.resolve(strict=True) / "reel-projects"
    projects.mkdir(exist_ok=True)
    project = projects / ("reel-" + uuid.uuid4().hex[:12])
    media = project / "media"
    media.mkdir(parents=True)
    try:
        for path in sources:
            shutil.copy2(path, media / path.name)
        audio_rel = ""
        if audio_source:
            audio_dir = project / "audio"
            audio_dir.mkdir()
            shutil.copy2(audio_source, audio_dir / audio_source.name)
            audio_rel = f"audio/{audio_source.name}"
        (project / "manifest.json").write_text(json.dumps({
            "source": source, "filenames": filenames,
            "creator": creator, "brief": brief,
            "audio_file": audio_rel,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        shutil.rmtree(project, ignore_errors=True)
        raise
    return {"project": project.name, "files": len(sources),
            "creator": creator, "audio": audio_source.name if audio_source else None,
            "message": "Progetto pronto. " + ("Puoi attivare la generazione giornaliera." if audio_source else "Per schedulare, prepara di nuovo il progetto indicando audio_filename: la musica deve essere già in hyperspace_share.")}


@tool(description="Attiva un Reel al giorno per il progetto indicato. Il render avviene sul Mac e finisce nella coda di revisione, senza pubblicazione. Default 09:00 Europe/Rome, 30 secondi.")
def reel_schedule_daily(project_id: str, daily_time: str = "09:00",
                        timezone_name: str = "Europe/Rome", duration: int = 30,
                        replace_existing: bool = False) -> dict:
    from shared import reel_daily
    return reel_daily.create_schedule(reel_daily.share_root(), project_id, daily_time,
                                      timezone_name, duration, replace_existing)


@tool(description="Mostra schedulazione e stato dell'ultimo render Reel giornaliero.")
def reel_daily_status() -> dict:
    from shared import reel_daily
    return reel_daily.get_status(reel_daily.share_root())


@tool(description="Accoda subito un render del Reel giornaliero, mantenendo la coda di revisione e senza pubblicarlo.")
def reel_render_now() -> dict:
    from shared import reel_daily
    return reel_daily.request_render_now(reel_daily.share_root())


@tool(description="Disattiva la generazione automatica giornaliera dei Reel.")
def reel_cancel_daily() -> dict:
    from shared import reel_daily
    return reel_daily.cancel_schedule(reel_daily.share_root())


@tool(description="Accoda una prova locale con zoom sul soggetto e lampi elettrici sui beat. Richiede MP4 verticale e audio nella radice di hyperspace_share; il livello karaoke MOV è facoltativo. L'anteprima va in reel-review; non pubblica.")
def reel_subject_fx_preview(video_filename: str, audio_filename: str,
                            karaoke_filename: str = "") -> dict:
    from shared import reel_fx
    return reel_fx.queue_preview(reel_fx.share_root(), video_filename,
                                 audio_filename, karaoke_filename)


@tool(description="Mostra lo stato e il file di revisione di una prova Reel con effetti sul soggetto.")
def reel_subject_fx_status(job_id: str) -> dict:
    from shared import reel_fx
    return reel_fx.get_status(reel_fx.share_root(), job_id)
