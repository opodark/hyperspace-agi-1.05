# SPDX-License-Identifier: Apache-2.0
"""Generatore deterministico di siti statici, manifest e bundle ZIP."""
from __future__ import annotations

import html
import json
import os
import re
import uuid
import zipfile
from datetime import datetime, timezone


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return value[:48] or "sito"


def build_site(name: str, brief: str, *, template: str = "landing",
               headline: str = "", call_to_action: str = "Contattaci") -> dict:
    if template not in {"landing", "showcase"}:
        raise ValueError("template non supportato")
    name = " ".join(str(name or "").split())
    brief = " ".join(str(brief or "").split())
    if not name or not brief:
        raise ValueError("nome e brief sono obbligatori")
    project_id = f"{_slug(name)}-{uuid.uuid4().hex[:8]}"
    title = html.escape(headline.strip() or name)
    description = html.escape(brief)
    cta = html.escape(call_to_action)
    sections = ("Servizi", "Metodo", "Contatti") if template == "landing" else ("Chi siamo", "Portfolio", "Contatti")
    cards = "".join(f'<article class="card"><h2>{s}</h2><p>{description}</p></article>' for s in sections)
    index = f'''<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{description}"><title>{html.escape(name)}</title><link rel="stylesheet" href="styles.css"></head><body><header><nav><strong>{html.escape(name)}</strong><a href="#contenuti">Scopri</a></nav><div class="hero"><p class="eyebrow">{template}</p><h1>{title}</h1><p>{description}</p><a class="cta" href="#contatti">{cta}</a></div></header><main id="contenuti">{cards}</main><footer id="contatti">© {datetime.now(timezone.utc).year} {html.escape(name)}</footer><script src="app.js"></script></body></html>'''
    css = ''':root{color-scheme:dark;--bg:#0b1020;--fg:#f6f7fb;--accent:#72e6c1;--card:#151c30}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,sans-serif}header,main,footer{max-width:1100px;margin:auto;padding:2rem}nav{display:flex;justify-content:space-between}a{color:var(--accent)}.hero{padding:10vh 0}.hero h1{font-size:clamp(2.5rem,8vw,6rem);line-height:1;margin:.2em 0}.eyebrow{text-transform:uppercase;letter-spacing:.2em}.cta{display:inline-block;padding:.8rem 1.2rem;border:1px solid var(--accent);border-radius:999px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}.card{background:var(--card);padding:1.5rem;border-radius:1rem}@media(max-width:600px){header,main,footer{padding:1.2rem}}'''
    manifest = {"version": 1, "id": project_id, "name": name, "brief": brief,
                "template": template, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "files": ["index.html", "styles.css", "app.js"]}
    return {"manifest": manifest, "files": {"index.html": index, "styles.css": css,
                                               "app.js": "document.documentElement.classList.add('js');\n"}}


def import_reference_html(project: dict, source_root: str, source_html: str,
                          *, max_images: int = 40) -> list[str]:
    """Copia nel progetto le immagini citate da un HTML ComfyUI autorizzato."""
    root = os.path.realpath(source_root)
    name = os.path.basename(str(source_html or "").replace("\\", "/"))
    if not name.lower().endswith((".html", ".htm")):
        raise ValueError("serve il nome di un file HTML")
    source = os.path.realpath(os.path.join(root, name))
    if not source.startswith(root + os.sep) or not os.path.isfile(source):
        raise ValueError("HTML di riferimento non trovato")
    with open(source, encoding="utf-8") as stream:
        markup = stream.read()
    references = re.findall(r'''(?:src|href)=["']([^"']+)["']''', markup,
                            flags=re.IGNORECASE)
    selected = []
    for reference in references:
        relative = reference.split("/output/", 1)[-1] if "/output/" in reference else reference
        relative = relative.lstrip("/")
        candidate = os.path.realpath(os.path.join(root, relative))
        if (not candidate.startswith(root + os.sep) or not os.path.isfile(candidate)
                or not candidate.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))):
            continue
        target = f"assets/{os.path.basename(candidate)}"
        if target not in selected:
            project.setdefault("binary_files", {})[target] = candidate
            selected.append(target)
        if len(selected) >= max_images:
            break
    if not selected:
        raise ValueError("l'HTML non contiene immagini locali importabili")
    gallery = '<section class="gallery" aria-label="Galleria">' + "".join(
        f'<img src="{html.escape(path, quote=True)}" alt="Immagine di riferimento {i}">'
        for i, path in enumerate(selected, 1)) + "</section>"
    project["files"]["index.html"] = project["files"]["index.html"].replace(
        "</main>", gallery + "</main>")
    project["files"]["styles.css"] += (
        ".gallery{grid-column:1/-1;display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}"
        ".gallery img{width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:1rem}"
    )
    project["manifest"]["source_html"] = name
    project["manifest"]["files"].extend(selected)
    return selected


class WebsiteStore:
    def __init__(self, root: str):
        self.root = os.path.realpath(root)
        os.makedirs(self.root, exist_ok=True)

    def save(self, project: dict) -> str:
        project_id = _slug(project["manifest"]["id"])
        folder = os.path.realpath(os.path.join(self.root, project_id))
        if not folder.startswith(self.root + os.sep):
            raise ValueError("percorso progetto non valido")
        os.makedirs(folder, exist_ok=True)
        for name, content in project["files"].items():
            if name not in {"index.html", "styles.css", "app.js"}:
                raise ValueError("file sito non consentito")
            with open(os.path.join(folder, name), "w", encoding="utf-8") as stream:
                stream.write(content)
        for name, source in project.get("binary_files", {}).items():
            target = os.path.realpath(os.path.join(folder, name))
            if not target.startswith(folder + os.sep):
                raise ValueError("asset non consentito")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(source, "rb") as reader, open(target, "wb") as writer:
                writer.write(reader.read())
        with open(os.path.join(folder, "manifest.json"), "w", encoding="utf-8") as stream:
            json.dump(project["manifest"], stream, ensure_ascii=False, indent=2)
        return project_id

    def bundle(self, project_id: str) -> str:
        project_id = _slug(project_id)
        folder = os.path.join(self.root, project_id)
        target = os.path.join(self.root, project_id + ".zip")
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            names = ["index.html", "styles.css", "app.js", "manifest.json"]
            manifest_path = os.path.join(folder, "manifest.json")
            with open(manifest_path, encoding="utf-8") as stream:
                names.extend(json.load(stream).get("files", []))
            for name in dict.fromkeys(names):
                archive.write(os.path.join(folder, name), name)
        return target

    def list(self) -> list[dict]:
        projects = []
        for name in sorted(os.listdir(self.root)):
            path = os.path.join(self.root, name, "manifest.json")
            if not os.path.isfile(path):
                continue
            try:
                with open(path, encoding="utf-8") as stream:
                    projects.append(json.load(stream))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        return sorted(projects, key=lambda x: x.get("created_at", ""), reverse=True)
