# SPDX-License-Identifier: Apache-2.0
"""Generate high-resolution explanatory visual diagrams for the HyperSpace 1.05 presentation.

Stile: tema scuro "mission control" coerente con web-node/progetto.html
(sfondo #070b18, accenti ciano / viola / rosa), rendering a 2x con glow e
testo a capo automatico. Stessi nomi file e proporzioni di prima, quindi il PDF
(generate_hyperspace_presentation.py) e la pagina web non cambiano layout.
"""

import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "docs" / "presentation_assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

S = 2  # supersampling: tutte le coordinate sono "logiche" (1200 px di larghezza)

# --------------------------------------------------------------------------
# Palette (identica alle variabili CSS di progetto.html)
# --------------------------------------------------------------------------
BG = "#070b18"
CARD = "#0d152a"
CARD2 = "#111b36"
LINE = "#263454"
TEXT = "#f4f6ff"
SOFT = "#c3cde6"
MUTED = "#8d9bbd"
CYAN = "#57e6d9"
VIOLET = "#9a7cff"
ROSE = "#f693bd"
OK = "#70e6aa"
AMBER = "#ffcf70"
BAD = "#ff8295"


def rgba(hexcolor, a=255):
    h = hexcolor.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


# --------------------------------------------------------------------------
# Font
# --------------------------------------------------------------------------
_FONT_CACHE = {}


def font(size, bold=False, mono=False):
    key = (size, bold, mono)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    px = int(round(size * S))
    f = None
    if mono and os.path.exists("/System/Library/Fonts/Menlo.ttc"):
        f = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", px, index=1 if bold else 0)
    elif os.path.exists("/System/Library/Fonts/SFNS.ttf"):
        try:
            f = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", px)
            f.set_variation_by_name("Bold" if bold else "Regular")
        except Exception:
            f = None
    if f is None:
        for path, idx in (
            ("/System/Library/Fonts/Helvetica.ttc", 1 if bold else 0),
            ("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf", 0),
        ):
            if os.path.exists(path):
                try:
                    f = ImageFont.truetype(path, px, index=idx)
                    break
                except Exception:
                    pass
    if f is None:
        f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f


