#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compone un Motion Reel in una pagina HTML autonoma ed eventualmente lo registra in MP4.

Ogni reel è un file `reels/<id>.js`: scene in canvas più la costante `REEL`.
Il build concatena `runtime.js` → `reels/<id>.js` → `player.js` dentro `shell.html`
e incorpora i font di `fonts/` come data URI, così la pagina funziona offline
e il video ha gli stessi font su Mac, OMEN e in un container.

La riga `// @meta` può aggiungere, oltre a id, title e aria:
  "dur": 60                      durata in secondi (default 30)
  "formats": ["9:16", "16:9"]    formati disponibili; il primo è quello predefinito
  "parts": ["rd-2026-10-27"]     reel di cui riusare le scene: nel codice sono `PARTS['<id>']`
  "assets": {"nome": "percorso"} immagini (percorso dalla radice del repo) incorporate come data URI: `IMGS['nome']`

    python3 build.py --list
    python3 build.py resilienza-2026-10-28                 # solo HTML
    python3 build.py resilienza-2026-10-28 --render        # HTML + MP4 (serve node + playwright)
    python3 build.py resilienza-2026-10-28 --stills 9,18   # PNG di controllo
    python3 build.py panoramica-2026-10-29 --format 16:9 --render   # versione orizzontale

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
SIZES = {"9:16": (1080, 1920), "16:9": (1920, 1080)}


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
    meta.setdefault("dur", 30)
    meta.setdefault("formats", ["9:16"])
    meta.setdefault("parts", [])
    meta.setdefault("assets", {})
    if unknown := [f for f in meta["formats"] if f not in SIZES]:
        raise SystemExit(f"reels/{reel_id}.js: formato sconosciuto {unknown} (validi: {', '.join(SIZES)})")
    return meta


def suffix(meta: dict, fmt: str) -> str:
    """Il formato predefinito tiene i nomi di sempre; gli altri aggiungono `-16x9` e simili."""
    return "" if fmt == meta["formats"][0] else "-" + fmt.replace(":", "x")


def font_faces() -> str:
    faces = []
    for family, weight, name in FONTS:
        data = base64.b64encode((HERE / "fonts" / name).read_bytes()).decode()
        faces.append(f'@font-face{{font-family:"{family}";font-weight:{weight};font-style:normal;'
                     f'font-display:block;src:url(data:font/woff;base64,{data}) format("woff")}}')
    return "\n".join(faces)


def _strip_header(js: str) -> str:
    return "\n".join(l for l in js.splitlines() if not l.startswith("// SPDX-") and not l.startswith("// @meta "))


def _part(part_id: str) -> str:
    """Un reel riusato dentro un altro: le sue scene restano nel suo scope e si leggono da PARTS."""
    path = REELS / f"{part_id}.js"
    if not path.exists():
        raise SystemExit(f"parte sconosciuta: {part_id}")
    js = path.read_text(encoding="utf-8")
    if read_meta(js, part_id)["parts"]:
        raise SystemExit(f"reels/{part_id}.js raccoglie già altri reel: non può essere una parte")
    return f"PARTS[{json.dumps(part_id)}] = (() => {{\n{_strip_header(js)}\nreturn REEL;\n}})();"


def asset_uris(meta: dict, reel_id: str) -> dict:
    """Le immagini del reel come data URI: la pagina resta autonoma e il render non dipende da file esterni."""
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".svg": "image/svg+xml"}
    out = {}
    for name, rel in meta["assets"].items():
        f = (REPO / rel).resolve()
        if REPO not in f.parents or not f.is_file() or f.suffix.lower() not in mime:
            raise SystemExit(f"reels/{reel_id}.js: asset `{name}` non valido ({rel}): serve un'immagine dentro il repository")
        out[name] = f"data:{mime[f.suffix.lower()]};base64," + base64.b64encode(f.read_bytes()).decode()
    return out


def build_page(reel_id: str, fmt: str | None = None) -> tuple[str, dict]:
    path = REELS / f"{reel_id}.js"
    if not path.exists():
        raise SystemExit(f"reel sconosciuto: {reel_id} (disponibili: {', '.join(reel_ids())})")
    reel_js = path.read_text(encoding="utf-8")
    meta = read_meta(reel_js, reel_id)
    fmt = fmt or meta["formats"][0]
    if fmt not in meta["formats"]:
        raise SystemExit(f"{reel_id}: formato {fmt} non previsto (disponibili: {', '.join(meta['formats'])})")
    w, h = SIZES[fmt]
    cfg = f"const CFG = {json.dumps({'dur': meta['dur'], 'land': w > h})};\nconst ASSETS = {json.dumps(asset_uris(meta, reel_id))};"
    lib = ["const PARTS = {};"] + [_part(p) for p in meta["parts"]] if meta["parts"] else []
    parts = [cfg, (HERE / "runtime.js").read_text(encoding="utf-8"), *lib, reel_js, (HERE / "player.js").read_text(encoding="utf-8")]
    script = "\n".join(_strip_header(p) for p in parts)
    shell = (HERE / "shell.html").read_text(encoding="utf-8")
    shell = shell.split("\n", 1)[1]  # via il commento di licenza: la pagina pubblicata non ha <html> proprio
    page = (shell.replace("{{TITLE}}", meta["title"])
                 .replace("{{ARIA}}", meta["aria"].replace("&", "&amp;").replace('"', "&quot;"))
                 .replace("{{W}}", str(w)).replace("{{H}}", str(h)).replace("{{DUR}}", str(meta["dur"]))
                 .replace("{{FONTFACE}}", font_faces())
                 .replace("{{SCRIPT}}", script))
    return page, {**meta, "format": fmt, "size": (w, h)}


def write_outputs(reel_id: str, out_dir: Path, fmt: str | None = None) -> tuple[Path, Path]:
    page, meta = build_page(reel_id, fmt)
    name = reel_id + suffix(meta, meta["format"])
    out_dir.mkdir(parents=True, exist_ok=True)
    html = out_dir / f"{name}.html"
    html.write_text(page, encoding="utf-8")
    # la pagina di render ha lo scheletro completo, perché Chromium la apre da file://
    render = out_dir / f".{name}.render.html"
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
    ap.add_argument("--format", help="formato fra quelli del reel, ad esempio 16:9 (default il primo)")
    ap.add_argument("--render", action="store_true", help="registra anche l'MP4 a 30 fps")
    ap.add_argument("--stills", help="istanti in secondi, separati da virgola: salva PNG invece del video")
    args = ap.parse_args(argv)
    if args.list or not args.reel:
        for rid in reel_ids():
            meta = read_meta((REELS / f"{rid}.js").read_text(encoding="utf-8"), rid)
            print(f"{rid}\t{meta['title']}\t{meta['dur']} s\t{' '.join(meta['formats'])}")
        return 0
    out_dir = args.out or REPO / "data" / "reel-projects" / "motion" / args.reel
    html, render = write_outputs(args.reel, out_dir, args.format)
    print(f"HTML: {html}")
    if args.render or args.stills:
        if args.stills:  # i PNG del formato predefinito restano dove sono sempre stati
            target = out_dir if html.stem == args.reel else out_dir / html.stem
        else:
            target = out_dir / f"{html.stem}.mp4"
        run_render(render, target, args.stills)
        print(f"{'PNG' if args.stills else 'MP4'}: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
