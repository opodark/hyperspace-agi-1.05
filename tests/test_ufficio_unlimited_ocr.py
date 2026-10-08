# SPDX-License-Identifier: Apache-2.0
import base64
import io
import json
from unittest.mock import MagicMock

import pytest
import requests
from PIL import Image

from shared import webui_tool_registry as registry
from shared.webui_custom_tools import ufficio_unlimited_ocr as ocr


@pytest.fixture
def share(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBUI_SHARE_DIR", str(tmp_path))
    monkeypatch.setenv("UNLIMITED_OCR_BASE_URL", "http://ocr-node:8000/v1")
    monkeypatch.setenv("UNLIMITED_OCR_API_KEY", "test-only")
    Image.new("RGB", (30, 20), "white").save(tmp_path / "page.png")
    return tmp_path


@pytest.fixture
def backend(monkeypatch):
    response = MagicMock()
    response.__enter__.return_value = response
    response.status_code = 200
    response.iter_content.return_value = [json.dumps({"choices": [{
        "finish_reason": "stop", "message": {"content": "# Documento\nTesto"}}]}).encode()]
    session = MagicMock()
    session.__enter__.return_value = session
    session.post.return_value = response
    monkeypatch.setattr(ocr.requests, "Session", lambda: session)
    return session, response


def test_registered_and_real_image_payload(share, backend):
    assert registry.load_tools()["leggi_documento_ocr"].required == ["percorso"]
    result = registry.execute("leggi_documento_ocr", {"percorso": "page.png", "anteprima_caratteri": 5})
    assert result["troncato"] and result["anteprima"] == "# Doc"
    assert (share / result["file"]).read_text() == "# Documento\nTesto"
    session, _ = backend
    args, kw = session.post.call_args
    assert args == ("http://ocr-node:8000/v1/chat/completions",)
    assert not session.trust_env and kw["allow_redirects"] is False
    assert kw["headers"]["Authorization"] == "Bearer test-only"
    body = kw["json"]
    assert body["skip_special_tokens"] is False
    assert body["vllm_xargs"] == {"ngram_size": 35, "window_size": 128}
    content = body["messages"][0]["content"]
    assert content[0]["text"] == "<image>document parsing."
    with Image.open(io.BytesIO(base64.b64decode(content[1]["image_url"]["url"].split(",")[1]))) as image:
        assert image.size == (30, 20)


def test_pdf_selection_and_rendering(share, backend):
    pdfium = pytest.importorskip("pypdfium2")
    with pdfium.PdfDocument.new() as document:
        for _ in range(3):
            document.new_page(72, 72).close()
        document.save(share / "scan.pdf")
    result = ocr.leggi_documento_ocr("scan.pdf", pagine=[3, 1], scrivi_file=False)
    assert result["pagine"] == [3, 1] and result["file"] is None
    body = backend[0].post.call_args.kwargs["json"]
    assert body["vllm_xargs"]["window_size"] == 1024
    assert body["messages"][0]["content"][0]["text"] == "<image>Multi page parsing."
    assert len(body["messages"][0]["content"]) == 3
    with pytest.raises(ValueError, match="invalid_pages"):
        ocr.leggi_documento_ocr("scan.pdf", pagine=[4])


def test_long_pdf_not_silently_truncated(share, backend):
    pdfium = pytest.importorskip("pypdfium2")
    with pdfium.PdfDocument.new() as document:
        for _ in range(17):
            document.new_page(72, 72).close()
        document.save(share / "long.pdf")
    with pytest.raises(ValueError, match="invalid_pages"):
        ocr.leggi_documento_ocr("long.pdf")
    backend[0].post.assert_not_called()


@pytest.mark.parametrize("kwargs", [
    {"percorso": "../page.png"}, {"percorso": "/tmp/page.png"},
    {"percorso": "missing.pdf"}, {"pagine": [True]}, {"pagine": [0]},
    {"pagine": [1, 1]}, {"pagine": [1]}, {"anteprima_caratteri": True},
    {"anteprima_caratteri": 20001}, {"scrivi_file": "false"},
])
def test_bad_inputs_never_sent(share, backend, kwargs):
    with pytest.raises(ValueError):
        ocr.leggi_documento_ocr(**({"percorso": "page.png"} | kwargs))
    backend[0].post.assert_not_called()


def test_symlinks_and_existing_output(share, backend, tmp_path):
    outside = share.parent / (share.name + "-outside.txt")
    outside.write_text("original")
    try:
        (share / "escape.png").symlink_to(outside)
        with pytest.raises(ValueError):
            ocr.leggi_documento_ocr("escape.png")
        (share / "page.ocr.md").symlink_to(outside)
        with pytest.raises(ValueError, match="file_exists"):
            ocr.leggi_documento_ocr("page.png")
        assert outside.read_text() == "original"
        backend[0].post.assert_not_called()
    finally:
        outside.unlink()


@pytest.mark.parametrize("body", [b"not-json", b"\xff", b"{}", b'{"choices":[]}',
    json.dumps({"choices": [{"finish_reason": "length", "message": {"content": "partial"}}]}).encode(),
    json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": ""}}]}).encode()])
def test_invalid_response_does_not_write(share, backend, body):
    backend[1].iter_content.return_value = [body]
    with pytest.raises(ValueError):
        ocr.leggi_documento_ocr("page.png")
    assert not (share / "page.ocr.md").exists()


@pytest.mark.parametrize("status", [302, 401, 500])
def test_http_errors_hide_body(share, backend, status):
    backend[1].status_code = status
    with pytest.raises(ValueError, match=f"ocr_http_error: HTTP {status}"):
        ocr.leggi_documento_ocr("page.png")


@pytest.mark.parametrize("error,code", [(requests.Timeout("secret"), "ocr_timeout"),
    (requests.ConnectionError("secret"), "tool_unavailable")])
def test_network_errors_redacted(share, backend, error, code):
    backend[0].post.side_effect = error
    with pytest.raises(ValueError, match=code) as caught:
        ocr.leggi_documento_ocr("page.png")
    assert "secret" not in str(caught.value)


def test_limits_and_unconfigured(share, backend, monkeypatch):
    monkeypatch.setattr(ocr, "MAX_REQUEST_BYTES", 10)
    with pytest.raises(ValueError, match="input_too_large"):
        ocr.leggi_documento_ocr("page.png")
    backend[0].post.assert_not_called()
    monkeypatch.setattr(ocr, "MAX_REQUEST_BYTES", 32_000_000)
    monkeypatch.setattr(ocr, "MAX_RESPONSE_BYTES", 2)
    with pytest.raises(ValueError, match="output_too_large"):
        ocr.leggi_documento_ocr("page.png")
    monkeypatch.delenv("UNLIMITED_OCR_BASE_URL")
    with pytest.raises(ValueError, match="tool_unavailable"):
        ocr.leggi_documento_ocr("page.png")
