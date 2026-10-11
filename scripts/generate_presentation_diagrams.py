# SPDX-License-Identifier: Apache-2.0
"""Generate high-resolution explanatory visual diagrams for the HyperSpace 1.05 presentation."""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "docs" / "presentation_assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# System fonts
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial.ttf"
if not os.path.exists(FONT_PATH):
    FONT_PATH = "/System/Library/Fonts/Helvetica.ttc"

def get_font(size, bold=False):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()

# Palette
C_DARK_BG = "#0B1020"
C_DARK_CARD = "#151D30"
C_LIGHT_BG = "#F8FAFC"
C_WHITE = "#FFFFFF"
C_BORDER = "#E2E8F0"
C_BORDER_DARK = "#1E293B"

C_CYAN = "#0284C7"
C_CYAN_LIGHT = "#38BDF8"
C_CYAN_BG = "#E0F2FE"

C_PURPLE = "#7C3AED"
C_PURPLE_LIGHT = "#A855F7"
C_PURPLE_BG = "#F3E8FF"

C_EMERALD = "#059669"
C_EMERALD_LIGHT = "#10B981"
C_EMERALD_BG = "#D1FAE5"

C_AMBER = "#D97706"
C_AMBER_LIGHT = "#F59E0B"
C_AMBER_BG = "#FEF3C7"

C_RED = "#DC2626"
C_RED_BG = "#FEE2E2"

C_TEXT_DARK = "#0F172A"
C_TEXT_MUTED = "#64748B"
C_TEXT_LIGHT = "#FFFFFF"
C_TEXT_LIGHT_MUTED = "#94A3B8"


def draw_arrow(draw, p1, p2, color=C_CYAN, width=3, arrow_size=12):
    x1, y1 = p1
    x2, y2 = p2
    draw.line([p1, p2], fill=color, width=width)
    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    a1 = angle + math.pi * 0.85
    a2 = angle - math.pi * 0.85
    p_left = (x2 + arrow_size * math.cos(a1), y2 + arrow_size * math.sin(a1))
    p_right = (x2 + arrow_size * math.cos(a2), y2 + arrow_size * math.sin(a2))
    draw.polygon([p2, p_left, p_right], fill=color)


def draw_badge(draw, xy, text, bg=C_CYAN_BG, text_color=C_CYAN, font_size=16):
    font = get_font(font_size)
    x, y = xy
    bbox = font.getbbox(text)
    w = bbox[2] - bbox[0] + 20
    h = bbox[3] - bbox[1] + 10
    draw.rounded_rectangle((x, y, x + w, y + h), radius=8, fill=bg)
    draw.text((x + 10, y + 4), text, fill=text_color, font=font)
    return w, h


