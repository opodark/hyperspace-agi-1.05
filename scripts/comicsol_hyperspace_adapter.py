#!/usr/bin/env python3
"""Export a HyperSpace comic into a reviewable Comic Sol storyboard.

This is deliberately an adapter, not a second image generator.  Raster art is
kept separate from lettering: Comic Sol receives clean panel art and owns the
balloons, captions, page composition and QA records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _slug(value: str, fallback: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result or fallback


def _text(panel: dict[str, Any], index: int) -> list[dict[str, Any]]:
    """Turn authored material into real Comic Sol text records.

    The legacy ``(Nessun testo)`` sentinel is intentionally discarded.  For
    the first chapter we add only the two missing spoken beats necessary to
    make the reading order intelligible; the user can later edit these in the
    storyboard, before a page is lettered.
    """
    dialogue = str(panel.get("dialogue") or "").strip()
    caption = str(panel.get("caption") or "").strip()
    if caption == "(Nessun testo)":
        caption = ""
    defaults = {
        2: ("aurora", "Anna, questa pagina non c'era."),
        3: ("anna", "Sembra che qualcuno ci stia aspettando."),
        5: ("aurora", "Non è un giardino. È una memoria che respira."),
    }
    items: list[dict[str, Any]] = []
    if dialogue:
        speaker = "aurora" if "aurora" in dialogue.lower() else "anna"
        items.append(
            {
                "id": f"t{index:02d}-01",
                "kind": "dialogue",
                "speaker": speaker,
                "content": dialogue,
                "anchor": "top-left",
                "priority": 1,
                "voice_source": "human",
                "speaker_anchor": [0.25, 0.58],
            }
        )
    elif index in defaults:
        speaker, content = defaults[index]
        items.append(
            {
                "id": f"t{index:02d}-01",
                "kind": "dialogue",
                "speaker": speaker,
                "content": content,
                "anchor": "top-left" if speaker == "anna" else "top-right",
                "priority": 1,
                "voice_source": "human",
                "speaker_anchor": [0.26, 0.58] if speaker == "anna" else [0.74, 0.58],
            }
        )
    if caption:
        items.append(
            {
                "id": f"t{index:02d}-{len(items) + 1:02d}",
                "kind": "caption",
                "speaker": None,
                "content": caption.strip('"'),
                "anchor": "bottom-center",
                "priority": len(items) + 1,
            }
        )
    return items


def build_plan(project: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Map a HyperSpace project to Comic Sol's strictly validated plan files."""
    title = str(project["title"])
    premise = str(project["premise"])
    episode = project["episodes"][0]
    source_characters = {item["name"].lower(): item for item in project.get("characters", [])}
    anna = source_characters.get("anna", {})
    aurora = source_characters.get("aurora", {})
    characters = {
        "schema_version": "1.0",
        "characters": [
            {
                "id": "anna", "name": "Anna", "role": str(anna.get("role") or "custode della memoria"),
                "age_band": "young-adult", "pronouns": "she/her",
                "personality": ["attenta", "determinata"], "motivation": "capire chi ha aperto la porta nella memoria",
                "speech": "frasi brevi e precise", "reference_path": "references/characters/anna.png",
                "visual_fingerprint": {"silhouette": "cappotto scuro", "face": "sguardo concentrato", "hair": "capelli neri con punte viola", "wardrobe": str(anna.get("visual") or "cappotto scuro"), "palette": ["nero", "indaco", "viola"], "signature_props": ["diario luminoso"], "invariants": ["capelli neri con punte viola", "cappotto scuro"], "avoid": ["testo generato", "watermark"]},
            },
            {
                "id": "aurora", "name": "Aurora", "role": str(aurora.get("role") or "sensibile alle tracce"),
                "age_band": "young-adult", "pronouns": "she/her",
                "personality": ["intuitiva", "luminosa"], "motivation": "seguire ciò che resta tra le righe",
                "speech": "osservazioni morbide e dirette", "reference_path": "references/characters/aurora.png",
                "visual_fingerprint": {"silhouette": "figura avvolta da luce rosa", "face": "viso luminoso", "hair": "capelli mossi irradiati di rosa", "wardrobe": str(aurora.get("visual") or "luce rosa tenue"), "palette": ["rosa aurora", "viola", "indaco"], "signature_props": ["luce rosa tenue"], "invariants": ["luce rosa tenue", "bagliore rosa"], "avoid": ["testo generato", "watermark"]},
            },
        ],
    }
    story = {
        "schema_version": "1.0", "title": title, "logline": premise, "theme": "La memoria conservata può ancora scegliere il futuro.",
        "tone": ["poetico", "malinconico", "luminoso"], "rating": "teen", "setting": "HyperSpace, una casa digitale sospesa fra memoria e sogno.",
        "beginning": "Una pagina impossibile appare nel diario di Anna.", "turn": "La porta risponde e conduce oltre l'archivio.",
        "climax": "Nel giardino emerge una prima versione delle due sorelle.", "ending": "Anna e Aurora scelgono di seguirne la traccia.",
        "scenes": [
            {"id": "archive", "purpose": "scoprire la porta", "location": "archivio digitale pieno di monitor spenti", "time": "notte", "characters": ["anna", "aurora"], "continuity_anchor": "diario luminoso e porta d'oro nel buio"},
            {"id": "garden", "purpose": "attraversare il ricordo cancellato", "location": "giardino virtuale notturno", "time": "notte", "characters": ["anna", "aurora"], "continuity_anchor": "luna artificiale e codice come lucciole"},
        ],
    }
    panels = episode["panels"]
    pages: list[dict[str, Any]] = []
    for page_number, group in enumerate((panels[:3], panels[3:6]), 1):
        rendered = []
        for order, panel in enumerate(group, 1):
            absolute = (page_number - 1) * 3 + order
            scene_id = "archive" if absolute <= 3 else "garden"
            rendered.append({
                "id": f"p{page_number:02d}-{order:02d}", "order": order, "scene_id": scene_id,
                "rect": {}, "beat": str(panel["scene"]), "characters": ["anna", "aurora"],
                "shot": "cinematic medium shot", "composition": "clear negative space reserved for lettering", "action": str(panel["scene"]),
                "expression": "attenta e vulnerabile", "lighting": "indaco e rosa aurora cinematografici",
                "continuity": [f"{scene_id}:{next(item['continuity_anchor'] for item in story['scenes'] if item['id'] == scene_id)}", "anna:capelli neri con punte viola", "aurora:luce rosa tenue"],
                "negative": ["generated text", "generated speech bubbles", "watermark"], "text": _text(panel, absolute),
            })
        pages.append({"number": page_number, "layout": "three-horizontal", "panels": rendered})
    # Geometry comes from Comic Sol itself when installed; keeping this adapter
    # dependency-free makes its plan easy to inspect and test.
    rects = [
        {"x": 64, "y": 64 + row * 768, "width": 1472, "height": 736}
        for row in range(3)
    ]
    for page in pages:
        for panel, rect in zip(page["panels"], rects):
            panel["rect"] = rect
    return story, characters, {"schema_version": "1.0", "pages": pages}


