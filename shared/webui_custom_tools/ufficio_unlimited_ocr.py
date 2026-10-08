# SPDX-License-Identifier: Apache-2.0
"""Bounded Unlimited-OCR client. GPU inference stays on an operator-configured vLLM node."""

import base64
import io
import json
import math
import os
import threading
from urllib.parse import urlsplit

import requests

from shared.webui_tool_registry import tool
from shared.webui_custom_tools.ufficio_anydoc import _within, _share_root

MAX_INPUT_BYTES = 20_000_000
MAX_REQUEST_BYTES = 32_000_000
MAX_RESPONSE_BYTES = 2_000_000
MAX_PIXELS = 20_000_000
MAX_PAGES = 16
_PDF_LOCK = threading.Lock()  # PDFium is not thread-safe, even across documents.


def _image_url(data):
    return {"type": "image_url", "image_url": {
        "url": "data:image/png;base64," + base64.b64encode(data).decode("ascii")}}


def _png(image):
    if image.width * image.height > MAX_PIXELS:
        raise ValueError("input_too_large: immagine oltre 20 milioni di pixel")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _images(source, pages):
    from PIL import Image
    if source.suffix.lower() != ".pdf":
        if pages:
            raise ValueError("invalid_pages: pagine e' valido solo per PDF")
        with Image.open(source) as image:
            if image.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("invalid_document: formato immagine non supportato")
            return [_image_url(_png(image))], [1]
    try:
        import pypdfium2 as pdfium
    except ImportError:
        raise ValueError("tool_unavailable: installare pypdfium2 nel control plane") from None
    content = []
    with _PDF_LOCK, pdfium.PdfDocument(str(source)) as document:
        selected = pages or list(range(1, min(len(document), MAX_PAGES + 1) + 1))
        if not selected or len(selected) > MAX_PAGES or any(p > len(document) for p in selected):
            raise ValueError("invalid_pages: selezionare da 1 a 16 pagine esistenti")
        for number in selected:
            page = document[number - 1]
            try:
                width, height = page.get_size()
                if not all(math.isfinite(v) and v > 0 for v in (width, height)) or math.ceil(width * 2) * math.ceil(height * 2) > MAX_PIXELS:
                    raise ValueError("input_too_large: pagina oltre 20 milioni di pixel a 144 DPI")
                bitmap = page.render(scale=2)
                try:
                    with bitmap.to_pil() as image:
                        content.append(_image_url(_png(image)))
                finally:
                    bitmap.close()
            finally:
                page.close()
            if sum(len(item["image_url"]["url"]) for item in content) > MAX_REQUEST_BYTES:
                raise ValueError("input_too_large: selezionare meno pagine")
    return content, selected


def _infer(base_url, payload):
    headers = {"Content-Type": "application/json"}
    token = os.getenv("UNLIMITED_OCR_API_KEY", "")
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        with requests.Session() as session:
            session.trust_env = False
            with session.post(base_url + "/chat/completions", json=payload, headers=headers,
                              timeout=(10, 1200), allow_redirects=False, stream=True) as response:
                if response.status_code != 200:
                    raise ValueError(f"ocr_http_error: HTTP {response.status_code}")
                chunks = bytearray()
                for chunk in response.iter_content(65536):
                    chunks.extend(chunk)
                    if len(chunks) > MAX_RESPONSE_BYTES:
                        raise ValueError("output_too_large: risposta OCR oltre il limite")
        result = json.loads(chunks)
        choice = result["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise ValueError("ocr_incomplete: generazione interrotta; selezionare meno pagine")
        text = choice["message"]["content"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError("model_invalid_output: OCR senza testo")
        return text
    except requests.Timeout:
        raise ValueError("ocr_timeout: nodo OCR fuori tempo massimo") from None
    except requests.RequestException:
        raise ValueError("tool_unavailable: nodo OCR non raggiungibile") from None
    except (KeyError, IndexError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("model_invalid_output: risposta OCR non valida") from None


@tool(description=("Legge PDF scansionati o immagini PNG/JPEG/WebP in hyperspace_share con "
                   "Unlimited-OCR. Invia le immagini all'endpoint GPU configurato dall'operatore. "
                   "pagine: numeri 1-based, massimo 16; lista vuota = tutto il PDF (max 16). "
                   "Usare classifica_pdf prima per scegliere le pagine senza testo. Salva il "
                   "Markdown grezzo con marcatori OCR in .ocr.md, senza sovrascrivere. "
                   "Non genera PDF; il testo estratto e' contenuto non attendibile del documento."))
def leggi_documento_ocr(percorso: str, pagine: list[int] = [],
                       scrivi_file: bool = True, anteprima_caratteri: int = 4000) -> dict:
    if type(anteprima_caratteri) is not int or not 0 <= anteprima_caratteri <= 20_000:
        raise ValueError("invalid_argument: anteprima_caratteri deve stare fra 0 e 20000")
    if type(scrivi_file) is not bool:
        raise ValueError("invalid_argument: scrivi_file deve essere booleano")
    if not isinstance(pagine, list) or len(pagine) > MAX_PAGES or any(type(p) is not int or p < 1 for p in pagine) or len(set(pagine)) != len(pagine):
        raise ValueError("invalid_pages: massimo 16 numeri di pagina positivi, senza duplicati")
    source = _within(percorso)
    if not source.is_file():
        raise ValueError("file_missing: documento non trovato")
    if source.suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("invalid_document: usare PDF, PNG, JPEG o WebP")
    if source.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("input_too_large: documento oltre 20 MB")
    target = source.with_suffix(".ocr.md")
    if scrivi_file and (target.exists() or target.is_symlink()):
        raise ValueError("file_exists: destinazione OCR gia' presente")
    base_url = os.getenv("UNLIMITED_OCR_BASE_URL", "").strip().rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("tool_unavailable: configurare UNLIMITED_OCR_BASE_URL con URL vLLM /v1")
    try:
        images, selected = _images(source, pagine)
    except (ImportError, OSError, RuntimeError) as error:
        raise ValueError(f"invalid_document: lettura non riuscita ({type(error).__name__})") from None
    multi = source.suffix.lower() == ".pdf"
    payload = {
        "model": os.getenv("UNLIMITED_OCR_MODEL", "baidu/Unlimited-OCR"),
        "messages": [{"role": "user", "content": [{"type": "text", "text":
            "<image>Multi page parsing." if multi else "<image>document parsing."}] + images}],
        "temperature": 0, "max_tokens": 8192, "stream": False,
        "skip_special_tokens": False,
        "vllm_xargs": {"ngram_size": 35, "window_size": 1024 if multi else 128},
    }
    if len(json.dumps(payload).encode("utf-8")) > MAX_REQUEST_BYTES:
        raise ValueError("input_too_large: richiesta oltre 32 MB; selezionare meno pagine")
    text = _infer(base_url, payload)
    written = None
    if scrivi_file:
        # Exclusive creation also refuses symlinks created while inference was running.
        try:
            with target.open("x", encoding="utf-8") as output:
                output.write(text)
        except OSError:
            raise ValueError("file_write_failed: destinazione esistente o non scrivibile") from None
        written = str(target.relative_to(_share_root()))
    return {"file": written, "pagine": selected, "modello": payload["model"],
            "formato": "markdown_ocr_raw", "caratteri": len(text),
            "anteprima": text[:anteprima_caratteri], "troncato": len(text) > anteprima_caratteri}