# --------------------------------------------------------------------------
# Canvas
# --------------------------------------------------------------------------
class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.im = Image.new("RGBA", (w * S, h * S), rgba(BG))
        self._background()

    # -- background: aurora + griglia + stelle ------------------------------
    def _background(self):
        w, h = self.w * S, self.h * S
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        g = ImageDraw.Draw(glow)
        g.ellipse((-w * 0.15, -h * 0.5, w * 0.45, h * 0.55), fill=rgba("#253160", 210))
        g.ellipse((w * 0.62, -h * 0.4, w * 1.15, h * 0.5), fill=rgba("#38224c", 190))
        g.ellipse((w * 0.25, h * 0.75, w * 0.8, h * 1.4), fill=rgba("#12304a", 120))
        glow = glow.filter(ImageFilter.GaussianBlur(120 * S / 2))
        self.im = Image.alpha_composite(self.im, glow)

        grid = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(grid)
        step = 40 * S
        for x in range(0, w, step):
            d.line([(x, 0), (x, h)], fill=(255, 255, 255, 12), width=1)
        for y in range(0, h, step):
            d.line([(0, y), (w, y)], fill=(255, 255, 255, 12), width=1)
        mask = Image.new("L", (w, h), 0)
        md = ImageDraw.Draw(mask)
        for y in range(h):
            md.line([(0, y), (w, y)], fill=int(255 * (1 - y / h * 0.75)))
        grid.putalpha(Image.composite(grid.getchannel("A"), Image.new("L", (w, h), 0), mask))
        self.im = Image.alpha_composite(self.im, grid)

        # polvere di stelle deterministica
        stars = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(stars)
        seed = 7
        for _ in range(70):
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            x = seed % w
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            y = seed % h
            r = 1 + (seed % 2)
            sd.ellipse((x, y, x + r, y + r), fill=(255, 255, 255, 40 + seed % 60))
        self.im = Image.alpha_composite(self.im, stars)

    # -- primitive -----------------------------------------------------------
    def _layer(self):
        layer = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
        return layer, ImageDraw.Draw(layer)

    def _commit(self, layer):
        self.im = Image.alpha_composite(self.im, layer)

    def _glow(self, draw_fn, color, radius=14, alpha=160):
        layer = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        draw_fn(d, rgba(color, alpha))
        layer = layer.filter(ImageFilter.GaussianBlur(radius * S / 2))
        self._commit(layer)

    def rrect(self, box, r=16, fill=CARD, outline=LINE, width=1, glow=None, fill_alpha=235, dashed=False):
        x1, y1, x2, y2 = [v * S for v in box]
        rr = r * S
        if glow:
            self._glow(lambda d, c: d.rounded_rectangle((x1, y1, x2, y2), radius=rr, outline=c, width=max(2, int(width * S * 2))), glow, 12, 150)
        layer, d = self._layer()
        if fill:
            d.rounded_rectangle((x1, y1, x2, y2), radius=rr, fill=rgba(fill, fill_alpha))
        if outline:
            if dashed:
                self._dashed_rrect(d, (x1, y1, x2, y2), rr, rgba(outline), int(width * S))
            else:
                d.rounded_rectangle((x1, y1, x2, y2), radius=rr, outline=rgba(outline), width=int(width * S))
        self._commit(layer)

    def _dashed_rrect(self, d, box, rr, color, width, dash=14, gap=10):
        x1, y1, x2, y2 = box
        sides = [((x1 + rr, y1), (x2 - rr, y1)), ((x2, y1 + rr), (x2, y2 - rr)), ((x2 - rr, y2), (x1 + rr, y2)), ((x1, y2 - rr), (x1, y1 + rr))]
        for a, b in sides:
            self._dash(d, a, b, color, width, dash * S // 2, gap * S // 2)
        d2 = 2 * rr
        d.arc((x1, y1, x1 + d2, y1 + d2), 180, 270, fill=color, width=width)
        d.arc((x2 - d2, y1, x2, y1 + d2), 270, 360, fill=color, width=width)
        d.arc((x2 - d2, y2 - d2, x2, y2), 0, 90, fill=color, width=width)
        d.arc((x1, y2 - d2, x1 + d2, y2), 90, 180, fill=color, width=width)

    @staticmethod
    def _dash(d, a, b, color, width, dash, gap):
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if length == 0:
            return
        ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        pos = 0
        while pos < length:
            end = min(pos + dash, length)
            d.line([(a[0] + ux * pos, a[1] + uy * pos), (a[0] + ux * end, a[1] + uy * end)], fill=color, width=width)
            pos += dash + gap

    def text(self, xy, s, size=15, color=TEXT, bold=False, mono=False, anchor="la", spacing=0):
        layer, d = self._layer()
        f = font(size, bold, mono)
        x, y = xy[0] * S, xy[1] * S
        if spacing:
            # tracking manuale per etichette in maiuscolo
            total = sum(f.getlength(ch) + spacing * S for ch in s) - spacing * S
            if anchor[0] == "m":
                x -= total / 2
            elif anchor[0] == "r":
                x -= total
            for ch in s:
                d.text((x, y), ch, font=f, fill=rgba(color), anchor="l" + anchor[1])
                x += f.getlength(ch) + spacing * S
        else:
            d.text((x, y), s, font=f, fill=rgba(color), anchor=anchor)
        self._commit(layer)

    def measure(self, s, size=15, bold=False, mono=False):
        return font(size, bold, mono).getlength(s) / S

    def wrap(self, s, size, maxw, bold=False):
        lines = []
        for para in s.split("\n"):
            words, cur = para.split(), ""
            for wd in words:
                trial = f"{cur} {wd}".strip()
                if self.measure(trial, size, bold) <= maxw:
                    cur = trial
                else:
                    if cur:
                        lines.append(cur)
                    cur = wd
            lines.append(cur)
        return lines

    def paragraph(self, xy, s, size=14.5, color=SOFT, maxw=300, lh=1.42, bold=False):
        x, y = xy
        for line in self.wrap(s, size, maxw, bold):
            self.text((x, y), line, size, color, bold)
            y += size * lh
        return y

    def chip(self, xy, label, color=CYAN, size=11.5, solid=False):
        w = self.measure(label, size, True) + 1.25 * len(label) + 28
        x, y = xy
        h = size + 14
        self.rrect((x, y, x + w, y + h), r=h / 2, fill=color if solid else color, outline=color, width=1, fill_alpha=255 if solid else 34)
        self.text((x + w / 2, y + h / 2 + 0.5), label, size, BG if solid else color, True, anchor="mm", spacing=1.2)
        return w, h

    def dot(self, c, r, color, glow=True):
        x, y = c[0] * S, c[1] * S
        if glow:
            self._glow(lambda d, col: d.ellipse((x - r * S * 1.6, y - r * S * 1.6, x + r * S * 1.6, y + r * S * 1.6), fill=col), color, 8, 190)
        layer, d = self._layer()
        d.ellipse((x - r * S, y - r * S, x + r * S, y + r * S), fill=rgba(color))
        self._commit(layer)

    def badge_num(self, c, n, color, r=15):
        x, y = c
        self._glow(lambda d, col: d.ellipse(((x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S), outline=col, width=4 * S), color, 8, 200)
        layer, d = self._layer()
        d.ellipse(((x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S), fill=rgba(BG), outline=rgba(color), width=2 * S)
        self._commit(layer)
        self.text((x, y + 0.5), str(n), 15, color, True, anchor="mm")

    def line(self, p1, p2, color=CYAN, width=2, glow=True, dashed=False):
        a = (p1[0] * S, p1[1] * S)
        b = (p2[0] * S, p2[1] * S)
        if glow:
            self._glow(lambda d, c: d.line([a, b], fill=c, width=int(width * S * 2)), color, 8, 140)
        layer, d = self._layer()
        if dashed:
            self._dash(d, a, b, rgba(color), int(width * S), 9 * S, 7 * S)
        else:
            d.line([a, b], fill=rgba(color), width=int(width * S))
        self._commit(layer)

    def arrow(self, p1, p2, color=CYAN, width=2.5, head=11, dashed=False):
        # accorcia leggermente per non finire dentro il bordo della card
        ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
        tip = p2
        base = (p2[0] - head * 0.9 * math.cos(ang), p2[1] - head * 0.9 * math.sin(ang))
        self.line(p1, base, color, width, True, dashed)
        left = (tip[0] - head * math.cos(ang - 0.42), tip[1] - head * math.sin(ang - 0.42))
        right = (tip[0] - head * math.cos(ang + 0.42), tip[1] - head * math.sin(ang + 0.42))
        layer, d = self._layer()
        d.polygon([(v[0] * S, v[1] * S) for v in (tip, left, right)], fill=rgba(color))
        self._commit(layer)

    def ring(self, c, r, color, width=2, glow=True, alpha=255):
        x, y = c[0] * S, c[1] * S
        rr = r * S
        if glow:
            self._glow(lambda d, col: d.ellipse((x - rr, y - rr, x + rr, y + rr), outline=col, width=int(width * S * 2)), color, 12, 130)
        layer, d = self._layer()
        d.ellipse((x - rr, y - rr, x + rr, y + rr), outline=rgba(color, alpha), width=int(width * S))
        self._commit(layer)

    def orb(self, c, r, color):
        x, y = c[0] * S, c[1] * S
        rr = r * S
        self._glow(lambda d, col: d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=col), color, r * 0.55, 150)
        layer, d = self._layer()
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=rgba("#0a1124"), outline=rgba(color), width=3 * S)
        self._commit(layer)

    def save(self, name):
        out = self.im.convert("RGB").filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=2))
        out.save(ASSETS_DIR / name, optimize=True)


