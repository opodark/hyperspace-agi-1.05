# SPDX-License-Identifier: Apache-2.0
"""Converte documenti d'ufficio in Markdown con anydoc (firecrawl-anydoc).

Tool del profilo Ufficio: legge un documento dalla cartella condivisa
(Word, PowerPoint, Excel, OpenDocument, RTF, EPUB, CSV, PDF) e scrive accanto
il Markdown corrispondente, senza inviare il file altrove. La conversione la fa
`anydoc`, la libreria Rust di Firecrawl; se il pacchetto non e' installato
nell'immagine del control-plane il tool lo dice con un errore chiaro invece di
fallire a vuoto (vedi docs/webui-tools.md). La skill testuale equivalente e'
importabile come draft dal Forge (`POST /forge/import/anydoc`).
"""

import os
from pathlib import Path

from shared.webui_tool_registry import tool

# Estensioni ammesse da anydoc. E' un filtro a monte: la libreria rileva il
# formato dal contenuto, ma qui rifiutiamo subito cio' che non e' un documento
# d'ufficio, senza doverlo leggere.
DOCUMENT_EXTENSIONS = {
    ".doc", ".docx", ".docm",                                  # Word
    ".ppt", ".pps", ".pot", ".pptx", ".pptm", ".ppsx", ".ppsm",  # PowerPoint
    ".xls", ".xlsx", ".xlsm", ".xlsb",                         # Excel
    ".odt", ".ods", ".odp",                                    # OpenDocument
    ".rtf", ".epub", ".csv", ".pdf",                           # altri supportati
}

# Tetto dell'anteprima riportata nel contesto del modello: un documento intero
# non e' un'anteprima e riempirebbe la finestra del contesto.
MAX_PREVIEW_CHARS = 20_000
# Tetto del Markdown scritto su disco: oltre, meglio non salvare affatto.
MAX_OUTPUT_BYTES = 10_000_000
DEFAULT_PREVIEW_CHARS = 4_000


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


def _load_anydoc():
    # Import locale: senza la libreria il modulo resta caricabile e il registro
    # dei tool non crolla all'avvio (l'import sta qui, non in cima al file).
    try:
        import anydoc
    except ImportError as error:
        raise ValueError(
            "anydoc non e' installato nel control plane: aggiungi 'firecrawl-anydoc' a "
            "control-plane/requirements.txt e ricostruisci il servizio (vedi docs/webui-tools.md)."
        ) from error
    return anydoc


@tool(description=("Converte un documento d'ufficio della cartella condivisa in Markdown con "
                   "anydoc: Word (.doc/.docx), PowerPoint (.ppt/.pptx), Excel (.xls/.xlsx), "
                   "OpenDocument (.odt/.ods/.odp), RTF, EPUB, CSV e PDF. Scrive il Markdown "
                   "accanto al documento e restituisce una anteprima limitata. Legge solo il "
                   "documento indicato: nessun invio a servizi esterni."))
def converti_documento_markdown(percorso: str, scrivi_file: bool = True,
                                sovrascrivi: bool = False,
                                anteprima_caratteri: int = DEFAULT_PREVIEW_CHARS) -> dict:
    if not isinstance(anteprima_caratteri, int) or isinstance(anteprima_caratteri, bool):
        raise ValueError("anteprima_caratteri deve essere un intero")
    if not 0 <= anteprima_caratteri <= MAX_PREVIEW_CHARS:
        raise ValueError(f"anteprima_caratteri deve stare fra 0 e {MAX_PREVIEW_CHARS}")

    source = _within(percorso)
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"Documento non trovato: {percorso}")
    suffix = source.suffix.lower()
    if suffix not in DOCUMENT_EXTENSIONS:
        raise ValueError(f"Formato non supportato: {suffix or '(nessuna estensione)'}")

    anydoc = _load_anydoc()
    try:
        markdown = anydoc.to_markdown(str(source))
    except OSError as error:
        raise ValueError(f"Impossibile leggere il documento: {error}") from error
    except anydoc.ConvertError as error:
        raise ValueError(f"Conversione non riuscita ({type(error).__name__}): {error}") from error
    if not isinstance(markdown, str):
        raise ValueError("anydoc non ha prodotto testo Markdown")

    written = None
    if scrivi_file:
        target = source.with_suffix(".md")
        if target == source:
            raise ValueError("Il file di destinazione coinciderebbe con la sorgente")
        if target.exists() and not sovrascrivi:
            raise ValueError(f"Esiste gia' {target.name}: passa sovrascrivi=True per rimpiazzarlo")
        if len(markdown.encode("utf-8")) > MAX_OUTPUT_BYTES:
            raise ValueError(f"Markdown oltre il limite di {MAX_OUTPUT_BYTES} byte: non salvato")
        try:
            target.write_text(markdown, encoding="utf-8")
        except OSError as error:
            raise ValueError(f"Impossibile scrivere {target.name}: {error}") from error
        written = target.name

    preview = markdown[:anteprima_caratteri]
    return {
        "file": written,
        "formato": suffix.lstrip("."),
        "caratteri": len(markdown),
        "byte": len(markdown.encode("utf-8")),
        "anteprima": preview,
        "troncato": len(markdown) > len(preview),
    }
