# SPDX-License-Identifier: Apache-2.0
"""Pipeline di montaggio riutilizzabile.

Sia la CLI (`autoedit.cli`) sia la GUI (`gui.py`) costruiscono un
`RenderConfig` e chiamano `run_pipeline`, cosi' la logica di montaggio
vive in un solo posto.
"""
from __future__ import annotations

import logging
import random
import shutil
import tempfile
import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .beats import detect_beats, get_cut_times
from .edl import build_segments
from .effects import EDIT_STYLES, finish_chain
from .media import load_media
from .overlays import prepare_watermark_png, render_cross_light_png, render_subtitle_png, render_title_png
from .person_layers import prepare_person_mask
from .render import Segment, concat_with_xfade, mux_audio, render_segments
from .subtitles import parse_subtitles

log = logging.getLogger("autoedit")

# formato di output -> (larghezza, altezza) in pixel
ASPECTS = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
}

# callback di avanzamento: (frazione 0..1, messaggio) -> None
ProgressCB = Callable[[float, str], None]


@dataclass
class RenderConfig:
    media_dir: Path
    audio: Path
    out: Path = Path("output.mp4")
    order_file: Optional[Path] = None
    aspect: str = "9:16"
    fps: int = 30
    style: str = "vivid"
    cuts_per_beat: float = 1.0
    accent_every: int = 4
    xfade_duration: float = 0.18
    beat_offset: float = 0.0   # sposta la griglia di taglio di N secondi nel brano (+ = tagli piu' avanti)
    strong_beats_only: bool = False   # taglia solo sui beat con accento marcato
    dynamic_pacing: bool = False      # accelera nei tratti intensi, rallenta nei tratti calmi
    snap_to_onsets: bool = True       # aggancia i tagli sottodivisi ai transienti reali
    transition_mode: str = "auto"     # auto | cut | fade | slide | zoom | chaos
    shuffle: bool = False

    # --- stile di montaggio (ricetta) ---------------------------------
    # "custom" = usa i singoli parametri qui sotto; altrimenti una voce di
    # effects.EDIT_STYLES pilota movimento/transizioni/effetti/rifiniture.
    edit_style: str = "clean"

    # --- effetti (usati quando edit_style == "custom") --------------------
    motion: str = "kenburns"          # kenburns | zoom | sway | handheld | punch | bounce | static
    motion_intensity: float = 1.0     # 0.2 .. 2.5
    impact_effects: tuple = ()        # chiavi in effects.IMPACT_EFFECTS, usate sui beat forti
    variety: float = 0.3             # 0 = ogni clip uguale, 1 = grade/movimento cambiano spesso
    grain: float = 0.0               # 0 .. 1
    vignette: bool = False
    chromatic: bool = False           # leggera aberrazione cromatica su tutto
    slowmo: bool = False              # (custom) slow-mo + accelerazioni sulle clip video
    hold_prob: float = 0.0            # (custom) probabilita' clip "hero" tenuta 2 beat (0..0.4)
    max_duration: Optional[float] = None
    target_duration: Optional[int] = None  # autocut esatto: 30, 60 o 120 secondi
    crescendo_finale: bool = False
    finale_media_dir: Optional[Path] = None
    seed: Optional[int] = None
    keep_temp: bool = False
    jobs: int = 0
    chunk_size: int = 10
    scene_profiles: dict[str, dict] = field(default_factory=dict)  # VL: effetti clip-wide per file
    separate_person: bool = False
    subject_style: str = "vivid"
    background_style: str = "moody"
    background_blur: float = 0.0
    background_dim: float = 0.0
    subject_spot: float = 0.0
    subject_dim: float = 0.0
    outline_color: str = "none"
    outline_strength: float = 0.0
    outline_width: float = 2.0
    cross_strobe: bool = False

    # --- intro / audio -----------------------------------------------------
    audio_start: float = 0.0     # da che secondo del brano partire (salta l'intro)
    hook_hold: float = 0.0       # tieni fermo il primo clip N secondi prima che parta il montaggio

    # --- watermark / logo ------------------------------------------------
    watermark: Optional[Path] = None
    watermark_pos: str = "br"    # tl | tr | bl | br
    watermark_scale: float = 0.15
    watermark_opacity: float = 0.85

    # --- titolo in sovrimpressione -------------------------------------
    title_text: str = ""
    title_pos: str = "center"    # top | center | bottom
    title_start: float = 0.0
    title_duration: float = 2.5

    # --- sottotitoli (SRT / VTT) ---------------------------------------
    subtitles_file: Optional[Path] = None
    subtitles_text: str = ""
    subtitles_pos: str = "bottom"        # bottom | center | top
    subtitles_style: str = "tiktok_bold" # tiktok_bold | box | yellow | minimal
    subtitles_font_size: int = 0         # 0 = automatico in base alla risoluzione



