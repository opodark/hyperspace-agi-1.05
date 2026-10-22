# SPDX-License-Identifier: Apache-2.0
"""Parsing e gestione dei sottotitoli per il TikTok/Reel Editor.

Supporta formati standard SRT, WebVTT o liste temporizzate, normalizzando
i timestamp e ripulendo formattazioni HTML o caratteri spuri.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, Union


@dataclass
class SubtitleCue:
    """Singola battuta di sottotitolo con intervallo temporale in secondi."""
    start: float
    end: float
    text: str

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(raw: str) -> str:
    """Rimuove tag HTML e spazi multipli preservando gli a capo."""
    text = _TAG_RE.sub("", raw)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def parse_timestamp(ts: str) -> float:
    """Converte un timestamp HH:MM:SS,mmm oppure MM:SS.mmm in secondi decimali."""
    ts = ts.strip().replace(",", ".")
    parts = ts.split(":")
    try:
        if len(parts) == 3:
            h, m, s = parts
            return float(h) * 3600.0 + float(m) * 60.0 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return float(m) * 60.0 + float(s)
        return float(ts)
    except (ValueError, TypeError):
        return 0.0


def parse_srt(content: str) -> list[SubtitleCue]:
    """Estrae i blocchi di sottotitoli da testo formattato SRT."""
    cues: list[SubtitleCue] = []
    # Pattern standard per blocchi SRT: indice opzionale, timing con freccia, testo
    pattern = re.compile(
        r"(?:^\s*\d+\s*\r?\n)?"
        r"(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3}|\d{1,2}:\d{2}[,\.]\d{1,3})\s*-->\s*"
        r"(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3}|\d{1,2}:\d{2}[,\.]\d{1,3})"
        r"(?:[^\r\n]*)\r?\n"
        r"([\s\S]*?)(?=(?:\r?\n\s*\r?\n|\Z))",
        re.MULTILINE,
    )
    for match in pattern.finditer(content.strip()):
        s_str, e_str, raw_text = match.groups()
        start = parse_timestamp(s_str)
        end = parse_timestamp(e_str)
        text = _clean_text(raw_text)
        if text and end > start:
            cues.append(SubtitleCue(start=round(start, 3), end=round(end, 3), text=text))
    return cues


def parse_vtt(content: str) -> list[SubtitleCue]:
    """Estrae i blocchi di sottotitoli da testo formattato WebVTT."""
    # Rimuove header WEBVTT iniziale
    cleaned = re.sub(r"^WEBVTT[^\n]*\n", "", content.strip(), flags=re.IGNORECASE)
    return parse_srt(cleaned)


def parse_subtitles(source: Union[str, Path, Sequence[dict]]) -> list[SubtitleCue]:
    """Funzione unificata: carica da percorso file, stringa grezza o lista di dict.

    I dict possono avere chiavi:
      - 'start', 'end', 'text'
    """
    if isinstance(source, (Path, str)):
        path = Path(source)
        if path.is_file():
            content = path.read_text(encoding="utf-8", errors="replace")
        else:
            content = str(source).strip()

        if not content:
            return []

        if content.upper().startswith("WEBVTT"):
            return parse_vtt(content)
        return parse_srt(content)

    cues: list[SubtitleCue] = []
    if isinstance(source, (list, tuple)):
        for item in source:
            if isinstance(item, SubtitleCue):
                cues.append(item)
            elif isinstance(item, dict):
                s = float(item.get("start", 0.0))
                e = float(item.get("end", 0.0))
                txt = _clean_text(str(item.get("text", "")))
                if txt and e > s:
                    cues.append(SubtitleCue(start=round(s, 3), end=round(e, 3), text=txt))
    return cues