# --------------------------------------------------------------------------
# Elementi condivisi
# --------------------------------------------------------------------------
W, H = 1200, 820


def frame(num, tag, title, accent):
    """Cornice standard: tag, titolo a gradiente-accento, barra footer."""
    c = Canvas(W, H)
    c.chip((56, 46), tag, accent)
    c.text((56, 86), title, 28, TEXT, True)
    c.line((56, 134), (200, 134), accent, 3)
    c.line((200, 134), (1144, 134), LINE, 1, glow=False)
    # footer
    c.line((56, 780), (1144, 780), LINE, 1, glow=False)
    c.dot((64, 800), 4, CYAN)
    c.text((78, 800), "HYPERSPACE AGI 1.05", 11, MUTED, True, anchor="lm", spacing=1.6)
    c.text((1144, 800), f"{num:02d} / 12", 11, MUTED, True, mono=True, anchor="rm")
    c.text((600, 800), "zerozerocomputer.it/progetto", 11, MUTED, False, anchor="mm")
    return c


def card(c, box, color, title, body=None, num=None, title_size=18, body_size=14, glow=False, fill=CARD, dashed=False, pad=22, body_color=SOFT):
    x1, y1, x2, y2 = box
    c.rrect(box, 16, fill, color, 1.5, glow=color if glow else None, dashed=dashed)
    # barra accento a sinistra
    c.rrect((x1 + 1, y1 + 18, x1 + 5, y2 - 18), 2, color, None)
    tx = x1 + pad
    ty = y1 + pad - 2
    if num is not None:
        c.badge_num((x1 + pad + 12, ty + 12), num, color)
        tx = x1 + pad + 36
    lines = c.wrap(title, title_size, x2 - tx - pad + 4, True)
    for ln in lines:
        c.text((tx, ty), ln, title_size, color, True)
        ty += title_size * 1.3
    if body:
        c.paragraph((x1 + pad, ty + 8 if num is None else max(ty + 8, y1 + pad + 32)), body, body_size, body_color, x2 - x1 - 2 * pad)


# --------------------------------------------------------------------------
# 01 - Cover
# --------------------------------------------------------------------------
def gen_diagram_01():
    w, h = 1200, 433
    c = Canvas(w, h)
    cx, cy = 600, 205
    # orbite ellittiche
    for rx, ry, col, a in ((330, 120, CYAN, 120), (250, 90, VIOLET, 150), (410, 150, ROSE, 70)):
        layer, d = c._layer()
        d.ellipse(((cx - rx) * S, (cy - ry) * S, (cx + rx) * S, (cy + ry) * S), outline=rgba(col, a), width=S)
        c._commit(layer)
    # nodi satellite
    sats = [
        (190, 96, "MISSION CONTROL", "Orchestrazione DAG bounded", CYAN),
        (1010, 96, "STANZA ERMETICA", "Sandbox e gate di qualità", OK),
        (190, 310, "MEMORIA HERMES", "FTS5 e Dream Loop notturno", VIOLET),
        (1010, 310, "MESH PRIVATA", "Tailscale cifrata, 0 porte aperte", AMBER),
    ]
    for sx, sy, t, sub, col in sats:
        c.line((cx, cy), (sx + (140 if sx < 600 else -140), sy), col, 1.5, dashed=True)
    for sx, sy, t, sub, col in sats:
        c.rrect((sx - 150, sy - 44, sx + 150, sy + 44), 14, CARD, col, 1.5, glow=col, fill_alpha=255)
        c.text((sx, sy - 12), t, 15, col, True, anchor="mm", spacing=1.4)
        c.text((sx, sy + 15), sub, 12.5, SOFT, anchor="mm")
    c.orb((cx, cy), 104, CYAN)
    c.ring((cx, cy), 120, VIOLET, 1.5, alpha=150)
    c.text((cx, cy - 34), "HYPERSPACE", 19, TEXT, True, anchor="mm", spacing=2.5)
    c.text((cx, cy + 6), "1.05", 54, CYAN, True, anchor="mm")
    c.text((cx, cy + 50), "AGI OPERATING SYSTEM", 9.5, MUTED, True, anchor="mm", spacing=1.6)
    # pill
    label = "100% LOCALE  ·  ZERO LEAK DEI DATI  ·  HUMAN-IN-THE-LOOP"
    pw = c.measure(label, 11.5, True) + 1.4 * len(label) + 48
    c.rrect((cx - pw / 2, 392, cx + pw / 2, 422), 15, CARD, CYAN, 1, fill_alpha=245)
    c.text((cx, 407), label, 11.5, CYAN, True, anchor="mm", spacing=1.4)
    c.save("diagram_01_cover.png")