_WM_POS = {"tl", "tr", "bl", "br"}


def apply_scene_profiles(segments, profiles: dict[str, dict]) -> None:
    """Apply validated VL suggestions to actual render segments, not just UI text."""
    from .effects import COLOR_STYLES, MOTION_MODES
    from .scene_vision import SAFE_IMPACTS
    for segment in segments:
        profile = profiles.get(segment.item.path.name, {})
        if profile.get("style") in COLOR_STYLES:
            segment.color_style = profile["style"]
        if profile.get("motion") in MOTION_MODES:
            segment.motion = profile["motion"]
        if segment.strong and profile.get("impact") in SAFE_IMPACTS - {"none"}:
            segment.impact_key = profile["impact"]


def fit_cut_times(cut_times, audio_duration: float, audio_start: float,
                  target_duration: int, hook_hold: float = 0.0) -> np.ndarray:
    """Beat-aligned internal cuts with an exact closing boundary."""
    if target_duration not in (30, 60, 120):
        raise ValueError("Autocut disponibile solo per 30, 60 o 120 secondi")
    audio_start = max(0.0, float(audio_start))
    end = audio_start + target_duration
    if end > float(audio_duration) + 0.01:
        raise ValueError(f"Il brano dal secondo {audio_start:g} dura meno di {target_duration}s: "
                         "scegli 30s, anticipa l'inizio o carica un brano piu lungo")
    hold = max(0.0, float(hook_hold))
    if 0 < hold < 0.3:
        hold = 0.3
    start = audio_start + hold
    if end - start < 0.18:
        raise ValueError("Hook troppo lungo per la durata scelta")
    planned = [start]
    for value in cut_times:
        beat = float(value)
        if beat - planned[-1] >= 0.18 and end - beat >= 0.18:
            planned.append(beat)
    planned.append(end)
    return np.asarray(planned, dtype=float)


def crescendo_cut_times(audio_start: float, audio_duration: float) -> np.ndarray:
    """Long restrained build, accelerating toward 110s; 40 hard cuts in the last 10s."""
    start = max(0.0, float(audio_start))
    if start + 120 > float(audio_duration) + 0.01:
        raise ValueError("Per il crescendo servono 120 secondi di audio dall'inizio scelto")
    times = [start]
    elapsed = 0.0
    while elapsed < 110 - 1e-6:
        # Opening holds are long enough to show movement; the pace grows steadily.
        step = 8.0 - 5.0 * (elapsed / 110.0)
        elapsed = min(110.0, elapsed + step)
        times.append(start + elapsed)
    times.extend(start + 110.0 + i * 0.25 for i in range(1, 41))
    return np.asarray(times, dtype=float)


