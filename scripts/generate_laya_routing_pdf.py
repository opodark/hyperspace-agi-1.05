#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Genera il documento PDF tecnico formattato: 'Laya in HyperSpace & La Selezione dei Nodi'.

Imposta un layout A4 pulito, professionale e tipograficamente curato con:
- Sintesi operativa di Laya (System 1)
- Il modello di Routing a 2 Stadi (Semantico vs Hardware)
- Diagramma di architettura vettoriale
- Formula matematica dello score e breakdown delle metriche
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

PDF_OUT = ROOT / "docs" / "laya-routing-hyperspace.pdf"

# Palette Colori
COLOR_PRIMARY = colors.HexColor("#0F172A")    # Deep Slate / Navy
COLOR_SECONDARY = colors.HexColor("#334155")  # Slate Gray
COLOR_ACCENT = colors.HexColor("#4F46E5")     # Indigo
COLOR_ACCENT_BG = colors.HexColor("#EEF2FF")  # Indigo light tint
COLOR_BG_LIGHT = colors.HexColor("#F8FAFC")   # Light slate bg
COLOR_BORDER = colors.HexColor("#E2E8F0")     # Light border
COLOR_EMERALD = colors.HexColor("#059669")    # Success
COLOR_AMBER = colors.HexColor("#D97706")      # Warning/Structural
COLOR_TEXT = colors.HexColor("#1E293B")       # Main text
COLOR_MUTED = colors.HexColor("#64748B")      # Secondary text
COLOR_DARK_CARD = colors.HexColor("#1E293B")  # Dark code bg


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
            self.drawString(18 * mm, h - 12 * mm, "HyperSpace AGI — Architettura Laya & Node Routing")
            self.drawRightString(w - 18 * mm, h - 12 * mm, "Report Tecnico Operativo")
            self.setStrokeColor(COLOR_BORDER)
            self.setLineWidth(0.5)
            self.line(18 * mm, h - 14 * mm, w - 18 * mm, h - 14 * mm)

        # Footer inferiore (tutte le pagine)
        self.setStrokeColor(COLOR_BORDER)
        self.setLineWidth(0.5)
        self.line(18 * mm, 14 * mm, w - 18 * mm, 14 * mm)

        self.setFont("Helvetica", 8)
        self.setFillColor(COLOR_MUTED)
        self.drawString(18 * mm, 10 * mm, "HyperSpace 1.05 — Framework di Orchestrazione Governata")
        page_str = f"Pagina {self._pageNumber} di {total_pages}"
        self.drawRightString(w - 18 * mm, 10 * mm, page_str)

        self.restoreState()