# --------------------------------------------------------------------------
# 02 - Paradigma
# --------------------------------------------------------------------------
def gen_diagram_02():
    c = frame(2, "PARADIGMA", "Dal chatbot al runtime governato", CYAN)

    # corsia 1: chatbot tradizionale
    c.rrect((56, 156, 1144, 436), 20, "#150f1c", BAD, 1.5, dashed=True)
    c.chip((78, 174), "MODELLO TRADIZIONALE", BAD)
    c.text((1122, 192), "rischio alto · instabile", 12.5, BAD, anchor="rm")
    steps = [
        ("Prompt", "Richiesta aperta in chat", MUTED),
        ("Loop LLM aperto", "Generazione libera, nessun vincolo", BAD),
        ("Azioni dirette sull'host", "Scrittura immediata su file", BAD),
        ("Disastro", "Loop infiniti, file rotti", BAD),
    ]
    xs = [78, 340, 620, 900]
    ws = [214, 232, 232, 222]
    for (t, s, col), x, wd in zip(steps, xs, ws):
        card(c, (x, 226, x + wd, 350), col, t, s, title_size=16, body_size=13.5, fill="#101426")
    for i in range(3):
        c.arrow((xs[i] + ws[i] + 4, 288), (xs[i + 1] - 6, 288), BAD if i else MUTED, 2.2, 10)
    c.paragraph((78, 372), "Criticità tipiche: l'AI dichiara di aver finito senza averlo fatto, sovrascrive codice host o consuma token all'infinito.", 14, BAD, 1030)

    # corsia 2: HyperSpace
    c.rrect((56, 462, 1144, 760), 20, "#0a1a1f", OK, 1.5, glow=OK)
    c.chip((78, 480), "HYPERSPACE 1.05", OK, solid=True)
    c.text((1122, 498), "sicuro · deterministico · verificabile", 12.5, OK, anchor="rm")
    steps = [
        ("Obiettivo", "Prompt + criteri oggettivi", CYAN),
        ("Mission Control", "DAG con budget rigido", CYAN),
        ("Stanza ermetica", "Sandbox Docker effimera", VIOLET),
        ("Gate di qualità", "Verifica binaria e test", OK),
        ("Review", "OK umano esplicito", OK),
    ]
    x = 78
    wd = 188
    for i, (t, s, col) in enumerate(steps):
        card(c, (x, 530, x + wd, 654), col, t, s, title_size=16, body_size=13.5, fill=CARD, glow=(i == 4))
        if i < 4:
            c.arrow((x + wd + 3, 592), (x + wd + 22, 592), col, 2.2, 9)
        x += wd + 25
    c.paragraph((78, 680), "Vantaggio: nessuna riga di codice tocca il tuo computer senza verifica algoritmica e tua autorizzazione.", 14, OK, 1030)
    c.save("diagram_02_paradigma.png")


# --------------------------------------------------------------------------
# 03 - Mission Control
# --------------------------------------------------------------------------
def gen_diagram_03():
    c = frame(3, "MISSION CONTROL", "Decomposizione a DAG bounded", VIOLET)

    card(c, (56, 164, 330, 292), CYAN, "Obiettivo operatore", "«Analizza i dati di vendita e crea una presentazione PDF»", title_size=17, body_size=13.5)
    card(c, (400, 164, 690, 292), VIOLET, "Planner", "Scompone in task ordinati con dipendenze rigide, validate prima dell'avvio.", title_size=17, body_size=13.5, glow=True)
    c.arrow((334, 228), (396, 228), CYAN, 2.5)

    tasks = [
        ("Task 1 · Lettura e ingestion", "repo-analyst · sola lettura", MUTED, 154),
        ("Task 2 · Compilazione e script", "coder · sandbox protetta", CYAN, 246),
        ("Task 3 · Validazione qualità", "verifier · quality gate", OK, 338),
    ]
    for t, s, col, y in tasks:
        c.rrect((790, y, 1144, y + 78), 14, CARD, col, 1.5, glow=col if col != MUTED else None)
        c.rrect((791, y + 14, 795, y + 64), 2, col, None)
        c.text((812, y + 24), t, 16, col if col != MUTED else TEXT, True)
        c.text((812, y + 50), s, 13, SOFT)
    c.arrow((694, 214), (786, 192), VIOLET, 2.2, 10)
    c.arrow((694, 228), (786, 284), VIOLET, 2.2, 10, dashed=True)
    c.arrow((694, 242), (786, 376), VIOLET, 2.2, 10, dashed=True)
    c.arrow((1000, 233), (1000, 246), MUTED, 2, 8)
    c.arrow((1000, 325), (1000, 338), MUTED, 2, 8)
    c.text((1144, 436), "verifica indipendente prima di procedere", 12, MUTED, anchor="rm")

    # budget
    c.rrect((56, 456, 1144, 740), 20, CARD, LINE, 1.5)
    c.text((82, 470), "GUARDRAIL MATEMATICI · BUDGET INVALICABILI", 12.5, MUTED, True, spacing=1.8)
    budgets = [
        ("40", "max step", "Nessun ciclo infinito: se sfora, si arresta con errore pulito.", CYAN),
        ("4096", "token per task", "Quota massima di ragionamento: meno spazio per le allucinazioni.", VIOLET),
        ("1200s", "timeout", "Scadenza assoluta prima di dichiarare il task fallito.", AMBER),
        ("3", "replan max", "L'AI può correggersi al massimo 3 volte, poi chiede aiuto.", OK),
    ]
    x = 82
    for big, label, desc, col in budgets:
        c.rrect((x, 506, x + 245, 706), 16, CARD2, col, 1.5)
        c.text((x + 22, 556), big, 44, col, True, anchor="lm")
        c.text((x + 22, 596), label.upper(), 12, MUTED, True, spacing=1.6)
        c.paragraph((x + 22, 622), desc, 13, SOFT, 202)
        x += 262
    c.save("diagram_03_mission_control.png")