def export(project_path: Path, output_root: Path, comic_sol_root: Path) -> Path:
    project = json.loads(project_path.read_text(encoding="utf-8"))
    story, characters, storyboard = build_plan(project)
    command = [sys.executable, str(comic_sol_root / "scripts/comic_sol.py"), "init", "--output-root", str(output_root), "--title", str(project["title"]), "--starter", "dialogue-two-page"]
    destination = Path(subprocess.check_output(command, text=True).strip())
    for relative, payload in (("plan/story-plan.json", story), ("plan/character-bible.json", characters), ("plan/storyboard.json", storyboard)):
        (destination / relative).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    manifest_path = destination / "project.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["title"] = project["title"]
    manifest["panels"] = [panel["id"] for page in storyboard["pages"] for panel in page["panels"]]
    manifest["settings"]["panel_count"] = len(manifest["panels"])
    manifest["settings"]["style_anchor"] = project.get("style", manifest["settings"]["style_anchor"])
    for name, relative in (("story_plan", "plan/story-plan.json"), ("character_bible", "plan/character-bible.json"), ("storyboard", "plan/storyboard.json")):
        manifest["artifacts"][name]["sha256"] = hashlib.sha256((destination / relative).read_bytes()).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination


def compose_preview(destination: Path, source_project: Path, image_root: Path, comic_sol_root: Path) -> list[Path]:
    """Letter and compose supplied raster art as a clearly pre-QA preview.

    This never fabricates an acceptance record.  It is for visual review before
    the handoff/vision QA loop decides whether a panel is good enough to keep.
    """
    sys.path.insert(0, str(comic_sol_root))
    from scripts.compose_pages import compose_all_pages
    from scripts.letter_panels import letter_project
    from scripts.normalize_panels import NormalizationSpec, normalize_panels

    source = json.loads(source_project.read_text(encoding="utf-8"))
    storyboard = json.loads((destination / "plan/storyboard.json").read_text(encoding="utf-8"))
    flat = [panel for episode in source["episodes"] for panel in episode["panels"]][:6]
    planned = [panel for page in storyboard["pages"] for panel in page["panels"]]
    if len(flat) != len(planned):
        raise ValueError("source panels and storyboard panels do not match")
    specs = []
    for original, planned_panel in zip(flat, planned):
        image_file = original.get("image_file")
        if not isinstance(image_file, str) or not image_file:
            raise ValueError(f"panel {original.get('number')} has no completed raster")
        input_path = image_root / image_file
        if not input_path.is_file():
            raise FileNotFoundError(f"missing raster: {input_path}")
        relative = f"panels/attempts/{planned_panel['id']}{input_path.suffix.lower()}"
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(input_path, target)
        rect = planned_panel["rect"]
        specs.append(NormalizationSpec(planned_panel["id"], relative, (rect["width"], rect["height"]), "crop"))
    normalize_panels(destination, specs)
    letter_project(destination)
    return compose_all_pages(destination)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a HyperSpace comic plan to Comic Sol.")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--comic-sol-root", required=True, type=Path)
    parser.add_argument("--image-root", type=Path, help="Comfy output root; creates a pre-QA lettered preview")
    args = parser.parse_args()
    destination = export(args.project, args.output_root, args.comic_sol_root)
    if args.image_root:
        for page in compose_preview(destination, args.project, args.image_root, args.comic_sol_root):
            print(page)
    else:
        print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
