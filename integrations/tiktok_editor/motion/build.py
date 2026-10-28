#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compone un Motion Reel in una pagina HTML autonoma ed eventualmente lo registra in MP4.

Ogni reel è un file `reels/<id>.js`: scene in canvas più la costante `REEL`.
Il build concatena `runtime.js` → `reels/<id>.js` → `player.js` dentro `shell.html`
e incorpora i font di `fonts/` come data URI, così la pagina funziona offline
e il video ha gli stessi font su Mac, OMEN e in un container.

    python3 build.py --list
    python3 build.py resilienza-2026-10-28                 # solo HTML
    python3 build.py resilienza-2026-10-28 --render        # HTML + MP4 (serve node + playwright)
    python3 build.py resilienza-2026-10-28 --stills 9,18   # PNG di controllo

Uscita predefinita: `data/reel-projects/motion/<id>/` nel repository.
Non pubblica nulla e non tocca `hyperspace_share/reel-review/`.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REELS = HERE / "reels"
FONTS = [  # (famiglia CSS, peso, file in fonts/)
    ("MeshDisplay", 900, "MeshDisplay-900.woff"),
    ("MeshDisplay", 600, "MeshDisplay-600.woff"),
    ("MeshDisplay", 500, "MeshDisplay-500.woff"),
    ("MeshMono", 400, "MeshMono-400.woff"),
    ("MeshMono", 700, "MeshMono-700.woff"),
]
META_RE = re.compile(r"^// @meta (\{.*\})\s*$", re.M)


def reel_ids() -> list[str]:
    return sorted(p.stem for p in REELS.glob("*.js"))


def read_meta(js: str, reel_id: str) -> dict:
    m = META_RE.search(js)
    if not m:
        raise SystemExit(f"reels/{reel_id}.js: manca la riga `// @meta {{...}}`")
    meta = json.loads(m.group(1))
    for key in ("id", "title", "aria"):
        if not meta.get(key):
            raise SystemExit(f"reels/{reel_id}.js: @meta senza `{key}`")
    if meta["id"] != reel_id:
        raise SystemExit(f"reels/{reel_id}.js: @meta id `{meta['id']}` diverso dal nome del file")
    return meta


def font_faces() -> str:
    faces = []
    for family, weight, name in FONTS:
        data = base64.b64encode((HERE / "fonts" / name).read_bytes()).decode()
        faces.append(f'@font-face{{font-family:"{family}";font-weight:{weight};font-style:normal;'
                     f'font-display:block;src:url(data:font/woff;base64,{data}) format("woff")}}')
    return "\n".join(faces)


def _strip_header(js: str) -> str:
    return "\n".join(l for l in js.splitlines() if not l.startswith("// SPDX-") and not l.startswith("// @meta "))


def build_page(reel_id: str) -> tuple[str, dict]:
    path = REELS / f"{reel_id}.js"
    if not path.exists():
        raise SystemExit(f"reel sconosciuto: {reel_id} (disponibili: {', '.join(reel_ids())})")
    reel_js = path.read_text(encoding="utf-8")
    meta = read_meta(reel_js, reel_id)
    parts = [(HERE / "runtime.js").read_text(encoding="utf-8"), reel_js, (HERE / "player.js").read_text(encoding="utf-8")]
    script = "\n".join(_strip_header(p) for p in parts)
    shell = (HERE / "shell.html").read_text(encoding="utf-8")
    shell = shell.split("\n", 1)[1]  # via il commento di licenza: la pagina pubblicata non ha <html> proprio
    page = (shell.replace("{{TITLE}}", meta["title"])
                 .replace("{{ARIA}}", meta["aria"].replace("&", "&amp;").replace('"', "&quot;"))
                 .replace("{{FONTFACE}}", font_faces())
                 .replace("{{SCRIPT}}", script))
    return page, meta


def write_outputs(reel_id: str, out_dir: Path) -> tuple[Path, Path]:
    page, _ = build_page(reel_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    html = out_dir / f"{reel_id}.html"
    html.write_text(page, encoding="utf-8")
    # la pagina di render ha lo scheletro completo, perché Chromium la apre da file://
    render = out_dir / f".{reel_id}.render.html"
    render.write_text('<!doctype html><html><head><meta charset="utf-8"></head><body>' + page + "</body></html>",
                      encoding="utf-8")
    return html, render


def run_render(render_page: Path, out: Path, stills: str | None) -> None:
    node = shutil.which("node")
    if not node:
        raise SystemExit("node non trovato: serve per registrare l'MP4 (vedi docs/motion-reels.md)")
    if not stills and not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg non trovato nel PATH")
    cmd = [node, str(HERE / "render.js"), str(render_page), str(out)]
    if stills:
        cmd += ["--stills", stills]
    subprocess.run(cmd, check=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reel", nargs="?", help="id del reel (nome del file in reels/ senza .js)")
    ap.add_argument("--list", action="store_true", help="elenca i reel disponibili")
    ap.add_argument("--out", type=Path, help="cartella di uscita (default data/reel-projects/motion/<id>)")
    ap.add_argument("--render", action="store_true", help="registra anche l'MP4 1080×1920, 30 fps, 30 s")
    ap.add_argument("--stills", help="istanti in secondi, separati da virgola: salva PNG invece del video")
    args = ap.parse_args(argv)
    if args.list or not args.reel:
        for rid in reel_ids():
            meta = read_meta((REELS / f"{rid}.js").read_text(encoding="utf-8"), rid)
            print(f"{rid}\t{meta['title']}")
        return 0
    out_dir = args.out or REPO / "data" / "reel-projects" / "motion" / args.reel
    html, render = write_outputs(args.reel, out_dir)
    print(f"HTML: {html}")
    if args.render or args.stills:
        target = out_dir if args.stills else out_dir / f"{args.reel}.mp4"
        run_render(render, target, args.stills)
        print(f"{'PNG' if args.stills else 'MP4'}: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