# --------------------------------------------------------------------------
# 04 - Stanza ermetica
# --------------------------------------------------------------------------
def gen_diagram_04():
    c = frame(4, "STANZA ERMETICA", "Sandbox effimera e tre cancelli di verifica", OK)

    c.rrect((56, 162, 456, 440), 20, CARD, OK, 1.5)
    c.chip((78, 180), "COMPUTER HOST · REALE", OK)
    items = ["Il tuo filesystem operativo", "Dati aziendali e codice sorgente", "Zero accessi diretti dal codice AI", "Scritture non autorizzate bloccate", "Nessun commit automatico"]
    y = 236
    for it in items:
        c.dot((86, y + 9), 3.5, OK, glow=False)
        c.text((102, y), it, 14.5, SOFT)
        y += 34

    # barriera
    c.rrect((492, 162, 556, 440), 18, "#0a1a1f", CYAN, 2, glow=CYAN)
    for yy in range(190, 420, 22):
        c.line((506, yy), (542, yy), CYAN, 1.2, glow=False)
    c.text((524, 458), "BARRIERA", 11, CYAN, True, anchor="mm", spacing=1.5)
    c.arrow((596, 330), (560, 330), AMBER, 2, 8, dashed=True)
    c.text((524, 476), "applied: false", 11.5, MUTED, True, mono=True, anchor="mm")

    c.rrect((592, 162, 1144, 440), 20, "#1d1708", AMBER, 1.5, dashed=True)
    c.chip((614, 180), "CODE SANDBOX · DOCKER USA E GETTA", AMBER)
    items = ["Spazio temporaneo, distrutto a fine task", "L'agente genera ed esegue script qui dentro", "Pruning automatico dei workspace vecchi", "Chiusura forzata immediata su stop", "Output in quarantena fino all'ok umano"]
    y = 236
    for it in items:
        c.dot((622, y + 9), 3.5, AMBER, glow=False)
        c.text((638, y), it, 14.5, SOFT)
        y += 34

    # gate
    c.text((56, 486), "TRE CANCELLI INDIPENDENTI DAL MODELLO", 12.5, MUTED, True, spacing=1.8)
    gates = [
        ("Cancello 1 · File header", "Controlla i byte magici reali (%PDF, PNG, ELF). Non si fida del nome del file né del testo dell'LLM.", CYAN),
        ("Cancello 2 · Parsing AST", "Analisi sintattica del codice: blocca gli errori prima di lanciare qualsiasi test.", VIOLET),
        ("Cancello 3 · Test automatici", "Suite Pytest nel container. Si procede solo se tutto è verde.", OK),
    ]
    x = 56
    for i, (t, d, col) in enumerate(gates):
        card(c, (x, 512, x + 332, 690), col, t, d, num=i + 1, title_size=16.5, body_size=13.5, glow=True)
        if i < 2:
            c.arrow((x + 336, 626), (x + 366, 626), col, 2.5, 10)
        x += 372
    c.save("diagram_04_sandbox_gates.png")


# --------------------------------------------------------------------------
# 05 - Forge e hook
# --------------------------------------------------------------------------
def gen_diagram_05():
    c = frame(5, "FORGE DELLE ABILITÀ", "Ciclo di vita delle skill e hook adattivi", CYAN)

    steps = [
        ("Proposta agente", "L'AI sintetizza uno script o una ricetta d'azione.", CYAN),
        ("Bozza inerte", "Stato DRAFT con lucchetto: impossibile eseguirla.", AMBER),
        ("Firma SHA-256", "Revisione umana e hash crittografico verificato.", VIOLET),
        ("Skill attiva", "Caricabile in sicurezza solo dai ruoli autorizzati.", OK),
    ]
    x = 56
    for i, (t, d, col) in enumerate(steps):
        card(c, (x, 164, x + 248, 336), col, t, d, num=i + 1, title_size=16.5, body_size=13.5, glow=(i == 3), dashed=(i == 1))
        if i < 3:
            c.arrow((x + 252, 250), (x + 280, 250), col, 2.5, 10)
        x += 280

    c.rrect((56, 372, 1144, 760), 20, CARD, LINE, 1.5)
    c.chip((78, 392), "HOOK · BEFORE_CONTEXT", CYAN)
    c.text((1122, 410), "iniezione intelligente, zero spreco di token", 12.5, MUTED, anchor="rm")
    examples = [
        ("security · sicurezza", "Inietta le best practice di security review nel contesto dell'agente.", VIOLET),
        ("convert · documento", "Inietta le linee guida AnyDoc per estrarre Markdown pulito.", CYAN),
        ("URL esplicito", "Impone il tool web_fetch e spegne la ricerca libera web_search.", OK),
    ]
    y = 440
    for trig, act, col in examples:
        c.rrect((78, y, 1122, y + 72), 14, CARD2, col, 1.2)
        c.text((100, y + 36), "TRIGGER", 10.5, MUTED, True, anchor="lm", spacing=1.6)
        c.text((100, y + 54), trig, 15.5, col, True, anchor="lm")
        c.arrow((330, y + 36), (372, y + 36), col, 2, 9)
        c.paragraph((392, y + 26), act, 14.5, SOFT, 700)
        y += 86
    c.paragraph((78, 704), "Regola aurea: al massimo 2 skill contemporanee e tetto rigido di 24.000 byte per proteggere la finestra di contesto.", 13.5, MUTED, 1030)
    c.save("diagram_05_forge_hooks.png")


