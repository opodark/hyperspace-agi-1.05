# SPDX-License-Identifier: Apache-2.0
"""Generate the Presentation PDF for the Extended Chat Features of HyperSpace Web-Node.

Features covered:
1. AnyDoc: Client-side document, code and PDF ingestion
2. Private Web Search: SearXNG real-time private search
3. Docker Code Sandbox: Ephemeral isolated Python code execution
4. User Experience & Architecture Guide
"""

import os
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
PDF_OUT = ROOT / "docs" / "hyperspace-chat-features.pdf"
WEB_ASSETS_DIR = ROOT / "web-node" / "assets" / "presentation"
WEB_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

S = 2  # Supersampling factor

# -----------------------------------------------------------------------------
# Color Palette
# -----------------------------------------------------------------------------
BG_COLOR = "#070b18"
CARD_COLOR = "#0d152a"
CARD2_COLOR = "#111b36"
LINE_COLOR = "#263454"
TEXT_COLOR = "#f4f6ff"
MUTED_COLOR = "#8d9bbd"
CYAN_COLOR = "#57e6d9"
VIOLET_COLOR = "#9a7cff"
ROSE_COLOR = "#f693bd"
OK_COLOR = "#70e6aa"
BAD_COLOR = "#ff8295"


def rgba(hexcolor, a=255):
    h = hexcolor.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


_FONT_CACHE = {}


def get_font(size, bold=False, mono=False):
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


class DiagramCanvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.im = Image.new("RGBA", (w * S, h * S), rgba(BG_COLOR))
        self._background()

    def _background(self):
        w, h = self.w * S, self.h * S
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        g = ImageDraw.Draw(glow)
        g.ellipse((-w * 0.15, -h * 0.5, w * 0.45, h * 0.55), fill=rgba("#1a2b56", 210))
        g.ellipse((w * 0.62, -h * 0.4, w * 1.15, h * 0.5), fill=rgba("#321c48", 190))
        g.ellipse((w * 0.25, h * 0.75, w * 0.8, h * 1.4), fill=rgba("#0d243a", 130))
        glow = glow.filter(ImageFilter.GaussianBlur(100 * S / 2))
        self.im = Image.alpha_composite(self.im, glow)

        draw = ImageDraw.Draw(self.im)
        step = 40 * S
        grid_col = rgba("#1c2b48", 40)
        for x in range(0, w, step):
            draw.line([(x, 0), (x, h)], fill=grid_col, width=1)
        for y in range(0, h, step):
            draw.line([(0, y), (w, y)], fill=grid_col, width=1)

    def draw(self):
        return ImageDraw.Draw(self.im)

    def save(self, path):
        out = self.im.resize((self.w, self.h), Image.Resampling.LANCZOS)
        out.convert("RGB").save(path, quality=95)

    def card(self, x, y, w, h, title="", subtitle="", color=CYAN_COLOR, fill=CARD_COLOR):
        d = self.draw()
        x1, y1 = x * S, y * S
        x2, y2 = (x + w) * S, (y + h) * S
        rad = 12 * S
        d.rounded_rectangle([x1, y1, x2, y2], radius=rad, fill=rgba(fill), outline=rgba(color, 160), width=int(1.5 * S))
        if title:
            d.text((x1 + 16 * S, y1 + 14 * S), title, font=get_font(13.5, bold=True), fill=rgba(TEXT_COLOR))
        if subtitle:
            d.text((x1 + 16 * S, y1 + 33 * S), subtitle, font=get_font(10.5), fill=rgba(MUTED_COLOR))

    def arrow(self, x1, y1, x2, y2, color=CYAN_COLOR, label=""):
        d = self.draw()
        sx1, sy1 = x1 * S, y1 * S
        sx2, sy2 = x2 * S, y2 * S
        d.line([(sx1, sy1), (sx2, sy2)], fill=rgba(color, 200), width=int(2 * S))
        # Arrowhead
        import math
        angle = math.atan2(sy2 - sy1, sx2 - sx1)
        arrow_len = 10 * S
        p1 = (sx2 - arrow_len * math.cos(angle - math.pi / 6), sy2 - arrow_len * math.sin(angle - math.pi / 6))
        p2 = (sx2 - arrow_len * math.cos(angle + math.pi / 6), sy2 - arrow_len * math.sin(angle + math.pi / 6))
        d.polygon([(sx2, sy2), p1, p2], fill=rgba(color))
        if label:
            mx = (sx1 + sx2) / 2
            my = (sy1 + sy2) / 2 - 10 * S
            d.text((mx, my), label, font=get_font(9.5, bold=True), fill=rgba(color), anchor="ms")


