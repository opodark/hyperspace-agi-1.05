"""Apple Vision person masks and separate foreground/background grades."""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from pathlib import Path

from .effects import COLOR_STYLES, crop_to_fill

SOURCE = Path(__file__).with_name("person_mask.swift")


def _run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "Comando fallito")[-1200:])


def mask_helper(cache_dir: Path) -> Path:
    """Compile the local macOS Vision helper once, with caches in writable storage."""
    if os.uname().sysname != "Darwin":
        raise RuntimeError("La separazione persona/sfondo richiede macOS Vision")
    cache_dir.mkdir(parents=True, exist_ok=True)
    binary = cache_dir / "person_mask"
    if binary.exists() and binary.stat().st_mtime >= SOURCE.stat().st_mtime:
        return binary
    sdk = Path("/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk")
    command = ["swiftc"]
    if sdk.is_dir():
        command += ["-sdk", str(sdk)]
    command += [str(SOURCE), "-o", str(binary)]
    environment = os.environ.copy()
    environment["CLANG_MODULE_CACHE_PATH"] = str(cache_dir / "clang-cache")
    environment["SWIFT_MODULE_CACHE_PATH"] = str(cache_dir / "swift-cache")
    result = subprocess.run(command, env=environment, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Impossibile compilare il supporto Vision: " + result.stderr[-1200:])
    return binary


def _key(path: Path) -> str:
    stat = path.stat()
    return hashlib.sha256(
        f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:{SOURCE.stat().st_mtime_ns}".encode()
    ).hexdigest()[:16]


def prepare_person_mask(path: Path, cache_dir: Path, fps: int = 4) -> Path:
    """Return a still PNG or a grayscale FFV1 mask video, cached by source file."""
    path = Path(path)
    cache_dir.mkdir(parents=True, exist_ok=True)
    helper = mask_helper(cache_dir)
    key = _key(path)
    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}:
        target = cache_dir / f"{key}.png"
        if not target.is_file():
            _run([str(helper), str(path), str(target)])
        return target

    target = cache_dir / f"{key}-{fps}fps.mkv"
    if target.is_file():
        return target
    with tempfile.TemporaryDirectory(prefix="person_frames_", dir=cache_dir) as frame_dir:
        folder = Path(frame_dir)
        _run(["ffmpeg", "-y", "-v", "error", "-i", str(path), "-vf", f"fps={fps}",
              str(folder / "frame_%06d.png")])
        frames = sorted(folder.glob("frame_*.png"))
        if not frames:
            raise RuntimeError("Nessun frame estratto dal video per la maschera persona")
        for offset in range(0, len(frames), 24):
            pairs = []
            for frame in frames[offset:offset + 24]:
                pairs.extend([str(frame), str(folder / ("mask_" + frame.name[6:]))])
            _run([str(helper), *pairs])
        temp_video = cache_dir / f"{key}-{fps}fps.partial.mkv"
        try:
            _run(["ffmpeg", "-y", "-v", "error", "-framerate", str(fps), "-i",
                  str(folder / "mask_%06d.png"), "-c:v", "ffv1", "-pix_fmt", "gray",
                  str(temp_video)])
            os.replace(temp_video, target)
        finally:
            temp_video.unlink(missing_ok=True)
    return target


def layer_filter(width: int, height: int, subject_style: str, background_style: str,
                 background_blur: float, background_dim: float = 0.0,
                 subject_spot: float = 0.0, subject_dim: float = 0.0,
                 outline_color: str = "none", outline_strength: float = 0.0,
                 outline_width: float = 2.0) -> str:
    """FFmpeg filter graph fed by source video [0:v] and a person mask [1:v]."""
    if subject_style not in COLOR_STYLES or background_style not in COLOR_STYLES:
        raise ValueError("Color grade persona/sfondo non valido")
    fill = crop_to_fill(1, 1, width, height)
    bg_parts = [COLOR_STYLES[background_style]] if COLOR_STYLES[background_style] else []
    if background_dim > 0:
        bg_parts.append(f"eq=brightness=-{min(float(background_dim), 0.8):g}")
    if background_blur > 0:
        bg_parts.append(f"gblur=sigma={min(float(background_blur), 20):g}")
    fg_parts = [COLOR_STYLES[subject_style]] if COLOR_STYLES[subject_style] else []
    if subject_spot > 0:
        fg_parts.append(f"eq=brightness={min(float(subject_spot), 0.4):g}")
    if subject_dim > 0:
        fg_parts.append(f"eq=brightness=-{min(float(subject_dim), 0.8):g}")
    bg = ",".join(bg_parts) or "null"
    fg = ",".join(fg_parts) or "null"
    color_map = {"none": "", "cyan": "0x00f5ff", "magenta": "0xff00c8",
                 "lime": "0x9dff00", "white": "0xffffff"}
    if outline_color not in color_map:
        raise ValueError("Colore contorno non valido")
    strength = max(0.0, min(1.0, float(outline_strength)))
    width_px = max(1.0, min(12.0, float(outline_width)))
    base = (f"[0:v]{fill},format=gbrp,split=2[bg0][fg0];"
            f"[bg0]{bg}[bg];[fg0]{fg}[fg];"
            f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
            f"format=gray,split=2[merge_mask][outline_mask];"
            f"[merge_mask]gblur=sigma=1,format=gbrp[mask];"
            f"[bg][fg][mask]maskedmerge[composite]")
    if outline_color == "none" or strength <= 0:
        return base.replace("split=2[merge_mask][outline_mask]", "null[merge_mask]") + ";[composite]null[out]"

    color = color_map[outline_color]
    radius = width_px * 0.65
    # Difference between a dilated silhouette and the original mask yields
    # an outline that follows the segmented person. Composite over the
    # already separated subject/background result, never as a screen-wide FX.
    return (base +
            f";[outline_mask]split=2[outline_src][mask_copy]"
            f";[outline_src]format=gray,lut=y='if(gt(val,16),255,0)',"
            f"gblur=sigma={radius:g},lut=y='if(gt(val,8),255,0)'[dilated]"
            f";[dilated][mask_copy]blend=all_expr='max(A-B,0)',format=gray[edge]"
            f";color=c={color}:s={width}x{height}:r=30,format=gbrp[color]"
            f";[color][edge]alphamerge,colorchannelmixer=aa={strength:g}[halo]"
            f";[composite][halo]overlay=shortest=1:format=auto[out]")
