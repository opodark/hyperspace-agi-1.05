#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Genera la Guida Ufficiale & Presentazione Divulgativa per 00MESH 1.05.

Produce:
1. 8 Grafiche HD (PNG 2x supersampled, zero caratteri mancanti, icone vettoriali)
   in `docs/presentation_assets/00mesh_guida_*.png` e copia negli artifact/web-node.
2. Documento PDF Widescreen 16:9 `docs/00mesh-guida-rapida.pdf` (10 slide).
3. Documento Markdown illustrato `docs/00mesh-guida-rapida.md`.
"""

from __future__ import annotations

import math
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ASSETS_DIR = ROOT / "docs" / "presentation_assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
WEB_DOCS_DIR = ROOT / "web-node" / "docs"
WEB_DOCS_DIR.mkdir(parents=True, exist_ok=True)

PDF_OUT = ROOT / "docs" / "00mesh-guida-rapida.pdf"
MD_OUT = ROOT / "docs" / "00mesh-guida-rapida.md"

S = 2  # Supersampling 2x per nitidezza Retina

# Palette Colori Brand 00MESH / ZeroZeroComputer
BG_DARK = "#070b18"
CARD_DARK = "#0d152a"
CARD_ALT = "#131e3a"
LINE_COL = "#263454"
TEXT_WHITE = "#f8fafc"
TEXT_MUTED = "#94a3b8"
CYAN = "#38bdf8"
TEAL = "#2dd4bf"
EMERALD = "#10b981"
VIOLET = "#a855f7"
SOLANA = "#9945ff"
SOL_GREEN = "#14f195"
AMBER = "#f59e0b"
ROSE = "#f43f5e"


def rgba(hexcolor: str, a: int = 255) -> tuple[int, int, int, int]:
    h = hexcolor.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


_FONT_CACHE: dict[tuple[float, bool, bool], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}


def get_font(size: float, bold: bool = False, mono: bool = False):
    key = (size, bold, mono)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    px = int(round(size * S))
    f = None
    if mono and os.path.exists("/System/Library/Fonts/Menlo.ttc"):
        try:
            f = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", px, index=1 if bold else 0)
        except Exception:
            f = None
    if f is None:
        for path, idx in (
            (
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
                if bold
                else "/System/Library/Fonts/Supplemental/Arial.ttf",
                0,
            ),
            ("/System/Library/Fonts/Helvetica.ttc", 1 if bold else 0),
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


class MarketingCanvas:
    """Motore di rendering infografico ad alta risoluzione senza glifi mancanti."""

    def __init__(self, w: int = 920, h: int = 390):
        self.w, self.h = w, h
        self.im = Image.new("RGBA", (w * S, h * S), rgba(BG_DARK))
        self._draw_cyber_bg()

    def _draw_cyber_bg(self):
        w, h = self.w * S, self.h * S
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        g = ImageDraw.Draw(glow)
        g.ellipse((-w * 0.1, -h * 0.4, w * 0.45, h * 0.6), fill=rgba("#162a58", 200))
        g.ellipse((w * 0.55, -h * 0.3, w * 1.1, h * 0.55), fill=rgba("#2c184c", 180))
        g.ellipse((w * 0.25, h * 0.6, w * 0.85, h * 1.3), fill=rgba("#0a2e38", 160))
        glow = glow.filter(ImageFilter.GaussianBlur(45 * S))
        self.im = Image.alpha_composite(self.im, glow)

        draw = ImageDraw.Draw(self.im)
        step = 36 * S
        grid_col = rgba("#1e2e4f", 45)
        for x in range(0, w, step):
            draw.line([(x, 0), (x, h)], fill=grid_col, width=1)
        for y in range(0, h, step):
            draw.line([(0, y), (w, y)], fill=grid_col, width=1)

    def draw(self) -> ImageDraw.ImageDraw:
        return ImageDraw.Draw(self.im)

    def save(self, path: Path) -> Path:
        out = self.im.resize((self.w, self.h), Image.Resampling.LANCZOS)
        out.convert("RGB").save(path, quality=95)
        return path

    def icon_circle(self, x: float, y: float, label: str, col: str = CYAN, r: float = 11):
        d = self.draw()
        cx, cy, sr = x * S, y * S, r * S
        d.ellipse(
            [cx - sr, cy - sr, cx + sr, cy + sr],
            fill=rgba(col, 55),
            outline=rgba(col, 235),
            width=int(1.5 * S),
        )
        d.text(
            (cx, cy),
            label,
            font=get_font(8.8, bold=True),
            fill=rgba(TEXT_WHITE),
            anchor="mm",
        )

    def box(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str = "",
        subtitle: str = "",
        badge: str = "",
        icon_tag: str = "",
        border_col: str = CYAN,
        fill_col: str = CARD_DARK,
        radius: int = 14,
    ):
        d = self.draw()
        x1, y1 = x * S, y * S
        x2, y2 = (x + w) * S, (y + h) * S
        d.rounded_rectangle(
            [x1, y1, x2, y2],
            radius=radius * S,
            fill=rgba(fill_col, 242),
            outline=rgba(border_col, 195),
            width=int(1.8 * S),
        )
        d.rounded_rectangle(
            [x1 + 14 * S, y1, x2 - 14 * S, y1 + 3.5 * S],
            radius=1 * S,
            fill=rgba(border_col, 240),
        )
        cur_y = y1 + 14 * S
        if badge:
            f_badge = get_font(9.0, bold=True)
            bbox = d.textbbox((0, 0), badge, font=f_badge)
            bw = (bbox[2] - bbox[0]) + 22 * S
            bh = 20 * S
            d.rounded_rectangle(
                [x1 + 14 * S, cur_y, x1 + 14 * S + bw, cur_y + bh],
                radius=10 * S,
                fill=rgba("#050914", 230),
                outline=rgba(border_col, 210),
                width=int(1.3 * S),
            )
            d.text(
                (x1 + 14 * S + bw / 2, cur_y + bh / 2),
                badge,
                font=f_badge,
                fill=rgba(border_col),
                anchor="mm",
            )
            cur_y += 27 * S

        if title:
            tx = x1 + 14 * S
            if icon_tag:
                self.icon_circle(x + 25, (cur_y / S) + 8, icon_tag, col=border_col, r=10)
                tx = x1 + 42 * S
            d.text(
                (tx, cur_y),
                title,
                font=get_font(13.2, bold=True),
                fill=rgba(TEXT_WHITE),
            )
            cur_y += 20 * S
        if subtitle:
            d.text(
                (x1 + 14 * S, cur_y),
                subtitle,
                font=get_font(10.2),
                fill=rgba(TEXT_MUTED),
            )

    def pill(self, x: float, y: float, text: str, col: str = CYAN, w: float = 0):
        d = self.draw()
        f_pill = get_font(10.0, bold=True)
        bbox = d.textbbox((0, 0), text, font=f_pill)
        pw = w * S if w > 0 else (bbox[2] - bbox[0]) + 24 * S
        ph = 24 * S
        d.rounded_rectangle(
            [x * S, y * S, x * S + pw, y * S + ph],
            radius=12 * S,
            fill=rgba("#060b18", 235),
            outline=rgba(col, 210),
            width=int(1.4 * S),
        )
        d.text(
            (x * S + pw / 2, y * S + ph / 2),
            text,
            font=f_pill,
            fill=rgba(TEXT_WHITE),
            anchor="mm",
        )

    def arrow(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        col: str = CYAN,
        label: str = "",
    ):
        d = self.draw()
        sx1, sy1 = x1 * S, y1 * S
        sx2, sy2 = x2 * S, y2 * S
        d.line([(sx1, sy1), (sx2, sy2)], fill=rgba(col, 225), width=int(2.2 * S))
        angle = math.atan2(sy2 - sy1, sx2 - sx1)
        alen = 10 * S
        p1 = (
            sx2 - alen * math.cos(angle - math.pi / 6),
            sy2 - alen * math.sin(angle - math.pi / 6),
        )
        p2 = (
            sx2 - alen * math.cos(angle + math.pi / 6),
            sy2 - alen * math.sin(angle + math.pi / 6),
        )
        d.polygon([(sx2, sy2), p1, p2], fill=rgba(col))
        if label:
            f_lbl = get_font(9.0, bold=True)
            bbox = d.textbbox((0, 0), label, font=f_lbl)
            mx, my = (sx1 + sx2) / 2, (sy1 + sy2) / 2 - 12 * S
            lw = (bbox[2] - bbox[0]) + 14 * S
            d.rounded_rectangle(
                [mx - lw / 2, my - 9 * S, mx + lw / 2, my + 9 * S],
                radius=6 * S,
                fill=rgba(BG_DARK, 240),
                outline=rgba(col, 150),
                width=S,
            )
            d.text(
                (mx, my),
                label,
                font=f_lbl,
                fill=rgba(col),
                anchor="mm",
            )


def generate_marketing_diagrams() -> dict[str, Path]:
    paths: dict[str, Path] = {}

    # 1. COPERTINA / VALORE ECOSISTEMA
    c1 = MarketingCanvas(920, 390)
    d1 = c1.draw()
    c1.box(
        25,
        30,
        265,
        330,
        title="AI Cloud Tradizionale",
        subtitle="Abbonamenti Mensili & Blocchi",
        badge="VECCHIO PARADIGMA",
        icon_tag="NO",
        border_col=ROSE,
        fill_col="#1a0f1e",
    )
    d1.text(
        (42 * S, 122 * S),
        "[X] Costo fisso: 20€ - 200€ / mese\n"
        "[X] Censure & filtri ideologici\n"
        "[X] I tuoi file su server di terzi\n"
        "[X] Nessun tool locale integrato\n"
        "[X] Limiti di messaggi ogni 3 ore\n"
        "[X] Zero ricompense per l'utente\n"
        "[X] Nessuna memoria persistente",
        font=get_font(10.8),
        fill=rgba("#fda4af"),
        spacing=9 * S,
    )

    c1.box(
        328,
        20,
        265,
        350,
        title="Ecosistema 00MESH 1.05",
        subtitle="Mesi di Sviluppo Già Pronti",
        badge="100% GRATIS PER TE",
        icon_tag="AI",
        border_col=CYAN,
        fill_col="#0c1938",
    )
    d1.text(
        (344 * S, 114 * S),
        "[+] Modelli Abliterated Senza Censure\n"
        "[+] 25+ Skill & Tool Nativi Pronti\n"
        "[+] AnyDoc PDF & Unlimited OCR\n"
        "[+] Docker Code Sandbox Sicura\n"
        "[+] SearXNG Web Search Privata\n"
        "[+] ComfyUI & Reel Editor 9:16\n"
        "[+] Memoria Hermes & Sogni REM\n"
        "[+] Oltre 2.465 Test di Sicurezza",
        font=get_font(10.6, bold=True),
        fill=rgba("#e0f2fe"),
        spacing=8 * S,
    )

    c1.box(
        630,
        30,
        265,
        330,
        title="Come Accedi a Gratis?",
        subtitle="Tu Scegli la Tua Modalità",
        badge="SOSTENIBILITÀ REALE",
        icon_tag="OK",
        border_col=SOL_GREEN,
        fill_col="#091f24",
    )
    d1.text(
        (646 * S, 122 * S),
        "1. MODALITÀ BANNER ADS\n"
        "   Naviga gratis: un semplice\n"
        "   banner Google AdSense copre\n"
        "   i costi dei server GPU.\n\n"
        "2. CONDIVIDI GPU LOCALE\n"
        "   Collega Ollama / LM Studio\n"
        "   con 1 click via Chrome:\n"
        "   Zero pubblicità + Guadagni\n"
        "   token $00MESH (Solana)!",
        font=get_font(10.5),
        fill=rgba("#a7f3d0"),
        spacing=6 * S,
    )

    c1.arrow(290, 195, 328, 195, col=CYAN, label="SUPERATO")
    c1.arrow(593, 195, 630, 195, col=SOL_GREEN, label="SBLOCCA")
    paths["cover"] = c1.save(ASSETS_DIR / "00mesh_guida_01_cover.png")

    # 2. LE 3 PORTE DI ACCESSO GRATUITO
    c2 = MarketingCanvas(920, 390)
    d2 = c2.draw()
    c2.box(
        25,
        28,
        275,
        334,
        title="Opzione A · Spettatore",
        subtitle="Zero Hardware · Banner AdSense",
        badge="PER CHI INIZIA SUBITO",
        icon_tag="A",
        border_col=AMBER,
    )
    d2.text(
        (40 * S, 120 * S),
        ">> Cosa devi fare:\n"
        " • Apri zerozerocomputer.it\n"
        " • Accetta il banner AdSense GDPR\n"
        " • Attiva il Nodo Web (1 click)\n\n"
        ">> Cosa ottieni GRATIS:\n"
        " • Accesso ai modelli della rete\n"
        " • +50 $00MESH di Benvenuto\n"
        " • Ricerca Web, PDF & Chat\n"
        " • Nessuna scheda video richiesta!",
        font=get_font(10.6),
        fill=rgba(TEXT_WHITE),
        spacing=7 * S,
    )

    c2.box(
        322,
        28,
        275,
        334,
        title="Opzione B · Condividi GPU",
        subtitle="Plugin Chrome + Ollama / LM Studio",
        badge="CONSIGLIATO · VIP & TOKEN",
        icon_tag="B",
        border_col=EMERALD,
        fill_col="#081c24",
    )
    d2.text(
        (337 * S, 120 * S),
        ">> Cosa devi fare:\n"
        " • Avvia Ollama o LM Studio sul PC\n"
        " • Installa 00MESH Chrome Bridge\n"
        " • Il semaforo diventa VERDE [ON]\n\n"
        ">> Cosa ottieni GRATIS:\n"
        " • Sblocco Istantaneo Chat Sovrana\n"
        " • Zero Chiavi d'attesa o blocchi\n"
        " • Guadagni da 2 a 6 $00MESH/task\n"
        " • +5 $00MESH per ogni ora online!",
        font=get_font(10.6),
        fill=rgba("#d1fae5"),
        spacing=7 * S,
    )

    c2.box(
        620,
        28,
        275,
        334,
        title="Opzione C · Chiave Membro",
        subtitle="Access Key Personale (hs-mesh-*)",
        badge="ACCESSO DIRETTO PRO",
        icon_tag="C",
        border_col=VIOLET,
    )
    d2.text(
        (635 * S, 120 * S),
        ">> Cosa devi fare:\n"
        " • Compila il modulo sul sito\n"
        " • Ricevi la tua chiave hs-mesh-*\n"
        " • Incollala nel Gate di Accesso\n\n"
        ">> Cosa ottieni GRATIS:\n"
        " • Accesso da qualsiasi telefono/PC\n"
        " • Tutte le Skill & Sandbox attive\n"
        " • Priorità nella coda GPU Mesh\n"
        " • Supporto diretto su Telegram",
        font=get_font(10.6),
        fill=rgba(TEXT_WHITE),
        spacing=7 * S,
    )
    paths["access"] = c2.save(ASSETS_DIR / "00mesh_guida_02_access.png")

    # 3. ARSENALE COMPLETO: TUTTI I TOOL E SKILL FRUIBILI SUBITO
    c3 = MarketingCanvas(920, 390)
    d3 = c3.draw()
    c3.box(
        340,
        138,
        240,
        118,
        title="00MESH Control Plane",
        subtitle="Orchestratore Intelligente",
        badge="CUORE DI HYPERSPACE",
        icon_tag="CP",
        border_col=CYAN,
        fill_col="#102042",
    )
    d3.text(
        (354 * S, 218 * S),
        "Seleziona da solo i tool e le skill\ngiuste mentre parli in italiano!",
        font=get_font(10.0),
        fill=rgba("#bae6fd"),
    )

    satellites = [
        (25, 18, "AnyDoc & OCR Illimitato", "PDF", "Trascina PDF, Word, Excel, Codice\nEstrazione istantanea 100% privata", CYAN, (285, 75, 340, 160)),
        (340, 12, "SearXNG Web Search", "WEB", "Notizie e dati in tempo reale\nZero tracciamento, fonti verificate", TEAL, (460, 110, 460, 138)),
        (635, 18, "Docker Code Sandbox", "PY", "Esegue Python in cassaforte isolata\nGrafici, calcoli e test senza rischi", EMERALD, (635, 75, 580, 160)),
        (25, 268, "ComfyUI & Reel 9:16", "IMG", "Genera immagini (/image) e video\nTikTok/Reels con Apple Vision", VIOLET, (285, 315, 340, 230)),
        (340, 275, "Memoria Hermes & Sogni", "MEM", "Ricorda tutto (SQLite FTS5)\nRiflette di notte per darti idee", AMBER, (460, 275, 460, 256)),
        (635, 268, "Skill Forge & Connettori", "25+", "Tool GitHub, M365, Google Drive,\nCrea Siti Web, Security Review", SOL_GREEN, (635, 315, 580, 230)),
    ]
    for sx, sy, stitle, stag, sdesc, scol, (ax1, ay1, ax2, ay2) in satellites:
        c3.box(sx, sy, 260, 98, title=stitle, icon_tag=stag, border_col=scol)
        d3.text((sx * S + 14 * S, sy * S + 46 * S), sdesc, font=get_font(10.0), fill=rgba(TEXT_MUTED), spacing=5 * S)
        c3.arrow(ax1, ay1, ax2, ay2, col=scol)

    paths["arsenal"] = c3.save(ASSETS_DIR / "00mesh_guida_03_arsenal.png")

    # 4. GUIDA ALLA CONSOLE CHAT SOVRANA
    c4 = MarketingCanvas(920, 390)
    d4 = c4.draw()
    c4.box(30, 20, 860, 350, title="", border_col="#334155", fill_col="#060a15")
    d4.rounded_rectangle([35 * S, 25 * S, 235 * S, 365 * S], radius=10 * S, fill=rgba("#0a1022"), outline=rgba(LINE_COL))
    c4.icon_circle(52, 46, "00", col=CYAN, r=9)
    d4.text((66 * S, 39 * S), "ZeroZeroComputer", font=get_font(11.5, bold=True), fill=rgba(CYAN))
    c4.pill(48, 70, "+ Nuova Chat", col=CYAN, w=172)
    d4.text((48 * S, 110 * S), "MODELLO MESH ATTIVO:", font=get_font(8.8, bold=True), fill=rgba(TEXT_MUTED))
    c4.pill(48, 128, "qwen3-vl:4b / abliterated", col=VIOLET, w=172)
    d4.text((48 * S, 172 * S), "CRONOLOGIA LOCALE:\n• Analisi Contratto PDF\n• Script Numeri Primi\n• Idea Reel Instagram", font=get_font(9.8), fill=rgba(TEXT_MUTED), spacing=7 * S)
    c4.pill(48, 325, "[ON] NODE OPERATOR", col=EMERALD, w=172)

    d4.text((260 * S, 38 * S), "Console Chat Sovrana Estesa (chat.html)", font=get_font(13, bold=True), fill=rgba(TEXT_WHITE))
    c4.pill(700, 33, "[ONLINE] Mesh Connessa", col=EMERALD, w=165)

    d4.rounded_rectangle([410 * S, 76 * S, 865 * S, 130 * S], radius=12 * S, fill=rgba("#231d42"), outline=rgba(VIOLET))
    d4.text((425 * S, 86 * S), "TU: Leggi il contratto allegato, cerca i tassi BCE 2026 sul web\ne calcola la rata esatta in Python!", font=get_font(10.3), fill=rgba(TEXT_WHITE), spacing=5 * S)

    d4.rounded_rectangle([260 * S, 144 * S, 865 * S, 274 * S], radius=12 * S, fill=rgba("#0d1730"), outline=rgba(CYAN))
    d4.text((275 * S, 154 * S), "00MESH AI: Ho estratto il PDF con AnyDoc, verificato le fonti su SearXNG\ne generato il calcolo. Clicca '[>] Esegui in Sandbox' per verificarlo:", font=get_font(10.3), fill=rgba("#e2e8f0"), spacing=4 * S)
    d4.rounded_rectangle([275 * S, 198 * S, 848 * S, 262 * S], radius=8 * S, fill=rgba("#040711"), outline=rgba(EMERALD))
    d4.text((290 * S, 208 * S), "PYTHON  |  rata = calcola_ammortamento(120000, tasso=0.031)\nOUTPUT  |  [OK] Exit 0  ->  Rata Mensile: EUR 575,42 / mese", font=get_font(9.8, mono=True), fill=rgba(SOL_GREEN), spacing=8 * S)
    c4.pill(685, 203, "[>] Esegui in Sandbox", col=EMERALD, w=152)

    d4.rounded_rectangle([260 * S, 290 * S, 865 * S, 355 * S], radius=12 * S, fill=rgba("#0a1328"), outline=rgba(CYAN))
    c4.pill(275, 300, "[+] 1. Allega File (PDF/Word/Code)", col=CYAN, w=230)
    c4.pill(515, 300, "[W] 2. Attiva Web Search Live", col=TEAL, w=210)
    c4.pill(740, 300, "Invia ->", col=VIOLET, w=110)
    d4.text((278 * S, 333 * S), "Scrivi qui come parleresti a un collega esperto o trascina un documento...", font=get_font(10), fill=rgba(TEXT_MUTED))

    paths["chat_ui"] = c4.save(ASSETS_DIR / "00mesh_guida_04_chat_ui.png")

    # 5. CREATIVITÀ & UFFICIO: IMMAGINI, REEL TIKTOK E SITI WEB
    c5 = MarketingCanvas(920, 390)
    d5 = c5.draw()
    c5.box(
        25,
        28,
        275,
        334,
        title="1. Studio Visivo ComfyUI",
        subtitle="Genera Immagini & Pose Esatte",
        badge="COMANDO /IMAGE",
        icon_tag="ART",
        border_col=VIOLET,
    )
    d5.text(
        (40 * S, 120 * S),
        "• Scrivi `/image` seguito dalla\n"
        "  descrizione in chat.\n"
        "• Usa `Anna Batch` per generare\n"
        "  fino a 50 scene in automatico!\n"
        "• Controllo posa DWPose:\n"
        "  carica una foto e l'AI replica\n"
        "  esattamente postura e mani.\n"
        "• Selezione automatica Vision:\n"
        "  scarta da sola le foto difettose!",
        font=get_font(10.4),
        fill=rgba(TEXT_WHITE),
        spacing=6 * S,
    )

    c5.box(
        322,
        28,
        275,
        334,
        title="2. Regista Reel 9:16",
        subtitle="Montaggio Musicale + Apple Vision",
        badge="TIKTOK & INSTAGRAM",
        icon_tag="VID",
        border_col=AMBER,
    )
    d5.text(
        (337 * S, 120 * S),
        "• Scegli le foto e una canzone:\n"
        "  il Beat Detection taglia i cambi\n"
        "  scena a tempo di musica!\n"
        "• Scontorno Magico (`person_mask`):\n"
        "  isola la persona senza telo verde\n"
        "  e mette i titoli DIETRO al corpo.\n"
        "• Effetti neon, strobo sui bassi\n"
        "  e 1 Reel pronto ogni mattina\n"
        "  alle 09:00 in coda di revisione!",
        font=get_font(10.4),
        fill=rgba(TEXT_WHITE),
        spacing=6 * S,
    )

    c5.box(
        620,
        28,
        275,
        334,
        title="3. Website & Ufficio",
        subtitle="Siti Web ZIP & Conversioni",
        badge="PRODUTTIVITÀ LAMPO",
        icon_tag="ZIP",
        border_col=CYAN,
    )
    d5.text(
        (635 * S, 120 * S),
        "• Chiedi: 'Crea un sito web per\n"
        "  la mia attività' -> genera HTML\n"
        "  responsive + pacchetto `.zip`!\n"
        "• Converti Word, Excel, PowerPoint\n"
        "  e PDF in Markdown pulito.\n"
        "• `classifica_pdf`: capisce da solo\n"
        "  quali pagine sono scansioni e\n"
        "  applica l'OCR solo dove serve!",
        font=get_font(10.4),
        fill=rgba(TEXT_WHITE),
        spacing=6 * S,
    )
    paths["creative"] = c5.save(ASSETS_DIR / "00mesh_guida_05_creative.png")

    # 6. COME FUNZIONA IL CHROME BRIDGE
    c6 = MarketingCanvas(920, 390)
    d6 = c6.draw()
    c6.box(
        25,
        60,
        250,
        265,
        title="1. Il Tuo PC / Mac",
        subtitle="Ollama (:11434) o LM Studio (:1234)",
        badge="100% LOCALE",
        icon_tag="GPU",
        border_col=CYAN,
    )
    d6.text(
        (40 * S, 152 * S),
        "• Hai una scheda NVIDIA RTX,\n"
        "  AMD o un Mac M1/M2/M3/M4?\n"
        "• Quando non giochi o non lavori,\n"
        "  la tua GPU resta ferma al 0%.\n"
        "• Avvia Ollama o LM Studio:\n"
        "  i modelli girano in locale!",
        font=get_font(10.4),
        fill=rgba(TEXT_WHITE),
        spacing=6 * S,
    )

    c6.box(
        335,
        40,
        250,
        305,
        title="2. Chrome Bridge",
        subtitle="Estensione Leggera (12 KB)",
        badge="ZERO CONFIGURAZIONE",
        icon_tag="EXT",
        border_col=EMERALD,
        fill_col="#071f24",
    )
    d6.text(
        (350 * S, 132 * S),
        "• Niente Docker o terminale!\n"
        "• Niente porte aperte sul router!\n"
        "• Supera i blocchi CORS del browser\n"
        "  in totale sicurezza (Manifest V3).\n"
        "• Rileva da sola Llama, Qwen,\n"
        "  Mistral, DeepSeek e Gemma.\n"
        "• I tuoi file personali NON escono\n"
        "  mai dal tuo computer!",
        font=get_font(10.4),
        fill=rgba("#a7f3d0"),
        spacing=6 * S,
    )

    c6.box(
        645,
        60,
        250,
        265,
        title="3. Rete 00MESH",
        subtitle="Accesso VIP + Ricompense",
        badge="PROOF-OF-USEFUL-WORK",
        icon_tag="VIP",
        border_col=SOLANA,
    )
    d6.text(
        (660 * S, 152 * S),
        "• Sblocca all'istante la Chat\n"
        "  Sovrana senza bisogno di chiave!\n"
        "• Ricevi micro-compiti AI dalla\n"
        "  rete e li risolvi con la tua GPU.\n"
        "• Ogni risposta verificata accredita\n"
        "  token $00MESH sul tuo Wallet!",
        font=get_font(10.4),
        fill=rgba(TEXT_WHITE),
        spacing=6 * S,
    )

    c6.arrow(275, 192, 335, 192, col=CYAN, label="Localhost")
    c6.arrow(585, 192, 645, 192, col=EMERALD, label="HTTPS Sicuro")
    paths["bridge"] = c6.save(ASSETS_DIR / "00mesh_guida_06_bridge.png")

    # 7. MINI GUIDA DI INSTALLAZIONE ILLUSTRATA IN 3 MINUTI
    c7 = MarketingCanvas(920, 390)
    d7 = c7.draw()
    steps = [
        (
            18,
            "PASSO 1 · MOTORE AI",
            "Ollama o LM Studio",
            "1",
            CYAN,
            "• Scarica da ollama.com\n"
            "  oppure da lmstudio.ai\n"
            "• Avvia un modello rapido:\n"
            "  `ollama run qwen3-vl:4b`\n"
            "• Oppure accendi il Server\n"
            "  su LM Studio (porta 1234).\n\n"
            "[Tempo: 90 secondi]",
        ),
        (
            244,
            "PASSO 2 · SCARICA ZIP",
            "00mesh-chrome-bridge",
            "2",
            TEAL,
            "• Vai su zerozerocomputer.it\n"
            "• Clicca il bottone verde:\n"
            "  `Scarica Estensione (.zip)`\n"
            "• Estrai la cartella dallo ZIP\n"
            "  (es. dentro Documenti).\n\n\n"
            "[Tempo: 20 secondi]",
        ),
        (
            470,
            "PASSO 3 · ESTENSIONI",
            "chrome://extensions/",
            "3",
            EMERALD,
            "• Digita `chrome://extensions`\n"
            "  su Chrome, Brave o Edge\n"
            "• Attiva in alto a destra:\n"
            "  `Modalita sviluppatore` ON\n"
            "• Clicca `Carica estensione\n"
            "  non pacchettizzata`.\n\n"
            "[Tempo: 40 secondi]",
        ),
        (
            696,
            "PASSO 4 · SEMAFORO ON",
            "Chatta & Mina $00MESH",
            "4",
            SOL_GREEN,
            "• Clicca l'icona 00MESH:\n"
            "  `[ON] Bridge GPU Attivo`!\n"
            "• Opzionale: `Firma Wallet`\n"
            "  Phantom (+50 $00MESH).\n"
            "• Apri la Chat Sovrana e usa\n"
            "  tutti i tool gratis!\n\n"
            "[Sei nella Mesh!]",
        ),
    ]
    for sx, sbadge, stitle, stag, scol, sbody in steps:
        c7.box(sx, 30, 206, 330, title=stitle, badge=sbadge, icon_tag=stag, border_col=scol)
        d7.text((sx * S + 14 * S, 122 * S), sbody, font=get_font(10.0), fill=rgba(TEXT_WHITE), spacing=6 * S)
    c7.arrow(224, 195, 244, 195, col=CYAN)
    c7.arrow(450, 195, 470, 195, col=TEAL)
    c7.arrow(676, 195, 696, 195, col=EMERALD)
    paths["install"] = c7.save(ASSETS_DIR / "00mesh_guida_07_install.png")

    # 8. TOKENOMICS $00MESH & PUMP.FUN
    c8 = MarketingCanvas(920, 390)
    d8 = c8.draw()
    c8.box(
        25,
        28,
        415,
        334,
        title="Distribuzione 1.000.000.000 $00MESH",
        subtitle="Offerta Fissa Solana SPL · Zero Inflazione",
        badge="FAIR LAUNCH PUMP.FUN",
        icon_tag="SPL",
        border_col=SOLANA,
    )
    bars = [
        ("70% Bonding Curve & Fair Launch (700M)", 0.70, CYAN, 130),
        ("20% Community Mining PoUW (200M)", 0.20, SOL_GREEN, 198),
        ("10% Core Dev & Ecosistema (100M)", 0.10, VIOLET, 266),
    ]
    for btitle, bpct, bcol, by in bars:
        d8.text((48 * S, by * S), btitle, font=get_font(10.5, bold=True), fill=rgba(TEXT_WHITE))
        d8.rounded_rectangle([48 * S, (by + 20) * S, 415 * S, (by + 42) * S], radius=8 * S, fill=rgba("#060a15"), outline=rgba(LINE_COL))
        fill_w = max(36, int(367 * bpct))
        d8.rounded_rectangle([48 * S, (by + 20) * S, (48 + fill_w) * S, (by + 42) * S], radius=8 * S, fill=rgba(bcol, 225))

    c8.box(
        475,
        28,
        420,
        334,
        title="Tabella Ricompense PoUW",
        subtitle="Quanto accumuli condividendo la tua GPU?",
        badge="CALCOLO UTILE REALE",
        icon_tag="WIN",
        border_col=SOL_GREEN,
    )
    d8.text(
        (495 * S, 120 * S),
        "[+] BONUS BENVENUTO (1 Click):\n"
        "    • +50.0 $00MESH alla connessione del nodo/wallet\n\n"
        "[+] PER OGNI COMPITO AI COMPLETATO:\n"
        "    • Modello Leggero (<= 4B, es. Qwen 4B):  +2.0 $00MESH\n"
        "    • Modello Medio (7B-9B, es. Llama 8B):  +3.0 $00MESH\n"
        "    • Modello Pesante (>= 14B / Bonsai 2):  +6.0 $00MESH\n"
        "    • Bonus Durata & Token: fino a +2.5 $00MESH extra\n\n"
        "[+] DISPONIBILITÀ ORARIA (UPTIME):\n"
        "    • +5.0 $00MESH per ogni ora con nodo attivo!",
        font=get_font(10.2),
        fill=rgba("#d1fae5"),
        spacing=5 * S,
    )
    paths["tokenomics"] = c8.save(ASSETS_DIR / "00mesh_guida_08_tokenomics.png")

    return paths


def build_pdf(diagrams: dict[str, Path]):
    PAGE_W = 297 * mm
    PAGE_H = 167 * mm
    PAGE = landscape((PAGE_W, PAGE_H))

    doc = SimpleDocTemplate(
        str(PDF_OUT),
        pagesize=PAGE,
        leftMargin=13 * mm,
        rightMargin=13 * mm,
        topMargin=11 * mm,
        bottomMargin=11 * mm,
    )

    base = getSampleStyleSheet()
    st_kicker = ParagraphStyle(
        "kicker",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#38bdf8"),
        spaceAfter=2,
    )
    st_title = ParagraphStyle(
        "title",
        parent=base["Title"],
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=23,
        textColor=colors.HexColor("#f8fafc"),
        alignment=0,
        spaceAfter=3,
    )
    st_sub = ParagraphStyle(
        "sub",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#cbd5e1"),
        spaceAfter=6,
    )
    st_card_h = ParagraphStyle(
        "card_h",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor("#38bdf8"),
        spaceAfter=2,
    )
    st_card_b = ParagraphStyle(
        "card_b",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#e2e8f0"),
    )

    def draw_bg(canvas, document):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#070b18"))
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#38bdf8"))
        canvas.rect(0, PAGE_H - 2 * mm, PAGE_W, 2 * mm, fill=1, stroke=0)
        canvas.setStrokeColor(colors.HexColor("#1e293b"))
        canvas.setLineWidth(0.5)
        canvas.line(13 * mm, 9 * mm, PAGE_W - 13 * mm, 9 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(
            13 * mm,
            5 * mm,
            "00MESH 1.05 by ZeroZeroComputer (www.zerozerocomputer.it)  ·  Guida Rapida & Presentazione Ufficiale",
        )
        canvas.drawRightString(
            PAGE_W - 13 * mm,
            5 * mm,
            f"Slide {document.page} di 10",
        )
        canvas.restoreState()

    story = []
    content_w = PAGE_W - 26 * mm

    def add_visual_slide(
        kicker: str,
        title: str,
        subtitle: str,
        img_path: Path,
        cards: list[tuple[str, str]],
        is_last: bool = False,
    ):
        story.append(Paragraph(kicker.upper(), st_kicker))
        story.append(Paragraph(title, st_title))
        story.append(Paragraph(subtitle, st_sub))

        story.append(RLImage(str(img_path), width=content_w, height=84 * mm))
        story.append(Spacer(1, 3 * mm))

        col_w = content_w / 3
        row_cells = []
        for ch, cb in cards:
            cell = [Paragraph(ch, st_card_h), Paragraph(cb, st_card_b)]
            row_cells.append(cell)
        t = Table([row_cells], colWidths=[col_w] * 3)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0d152a")),
                    ("BOX", (0, 0), (0, 0), 0.8, colors.HexColor("#1e293b")),
                    ("BOX", (1, 0), (1, 0), 0.8, colors.HexColor("#1e293b")),
                    ("BOX", (2, 0), (2, 0), 0.8, colors.HexColor("#1e293b")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(t)
        if not is_last:
            story.append(PageBreak())

    # SLIDE 1
    add_visual_slide(
        "SLIDE 01 · BENVENUTO NELL'ERA DELL'AI SOVRANA E GRATUITA",
        "00MESH 1.05: Tutta la Potenza AI, Gratis e Alla Portata di Tutti",
        "Perché pagare 20€/mese di abbonamenti censurati quando puoi avere mesi di sviluppo e 25+ tool professionali a costo zero?",
        diagrams["cover"],
        [
            ("Zero Abbonamenti Mensili", "Non ti chiediamo carte di credito. Tutta l'infrastruttura HyperSpace / 00MESH è accessibile gratuitamente."),
            ("Mesi di Sviluppo Già Pronti", "PDF AnyDoc, OCR illimitato, Ricerca Web SearXNG, Sandbox Python, ComfyUI e Reel Editor già integrati per te."),
            ("Tu Scegli Come Contribuire", "Guarda un semplice banner pubblicitario oppure condividi la tua scheda video con Ollama/LM Studio per essere anche premiato!"),
        ],
    )

    # SLIDE 2
    add_visual_slide(
        "SLIDE 02 · IL MODELLO SOSTENIBILE SPIEGATO SEMPLICE",
        "Le 3 Porte di Accesso: Banner Pubblicitario o Calcolo Condiviso",
        "I server AI consumano corrente: ecco come 00MESH azzera i costi per te e trasforma ogni utente in protagonista.",
        diagrams["access"],
        [
            ("Porta 1: Banner AdSense (Zero PC)", "Non hai un PC potente? Nessun problema: il circuito pubblicitario etico GDPR ripaga i server mentre tu usi la rete gratis."),
            ("Porta 2: Condividi GPU (1-Click VIP)", "Hai Ollama o LM Studio? L'estensione Chrome ti sblocca subito la Chat Estesa senza chiavi e ti accredita token $00MESH."),
            ("Porta 3: Chiave Membro (hs-mesh-*)", "Richiedi gratuitamente la tua chiave personale dal modulo sul sito per entrare anche da smartphone o tablet."),
        ],
    )

    # SLIDE 3
    add_visual_slide(
        "SLIDE 03 · LA TUA CASSETTA DEGLI ATTREZZI AUTOMATICA",
        "25+ Skill e Tool Già Integrati: Tu Chiedi, L'AI Sceglie l'Attrezzo",
        "Non devi imparare comandi da programmatore: l'hook 'before_context' capisce cosa ti serve e attiva il tool giusto da solo.",
        diagrams["arsenal"],
        [
            ("Selettore Automatico Intelligente", "Scrivi 'sicurezza', 'converti PDF', 'cerca sul web' o 'crea sito': il Control Plane inietta in <1ms la skill firmata SHA-256."),
            ("Nessuna Allucinazione o Finta", "Quando dai un link preciso, l'AI usa web_fetch e legge davvero la pagina. Quando fa un calcolo, esegue vero codice Python."),
            ("Memoria Hermes & Sogni Notturni", "A differenza dei soliti chatbot smemorati, Hermes ricorda i tuoi progetti e di notte riflette per proporti nuove soluzioni."),
        ],
    )

    # SLIDE 4
    add_visual_slide(
        "SLIDE 04 · GUIDA PRATICA ALLA CONSOLE CHAT SOVRANA",
        "Dentro la Chat Estesa: 3 Pulsanti per Fare Tutto",
        "Un'interfaccia pulita, identica alle chat più famose, ma senza filtri ideologici e con tre superpoteri sotto la barra di testo.",
        diagrams["chat_ui"],
        [
            ("1. Tasto '[+] Allega File' (AnyDoc)", "Trascina PDF, contratti, file Word, CSV o codice sorgente: vengono decompressi nel tuo browser senza fughe di dati."),
            ("2. Tasto '[W] Web Search' (SearXNG)", "Illumina il bottone Web Search per interrogare internet in tempo reale senza tracciamento e con l'elenco delle fonti cliccabili."),
            ("3. Tasto '[>] Esegui in Sandbox'", "Su ogni blocco di codice Python compare il tasto Esegui: cliccalo per lanciarlo in un container Docker usa-e-getta sicuro al 100%."),
        ],
    )

    # SLIDE 5
    add_visual_slide(
        "SLIDE 05 · STUDIO MULTIMEDIALE, SOCIAL & UFFICIO",
        "Immagini ComfyUI, Video Reel 9:16 e Siti Web Pronti all'Uso",
        "Mesi di ingegneria creativa condensati in comandi semplicissimi per creator, professionisti, negozi e uffici.",
        diagrams["creative"],
        [
            ("Immagini & Pose Controllate", "Usa /image in chat o 'Anna Batch diretto' per generare fino a 50 immagini coerenti con controllo della posa DWPose."),
            ("Reel Editor + Apple Vision", "Sincronizza i tagli video ai battiti musicali e posiziona i titoli karaoke DIETRO alle persone senza bisogno di green screen."),
            ("Generatore Siti Web & Ufficio", "Usa create_website per ottenere un sito web completo in .zip, o converti scansioni cartacee con Unlimited OCR locale."),
        ],
    )

    # SLIDE 6
    add_visual_slide(
        "SLIDE 06 · TRASFORMA IL TUO PC IN UN NODO SOVRANO",
        "Condividere Calcolo con Ollama o LM Studio: Come Funziona?",
        "La tua scheda video dorme per il 90% della giornata. Risvegliala con l'estensione Chrome 00MESH senza toccare il router!",
        diagrams["bridge"],
        [
            ("Zero Configurazioni da Sistemista", "Non serve installare Docker, né Python, né aprire porte sul modem di casa. L'estensione Chrome fa da ponte sicuro."),
            ("100% Velocità Hardware Nativa", "Sfrutta tutta la potenza di NVIDIA CUDA, AMD ROCm o Apple Silicon Metal attraverso Ollama (:11434) o LM Studio (:1234)."),
            ("Privacy Totale & Reversibile", "Condividi solo i calcoli matematici del modello AI: nessuno può leggere i tuoi file e ti disconnetti chiudendo il browser."),
        ],
    )

    # SLIDE 7
    add_visual_slide(
        "SLIDE 07 · MINI GUIDA D'INSTALLAZIONE PASSO-PASSO",
        "Attiva il Tuo Nodo GPU in 3 Minuti Orologio (Passo dopo Passo)",
        "Segui questi 4 passaggi illustrati una sola volta: dal minuto successivo avrai accesso illimitato e mining attivo.",
        diagrams["install"],
        [
            ("1. Apri Ollama o LM Studio", "Assicurati che Ollama sia attivo vicino all'orologio di sistema o che il Local Server di LM Studio sia acceso."),
            ("2. Carica in chrome://extensions", "Attiva la levetta 'Modalità sviluppatore' in alto a destra e clicca 'Carica estensione non pacchettizzata' sulla cartella estratta."),
            ("3. Goditi il Semaforo Verde [ON]", "La pagina zerozerocomputer.it rileverà subito il plugin: vedrai 'Bridge GPU Attivo' e il pulsante per entrare nella Chat!"),
        ],
    )

    # SLIDE 8
    add_visual_slide(
        "SLIDE 08 · TOKENOMICS $00MESH & RICOMPENSE SOLANA",
        "Più Aiuti la Rete, Più Accumuli: Proof-of-Useful-Work (PoUW)",
        "Niente sprechi di corrente stile Bitcoin: su 00MESH ogni punto guadagnato corrisponde a una risposta AI reale data alla community.",
        diagrams["tokenomics"],
        [
            ("+50 $00MESH Subito al Primo Avvio", "Collega il tuo nodo e firma gratuitamente con il wallet Phantom o Solflare (Ed25519) per ricevere il Welcome Grant."),
            ("Moltiplicatori Fino a 3.0x", "Modelli leggeri pagano 2 $00MESH/task, modelli medi 3 $00MESH e modelli pesanti (>=14B) ben 6 $00MESH + 5 $00MESH/ora di uptime!"),
            ("Pool Comunitaria del 20% (200M)", "Su 1 Miliardo di token fissi su pump.fun (Solana), 200 Milioni sono riservati esclusivamente a chi condivide calcolo."),
        ],
    )

    # SLIDE 9: TABELLA RICETTARIO DEI COMANDI
    story.append(Paragraph("SLIDE 09 · IL RICETTARIO RAPIDO COPIA-E-INCOLLA", st_kicker))
    story.append(Paragraph("Cosa Posso Chiedere Oggi? 8 Esempi Pronti per Iniziare", st_title))
    story.append(
        Paragraph(
            "Non sai da dove partire? Copia una di queste frasi nella Chat Sovrana e guarda i tool di HyperSpace lavorare al posto tuo:",
            st_sub,
        )
    )

    th_style = ParagraphStyle("th", parent=st_card_h, textColor=colors.white, fontSize=9)
    td_bold = ParagraphStyle("tdb", parent=st_card_b, fontName="Helvetica-Bold", textColor=colors.HexColor("#38bdf8"))
    td_norm = ParagraphStyle("tdn", parent=st_card_b, fontSize=8.3)
    td_code = ParagraphStyle("tdc", parent=st_card_b, fontName="Courier", fontSize=8, textColor=colors.HexColor("#a7f3d0"))

    recipes = [
        [
            Paragraph("Cosa Vuoi Fare", th_style),
            Paragraph("Cosa Fare / Scrivere nella Chat", th_style),
            Paragraph("Skill / Tool Attivato in Automatico", th_style),
            Paragraph("Costo per Te", th_style),
        ],
        [
            Paragraph("[PDF] Capire un Contratto Lungo", td_bold),
            Paragraph("Clicca '[+] Allega File', scegli il PDF e scrivi: «Riassumi i punti critici e le scadenze»", td_norm),
            Paragraph("AnyDoc Client Decompressor + classificazione PDF", td_code),
            Paragraph("0,00 EUR (Gratis)", td_bold),
        ],
        [
            Paragraph("[WEB] Fare Ricerca di Mercato Live", td_bold),
            Paragraph("Attiva '[W] Web Search' e scrivi: «Confronta i prezzi e le novità sulle batterie stato solido 2026»", td_norm),
            Paragraph("SearXNG Private Meta-Search + Citazione Fonti", td_code),
            Paragraph("0,00 EUR (Gratis)", td_bold),
        ],
        [
            Paragraph("[PY] Calcolare o Testare Codice", td_bold),
            Paragraph("«Scrivi uno script Python che simula un piano di risparmio e verifica il risultato» + Clicca [>] Esegui", td_norm),
            Paragraph("code_sandbox (Container Docker Isolato Offline)", td_code),
            Paragraph("0,00 EUR (Gratis)", td_bold),
        ],
        [
            Paragraph("[IMG] Creare un'Immagine AI", td_bold),
            Paragraph("Scrivi: «/image ritratto cyberpunk cinematografico al tramonto, luci al neon, 8k»", td_norm),
            Paragraph("ComfyUI GPU Bridge (SD 1.5 / SDXL / Qwen-Image)", td_code),
            Paragraph("0,00 EUR (Gratis)", td_bold),
        ],
        [
            Paragraph("[VID] Preparare un Reel 9:16", td_bold),
            Paragraph("«Prepara un progetto Reel con le migliori foto di Anna e programma il montaggio alle 09:00»", td_norm),
            Paragraph("reel_prepare_project + person_mask Apple Vision", td_code),
            Paragraph("0,00 EUR (Gratis)", td_bold),
        ],
        [
            Paragraph("[ZIP] Creare un Sito Web Completo", td_bold),
            Paragraph("«Crea un sito web landing page per la mia pizzeria artigianale con pulsante Prenota»", td_norm),
            Paragraph("create_website (Genera HTML responsive + ZIP)", td_code),
            Paragraph("0,00 EUR (Gratis)", td_bold),
        ],
        [
            Paragraph("[SEC] Controllare la Sicurezza", td_bold),
            Paragraph("«Fai una security review completa di questo script e verifica se ci sono vulnerabilità»", td_norm),
            Paragraph("Hook before_context -> Skill ECC Security-Review", td_code),
            Paragraph("0,00 EUR (Gratis)", td_bold),
        ],
        [
            Paragraph("[MEM] Salvare un Ricordo Duraturo", td_bold),
            Paragraph("«Ricorda nella memoria Hermes che il nostro cliente principale usa il listino B scontato del 15%»", td_norm),
            Paragraph("omega_store / omega_query (Database SQLite FTS5)", td_code),
            Paragraph("0,00 EUR (Gratis)", td_bold),
        ],
    ]

    rt = Table(recipes, colWidths=[58 * mm, 102 * mm, 76 * mm, 35 * mm])
    rt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#0d152a")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#0d152a"), colors.HexColor("#111c38")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#263454")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(rt)
    story.append(PageBreak())

    # SLIDE 10: CALL TO ACTION & RIEPILOGO FINALE
    add_visual_slide(
        "SLIDE 10 · ENTRA ORA NELLA RETE SOVRANA ZEROZEROCOMPUTER",
        "Inizia Subito in 60 Secondi: Il Futuro dell'AI è Nelle Tue Mani",
        "Scegli la tua corsia preferita: naviga gratis supportato dal banner o accendi Ollama/LM Studio per diventare un Nodo Operatore.",
        diagrams["install"],
        [
            ("1. Vai su zerozerocomputer.it", "Apri la piattaforma dal tuo browser: trovi subito la Chat Sovrana, la mappa 3D dei nodi in tempo reale e il modulo per la tua chiave."),
            ("2. Scarica 00mesh-chrome-bridge.zip", "Collega il tuo Ollama o LM Studio locale in 3 click per avere accesso immediato illimitato e accumulare token $00MESH."),
            ("3. Unisciti alla Community", "Hai domande o vuoi collegare un server aziendale? Scrivici dal modulo contatti sul sito o a info@zerozerocomputer.it!"),
        ],
        is_last=True,
    )

    doc.build(story, onFirstPage=draw_bg, onLaterPages=draw_bg)
    shutil.copy2(PDF_OUT, WEB_DOCS_DIR / PDF_OUT.name)
    print(f"[OK] Presentazione PDF generata: {PDF_OUT} ({PDF_OUT.stat().st_size // 1024} KB)")


def build_markdown():
    md_text = r"""# 🚀 00MESH 1.05 — Guida Rapida & Presentazione Ufficiale
