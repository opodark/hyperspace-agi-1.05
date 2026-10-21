#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# shared/pdf_generator.py
"""Generatore Deterministico di Documenti PDF A4 per HyperSpace AGI.

Converte Markdown e testo formattato in PDF vettoriali professionali
utilizzando ReportLab, con supporto per:
- Titoli (H1, H2, H3, H4)
- Paragrafi, enfasi (grassetto/corsivo)
- Liste puntate e numerate
- Tabelle formattate
- Blocchi di codice ed estratti
- Header e Footer eleganti con numerazione 'Pagina X di Y'
- Output binario diretto (in-memory) e salvataggio su file.
"""

from __future__ import annotations

import html
import io
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Union

ROOT = Path(__file__).resolve().parents[1]

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm, mm
    from reportlab.pdfgen import canvas
    from reportlab.platypus import (
        HRFlowable,
        KeepTogether,
        PageBreak,
        Paragraph,
        Preformatted,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class NumberedCanvas(canvas.Canvas if REPORTLAB_AVAILABLE else object):
    """Canvas dinamico a due passaggi per calcolare e disegnare 'Pagina X di Y'."""

    def __init__(self, *args, **kwargs):
        self.doc_title = kwargs.pop("doc_title", "HyperSpace AGI")
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, total_pages: int):
        self.saveState()
        w, h = A4

        # Header superiore (da pagina 2)
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#475569"))
            self.drawString(50, h - 35, "HYPERSPACE AGI")
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#64748b"))
            self.drawString(130, h - 35, f"·  {self.doc_title[:65]}")

            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.75)
            self.line(50, h - 42, w - 50, h - 42)

        # Footer inferiore (su tutte le pagine)
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.75)
        self.line(50, 42, w - 50, 42)

        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawString(50, 30, "Documento Generato da HyperSpace Sovereign Mesh Ecosystem")

        page_str = f"Pagina {self._pageNumber} di {total_pages}"
        self.drawRightString(w - 50, 30, page_str)

        self.restoreState()


def _format_inline_markdown(text: str) -> str:
    """Traduce markdown inline (**bold**, *italic*, `code`) in tag ReportLab."""
    # Escape caratteri XML/HTML
    s = html.escape(text)

    # Grassetto **text**
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    # Corsivo *text* o _text_
    s = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", s)
    # Codice inline `code`
    s = re.sub(r"`(.+?)`", r'<font face="Courier" color="#4f46e5" size="8.5"><b>\1</b></font>', s)

    return s