def _build_overlays(cfg: RenderConfig, target_w: int, target_h: int, work_dir: Path,
                    beat_info=None, audio_offset: float = 0.0,
                    total_dur: float = 0.0) -> list[dict]:
    """Prepara i PNG di watermark, titolo e sottotitoli sincronizzati per mux_audio."""
    overlays: list[dict] = []

    if cfg.watermark and Path(cfg.watermark).is_file():
        wm_png = work_dir / "watermark.png"
        ww, wh = prepare_watermark_png(Path(cfg.watermark), target_w,
                                       max(0.03, min(0.6, cfg.watermark_scale)), wm_png)
        m = int(target_w * 0.04)
        pos = cfg.watermark_pos if cfg.watermark_pos in _WM_POS else "br"
        xy = {
            "tl": (m, m),
            "tr": (target_w - ww - m, m),
            "bl": (m, target_h - wh - m),
            "br": (target_w - ww - m, target_h - wh - m),
        }[pos]
        overlays.append({"png": wm_png, "x": xy[0], "y": xy[1],
                         "opacity": max(0.05, min(1.0, cfg.watermark_opacity))})

    if cfg.title_text and cfg.title_text.strip():
        ti_png = work_dir / "title.png"
        render_title_png(cfg.title_text, target_w, target_h, cfg.title_pos, ti_png)
        s = max(0.0, cfg.title_start)
        e = s + max(0.4, cfg.title_duration)
        overlays.append({"png": ti_png, "x": 0, "y": 0, "start": s, "end": e, "fade": 0.3})

    # Sottotitoli sincronizzati (da file SRT/VTT o testo incollato)
    sub_source = cfg.subtitles_file or (cfg.subtitles_text.strip() if cfg.subtitles_text else None)
    if sub_source:
        try:
            cues = parse_subtitles(sub_source)
            for idx, cue in enumerate(cues):
                s = cue.start - audio_offset
                e = cue.end - audio_offset
                if total_dur > 0:
                    if s >= total_dur or e <= 0.02:
                        continue
                    s = max(0.0, s)
                    e = min(total_dur, e)
                else:
                    if e <= 0.02:
                        continue
                    s = max(0.0, s)
                if e - s < 0.04:
                    continue
                sub_png = work_dir / f"sub_{idx:04d}.png"
                render_subtitle_png(cue.text, target_w, target_h, sub_png,
                                    pos=cfg.subtitles_pos, style=cfg.subtitles_style,
                                    font_size=cfg.subtitles_font_size)
                overlays.append({
                    "png": sub_png,
                    "x": 0,
                    "y": 0,
                    "start": s,
                    "end": e,
                    "fade": 0.03,
                })
        except Exception as exc:
            log.warning("Impossibile caricare i sottotitoli: %s", exc)

    if cfg.crescendo_finale and cfg.cross_strobe:
        cross_png = work_dir / "cross-light.png"
        render_cross_light_png(target_w, target_h, cross_png)
        start = cfg.audio_start + 110.0
        beat_times = [float(t) - cfg.audio_start for t in getattr(beat_info, "beat_times", [])
                      if start <= float(t) < start + 10.0]
        pulses = []
        for t in beat_times:
            if not pulses or t - pulses[-1] >= 0.28:
                pulses.append(t)
        if not pulses:
            pulses = [110.0 + i * 0.5 for i in range(20)]
        overlays.append({"png": cross_png, "x": 0, "y": 0,
                         "pulse_times": pulses, "pulse_width": 0.11})

    return overlays


