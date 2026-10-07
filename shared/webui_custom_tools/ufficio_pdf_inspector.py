# SPDX-License-Identifier: Apache-2.0
"""Classifica un PDF della cartella condivisa con pdf-inspector (Firecrawl).

Tool del profilo Ufficio: dice se un PDF e' testo nativo, scansione, immagini o
misto, quanto e' sicura la stima e **quali pagine** non hanno testo estraibile.
Serve a instradare pagina per pagina: cio' che si estrae in locale resta in
locale, all'OCR va solo cio' che serve. La classificazione la fa `pdf-inspector`,
la libreria Rust di Firecrawl (binding Python); il tool usa solo le funzioni
native (`process_pdf`), quindi non esegue OCR, non scarica modelli e non tocca
la rete. Se il pacchetto non e' installato nell'immagine del control-plane il
tool lo dice con un errore chiaro invece di fallire a vuoto (vedi
docs/webui-tools.md). La skill testuale del catalogo Firecrawl e' importabile
come draft dal Forge (`POST /forge/import/firecrawl-skills`).
"""

import os
from pathlib import Path

from shared.webui_tool_registry import tool

# Solo PDF: la classificazione riguarda i file PDF.
PDF_EXTENSIONS = {".pdf"}

# Tetto dell'anteprima riportata nel contesto del modello: un documento intero
# non e' un'anteprima e riempirebbe la finestra del contesto.
MAX_PREVIEW_CHARS = 20_000
DEFAULT_PREVIEW_CHARS = 2_000


def _share_root() -> Path:
    try:
        return Path(os.getenv("WEBUI_SHARE_DIR", "/app/hyperspace_share")).resolve(strict=True)
    except OSError as error:
        raise ValueError(f"Cartella condivisa non disponibile: {error}") from error


def _within(relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip() or Path(relative).is_absolute():
        raise ValueError("Usa un percorso relativo non vuoto nella cartella condivisa")
    base = _share_root()
    target = (base / relative).resolve()
    if not target.is_relative_to(base):
        raise ValueError("Percorso esterno alla cartella condivisa")
    return target


def _load_pdf_inspector():
    # Import locale: senza la libreria il modulo resta caricabile e il registro
    # dei tool non crolla all'avvio (l'import sta qui, non in cima al file).
    try:
        import pdf_inspector
    except ImportError as error:
        raise ValueError(
            "pdf-inspector non e' installato nel control plane: aggiungi 'pdf-inspector' a "
            "control-plane/requirements.txt e ricostruisci il servizio (vedi docs/webui-tools.md)."
        ) from error
    return pdf_inspector


@tool(description=("Classifica un PDF della cartella condivisa con pdf-inspector: dice se e' "
                   "testo nativo, scansione, immagini o misto, con una confidenza e l'elenco "
                   "(numeri di pagina 1-based) delle pagine senza testo estraibile, cosi' si "
                   "manda all'OCR solo cio' che serve. Legge il PDF in locale: non esegue OCR, "
                   "non scarica modelli e non invia nulla alla rete."))
def classifica_pdf(percorso: str, estrai_markdown: bool = False,
                   anteprima_caratteri: int = DEFAULT_PREVIEW_CHARS) -> dict:
    if not isinstance(anteprima_caratteri, int) or isinstance(anteprima_caratteri, bool):
        raise ValueError("anteprima_caratteri deve essere un intero")
    if not 0 <= anteprima_caratteri <= MAX_PREVIEW_CHARS:
        raise ValueError(f"anteprima_caratteri deve stare fra 0 e {MAX_PREVIEW_CHARS}")

    source = _within(percorso)
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"PDF non trovato: {percorso}")
    if source.suffix.lower() not in PDF_EXTENSIONS:
        raise ValueError("Formato non supportato: usa un file .pdf")

    pdf_inspector = _load_pdf_inspector()
    try:
        # process_pdf fa solo estrazione nativa: nessun OCR, nessun download.
        result = pdf_inspector.process_pdf(str(source))
    except OSError as error:
        raise ValueError(f"Impossibile leggere il PDF: {error}") from error
    except Exception as error:  # PdfError e simili della libreria Rust
        raise ValueError(f"Lettura del PDF non riuscita ({type(error).__name__}): {error}") from error

    pages_needing_ocr = [int(page) for page in (getattr(result, "pages_needing_ocr", None) or [])]
    markdown = getattr(result, "markdown", None) if estrai_markdown else None

    preview = ""
    truncated = False
    if isinstance(markdown, str):
        preview = markdown[:anteprima_caratteri]
        truncated = len(markdown) > len(preview)

    return {
        "pdf_type": str(getattr(result, "pdf_type", "") or ""),
        "confidenza": round(float(getattr(result, "confidence", 0.0) or 0.0), 4),
        "pagine": int(getattr(result, "page_count", 0) or 0),
        "pagine_senza_testo": pages_needing_ocr,
        "serve_ocr": bool(pages_needing_ocr),
        "codifica_rotta": bool(getattr(result, "has_encoding_issues", False)),
        "caratteri": len(markdown) if isinstance(markdown, str) else 0,
        "anteprima": preview,
        "troncato": truncated,
    }