### *Come sfruttare GRATIS mesi di sviluppo AI, 25+ Skill e Tool professionali con un semplice Banner Pubblicitario o condividendo la tua GPU con Ollama / LM Studio*

> **🎯 Il Messaggio in 10 Secondi:**
> Mentre tutti ti chiedono **20€ o 200€ al mese** per usare chatbot chiusi, censurati e che leggono i tuoi affari privati, **ZeroZeroComputer** ha costruito **00MESH (HyperSpace 1.05)**: una centrale operativa di Intelligenza Artificiale Sovrana con **oltre 25 strumenti professionali già integrati**.
> E la parte migliore? **Per te è 100% GRATIS.** Non paghi con la carta di credito: la rete si sostiene con un semplice **banner pubblicitario etico** oppure **condividendo un pizzico della tua scheda video** quando non la usi (tramite **Ollama** o **LM Studio**), premiandoti pure con i token **`$00MESH`** su Solana!

📄 **Versione Slide PDF Widescreen (16:9) pronta da scaricare e presentare:**
👉 [**Scarica `00mesh-guida-rapida.pdf`**](00mesh-guida-rapida.pdf)

---

## 🌟 Slide 1 · Perché pagare abbonamenti quando hai 00MESH gratis?

![Confronto Paradigma 00MESH](presentation_assets/00mesh_guida_01_cover.png)

