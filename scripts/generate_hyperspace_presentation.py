# SPDX-License-Identifier: Apache-2.0
"""Generate the reviewable HyperSpace 1.05 project presentation PDF."""

from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "hyperspace-1.05-presentation.pdf"
PAGE = landscape((297 * mm, 167 * mm))
NAVY, INK, MUTED = (
    colors.HexColor("#0B1020"),
    colors.HexColor("#172033"),
    colors.HexColor("#667085"),
)
CYAN, PURPLE, PALE = (
    colors.HexColor("#36D1DC"),
    colors.HexColor("#7C5CFC"),
    colors.HexColor("#F5F7FB"),
)
BASE = getSampleStyleSheet()
S = {
    "title": ParagraphStyle(
        "title",
        parent=BASE["Title"],
        fontName="Helvetica-Bold",
        fontSize=26,
        leading=31,
        textColor=colors.white,
        spaceAfter=9,
    ),
    "subtitle": ParagraphStyle(
        "subtitle",
        parent=BASE["Normal"],
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#C9D4EE"),
    ),
    "h": ParagraphStyle(
        "h",
        parent=BASE["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=INK,
        spaceAfter=10,
    ),
    "kicker": ParagraphStyle(
        "kicker",
        parent=BASE["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=PURPLE,
    ),
    "body": ParagraphStyle(
        "body",
        parent=BASE["BodyText"],
        fontSize=11,
        leading=15,
        textColor=INK,
        spaceAfter=7,
    ),
    "small": ParagraphStyle(
        "small", parent=BASE["BodyText"], fontSize=8, leading=10, textColor=MUTED
    ),
}


def box(title, text, width=74):
    return Table(
        [[Paragraph(f"<b>{title}</b>", S["body"])], [Paragraph(text, S["body"])]],
        colWidths=[width * mm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D9E0EF")),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        ),
    )


def frame(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(PALE)
    canvas.rect(0, 0, PAGE[0], PAGE[1], fill=1, stroke=0)
    canvas.setStrokeColor(colors.HexColor("#D9E0EF"))
    canvas.line(16 * mm, 13 * mm, PAGE[0] - 16 * mm, 13 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(16 * mm, 8 * mm, "HYPERSPACE AGI 1.05  ·  PROJECT REVIEW")
    canvas.drawRightString(PAGE[0] - 16 * mm, 8 * mm, str(doc.page))
    canvas.restoreState()


def slide(story, label, title, content):
    story += [
        Paragraph(label.upper(), S["kicker"]),
        Paragraph(title, S["h"]),
        content,
        PageBreak(),
    ]


def build():
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=PAGE,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
    )
    story = [
        Spacer(1, 28 * mm),
        Paragraph("HyperSpace AGI 1.05", S["title"]),
        Paragraph(
            "Dal progetto al runtime operativo per agenti IA locali e distribuiti",
            S["subtitle"],
        ),
        Spacer(1, 12 * mm),
        Paragraph(
            "Traguardi · architettura · opportunità commerciali · prossimi 18 mesi",
            S["subtitle"],
        ),
        PageBreak(),
    ]
    slide(
        story,
        "01 · La tesi",
        "Non un chatbot: un runtime governato",
        Table(
            [
                [
                    Paragraph(
                        "HyperSpace coordina modelli, strumenti, memoria, policy e nodi per svolgere lavoro reale.",
                        S["body"],
                    )
                ],
                [
                    Paragraph(
                        "Il prodotto è il confine operativo: capability, budget, audit, sandbox e revisione umana.",
                        S["body"],
                    )
                ],
                [
                    Paragraph(
                        "La chat è una superficie; il control plane è il cuore.",
                        S["body"],
                    )
                ],
            ],
            colWidths=[235 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.8, CYAN),
                    ("LEFTPADDING", (0, 0), (-1, -1), 14),
                    ("TOPPADDING", (0, 0), (-1, -1), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ]
            ),
        ),
    )
    slide(
        story,
        "02 · Cosa c'è",
        "Una base già ampia e concreta",
        Table(
            [
                [
                    box(
                        "Control plane",
                        "API OpenAI-compatible, routing, tool loop, dashboard e connector fabric",
                    ),
                    box(
                        "Mission Control",
                        "Obiettivo → DAG bounded → worker → verifica → review",
                    ),
                    box(
                        "Sandbox e Forge",
                        "Diff, test e skill approvate senza applicazione automatica",
                    ),
                ],
                [
                    box(
                        "Memoria e sogni",
                        "Hermes come direzione, Dream review e graphify",
                    ),
                    box(
                        "Profili verticali",
                        "Ufficio e Multimedia: AnyDoc, PDF, Reel, Website e Comic",
                    ),
                    box("Canali e nodi", "Telegram, Instagram, web node e Tailscale"),
                ],
            ],
            colWidths=[77 * mm] * 3,
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                ]
            ),
        ),
    )
    slide(
        story,
        "03 · Traguardi 1.05",
        "Dalla promessa ai contratti verificabili",
        Table(
            [
                [
                    Paragraph(
                        "✓ Missioni bounded con budget, concorrenza, retry e tempo cumulativo",
                        S["body"],
                    ),
                    Paragraph(
                        "✓ Allowlist per tool e azioni; errori ed evidenze strutturate",
                        S["body"],
                    ),
                ],
                [
                    Paragraph(
                        "✓ Skill approvate, hash verificate e selezione con tool compatibili",
                        S["body"],
                    ),
                    Paragraph(
                        "✓ Review legata alla versione degli artifact", S["body"]
                    ),
                ],
                [
                    Paragraph(
                        "✓ Bundle AnyDoc, Firecrawl skills e Wayfinder tracciati",
                        S["body"],
                    ),
                    Paragraph(
                        "✓ Repository 1.05 pubblicato e documentazione raccolta",
                        S["body"],
                    ),
                ],
            ],
            colWidths=[117 * mm, 117 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#D9E0EF")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9E0EF")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("TOPPADDING", (0, 0), (-1, -1), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ]
            ),
        ),
    )
    slide(
        story,
        "04 · Commerciale",
        "Quattro ingressi, un solo core",
        Table(
            [
                [
                    box(
                        "Enterprise Local",
                        "Dati interni, connettori, audit e inferenza locale. Licenza/supporto annuale.",
                    ),
                    box(
                        "Agent Operations",
                        "Missioni, sandbox, review e report per team tecnici.",
                    ),
                    box(
                        "HyperSpace Ufficio",
                        "Documenti, PDF, Office bridge e memoria di progetto.",
                    ),
                ],
                [
                    box(
                        "HyperSpace Multimedia",
                        "Reel, immagini, fumetti e pipeline narrative. Licenza studio e servizi.",
                    )
                ],
            ],
            colWidths=[77 * mm] * 3,
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                ]
            ),
        ),
    )
    slide(
        story,
        "05 · Piano",
        "Vendere un caso d'uso prima della piattaforma",
        Table(
            [
                [
                    Paragraph(
                        "<b>0–3 mesi</b>  ·  Pilota pagante Enterprise Local o Ufficio, caso d'uso stretto, metriche e installazione assistita",
                        S["body"],
                    )
                ],
                [
                    Paragraph(
                        "<b>3–9 mesi</b>  ·  Installer, profili, backup/recovery, benchmark, audit export e contratto connector ripetibile",
                        S["body"],
                    )
                ],
                [
                    Paragraph(
                        "<b>9–18 mesi</b>  ·  Linux production, browser worker, mesh, tenancy e marketplace dopo l'hardening",
                        S["body"],
                    )
                ],
            ],
            colWidths=[235 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9E0EF")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("TOPPADDING", (0, 0), (-1, -1), 11),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
                ]
            ),
        ),
    )
    slide(
        story,
        "06 · Onestà",
        "Pronto oggi, roadmap domani",
        Table(
            [
                [
                    box(
                        "Oggi",
                        "Runtime locale, control plane, sandbox, Forge, connettori, profili verticali, documentazione e test.",
                    ),
                    box(
                        "Da dimostrare",
                        "Benchmark comparabili, recovery Hermes, installazione ripetibile e valore di un pilota.",
                    ),
                    box(
                        "Dopo",
                        "Mesh completa, HIP, failover, browser worker completo e multi-tenancy pubblica.",
                    ),
                ]
            ],
            colWidths=[77 * mm] * 3,
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                ]
            ),
        ),
    )
    slide(
        story,
        "07 · Metriche",
        "Il prodotto si decide con numeri osservabili",
        Table(
            [
                [
                    Paragraph("Tempo dall'obiettivo al diff approvabile", S["body"]),
                    Paragraph("Costo e latenza per missione", S["body"]),
                    Paragraph("Task conclusi senza intervento extra", S["body"]),
                ],
                [
                    Paragraph("Errori bloccati dalla policy", S["body"]),
                    Paragraph("Tempo di installazione e recovery", S["body"]),
                    Paragraph("Retention e valore del pilota", S["body"]),
                ],
            ],
            colWidths=[78 * mm] * 3,
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.8, CYAN),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9E0EF")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("TOPPADDING", (0, 0), (-1, -1), 13),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 13),
                ]
            ),
        ),
    )
    slide(
        story,
        "08 · Chiusura",
        "La prossima milestone è un prodotto ripetibile",
        Table(
            [
                [
                    Paragraph(
                        "HyperSpace ha già una base rara: tratta l'agente come un componente operativo governato, non come una conversazione brillante.",
                        S["title"],
                    )
                ],
                [
                    Paragraph(
                        "Il prossimo salto commerciale è rendere un profilo verticale installabile, misurabile e supportabile.",
                        S["subtitle"],
                    )
                ],
                [
                    Spacer(1, 8 * mm),
                    Paragraph(
                        "Fonti: README.md · VISION.md · ROADMAP.md · docs/architecture.md · docs/mission-control.md · docs/tool-skill-forge.md · docs/skill-hooks.md · docs/growth-strategy.md · docs/dreams.md · docs/development-security-tools.md · docs/tiktok-editor.md",
                        S["small"],
                    ),
                ],
            ],
            colWidths=[235 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                    ("LEFTPADDING", (0, 0), (-1, -1), 16),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                    ("TOPPADDING", (0, 0), (-1, -1), 15),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 15),
                ]
            ),
        ),
    )
    doc.build(story, onFirstPage=frame, onLaterPages=frame)
    print(OUT)


if __name__ == "__main__":
    build()
