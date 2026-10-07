#!/usr/bin/env python3
"""Interfaccia grafica per autoedit (gira nel browser, tutto in locale).

Avvio:
    pip install -r requirements-gui.txt
    python gui.py

Flusso in due passi:
  1. ANALIZZA  -> carichi foto/video + canzone, vedi miniature, forma
     d'onda con i beat e i dati del brano.
  2. GENERA    -> scegli effetti / ritmo / formato, eventualmente riordini
     o escludi media nella tabella, e monti il video.
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import gradio as gr
except ImportError:
    sys.exit("Manca 'gradio'. Installalo con:  pip install -r requirements-gui.txt")

import numpy as np
from PIL import Image, ImageDraw

from autoedit.beats import detect_beats
from autoedit.brief import (LLMConfig, discover_control_plane, load_llm_config,
                            save_llm_config, suggest_overrides)
from autoedit.effects import COLOR_LABELS, EDIT_STYLE_LABELS, IMPACT_LABELS, MOTION_LABELS
from autoedit.media import IMAGE_EXT, VIDEO_EXT, copy_upright_image
from autoedit.pipeline import ASPECTS, RenderConfig, run_pipeline
from autoedit.guides import comic_styles, comics_for
from autoedit.scene_vision import analyze_scene, discover_vision_model
from autoedit.person_layers import prepare_person_mask
from draft import read_draft, valid_state, write_draft

logging.basicConfig(level=logging.INFO, format="%(message)s")
for _noisy in ("numba", "librosa", "matplotlib"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# --- etichette "umane" <-> valori interni ---------------------------------
SPEEDS = {
    "Lento — 1 taglio ogni 2 beat": 0.5,
    "Normale — 1 taglio a beat": 1.0,
    "Veloce — 2 tagli a beat": 2.0,
}
AUTOCUT = {"30 secondi": 30, "60 secondi": 60, "120 secondi": 120, "Libero / manuale": None}
ASPECT_LABELS = {
    "Verticale 9:16 (TikTok / Reels / Shorts)": "9:16",
    "Verticale 4:5 (feed Instagram)": "4:5",
    "Quadrato 1:1": "1:1",
    "Orizzontale 16:9": "16:9",
}
TRANSITIONS = {
    "Automatiche": "auto",
    "Solo stacchi netti": "cut",
    "Solo dissolvenze": "fade",
    "Solo slide": "slide",
    "Solo zoom": "zoom",
    "Caotiche": "chaos",
}
WM_POS = {
    "Basso a destra": "br", "Basso a sinistra": "bl",
    "Alto a destra": "tr", "Alto a sinistra": "tl",
}
TITLE_POS = {"In alto": "top", "Al centro": "center", "In basso": "bottom"}

STYLE_BY_LABEL = {v: k for k, v in COLOR_LABELS.items()}
MOTION_BY_LABEL = {v: k for k, v in MOTION_LABELS.items()}
IMPACT_BY_LABEL = {v: k for k, v in IMPACT_LABELS.items()}
# interno -> etichetta (per applicare i suggerimenti del Brief AI)
SPEED_BY_VALUE = {v: k for k, v in SPEEDS.items()}
ASPECT_BY_VALUE = {v: k for k, v in ASPECT_LABELS.items()}
TRANS_BY_VALUE = {v: k for k, v in TRANSITIONS.items()}
TITLE_BY_VALUE = {v: k for k, v in TITLE_POS.items()}
EDIT_STYLE_BY_LABEL = {v: k for k, v in EDIT_STYLE_LABELS.items()}
LLM_PROVIDERS = {"Compatibile OpenAI (anche locale)": "openai", "Anthropic (Claude)": "anthropic"}
PROVIDER_LABEL = {v: k for k, v in LLM_PROVIDERS.items()}

ALLOWED_EXT = sorted(IMAGE_EXT | VIDEO_EXT)
TABLE_HEADERS = ["#", "file", "includi", "ordine"]

BUILTIN_PRESETS_DIR = Path(__file__).resolve().parent / "presets"
PRESETS_DIR = Path(os.getenv("TIKTOK_EDITOR_DATA_DIR",
                          str(Path(__file__).resolve().parents[3] / "data" / "tiktok-editor"))) / "presets"
DATA_DIR = PRESETS_DIR.parent
WEBUI_PROJECTS = Path(os.getenv("TIKTOK_EDITOR_SHARE_DIR", "/Users/opo/hyperspace_share")) / "reel-projects"
# campi salvati in un preset (ordine = ordine degli output di "Carica")
PRESET_FIELDS = [
    "edit_style", "style", "speed", "duration_preset", "aspect", "transition", "motion", "motion_intensity",
    "variety", "impact", "grain", "vignette", "chromatic", "slowmo", "hold_prob", "title_text",
    "title_pos", "title_start", "title_dur", "wm_pos", "wm_scale", "wm_opacity", "hook_hold",
    "audio_start", "beat_offset", "xfade_ms", "snap_onsets", "dynamic_pacing", "strong_only",
    "shuffle", "max_dur", "seed", "use_scene_ai", "crescendo_finale",
    "separate_person", "subject_style", "background_style", "background_blur",
    "background_dim", "subject_spot", "subject_dim", "outline_color",
    "outline_strength", "outline_width", "cross_strobe",
]


def _list_presets() -> list[str]:
    return sorted({p.stem for directory in (BUILTIN_PRESETS_DIR, PRESETS_DIR)
                   if directory.is_dir() for p in directory.glob("*.json")})


def _list_webui_projects() -> list[str]:
    if not WEBUI_PROJECTS.is_dir():
        return []
    return sorted((p.name for p in WEBUI_PROJECTS.iterdir()
                   if p.is_dir() and (p / "manifest.json").is_file() and (p / "media").is_dir()),
                  reverse=True)


def _open_webui_project(name: str):
    if not name or name != Path(name).name:
        raise gr.Error("Scegli un progetto WebUI valido.")
    folder = (WEBUI_PROJECTS / name).resolve(strict=True)
    if not folder.is_relative_to(WEBUI_PROJECTS.resolve(strict=True)):
        raise gr.Error("Percorso progetto non valido.")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    creator = manifest.get("creator", "Altro progetto")
    brief = manifest.get("brief", "")
    if not isinstance(creator, str) or creator not in {"Anna", "Aurora", "Altro progetto"}:
        raise gr.Error("Il profilo creator nel manifest non è valido.")
    if not isinstance(brief, str) or len(brief) > 4000:
        raise gr.Error("Il brief nel manifest non è valido.")
    media = folder / "media"
    paths = []
    for filename in manifest.get("filenames", []):
        if filename != Path(filename).name:
            raise gr.Error("Manifest progetto non valido.")
        path = media / filename
        if not path.is_file() or path.is_symlink():
            raise gr.Error(f"File progetto mancante: {filename}")
        paths.append(str(path))
    if not paths:
        raise gr.Error("Il progetto non contiene media.")
    audio_path = None
    if manifest.get("audio_file"):
        audio_path = (folder / manifest["audio_file"]).resolve(strict=True)
        if not audio_path.is_relative_to(folder) or not audio_path.is_file():
            raise gr.Error("Percorso audio nel progetto non valido.")
    next_action = "premi Analizza" if audio_path else "aggiungi la musica e premi Analizza"
    return (paths, gr.update(value=creator), brief,
            f"✅ Progetto **{name}** caricato ({len(paths)} media). Controlla il brief, {next_action}.",
            str(audio_path) if audio_path else None)


def _as_path(f) -> Path:
    return Path(getattr(f, "name", f))


def _make_thumb(path: Path, kind: str, out: Path) -> None:
    if kind == "video":
        subprocess.run(
            ["ffmpeg", "-y", "-ss", "0", "-i", str(path), "-frames:v", "1",
             "-vf", "scale=240:-2", str(out), "-loglevel", "error"],
            check=False,
        )
    if not out.exists():
        try:
            im = Image.open(path)
            im.thumbnail((240, 426))
            im.convert("RGB").save(out, "JPEG", quality=85)
        except Exception:  # noqa: BLE001
            pass


def _waveform_png(audio_path: Path, beat_info, out: Path, w: int = 1200, h: int = 240) -> None:
    try:
        import librosa
        y, sr = librosa.load(str(audio_path), sr=8000, mono=True)
    except Exception:  # noqa: BLE001
        y, sr = np.zeros(8000), 8000
    dur = max(1e-3, len(y) / sr)
    env = np.abs(y)
    step = max(1, len(env) // w)
    cols = np.array([env[i * step:(i + 1) * step].max() if (i * step) < len(env) else 0.0
                     for i in range(w)])
    cols = cols / (cols.max() or 1.0)

    img = Image.new("RGB", (w, h), "#0f1117")
    d = ImageDraw.Draw(img)
    mid = h // 2
    for x, v in enumerate(cols):
        bar = int(v * (h * 0.44))
        d.line([(x, mid - bar), (x, mid + bar)], fill="#5b8def")
    for t in getattr(beat_info, "beat_times", []):
        d.line([(int(t / dur * w), 0), (int(t / dur * w), h)], fill="#343a46")
    for t in getattr(beat_info, "downbeat_times", []):
        d.line([(int(t / dur * w), 0), (int(t / dur * w), h)], fill="#e0b341")
    for t in getattr(beat_info, "strong_times", []):
        d.line([(int(t / dur * w), h - 16), (int(t / dur * w), h)], fill="#e0553b")
    img.save(out)


def _rows_from_table(table) -> list[list]:
    if table is None:
        return []
    if hasattr(table, "values"):
        return table.values.tolist()
    return [list(r) for r in table]


# --- logica pura (nessun oggetto Gradio) ---------------------------------
def _do_analyze(files, audio, finale_files=None):
    if not files:
        raise gr.Error("Carica almeno una foto o un video.")
    if not audio:
        raise gr.Error("Carica un file audio (mp3 o wav).")

    work_root = DATA_DIR / "draft-media"
    work_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="reel_", dir=work_root))
    media_dir = work / "media"
    media_dir.mkdir()

    metas = []
    for i, f in enumerate(files):
        src = _as_path(f)
        if src.suffix.lower() not in IMAGE_EXT | VIDEO_EXT:
            continue
        dst = media_dir / f"{i:03d}_{src.name}"
        if src.suffix.lower() in IMAGE_EXT:
            copy_upright_image(src, dst)
        else:
            shutil.copy2(src, dst)
        kind = "video" if src.suffix.lower() in VIDEO_EXT else "image"
        thumb = work / f"thumb_{i:03d}.jpg"
        _make_thumb(dst, kind, thumb)
        metas.append({"name": dst.name, "orig": src.name, "kind": kind,
                      "thumb": str(thumb) if thumb.exists() else str(dst)})
    if not metas:
        raise gr.Error("Nessun file valido. Formati: " + ", ".join(e.lstrip(".") for e in ALLOWED_EXT))

    finale_dir = work / "finale"
    finale_dir.mkdir()
    finale_paths = []
    for i, f in enumerate(finale_files or []):
        src = _as_path(f)
        if src.suffix.lower() not in IMAGE_EXT | VIDEO_EXT:
            continue
        dst = finale_dir / f"{i:03d}_{src.name}"
        if src.suffix.lower() in IMAGE_EXT:
            copy_upright_image(src, dst)
        else:
            shutil.copy2(src, dst)
        finale_paths.append(str(dst))

    audio_source = _as_path(audio)
    audio_path = work / ("audio" + audio_source.suffix.lower())
    shutil.copy2(audio_source, audio_path)
    bi = detect_beats(audio_path)
    wave = work / "wave.png"
    _waveform_png(audio_path, bi, wave)

    gallery = [(m["thumb"], f'{i} · {m["orig"]}') for i, m in enumerate(metas)]
    table = [[i, m["orig"], True, i] for i, m in enumerate(metas)]
    info = (
        f"### Brano · {bi.tempo:.0f} BPM\n"
        f"- {len(bi.beat_times)} beat · {len(bi.downbeat_times)} downbeat (gialli) · "
        f"{len(bi.strong_times)} beat forti (rossi) · {len(bi.onset_times)} transienti\n"
        f"- durata {bi.duration:.1f}s · **{len(metas)} media** caricati"
    )
    state = {"work": str(work), "media_dir": str(media_dir),
             "audio": str(audio_path), "metas": metas, "finale_files": finale_paths,
             "beat": {"bpm": round(float(bi.tempo)), "duration": round(float(bi.duration), 1),
                      "downbeats": int(len(bi.downbeat_times))}}
    write_draft(DATA_DIR, {"state": state, "table": table, "info": info,
                           "wave": str(wave)})
    return state, gallery, table, str(wave), info


def _do_generate(state, p: dict, force_seed, progress) -> tuple[str, str]:
    if not state:
        raise gr.Error("Premi prima «Analizza».")
    media_dir = Path(state["media_dir"])
    audio_path = Path(state["audio"])
    metas = state["metas"]
    work = Path(state["work"])

    chosen = []
    for r in _rows_from_table(p.get("table")):
        try:
            idx, keep, order = int(r[0]), bool(r[2]), float(r[3])
        except (ValueError, TypeError, IndexError):
            continue
        if keep and 0 <= idx < len(metas):
            chosen.append((order, idx))
    if not chosen:
        chosen = [(i, i) for i in range(len(metas))]
    chosen.sort()

    order_file = work / "order.txt"
    order_file.write_text("\n".join(metas[idx]["name"] for _, idx in chosen))
    out_path = work / "reel.mp4"

    seed_val = p.get("seed")
    cfg = RenderConfig(
        media_dir=media_dir, audio=audio_path, out=out_path, order_file=order_file,
        aspect=ASPECT_LABELS[p["aspect"]],
        style=STYLE_BY_LABEL.get(p["style"], "vivid"),
        cuts_per_beat=SPEEDS[p["speed"]],
        beat_offset=float(p.get("beat_offset") or 0.0),
        xfade_duration=max(0.0, float(p.get("xfade_ms") or 0.0) / 1000.0),
        strong_beats_only=bool(p.get("strong_only")),
        dynamic_pacing=bool(p.get("dynamic_pacing")),
        snap_to_onsets=bool(p.get("snap_onsets")),
        transition_mode=TRANSITIONS.get(p.get("transition"), "auto"),
        edit_style=EDIT_STYLE_BY_LABEL.get(p.get("edit_style"), "clean"),
        motion=MOTION_BY_LABEL.get(p.get("motion"), "kenburns"),
        motion_intensity=float(p.get("motion_intensity") or 1.0),
        impact_effects=tuple(IMPACT_BY_LABEL.get(x, x) for x in (p.get("impact") or [])),
        variety=float(p.get("variety") if p.get("variety") is not None else 0.3),
        grain=float(p.get("grain") or 0.0),
        vignette=bool(p.get("vignette")),
        chromatic=bool(p.get("chromatic")),
        slowmo=bool(p.get("slowmo")),
        hold_prob=float(p.get("hold_prob") or 0.0),
        audio_start=float(p.get("audio_start") or 0.0),
        hook_hold=float(p.get("hook_hold") or 0.0),
        title_text=(p.get("title_text") or "").strip(),
        title_pos=TITLE_POS.get(p.get("title_pos"), "center"),
        title_start=float(p.get("title_start") or 0.0),
        title_duration=float(p.get("title_dur") or 2.5),
        watermark=Path(_as_path(p["wm_file"])) if p.get("wm_file") else None,
        watermark_pos=WM_POS.get(p.get("wm_pos"), "br"),
        watermark_scale=float(p.get("wm_scale") or 0.15),
        watermark_opacity=float(p.get("wm_opacity") or 0.85),
        shuffle=bool(p.get("shuffle")),
        max_duration=float(p["max_dur"]) if p.get("max_dur") else None,
        target_duration=AUTOCUT.get(p.get("duration_preset")),
        crescendo_finale=bool(p.get("crescendo_finale")),
        finale_media_dir=Path(state["work"]) / "finale",
        separate_person=bool(p.get("separate_person")),
        subject_style=STYLE_BY_LABEL.get(p.get("subject_style"), "vivid"),
        background_style=STYLE_BY_LABEL.get(p.get("background_style"), "moody"),
        background_blur=float(p.get("background_blur") or 0.0),
        background_dim=float(p.get("background_dim") or 0.0),
        subject_spot=float(p.get("subject_spot") or 0.0),
        subject_dim=float(p.get("subject_dim") or 0.0),
        outline_color=p.get("outline_color", "none"),
        outline_strength=float(p.get("outline_strength") or 0.0),
        outline_width=float(p.get("outline_width") or 2.0),
        cross_strobe=bool(p.get("cross_strobe")),
        scene_profiles=state.get("scene_profiles", {}) if p.get("use_scene_ai") else {},
        seed=force_seed if force_seed is not None
        else (int(seed_val) if seed_val not in (None, "") else None),
    )

    try:
        run_pipeline(cfg, progress=lambda fr, msg: progress(fr, desc=msg))
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        raise gr.Error(f"Errore durante il montaggio: {e}")
    return str(out_path), str(out_path)


with gr.Blocks(title="autoedit — montaggio automatico") as demo:
    state = gr.State()
    gr.HTML(comic_styles())
    gr.Markdown(
        "# 🎬 HyperSpace Reel Editor\n"
        "**1.** Carica foto/video + una canzone e premi **Analizza**. "
        "**2.** Descrivi il reel nel brief HyperSpace e rivedi le impostazioni. "
        "**3.** Premi **Genera**.\n\n"
        "*Il formato scelto non concede diritti musicali: verifica il brano e la sua "
        "durata disponibile nel catalogo TikTok prima di pubblicare.*"
    )

    with gr.Accordion("🔗 Progetti preparati in WebUI", open=False):
        with gr.Row():
            webui_project = gr.Dropdown(_list_webui_projects(), label="Progetto WebUI")
            webui_refresh = gr.Button("Aggiorna elenco")
            webui_open = gr.Button("Apri progetto", variant="secondary")
        webui_status = gr.Markdown()
        gr.HTML(comics_for("webui_project"))

    with gr.Row():
        files = gr.File(label="Foto e video", file_count="multiple", file_types=ALLOWED_EXT)
        audio = gr.Audio(label="Canzone (mp3 / wav)", type="filepath")
    with gr.Accordion("🎭 Crescendo e finale acrobatico", open=False):
        crescendo_finale = gr.Checkbox(label="1:50 preparazione lenta + 10 secondi di scatti rapidi (totale 2:00)")
        cross_strobe = gr.Checkbox(label="Croce di luce stroboscopica sui battiti del finale")
        finale_files = gr.File(label="Scatti acrobatici per il finale", file_count="multiple",
                               file_types=ALLOWED_EXT)
        gr.Markdown("Metti nei media principali l'emersione dal buio, l'avvicinamento al palo e lo stretching in ordine. "
                    "Qui carica molte pose acrobatiche diverse. Il cambio avviene al secondo 110 del video.")
    gr.HTML(comics_for("files", "audio"))
    analizza_btn = gr.Button("🔍 Analizza", variant="secondary")
    draft_status = gr.Markdown()

    info_md = gr.Markdown()
    wave_img = gr.Image(label="Forma d'onda + beat / downbeat / beat forti", interactive=False)
    gallery = gr.Gallery(label="Media caricati", columns=6, height="auto")
    table = gr.Dataframe(
        headers=TABLE_HEADERS, datatype=["number", "str", "bool", "number"],
        column_count=(4, "fixed"), interactive=True,
        label="Ordine e selezione — cambia «ordine» per riordinare, togli «includi» per escludere",
    )
    gr.HTML(comics_for("table"))

    gr.Markdown("### 1 · Descrivi il reel")
    gr.Markdown("Scrivi il risultato che vuoi. HyperSpace userà brief, musica e media per preparare le impostazioni; puoi rivederle prima del render.")
    creator_profile = gr.Dropdown(
        ["Anna", "Aurora", "Altro progetto"], value="Altro progetto",
        label="Progetto / creator")
    brief_text = gr.Textbox(
        lines=3, label="Che video vuoi ottenere?",
        placeholder="Es. Tono cinematografico e intimo, apertura lenta e scura, movimento morbido, titolo breve e leggibile, chiusura energica sui beat.")
    with gr.Row():
        brief_btn = gr.Button("✨ Prepara le impostazioni con HyperSpace", variant="primary")
        brief_status = gr.Markdown("Collegamento HyperSpace: usa il modello rilevato automaticamente o configurane uno nelle impostazioni avanzate.")

    with gr.Accordion("👁️ Analisi visiva delle scene (modello VL locale)", open=False):
        scene_ai_btn = gr.Button("Analizza soggetto e sfondo delle scene selezionate")
        use_scene_ai = gr.Checkbox(value=False,
                                   label="Applica colori, movimenti e impatti sui beat forti suggeriti")
        scene_ai_status = gr.Markdown("Il modello descrive le scene; non crea una maschera pixel del soggetto.")
        gr.HTML(comics_for("scene_ai"))

    with gr.Accordion("🎭 Persona e sfondo separati", open=False):
        separate_person = gr.Checkbox(label="Riconosci la persona e applica color grade separati")
        with gr.Row():
            subject_style = gr.Dropdown(list(STYLE_BY_LABEL), value=COLOR_LABELS["vivid"],
                                        label="Colore della persona")
            background_style = gr.Dropdown(list(STYLE_BY_LABEL), value=COLOR_LABELS["moody"],
                                           label="Colore dello sfondo")
            background_blur = gr.Slider(0, 12, value=0, step=0.5, label="Sfocatura dello sfondo")
        with gr.Row():
            background_dim = gr.Slider(0, 0.8, value=0, step=0.05,
                                       label="Oscuramento sfondo (0 = nessuno)")
            subject_spot = gr.Slider(0, 0.4, value=0, step=0.02,
                                     label="Luce sulla persona (0 = nessuna)")
            subject_dim = gr.Slider(0, 0.8, value=0, step=0.02,
                                    label="Oscura la persona (per una sagoma appena visibile)")
        with gr.Row():
            outline_color = gr.Dropdown(
                ["none", "cyan", "magenta", "lime", "white"], value="none",
                label="Contorno luminoso aderente alla persona")
            outline_strength = gr.Slider(0, 1, value=0, step=0.05,
                                         label="Intensità del contorno")
            outline_width = gr.Slider(1, 12, value=3, step=0.5,
                                      label="Spessore del bagliore")
        mask_preview_btn = gr.Button("Mostra maschera della prima scena selezionata")
        mask_preview = gr.Image(label="Maschera persona: bianco = soggetto", interactive=False)
        gr.Markdown("Usa Vision di macOS per foto e video. La maschera segue la persona; "
                    "il palo e gli oggetti restano normalmente nello sfondo. "
                    "Il primo render del video può richiedere alcuni minuti per preparare le maschere.")

    gr.Markdown("### Montaggio")
    edit_style = gr.Dropdown(
        list(EDIT_STYLE_BY_LABEL), value=EDIT_STYLE_LABELS["clean"],
        label="Stile di montaggio — ricette coerenti stile TikTok/CapCut (il pannello Effetti serve solo con «Personalizzato»)")
    gr.HTML(comics_for("edit_style"))
    with gr.Row():
        speed = gr.Dropdown(list(SPEEDS), value=list(SPEEDS)[1], label="Velocità dei tagli")
        aspect = gr.Dropdown(list(ASPECT_LABELS), value=list(ASPECT_LABELS)[0], label="Formato video")
        transition_mode = gr.Dropdown(list(TRANSITIONS), value=list(TRANSITIONS)[0],
                                      label="Transizioni (solo «Personalizzato»)")
    gr.HTML(comics_for("speed", "aspect", "transition"))
    duration_preset = gr.Dropdown(list(AUTOCUT), value="30 secondi",
                                  label="Autocut — durata esatta del reel")
    gr.HTML(comics_for("duration_preset"))

    with gr.Accordion("💾 Preset", open=False):
        with gr.Row():
            preset_dd = gr.Dropdown(_list_presets(), label="Preset salvati", scale=3)
            carica_btn = gr.Button("Carica", scale=1)
            elimina_btn = gr.Button("Elimina", variant="stop", scale=1)
        with gr.Row():
            preset_name = gr.Textbox(label="Nome per salvare le impostazioni attuali", scale=3)
            salva_btn = gr.Button("Salva", variant="secondary", scale=1)
        gr.HTML(comics_for("preset"))

    with gr.Accordion("⚙️ Connessione HyperSpace / provider AI", open=False):
        _llm0 = load_llm_config()
        llm_detect_btn = gr.Button("🔎 Trova automaticamente HyperSpace", variant="secondary")
        with gr.Row():
            llm_provider = gr.Radio(list(LLM_PROVIDERS),
                                    value=PROVIDER_LABEL.get(_llm0.provider, list(LLM_PROVIDERS)[0]),
                                    label="Provider")
            llm_model = gr.Textbox(value=_llm0.model, label="Modello",
                                   placeholder="es. llama3.1  ·  qwen2.5:7b  ·  claude-opus-5")
        with gr.Row():
            llm_base_url = gr.Textbox(value=_llm0.base_url, label="Base URL (vuoto = default del provider)",
                                      placeholder="HyperSpace: http://127.0.0.1:8085/v1")
            llm_key = gr.Textbox(value=_llm0.api_key, label="API key (le locali spesso non la vogliono)",
                                 type="password")
        llm_save_btn = gr.Button("Salva connessione", variant="secondary")
        llm_status = gr.Markdown()
        gr.HTML(comics_for("provider", "model", "base_url", "api_key"))

    with gr.Accordion("🎨 Effetti (solo con stile «Personalizzato»)", open=False):
        with gr.Row():
            style = gr.Dropdown(list(STYLE_BY_LABEL), value=COLOR_LABELS["vivid"],
                                label="Colore / grade di base")
            motion = gr.Dropdown(list(MOTION_BY_LABEL), value=MOTION_LABELS["kenburns"],
                                 label="Movimento")
            motion_intensity = gr.Slider(0.2, 2.5, value=1.0, step=0.1, label="Intensità movimento")
        variety = gr.Slider(0.0, 1.0, value=0.3, step=0.05,
                            label="Varietà — quanto grade/movimento cambiano da clip a clip (anti-monotonia)")
        impact_group = gr.CheckboxGroup(
            list(IMPACT_BY_LABEL), value=[IMPACT_LABELS["flash"], IMPACT_LABELS["rgbsplit"]],
            label="Effetti d'impatto sui beat forti (scelti a caso fra questi)")
        with gr.Row():
            grain = gr.Slider(0.0, 1.0, value=0.0, step=0.05, label="Grana")
            vignette = gr.Checkbox(value=False, label="Vignettatura")
            chromatic = gr.Checkbox(value=False, label="Aberrazione cromatica")
        with gr.Row():
            slowmo = gr.Checkbox(value=False,
                                 label="Slow-motion + accelerazioni sulle clip video")
            hold_prob = gr.Slider(0.0, 0.4, value=0.0, step=0.02,
                                  label="Clip «hero» tenute 2 beat (0 = mai)")
        gr.HTML(comics_for("style", "motion", "motion_intensity", "variety", "impact",
                           "grain", "vignette", "chromatic", "slowmo", "hold_prob"))

    with gr.Accordion("✍️ Testo / titolo", open=False):
        title_text = gr.Textbox(label="Testo del titolo (vuoto = niente)", lines=2)
        with gr.Row():
            title_pos = gr.Dropdown(list(TITLE_POS), value="Al centro", label="Posizione")
            title_start = gr.Number(value=0.0, label="Compare al secondo")
            title_dur = gr.Number(value=2.5, label="Resta per (s)")
        gr.HTML(comics_for("title_text", "title_pos", "title_start", "title_dur"))

    with gr.Accordion("🖼️ Logo / watermark", open=False):
        wm_file = gr.Image(label="PNG con trasparenza (vuoto = niente)", type="filepath")
        with gr.Row():
            wm_pos = gr.Dropdown(list(WM_POS), value=list(WM_POS)[0], label="Angolo")
            wm_scale = gr.Slider(0.05, 0.40, value=0.15, step=0.01, label="Dimensione")
            wm_opacity = gr.Slider(0.2, 1.0, value=0.85, step=0.05, label="Opacità")
        gr.HTML(comics_for("wm_file", "wm_pos", "wm_scale", "wm_opacity"))

    with gr.Accordion("⏱️ Ritmo / sincronia / hook", open=False):
        with gr.Row():
            hook_hold = gr.Slider(0.0, 2.0, value=0.0, step=0.1,
                                  label="Hook — tieni fermo il primo clip (s)")
            audio_start = gr.Number(value=0.0, label="Inizio canzone (s) — salta l'intro")
        beat_offset = gr.Slider(-0.20, 0.20, value=0.0, step=0.01,
                                label="Sincronia fine (s) — tagli in ritardo: alza · in anticipo: abbassa")
        xfade_ms = gr.Slider(0, 500, value=180, step=10,
                             label="Durata transizioni (ms) — sotto ~70 = stacchi netti sul beat")
        snap_onsets = gr.Checkbox(value=True, label="Aggancia i tagli ai transienti reali (consigliato)")
        dynamic_pacing = gr.Checkbox(value=False, label="Ritmo dinamico — più tagli nei momenti intensi")
        strong_only = gr.Checkbox(value=False, label="Taglia solo sui beat forti")
        shuffle = gr.Checkbox(value=False, label="Ordine casuale dei media (ignora la tabella)")
        max_dur = gr.Number(label="Durata massima (solo Autocut Libero/manuale; vuoto = tutta la canzone)", value=None)
        seed = gr.Number(label="Seed (stesso numero = stesso risultato)", value=None, precision=0)
        gr.HTML(comics_for("hook_hold", "audio_start", "beat_offset", "xfade_ms",
                           "snap_onsets", "dynamic_pacing", "strong_only", "shuffle",
                           "max_dur", "seed"))

    with gr.Row():
        genera_btn = gr.Button("🎬 Genera", variant="primary", size="lg")
        variante_btn = gr.Button("🎲 Variante", variant="secondary")
    with gr.Row():
        out_video = gr.Video(label="Anteprima")
        out_file = gr.File(label="Scarica il video")

    def _params(d: dict) -> dict:
        return {
            "table": d[table], "style": d[style], "speed": d[speed],
            "duration_preset": d[duration_preset], "aspect": d[aspect],
            "edit_style": d[edit_style],
            "transition": d[transition_mode], "motion": d[motion],
            "motion_intensity": d[motion_intensity], "variety": d[variety],
            "impact": d[impact_group], "grain": d[grain], "vignette": d[vignette],
            "chromatic": d[chromatic], "slowmo": d[slowmo], "hold_prob": d[hold_prob],
            "title_text": d[title_text], "title_pos": d[title_pos],
            "title_start": d[title_start], "title_dur": d[title_dur], "wm_file": d[wm_file],
            "wm_pos": d[wm_pos], "wm_scale": d[wm_scale], "wm_opacity": d[wm_opacity],
            "hook_hold": d[hook_hold], "audio_start": d[audio_start], "beat_offset": d[beat_offset],
            "xfade_ms": d[xfade_ms], "snap_onsets": d[snap_onsets], "dynamic_pacing": d[dynamic_pacing],
            "strong_only": d[strong_only], "shuffle": d[shuffle], "max_dur": d[max_dur],
            "seed": d[seed],
            "use_scene_ai": d[use_scene_ai],
            "crescendo_finale": d[crescendo_finale],
            "separate_person": d[separate_person],
            "subject_style": d[subject_style],
            "background_style": d[background_style],
            "background_blur": d[background_blur],
            "background_dim": d[background_dim],
            "subject_spot": d[subject_spot],
            "subject_dim": d[subject_dim],
            "outline_color": d[outline_color],
            "outline_strength": d[outline_strength],
            "outline_width": d[outline_width],
            "cross_strobe": d[cross_strobe],
        }

    def on_scene_ai(st, rows, progress=gr.Progress()):
        if not st:
            raise gr.Error("Premi prima Analizza per caricare le scene.")
        model = discover_vision_model()
        if not model:
            raise gr.Error("Nessun modello VL locale disponibile sul control-plane HyperSpace.")
        selected = []
        for row in _rows_from_table(rows):
            try:
                index = int(row[0])
                keep = bool(row[2])
            except (TypeError, ValueError, IndexError):
                continue
            if keep and 0 <= index < len(st["metas"]):
                selected.append(st["metas"][index])
        if not selected:
            raise gr.Error("Seleziona almeno una scena nella tabella.")
        if len(selected) > 20:
            raise gr.Error("Per l'analisi VL seleziona al massimo 20 scene per volta.")
        profiles = dict(st.get("scene_profiles", {}))
        failures = []
        for index, meta in enumerate(selected, 1):
            progress(index / len(selected), desc=f"Analisi visiva {index}/{len(selected)}")
            try:
                profiles[meta["name"]] = analyze_scene(Path(meta["thumb"]), model)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{meta['orig']}: {str(exc)[:90]}")
                if "occupato da un altro modello" in str(exc):
                    break
        updated = {**st, "scene_profiles": profiles}
        write_draft(DATA_DIR, {"state": updated})
        lines = [f"### Analizzate {len(selected) - len(failures)}/{len(selected)} scene con `{model}`"]
        for meta in selected:
            profile = profiles.get(meta["name"])
            if profile:
                lines.append(f"- **{meta['orig']}**: {profile['subject']} · sfondo: {profile['background']} "
                             f"→ {profile['style']} / {profile['motion']} / {profile['impact']}")
        if failures:
            lines.append("⚠️ Non analizzate: " + "; ".join(failures))
        lines.append("Attiva la casella qui sopra per usare i suggerimenti nel render.")
        return updated, "\n".join(lines)

    def on_generate(d, progress=gr.Progress()):
        return _do_generate(d[state], _params(d), None, progress)

    def on_variante(d, progress=gr.Progress()):
        return _do_generate(d[state], _params(d), random.randrange(1 << 30), progress)

    def preview_person_mask(st, rows):
        if not st:
            raise gr.Error("Premi prima Analizza.")
        selected = None
        for row in _rows_from_table(rows):
            try:
                if bool(row[2]):
                    selected = int(row[0])
                    break
            except (IndexError, TypeError, ValueError):
                continue
        if selected is None or not 0 <= selected < len(st["metas"]):
            raise gr.Error("Seleziona una scena nella tabella.")
        path = Path(st["media_dir"]) / st["metas"][selected]["name"]
        mask = prepare_person_mask(path, Path(st["work"]) / "person-masks")
        if mask.suffix != ".png":
            thumb = Path(st["work"]) / "mask-preview.png"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mask),
                            "-frames:v", "1", str(thumb)], check=True)
            return str(thumb)
        return str(mask)

    # componenti nell'ordine di PRESET_FIELDS (per Carica/Salva)
    PRESET_COMPONENTS = [
        edit_style, style, speed, duration_preset, aspect, transition_mode, motion, motion_intensity, variety,
        impact_group, grain, vignette, chromatic, slowmo, hold_prob, title_text, title_pos,
        title_start, title_dur, wm_pos, wm_scale, wm_opacity, hook_hold, audio_start, beat_offset,
        xfade_ms, snap_onsets, dynamic_pacing, strong_only, shuffle, max_dur, seed,
        use_scene_ai, crescendo_finale, separate_person, subject_style, background_style,
        background_blur, background_dim, subject_spot, subject_dim,
        outline_color, outline_strength, outline_width, cross_strobe,
    ]

    def load_preset(name):
        if not name:
            return [gr.update() for _ in PRESET_FIELDS]
        path = PRESETS_DIR / f"{name}.json"
        if not path.is_file():
            path = BUILTIN_PRESETS_DIR / f"{name}.json"
        if not path.is_file():
            raise gr.Error(f"Preset «{name}» non trovato.")
        data = json.loads(path.read_text())
        return [gr.update(value=data[f]) if f in data else gr.update() for f in PRESET_FIELDS]

    def save_preset(d):
        name = (d[preset_name] or "").strip()
        if not name:
            raise gr.Error("Scrivi un nome per il preset.")
        safe = re.sub(r"[^\w\- ]", "", name).strip() or "preset"
        data = {f: d[c] for f, c in zip(PRESET_FIELDS, PRESET_COMPONENTS)}
        PRESETS_DIR.mkdir(parents=True, exist_ok=True)
        (PRESETS_DIR / f"{safe}.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False))
        return gr.update(choices=_list_presets(), value=safe)

    def delete_preset(name):
        if name:
            if not (PRESETS_DIR / f"{name}.json").is_file():
                raise gr.Error("I preset inclusi non si eliminano; salva una copia personalizzata.")
            (PRESETS_DIR / f"{name}.json").unlink(missing_ok=True)
        return gr.update(choices=_list_presets(), value=None)

    # ---- Brief AI ----
    def _llm_cfg(d) -> LLMConfig:
        return LLMConfig(
            provider=LLM_PROVIDERS.get(d[llm_provider], "openai"),
            base_url=(d[llm_base_url] or "").strip(),
            model=(d[llm_model] or "").strip(),
            api_key=(d[llm_key] or "").strip(),
        )

    def save_llm(d):
        save_llm_config(_llm_cfg(d))
        return "✅ Connessione salvata in `llm_config.json`."

    def detect_llm():
        cfg = discover_control_plane()
        if cfg is None:
            return (gr.update(), gr.update(), gr.update(), gr.update(),
                    "❌ Control plane non raggiungibile su `127.0.0.1:8085` o nessun modello locale trovato.")
        return (PROVIDER_LABEL["openai"], cfg.model, cfg.base_url, cfg.api_key,
                f"✅ HyperSpace trovato: `{cfg.model}`. Nessuna configurazione manuale necessaria.")

    # componenti aggiornati da un brief, nell'ordine di BRIEF_KEYS
    BRIEF_COMPONENTS = [edit_style, style, motion, motion_intensity, transition_mode, variety,
                        impact_group, grain, vignette, chromatic, slowmo, hold_prob, speed,
                        aspect, duration_preset, strong_only, dynamic_pacing, xfade_ms, hook_hold, title_text,
                        title_pos]
    BRIEF_KEYS = ["edit_style", "style", "motion", "motion_intensity", "transition_mode",
                  "variety", "impact_effects", "grain", "vignette", "chromatic", "slowmo",
                  "hold_prob", "cuts_per_beat", "aspect", "target_duration",
                  "strong_beats_only", "dynamic_pacing",
                  "xfade_ms", "hook_hold", "title_text", "title_pos"]

    def _brief_update(key, ov):
        if key not in ov:
            return gr.update()
        v = ov[key]
        if key == "edit_style":
            return gr.update(value=EDIT_STYLE_LABELS.get(v, v))
        if key == "style":
            return gr.update(value=COLOR_LABELS.get(v, v))
        if key == "motion":
            return gr.update(value=MOTION_LABELS.get(v, v))
        if key == "transition_mode":
            return gr.update(value=TRANS_BY_VALUE.get(v, list(TRANSITIONS)[0]))
        if key == "impact_effects":
            return gr.update(value=[IMPACT_LABELS.get(x, x) for x in v])
        if key == "cuts_per_beat":
            return gr.update(value=SPEED_BY_VALUE.get(v, list(SPEEDS)[1]))
        if key == "aspect":
            return gr.update(value=ASPECT_BY_VALUE.get(v, list(ASPECT_LABELS)[0]))
        if key == "target_duration":
            return gr.update(value=next((label for label, seconds in AUTOCUT.items()
                                         if seconds == v), "30 secondi"))
        if key == "title_pos":
            return gr.update(value=TITLE_BY_VALUE.get(v, "Al centro"))
        return gr.update(value=v)

    def apply_brief(d):
        st = d[state]
        if not st:
            raise gr.Error("Carica foto/video e musica, poi premi Analizza prima di preparare il brief.")
        metas = st.get("metas", [])
        beat = st.get("beat", {})
        context = {
            "creator": d[creator_profile],
            "bpm": beat.get("bpm", "?"), "duration": beat.get("duration", "?"),
            "downbeats": beat.get("downbeats", "?"),
            "n_media": len(metas),
            "n_images": sum(1 for m in metas if m.get("kind") == "image"),
            "n_videos": sum(1 for m in metas if m.get("kind") == "video"),
            "names": [m.get("orig", "") for m in metas],
        }
        try:
            ov = suggest_overrides(_llm_cfg(d), d[brief_text] or "", context)
        except Exception as e:  # noqa: BLE001
            return [gr.update() for _ in BRIEF_COMPONENTS] + [f"❌ {e}"]
        if not ov:
            return [gr.update() for _ in BRIEF_COMPONENTS] + [
                "⚠️ Il modello non ha proposto impostazioni valide. Riprova con un brief più esplicito."]
        applied = ", ".join(f"`{k}`" for k in ov)
        return [_brief_update(k, ov) for k in BRIEF_KEYS] + [f"✅ Applicato: {applied}"]

    gen_set = {
        state, table, style, speed, duration_preset, aspect, edit_style, transition_mode, motion, motion_intensity,
        variety, impact_group, grain, vignette, chromatic, slowmo, hold_prob, title_text,
        title_pos, title_start, title_dur, wm_file, wm_pos, wm_scale, wm_opacity, hook_hold,
        audio_start, beat_offset, xfade_ms, snap_onsets, dynamic_pacing, strong_only, shuffle,
        max_dur, seed, use_scene_ai, crescendo_finale, separate_person, subject_style,
        background_style, background_blur, background_dim, subject_spot, subject_dim,
        outline_color, outline_strength, outline_width, cross_strobe,
    }
    draft_components = [table, *PRESET_COMPONENTS, creator_profile, brief_text, wm_file]
    draft_keys = ["table", *PRESET_FIELDS, "creator_profile", "brief_text", "wm_file"]

    def save_draft_settings(d):
        settings = {}
        for key, component in zip(draft_keys, draft_components):
            value = d[component]
            if key == "table":
                value = _rows_from_table(value)
            elif key == "wm_file" and value:
                source = _as_path(value)
                if source.is_file():
                    target = DATA_DIR / "draft-watermark" / source.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if source.resolve() != target.resolve():
                        shutil.copy2(source, target)
                    value = str(target)
            settings[key] = value
        write_draft(DATA_DIR, {"settings": settings})

    def restore_draft():
        saved = read_draft(DATA_DIR)
        st = saved.get("state")
        settings = saved.get("settings", {})
        values = [gr.update(value=settings[key]) if key in settings else gr.update()
                  for key in draft_keys]
        if not valid_state(st):
            status = "✅ Impostazioni della bozza recuperate." if settings else ""
            return [None, None, None, None, None, None, None, status] + values
        gallery_items = [(m["thumb"], f'{i} · {m["orig"]}')
                         for i, m in enumerate(st["metas"])]
        rows = settings.get("table", saved.get("table"))
        values[0] = gr.update(value=rows)
        return ([st, [str(Path(st["media_dir"]) / m["name"]) for m in st["metas"]],
                 st["audio"], st.get("finale_files", []), gallery_items, saved.get("wave"), saved.get("info"),
                 "✅ Bozza recuperata: media, audio e impostazioni ripristinati."] + values)

    demo.load(restore_draft,
              outputs=[state, files, audio, finale_files, gallery, wave_img, info_md, draft_status, *draft_components])
    for component in draft_components:
        component.change(save_draft_settings, inputs=set(draft_components), outputs=None)
    analizza_btn.click(_do_analyze, inputs=[files, audio, finale_files],
                       outputs=[state, gallery, table, wave_img, info_md])
    webui_refresh.click(lambda: gr.update(choices=_list_webui_projects()), outputs=[webui_project])
    webui_open.click(_open_webui_project, inputs=[webui_project],
                     outputs=[files, creator_profile, brief_text, webui_status, audio])
    scene_ai_btn.click(on_scene_ai, inputs=[state, table], outputs=[state, scene_ai_status])
    mask_preview_btn.click(preview_person_mask, inputs=[state, table], outputs=[mask_preview])
    genera_btn.click(on_generate, inputs=gen_set, outputs=[out_video, out_file])
    variante_btn.click(on_variante, inputs=gen_set, outputs=[out_video, out_file])

    carica_btn.click(load_preset, inputs=[preset_dd], outputs=PRESET_COMPONENTS)
    salva_btn.click(save_preset, inputs=gen_set | {preset_name}, outputs=[preset_dd])
    elimina_btn.click(delete_preset, inputs=[preset_dd], outputs=[preset_dd])

    _llm_set = {llm_provider, llm_model, llm_base_url, llm_key}
    llm_save_btn.click(save_llm, inputs=_llm_set, outputs=[llm_status])
    llm_detect_btn.click(detect_llm, outputs=[llm_provider, llm_model, llm_base_url,
                                              llm_key, llm_status])
    brief_btn.click(apply_brief, inputs=_llm_set | {state, creator_profile, brief_text},
                    outputs=BRIEF_COMPONENTS + [brief_status])


if __name__ == "__main__":
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("ATTENZIONE: 'ffmpeg' / 'ffprobe' non trovati nel PATH. "
              "Installali (es. 'brew install ffmpeg') o il montaggio fallira'.\n")
    demo.launch(inbrowser=True)
