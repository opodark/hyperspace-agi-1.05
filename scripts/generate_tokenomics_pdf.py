#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Genera il documento PDF tecnico formattato: 'HyperSpace Tokenomics ($HYPER) & pump.fun Architecture'.

Layout A4 professionale e tipograficamente curato con:
- Sintesi operativa del modello economico Proof-of-Useful-Work (PoUW)
- Parametri di emissione, supply pump.fun (Solana SPL) e allocazione pool
- Tabelle delle ricompense (Onboarding, Inferenza modelli leggeri/medi/pesanti, Uptime)
- Integrazione crittografica dei wallet Phantom/Solflare e calcolo dello snapshot per l'airdrop
- Roadmap a 4 fasi verso il lancio decentralizzato
- Numerazione pagine 'Pagina X di Y' e header/footer eleganti.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

PDF_OUT = ROOT / "docs" / "hyperspace-tokenomics.pdf"

# Palette Colori Cyberpunk / Corporate Executive
COLOR_PRIMARY = colors.HexColor("#0F172A")    # Deep Navy Slate
COLOR_SECONDARY = colors.HexColor("#334155")  # Slate Gray
COLOR_ACCENT = colors.HexColor("#4F46E5")     # Cyber Indigo
COLOR_ACCENT_BG = colors.HexColor("#EEF2FF")  # Indigo Light Tint
COLOR_BG_LIGHT = colors.HexColor("#F8FAFC")   # Light Slate Bg
COLOR_BORDER = colors.HexColor("#CBD5E1")     # Light Border
COLOR_EMERALD = colors.HexColor("#059669")    # Success / Money
COLOR_EMERALD_BG = colors.HexColor("#ECFDF5") # Success Light Tint
COLOR_AMBER = colors.HexColor("#D97706")      # Warning / Golden
COLOR_TEXT = colors.HexColor("#1E293B")       # Dark Charcoal
COLOR_MUTED = colors.HexColor("#64748B")      # Muted Gray
COLOR_SOLANA = colors.HexColor("#9945FF")     # Solana Purple
COLOR_SOLANA_BG = colors.HexColor("#F3E8FF")  # Solana Light Tint


