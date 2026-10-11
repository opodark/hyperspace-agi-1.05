# SPDX-License-Identifier: Apache-2.0
"""Generate the HyperSpace 1.05 Divulgative & Visual Presentation PDF.

Features:
- High-level, accessible, engaging explanations for a broader audience
- Rich visual explanatory diagrams and illustrations on every slide
- Widescreen 16:9 layout with dual themes (Dark Space Navy & Clean Light Tech)
- Exactly 12 slides on 12 pages with zero overflow
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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

from scripts.generate_presentation_diagrams import generate_all

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "hyperspace-1.05-presentation.pdf"
ASSETS_DIR = ROOT / "docs" / "presentation_assets"

PAGE_W = 297 * mm
PAGE_H = 167 * mm
PAGE = landscape((PAGE_W, PAGE_H))

# Colors
DARK_BG = colors.HexColor("#0B1020")
DARK_CARD = colors.HexColor("#151D30")
LIGHT_BG = colors.HexColor("#F8FAFC")
CARD_BG = colors.white
BORDER_LIGHT = colors.HexColor("#E2E8F0")

TEXT_DARK = colors.HexColor("#0F172A")
TEXT_MUTED = colors.HexColor("#64748B")
TEXT_LIGHT = colors.white
TEXT_LIGHT_MUTED = colors.HexColor("#94A3B8")

CYAN = colors.HexColor("#0284C7")
CYAN_BRIGHT = colors.HexColor("#38BDF8")
PURPLE = colors.HexColor("#7C3AED")
PURPLE_LIGHT = colors.HexColor("#A855F7")
EMERALD = colors.HexColor("#059669")
EMERALD_LIGHT = colors.HexColor("#10B981")
AMBER = colors.HexColor("#D97706")

BASE = getSampleStyleSheet()

S = {
    # Typography Cover & Dark
    "cover_kicker": ParagraphStyle(
        "cover_kicker",
        parent=BASE["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=CYAN_BRIGHT,
        spaceAfter=4,
    ),
    "cover_title": ParagraphStyle(
        "cover_title",
        parent=BASE["Title"],
        fontName="Helvetica-Bold",
        fontSize=27,
        leading=32,
        textColor=TEXT_LIGHT,
        spaceAfter=6,
    ),
    "cover_subtitle": ParagraphStyle(
        "cover_subtitle",
        parent=BASE["Normal"],
        fontName="Helvetica",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#CBD5E1"),
        spaceAfter=8,
    ),
    "cover_tag": ParagraphStyle(
        "cover_tag",
        parent=BASE["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#E0F2FE"),
    ),
    "cover_footer": ParagraphStyle(
        "cover_footer",
        parent=BASE["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=TEXT_LIGHT_MUTED,
    ),
    # Content Slides Header
    "kicker": ParagraphStyle(
        "kicker",
        parent=BASE["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=PURPLE,
        spaceAfter=2,
    ),
    "slide_title": ParagraphStyle(
        "slide_title",
        parent=BASE["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=TEXT_DARK,
        spaceAfter=2,
    ),
    "slide_subtitle": ParagraphStyle(
        "slide_subtitle",
        parent=BASE["Normal"],
        fontName="Helvetica",
        fontSize=9.2,
        leading=12.5,
        textColor=TEXT_MUTED,
        spaceAfter=6,
    ),
    # Divulgative Card Content
    "div_section_head": ParagraphStyle(
        "div_section_head",
        parent=BASE["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.8,
        leading=13,
        textColor=CYAN,
        spaceAfter=2,
    ),
    "div_section_head_purple": ParagraphStyle(
        "div_section_head_purple",
        parent=BASE["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.8,
        leading=13,
        textColor=PURPLE,
        spaceAfter=2,
    ),
    "div_section_head_emerald": ParagraphStyle(
        "div_section_head_emerald",
        parent=BASE["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.8,
        leading=13,
        textColor=EMERALD,
        spaceAfter=2,
    ),
    "div_section_head_amber": ParagraphStyle(
        "div_section_head_amber",
        parent=BASE["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.8,
        leading=13,
        textColor=AMBER,
        spaceAfter=2,
    ),
    "div_body": ParagraphStyle(
        "div_body",
        parent=BASE["BodyText"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=11.3,
        textColor=TEXT_DARK,
        spaceAfter=4,
    ),
    "caption": ParagraphStyle(
        "caption",
        parent=BASE["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=7.6,
        leading=9.8,
        textColor=TEXT_MUTED,
    ),
}


def draw_dark_frame(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(DARK_BG)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setStrokeColor(CYAN_BRIGHT)
    canvas.setLineWidth(2)
    canvas.line(0, PAGE_H - 2, PAGE_W, PAGE_H - 2)
    canvas.setStrokeColor(colors.HexColor("#1E293B"))
    canvas.setLineWidth(0.6)
    canvas.line(16 * mm, 10 * mm, PAGE_W - 16 * mm, 10 * mm)
    canvas.setFont("Helvetica-Bold", 7.5)
    canvas.setFillColor(CYAN_BRIGHT)
    canvas.drawString(16 * mm, 6 * mm, "HYPERSPACE AGI 1.05")
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(TEXT_LIGHT_MUTED)
    canvas.drawString(56 * mm, 6 * mm, "·  SISTEMA OPERATIVO PER AGENTI AUTONOMI")
    canvas.drawRightString(PAGE_W - 16 * mm, 6 * mm, str(doc.page))
    canvas.restoreState()


def draw_light_frame(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(LIGHT_BG)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(CYAN)
    canvas.rect(0, PAGE_H - 2.5 * mm, PAGE_W, 2.5 * mm, fill=1, stroke=0)
    canvas.setStrokeColor(BORDER_LIGHT)
    canvas.setLineWidth(0.6)
    canvas.line(16 * mm, 10 * mm, PAGE_W - 16 * mm, 10 * mm)
    canvas.setFont("Helvetica-Bold", 7.5)
    canvas.setFillColor(PURPLE)
    canvas.drawString(16 * mm, 6 * mm, "HYPERSPACE AGI 1.05")
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawString(56 * mm, 6 * mm, "·  GUIDA DIVULGATIVA & ARCHITETTURA VISIVA")
    canvas.drawRightString(PAGE_W - 16 * mm, 6 * mm, str(doc.page))
    canvas.restoreState()


def make_divulgative_slide(story, kicker, title, subtitle, sections, diagram_name, caption_text, badge_color="cyan"):
    """Create a 2-column slide with friendly explanatory text on left, rich diagram on right."""
    story.append(Paragraph(kicker.upper(), S["kicker"]))
    story.append(Paragraph(title, S["slide_title"]))
    story.append(Paragraph(subtitle, S["slide_subtitle"]))

    style_map = {
        "cyan": "div_section_head",
        "purple": "div_section_head_purple",
        "emerald": "div_section_head_emerald",
        "amber": "div_section_head_amber",
    }
    h_style = style_map.get(badge_color, "div_section_head")

    # Left content: Structured text
    left_flow = []
    for sec_title, sec_body in sections:
        left_flow.append(Paragraph(sec_title, S[h_style]))
        left_flow.append(Paragraph(sec_body, S["div_body"]))
        left_flow.append(Spacer(1, 1.5 * mm))

    left_table = Table([[left_flow]], colWidths=[130 * mm], style=[
        ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
        ("BOX", (0, 0), (-1, -1), 0.7, BORDER_LIGHT),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ])

    # Right content: Diagram image + caption
    diag_path = str(ASSETS_DIR / diagram_name)
    img_widget = RLImage(diag_path, width=128 * mm, height=88 * mm)
    cap_widget = Paragraph(f"<b>Grafica esplicativa:</b> {caption_text}", S["caption"])

    right_flow = [img_widget, Spacer(1, 1.5 * mm), cap_widget]
    right_table = Table([[right_flow]], colWidths=[131 * mm], style=[
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ])

    # Two columns side by side
    row = Table([[left_table, right_table]], colWidths=[133 * mm, 133 * mm], style=[
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ])

    story.append(row)
    story.append(PageBreak())


def build_pdf():
    # Ensure diagrams exist
    generate_all()

    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=PAGE,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=11 * mm,
        bottomMargin=13 * mm,
    )
    story = []

    # =========================================================================
    # SLIDE 1: COVER (Dark Theme)
    # =========================================================================
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("HYPERSPACE AGI · RELEASE 1.05 · GUIDA DIVULGATIVA", S["cover_kicker"]))
    story.append(Paragraph("HyperSpace AGI 1.05", S["cover_title"]))
    story.append(
        Paragraph(
            "L'Intelligenza Artificiale che Lavora Davvero: Dai Chatbot ai Sistemi Operativi per Agenti Autonomi Governative",
            S["cover_subtitle"],
        )
    )

    # Hero diagram
    hero_path = str(ASSETS_DIR / "diagram_01_cover.png")
    story.append(RLImage(hero_path, width=255 * mm, height=92 * mm))
    story.append(Spacer(1, 3 * mm))

    tags = [
        "Zero Allucinazioni Applicate",
        "Stanza Ermetica (Sandbox)",
        "Memoria & Sogni Notturni",
        "100% Locale e Privato",
        "Video & Visione Neurale",
        "Oltre 2.300 Test di Sicurezza",
    ]
    tag_cells = [[
        Paragraph(f"<b>✓ {tag}</b>", S["cover_tag"]) for tag in tags[:3]
    ], [
        Paragraph(f"<b>✓ {tag}</b>", S["cover_tag"]) for tag in tags[3:]
    ]]
    story.append(Table(tag_cells, colWidths=[85 * mm, 85 * mm, 85 * mm], style=[
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    story.append(PageBreak())

    # =========================================================================
    # SLIDE 2: IL NUOVO PARADIGMA
    # =========================================================================
    make_divulgative_slide(
        story,
        "01 · Il Nuovo Paradigma",
        "Oltre i Chatbot: Perché serve un Runtime Governato?",
        "I modelli linguistici sono brillanti ma caotici. HyperSpace è il telaio che li rende sicuri per il mondo reale.",
        [
            (
                "L'Intuizione Chiave",
                "Un'AI lasciata libera in chat è come un'automobile potente senza freni: può generare idee brillanti, ma se le dai accesso al computer rischia di cancellare file per errore, inventare fatti inesistenti o bloccarsi in loop infiniti consumando risorse.",
            ),
            (
                "Come Cambia Tutto con HyperSpace",
                "HyperSpace non lascia mai l'AI agire direttamente sul tuo computer. Costruisce una <b>torre di controllo</b> (Control Plane) e una <b>stanza ermetica</b>: ogni compito ha regole rigide, permessi espliciti e un budget massimo prefissato.",
            ),
            (
                "Il Tuo Vantaggio Diretto",
                "Ottieni tutta la potenza operativa dell'AI per automatizzare il lavoro reale, ma con la certezza matematica che nessun dato sensibile verrà corrotto e nessun codice verrà applicato senza la tua esplicita autorizzazione.",
            ),
        ],
        "diagram_02_paradigma.png",
        "Confronto tra il modello caotico convenzionale e il runtime sicuro governato di HyperSpace 1.05.",
        badge_color="purple",
    )

    # =========================================================================
    # SLIDE 3: MISSION CONTROL
    # =========================================================================
    make_divulgative_slide(
        story,
        "02 · Orchestrazione Intelligente",
        "Mission Control: Il Direttore d'Orchestra dell'AI",
        "Come trasformare un grande obiettivo complesso in una serie ordinata di piccoli compiti certi e verificabili.",
        [
            (
                "Il Problema dei Compiti Grandi",
                "Se chiedi a un normale assistente AI: <i>'Analizza questo progetto, scrivi il programma, fai i test e crea un PDF'</i>, si distrae, salta passaggi o dichiara falsamente di aver finito.",
            ),
            (
                "Il Principio del DAG Bounded",
                "Mission Control applica il principio del <i>Divide et Impera</i>: scompone l'obiettivo in un albero ordinato di compiti (DAG). Assegna ciascun compito a un ruolo specialistico (l'Analista legge solo, il Coder programma in sandbox, il Verificatore controlla).",
            ),
            (
                "Garanzia di Terminazione (Stop ai Loop)",
                "Ogni missione ha tetti massimi invalicabili su passi totali, tempo e token. Se un compito incontra un vicolo cieco, non continua a girare a vuoto: si arresta in modo ordinato, spiega il motivo e cerca una via alternativa.",
            ),
        ],
        "diagram_03_mission_control.png",
        "Struttura del grafo di compiti ordinati (DAG) con ruoli distinti e tetti di budget operativi.",
        badge_color="cyan",
    )

    # =========================================================================
    # SLIDE 4: CODE SANDBOX & QUALITY GATES
    # =========================================================================
    make_divulgative_slide(
        story,
        "03 · Sicurezza & Esecuzione Isolata",
        "La Stanza Ermetica: Nessun Codice Tocca il Tuo Computer",
        "Sandbox usa-e-getta e controlli oggettivi indipendenti: ci fidiamo solo delle prove tangibili, non delle parole dell'AI.",
        [
            (
                "Il Rifiuto dell'Auto-Certificazione",
                "Spesso i modelli linguistici rispondono: <i>'Ho eseguito tutto con successo!'</i> anche se il file è corrotto o non è mai stato creato. HyperSpace rifiuta categoricamente l'auto-certificazione dell'AI.",
            ),
            (
                "La Stanza Ermetica (Sandbox Docker)",
                "L'agente lavora esclusivamente all'interno di una sandbox virtuale isolata usa-e-getta. Se genera codice sbagliato o comandi errati, si rompe solo l'ambiente virtuale temporaneo: il tuo computer host rimane intoccabile.",
            ),
            (
                "I 3 Cancelli di Controllo Oggettivi (Gate)",
                "Prima di mostrarti il risultato, intervengono validatori matematici esterni: ispezionano i byte effettivi del file (es. %PDF reale), controllano la sintassi del codice e pretendono il superamento al 100% dei test automatici.",
            ),
        ],
        "diagram_04_sandbox_gates.png",
        "Isolamento ermetico tra host e sandbox con i tre cancelli di controllo algoritmici indipendenti.",
        badge_color="emerald",
    )

    # =========================================================================
    # SLIDE 5: TOOL & SKILL FORGE
    # =========================================================================
    make_divulgative_slide(
        story,
        "04 · Il Laboratorio delle Abilità",
        "Forge & Hook Adattivi: Come l'AI Impara Nuovi Tool",
        "Estensione dinamica delle capacità con blocco di sicurezza crittografico e attivazione automatica al momento giusto.",
        [
            (
                "Perché Creare Nuove Abilità?",
                "Un sistema bloccato su strumenti fissi invecchia subito. HyperSpace permette agli agenti di sintetizzare nuove abilità (skill) e strumenti personalizzati quando affrontano problemi inediti.",
            ),
            (
                "Il Blocco di Sicurezza a Due Fasi",
                "Per evitare che l'AI esegua codice non autorizzato, ogni nuova abilità nasce come una <b>Bozza Inerte</b>. Rimane sigillata con un lucchetto finché non viene ispezionata e firmata con un'impronta crittografica <b>SHA-256</b>.",
            ),
            (
                "Iniezione Intelligente 'before_context'",
                "Non intasiamo la memoria con decine di istruzioni inutili: un selettore automatico legge le parole chiave dell'utente (es. 'sicurezza', 'PDF', 'URL') e carica al massimo 2 abilità necessarie (tetto rigido di 24 KB), evitando sprechi di token.",
            ),
        ],
        "diagram_05_forge_hooks.png",
        "Ciclo di vita della skill dalla bozza alla firma crittografica, con iniezione contestuale intelligente.",
        badge_color="amber",
    )

    # =========================================================================
    # SLIDE 6: HERMES MEMORY & DREAM LOOP
    # =========================================================================
    make_divulgative_slide(
        story,
        "05 · Memoria Viva & Riflessione",
        "Memoria Hermes & Sogni Notturni: Il Sonno REM dell'AI",
        "Come HyperSpace ricorda tutto quello che fai e riflette durante i momenti di riposo per trovare nuove intuizioni.",
        [
            (
                "Superare l'Amnesia dei Chatbot",
                "I normali chatbot dimenticano tutto non appena chiudi la finestra. HyperSpace utilizza Hermes come memoria unica duratura (database SQLite FTS5 ultra-veloce e file Markdown canonici).",
            ),
            (
                "Il Sonno REM dell'AI (Dream Loop)",
                "Cosa fa il sistema quando non stai lavorando o durante la notte? Entra in fase di <b>Sogno</b> (idle-only): rilegge le memorie recenti, trova collegamenti inaspettati tra compiti diversi e prepara sintesi utili per il giorno dopo.",
            ),
            (
                "Quarantena delle Ipotesi & Preemption",
                "Le intuizioni notturne restano 'ipotesi': NON modificano la memoria ufficiale finché tu non le confermi. E se scrivi un messaggio mentre l'AI sta sognando? Il sogno si ferma all'istante in pochi millisecondi!",
            ),
        ],
        "diagram_06_hermes_dreams.png",
        "Architettura della memoria Hermes e ciclo notturno di riflessione autonoma con quarantena delle ipotesi.",
        badge_color="purple",
    )

    # =========================================================================
    # SLIDE 7: TAILSCALE MESH
    # =========================================================================
    make_divulgative_slide(
        story,
        "06 · Rete Distribuita & Calcolo Ibrido",
        "La Rete Nervosa Privata: Più Computer, Una Sola Mente",
        "Collega Mac, PC Windows, server Linux e browser in una rete mesh cifrata privata a zero fuga di dati.",
        [
            (
                "Il Valore dell'Hardware che Già Possiedi",
                "Invece di pagare costosi abbonamenti cloud per ogni singolo modello, HyperSpace unisce tutti i tuoi computer in un'unica rete neurale privata coordinata dal Control Plane.",
            ),
            (
                "Specializzazione Hardware Dinamica",
                "Ciascun dispositivo fa ciò in cui eccelle: il <b>Mac Studio</b> usa Neural Engine e Metal per video e audio ultra-veloci; il <b>PC Windows</b> usa la GPU RTX per la grafica pesante; il <b>Server Linux</b> esegue modelli linguistici aperti con Ollama a zero costi.",
            ),
            (
                "Privacy Totale via Tailscale Mesh",
                "Tutti i nodi comunicano tra loro con una VPN peer-to-peer crittografata (WireGuard). Non serve aprire porte sul router aziendale e nessun dato transita su server cloud di terze parti.",
            ),
        ],
        "diagram_07_mesh_network.png",
        "Mappa della rete mesh distribuita: collaborazione eterogenea sicura tra Mac, Windows e Linux.",
        badge_color="cyan",
    )

    # =========================================================================
    # SLIDE 8: REEL EDITOR & APPLE VISION
    # =========================================================================
    make_divulgative_slide(
        story,
        "07 · Produzione Video Intelligente",
        "Reel Editor: Il Regista Virtuale con Occhi Apple Vision",
        "Pipeline automatizzata per video verticali 9:16 a tempo di musica, con segmentazione neurale nativa su Mac.",
        [
            (
                "L'Esigenza del Contenuto Verticale",
                "Creare video di qualità per TikTok, Instagram Reels e YouTube Shorts richiede ore di lavoro manuale: allineare i tagli alla musica, isolare le persone e sincronizzare i testi.",
            ),
            (
                "Visione Neurale Swift su macOS",
                "Grazie a un modulo nativo in Swift (<code>person_mask.swift</code>) integrato con Apple Vision, il Mac isola la figura umana in tempo reale <b>senza green screen</b>: permette di posizionare titoli karaoke (rame/avorio) ed effetti particellari <i>dietro</i> al soggetto!",
            ),
            (
                "Il Reel Giornaliero in Coda di Revisione",
                "Un demone programmato (LaunchAgent) analizza il ritmo musicale con Beat Detection e monta un nuovo video ogni mattina alle 09:00: il video ti aspetta nella cartella di revisione, pronto per il tuo ok prima della pubblicazione.",
            ),
        ],
        "diagram_08_reel_vision.png",
        "Composizione video a strati 9:16: traccia audio a tempo, testi karaoke e persona isolata via Apple Vision.",
        badge_color="amber",
    )

    # =========================================================================
    # SLIDE 9: HYPERSPACE UFFICIO
    # =========================================================================
    make_divulgative_slide(
        story,
        "08 · Automazione Documentale",
        "HyperSpace Ufficio: AnyDoc, OCR Illimitato e Connettori M365",
        "Dalle scansioni cartacee all'integrazione fluida con Microsoft 365, Google Workspace e OnlyOffice a zero fughe di dati.",
        [
            (
                "Il Labirinto Documentale",
                "Gli uffici moderni sono sommersi da contratti cartacei scansionati, PDF complessi con tabelle intricate e documenti sparsi in decine di cartelle.",
            ),
            (
                "AnyDoc & Unlimited OCR Offline",
                "HyperSpace converte qualsiasi file (PDF, Word, fogli di calcolo, scansioni cartacee) in testo pulito Markdown strutturato. L'OCR gira interamente in locale: non paghi nulla a consumo e non invii documenti riservati a terzi.",
            ),
            (
                "Connettori Sicuri Zero-Leak",
                "Integrazione diretta con <b>Microsoft 365</b>, <b>Google Workspace</b>, <b>GitHub</b> e OnlyOffice per lavorare sui documenti direttamente nel browser. Tutte le credenziali e password vengono cancellate e redatte automaticamente da ogni traccia di log.",
            ),
        ],
        "diagram_09_ufficio_connectors.png",
        "Il flusso documentale: dall'ingestion universale alla collaborazione protetta con Microsoft 365.",
        badge_color="emerald",
    )

    # =========================================================================
    # SLIDE 10: MULTI-AGENT COEXISTENCE
    # =========================================================================
    make_divulgative_slide(
        story,
        "09 · Ingegneria del Software & Metodo",
        "La Torre di Controllo: Più Agenti AI sullo Stesso Progetto",
        "Come molteplici agenti AI collaborano sullo stesso codice senza sovrascriversi o entrare in conflitto.",
        [
            (
                "La Sfida della Convivenza",
                "Cosa succede quando più programmatori AI operano sullo stesso computer? Senza regole, si sovrascrivono il codice a vicenda, cancellano modifiche recenti e creano caos nel repository.",
            ),
            (
                "La Costituzione e il Diario di Bordo",
                "In HyperSpace vigono due regole ferree: <code>AGENTS.md</code> stabilisce esattamente chi può toccare cosa; <code>AGENT-LOG.md</code> è un diario di bordo in cui ogni agente legge cosa è stato fatto prima di agire e firma il proprio operato alla fine.",
            ),
            (
                "Lo Scudo dei 2.300 Test Automatici",
                "Una gigantesca suite di oltre 2.315 test automatici vigila continuamente sull'integrità del sistema: se un agente commette un errore, i test lo bloccano all'istante prima che il danno si propaghi.",
            ),
        ],
        "diagram_10_multi_agent.png",
        "Collaborazione multi-agente: Cline, Codex, Claude Code e Antigravity coordinati da regole e test continui.",
        badge_color="purple",
    )

    # =========================================================================
    # SLIDE 11: I 4 PROFILI COMMERCIALI
    # =========================================================================
    make_divulgative_slide(
        story,
        "10 · Applicazioni & Mercato",
        "Quattro Soluzioni ad Alto Valore Pronte all'Uso",
        "Dalla teoria al fatturato immediato: come HyperSpace si trasforma in prodotto per aziende, sviluppatori, uffici e creator.",
        [
            (
                "1. Enterprise Local (Privacy Assoluta)",
                "Per banche, sanità, studi legali e pubblica amministrazione: agenti intelligenti che operano su dati riservati on-premise, con zero fuga di dati all'estero e audit crittografico certificato.",
            ),
            (
                "2. Agent Operations Platform (Per Dev Team)",
                "Per software house e team tecnologici: risoluzione autonoma di ticket, bug fixing e refactoring in sandbox usa-e-getta senza rischi per la produzione.",
            ),
            (
                "3. HyperSpace Ufficio & 4. Multimedia",
                "Per studi professionali (gestione contratti, OCR illimitato, OnlyOffice) e per media house/creator (generazione video ritmici automatici 9:16 e personaggi virtuali con stile consistente).",
            ),
        ],
        "diagram_11_business_quadrants.png",
        "I quattro quadranti commerciali: quattro mercati verticali serviti da un unico motore operativo solido.",
        badge_color="cyan",
    )

    # =========================================================================
    # SLIDE 12: CONCLUSIONE & SINTESI (Dark Theme)
    # =========================================================================
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("HYPERSPACE AGI 1.05  ·  SINTESI ESECUTIVA & VISIONE", S["cover_kicker"]))
    story.append(Paragraph("L'Intelligenza Artificiale che Lavora per Davvero", S["cover_title"]))
    story.append(
        Paragraph(
            "HyperSpace 1.05 non è una promessa astratta né una chat superficiale: è un runtime solido, sicuro e pronto all'uso aziendale.",
            S["cover_subtitle"],
        )
    )

    # Summary visual infographic
    sum_path = str(ASSETS_DIR / "diagram_12_summary_vision.png")
    story.append(RLImage(sum_path, width=255 * mm, height=88 * mm))
    story.append(Spacer(1, 3 * mm))
    story.append(
        Paragraph(
            "<b>HyperSpace AGI 1.05</b>  ·  Documentazione completa in <code>docs/</code>  ·  Repository: <code>/Users/opo/hyperspace-agi-1.04</code>",
            S["cover_footer"],
        )
    )

    # Multi-page build with frame callbacks
    def page_decorator(canvas, document):
        if document.page in (1, 12):
            draw_dark_frame(canvas, document)
        else:
            draw_light_frame(canvas, document)

    doc.build(story, onFirstPage=page_decorator, onLaterPages=page_decorator)
    print(f"Divulgative & Visual presentation generated at {OUT}")


if __name__ == "__main__":
    build_pdf()