# --------------------------------------------------------------------------
# 06 - Hermes e Dream Loop
# --------------------------------------------------------------------------
def gen_diagram_06():
    c = frame(6, "MEMORIA E SOGNI", "Memoria Hermes e Dream Loop notturno", VIOLET)

    c.rrect((56, 160, 1144, 372), 20, CARD, CYAN, 1.5)
    c.chip((78, 178), "DI GIORNO · UNICA FONTE DI VERITÀ", CYAN)
    mem = [
        ("MEMORY.md e USER.md", "Fatti consolidati sull'utente e preferenze di lavoro."),
        ("SQLite FTS5 · state.db", "Ricerca full-text istantanea sugli episodi passati."),
        ("Graphify · code graph", "Mappa locale delle dipendenze del codice."),
    ]
    x = 78
    for t, d in mem:
        card(c, (x, 222, x + 336, 346), CYAN, t, d, title_size=16, body_size=13.5, fill=CARD2)
        x += 356

    c.arrow((600, 376), (600, 410), VIOLET, 3, 12)
    c.text((622, 393), "ogni notte, a riposo", 12, MUTED, True, anchor="lm", spacing=1.2)

    c.rrect((56, 418, 1144, 760), 20, "#120e24", VIOLET, 1.5, glow=VIOLET)
    c.chip((78, 436), "DI NOTTE · DREAM LOOP IDLE-ONLY", VIOLET, solid=True)
    steps = [
        ("Attivazione a riposo", "Parte solo se il computer non ha lavoro prioritario in corso."),
        ("Sintesi delle memorie", "Trova contraddizioni, collegamenti nascosti e idee evolutive."),
        ("Quarantena ipotesi", "I risultati restano ipotesi: non toccano la memoria senza ok."),
    ]
    x = 78
    for i, (t, d) in enumerate(steps):
        card(c, (x, 480, x + 322, 628), VIOLET, t, d, num=i + 1, title_size=16, body_size=13.5, fill=CARD)
        if i < 2:
            c.arrow((x + 326, 554), (x + 352, 554), VIOLET, 2.5, 10)
        x += 356
    c.rrect((78, 654, 1122, 734), 14, "#1d1708", AMBER, 1.2)
    c.chip((98, 678), "PREEMPTION", AMBER)
    c.paragraph((246, 685), "Se l'utente scrive anche una sola parola, il sogno si interrompe in millisecondi per rispondere subito.", 14, SOFT, 860)
    c.save("diagram_06_hermes_dreams.png")


# --------------------------------------------------------------------------
# 07 - Mesh
# --------------------------------------------------------------------------
def gen_diagram_07():
    c = frame(7, "RETE DISTRIBUITA", "Mesh privata cifrata e calcolo eterogeneo", CYAN)
    cx, cy = 600, 452

    nodes = [
        (56, 164, "Mac Studio / MacBook", "Apple Silicon: Metal e Neural Engine, vision e audio in locale.", OK, (456, 262)),
        (744, 164, "Workstation Windows", "GPU NVIDIA RTX per ComfyUI e simulazioni pesanti.", VIOLET, (744, 262)),
        (56, 540, "Server Linux on-premise", "Ollama locale: modelli aperti, zero costi API.", CYAN, (456, 642)),
        (744, 540, "Web Node nel browser", "Portatili e tablet: trascrizione, OCR e micro-task.", AMBER, (744, 642)),
    ]
    for _, _, _, _, col, edge in nodes:
        c.line((cx, cy), edge, col, 2, dashed=True)
        mx, my = (cx + edge[0]) / 2, (cy + edge[1]) / 2
        c.dot((mx, my), 4, col)
    # anelli hub
    c.ring((cx, cy), 128, CYAN, 1, alpha=70)
    c.ring((cx, cy), 98, VIOLET, 1, alpha=110)
    c.orb((cx, cy), 72, CYAN)
    c.text((cx, cy - 18), "TAILSCALE", 17, CYAN, True, anchor="mm", spacing=2.5)
    c.text((cx, cy + 6), "MESH", 24, TEXT, True, anchor="mm", spacing=4)
    c.text((cx, cy + 32), "WireGuard P2P", 11.5, MUTED, anchor="mm")
    for x, y, t, d, col, _ in nodes:
        card(c, (x, y, x + 400, y + 120), col, t, d, title_size=17, body_size=13.5, glow=True)
    c.text((cx, 748), "Nessuna porta esposta a Internet · nessun dato inviato a terzi", 13.5, OK, True, anchor="mm")
    c.save("diagram_07_mesh_network.png")