class NumberedCanvas(canvas.Canvas):
    """Canvas a due passaggi per calcolare e disegnare 'Pagina X di Y' ed header/footer."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, total_pages: int):
        self.saveState()
        w, h = A4

        # Header superiore (dalla pagina 2 in poi)
        if self._pageNumber > 1:
            self.setFont("Helvetica", 8)
            self.setFillColor(COLOR_MUTED)
            self.drawString(18 * mm, h - 12 * mm, "00MESH — Tokenomics & Proof-of-Useful-Work Architecture")
            self.drawRightString(w - 18 * mm, h - 12 * mm, "Whitepaper Ufficiale • pump.fun Standard ($00MESH)")
            self.setStrokeColor(COLOR_BORDER)
            self.setLineWidth(0.5)
            self.line(18 * mm, h - 14 * mm, w - 18 * mm, h - 14 * mm)

        # Footer inferiore (tutte le pagine)
        self.setStrokeColor(COLOR_BORDER)
        self.setLineWidth(0.5)
        self.line(18 * mm, 14 * mm, w - 18 * mm, 14 * mm)

        self.setFont("Helvetica", 8)
        self.setFillColor(COLOR_MUTED)
        self.drawString(18 * mm, 10 * mm, "00MESH Network by ZeroZero Computer — https://www.zerozerocomputer.it")
        page_str = f"Pagina {self._pageNumber} di {total_pages}"
        self.drawRightString(w - 18 * mm, 10 * mm, page_str)

        self.restoreState()


def create_tokenomics_pdf(output_path: Path):
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()

    # Stili tipografici personalizzati
    style_title = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=21,
        leading=25,
        textColor=COLOR_PRIMARY,
        spaceAfter=4,
    )
    style_subtitle = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=COLOR_ACCENT,
        spaceAfter=12,
    )
    style_h1 = ParagraphStyle(
        "SectionH1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=COLOR_PRIMARY,
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True,
    )
    style_h2 = ParagraphStyle(
        "SectionH2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=COLOR_SECONDARY,
        spaceBefore=7,
        spaceAfter=3,
        keepWithNext=True,
    )
    style_body = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=COLOR_TEXT,
        spaceAfter=6,
    )
    style_body_bold = ParagraphStyle(
        "BodyDarkBold",
        parent=style_body,
        fontName="Helvetica-Bold",
    )
    style_callout = ParagraphStyle(
        "CalloutText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12.5,
        textColor=COLOR_PRIMARY,
    )
    style_table_header = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
    )
    style_table_cell = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=COLOR_TEXT,
    )
    style_table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=style_table_cell,
        fontName="Helvetica-Bold",
    )
    style_code = ParagraphStyle(
        "CodeText",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=7.5,
        leading=10,
        textColor=COLOR_PRIMARY,
    )

    story = []
    w_content = A4[0] - 36 * mm

    # ═════════════════════════════════════════════════════════════════════════
    # PAGINA 1: EXECUTIVE SUMMARY, METRICHE CHIAVE E MODELLO ECONOMICO
    # ═════════════════════════════════════════════════════════════════════════

    story.append(Paragraph("00MESH Network Tokenomics ($00MESH)", style_title))
    story.append(Paragraph("Architettura Proof-of-Useful-Work (PoUW) • Standard Solana SPL • Lancio pump.fun", style_subtitle))
    story.append(HRFlowable(width="100%", thickness=1.5, color=COLOR_ACCENT, spaceBefore=0, spaceAfter=8))

    # Box Executive Callout
    box_summary_content = [
        Paragraph(
            "<b>Sintesi Esecutiva:</b> 00MESH (sviluppato da ZeroZero Computer) supera il paradigma dei token speculativi introducendo una "
            "<b>Proof-of-Useful-Work (PoUW)</b> reale. Chi possiede un computer (GPU consumer NVIDIA RTX, Apple Silicon o PC Linux) "
            "può federarlo nella mesh P2P sovereign ed eseguire compiti di inferenza AI distribuiti. "
            "Ogni task completato genera punti computazionali proporzionali alla potenza erogata, "
            "registrati in modo crittografico nel ledger e convertibili in token SPL su <b>pump.fun (Solana)</b>.",
            style_callout,
        )
    ]
    box_table = Table([[box_summary_content]], colWidths=[w_content])
    box_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_ACCENT_BG),
        ("BOX", (0, 0), (-1, -1), 1, COLOR_ACCENT),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(box_table)
    story.append(Spacer(1, 8))

    # Sezione Specifiche Token
    story.append(Paragraph("1. Specifiche del Token & Standard Tecnico", style_h1))

    specs_data = [
        [Paragraph("Parametro", style_table_header), Paragraph("Specifiche Ufficiali", style_table_header), Paragraph("Rilevanza Architetturale", style_table_header)],
        [Paragraph("Nome del Token", style_table_cell_bold), Paragraph("00MESH Network Token", style_table_cell), Paragraph("Identità della mesh di calcolo sovereign ZeroZero Computer", style_table_cell)],
        [Paragraph("Ticker / Simbolo", style_table_cell_bold), Paragraph("<b>$00MESH</b>", style_table_cell), Paragraph("Token di utilità e settlement di calcolo su Solana", style_table_cell)],
        [Paragraph("Network / Blockchain", style_table_cell_bold), Paragraph("Solana SPL", style_table_cell), Paragraph("Transazioni sub-second, fee microscopiche ($0.0002)", style_table_cell)],
        [Paragraph("DEX / Launchpad", style_table_cell_bold), Paragraph("<b>pump.fun</b>", style_table_cell), Paragraph("Bonding curve trasparente, liquidità e fair launch", style_table_cell)],
        [Paragraph("Supply Totale Fissa", style_table_cell_bold), Paragraph("<b>1.000.000.000 $00MESH</b>", style_table_cell), Paragraph("1 Miliardo standard pump.fun (nessuna inflazione arbitraria)", style_table_cell)],
        [Paragraph("Community Mining Pool", style_table_cell_bold), Paragraph("<b>200.000.000 $00MESH (20%)</b>", style_table_cell), Paragraph("Riservato esclusivamente ai nodi minatori della mesh", style_table_cell)],
        [Paragraph("Decimali Solana", style_table_cell_bold), Paragraph("6 decimali", style_table_cell), Paragraph("Standard nativo pump.fun / Raydium", style_table_cell)],
    ]
    table_specs = Table(specs_data, colWidths=[42 * mm, 62 * mm, 70 * mm])
    table_specs.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [COLOR_BG_LIGHT, colors.white]),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table_specs)
    story.append(Spacer(1, 10))

    # Sezione Allocazione Supply (Tokenomics Breakdown)
    story.append(Paragraph("2. Allocazione della Supply Totale (1.000.000.000 $00MESH)", style_h1))

    alloc_data = [
        [Paragraph("Allocazione", style_table_header), Paragraph("Token ($00MESH)", style_table_header), Paragraph("Quota %", style_table_header), Paragraph("Finalità e Vincoli", style_table_header)],
        [
            Paragraph("<b>Bonding Curve & Liquidity</b>", style_table_cell_bold),
            Paragraph("700.000.000", style_table_cell),
            Paragraph("<b>70.0%</b>", style_table_cell_bold),
            Paragraph("Fornita alla bonding curve pump.fun e migrazione automatica a Raydium al completamento.", style_table_cell)
        ],
        [
            Paragraph("<b>Mesh Community Mining Pool</b>", style_table_cell_bold),
            Paragraph("200.000.000", style_table_cell),
            Paragraph("<b>20.0%</b>", style_table_cell_bold),
            Paragraph("Distribuito esclusivamente tramite Proof-of-Useful-Work (calcolo nodi, uptime, inferenze).", style_table_cell)
        ],
        [
            Paragraph("<b>Core Dev & Ecosystem Reserve</b>", style_table_cell_bold),
            Paragraph("100.000.000", style_table_cell),
            Paragraph("<b>10.0%</b>", style_table_cell_bold),
            Paragraph("Sviluppo runtime, bridge hardware, partnership infrastrutturali e sicurezza.", style_table_cell)
        ],
    ]
    table_alloc = Table(alloc_data, colWidths=[45 * mm, 32 * mm, 22 * mm, 75 * mm])
    table_alloc.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_SECONDARY),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [COLOR_EMERALD_BG, colors.white, COLOR_BG_LIGHT]),
        ("PADDING", (0, 0), (-1, -1), 4.5),
    ]))
    story.append(table_alloc)

    # ═════════════════════════════════════════════════════════════════════════
    # PAGINA 2: REWARD MECHANICS, MATEMATICA DI CALCOLO E PROOF-OF-WORK
    # ═════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())

    story.append(Paragraph("3. Meccanica dei Reward e Proof-of-Useful-Work", style_h1))
    story.append(Paragraph(
        "Il modello economico premia i nodi secondo tre vettori complementari: <b>Onboarding</b>, "
        "<b>Potenza di Calcolo Erogata</b> e <b>Disponibilità Temporale</b>.",
        style_body
    ))

    # Vettore 1: Onboarding
    story.append(Paragraph("A. Welcome Grant di Onboarding (Node Join)", style_h2))
    story.append(Paragraph(
        "Quando un nuovo nodo effettua il pairing crittografico nella mesh (annunciando il proprio endpoint e la chiave pubblica ECDSA o collegando un wallet Solana), "
        "riceve un credito iniziale di benvenuto pari a <b>+50.0 $00MESH</b>. L'accredito è registrato in modo idempotente "
        "nel database del Control Plane (`shared/db.py`) per impedire registrazioni duplicate dallo stesso `node_id`.",
        style_body
    ))

    # Vettore 2: Task di Inferenza
    story.append(Paragraph("B. Proof-of-Useful-Work (Inferenza & Calcolo AI)", style_h2))
    story.append(Paragraph(
        "Ogni volta che un nodo completa con successo un task di inferenza (instradato dal Control Plane via Laya Engine), "
        "matura una ricompensa calcolata in base alla complessità del modello e al tempo di elaborazione:",
        style_body
    ))

    formula_text = [
        Paragraph(
            "<b>Formula Matematica del Reward Task:</b><br/>"
            "<code>Reward = (Base_Reward × Moltiplicatore_Modello) + Bonus_Durata + Bonus_Token</code><br/>"
            "• <i>Base_Reward</i>: 2.0 $00MESH fisso per esecuzione completata con successo (`status = 'done'`).<br/>"
            "• <i>Bonus_Durata</i>: +0.10 $00MESH per ogni secondo oltre i 5s (fino a max +2.0 $00MESH).<br/>"
            "• <i>Bonus_Token</i>: bonus per contesti estesi (>500 token generati).",
            style_callout
        )
    ]
    box_formula = Table([[formula_text]], colWidths=[w_content])
    box_formula.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_LIGHT),
        ("BOX", (0, 0), (-1, -1), 1, COLOR_SECONDARY),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(box_formula)
    story.append(Spacer(1, 6))

    tiers_data = [
        [Paragraph("Categoria Modello", style_table_header), Paragraph("Esempi Concreti", style_table_header), Paragraph("Moltiplicatore", style_table_header), Paragraph("Reward Base", style_table_header), Paragraph("Profilo Hardware Tipico", style_table_header)],
        [
            Paragraph("<b>Modelli Leggeri</b> (&le; 4B)", style_table_cell_bold),
            Paragraph("<code>qwen3.5:4b</code>, embeddings", style_table_cell),
            Paragraph("<b>1.0x</b>", style_table_cell),
            Paragraph("<b>2.0 $00MESH</b>", style_table_cell_bold),
            Paragraph("Mac mini, CPU/iGPU, laptop base", style_table_cell)
        ],
        [
            Paragraph("<b>Modelli Medi</b> (7B - 9B)", style_table_cell_bold),
            Paragraph("<code>qwen3:8b</code>, <code>granite3.3:8b</code>", style_table_cell),
            Paragraph("<b>1.5x</b>", style_table_cell),
            Paragraph("<b>3.0 $00MESH</b>", style_table_cell_bold),
            Paragraph("GPU laptop 6-8 GB, Mac M1/M2/M3", style_table_cell)
        ],
        [
            Paragraph("<b>Avanzati / MoE / Ternari</b> (&ge; 14B)", style_table_cell_bold),
            Paragraph("<code>Ternary-Bonsai-2-27B</code>, MoE", style_table_cell),
            Paragraph("<b>3.0x</b>", style_table_cell),
            Paragraph("<b>6.0 $00MESH</b>", style_table_cell_bold),
            Paragraph("RTX 3070 8GB (Prism ML), Mac 16GB+", style_table_cell)
        ],
    ]
    table_tiers = Table(tiers_data, colWidths=[42 * mm, 45 * mm, 22 * mm, 25 * mm, 40 * mm])
    table_tiers.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT, COLOR_EMERALD_BG]),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table_tiers)
    story.append(Spacer(1, 8))

    # Vettore 3: Uptime
    story.append(Paragraph("C. Proof-of-Availability (Uptime & Canale E2EE Mantenuto)", style_h2))
    story.append(Paragraph(
        "I nodi che mantengono un uptime verificato ricevono <b>5.0 $00MESH per ogni ora</b> di connessione attiva. "
        "Il Control Plane interroga la telemetria periodica (`/mesh/sync/status`); se il canale sicuro `secp256k1` + `AES-256-GCM` "
        "rimane responsivo e alimentato (rete fissa AC o profilo batteria optimal), il saldo viene incrementato automaticamente.",
        style_body
    ))

    # ═════════════════════════════════════════════════════════════════════════
    # PAGINA 3: INTEGRAZIONE SOLANA, SNAPSHOT PUMP.FUN E ROADMAP
    # ═════════════════════════════════════════════════════════════════════════
    story.append(PageBreak())

    story.append(Paragraph("4. Collegamento Wallet Solana & pump.fun Snapshot", style_h1))
    story.append(Paragraph(
        "I nodi accumulano punti computazionali $00MESH nel ledger SQLite del Control Plane. Per consentire agli operatori dei nodi di "
        "ricevere i token reali su Solana al momento del lancio su pump.fun, è stato predisposto il sistema di binding crittografico.",
        style_body
    ))

    sol_box_content = [
        Paragraph(
            "<b>Workflow Operativo per i Nodi della Mesh:</b><br/>"
            "<b>1. Esegui il Nodo:</b> Avvia il nodo via Docker Compose, browser web o su Windows con <code>scripts/start_bonsai_daemon.ps1</code>.<br/>"
            "<b>2. Eroga Calcolo Sovrano:</b> Il nodo risponde ai prompt, esegue inferenze MoE/ComfyUI e accumula punti nel database.<br/>"
            "<b>3. Collega il Wallet Solana:</b> L'operatore associa il proprio indirizzo Phantom o Solflare in Base58 via CLI o interfaccia Web:<br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<code>python scripts/tokenomics_cli.py link-wallet &lt;node_id&gt; &lt;indirizzo_solana&gt;</code><br/>"
            "<b>4. Esportazione Snapshot:</b> Al lancio su pump.fun, 00MESH calcola lo snapshot di airdrop proporzionale ai punti minati.",
            style_callout
        )
    ]
    table_sol_box = Table([[sol_box_content]], colWidths=[w_content])
    table_sol_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_SOLANA_BG),
        ("BOX", (0, 0), (-1, -1), 1, COLOR_SOLANA),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(table_sol_box)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Formula di Calcolo Airdrop su pump.fun:", style_h2))
    story.append(Paragraph(
        "$$\\text{Token SPL Assegnati al Nodo} = \\left( \\frac{\\text{Punti } \\$00MESH \\text{ Minati dal Nodo}}{\\text{Totale Punti Minati da Tutta la Mesh}} \\right) \\times 200.000.000 \\text{ \\$00MESH}$$",
        style_body
    ))

    # Tabella Snapshot Reale Esempio
    story.append(Paragraph("Esempio di Snapshot Generato (`scripts/tokenomics_cli.py snapshot`):", style_h2))
    snap_data = [
        [Paragraph("Node ID", style_table_header), Paragraph("Hardware / Ruolo", style_table_header), Paragraph("Indirizzo Solana Registrato", style_table_header), Paragraph("Quota %", style_table_header), Paragraph("Claimable SPL ($00MESH)", style_table_header)],
        [
            Paragraph("<code>node-hp-omen-16</code>", style_table_cell_bold),
            Paragraph("RTX 3070 8GB • Bonsai 2", style_table_cell),
            Paragraph("<code>7xKXtg2CW8...uJosgAsU</code>", style_table_cell),
            Paragraph("<b>65.40%</b>", style_table_cell_bold),
            Paragraph("<b>130.800.000 $00MESH</b>", style_table_cell_bold)
        ],
        [
            Paragraph("<code>node-macbook-pro</code>", style_table_cell_bold),
            Paragraph("Apple M-Series • Qwen3 8B", style_table_cell),
            Paragraph("<code>EPjFWdd5Au...ZwyTDt1v</code>", style_table_cell),
            Paragraph("<b>34.60%</b>", style_table_cell_bold),
            Paragraph("<b>69.200.000 $00MESH</b>", style_table_cell_bold)
        ],
    ]
    table_snap = Table(snap_data, colWidths=[40 * mm, 42 * mm, 42 * mm, 20 * mm, 30 * mm])
    table_snap.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT]),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table_snap)
    story.append(Spacer(1, 8))

    # Roadmap a 4 Fasi
    story.append(Paragraph("5. Roadmap di Implementazione & Lancio", style_h1))

    roadmap_data = [
        [Paragraph("Fase", style_table_header), Paragraph("Milestone", style_table_header), Paragraph("Stato", style_table_header), Paragraph("Obiettivi Operativi", style_table_header)],
        [
            Paragraph("<b>Fase 1</b>", style_table_cell_bold),
            Paragraph("Ledger PoUW & Rotte Web", style_table_cell_bold),
            Paragraph("<font color='#059669'><b>COMPLETATO ✅</b></font>", style_table_cell),
            Paragraph("Tabelle SQLite, modulo <code>shared/tokenomics.py</code>, rotte REST <code>/web/node/*</code> e CLI.", style_table_cell)
        ],
        [
            Paragraph("<b>Fase 2</b>", style_table_cell_bold),
            Paragraph("Binding Solana & Leaderboard", style_table_cell_bold),
            Paragraph("<font color='#059669'><b>ATTIVO ORA 🚀</b></font>", style_table_cell),
            Paragraph("Gli operatori collegano il wallet Phantom. Classifica pubblica live su <code>/tokenomics/leaderboard</code>.", style_table_cell)
        ],
        [
            Paragraph("<b>Fase 3</b>", style_table_cell_bold),
            Paragraph("Lancio pump.fun & Claim", style_table_cell_bold),
            Paragraph("<font color='#D97706'><b>IN PROGRAMMA ⏳</b></font>", style_table_cell),
            Paragraph("Deploy bonding curve su pump.fun e claim Merkle Tree per tutti i miner registrati.", style_table_cell)
        ],
        [
            Paragraph("<b>Fase 4</b>", style_table_cell_bold),
            Paragraph("Staking & Governance Mesh", style_table_cell_bold),
            Paragraph("<font color='#64748B'><b>FUTURO 🌐</b></font>", style_table_cell),
            Paragraph("Staking di $00MESH per priorità di routing, pagamento task agenti complessi e governance.", style_table_cell)
        ],
    ]
    table_road = Table(roadmap_data, colWidths=[20 * mm, 45 * mm, 32 * mm, 77 * mm])
    table_road.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_SECONDARY),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [COLOR_EMERALD_BG, colors.white, COLOR_BG_LIGHT, colors.white]),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table_road)
    story.append(Spacer(1, 8))

    # Sezione 6: Disclaimer Legale & MiCA
    story.append(Paragraph("6. Disclaimer Legale & Conformità Regolamentare (MiCA UE 2023/1114)", style_h1))
    disclaimer_text = [
        Paragraph(
            "<b>Avviso Legale & Trasparenza Regolamentare:</b><br/>"
            "• <i>Natura Sperimentale</i>: Il token <b>$00MESH</b> è un utility token sperimentale e un sistema di punti computazionali a supporto della ricerca e dello sviluppo di reti AI distribuite. Non costituisce strumento finanziario, investimento speculativo, quota azionaria o promessa di rendimento futuro ai sensi del Regolamento Europeo MiCA (UE 2023/1114) e della normativa Consob / TUF.<br/>"
            "• <i>Assenza di Rendimenti Garantiti</i>: L'assegnazione di punti PoUW o ricompense di uptime non rappresenta un diritto a dividendi o rendita passiva.<br/>"
            "• <i>Consulenza Legale</i>: Questo documento ha valore puramente tecnico-architetturale. Prima di effettuare qualsiasi operazione su blockchain, consultare un professionista legale qualificato.",
            style_code
        )
    ]
    box_disclaimer = Table([[disclaimer_text]], colWidths=[w_content])
    box_disclaimer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_BG_LIGHT),
        ("BOX", (0, 0), (-1, -1), 1, COLOR_SECONDARY),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(box_disclaimer)

    # Compilazione del documento
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"✅ Documento PDF generato con successo: {output_path}")


def main():
    create_tokenomics_pdf(PDF_OUT)


if __name__ == "__main__":
    main()