# -----------------------------------------------------------------------------
# 1. DIAGRAM 01: COVER HERO EMBLEM
# -----------------------------------------------------------------------------
def gen_diagram_01():
    img = Image.new("RGB", (1200, 520), color=C_DARK_BG)
    draw = ImageDraw.Draw(img)

    f_title = get_font(28)
    f_sub = get_font(18)
    f_badge = get_font(15)

    # Central Core
    cx, cy = 600, 240
    draw.ellipse((cx - 160, cy - 160, cx + 160, cy + 160), fill=C_DARK_CARD, outline=C_CYAN_LIGHT, width=3)
    draw.ellipse((cx - 130, cy - 130, cx + 130, cy + 130), fill=C_DARK_BG, outline=C_PURPLE_LIGHT, width=2)
    
    t1 = "HYPERSPACE 1.05"
    t2 = "AGI OPERATING SYSTEM"
    b1 = f_title.getbbox(t1)
    b2 = f_sub.getbbox(t2)
    draw.text((cx - (b1[2]-b1[0])//2, cy - 25), t1, fill=C_TEXT_LIGHT, font=f_title)
    draw.text((cx - (b2[2]-b2[0])//2, cy + 12), t2, fill=C_CYAN_LIGHT, font=f_sub)

    # 4 Satellite Nodes
    nodes = [
        (180, 110, "MISSION CONTROL", "Bounded DAG Orchestration", C_CYAN),
        (1020, 110, "CODE SANDBOX", "Quarantine & Model-Agnostic Gates", C_EMERALD_LIGHT),
        (180, 370, "HERMES MEMORY", "FTS5 SQLite & Dream Loop", C_PURPLE_LIGHT),
        (1020, 370, "TAILSCALE MESH", "Private Encrypted Fabric", C_AMBER_LIGHT),
    ]

    for nx, ny, title, sub, col in nodes:
        draw_arrow(draw, (cx, cy), (nx, ny), color=col, width=2, arrow_size=10)
        draw.rounded_rectangle((nx - 150, ny - 50, nx + 150, ny + 50), radius=14, fill=C_DARK_CARD, outline=col, width=2)
        bt = f_sub.getbbox(title)
        bs = f_badge.getbbox(sub)
        draw.text((nx - (bt[2]-bt[0])//2, ny - 24), title, fill=C_TEXT_LIGHT, font=f_sub)
        draw.text((nx - (bs[2]-bs[0])//2, ny + 6), sub, fill=col, font=f_badge)

    # Bottom Pill
    foot_text = "100% INFERENZA LOCALE SOVRANA  ·  ZERO LEAK DEI DATI  ·  HUMAN-IN-THE-LOOP DIRETTO"
    bf = f_badge.getbbox(foot_text)
    fx = cx - (bf[2]-bf[0])//2 - 20
    draw.rounded_rectangle((fx, 465, fx + (bf[2]-bf[0]) + 40, 505), radius=10, fill=C_DARK_CARD, outline=C_CYAN, width=1)
    draw.text((fx + 20, 475), foot_text, fill=C_CYAN_LIGHT, font=f_badge)

    img.save(ASSETS_DIR / "diagram_01_cover.png")


# -----------------------------------------------------------------------------
# 2. DIAGRAM 02: PARADIGMA - CHATBOT VS GOVERNED RUNTIME
# -----------------------------------------------------------------------------
def gen_diagram_02():
    img = Image.new("RGB", (1200, 820), color=C_LIGHT_BG)
    draw = ImageDraw.Draw(img)

    f_head = get_font(24)
    f_sub = get_font(18)
    f_body = get_font(15)
    f_pill = get_font(14)

    # Top: Chatbot tradizionale
    draw.rounded_rectangle((40, 40, 1160, 380), radius=18, fill=C_WHITE, outline=C_RED, width=2)
    draw_badge(draw, (70, 65), "MODELLO TRADIZIONALE", bg=C_RED_BG, text_color=C_RED, font_size=15)
    draw.text((310, 68), "Chatbot con Tool Esterni (Rischio Alto & Instabile)", fill=C_TEXT_DARK, font=f_head)

    # Steps traditional
    boxes_trad = [
        (80, 140, 260, 240, "Utente / Prompt", "Richiesta aperta in chat", "#F1F5F9", C_TEXT_DARK),
        (380, 140, 580, 240, "Loop LLM Aperto", "Generazione libera non vincolata", "#FEF2F2", C_RED),
        (700, 140, 940, 240, "Azioni Dirette Host", "Scrittura immediata su file", "#FEF2F2", C_RED),
        (1010, 140, 1120, 240, "Disastro", "Loop infiniti\nFile rotti", C_RED_BG, C_RED),
    ]
    for x1, y1, x2, y2, t, s, bg, tc in boxes_trad:
        draw.rounded_rectangle((x1, y1, x2, y2), radius=12, fill=bg, outline=tc, width=1)
        draw.text((x1 + 15, y1 + 25), t, fill=tc, font=f_sub)
        draw.text((x1 + 15, y1 + 55), s, fill=C_TEXT_MUTED, font=f_body)

    draw_arrow(draw, (260, 190), (380, 190), color=C_TEXT_MUTED, width=2)
    draw_arrow(draw, (580, 190), (700, 190), color=C_RED, width=2)
    draw_arrow(draw, (940, 190), (1010, 190), color=C_RED, width=2)

    draw.text((80, 280), "Criticità tipiche: L'AI inventa di aver completato il lavoro, cancella codice host o consuma token all'infinito.", fill=C_RED, font=f_body)

    # Bottom: HyperSpace Governed Runtime
    draw.rounded_rectangle((40, 420, 1160, 780), radius=18, fill=C_WHITE, outline=C_EMERALD, width=2)
    draw_badge(draw, (70, 445), "HYPERSPACE 1.05", bg=C_EMERALD_BG, text_color=C_EMERALD, font_size=15)
    draw.text((250, 448), "Runtime Operativo Governato (Sicuro, Deterministico, Verificabile)", fill=C_TEXT_DARK, font=f_head)

    boxes_hs = [
        (80, 520, 250, 630, "Obiettivo Chiaro", "Prompt + Criteri oggettivi", "#F8FAFC", C_TEXT_DARK),
        (300, 520, 510, 630, "Mission Control", "DAG con Budget rigido", C_CYAN_BG, C_CYAN),
        (560, 520, 780, 630, "Stanza Ermetica", "Sandbox Docker effimera", C_PURPLE_BG, C_PURPLE),
        (830, 520, 990, 630, "Gate Qualità", "Verifica binaria / test", C_EMERALD_BG, C_EMERALD),
        (1030, 520, 1130, 630, "Review", "OK Umano", "#ECFDF5", C_EMERALD),
    ]
    for x1, y1, x2, y2, t, s, bg, tc in boxes_hs:
        draw.rounded_rectangle((x1, y1, x2, y2), radius=12, fill=bg, outline=tc, width=1)
        draw.text((x1 + 12, y1 + 25), t, fill=tc, font=f_sub)
        draw.text((x1 + 12, y1 + 55), s, fill=C_TEXT_DARK, font=f_body)

    draw_arrow(draw, (250, 575), (300, 575), color=C_CYAN, width=2)
    draw_arrow(draw, (510, 575), (560, 575), color=C_PURPLE, width=2)
    draw_arrow(draw, (780, 575), (830, 575), color=C_EMERALD, width=2)
    draw_arrow(draw, (990, 575), (1030, 575), color=C_EMERALD, width=2)

    draw.text((80, 670), "Vantaggio Assoluto: Nessuna riga di codice tocca il tuo computer senza verifica algoritmica e tua autorizzazione esplicita.", fill=C_EMERALD, font=f_body)

    img.save(ASSETS_DIR / "diagram_02_paradigma.png")


# -----------------------------------------------------------------------------
# 3. DIAGRAM 03: MISSION CONTROL DAG
# -----------------------------------------------------------------------------
def gen_diagram_03():
    img = Image.new("RGB", (1200, 820), color=C_LIGHT_BG)
    draw = ImageDraw.Draw(img)

    f_head = get_font(22)
    f_sub = get_font(17)
    f_body = get_font(14)
    f_badge = get_font(13)

    draw.rounded_rectangle((40, 40, 1160, 780), radius=18, fill=C_WHITE, outline=C_BORDER, width=2)
    draw_badge(draw, (70, 65), "MISSION CONTROL", bg=C_PURPLE_BG, text_color=C_PURPLE, font_size=15)
    draw.text((270, 68), "Decomposizione a DAG Bounded (Grafo Aciclico con Limiti)", fill=C_TEXT_DARK, font=f_head)

    # Goal Box
    draw.rounded_rectangle((80, 150, 360, 260), radius=14, fill=C_CYAN_BG, outline=C_CYAN, width=2)
    draw.text((105, 175), "Obiettivo Operatore", fill=C_CYAN, font=f_sub)
    draw.text((105, 205), "Es: 'Analizza dati vendite\ne crea presentazione PDF'", fill=C_TEXT_DARK, font=f_body)

    # Planner Box
    draw.rounded_rectangle((440, 150, 720, 260), radius=14, fill=C_PURPLE_BG, outline=C_PURPLE, width=2)
    draw.text((465, 175), "Planner (Architetto)", fill=C_PURPLE, font=f_sub)
    draw.text((465, 205), "Scompone in task ordinati\ncon dipendenze rigide", fill=C_TEXT_DARK, font=f_body)

    draw_arrow(draw, (360, 205), (440, 205), color=C_CYAN, width=3)

    # Tasks Level
    # Task 1
    draw.rounded_rectangle((800, 110, 1120, 200), radius=12, fill="#F8FAFC", outline=C_BORDER, width=2)
    draw.text((820, 125), "Task 1: Lettura & Ingestion", fill=C_TEXT_DARK, font=f_sub)
    draw.text((820, 155), "Ruolo: repo-analyst (Sola lettura)", fill=C_TEXT_MUTED, font=f_body)

    # Task 2
    draw.rounded_rectangle((800, 220, 1120, 310), radius=12, fill="#F8FAFC", outline=C_CYAN, width=2)
    draw.text((820, 235), "Task 2: Compilazione & Script", fill=C_CYAN, font=f_sub)
    draw.text((820, 265), "Ruolo: coder (Code Sandbox protetta)", fill=C_TEXT_DARK, font=f_body)

    # Task 3
    draw.rounded_rectangle((800, 330, 1120, 420), radius=12, fill="#F8FAFC", outline=C_EMERALD, width=2)
    draw.text((820, 345), "Task 3: Validazione Qualità", fill=C_EMERALD, font=f_sub)
    draw.text((820, 375), "Ruolo: verifier (Quality Gate)", fill=C_TEXT_DARK, font=f_body)

    draw_arrow(draw, (720, 185), (800, 155), color=C_PURPLE, width=2)
    draw_arrow(draw, (720, 205), (800, 265), color=C_PURPLE, width=2)
    draw_arrow(draw, (720, 225), (800, 375), color=C_PURPLE, width=2)

    # Governance & Budget Box
    draw.rounded_rectangle((80, 470, 1120, 740), radius=14, fill="#F8FAFC", outline=C_BORDER, width=1)
    draw.text((110, 495), "I Guardrail Matematici di Sicurezza (Budget Invalicabili)", fill=C_TEXT_DARK, font=f_sub)

    budgets = [
        ("Max Steps: 40", "Nessun ciclo infinito; se sforato, si arresta con errore pulito", C_CYAN),
        ("Token/Task: 4096", "Quota massima di pensiero per prevenire allucinazioni", C_PURPLE),
        ("Timeout: 1200s", "Deadline assoluta prima di dichiarare fallito il task", C_AMBER),
        ("Replan: Max 3", "L'AI può correggersi al massimo 3 volte prima di chiedere aiuto", C_EMERALD),
    ]

    bx = 110
    by = 545
    for title, desc, col in budgets:
        draw.rounded_rectangle((bx, by, bx + 225, by + 155), radius=10, fill=C_WHITE, outline=col, width=2)
        draw.text((bx + 15, by + 20), title, fill=col, font=f_sub)
        draw.text((bx + 15, by + 60), desc, fill=C_TEXT_DARK, font=f_body)
        bx += 245

    img.save(ASSETS_DIR / "diagram_03_mission_control.png")


# -----------------------------------------------------------------------------
# 4. DIAGRAM 04: CODE SANDBOX & QUALITY GATES
# -----------------------------------------------------------------------------
def gen_diagram_04():
    img = Image.new("RGB", (1200, 820), color=C_LIGHT_BG)
    draw = ImageDraw.Draw(img)

    f_head = get_font(22)
    f_sub = get_font(17)
    f_body = get_font(14)

    draw.rounded_rectangle((40, 40, 1160, 780), radius=18, fill=C_WHITE, outline=C_BORDER, width=2)
    draw_badge(draw, (70, 65), "STANZA ERMETICA & GATE", bg=C_EMERALD_BG, text_color=C_EMERALD, font_size=15)
    draw.text((320, 68), "Code Sandbox Effimera & Gate di Qualità Model-Agnostic", fill=C_TEXT_DARK, font=f_head)

    # Left: Host OS
    draw.rounded_rectangle((80, 150, 450, 450), radius=16, fill="#F8FAFC", outline=C_EMERALD, width=2)
    draw.text((110, 180), "COMPUTER HOST (Reale)", fill=C_EMERALD, font=f_sub)
    draw.text((110, 215), "• Il tuo filesystem operativo\n• Dati aziendali e codice sorgente\n• Zero accessi diretti da codice AI\n• File protetti da scrittura non autorizzata\n• Nessun commit automatico", fill=C_TEXT_DARK, font=f_body)

    # Center: The Wall
    draw.rounded_rectangle((490, 150, 570, 450), radius=10, fill=C_DARK_CARD, outline=C_CYAN, width=2)
    draw.text((515, 230), "B\nA\nR\nR\nI\nE\nR\nA", fill=C_CYAN_LIGHT, font=f_sub)

    # Right: Sandbox
    draw.rounded_rectangle((610, 150, 1120, 450), radius=16, fill="#FEF3C7", outline=C_AMBER, width=2)
    draw.text((640, 180), "CODE SANDBOX EFFIMERA (Docker)", fill=C_AMBER, font=f_sub)
    draw.text((640, 215), "• Spazio usa-e-getta temporaneo\n• L'agente genera ed esegue script qui dentro\n• Auto-pruning automatico dei workspace vecchi\n• Chiusura forzata immediata su stop\n• Output in quarantena (applied: false)", fill=C_TEXT_DARK, font=f_body)

    # Bottom: Quality Gates
    draw.rounded_rectangle((80, 500, 1120, 740), radius=16, fill=C_WHITE, outline=C_CYAN, width=2)
    draw.text((110, 525), "I 3 Cancelli di Validazione Indipendente (Model-Agnostic Gates)", fill=C_CYAN, font=f_sub)

    gates = [
        ("Cancello 1: File Header", "Verifica fisica dei byte magici (%PDF, PNG, ELF)\nNon si fida del nome file o del testo dell'LLM.", C_CYAN),
        ("Cancello 2: Parsing AST", "Analisi sintattica dell'albero di codice\nBlocca errori di sintassi prima di qualsiasi test.", C_PURPLE),
        ("Cancello 3: Test Automatici", "Esecuzione suite Pytest nel container\nSolo se tutti i test sono VERDI si può procedere.", C_EMERALD),
    ]

    gx = 110
    for title, desc, col in gates:
        draw.rounded_rectangle((gx, 570, gx + 315, 710), radius=12, fill="#F8FAFC", outline=col, width=1)
        draw.text((gx + 15, 590), title, fill=col, font=f_sub)
        draw.text((gx + 15, 630), desc, fill=C_TEXT_DARK, font=f_body)
        gx += 335

    img.save(ASSETS_DIR / "diagram_04_sandbox_gates.png")


# -----------------------------------------------------------------------------
# 5. DIAGRAM 05: TOOL & SKILL FORGE
# -----------------------------------------------------------------------------
def gen_diagram_05():
    img = Image.new("RGB", (1200, 820), color=C_LIGHT_BG)
    draw = ImageDraw.Draw(img)

    f_head = get_font(22)
    f_sub = get_font(17)
    f_body = get_font(14)

    draw.rounded_rectangle((40, 40, 1160, 780), radius=18, fill=C_WHITE, outline=C_BORDER, width=2)
    draw_badge(draw, (70, 65), "FORGE DELLE ABILITÀ", bg=C_CYAN_BG, text_color=C_CYAN, font_size=15)
    draw.text((310, 68), "Ciclo di Vita delle Skill & Hook Adattivi Deterministici", fill=C_TEXT_DARK, font=f_head)

    # 4 Steps of Skill Lifecycle
    steps = [
        (80, 160, "1. Proposta Agente", "L'AI sintetizza un nuovo\nscript o ricetta d'azione", C_CYAN),
        (350, 160, "2. Bozza Inerte", "Stato DRAFT con lucchetto;\nimpossibile eseguirla", C_AMBER),
        (620, 160, "3. Firma SHA-256", "Revisione umana & hash\ncrittografico verificato", C_PURPLE),
        (890, 160, "4. Skill Attiva", "Caricabile in sicurezza\nsolo per ruoli autorizzati", C_EMERALD),
    ]

    for x, y, title, desc, col in steps:
        draw.rounded_rectangle((x, y, x + 230, y + 150), radius=14, fill="#F8FAFC", outline=col, width=2)
        draw.text((x + 15, y + 25), title, fill=col, font=f_sub)
        draw.text((x + 15, y + 65), desc, fill=C_TEXT_DARK, font=f_body)

    draw_arrow(draw, (310, 235), (350, 235), color=C_CYAN, width=2)
    draw_arrow(draw, (580, 235), (620, 235), color=C_AMBER, width=2)
    draw_arrow(draw, (850, 235), (890, 235), color=C_PURPLE, width=2)

    # Bottom: Adaptive Hook Engine
    draw.rounded_rectangle((80, 370, 1120, 730), radius=16, fill="#F8FAFC", outline=C_BORDER, width=1)
    draw.text((110, 400), "Hook 'before_context': Iniezione Intelligente Senza Spreco di Token", fill=C_TEXT_DARK, font=f_sub)

    examples = [
        ("Trigger 'security' / 'sicurezza'", "Inietta automaticamente le best practice di security review nel contesto dell'agente", C_PURPLE),
        ("Trigger 'convert' / 'documento'", "Inietta le linee guida di conversione AnyDoc per estrarre Markdown pulito", C_CYAN),
        ("Trigger con URL Esplicito", "Impone obbligatoriamente il tool web_fetch e spegne la ricerca libera web_search", C_EMERALD),
    ]

    ey = 460
    for trigger, action, col in examples:
        draw.rounded_rectangle((110, ey, 1090, ey + 65), radius=10, fill=C_WHITE, outline=col, width=1)
        draw.text((130, ey + 22), trigger, fill=col, font=f_sub)
        draw.text((450, ey + 22), action, fill=C_TEXT_DARK, font=f_body)
        ey += 85

    draw.text((110, 685), "Regola Aurea: Massimo 2 skill contemporanee e tetto rigido di 24.000 byte per preservare la finestra di contesto.", fill=C_TEXT_MUTED, font=f_body)

    img.save(ASSETS_DIR / "diagram_05_forge_hooks.png")


# -----------------------------------------------------------------------------
# 6. DIAGRAM 06: HERMES MEMORY & DREAM LOOP
# -----------------------------------------------------------------------------
def gen_diagram_06():
    img = Image.new("RGB", (1200, 820), color=C_LIGHT_BG)
    draw = ImageDraw.Draw(img)

    f_head = get_font(22)
    f_sub = get_font(17)
    f_body = get_font(14)

    draw.rounded_rectangle((40, 40, 1160, 780), radius=18, fill=C_WHITE, outline=C_BORDER, width=2)
    draw_badge(draw, (70, 65), "MEMORIA & SOGNI", bg=C_PURPLE_BG, text_color=C_PURPLE, font_size=15)
    draw.text((280, 68), "Memoria Hermes & Nightly Dream Loop (Il Sonno REM dell'AI)", fill=C_TEXT_DARK, font=f_head)

    # Top: Hermes Single Source of Truth
    draw.rounded_rectangle((80, 150, 1120, 350), radius=16, fill="#F8FAFC", outline=C_CYAN, width=2)
    draw.text((110, 175), "DI GIORNO: Hermes Agent come Unica Fonte di Verità", fill=C_CYAN, font=f_sub)

    mem_boxes = [
        ("MEMORY.md & USER.md", "Fatti consolidati sull'utente e preferenze di lavoro", 110, 220),
        ("SQLite FTS5 (state.db)", "Ricerca full-text istantanea ad altissima velocità", 460, 220),
        ("Graphify Code Graph", "Mappa delle dipendenze del codice generata localmente", 810, 220),
    ]
    for title, desc, mx, my in mem_boxes:
        draw.rounded_rectangle((mx, my, mx + 300, my + 95), radius=10, fill=C_WHITE, outline=C_BORDER, width=1)
        draw.text((mx + 15, my + 18), title, fill=C_TEXT_DARK, font=f_sub)
        draw.text((mx + 15, my + 50), desc, fill=C_TEXT_MUTED, font=f_body)

    # Bottom: Dream Loop
    draw.rounded_rectangle((80, 400, 1120, 730), radius=16, fill="#F3E8FF", outline=C_PURPLE, width=2)
    draw.text((110, 425), "DI NOTTE / IN PAUSA: Il Dream Loop (Riflessione Cognitiva Idle-Only)", fill=C_PURPLE, font=f_sub)

    steps_dream = [
        ("1. Attivazione a Riposo", "Parte solo quando il computer non ha lavoro prioritario in corso", 110, 475),
        ("2. Sintesi delle Memorie", "Trova contraddizioni, collegamenti nascosti e idee evolutive", 460, 475),
        ("3. Quarantena Ipotesi", "I risultati restano 'ipotesi': NON toccano la memoria senza ok", 810, 475),
    ]
    for title, desc, sx, sy in steps_dream:
        draw.rounded_rectangle((sx, sy, sx + 300, sy + 105), radius=10, fill=C_WHITE, outline=C_PURPLE, width=1)
        draw.text((sx + 15, sy + 20), title, fill=C_PURPLE, font=f_sub)
        draw.text((sx + 15, sy + 55), desc, fill=C_TEXT_DARK, font=f_body)

    draw_arrow(draw, (410, 525), (460, 525), color=C_PURPLE, width=2)
    draw_arrow(draw, (760, 525), (810, 525), color=C_PURPLE, width=2)

    draw.text((110, 640), "Preemption Istantanea: Se l'utente scrive anche una sola parola, il sogno si interrompe in millisecondi per rispondere subito!", fill=C_PURPLE, font=f_body)

    img.save(ASSETS_DIR / "diagram_06_hermes_dreams.png")


# -----------------------------------------------------------------------------
# 7. DIAGRAM 07: TAILSCALE MESH & DISTRIBUTED HARDWARE
# -----------------------------------------------------------------------------
def gen_diagram_07():
    img = Image.new("RGB", (1200, 820), color=C_LIGHT_BG)
    draw = ImageDraw.Draw(img)

    f_head = get_font(22)
    f_sub = get_font(17)
    f_body = get_font(14)

    draw.rounded_rectangle((40, 40, 1160, 780), radius=18, fill=C_WHITE, outline=C_BORDER, width=2)
    draw_badge(draw, (70, 65), "RETE NERVOSA DISTRIBUITA", bg=C_CYAN_BG, text_color=C_CYAN, font_size=15)
    draw.text((370, 68), "Mesh Privata Cifrata Tailscale & Calcolo Eterogeneo Ibrido", fill=C_TEXT_DARK, font=f_head)

    # Central Cloud Overlay
    draw.rounded_rectangle((440, 280, 760, 540), radius=20, fill=C_DARK_CARD, outline=C_CYAN_LIGHT, width=3)
    draw.text((475, 360), "TESSUTO PRIVATO", fill=C_TEXT_LIGHT, font=f_head)
    draw.text((505, 400), "TAILSCALE MESH", fill=C_CYAN_LIGHT, font=f_sub)
    draw.text((470, 440), "VPN Cifrata P2P WireGuard", fill=C_TEXT_LIGHT_MUTED, font=f_body)

    # 4 Nodes
    nodes = [
        (80, 140, "Mac Studio / MacBook", "Apple Silicon Metal & Neural Engine\nVision & Audio ultra-veloci in locale", C_EMERALD, (380, 210), (460, 310)),
        (720, 140, "PC Windows Workstation", "GPU Dedicate NVIDIA RTX\nRendering ComfyUI & simulazioni pesanti", C_PURPLE, (720, 210), (680, 310)),
        (80, 550, "Server Linux On-Premise", "Istanza Ollama Locale\nModelli linguistici aperti, zero costi API", C_CYAN, (380, 620), (460, 510)),
        (720, 550, "Web Nodes nel Browser", "Nodi leggeri su portatili/tablet\nTrascrizione, OCR e piccoli task di supporto", C_AMBER, (720, 620), (680, 510)),
    ]

    for nx, ny, title, desc, col, p_start, p_end in nodes:
        draw.rounded_rectangle((nx, ny, nx + 400, ny + 140), radius=14, fill="#F8FAFC", outline=col, width=2)
        draw.text((nx + 20, ny + 25), title, fill=col, font=f_sub)
        draw.text((nx + 20, ny + 65), desc, fill=C_TEXT_DARK, font=f_body)
        draw.line([p_start, p_end], fill=col, width=2)

    draw.text((110, 730), "Vantaggio di Sovranità: I nodi comunicano tra loro senza esporre porte a Internet e senza inviare dati a terzi.", fill=C_EMERALD, font=f_body)

    img.save(ASSETS_DIR / "diagram_07_mesh_network.png")


# -----------------------------------------------------------------------------
# 8. DIAGRAM 08: REEL EDITOR & APPLE VISION
# -----------------------------------------------------------------------------
def gen_diagram_08():
    img = Image.new("RGB", (1200, 820), color=C_LIGHT_BG)
    draw = ImageDraw.Draw(img)

    f_head = get_font(22)
    f_sub = get_font(17)
    f_body = get_font(14)

    draw.rounded_rectangle((40, 40, 1160, 780), radius=18, fill=C_WHITE, outline=C_AMBER_BG, width=2)
    draw_badge(draw, (70, 65), "PRODUZIONE MULTIMEDIA", bg=C_AMBER_BG, text_color=C_AMBER, font_size=15)
    draw.text((340, 68), "Reel Editor: Montaggio Dinamico & Vision Neurale Apple", fill=C_TEXT_DARK, font=f_head)

    # 9:16 Video Phone Mockup on Left
    draw.rounded_rectangle((90, 150, 420, 720), radius=28, fill=C_DARK_CARD, outline=C_CYAN, width=3)
    draw.rounded_rectangle((110, 180, 400, 690), radius=18, fill=C_DARK_BG, outline=C_BORDER_DARK, width=1)
    draw.text((150, 210), "REEL 9:16 (1080x1920)", fill=C_CYAN_LIGHT, font=f_sub)
    draw.text((130, 260), "1. Traccia Musicale", fill=C_TEXT_LIGHT_MUTED, font=f_body)
    draw.text((130, 310), "2. Beat Detection (Tagli)", fill=C_EMERALD_LIGHT, font=f_body)
    draw.text((130, 360), "3. Testo Karaoke Dietro", fill=C_AMBER_LIGHT, font=f_body)
    draw.text((130, 420), "4. Soggetto in Primo Piano\n   (Scontornato da AI)", fill=C_WHITE, font=f_sub)
    draw.text((130, 520), "Durate: 30s | 60s | 120s\nExport: MP4 TikTok/Reels", fill=C_CYAN_LIGHT, font=f_body)

    # Explanatory Layers on Right
    layers = [
        ("Analisi Audio & Beat Detection", "Rileva i picchi ritmici della musica e posiziona i cambi di inquadratura al millisecondo esatto sul ritmo musicale.", C_CYAN),
        ("Segmentazione Swift Apple Vision", "Modulo nativo in Swift (person_mask.swift) su macOS: isola il corpo umano istantaneamente senza green screen.", C_PURPLE),
        ("Composizione a Più Livelli", "Permette di posizionare titoli, karaoke rame/avorio ed effetti dietro la persona, creando un look da studio televisivo.", C_EMERALD),
        ("Generazione Giornaliera alle 09:00", "Un LaunchAgent macOS monta un nuovo video ogni mattina e lo invia alla coda di revisione senza pubblicarlo subito.", C_AMBER),
    ]

    ly = 160
    for title, desc, col in layers:
        draw.rounded_rectangle((460, ly, 1120, ly + 115), radius=14, fill="#F8FAFC", outline=col, width=2)
        draw.text((485, ly + 20), title, fill=col, font=f_sub)
        draw.text((485, ly + 55), desc, fill=C_TEXT_DARK, font=f_body)
        ly += 140

    img.save(ASSETS_DIR / "diagram_08_reel_vision.png")


# -----------------------------------------------------------------------------
# 9. DIAGRAM 09: HYPERSPACE UFFICIO & CONNECTORS
# -----------------------------------------------------------------------------
def gen_diagram_09():
    img = Image.new("RGB", (1200, 820), color=C_LIGHT_BG)
    draw = ImageDraw.Draw(img)

    f_head = get_font(22)
    f_sub = get_font(17)
    f_body = get_font(14)

    draw.rounded_rectangle((40, 40, 1160, 780), radius=18, fill=C_WHITE, outline=C_BORDER, width=2)
    draw_badge(draw, (70, 65), "UFFICIO & ENTERPRISE", bg=C_CYAN_BG, text_color=C_CYAN, font_size=15)
    draw.text((320, 68), "HyperSpace Ufficio: AnyDoc, Unlimited OCR & Connettori", fill=C_TEXT_DARK, font=f_head)

    # 3 Pillars: Ingestion, Engine, Connectors
    cols = [
        (80, 150, "1. INGESTION UNIVERSALE", [
            ("PDF Complessi", "Estratti e analizzati a fondo"),
            ("Scansioni Cartacee", "Unlimited OCR offline gratuito"),
            ("Documenti Office", "Word, Excel e presentazioni"),
            ("Contratti & Moduli", "Riconoscimento campi e firme"),
        ], C_CYAN),
        (440, 150, "2. CORE ELABORAZIONE", [
            ("AnyDoc Markdown", "Conversione in testo pulito"),
            ("OnlyOffice Bridge", "Editing e commenti collaborativi"),
            ("Ispezione PDF", "Verifica metadati e firme digitali"),
            ("Memoria di Progetto", "Tutto memorizzato in Hermes"),
        ], C_PURPLE),
        (800, 150, "3. CONNETTORI ENTERPRISE", [
            ("Microsoft 365", "Outlook, Teams, OneDrive"),
            ("Google Workspace", "Gmail, Drive, Docs"),
            ("GitHub Enterprise", "Repository e automazioni"),
            ("Zero Credential Leak", "Password cancellate dai log"),
        ], C_EMERALD),
    ]

    for cx, cy, title, items, col in cols:
        draw.rounded_rectangle((cx, cy, cx + 320, cy + 560), radius=16, fill="#F8FAFC", outline=col, width=2)
        draw.text((cx + 20, cy + 30), title, fill=col, font=f_sub)
        iy = cy + 90
        for ititle, idesc in items:
            draw.rounded_rectangle((cx + 15, iy, cx + 305, iy + 90), radius=10, fill=C_WHITE, outline=C_BORDER, width=1)
            draw.text((cx + 30, iy + 18), ititle, fill=C_TEXT_DARK, font=f_sub)
            draw.text((cx + 30, iy + 50), idesc, fill=C_TEXT_MUTED, font=f_body)
            iy += 105

    draw_arrow(draw, (400, 430), (440, 430), color=C_CYAN, width=3)
    draw_arrow(draw, (760, 430), (800, 430), color=C_PURPLE, width=3)

    img.save(ASSETS_DIR / "diagram_09_ufficio_connectors.png")


# -----------------------------------------------------------------------------
# 10. DIAGRAM 10: MULTI-AGENT COEXISTENCE
# -----------------------------------------------------------------------------
def gen_diagram_10():
    img = Image.new("RGB", (1200, 820), color=C_LIGHT_BG)
    draw = ImageDraw.Draw(img)

    f_head = get_font(22)
    f_sub = get_font(17)
    f_body = get_font(14)

    draw.rounded_rectangle((40, 40, 1160, 780), radius=18, fill=C_WHITE, outline=C_BORDER, width=2)
    draw_badge(draw, (70, 65), "INGEGNERIA MULTI-AGENTE", bg=C_EMERALD_BG, text_color=C_EMERALD, font_size=15)
    draw.text((360, 68), "Coesistenza Multi-Agente Sullo Stesso Repository", fill=C_TEXT_DARK, font=f_head)

    # The 4 Agents
    agents = [
        ("CLINE", "Lavoro su editor in VS Code", C_CYAN),
        ("CODEX", "Infrastruttura e Control Plane", C_PURPLE),
        ("CLAUDE CODE", "Sviluppo motore editor reel", C_AMBER),
        ("ANTIGRAVITY", "Orchestrazione, test e audit", C_EMERALD),
    ]

    ax = 80
    for name, role, col in agents:
        draw.rounded_rectangle((ax, 150, ax + 235, 290), radius=14, fill="#F8FAFC", outline=col, width=2)
        draw.text((ax + 20, 180), name, fill=col, font=f_sub)
        draw.text((ax + 20, 220), role, fill=C_TEXT_DARK, font=f_body)
        draw_arrow(draw, (ax + 117, 290), (ax + 117, 360), color=col, width=2)
        ax += 270

    # Shared Foundation Box
    draw.rounded_rectangle((80, 360, 1120, 730), radius=16, fill=C_DARK_CARD, outline=C_CYAN_LIGHT, width=2)
    draw.text((110, 390), "IL PROTOCOLLO DI CONVIVENZA (Come Lavorare Insieme Senza Conflitti)", fill=C_TEXT_LIGHT, font=f_head)

    rules = [
        ("1. AGENTS.md (La Costituzione)", "Definisce perimetro, strumenti permessi e regole inderogabili. Nessun agente tocca file fuori dal proprio incarico."),
        ("2. AGENT-LOG.md (Il Diario di Bordo)", "Registro append-only condiviso: prima di iniziare ogni agente legge cosa è stato fatto, e alla fine firma il proprio operato."),
        ("3. La Verità è solo nel Repository", "Vietate cartelle esterne o copie divergenti: l'unico codice valido è quello sincronizzato nel progetto."),
        ("4. Oltre 2.300 Test di Sicurezza", "Suite monolitica continuamente verificata a verde: nessuno può lasciare la codebase rotta per l'agente successivo."),
    ]

    ry = 450
    for rtitle, rdesc in rules:
        draw.rounded_rectangle((110, ry, 1090, ry + 55), radius=8, fill="#1E293B", outline=C_BORDER_DARK, width=1)
        draw.text((130, ry + 16), rtitle, fill=C_CYAN_LIGHT, font=f_sub)
        draw.text((450, ry + 16), rdesc, fill=C_TEXT_LIGHT, font=f_body)
        ry += 65

    img.save(ASSETS_DIR / "diagram_10_multi_agent.png")


# -----------------------------------------------------------------------------
# 11. DIAGRAM 11: I 4 PROFILI COMMERCIALI
# -----------------------------------------------------------------------------
def gen_diagram_11():
    img = Image.new("RGB", (1200, 820), color=C_LIGHT_BG)
    draw = ImageDraw.Draw(img)

    f_head = get_font(22)
    f_sub = get_font(17)
    f_body = get_font(14)

    draw.rounded_rectangle((40, 40, 1160, 780), radius=18, fill=C_WHITE, outline=C_BORDER, width=2)
    draw_badge(draw, (70, 65), "MERCATO & VALORE", bg=C_PURPLE_BG, text_color=C_PURPLE, font_size=15)
    draw.text((270, 68), "I Quattro Sbocchi Commerciali di HyperSpace 1.05", fill=C_TEXT_DARK, font=f_head)

    # 4 Quadrants
    quads = [
        (80, 140, "1. ENTERPRISE LOCAL", "Banche, Sanità, Legali, PA", "Agenti intelligenti su dati riservati on-premise; zero fuga di dati all'estero; audit crittografico completo.", "Licenza Annuale + Supporto", C_CYAN),
        (620, 140, "2. AGENT OPERATIONS", "Software House & Scale-up", "Mission Control bounded, sandbox usa-e-getta, pipeline di risoluzione automatica bug e test di codice.", "Abbonamento per Workspace/Nodo", C_PURPLE),
        (80, 440, "3. HYPERSPACE UFFICIO", "Studi Professionali & PMI", "AnyDoc conversione istantanea, Unlimited OCR, OnlyOffice bridge, memoria condivisa di studio.", "Pacchetto Chiavi in Mano / Mese", C_EMERALD),
        (620, 440, "4. HYPERSPACE MULTIMEDIA", "Media House & Creator", "Reel Editor ritmico, Apple Vision person segmentation, Comic Builder e identità virtuali coerenti.", "Licenza Studio + Prod. Video", C_AMBER),
    ]

    for qx, qy, title, target, val, model, col in quads:
        draw.rounded_rectangle((qx, qy, qx + 500, qy + 270), radius=16, fill="#F8FAFC", outline=col, width=2)
        draw.text((qx + 25, qy + 25), title, fill=col, font=f_sub)
        draw.text((qx + 25, qy + 60), f"Target: {target}", fill=C_TEXT_MUTED, font=f_body)
        draw.text((qx + 25, qy + 105), val, fill=C_TEXT_DARK, font=f_body)
        draw.rounded_rectangle((qx + 25, qy + 200, qx + 475, qy + 245), radius=8, fill=C_WHITE, outline=col, width=1)
        draw.text((qx + 40, qy + 215), f"Modello: {model}", fill=col, font=f_body)

    img.save(ASSETS_DIR / "diagram_11_business_quadrants.png")


# -----------------------------------------------------------------------------
# 12. DIAGRAM 12: VISION & SUMMARY
# -----------------------------------------------------------------------------
def gen_diagram_12():
    img = Image.new("RGB", (1200, 480), color=C_DARK_BG)
    draw = ImageDraw.Draw(img)

    f_head = get_font(22)
    f_sub = get_font(17)
    f_body = get_font(14)

    draw.rounded_rectangle((30, 20, 1170, 460), radius=18, fill=C_DARK_CARD, outline=C_CYAN_LIGHT, width=2)

    pillars = [
        ("1. GOVERNATA", "DAG Bounded con limiti matematici;\nniente allucinazioni o loop infiniti", C_CYAN_LIGHT),
        ("2. SICURA", "Code Sandbox usa-e-getta e cancelli\ndi qualità indipendenti dal modello", C_EMERALD_LIGHT),
        ("3. COGNITIVA", "Memoria Hermes SQLite FTS5 e sonno\nREM notturno con quarantena ipotesi", C_PURPLE_LIGHT),
        ("4. DISTRIBUITA", "Mesh privata Tailscale a zero fughe\ne inferenza 100% locale su GPU", C_AMBER_LIGHT),
    ]

    px = 60
    for ptitle, pdesc, col in pillars:
        draw.rounded_rectangle((px, 60, px + 250, 410), radius=14, fill=C_DARK_BG, outline=col, width=2)
        draw.text((px + 20, 95), ptitle, fill=col, font=f_head)
        draw.text((px + 20, 150), pdesc, fill=C_TEXT_LIGHT, font=f_sub)
        px += 275

    img.save(ASSETS_DIR / "diagram_12_summary_vision.png")


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
