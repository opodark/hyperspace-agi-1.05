# SPDX-License-Identifier: Apache-2.0
"""
Modulo Trascrizione Audio (STT) per HyperSpace.

Supporta la conversione e trascrizione di messaggi vocali (Telegram, WebUI, file audio)
utilizzando ffmpeg e Whisper.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Optional

logger = logging.getLogger("audio_transcriber")

WHISPER_BIN = os.getenv("WHISPER_BIN", "/opt/homebrew/bin/whisper")
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "/opt/homebrew/bin/ffmpeg")
DEFAULT_MODEL = os.getenv("WHISPER_MODEL", "tiny")


def is_stt_available() -> bool:
    return os.path.exists(WHISPER_BIN) and os.path.exists(FFMPEG_BIN)


def transcribe_audio(audio_path: str | Path, language: str = "it", model: str = DEFAULT_MODEL) -> str:
    """Trascrive un file audio in testo usando Whisper."""
    if not is_stt_available():
        raise RuntimeError(f"Whisper o ffmpeg non disponibili (whisper: {WHISPER_BIN}, ffmpeg: {FFMPEG_BIN})")

    src_path = Path(audio_path)
    if not src_path.is_file():
        raise FileNotFoundError(f"File audio non trovato: {audio_path}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        wav_path = tmp_dir_path / "audio_16k.wav"

        # Conversione audio in WAV 16kHz mono
        cmd_ffmpeg = [
            FFMPEG_BIN, "-y",
            "-i", str(src_path),
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            str(wav_path)
        ]
        res_ff = subprocess.run(cmd_ffmpeg, capture_output=True, timeout=30)
        if res_ff.returncode != 0:
            logger.error("FFmpeg error: %s", res_ff.stderr.decode("utf-8", errors="replace"))
            raise RuntimeError(f"Errore nella conversione audio ffmpeg: {res_ff.stderr[:200]}")

        # Invocazione Whisper
        cmd_whisper = [
            WHISPER_BIN,
            str(wav_path),
            "--model", model,
            "--language", language,
            "--output_format", "json",
            "--output_dir", str(tmp_dir_path)
        ]
        res_wh = subprocess.run(cmd_whisper, capture_output=True, text=True, timeout=120)
        if res_wh.returncode != 0:
            logger.error("Whisper error: %s", res_wh.stderr)
            raise RuntimeError(f"Errore durante trascrizione Whisper: {res_wh.stderr[:200]}")

        json_out = tmp_dir_path / f"{wav_path.stem}.json"
        if not json_out.is_file():
            logger.warning("File JSON di output Whisper non trovato: %s", json_out)
            return ""

        try:
            data = json.loads(json_out.read_text(encoding="utf-8"))
            return data.get("text", "").strip()
        except Exception as exc:
            logger.error("Errore lettura json trascrizione: %s", exc)
            return ""