def create_pdf(output_path: Path):
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
        fontSize=20,
        leading=24,
        textColor=COLOR_PRIMARY,
        spaceAfter=4,
    )
    style_subtitle = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=COLOR_SECONDARY,
        spaceAfter=12,
    )
    style_h1 = ParagraphStyle(
        "SectionH1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=COLOR_PRIMARY,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True,
    )
    style_h2 = ParagraphStyle(
        "SectionH2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14.5,
        textColor=COLOR_ACCENT,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True,
    )
    style_body = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=COLOR_TEXT,
        spaceAfter=5,
    )
    style_body_bold = ParagraphStyle(
        "BodyDarkBold",
        parent=style_body,
        fontName="Helvetica-Bold",
    )
    style_bullet = ParagraphStyle(
        "BulletText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12.5,
        textColor=COLOR_TEXT,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3,
    )
    style_callout = ParagraphStyle(
        "CalloutText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12.5,
        textColor=COLOR_TEXT,
    )
    style_code = ParagraphStyle(
        "CodeText",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#F1F5F9"),
    )
    style_formula = ParagraphStyle(
        "FormulaText",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=15,
        alignment=1, # Center
        textColor=COLOR_PRIMARY,
    )
    style_badge = ParagraphStyle(
        "BadgeText",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=COLOR_ACCENT,
        alignment=1,
    )
    style_th = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11.5,
        textColor=colors.white,
    )
    style_td = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11.5,
        textColor=COLOR_TEXT,
    )

    story = []

    # ── HEADER & TITOLO ────────────────────────────────────────────────────────
    story.append(Paragraph("HyperSpace AGI — Report Tecnico di Architettura", style_subtitle))
    story.append(Paragraph("Laya in HyperSpace & La Selezione dei Nodi", style_title))
    story.append(Paragraph("Decision Engine System 1 non-autoregressivo e Routing a 2 Stadi (Semantico vs Metrico)", style_subtitle))

    # Badge Bar
    badges = [
        [
            Paragraph("<b>MODULO: LAYA SYSTEM 1</b>", style_badge),
            Paragraph("<b>LATENZA: SUB-50 MS</b>", style_badge),
            Paragraph("<b>ROUTING A 2 STADI</b>", style_badge),
            Paragraph("<b>HARDWARE: MPS / MESH</b>", style_badge),
        ]
    ]
    badge_table = Table(badges, colWidths=[43.5 * mm] * 4)
    badge_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_ACCENT_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_ACCENT),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(badge_table)
    story.append(Spacer(1, 8))

    # ── SEZIONE 1 ──────────────────────────────────────────────────────────────
    story.append(Paragraph("1. Cosa fa Laya adesso in HyperSpace (Recap)", style_h1))
    story.append(Paragraph(
        "Laya (<code>NandhaKishorM/laya</code>) agisce come il livello <b>System 1 (intuitivo, categorico, sub-50ms)</b> "
        "di HyperSpace, perfettamente complementare al <b>System 2 (deliberativo, autoregressivo, CoT lento)</b>:",
        style_body
    ))

    # Elenco dei 3 punti operativi
    p1 = (
        "<b>1. Fast-Gate in Mission Control (<code>control-plane/cp/mission.py</code>):</b><br/>"
        "Quando un worker completa un task, il verifier deve emettere un verdetto rapido: <code>pass</code>, "
        "<code>retry</code>, <code>replan</code> o <code>fail</code>. Invece di attendere 5–10 secondi e spendere token "
        "invocando un LLM grande, <b>Laya valuta la conformità del task in ~35 ms</b> in singola forward pass. "
        "Se la confidenza è &ge; 0.85, il verdetto è registrato subito (<code>system: 'laya-1'</code>). "
        "Se Laya è incerto o offline, scatta in automatico il fallback su System 2 (<code>_mission_llm</code>)."
    )
    p2 = (
        "<b>2. Client tipizzato fail-safe (<code>shared/laya_client.py</code>):</b><br/>"
        "Mette a disposizione di tutto il repository chiamate pure (<code>decide_choice</code>, <code>decide_noul</code>, "
        "<code>decide_score</code>, <code>predict_batch</code>) senza appesantire il <code>.venv</code> di base con PyTorch o transformers. "
        "Gestisce soglie di astensione (<code>abstention</code>) e fail-closed sicuro."
    )
    p3 = (
        "<b>3. Infrastruttura e Diagnostica:</b><br/>"
        "È orchestrabile via Docker con profilo opzionale (<code>docker compose --profile decision up -d laya</code>) "
        "o tramite il runner locale Apple Silicon Metal (<code>scripts/laya_service.py --device mps</code>). "
        "Monitorabile in qualsiasi momento con lo script di diagnostica <code>scripts/diagnostics/laya_health.py</code>."
    )

    for item in [p1, p2, p3]:
        story.append(Paragraph(f"• {item}", style_bullet))
        story.append(Spacer(1, 2))

    story.append(Spacer(1, 4))

    # ── SEZIONE 2 ──────────────────────────────────────────────────────────────
    story.append(Paragraph("2. Come vengono scelti i nodi? (Il Routing a 2 Stadi)", style_h1))
    story.append(Paragraph(
        "In HyperSpace la scelta del nodo è un processo a <b>due stadi separati e complementari</b>:<br/>"
        "<b>Stadio 1:</b> Laya decide <i>cosa serve alla richiesta</i> (Routing Semantico & di Capacità).<br/>"
        "<b>Stadio 2:</b> HyperSpace Control Plane decide <i>chi ha le risorse fisiche per farlo</i> (Routing Hardware & Metriche).",
        style_body
    ))
    story.append(Spacer(1, 4))

    # ── DIAGRAMMA TABELLARE ARCHITETTURA A 2 STADI ─────────────────────────────
    flow_data = [
        [
            Paragraph("<b>Richiesta Utente (Prompt / Task)</b>", style_callout),
        ],
        [
            Paragraph("↓", ParagraphStyle("Arrow", parent=style_callout, alignment=1, fontSize=12, textColor=COLOR_ACCENT)),
        ],
        [
            Paragraph(
                "<b>STADIO 1: LAYA (Routing Semantico & Triage Istantaneo ~33ms)</b><br/>"
                "• Rilevamento Lingua & Script (<0.5ms): Inglese vs Multilingua (100+ lingue)<br/>"
                "• Identificazione Classe Requisiti: <code>code_sandbox</code>, <code>multimedia_vision</code>, <code>fast_chat</code>, <code>reasoning_heavy</code><br/>"
                "• Flag Reasoning Dinamico: <code>think = true / false</code> (spegne il CoT se bastano i tool)",
                style_callout
            ),
        ],
        [
            Paragraph("↓ [Requisiti Estratti: classe modello, memoria richiesta, tool abilitati]", ParagraphStyle("Arrow2", parent=style_callout, alignment=1, fontSize=8, textColor=COLOR_MUTED)),
        ],
        [
            Paragraph(
                "<b>STADIO 2: HYPERSPACE CONTROL PLANE (Routing Hardware & Metriche — <code>control-plane/routing.py</code>)</b><br/>"
                "• Normalizzazione Min-Max dei candidati idonei della flotta mesh<br/>"
                "• Punteggio di Qualità Dinamico: Latenza EWMA + Throughput TPS effettivo + Pressione cache GPU<br/>"
                "• Punteggio Strutturale: VRAM disponibile (peso 55%) + Saturazione/Carico (25%) + Tier (10%)<br/>"
                "• Gate di Salute (<code>health_s</code>) & Penalità Anti-Hotspot Esponenziale",
                style_callout
            ),
        ],
        [
            Paragraph("↓", ParagraphStyle("Arrow3", parent=style_callout, alignment=1, fontSize=12, textColor=COLOR_ACCENT)),
        ],
        [
            Table(
                [
                    [
                        Paragraph("<b>Mac Locale (Apple Silicon)</b><br/>Control Plane, Laya su Metal (MPS), Tool leggeri, Triage", style_callout),
                        Paragraph("<b>Worker Remoto (GPU RTX / Linux)</b><br/>ComfyUI, Generazione Immagini, Modelli grandi 32B/70B", style_callout),
                    ]
                ],
                colWidths=[84 * mm, 84 * mm],
                style=[
                    ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#F1F5F9")),
                    ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        ]
    ]

    diagram_table = Table(flow_data, colWidths=[174 * mm])
    diagram_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), COLOR_ACCENT_BG),
        ("BACKGROUND", (0, 2), (0, 2), colors.HexColor("#F0FDF4")), # Green tint
        ("BACKGROUND", (0, 4), (0, 4), colors.HexColor("#EFF6FF")), # Blue tint
        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    story.append(diagram_table)
    story.append(Spacer(1, 10))
    story.append(PageBreak())

    # ── STADIO 1 DETTAGLIO ─────────────────────────────────────────────────────
    story.append(Paragraph("Stadio 1 — Come Laya instrada semanticamente", style_h2))
    story.append(Paragraph(
        "Laya opera su due livelli decisionali interni prima che qualsiasi byte tocchi la rete:",
        style_body
    ))
    story.append(Paragraph(
        "• <b>Router dei Checkpoint Interno (&lt;0.5 ms):</b> Laya analizza lo script e la lingua all'istante:<br/>"
        "&nbsp;&nbsp;– Testo inglese &rarr; checkpoint <code>laya</code> (ModernBERT-large, 421M);<br/>"
        "&nbsp;&nbsp;– Testo italiano o altre 100+ lingue &rarr; checkpoint <code>laya-multilingual</code> (mmBERT, 322M);<br/>"
        "&nbsp;&nbsp;– Workflow strutturati specifici &rarr; checkpoint <code>laya-typed-decisions</code>.",
        style_bullet
    ))
    story.append(Paragraph(
        "• <b>Triage di Classe e Requisiti:</b> Con una forward pass categorica <code>choice</code>, Laya classifica il fabbisogno:<br/>"
        "&nbsp;&nbsp;– <code>code_sandbox</code>: richiede un nodo con runner Docker o sandbox isolata;<br/>"
        "&nbsp;&nbsp;– <code>multimedia_vision</code>: instrada verso il worker dedicato alle immagini (ComfyUI con alta VRAM);<br/>"
        "&nbsp;&nbsp;– <code>fast_chat</code>: gestibile dal modello leggero locale senza allocare risorse pesanti;<br/>"
        "&nbsp;&nbsp;– <code>reasoning_heavy</code>: richiede un nodo con modello di deduzione logica (Qwen/DeepSeek CoT attivo).",
        style_bullet
    ))

    story.append(Spacer(1, 6))

    # ── STADIO 2 DETTAGLIO ─────────────────────────────────────────────────────
    story.append(Paragraph("Stadio 2 — Come HyperSpace sceglie la macchina fisica (<code>control-plane/routing.py</code>)", style_h2))
    story.append(Paragraph(
        "Una volta che i requisiti sono noti, entra in gioco il router metrico di HyperSpace (<code>compute_score</code>), "
        "che calcola un punteggio matematico normalizzato per ciascun nodo candidato:",
        style_body
    ))

    # Box Formula Matematica
    formula_box = Table(
        [[Paragraph("<b>Score = Health_Gate × ( q · Quality + (1 - q) · Structural ) - Recent_Penalty</b>", style_formula)]],
        colWidths=[174 * mm]
    )
    formula_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_ACCENT_BG),
        ("BOX", (0, 0), (-1, -1), 0.75, COLOR_ACCENT),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(formula_box)
    story.append(Spacer(1, 6))

    # Dettaglio componenti formula
    story.append(Paragraph(
        "• <b>Gate di Salute (<code>Health_Gate</code>):</b> Se il nodo è online e invia metriche fresche: moltiplicatore <code>1.0</code>. "
        "Se è degradato o i campioni sono vecchi: depenalizzato a <code>0.4</code>. Se offline o non risponde: <code>0.0</code> (eliminato).",
        style_bullet
    ))
    story.append(Paragraph(
        "• <b>Punteggio di Qualità (<code>Quality</code>):</b> Latenza EWMA (<code>lat_s</code>, peso 45%), Throughput (<code>tps_s</code>, peso 35%) "
        "e Pressione cache GPU (<code>gpu_s</code>, peso 20%). Il fattore <i>q</i> indica la freschezza delle metriche (1.0 se fresche, 0.0 se assenti).",
        style_bullet
    ))
    story.append(Paragraph(
        "• <b>Punteggio Strutturale (<code>Structural</code>):</b> Entra in gioco quando i campioni latenza mancano. "
        "<b>VRAM libera (<code>vram_s</code>, peso 55%)</b> dà priorità alle macchine con memoria video capiente (fondamentale per il nodo remoto ComfyUI); "
        "Carico/Saturazione (<code>load_s</code>, peso 25%); Tier di rete gerarchico <code>root &gt; hub &gt; leaf</code> (peso 10%).",
        style_bullet
    ))
    story.append(Paragraph(
        "• <b>Penalità Anti-Hotspot (<code>Recent_Penalty</code>):</b> Decremento esponenziale applicato al nodo selezionato più di recente "
        "per prevenire il sovraccarico di una singola macchina e distribuire il traffico equamente.",
        style_bullet
    ))

    story.append(Spacer(1, 6))

    # ── SEZIONE 3: IN SINTESI ──────────────────────────────────────────────────
    story.append(Paragraph("3. In Sintesi: Matrice di Responsabilità", style_h1))

    table_comparison_data = [
        [
            Paragraph("<b>Dimensione</b>", style_th),
            Paragraph("<b>Laya (System 1)</b>", style_th),
            Paragraph("<b>HyperSpace Router (<code>routing.py</code>)</b>", style_th),
        ],
        [
            Paragraph("<b>Scopo Primario</b>", style_td),
            Paragraph("<b>Routing Semantico</b> e Decisioni Tipizzate", style_td),
            Paragraph("<b>Routing Hardware</b> e Bilanciamento di Carico", style_td),
        ],
        [
            Paragraph("<b>Tempo di Risposta</b>", style_td),
            Paragraph("<b>30–35 ms</b> (GPU) / ~120 ms (Mac MPS)", style_td),
            Paragraph("<b>&lt; 5 ms</b> (Calcolo matematico puro su telemetria)", style_td),
        ],
        [
            Paragraph("<b>Input Analizzato</b>", style_td),
            Paragraph("Testo, prompt, evidenza task, lingua, intent", style_td),
            Paragraph("Heartbeat, VRAM (GB), saturazione, latenza EWMA, TPS", style_td),
        ],
        [
            Paragraph("<b>Output Prodotto</b>", style_td),
            Paragraph("Scelta categorica (<code>choice</code>), booleano (<code>noul</code>), score", style_td),
            Paragraph("ID del nodo fisico ottimale nella mesh", style_td),
        ],
        [
            Paragraph("<b>Comportamento Fallimento</b>", style_td),
            Paragraph("Astensione calibrata &rarr; escalation a System 2", style_td),
            Paragraph("Failover automatico al nodo secondo classificato", style_td),
        ],
    ]

    comp_table = Table(table_comparison_data, colWidths=[36 * mm, 69 * mm, 69 * mm])
    comp_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY),
        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    story.append(comp_table)
    story.append(Spacer(1, 8))

    # Conclusione callout box
    conclusion_text = (
        "<b>Conclusione Architetturale:</b> Laya e HyperSpace <code>routing.py</code> lavorano in tandem armonico. "
        "Laya è il <i>cervello di triage rapido</i> che capisce in 30 ms il bisogno della richiesta o l'esito del lavoro, "
        "mentre <code>routing.py</code> è il <i>direttore infrastrutturale</i> che invia il calcolo pesante al nodo "
        "più idoneo della mesh (Mac locale per l'interazione rapida, worker GPU remoto per ComfyUI e rendering video)."
    )
    conclusion_box = Table([[Paragraph(conclusion_text, style_body)]], colWidths=[174 * mm])
    conclusion_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_ACCENT_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_ACCENT),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(conclusion_box)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF generato con successo: {output_path}")


if __name__ == "__main__":
    OUT = PDF_OUT
    OUT.parent.mkdir(parents=True, exist_ok=True)
    create_pdf(OUT)