def generate_pdf_from_markdown(
    markdown_text: str,
    output_path: Optional[Union[str, Path]] = None,
    title: str = "Documento HyperSpace",
    subtitle: str = "",
    author: str = "HyperSpace AGI",
) -> bytes:
    """Converte un testo Markdown in un PDF A4 professionale deterministico."""
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("ReportLab non disponibile nel runtime corrente.")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=50,
        rightMargin=50,
        topMargin=55,
        bottomMargin=55,
    )

    styles = getSampleStyleSheet()

    # Palette stili
    style_title = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=6,
    )
    style_subtitle = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#475569"),
        spaceAfter=14,
    )
    style_h1 = ParagraphStyle(
        "H1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=16,
        spaceAfter=6,
        keepWithNext=True,
    )
    style_h2 = ParagraphStyle(
        "H2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#334155"),
        spaceBefore=12,
        spaceAfter=4,
        keepWithNext=True,
    )
    style_h3 = ParagraphStyle(
        "H3",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#475569"),
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True,
    )
    style_body = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=6,
    )
    style_bullet = ParagraphStyle(
        "Bullet",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#1e293b"),
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3,
    )
    style_code = ParagraphStyle(
        "CodeBlock",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
        backColor=colors.HexColor("#f8fafc"),
        borderPadding=6,
        spaceBefore=4,
        spaceAfter=8,
    )

    story = []

    # Intestazione iniziale / Copertina leggera
    story.append(Paragraph(_format_inline_markdown(title), style_title))
    if subtitle:
        story.append(Paragraph(_format_inline_markdown(subtitle), style_subtitle))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#4f46e5"), spaceBefore=2, spaceAfter=14))

    lines = markdown_text.strip().split("\n")
    in_code_block = False
    code_lines: List[str] = []
    in_table = False
    table_rows: List[List[str]] = []

    def flush_table():
        nonlocal in_table, table_rows
        if not table_rows:
            in_table = False
            return
        # Costruisce la tabella ReportLab
        formatted_rows = []
        for r_idx, row in enumerate(table_rows):
            is_header = (r_idx == 0)
            row_cells = []
            for cell in row:
                cell_style = ParagraphStyle(
                    f"TableCell_{r_idx}",
                    parent=styles["Normal"],
                    fontName="Helvetica-Bold" if is_header else "Helvetica",
                    fontSize=8.5,
                    leading=11,
                    textColor=colors.HexColor("#0f172a") if is_header else colors.HexColor("#334155"),
                )
                row_cells.append(Paragraph(_format_inline_markdown(cell), cell_style))
            formatted_rows.append(row_cells)

        t = Table(formatted_rows, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 8))
        table_rows = []
        in_table = False

    for line in lines:
        stripped = line.strip()

        # Blocchi di codice ```
        if stripped.startswith("```"):
            if in_code_block:
                in_code_block = False
                code_text = "\n".join(code_lines)
                story.append(Preformatted(code_text, style_code))
                code_lines = []
            else:
                if in_table:
                    flush_table()
                in_code_block = True
                code_lines = []
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        # Tabelle Markdown | col 1 | col 2 |
        if stripped.startswith("|") and stripped.endswith("|"):
            # Righe di separazione |---|---|
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                continue
            cells = [c.strip() for c in stripped[1:-1].split("|")]
            table_rows.append(cells)
            in_table = True
            continue
        elif in_table:
            flush_table()

        if not stripped:
            story.append(Spacer(1, 4))
            continue

        # Separatori orizzontali ---
        if re.match(r"^[-*_]{3,}$", stripped):
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceBefore=6, spaceAfter=8))
            continue

        # Headings
        if stripped.startswith("# "):
            story.append(Paragraph(_format_inline_markdown(stripped[2:]), style_h1))
        elif stripped.startswith("## "):
            story.append(Paragraph(_format_inline_markdown(stripped[3:]), style_h2))
        elif stripped.startswith("### "):
            story.append(Paragraph(_format_inline_markdown(stripped[4:]), style_h3))
        elif stripped.startswith("#### "):
            story.append(Paragraph(_format_inline_markdown(stripped[5:]), style_h3))
        # Liste puntate - o *
        elif stripped.startswith("- ") or stripped.startswith("* "):
            content = _format_inline_markdown(stripped[2:])
            bullet_char = "&bull;&nbsp;&nbsp;"
            story.append(Paragraph(f"{bullet_char}{content}", style_bullet))
        # Liste numerate 1. 2.
        elif re.match(r"^\d+\.\s", stripped):
            num_match = re.match(r"^(\d+\.)\s(.*)", stripped)
            if num_match:
                prefix = f"<b>{num_match.group(1)}</b>&nbsp;&nbsp;"
                content = _format_inline_markdown(num_match.group(2))
                story.append(Paragraph(f"{prefix}{content}", style_bullet))
        else:
            story.append(Paragraph(_format_inline_markdown(stripped), style_body))

    if in_table:
        flush_table()

    # Costruzione documento
    def make_canvas(*args, **kwargs):
        return NumberedCanvas(*args, doc_title=title, **kwargs)

    doc.build(story, canvasmaker=make_canvas)
    pdf_bytes = buffer.getvalue()

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "wb") as f:
            f.write(pdf_bytes)

    return pdf_bytes
