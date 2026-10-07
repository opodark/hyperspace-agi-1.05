"""Overlay grafici (titolo, watermark/logo) resi con PIL.

Questa build di ffmpeg non ha il filtro `drawtext`, quindi il testo lo
disegniamo noi su un PNG trasparente e poi lo diamo in pasto al filtro
`overlay`. Stesso trucco per il logo: lo pre-scaliamo qui.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

# font "bold" plausibili su macOS / Linux; il primo che si carica vince.
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/SFNS.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _load_font(size: int) -> ImageFont.ImageFont:
    for p in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(p, size=size)
        except Exception:  # noqa: BLE001
            continue
    try:
        return ImageFont.load_default(size=size)   # Pillow >= 10
    except TypeError:
        return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        cur = ""
        for word in paragraph.split():
            trial = (cur + " " + word).strip()
            if not cur or draw.textlength(trial, font=font) <= max_w:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines or [""]


def render_title_png(text: str, w: int, h: int, pos: str, out: Path) -> None:
    """PNG trasparente grande quanto il video, col testo (a capo
    automatico) in alto / al centro / in basso, con contorno scuro per
    restare leggibile su qualsiasi sfondo."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    size = max(24, int(w * 0.075))
    font = _load_font(size)
    margin = int(w * 0.08)
    lines = _wrap(d, text.strip(), font, w - 2 * margin)
    line_h = int(size * 1.28)
    block_h = line_h * len(lines)

    if pos == "top":
        y = int(h * 0.08)
    elif pos == "bottom":
        y = int(h * 0.92) - block_h
    else:
        y = (h - block_h) // 2

    stroke = max(2, size // 22)
    for ln in lines:
        tw = d.textlength(ln, font=font)
        x = (w - tw) / 2
        for dx in (-stroke, 0, stroke):
            for dy in (-stroke, 0, stroke):
                if dx or dy:
                    d.text((x + dx, y + dy), ln, font=font, fill=(0, 0, 0, 210))
        d.text((x, y), ln, font=font, fill=(255, 255, 255, 255))
        y += line_h
    img.save(out)


def prepare_watermark_png(src: Path, target_w: int, scale: float, out: Path) -> tuple[int, int]:
    """Ridimensiona il logo a `scale` della larghezza del video,
    mantenendo l'alpha. Ritorna (w, h) finali in pixel."""
    im = Image.open(src).convert("RGBA")
    new_w = max(1, int(target_w * scale))
    new_h = max(1, int(round(im.height * new_w / im.width)))
    im = im.resize((new_w, new_h), Image.LANCZOS)
    im.save(out)
    return new_w, new_h


def render_cross_light_png(w: int, h: int, out: Path) -> None:
    """Soft luminous Latin-cross mask for brief beat-synced illumination."""
    shape = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(shape)
    cx = w // 2
    arm_y = int(h * 0.35)
    shaft_half = max(4, int(w * 0.045))
    arm_half = int(w * 0.38)
    arm_thick = max(5, int(w * 0.045))
    draw.rectangle((cx - shaft_half, int(h * 0.06), cx + shaft_half, int(h * 0.92)), fill=255)
    draw.rectangle((cx - arm_half, arm_y - arm_thick, cx + arm_half,
                    arm_y + arm_thick), fill=255)
    glow = shape.filter(ImageFilter.GaussianBlur(radius=max(6, int(w * 0.08))))
    glow = glow.point(lambda a: int(a * 0.55))
    core = shape.filter(ImageFilter.GaussianBlur(radius=max(2, int(w * 0.01))))
    core = core.point(lambda a: int(a * 0.45))
    alpha = ImageChops.add(glow, core)
    img = Image.new("RGBA", (w, h), (255, 246, 221, 0))
    img.putalpha(alpha)
    img.save(out)
