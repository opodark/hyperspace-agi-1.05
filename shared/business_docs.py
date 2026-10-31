# SPDX-License-Identifier: Apache-2.0
"""
shared/business_docs.py — Generatore di Preventivi e Fatture per PMI (ReportLab PDF).

Modulo deterministico per la gestione documentale aziendale (botteghe, artigiani,
professionisti, studi). Crea documenti PDF professionali conformi e validati
con calcolo automatico di imponibile, aliquote IVA, ritenuta e totali.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


@dataclass
class DocumentParty:
    name: str
    address: str = ""
    vat_number: str = ""  # P.IVA
    tax_code: str = ""    # Codice Fiscale
    email: str = ""
    phone: str = ""


@dataclass
class DocumentItem:
    description: str
    quantity: float
    unit_price: float
    vat_rate: float = 22.0  # Percentuale IVA (es. 22.0, 10.0, 4.0, 0.0)

    @property
    def total_net(self) -> float:
        return round(self.quantity * self.unit_price, 2)

    @property
    def vat_amount(self) -> float:
        return round(self.total_net * (self.vat_rate / 100.0), 2)


@dataclass
class BusinessDocument:
    doc_type: str  # "PREVENTIVO" o "FATTURA"
    number: str
    date: str
    issuer: DocumentParty
    client: DocumentParty
    items: list[DocumentItem] = field(default_factory=list)
    notes: str = ""
    payment_terms: str = "Bonifico Bancario 30gg data fattura"
    withholding_tax_rate: float = 0.0  # Ritenuta d'acconto (es. 20.0 per professionisti)

    def calculate_totals(self) -> dict[str, float]:
        subtotal_net = sum(item.total_net for item in self.items)
        vat_breakdown: dict[float, float] = {}
        for item in self.items:
            vat_breakdown[item.vat_rate] = vat_breakdown.get(item.vat_rate, 0.0) + item.vat_amount
        total_vat = sum(vat_breakdown.values())
        withholding = round(subtotal_net * (self.withholding_tax_rate / 100.0), 2)
        total_gross = round(subtotal_net + total_vat, 2)
        net_payable = round(total_gross - withholding, 2)

        return {
            "subtotal_net": subtotal_net,
            "total_vat": total_vat,
            "withholding": withholding,
            "total_gross": total_gross,
            "net_payable": net_payable,
        }

    def render_pdf(self, output_path: str | Path) -> str:
        output_file = Path(output_path).resolve()
        output_file.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(output_file),
            pagesize=A4,
            leftMargin=1.5 * cm,
            rightMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#1A365D"),
            fontName="Helvetica-Bold",
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#4A5568"),
        )
        bold_style = ParagraphStyle(
            "DocBold",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            fontName="Helvetica-Bold",
        )
        normal_style = ParagraphStyle(
            "DocNormal",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
        )

        story = []

        # Intestazione: Tipo Doc e Dati Emittente / Cliente
        header_data = [
            [
                Paragraph(f"<b>{self.doc_type}</b> N° {self.number}<br/><font size=8 color='#718096'>Data: {self.date}</font>", title_style),
                Paragraph(f"<b>{self.issuer.name}</b><br/>{self.issuer.address}<br/>P.IVA: {self.issuer.vat_number}<br/>{self.issuer.email}", subtitle_style),
            ]
        ]
        header_table = Table(header_data, colWidths=[9 * cm, 9 * cm])
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 15))

        # Riquadro Cliente
        client_data = [
            [
                Paragraph("<b>Destinatario / Committente:</b>", bold_style),
            ],
            [
                Paragraph(f"<b>{self.client.name}</b><br/>{self.client.address}<br/>P.IVA / C.F.: {self.client.vat_number or self.client.tax_code}<br/>Email: {self.client.email}", normal_style),
            ]
        ]
        client_table = Table(client_data, colWidths=[18 * cm])
        client_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(client_table)
        story.append(Spacer(1, 15))

        # Tabella Righe / Articoli
        items_data = [["Descrizione", "Q.tà", "Prezzo Unit.", "IVA %", "Totale"]]
        for item in self.items:
            items_data.append([
                Paragraph(item.description, normal_style),
                f"{item.quantity:g}",
                f"€ {item.unit_price:.2f}",
                f"{item.vat_rate:.0f}%",
                f"€ {item.total_net:.2f}",
            ])

        items_table = Table(items_data, colWidths=[9 * cm, 1.8 * cm, 2.5 * cm, 1.8 * cm, 2.9 * cm])
        items_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 10))

        # Totali
        totals = self.calculate_totals()
        totals_data = [
            ["Totale Imponibile:", f"€ {totals['subtotal_net']:.2f}"],
            ["Totale IVA:", f"€ {totals['total_vat']:.2f}"],
        ]
        if totals["withholding"] > 0:
            totals_data.append([f"Ritenuta d'acconto ({self.withholding_tax_rate:.0f}%):", f"- € {totals['withholding']:.2f}"])
        totals_data.append(["Totale da Saldare:", f"€ {totals['net_payable']:.2f}"])

        totals_table = Table(totals_data, colWidths=[14 * cm, 4 * cm])
        totals_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, 0), (-1, -2), "Helvetica"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, -1), (-1, -1), 11),
            ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#1A365D")),
            ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#2B6CB0")),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(totals_table)
        story.append(Spacer(1, 15))

        # Condizioni e Note
        notes_text = []
        if self.payment_terms:
            notes_text.append(f"<b>Modalità di Pagamento:</b> {self.payment_terms}")
        if self.notes:
            notes_text.append(f"<b>Note:</b> {self.notes}")
        if notes_text:
            notes_para = Paragraph("<br/>".join(notes_text), normal_style)
            notes_table = Table([[notes_para]], colWidths=[18 * cm])
            notes_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EDF2F7")),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]))
            story.append(notes_table)

        doc.build(story)
        return str(output_file)