# -----------------------------------------------------------------------------
# Generate Diagram Images
# -----------------------------------------------------------------------------
def generate_diagrams():
    # 1. Architecture Overview Diagram
    c1 = DiagramCanvas(800, 360)
    c1.card(40, 40, 210, 280, title="🌐 Browser Web-Node", subtitle="Client Chat (100vh) ZeroZeroComputer", color=CYAN_COLOR)
    d = c1.draw()
    d.text((55 * S, 110 * S), "• AnyDoc (PDF & Code)\n• SearXNG Query Engine\n• Python Sandbox Terminal\n• SSE Streaming Parser\n• LocalStorage Sessions", font=get_font(11), fill=rgba("#cbd5e1"), spacing=8*S)

    c1.card(300, 110, 180, 140, title="⚡ Federation Gateway", subtitle="Ingresso Pubblico (Porta 8095)", color=VIOLET_COLOR)
    d.text((315 * S, 175 * S), "• Whitelist rigorosa\n• Rate-limiting per rotta\n• Preflight CORS nativo", font=get_font(10.5), fill=rgba("#cbd5e1"), spacing=6*S)

    c1.card(530, 40, 230, 90, title="🧠 Control-Plane Mesh", subtitle="Porta 8085 / Orchestrazione", color=CYAN_COLOR)
    c1.card(530, 145, 230, 85, title="🔍 SearXNG Privato", subtitle="Porta 8092 / No-Tracking Search", color=ROSE_COLOR)
    c1.card(530, 245, 230, 85, title="📦 Docker Code Sandbox", subtitle="Isolamento sterile offline Python", color=OK_COLOR)

    c1.arrow(250, 180, 300, 180, color=CYAN_COLOR, label="POST /web/*")
    c1.arrow(480, 150, 530, 85, color=VIOLET_COLOR, label="/v1/chat")
    c1.arrow(480, 180, 530, 180, color=ROSE_COLOR, label="/web/search")
    c1.arrow(480, 210, 530, 280, color=OK_COLOR, label="/web/sandbox/run")
    p1 = ASSETS_DIR / "chat_features_arch.png"
    c1.save(p1)

    # 2. AnyDoc Flow Diagram
    c2 = DiagramCanvas(800, 360)
    c2.card(40, 80, 200, 200, title="📁 File Ingestion", subtitle="Drag & Drop o Picker", color=CYAN_COLOR)
    d2 = c2.draw()
    d2.text((55 * S, 150 * S), "• Codice (.py, .js, .json)\n• Documenti (.txt, .md, .csv)\n• File PDF multipagina\n• Anteprima chip e rimozione", font=get_font(10.5), fill=rgba("#cbd5e1"), spacing=6*S)

    c2.card(290, 80, 220, 200, title="⚙️ Client Decompressor", subtitle="Zero Dipendenze Esterne", color=VIOLET_COLOR)
    d2.text((305 * S, 150 * S), "• DecompressionStream('deflate')\n• Decodifica stream FlateDecode\n• Parser operatore BT..ET\n• Nessun leak di dati privati", font=get_font(10.5), fill=rgba("#cbd5e1"), spacing=6*S)

    c2.card(560, 80, 200, 200, title="💬 Prompt Context", subtitle="Iniezione Neurale", color=OK_COLOR)
    d2.text((575 * S, 150 * S), "• Sezione [Documenti Allegati]\n• Badge pillola nel messaggio\n• Riferimenti riga e sintassi\n• Risposte contestualizzate", font=get_font(10.5), fill=rgba("#cbd5e1"), spacing=6*S)

    c2.arrow(240, 180, 290, 180, color=CYAN_COLOR, label="Lettura locale")
    c2.arrow(510, 180, 560, 180, color=VIOLET_COLOR, label="Testo estratto")
    p2 = ASSETS_DIR / "chat_features_anydoc.png"
    c2.save(p2)

    # 3. SearXNG Web Search Flow Diagram
    c3 = DiagramCanvas(800, 360)
    c3.card(40, 80, 210, 200, title="🌐 Toggle Web Search", subtitle="Controllo Utente Diretto", color=CYAN_COLOR)
    d3 = c3.draw()
    d3.text((55 * S, 150 * S), "• Tasto illuminato nel composer\n• Query utente naturale\n• Feedback visivo ricerca attiva\n• Zero profilazione o cookie", font=get_font(10.5), fill=rgba("#cbd5e1"), spacing=6*S)

    c3.card(290, 80, 220, 200, title="🔍 SearXNG Container", subtitle="Metaricerca Locale (Porta 8092)", color=ROSE_COLOR)
    d3.text((305 * S, 150 * S), "• Interrogazione multi-motore\n• Rilevamento lingua automatico\n• Fallback DuckDuckGo Lite\n• Filtraggio anti-throttling", font=get_font(10.5), fill=rgba("#cbd5e1"), spacing=6*S)

    c3.card(550, 80, 210, 200, title="📑 Fonti Verificate", subtitle="Trasparenza Totale", color=OK_COLOR)
    d3.text((565 * S, 150 * S), "• Accordion 'Fonti Consultate'\n• Link diretti verificabili\n• Snippet e metadati fonte\n• Risposte con dati odierni", font=get_font(10.5), fill=rgba("#cbd5e1"), spacing=6*S)

    c3.arrow(250, 180, 290, 180, color=CYAN_COLOR, label="/web/search")
    c3.arrow(510, 180, 550, 180, color=ROSE_COLOR, label="Fonti estratte")
    p3 = ASSETS_DIR / "chat_features_search.png"
    c3.save(p3)

    # 4. Code Sandbox Execution Diagram
    c4 = DiagramCanvas(800, 360)
    c4.card(40, 80, 210, 200, title="🐍 Script Assistant", subtitle="Markdown Code Box", color=CYAN_COLOR)
    d4 = c4.draw()
    d4.text((55 * S, 150 * S), "• Blocco codice Python\n• Tasto '▶ Esegui in Sandbox'\n• Codice fino a 64 KB\n• Stato 'Esecuzione…'", font=get_font(10.5), fill=rgba("#cbd5e1"), spacing=6*S)

    c4.card(290, 80, 220, 200, title="📦 Docker Sandbox", subtitle="MicroVM Sterile Offline", color=VIOLET_COLOR)
    d4.text((305 * S, 150 * S), "• Workspace temporaneo\n• Python 3.12 isolato\n• Nessun accesso di rete\n• Timeout e discard automatico", font=get_font(10.5), fill=rgba("#cbd5e1"), spacing=6*S)

    c4.card(550, 80, 210, 200, title="💻 Terminale Inline", subtitle="Output Cyberpunk", color=OK_COLOR)
    d4.text((565 * S, 150 * S), "• Stdout in tempo reale (400ms)\n• Cattura traceback Stderr\n• Badge Exit Code (Exit 0)\n• Tasto '↺ Riesegui'", font=get_font(10.5), fill=rgba("#cbd5e1"), spacing=6*S)

    c4.arrow(250, 180, 290, 180, color=CYAN_COLOR, label="Esegui script")
    c4.arrow(510, 180, 550, 180, color=VIOLET_COLOR, label="Stdout / Stderr")
    p4 = ASSETS_DIR / "chat_features_sandbox.png"
    c4.save(p4)

    return [p1, p2, p3, p4]


