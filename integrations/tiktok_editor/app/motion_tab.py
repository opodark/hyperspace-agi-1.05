# SPDX-License-Identifier: Apache-2.0
"""Scheda «Motion Reels» del Reel Editor: catalogo, anteprima dal vivo, fotogrammi e render MP4.

Usa `integrations/tiktok_editor/motion/build.py` senza modificarlo: la pagina
autonoma che build.py compone è la stessa che la scheda mostra in un iframe e
che render.js registra in MP4. Le uscite vanno in `data/reel-projects/motion/<id>/`.
"""
from __future__ import annotations

import html
import importlib.util
import re
import shutil
import subprocess
import time
from pathlib import Path

import gradio as gr

MOTION_DIR = Path(__file__).resolve().parents[1] / "motion"
_spec = importlib.util.spec_from_file_location("motion_build", MOTION_DIR / "build.py")
motion_build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(motion_build)

OUT_ROOT = motion_build.REPO / "data" / "reel-projects" / "motion"
TIMES_RE = re.compile(r"^\s*\d+(?:\.\d+)?(?:\s*,\s*\d+(?:\.\d+)?)*\s*$")
FRAME_RE = re.compile(r"^frame (\d+)/(\d+)")


def _meta(rid: str) -> dict:
    return motion_build.read_meta((motion_build.REELS / f"{rid}.js").read_text(encoding="utf-8"), rid)


def _reels() -> list[tuple[str, str]]:
    out = []
    for rid in motion_build.reel_ids():
        meta = _meta(rid)
        out.append((f"{meta['title']} · {meta['dur']} s · {rid}", rid))
    return out


def _fmt(rid: str, fmt: str | None) -> str:
    formats = _meta(rid)["formats"]
    return fmt if fmt in formats else formats[0]


def _mp4(rid: str, meta: dict) -> Path:
    return _out_dir(rid) / f"{rid}{motion_build.suffix(meta, meta['format'])}.mp4"


def _check(rid: str | None) -> str:
    if not rid or rid not in motion_build.reel_ids():
        raise gr.Error("Scegli un reel dall'elenco.")
    return rid


def _out_dir(rid: str) -> Path:
    return OUT_ROOT / rid


def _playwright_ok() -> bool:
    node = shutil.which("node")
    if not node:
        return False
    probe = subprocess.run([node, "-e", "require.resolve('playwright')"], cwd=MOTION_DIR,
                           capture_output=True, timeout=20)
    return probe.returncode == 0


def tools_status() -> str:
    node, ffmpeg, pw = bool(shutil.which("node")), bool(shutil.which("ffmpeg")), _playwright_ok()
    mark = lambda ok: "✅" if ok else "❌"  # noqa: E731
    line = f"{mark(node)} node · {mark(ffmpeg)} ffmpeg · {mark(pw)} Playwright"
    if not (node and ffmpeg and pw):
        line += ("  \nPer fotogrammi e MP4: `cd integrations/tiktok_editor/motion && "
                 "npm i --no-save playwright && npx playwright install chromium`")
    return line


def _iframe(page: str) -> str:
    doc = ('<!doctype html><html><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width,initial-scale=1">'
           '<style>html,body{margin:0;height:100%}</style></head><body>' + page + "</body></html>")
    return (f'<iframe class="hs-motion-frame" title="Anteprima del reel" srcdoc="{html.escape(doc, quote=True)}" '
            'style="width:100%;height:860px;border:0;border-radius:14px;background:#07080A"></iframe>')


def _info(rid: str, meta: dict) -> str:
    mp4 = _mp4(rid, meta)
    w, h = meta["size"]
    lines = [f"### {meta['title']}", f"{w}×{h} · {meta['dur']} s · formato {meta['format']}", meta["aria"]]
    if mp4.is_file():
        when = time.strftime("%d/%m %H:%M", time.localtime(mp4.stat().st_mtime))
        lines.append(f"🎥 MP4 già registrato il {when} ({mp4.stat().st_size / 1e6:.1f} MB).")
    else:
        lines.append("🎥 Nessun MP4 ancora: premi **Registra MP4**.")
    return "\n\n".join(lines)


def on_formats(rid):
    """Al cambio di reel: i formati che quel reel prevede."""
    formats = _meta(_check(rid))["formats"]
    return gr.update(choices=formats, value=formats[0], visible=len(formats) > 1)


def on_select(rid, fmt=None):
    rid = _check(rid)
    page, meta = motion_build.build_page(rid, _fmt(rid, fmt))
    html_path, _ = motion_build.write_outputs(rid, _out_dir(rid), meta["format"])
    mp4 = _mp4(rid, meta)
    existing = str(mp4) if mp4.is_file() else None
    files = [str(html_path)] + ([existing] if existing else [])
    return _iframe(page), _info(rid, meta), existing, files