### Cosa significa per te (spiegato in modo semplice e diretto):
* **Basta abbonamenti da 20€/mese:** Non devi inserire nessuna carta di credito.
* **Modelli "Abliterated" (Senza Censure o Paternalismi):** I modelli della rete 00MESH rispondono alle tue domande tecniche, creative e lavorative senza farti la morale e senza blocchi artificiali.
* **Mesi di sviluppo già pronti sotto il cofano:** Non hai davanti una semplice scatola vuota di chat, ma un intero **Sistema Operativo per Agenti** capace di leggere PDF, navigare sul web, eseguire codice Python in una stanza blindata, creare siti web e montare video verticali per TikTok e Instagram!

---

## 🚪 Slide 2 · Le 3 Porte di Accesso: Come fai a usare tutto a Gratis?

I computer che fanno girare l'Intelligenza Artificiale consumano energia elettrica e schede video costose. Come fa **00MESH** a offrirti tutto gratuitamente? Ti lascia **3 strade semplicissime**:

![Le 3 Porte di Accesso a 00MESH](presentation_assets/00mesh_guida_02_access.png)

1. **🟡 OPZIONE A — Modalità "Spettatore Smart" (Con Banner Pubblicitario + Nodo Browser):**
   * **Per chi è:** Non hai una scheda video potente o sei su un portatile leggero? Nessun problema!
   * **Come funziona:** Accettando il banner pubblicitario (Google AdSense conforme al GDPR) sulle pagine informative e attivando con 1 click il **Nodo Web Browser**, le visualizzazioni pubblicitarie e i micro-compiti leggeri aiutano a pagare la corrente dei server GPU centrali.
   * **Il tuo vantaggio:** Usi l'AI gratis senza installare nulla sul computer e ricevi subito **+50 `$00MESH`** di benvenuto!