# -----------------------------------------------------------------------------
# Generate PDF Document with ReportLab
# -----------------------------------------------------------------------------
def build_pdf(diagram_paths):
    PAGE_W = 297 * mm
    PAGE_H = 172 * mm
    PAGE = landscape((PAGE_W, PAGE_H))

    doc = SimpleDocTemplate(
        str(PDF_OUT),
        pagesize=PAGE,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    BASE = getSampleStyleSheet()

    styles = {
        "title": ParagraphStyle("Title", parent=BASE["Title"], fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=colors.HexColor("#f4f6ff"), spaceAfter=4),
        "subtitle": ParagraphStyle("Sub", parent=BASE["Normal"], fontName="Helvetica", fontSize=12, leading=16, textColor=colors.HexColor("#9ba9c7"), spaceAfter=12),
        "heading": ParagraphStyle("H2", parent=BASE["Heading2"], fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=colors.HexColor("#57e6d9"), spaceAfter=6),
        "body": ParagraphStyle("Body", parent=BASE["Normal"], fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=colors.HexColor("#cbd5e1")),
        "bullet": ParagraphStyle("Bul", parent=BASE["Normal"], fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=colors.HexColor("#cbd5e1"), leftIndent=12),
        "tag": ParagraphStyle("Tag", parent=BASE["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=colors.HexColor("#57e6d9")),
        "card_title": ParagraphStyle("CT", parent=BASE["Normal"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.white),
        "card_body": ParagraphStyle("CB", parent=BASE["Normal"], fontName="Helvetica", fontSize=8.5, leading=12, textColor=colors.HexColor("#94a3b8")),
    }

    story = []

    def slide_header(title, subtitle, tag="HYPERSPACE 1.05 · WEB-NODE CHAT"):
        return [
            Paragraph(f"<font color='#57e6d9'><b>{tag}</b></font>", styles["tag"]),
            Spacer(1, 1 * mm),
            Paragraph(title, styles["title"]),
            Paragraph(subtitle, styles["subtitle"]),
        ]

    # ── Slide 1: Copertina ───────────────────────────────────────────────────
    story.extend([
        Spacer(1, 10 * mm),
        Paragraph("<font color='#57e6d9'><b>ZERO ZERO COMPUTER · ARCHITETTURA DISTRIBUITA HYPERSPACE</b></font>", styles["tag"]),
        Spacer(1, 2 * mm),
        Paragraph("La Nuova Chat Estesa del Web-Node", ParagraphStyle("CovT", parent=styles["title"], fontSize=28, leading=32)),
        Paragraph("AnyDoc Ingestion, Ricerca Web SearXNG Privata e Sandbox Docker per l'Esecuzione di Codice", ParagraphStyle("CovS", parent=styles["subtitle"], fontSize=13, leading=17)),
        Spacer(1, 4 * mm),
    ])

    img_arch = RLImage(str(diagram_paths[0]), width=265 * mm, height=95 * mm)
    story.append(img_arch)
    story.append(Spacer(1, 4 * mm))

    footer_table = Table(
        [[
            Paragraph("<b>📎 AnyDoc Ingestion</b><br/>PDF & Code nel Browser", styles["card_title"]),
            Paragraph("<b>🌐 Private Web Search</b><br/>SearXNG Privato & Fonti Verificate", styles["card_title"]),
            Paragraph("<b>⚡ Docker Code Sandbox</b><br/>Python Sterile Offline in 400ms", styles["card_title"]),
            Paragraph("<b>🔒 Zero-Knowledge Privacy</b><br/>Hosting Linux Aruba & Cloudflare", styles["card_title"]),
        ]],
        colWidths=[65 * mm, 70 * mm, 65 * mm, 65 * mm],
    )
    footer_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0d152a")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#1e2d4a")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#1e2d4a")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(footer_table)
    story.append(PageBreak())

    # ── Slide 2: AnyDoc Ingestion ────────────────────────────────────────────
    story.extend(slide_header(
        "📎 AnyDoc Ingestion: Documenti, Codice e PDF",
        "Analisi client-side istantanea a zero dipendenze: i tuoi file non lasciano il browser finché non invii il messaggio."
    ))

    img_anydoc = RLImage(str(diagram_paths[1]), width=265 * mm, height=90 * mm)
    story.append(img_anydoc)
    story.append(Spacer(1, 4 * mm))

    anydoc_info = Table([
        [
            Paragraph("<b>Formati Supportati</b><br/>Python (.py), JavaScript, TypeScript, HTML, CSS, JSON, CSV, TSV, YAML, Shell script, SQL, log e documenti PDF multipagina.", styles["card_body"]),
            Paragraph("<b>Estrattore PDF Nativo</b><br/>Decodifica degli stream binari zlib FlateDecode tramite <i>DecompressionStream('deflate')</i> nativo del browser ed estrazione blocchi operatore BT..ET.", styles["card_body"]),
            Paragraph("<b>Esperienza d'Uso (UX)</b><br/>Trascina qualsiasi file sulla finestra (Drag & Drop con overlay visivo) o tocca <i>📎 Allega File</i>. I documenti compaiono come chip modificabili nel composer.", styles["card_body"]),
        ]
    ], colWidths=[88 * mm, 88 * mm, 88 * mm])
    anydoc_info.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0d152a")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#1e2d4a")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#1e2d4a")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(anydoc_info)
    story.append(PageBreak())

    # ── Slide 3: Private Web Search ──────────────────────────────────────────
    story.extend(slide_header(
        "🌐 Ricerca Web Privata in Tempo Reale con SearXNG",
        "Informazioni fresche e citazioni verificate senza tracciamento pubblicitario o profilazione dell'utente."
    ))

    img_search = RLImage(str(diagram_paths[2]), width=265 * mm, height=90 * mm)
    story.append(img_search)
    story.append(Spacer(1, 4 * mm))

    search_info = Table([
        [
            Paragraph("<b>Controllo Utente a Singolo Tocco</b><br/>Attiva o disattiva la ricerca con il pulsante toggle <i>🌐 Web Search</i> nel composer. Quando attivo, si illumina con un bagliore ciano.", styles["card_body"]),
            Paragraph("<b>Motore SearXNG Self-Hosted</b><br/>La query passa dall'endpoint protetto <i>/web/search</i> verso l'istanza container locale (porta 8092), con rilevamento lingua della query e fallback su DuckDuckGo Lite.", styles["card_body"]),
            Paragraph("<b>Trasparenza delle Fonti Citate</b><br/>Ogni risposta arricchita mostra un accordion collassabile <i>🌐 Fonti Web Consultate</i> con link diretti e snippet estratti dai siti originali.", styles["card_body"]),
        ]
    ], colWidths=[88 * mm, 88 * mm, 88 * mm])
    search_info.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0d152a")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#1e2d4a")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#1e2d4a")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(search_info)
    story.append(PageBreak())

    # ── Slide 4: Docker Code Sandbox ─────────────────────────────────────────
    story.extend(slide_header(
        "⚡ Docker Code Sandbox: Esecuzione di Script Python",
        "Esegui il codice generato dal modello in micro-ambienti isolati offline direttamente nella finestra di chat."
    ))

    img_sandbox = RLImage(str(diagram_paths[3]), width=265 * mm, height=90 * mm)
    story.append(img_sandbox)
    story.append(Spacer(1, 4 * mm))

    sandbox_info = Table([
        [
            Paragraph("<b>Pulsante Esegui Integrato</b><br/>Ogni blocco di codice Python generato dall'assistente include il pulsante <i>▶ Esegui in Sandbox</i> nell'header del box Markdown.", styles["card_body"]),
            Paragraph("<b>Isolamento Sterile & Pulizia</b><br/>Lo script viene scritto in uno workspace usa-e-getta dentro il container Docker offline (senza socket Docker e senza rete). Al termine, lo workspace viene eliminato.", styles["card_body"]),
            Paragraph("<b>Terminale Cyberpunk Reattivo</b><br/>L'esecuzione dura meno di 500ms e renderizza un terminale inline con stdout in verde, stderr in rosso, Exit Code badge (Exit 0) e tempo di run.", styles["card_body"]),
        ]
    ], colWidths=[88 * mm, 88 * mm, 88 * mm])
    sandbox_info.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0d152a")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#1e2d4a")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#1e2d4a")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(sandbox_info)
    story.append(PageBreak())

    # ── Slide 5: Guida Pratica & Architettura ─────────────────────────────────
    story.extend(slide_header(
        "Guida Utente & Accesso alla Mesh Neurale",
        "Come sfruttare al massimo la Web App Chat su zerozerocomputer.it/chat.html"
    ))

    guide_table = Table([
        [
            Paragraph("<b>1. Accesso & Chiave Mesh</b><br/>Inserisci la tua chiave autorizzata (es. <i>hs-mesh-*</i>) per sbloccare l'accesso diretto alla rete neurale. La chiave viene memorizzata in modo sicuro e verificata dal Control-Plane.", styles["card_body"]),
            Paragraph("<b>2. Scelta del Modello</b><br/>Seleziona dal menu in alto il modello ideale: modelli standard o varianti <i>🔥 Abliterated</i> per la massima libertà di calcolo senza filtri ideologici.", styles["card_body"]),
        ],
        [
            Paragraph("<b>3. Gestione Conversazioni</b><br/>La cronologia delle chat viene salvata localmente nel browser (localStorage). Puoi creare nuove chat, rinominarle o cancellarle con un clic.", styles["card_body"]),
            Paragraph("<b>4. Sblocco Limite Token</b><br/>Il gateway federato supporta risposte lunghe e articolate fino a 4096 token con streaming SSE fluido a bassa latenza.", styles["card_body"]),
        ],
        [
            Paragraph("<b>5. Privacy & Hosting Linux</b><br/>Nessun tracciamento commerciale. Backend self-hosted su Docker, reverse-proxy Cloudflare e front-end distribuito su Hosting Linux Aruba.", styles["card_body"]),
            Paragraph("<b>6. Supporto Tecnico ZeroZeroComputer</b><br/>Sede legale a Saronno (VA). Assistenza diretta via email a <i>info@zerozerocomputer.it</i> o tramite il form contatti della landing page.", styles["card_body"]),
        ],
    ], colWidths=[132 * mm, 132 * mm])
    guide_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0d152a")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#1e2d4a")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#1e2d4a")),
        ("PADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(guide_table)

    # Decorator background per ogni pagina
    def draw_bg(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor(BG_COLOR))
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=True, stroke=False)
        # Linea sottile superiore e inferiore
        canvas.setStrokeColor(colors.HexColor("#1e2d4a"))
        canvas.setLineWidth(1)
        canvas.line(14 * mm, PAGE_H - 10 * mm, PAGE_W - 14 * mm, PAGE_H - 10 * mm)
        canvas.line(14 * mm, 10 * mm, PAGE_W - 14 * mm, 10 * mm)
        # Footer
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(14 * mm, 6 * mm, "Zero Zero Computer · HyperSpace AGI 1.05 · Chat Estesa & Connettori Mesh")
        canvas.drawRightString(PAGE_W - 14 * mm, 6 * mm, f"Pagina {canvas._pageNumber} di 5")
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_bg, onLaterPages=draw_bg)

    # Copia anche nel web-node assets
    import shutil
    web_dest = WEB_ASSETS_DIR / "hyperspace-chat-features.pdf"
    shutil.copyfile(PDF_OUT, web_dest)
    print(f"PDF generato con successo: {PDF_OUT}")
    print(f"PDF copiato in web-node: {web_dest}")


def main():
    print("1. Generazione diagrammi visivi ad alta risoluzione...")
    diagrams = generate_diagrams()
    print("2. Compilazione del documento PDF di presentazione con ReportLab...")
    build_pdf(diagrams)
    print("Fatto!")


if __name__ == "__main__":
    main()