def run_pipeline(cfg: RenderConfig, progress: Optional[ProgressCB] = None) -> Path:
    """Esegue l'intera pipeline e ritorna il percorso del video finale.

    `progress`, se passato, viene chiamato con (frazione, messaggio) a
    ogni tappa; gli stessi messaggi finiscono comunque nel logger.
    """
    def _p(frac: float, msg: str) -> None:
        log.info(msg)
        if progress is not None:
            progress(frac, msg)

    if cfg.aspect not in ASPECTS:
        raise ValueError(f"Formato non valido: {cfg.aspect}")

    rng = random.Random(cfg.seed)
    target_w, target_h = ASPECTS[cfg.aspect]

    _p(0.02, f"Carico i media da {cfg.media_dir} ...")
    media_items = load_media(cfg.media_dir, order_file=cfg.order_file)
    finale_items = load_media(cfg.finale_media_dir) if cfg.crescendo_finale and cfg.finale_media_dir else []
    if cfg.crescendo_finale and not finale_items:
        raise ValueError("Carica le immagini acrobatiche per il finale")
    _p(0.08, "Trovati %d media (%d foto, %d video)." % (
        len(media_items),
        sum(1 for m in media_items if m.kind == "image"),
        sum(1 for m in media_items if m.kind == "video"),
    ))

    _p(0.10, f"Rilevo il beat di {cfg.audio} ...")
    beat_info = detect_beats(cfg.audio)
    _p(0.20, "Tempo stimato: %.1f BPM, %d beat (%d forti, %d downbeat), %d transienti, "
             "durata audio %.1fs" % (
        beat_info.tempo, len(beat_info.beat_times), len(beat_info.strong_times),
        len(beat_info.downbeat_times), len(beat_info.onset_times), beat_info.duration,
    ))

    cut_times = get_cut_times(
        beat_info, cfg.cuts_per_beat,
        strong_only=cfg.strong_beats_only,
        dynamic=cfg.dynamic_pacing,
        snap=cfg.snap_to_onsets,
    )
    if cfg.crescendo_finale:
        cut_times = crescendo_cut_times(cfg.audio_start, beat_info.duration)
    elif cfg.beat_offset:
        cut_times = cut_times - cfg.beat_offset
        cut_times = cut_times[cut_times >= 0.0]
    if cfg.crescendo_finale:
        pass
    elif cfg.target_duration is not None:
        cut_times = fit_cut_times(cut_times, beat_info.duration, cfg.audio_start,
                                  cfg.target_duration, cfg.hook_hold)
    else:
        if cfg.audio_start and cfg.audio_start > 0:
            cut_times = cut_times[cut_times >= cfg.audio_start]
        if cfg.max_duration and len(cut_times):
            cut_times = cut_times[cut_times <= cut_times[0] + cfg.max_duration]
    if len(cut_times) < 2:
        raise ValueError("Troppo pochi punti di taglio: brano troppo corto, "
                         "audio-start / beat-offset / max-duration troppo aggressivi.")
    first_cut = float(cut_times[0])

    # ricetta ("clean"/"hype"/...) oppure None per la modalita' custom
    recipe = EDIT_STYLES.get(cfg.edit_style) if cfg.edit_style not in ("custom", "", None) else None
    if recipe:
        xfd = 0.0 if recipe["xfade_ms"] < 70 else recipe["xfade_ms"] / 1000.0
        finish = finish_chain(recipe["grain"], recipe["vignette"], recipe["chromatic"])
        motion_intensity = recipe["motion_intensity"]
        _p(0.21, f"Stile montaggio: {cfg.edit_style}")
    else:
        xfd = cfg.xfade_duration if cfg.transition_mode != "cut" else 0.0
        finish = finish_chain(grain=max(0.0, cfg.grain), vignette=bool(cfg.vignette),
                              chromatic=bool(cfg.chromatic))
        motion_intensity = cfg.motion_intensity

    segments = build_segments(
        media_items, cut_times, beat_info,
        accent_every=cfg.accent_every, shuffle=cfg.shuffle, rng=rng,
        transition_mode=cfg.transition_mode,
        base_style=cfg.style, base_motion=cfg.motion,
        variety=max(0.0, min(1.0, cfg.variety)),
        impact_pool=tuple(cfg.impact_effects or ()),
        recipe=None if cfg.crescendo_finale else recipe,
        video_speeds=([1.0, 1.0, 0.5, 2.0, 1.6] if cfg.slowmo else [1.0]),
        hold_prob=0.0 if cfg.crescendo_finale else max(0.0, min(0.4, cfg.hold_prob)),
    )
    if cfg.crescendo_finale:
        split = next(i for i, t in enumerate(cut_times[:-1]) if t >= cfg.audio_start + 110 - 1e-6)
        for i, segment in enumerate(segments):
            if i >= split:
                segment.item = finale_items[(i - split) % len(finale_items)]
            segment.transition = "fade"
            segment.motion = "static"
            segment.impact_key = ""
            segment.video_speed = 0.5 if i < split else 1.0
        xfd = 0.0
        finish = ""
        motion_intensity = 0.2
    if cfg.scene_profiles and not cfg.crescendo_finale:
        apply_scene_profiles(segments, cfg.scene_profiles)

    # "hook": un clip iniziale tenuto fermo prima che il montaggio parta.
    # L'audio viene fatto partire prima di altrettanto, cosi' il primo
    # taglio vero cade comunque sul beat.
    audio_offset = first_cut
    hold = max(0.0, cfg.hook_hold)
    if 0.0 < hold < 0.3:
        hold = 0.3
    if hold and segments and not cfg.crescendo_finale:
        intro = Segment(item=segments[0].item, duration=hold,
                        transition="fade", accented=False, strong=False)
        segments.insert(0, intro)
        audio_offset = max(0.0, first_cut - hold)

    _p(0.25, "Costruiti %d segmenti (durata totale prevista %.1fs)." % (
        len(segments), sum(s.duration for s in segments),
    ))

    work_dir = Path(tempfile.mkdtemp(prefix="autoedit_"))
    try:
        if cfg.separate_person:
            unique = sorted({s.item.path for s in segments})
            masks = {}
            mask_dir = cfg.out.parent / "person-masks"
            for index, path in enumerate(unique, 1):
                _p(0.25 + 0.04 * index / len(unique),
                   f"Maschera persona {index}/{len(unique)}: {path.name}")
                masks[path] = prepare_person_mask(path, mask_dir)
            for segment in segments:
                segment.person_mask = masks[segment.item.path]
        _p(0.30, f"Rendering dei segmenti in {work_dir} ...")
        render_segments(segments, target_w, target_h, cfg.fps, cfg.style, rng, work_dir,
                        jobs=cfg.jobs, xfade_duration=xfd, chunk_size=cfg.chunk_size,
                        motion=cfg.motion, motion_intensity=motion_intensity, finish=finish,
                        subject_style=cfg.subject_style, background_style=cfg.background_style,
                        background_blur=cfg.background_blur,
                        background_dim=cfg.background_dim, subject_spot=cfg.subject_spot,
                        subject_dim=cfg.subject_dim, outline_color=cfg.outline_color,
                        outline_strength=cfg.outline_strength, outline_width=cfg.outline_width)

        silent_path = work_dir / "silent.mp4"
        _p(0.80, "Assemblo i segmenti con le transizioni ...")
        total_dur = concat_with_xfade(segments, xfd, silent_path, cfg.fps,
                                      work_dir=work_dir, chunk_size=cfg.chunk_size,
                                      target_w=target_w, target_h=target_h)
        _p(0.92, "Montaggio video pronto (%.2fs)." % total_dur)

        overlays = _build_overlays(cfg, target_w, target_h, work_dir, beat_info,
                                  audio_offset=audio_offset, total_dur=total_dur)

        cfg.out.parent.mkdir(parents=True, exist_ok=True)
        _p(0.95, "Audio + testo/logo ..." if overlays else "Aggiungo la traccia audio ...")
        mux_audio(silent_path, cfg.audio, cfg.out, total_dur, fade_in=0.15,
                  fade_out=0.15 if cfg.crescendo_finale else 1.5,
                  audio_offset=audio_offset, overlays=overlays,
                  target_duration=120 if cfg.crescendo_finale else cfg.target_duration)
        _p(1.0, f"Fatto -> {cfg.out}")
    finally:
        if not cfg.keep_temp:
            shutil.rmtree(work_dir, ignore_errors=True)
        else:
            log.info("File temporanei conservati in %s", work_dir)

    return cfg.out