2. **🟢 OPZIONE B — Modalità "Condividi Calcolo GPU" (Con Ollama o LM Studio):**
   * **Per chi è:** Hai un PC con scheda video (es. NVIDIA RTX / AMD) o un Mac (M1/M2/M3/M4)? Per il 90% del tempo in cui navighi o guardi un film, la tua scheda video è ferma allo 0%.
   * **Come funziona:** Tieni aperto **Ollama** o **LM Studio** e aggiungi la nostra leggerissima **Estensione Chrome (`00mesh-chrome-bridge.zip`)**.
   * **Il tuo vantaggio:** **Sblocco istantaneo VIP della Chat Sovrana** (senza bisogno di chiavi d'accesso!) + guadagni token **`$00MESH`** ogni volta che la tua scheda video aiuta un altro utente della rete!

3. **🟣 OPZIONE C — Modalità "Chiave di Rete Membro" (`hs-mesh-*`):**
   * **Per chi è:** Vuoi entrare anche da smartphone, tablet o dal PC dell'ufficio?
   * **Come funziona:** Compili il modulo in fondo alla pagina `zerozerocomputer.it` e ricevi gratuitamente la tua chiave personale `hs-mesh-*`.

---

## 🧰 Slide 3 · Il Tuo Arsenale Segreto: 25+ Skill e Tool che si attivano da soli!

La domanda più frequente di chi inizia è: *"Ma devo imparare comandi complessi per usare tutti gli strumenti sviluppati in questi mesi?"*
**Risposta: ASSOLUTAMENTE NO!**

![Arsenale Completo di Skill e Tool 00MESH](presentation_assets/00mesh_guida_03_arsenal.png)

Dietro la chat lavora un meccanismo automatico chiamato **Hook `before_context`**. Mentre tu scrivi normalmente in italiano, lui legge le tue parole chiave e **innesta nel cervello dell'AI gli attrezzi giusti in meno di un millisecondo**:

| Cosa scrivi tu (in italiano normale) | Quale Super-Potere si accende da solo dietro le quinte |
|---|---|
| *"Leggi questo file PDF / Word / Excel"* | **📎 AnyDoc & PDF Inspector**: estrae tabelle e testo in Markdown pulito direttamente nel browser o col convertitore locale, e usa **Unlimited OCR** sulle scansioni cartacee! |
| *"Cerca le ultime notizie su..."* | **🔍 SearXNG Private Search**: interroga i motori di ricerca senza farti spiare dai cookie e ti mostra il box **Fonti Consultate** con i link veri cliccabili. |
| *"Leggi questa pagina: https://..."* | **🌐 Lettore Diretto `web_fetch`**: non inventa risposte! Apre davvero l'indirizzo web che hai incollato e ne legge il contenuto riga per riga. |
| *"Calcola / Scrivi un programma Python"* | **🐍 Docker Code Sandbox**: apre una cassaforte usa-e-getta, esegue il programma per davvero e ti mostra il risultato matematico certificato (`Exit 0`). |
| *"Controlla se questo codice è sicuro"* | **🛡️ Skill ECC `security-review` & `verification-loop`**: carica le regole di sicurezza firmate crittograficamente (SHA-256) per scovare bug e vulnerabilità. |
| *"Ricordati che il mio progetto..."* | **🧬 Memoria Hermes (`omega_store` / `omega_query`)**: salva i fatti nel database SQLite FTS5 a lungo termine. E di notte, col **Dream Loop**, l'AI rilegge i ricordi e prepara intuizioni per il mattino dopo! |
| *"Pianifica i passi di questo lavoro"* | **🗺️ Wayfinder & Mission Control**: scompone un obiettivo complesso in una mappa ordinata di compiti verificabili che non va mai in loop infinito. |

---

## 💬 Slide 4 · Guida Visiva alla Console Chat Sovrana (3 Bottoni e Sai Usare Tutto)

Quando apri **`chat.html`** (cliccando su *"💬 Apri Chat Estesa"*), ti trovi davanti una plancia chiarissima. Ecco cosa fanno i comandi principali:

![Anatomia della Console Chat Sovrana](presentation_assets/00mesh_guida_04_chat_ui.png)

1. **Selettore Modello (in alto a sinistra):** Scegli con quale cervello parlare (es. `qwen3-vl:4b-instruct` velocissimo a 95 token/sec, modelli *abliterated* senza filtri, oppure `Anna Batch diretto` per generare decine di immagini).
2. **Pulsante `📎 Allega File` (o trascina col mouse):** Trascina dentro la finestra qualsiasi documento (`.pdf`, `.txt`, `.md`, `.csv`, `.json`, `.py`, `.js`, `.html`). Il file viene letto all'istante e compare come una targhetta sopra il messaggio!
3. **Pulsante `🌐 Web Search`:** Cliccalo per accenderlo quando vuoi che l'AI cerchi fatti accaduti oggi stesso su internet.
4. **Pulsante `▶ Esegui in Sandbox` (dentro le risposte di codice):** Ogni volta che l'AI scrive un programma in Python, in alto a destra sul riquadro del codice appare il bottone **`▶ Esegui in Sandbox`**. Cliccalo e sotto si aprirà un vero terminale nero con il risultato reale dell'esecuzione!

---

## 🎨 Slide 5 · Creatività e Multimedia: Immagini, Reel TikTok 9:16 e Siti Web!

Non solo testo e ufficio: in 00MESH sono stati integrati mesi di sviluppo dedicati a chi crea contenuti social, siti web e grafica.

![Creatività, Reel Editor e Website Builder](presentation_assets/00mesh_guida_05_creative.png)

* **🎨 Generatore Immagini (`/image` e `Anna Batch`):**
  * Scrivi `/image` seguito da quello che vuoi vedere e i nodi GPU della rete (con **ComfyUI**) creano l'immagine per te.
  * Vuoi che il personaggio abbia **esattamente una posa del corpo e delle mani**? Il sistema integra **ControlNet DWPose** e un selezionatore visivo automatico (`qwen3-vl`) che controlla le immagini generate e **scarta da solo quelle venute male**!
* **🎬 Reel Editor Verticale 9:16 con Occhi Apple Vision:**
  * Hai foto o clip video e una canzone? Il tool `reel_prepare_project` prepara il montaggio verticale per TikTok, Instagram Reels e YouTube Shorts.
  * **Magia senza Green Screen:** Grazie a `person_mask.swift` (Apple Vision), il sistema ritaglia automaticamente la sagoma della persona e posiziona **i titoli karaoke luminosi DIETRO il soggetto** e i tagli esattamente a tempo con i battiti della cassa musicale!
* **🌐 Creatore di Siti Web (`create_website`):**
  * Chiedi in chat di creare una landing page o un sito vetrina per il tuo negozio o progetto: il tool genera il sito completo responsive e ti consegna il file **`.zip` pronto da pubblicare**!

---

## 🔌 Slide 6 · Come funziona la Condivisione GPU con Ollama o LM Studio?

Perché migliaia di appassionati stanno collegando il proprio PC o Mac a 00MESH? Perché è **il modo più intelligente di trasformare l'hardware che hai già pagato in un lasciapassare gratuito e remunerato**.

![Funzionamento del Chrome Bridge con Ollama e LM Studio](presentation_assets/00mesh_guida_06_bridge.png)

* **Il Problema che abbiamo risolto per te:** Di solito, per mettere in rete un computer servono competenze da ingegnere informatico (Docker, Linux, porte sul router, indirizzi IP).
* **La Soluzione 00MESH Chrome Bridge:** Abbiamo racchiuso tutto in una **minuscola estensione per Google Chrome, Brave o Edge (12 KB)**.
  * L'estensione parla da un lato con il tuo **Ollama** (`localhost:11434`) o **LM Studio** (`127.0.0.1:1234`) sul tuo computer.
  * Dall'altro lato parla in HTTPS crittografato con il Gateway 00MESH.
  * **Sicurezza Totale:** L'estensione **NON può leggere i tuoi file personali**. Riceve solo una domanda di testo, la fa risolvere alla tua scheda video e restituisce la risposta, accreditandoti i punti!

---

## 🛠️ Slide 7 · Mini Guida di Installazione Passo-Passo (In 3 Minuti!)

Anche se non hai mai installato un'estensione manuale prima d'ora, segui questi **4 passi illustrati** e sarai operativo in meno di 3 minuti:

![Mini Guida di Installazione in 4 Passi](presentation_assets/00mesh_guida_07_install.png)

### Passo 1 · Accendi il tuo motore AI locale (Ollama o LM Studio)
* **Se scegli Ollama (Consigliato, leggerissimo):**
  1. Vai su [ollama.com](https://ollama.com), scarica il programma per Windows, Mac o Linux e installalo con due click.
  2. Apri il Terminale (o Prompt dei comandi) e incolla questo singolo comando per scaricare un modello veloce e intelligente:
     ```bash
     ollama run qwen3-vl:4b-instruct
     ```
  3. Fatto! Ora vicino all'orologio del tuo computer c'è l'iconcina del lama: significa che è attivo sulla porta `11434`.
* **Se preferisci LM Studio (Tutto grafico col mouse):**
  1. Scarica [lmstudio.ai](https://lmstudio.ai), cerca un modello qualsiasi (es. *Qwen*, *Llama 3* o *Mistral*) e scaricalo.
  2. Clicca sull'icona **`<->` (Local Server)** a sinistra e premi il pulsante verde **Start Server** (porta `1234`).

### Passo 2 · Scarica il pacchetto dell'Estensione 00MESH
1. Vai sulla pagina principale di **00MESH** (`zerozerocomputer.it`).
2. Clicca sul bottone verde **`⬇️ Scarica Estensione (.zip)`** (il file si chiama `00mesh-chrome-bridge.zip`).
3. Fai doppio click sul file `.zip` scaricato per **estrarre la cartella** (mettila ad esempio nella tua cartella *Documenti* così non la cancelli per sbaglio).

### Passo 3 · Carica l'Estensione nel tuo Browser (Chrome, Brave o Edge)
1. Apri una nuova scheda del browser, clicca nella barra degli indirizzi in alto, scrivi esattamente questo e premi Invio:
   ```text
   chrome://extensions/
   ```
2. Guarda **in alto a destra**: troverai un interruttore chiamato **"Modalità sviluppatore"** (*Developer mode*). **Cliccalo per attivarlo!**
3. Ora **in alto a sinistra** sono apparsi tre nuovi bottoni: clicca sul primo, **`Carica estensione non pacchettizzata`** (*Load unpacked*).
4. Seleziona la cartella `00mesh-chrome-bridge` che hai estratto al Passo 2 e conferma.

### Passo 4 · Semaforo Verde 🟢, Wallet e Chat Sbloccata!
1. Clicca sull'icona del puzzle 🧩 in alto a destra su Chrome e fissa l'icona **00MESH Bridge**.
2. Cliccandoci sopra vedrai che **ha già trovato da sola Ollama o LM Studio** e i tuoi modelli!
3. Torna su `zerozerocomputer.it`: il riquadro di accesso diventerà subito verde (**`🟢 Bridge GPU Attivo`**) e il bottone **`💬 Apri Chat Estesa Sovrana ↗`** sarà completamente sbloccato!

---

## 🪙 Slide 8 · Tokenomics `$00MESH`: Guadagna Condividendo la Tua Potenza!

Ogni volta che il tuo browser o la tua scheda video sono connessi, partecipi alla **Proof-of-Useful-Work (PoUW)**:

![Tokenomics e Tabella Ricompense $00MESH](presentation_assets/00mesh_guida_08_tokenomics.png)

* **🎁 +50.0 `$00MESH` Subito al Primo Collegamento:** Ti basta inserire il tuo indirizzo Solana (wallet gratuito **Phantom** o **Solflare**) e cliccare su **`🟣 Firma Wallet`** per ricevere all'istante il bonus di benvenuto!
* **⚡ Ricompense ad Ogni Risposta AI (Task):**
  * **+2.0 `$00MESH`** per task con modelli leggeri ($\le 4\text{B}$ parametri).
  * **+3.0 `$00MESH`** per task con modelli intermedi ($7\text{B}-9\text{B}$ parametri).
  * **+6.0 `$00MESH`** per task con modelli avanzati ($\ge 14\text{B}$ / MoE / Ternary Bonsai 2).
  * **+5.0 `$00MESH` ogni ora** semplicemente per tenere il nodo acceso e disponibile!
* **🟣 Fair Launch su pump.fun (Solana SPL):** Su **1.000.000.000** di token totali fissi, **200.000.000 `$00MESH` (il 20%)** sono riservati esclusivamente alla Community Pool per chi ha condiviso calcolo nella rete!

> *Nota legale di trasparenza (MiCA UE 2023/1114): `$00MESH` è un utility token sperimentale e un sistema di punti computazionali per premiare il calcolo utile condiviso nella rete di ricerca 00MESH, non un prodotto finanziario speculativo o una promessa di rendita garantita.*

---

## 📋 Riepilogo Veloce: Quali Prompt Provare Subito?

Appena entri nella Chat Sovrana, prova uno di questi 5 comandi per toccare con mano mesi di sviluppo:

1. **Testa la Sandbox Python:**
   > *"Scrivi uno script Python che calcola i primi 50 numeri della serie di Fibonacci, mostra il tempo di calcolo in millisecondi e verifica che funzioni."* *(Poi clicca su `▶ Esegui in Sandbox`!)*
2. **Testa la Ricerca Web Privata:**
   > *(Accendi `🌐 Web Search`)* *"Quali sono le ultime novità di questa settimana sui modelli AI open-source? Citami le fonti."*
3. **Testa l'Analisi Documenti AnyDoc:**
   > *(Trascina un PDF qualsiasi nella chat)* *"Fammi un riassunto in 5 punti chiave e dimmi se ci sono clausole a cui fare attenzione."*
4. **Testa il Creatore di Siti Web:**
   > *"Usa il tool create_website per creare una landing page moderna per uno studio fotografico a Milano chiamato LucePura."*
5. **Testa la Generazione Immagini:**
   > *"/image un astronauta che legge un libro olografico in una biblioteca futuristica immersa nella natura, stile cinematografico 8k"*
"""
    MD_OUT.write_text(md_text, encoding="utf-8")
    print(f"[OK] Guida Markdown generata: {MD_OUT} ({MD_OUT.stat().st_size // 1024} KB)")


def main():
    diagrams = generate_marketing_diagrams()
    build_pdf(diagrams)
    build_markdown()


if __name__ == "__main__":
    main()
