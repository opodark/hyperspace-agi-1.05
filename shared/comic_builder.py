# SPDX-License-Identifier: Apache-2.0
"""Progetti narrativi persistenti: storyline, continuity bible e vignette."""
from __future__ import annotations

import json
import html
import os
import re
import uuid
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return value[:48] or "fumetto"


def new_project(title: str, premise: str, *, authors=("anna", "aurora"),
                style: str = "graphic novel") -> dict:
    title = " ".join(str(title or "").split())
    premise = " ".join(str(premise or "").split())
    if not title or not premise:
        raise ValueError("titolo e premessa sono obbligatori")
    return {"version": 1, "id": f"{_slug(title)}-{uuid.uuid4().hex[:8]}",
            "title": title[:120], "premise": premise[:1200],
            "authors": [str(x)[:64] for x in authors if str(x).strip()],
            "style": " ".join(str(style or "graphic novel").split())[:300],
            "characters": [], "continuity": {}, "episodes": [],
            "status": "draft", "created_at": _now(), "updated_at": _now()}


def add_character(project: dict, *, name: str, visual: str, role: str = "") -> dict:
    character = {"name": " ".join(str(name).split())[:80],
                 "role": " ".join(str(role).split())[:160],
                 "visual": " ".join(str(visual).split())[:800]}
    if not character["name"] or not character["visual"]:
        raise ValueError("nome e identità visiva sono obbligatori")
    project.setdefault("characters", []).append(character)
    project["updated_at"] = _now()
    return character


def add_episode(project: dict, *, title: str, synopsis: str, panels: list[dict]) -> dict:
    if not panels:
        raise ValueError("un episodio richiede almeno una vignetta")
    normalized = []
    for index, panel in enumerate(panels, 1):
        scene = " ".join(str(panel.get("scene") or "").split())
        if not scene:
            raise ValueError(f"scena mancante nella vignetta {index}")
        normalized.append({"number": index, "scene": scene[:1200],
                           "dialogue": " ".join(str(panel.get("dialogue") or "").split())[:500],
                           "caption": " ".join(str(panel.get("caption") or "").split())[:500],
                           "image_job_id": "", "image_file": "", "status": "draft"})
    episode = {"id": f"ep-{len(project.get('episodes', []))+1:03d}",
               "title": " ".join(str(title or "").split())[:120],
               "synopsis": " ".join(str(synopsis or "").split())[:1200],
               "panels": normalized, "created_at": _now()}
    project.setdefault("episodes", []).append(episode)
    project["updated_at"] = _now()
    return episode


def panel_prompt(project: dict, episode: dict, panel: dict, *, scene: str = "") -> str:
    cast = "; ".join(f"{c['name']}: {c['visual']}" for c in project.get("characters", []))
    cast_names = " and ".join(c["name"] for c in project.get("characters", []))
    continuity = "; ".join(f"{k}: {v}" for k, v in project.get("continuity", {}).items())
    return ". ".join(x for x in (
        scene or panel.get("scene", ""), f"visual style: {project.get('style', 'graphic novel')}",
        f"the foreground must visibly include {cast_names}, distinct characters, interacting with the scene" if cast_names else "",
        f"consistent characters: {cast}" if cast else "",
        f"continuity: {continuity}" if continuity else "",
        ("score_9, score_8_up, source_anime, graphic novel illustration, cel shading, "
         "inked outlines, dynamic composition, single comic panel, no speech bubbles, "
         "no text, consistent recurring characters"),
    ) if x)


def episode_html(project: dict, episode: dict, *, image_url=lambda value: value) -> str:
    """Tavola HTML: il testo resta DOM leggibile, mai affidato al diffusion."""
    panels = []
    for panel in episode.get("panels", []):
        file = str(panel.get("image_file") or "")
        visual = (f'<img src="{html.escape(image_url(file), quote=True)}" alt="{html.escape(panel.get("scene", ""), quote=True)}">'
                  if file else '<div class="placeholder">Vignetta non ancora generata</div>')
        dialogue = str(panel.get("dialogue", "")).strip()
        caption = str(panel.get("caption", "")).strip()
        # I segnaposto generati dal modello non sono testo narrativo.
        if caption.casefold() in {"(nessun testo)", "nessun testo", "none"}:
            caption = ""
        balloon = (f'<div class="balloon">{html.escape(dialogue)}</div>' if dialogue else "")
        narration = (f'<div class="caption">{html.escape(caption)}</div>' if caption else "")
        panels.append(f'<article class="panel"><div class="art">{visual}{balloon}{narration}</div></article>')
    return f'''<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(episode.get("title", "Fumetto"))}</title><style>body{{margin:0;background:#111;color:#f7f7f7;font:16px/1.45 system-ui}}header,.page{{max-width:1100px;margin:auto;padding:24px}}.page{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}}.panel{{background:#fff;color:#111;border:8px solid #fff;box-shadow:0 8px 30px #0008}}.art{{position:relative;overflow:hidden}}img,.placeholder{{display:block;width:100%;aspect-ratio:1/1;object-fit:cover;background:#ddd}}.placeholder{{display:grid;place-items:center}}.balloon{{position:absolute;top:5%;right:4%;max-width:62%;padding:9px 13px;border:3px solid #111;border-radius:48% 52% 46% 54%/55% 42% 58% 45%;background:#fff;font-family:ui-rounded,system-ui,sans-serif;font-weight:700;font-size:clamp(12px,2vw,18px);line-height:1.15;box-shadow:2px 3px 0 #111}}.balloon:after{{content:"";position:absolute;right:18%;bottom:-17px;border-width:14px 7px 0;border-style:solid;border-color:#111 transparent transparent;transform:rotate(24deg)}}.caption{{position:absolute;left:0;right:0;bottom:0;background:#111e;color:#fff;padding:8px 11px;font:600 clamp(11px,1.7vw,15px)/1.25 system-ui,sans-serif;text-shadow:1px 1px #000}}@media(max-width:700px){{.page{{grid-template-columns:1fr}}}}</style></head><body><header><h1>{html.escape(project.get("title", ""))}</h1><h2>{html.escape(episode.get("title", ""))}</h2><p>{html.escape(episode.get("synopsis", ""))}</p></header><main class="page">{"".join(panels)}</main></body></html>'''


class ComicStore:
    def __init__(self, root: str):
        self.root = os.path.realpath(root)
        os.makedirs(self.root, exist_ok=True)

    def save(self, project: dict) -> str:
        path = os.path.join(self.root, _slug(project.get("id")) + ".json")
        with open(path, "w", encoding="utf-8") as stream:
            json.dump(project, stream, ensure_ascii=False, indent=2)
        return path

    def load(self, project_id: str) -> dict:
        path = os.path.join(self.root, _slug(project_id) + ".json")
        with open(path, encoding="utf-8") as stream:
            return json.load(stream)

    def list(self) -> list[dict]:
        result = []
        for name in sorted(os.listdir(self.root)):
            if name.endswith(".json"):
                try:
                    result.append(self.load(name[:-5]))
                except (OSError, ValueError, json.JSONDecodeError):
                    pass
        return result
