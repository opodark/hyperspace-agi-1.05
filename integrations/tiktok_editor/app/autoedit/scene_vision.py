# SPDX-License-Identifier: Apache-2.0
"""Optional per-scene VL analysis through HyperSpace's local control-plane."""
from __future__ import annotations

import base64
import io
import json
import os
import urllib.request
from pathlib import Path

from PIL import Image

from .brief import _extract_json
from .effects import COLOR_STYLES, MOTION_MODES

SAFE_IMPACTS = {"none", "pulse", "rgbsplit", "flash", "blur"}

CP_URL = "http://127.0.0.1:8085/v1"
OLLAMA_URL = os.getenv("TIKTOK_EDITOR_OLLAMA_URL", "http://127.0.0.1:11434")


def discover_vision_model(base_url: str = CP_URL, timeout: float = 3.0) -> str | None:
    try:
        req = urllib.request.Request(base_url.rstrip("/") + "/models",
                                     headers={"Authorization": "Bearer hyperspace-local"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = json.load(response)
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        return None
    ids = [str(row.get("id", "")) for row in payload["data"] if isinstance(row, dict)]
    local = [name for name in ids if name.startswith("🕸️ ") and "::" not in name
             and any(tag in name.lower() for tag in ("-vl:", "vision", "llava"))]
    return next((name for name in local if "instruct" in name.lower()), None) or (local[0] if local else None)


def validate_scene(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Il modello visivo non ha restituito una scena valida")
    subject = str(raw.get("subject", "")).strip()[:100]
    background = str(raw.get("background", "")).strip()[:100]
    if not subject or not background:
        raise ValueError("Il modello non ha identificato soggetto e sfondo")
    position = raw.get("subject_position", "center")
    if position not in ("left", "center", "right"):
        position = "center"
    style = raw.get("style", "vivid")
    motion = raw.get("motion", "kenburns")
    impact = raw.get("impact", "none")
    return {"subject": subject, "background": background,
            "subject_position": position,
            "style": style if style in COLOR_STYLES else "vivid",
            "motion": motion if motion in MOTION_MODES else "kenburns",
            "impact": impact if impact in SAFE_IMPACTS else "none"}


def analyze_scene(path: Path, model: str, base_url: str = OLLAMA_URL) -> dict:
    """Describe a still frame; model chooses safe clip-wide color and motion effects.

    A VL description is not a pixel mask: this intentionally does not claim to
    blur or replace only the background.
    """
    with Image.open(path) as source:
        image = source.convert("RGB")
        image.thumbnail((768, 768))
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=78)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    native_model = model.removeprefix("🕸️ ")
    if "::" in native_model:
        raise ValueError("Scegli un modello VL locale non vincolato a un nodo remoto")
    base = base_url.rstrip("/")
    with urllib.request.urlopen(base + "/api/ps", timeout=5) as response:
        loaded = json.load(response)
    active = {str(row.get("name") or row.get("model") or "") for row in loaded.get("models", [])}
    if active and not any(name.split(":")[0] == native_model.split(":")[0] for name in active):
        raise RuntimeError("Il backend VL è occupato da un altro modello; riprova quando è libero.")
    prompt = (
        "Analizza questa scena per un reel. Rispondi SOLO con JSON: "
        '{"subject":"soggetto principale breve","background":"sfondo breve",'
        '"subject_position":"left|center|right",'
        '"style":"vivid|warm|cold|cinematic|dream|neon|moody|retro",'
        '"motion":"kenburns|zoom|sway|static",'
        '"impact":"none|pulse|rgbsplit|flash|blur"}. '
        "Scegli colore, movimento e un effetto breve per i beat forti; "
        "usa none se l'effetto rischia di distrarre dal soggetto."
    )
    body = json.dumps({"model": native_model,
                       "messages": [{"role": "user", "content": prompt, "images": [encoded]}],
                       "stream": False, "think": False, "keep_alive": "2m",
                       "options": {"temperature": 0, "num_predict": 220, "num_ctx": 4096}},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base + "/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as response:
        payload = json.load(response)
    content = str((payload.get("message") or {}).get("content") or "")
    if not content:
        raise ValueError("Il modello VL non ha risposto; riprova dopo aver liberato la memoria.")
    return validate_scene(_extract_json(content))