# --------------------------------------------------------------------------
# 08 - Reel Forge
# --------------------------------------------------------------------------
def gen_diagram_08():
    c = frame(8, "PRODUZIONE MULTIMEDIA", "Reel Forge: montaggio a ritmo e vision neurale", AMBER)

    # telefono 9:16
    px1, py1, px2, py2 = 70, 160, 390, 760
    c.rrect((px1, py1, px2, py2), 38, "#0a1124", CYAN, 2.5, glow=CYAN)
    c.rrect((px1 + 14, py1 + 14, px2 - 14, py2 - 14), 28, BG, LINE, 1)
    c.rrect(((px1 + px2) / 2 - 36, py1 + 24, (px1 + px2) / 2 + 36, py1 + 34), 5, LINE, None)
    c.text(((px1 + px2) / 2, py1 + 66), "REEL 9:16 · 1080×1920", 11.5, CYAN, True, anchor="mm", spacing=1.4)
    layers = [
        ("Traccia musicale", MUTED, 100),
        ("Beat detection · tagli", OK, 100),
        ("Testo karaoke dietro", AMBER, 100),
        ("Soggetto scontornato", ROSE, 100),
    ]
    y = 244
    for i, (t, col, _) in enumerate(layers):
        inset = i * 6
        c.rrect((px1 + 38 - inset, y, px2 - 38 + inset, y + 72), 14, CARD2, col, 1.5, glow=col if i == 3 else None)
        c.text((px1 + 58 - inset, y + 36), f"L{4 - i}", 12, col, True, mono=True, anchor="lm")
        c.text((px1 + 94 - inset, y + 36), t, 14, TEXT if i == 3 else SOFT, i == 3, anchor="lm")
        y += 88
    c.text(((px1 + px2) / 2, 628), "30 s  ·  60 s  ·  120 s", 13, CYAN, True, anchor="mm")
    c.text(((px1 + px2) / 2, 654), "Export H.264/AAC per TikTok e Reels", 12, MUTED, anchor="mm")
    c.chip(((px1 + px2) / 2 - 62, 690), "REVIEW OBBLIGATORIA", ROSE, 10.5)

    cards = [
        ("Audio e beat detection", "Rileva i picchi ritmici e posiziona i cambi di inquadratura al millisecondo.", CYAN),
        ("Segmentazione Apple Vision", "person_mask.swift su macOS: isola il corpo umano senza green screen.", VIOLET),
        ("Composizione a livelli", "Titoli, karaoke ed effetti dietro la persona: look da studio televisivo.", OK),
        ("Generazione alle 09:00", "Un LaunchAgent monta un video ogni mattina e lo manda in revisione, mai in pubblicazione diretta.", AMBER),
    ]
    y = 164
    for i, (t, d, col) in enumerate(cards):
        card(c, (440, y, 1144, y + 132), col, t, d, num=i + 1, title_size=17, body_size=14, glow=(i == 1))
        if i < 3:
            c.arrow((792, y + 134), (792, y + 148), col, 2, 8)
        y += 150
    c.save("diagram_08_reel_vision.png")


# --------------------------------------------------------------------------
# 09 - Ufficio
# --------------------------------------------------------------------------
def gen_diagram_09():
    c = frame(9, "UFFICIO ED ENTERPRISE", "AnyDoc, OCR illimitato e connettori governati", CYAN)
    cols = [
        (56, "1 · INGESTION", CYAN, [("PDF complessi", "Estratti e analizzati a fondo"), ("Scansioni cartacee", "OCR offline illimitato"), ("Documenti Office", "Word, Excel, presentazioni"), ("Contratti e moduli", "Campi e firme riconosciuti")]),
        (432, "2 · ELABORAZIONE", VIOLET, [("AnyDoc Markdown", "Conversione in testo pulito"), ("OnlyOffice bridge", "Editing e commenti condivisi"), ("Ispezione PDF", "Metadati e firme digitali"), ("Memoria di progetto", "Tutto salvato in Hermes")]),
        (808, "3 · CONNETTORI", OK, [("Microsoft 365", "Outlook, Teams, OneDrive"), ("Google Workspace", "Gmail, Drive, Docs"), ("GitHub", "Repository e automazioni"), ("Zero credential leak", "Password rimosse dai log")]),
    ]
    for x, title, col, items in cols:
        c.rrect((x, 160, x + 336, 760), 20, CARD, col, 1.5, glow=col)
        c.text((x + 24, 190), title, 13.5, col, True, spacing=2)
        c.line((x + 24, 214), (x + 312, 214), LINE, 1, glow=False)
        y = 232
        for t, d in items:
            c.rrect((x + 18, y, x + 318, y + 106), 14, CARD2, LINE, 1)
            c.rrect((x + 19, y + 18, x + 23, y + 88), 2, col, None)
            c.text((x + 40, y + 28), t, 16.5, TEXT, True)
            c.text((x + 40, y + 60), d, 13.5, SOFT)
            y += 122
    c.arrow((396, 460), (428, 460), CYAN, 3, 11)
    c.arrow((772, 460), (804, 460), VIOLET, 3, 11)
    c.save("diagram_09_ufficio_connectors.png")


# --------------------------------------------------------------------------
# 10 - Multi agente
# --------------------------------------------------------------------------
def gen_diagram_10():
    c = frame(10, "INGEGNERIA MULTI-AGENTE", "Più agenti, un solo repository, zero conflitti", OK)
    agents = [("CLINE", "Feature in VS Code", CYAN), ("CODEX", "Infrastruttura e Control Plane", VIOLET), ("CLAUDE CODE", "Motore dell'editor reel", AMBER), ("ANTIGRAVITY", "Orchestrazione, test e audit", OK)]
    x = 56
    for name, role, col in agents:
        c.rrect((x, 160, x + 250, 262), 16, CARD, col, 1.5, glow=col)
        c.orb((x + 38, 211), 17, col)
        c.text((x + 70, 198), name, 15, col, True, anchor="lm", spacing=1.6)
        c.text((x + 70, 226), role, 12.5, SOFT, anchor="lm")
        c.arrow((x + 125, 266), (x + 125, 330), col, 2.2, 10)
        x += 279
    c.rrect((56, 336, 1144, 760), 20, "#0a1a1f", CYAN, 1.5, glow=CYAN)
    c.text((82, 366), "IL PROTOCOLLO DI CONVIVENZA", 13.5, CYAN, True, spacing=2)
    rules = [
        ("AGENTS.md", "La costituzione", "Perimetro, strumenti permessi e regole inderogabili: nessun agente tocca file fuori dal proprio incarico.", CYAN),
        ("AGENT-LOG.md", "Diario di bordo", "Registro append-only: prima di iniziare si legge cosa è stato fatto, alla fine si firma.", VIOLET),
        ("Il repository", "L'unica verità", "Niente cartelle esterne o copie divergenti: vale solo il codice nel progetto.", OK),
        ("Test", "Sempre verdi", "Suite continuamente verificata: nessuno lascia la codebase rotta all'agente successivo.", AMBER),
    ]
    y = 396
    for i, (t, sub, d, col) in enumerate(rules):
        c.rrect((78, y, 1122, y + 78), 14, CARD, col, 1.2)
        c.badge_num((110, y + 39), i + 1, col)
        c.text((144, y + 28), t, 16, col, True, anchor="lm")
        c.text((144, y + 52), sub, 12.5, MUTED, anchor="lm")
        c.paragraph((400, y + 20), d, 14, SOFT, 690)
        y += 88
    c.save("diagram_10_multi_agent.png")