def on_stills(rid, times, fmt=None):
    rid = _check(rid)
    fmt, dur = _fmt(rid, fmt), _meta(rid)["dur"]
    times = (times or "").strip() or "4,9,14,19,24,29"
    if not TIMES_RE.match(times) or any(float(t) > dur for t in times.split(",")):
        raise gr.Error(f"Scrivi istanti in secondi separati da virgola, fra 0 e {dur:g}.")
    if not _playwright_ok():
        raise gr.Error("Per i fotogrammi servono node e Playwright: vedi lo stato strumenti in alto.")
    out = _out_dir(rid)
    html_path, render_page = motion_build.write_outputs(rid, out, fmt)
    stills = out / "stills" / html_path.stem
    try:
        motion_build.run_render(render_page, stills, ",".join(t.strip() for t in times.split(",")))
    except (subprocess.CalledProcessError, SystemExit) as exc:
        raise gr.Error(f"Fotogrammi non generati: {exc}")
    return [(str(stills / f"still-{float(t):g}.png"), f"{float(t):g} s") for t in times.split(",")]


def on_render(rid, fmt=None, progress=gr.Progress()):
    rid = _check(rid)
    node = shutil.which("node")
    if not node or not shutil.which("ffmpeg") or not _playwright_ok():
        raise gr.Error("Per l'MP4 servono node, ffmpeg e Playwright: vedi lo stato strumenti in alto.")
    out = _out_dir(rid)
    html_path, render_page = motion_build.write_outputs(rid, out, _fmt(rid, fmt))
    final, part = out / f"{html_path.stem}.mp4", out / f"{html_path.stem}.part.mp4"
    progress(0, desc="Avvio di Chromium…")
    proc = subprocess.Popen([node, str(MOTION_DIR / "render.js"), str(render_page), str(part)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    tail: list[str] = []
    for line in proc.stdout:
        m = FRAME_RE.match(line)
        if m:
            done, total = int(m.group(1)), int(m.group(2))
            progress(done / total, desc=f"Registrazione fotogramma {done}/{total}")
        else:
            tail = (tail + [line.strip()])[-6:]
    if proc.wait() != 0 or not part.is_file():
        part.unlink(missing_ok=True)
        raise gr.Error("Render non riuscito: " + (" · ".join(t for t in tail if t) or f"codice {proc.returncode}"))
    part.replace(final)
    _, meta = motion_build.build_page(rid, _fmt(rid, fmt))
    return str(final), [str(html_path), str(final)], _info(rid, meta)


def build_motion_tab(demo: gr.Blocks) -> None:
    """Crea i componenti della scheda; va chiamata dentro un `gr.Tab` di `demo`."""
    choices = _reels()
    with gr.Row(equal_height=False):
        with gr.Column(scale=2, min_width=340):
            preview = gr.HTML(label="Anteprima dal vivo")
        with gr.Column(scale=3, min_width=420):
            gr.Markdown("Reel di 30 o 60 s disegnati in codice (`integrations/tiktok_editor/motion/reels/`), "
                        "verticali 9:16 e, quando il reel lo prevede, anche orizzontali 16:9 per YouTube. "
                        "L'anteprima a sinistra è lo stesso codice da cui nasce l'MP4.")
            with gr.Row():
                reel_dd = gr.Dropdown(choices, value=choices[-1][1] if choices else None,
                                      label="Reel", scale=4)
                refresh_btn = gr.Button("↻ Aggiorna", scale=1)
            fmt = gr.Radio(["9:16"], value="9:16", label="Formato", visible=False)
            info = gr.Markdown()
            with gr.Row():
                times = gr.Textbox(value="4,9,14,19,24,29", label="Istanti dei fotogrammi (s)", scale=3)
                stills_btn = gr.Button("🖼️ Fotogrammi di controllo", scale=2)
            render_btn = gr.Button("🎥 Registra MP4 · 30 fps", variant="primary", size="lg")
            gr.Markdown("Il render dura un paio di minuti per 30 s. Il video è muto: aggiungi la musica nell'app del "
                        "social oppure caricalo nella scheda «Reel da foto e video».", elem_classes="hs-note")
            stills = gr.Gallery(label="Fotogrammi", columns=6, height=300, allow_preview=True)
            video = gr.Video(label="MP4 registrato", height=520)
            files = gr.File(label="File del reel (pagina HTML autonoma e MP4)", file_count="multiple")
            gr.Markdown(tools_status, elem_classes="hs-note")

    shown = [preview, info, video, files]
    reel_dd.change(on_formats, inputs=[reel_dd], outputs=[fmt]).then(on_select, inputs=[reel_dd, fmt], outputs=shown)
    fmt.input(on_select, inputs=[reel_dd, fmt], outputs=shown)
    refresh_btn.click(lambda: gr.update(choices=_reels()), outputs=[reel_dd])
    stills_btn.click(on_stills, inputs=[reel_dd, times, fmt], outputs=[stills])
    render_btn.click(on_render, inputs=[reel_dd, fmt], outputs=[video, files, info])
    demo.load(on_formats, inputs=[reel_dd], outputs=[fmt]).then(on_select, inputs=[reel_dd, fmt], outputs=shown)