# --------------------------------------------------------------------------
# 11 - Quadranti
# --------------------------------------------------------------------------
def gen_diagram_11():
    c = frame(11, "MERCATO E VALORE", "I quattro sbocchi di HyperSpace 1.05", VIOLET)
    quads = [
        (56, 160, "ENTERPRISE LOCAL", "Banche, sanità, legale, PA", "Agenti su dati riservati on-premise: nessuna fuga all'estero e audit completo.", "Licenza annuale + supporto", CYAN),
        (608, 160, "AGENT OPERATIONS", "Software house e scale-up", "Mission Control bounded, sandbox usa e getta, correzione automatica di bug e test.", "Abbonamento per workspace/nodo", VIOLET),
        (56, 468, "HYPERSPACE UFFICIO", "Studi professionali e PMI", "AnyDoc, OCR illimitato, bridge OnlyOffice e memoria condivisa di studio.", "Pacchetto chiavi in mano / mese", OK),
        (608, 468, "HYPERSPACE MULTIMEDIA", "Media house e creator", "Reel Forge ritmico, Apple Vision, Comic Builder e identità virtuali coerenti.", "Licenza studio + produzione video", AMBER),
    ]
    for i, (x, y, title, target, val, model, col) in enumerate(quads):
        c.rrect((x, y, x + 536, y + 292), 20, CARD, col, 1.5, glow=col)
        c.text((x + 30, y + 44), f"0{i + 1}", 40, col, True, anchor="lm")
        c.text((x + 100, y + 34), title, 17, TEXT, True, anchor="lm", spacing=1.2)
        c.text((x + 100, y + 58), target, 13.5, col, True, anchor="lm")
        c.line((x + 30, y + 86), (x + 506, y + 86), LINE, 1, glow=False)
        c.paragraph((x + 30, y + 108), val, 17, SOFT, 476, 1.45)
        c.rrect((x + 30, y + 224, x + 506, y + 262), 12, CARD2, col, 1.2)
        c.text((x + 48, y + 243), "MODELLO", 10.5, MUTED, True, anchor="lm", spacing=1.6)
        c.text((x + 130, y + 243), model, 14, col, True, anchor="lm")
    c.save("diagram_11_business_quadrants.png")


# --------------------------------------------------------------------------
# 12 - Visione
# --------------------------------------------------------------------------
def gen_diagram_12():
    w, h = 1200, 414
    c = Canvas(w, h)
    c.chip((56, 34), "VISIONE", CYAN)
    c.text((56, 72), "Un sistema operativo per l'AI che lavora davvero", 26, TEXT, True)
    pillars = [
        ("01", "GOVERNATA", "DAG bounded con limiti matematici: niente allucinazioni operative né loop infiniti.", CYAN),
        ("02", "SICURA", "Sandbox usa e getta e cancelli di qualità indipendenti dal modello.", OK),
        ("03", "COGNITIVA", "Memoria Hermes FTS5 e sogno notturno, con ipotesi in quarantena.", VIOLET),
        ("04", "DISTRIBUITA", "Mesh privata Tailscale a zero fughe e inferenza 100% locale su GPU.", AMBER),
    ]
    x = 56
    for num, t, d, col in pillars:
        c.rrect((x, 124, x + 258, 358), 18, CARD, col, 1.5, glow=col)
        c.text((x + 24, 166), num, 34, col, True, anchor="lm")
        c.text((x + 24, 208), t, 15.5, TEXT, True, spacing=2)
        c.line((x + 24, 228), (x + 70, 228), col, 3)
        c.paragraph((x + 24, 244), d, 13.5, SOFT, 212)
        x += 276
    c.text((600, 388), "L'autonomia si guadagna con verifica e prova di sicurezza · l'umano resta sovrano", 12.5, MUTED, anchor="mm")
    c.save("diagram_12_summary_vision.png")


def generate_all():
    print("Generating all 12 presentation diagrams...")
    gen_diagram_01()
    gen_diagram_02()
    gen_diagram_03()
    gen_diagram_04()
    gen_diagram_05()
    gen_diagram_06()
    gen_diagram_07()
    gen_diagram_08()
    gen_diagram_09()
    gen_diagram_10()
    gen_diagram_11()
    gen_diagram_12()
    print("All 12 diagrams successfully generated in docs/presentation_assets/!")


if __name__ == "__main__":
    generate_all()
