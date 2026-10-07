# SPDX-License-Identifier: Apache-2.0
"""Il tool `classifica_pdf`: PDF -> classificazione + pagine che servono OCR.

pdf-inspector non e' installato nell'ambiente di test del repository, quindi i
casi qui iniettano un modulo finto in `sys.modules['pdf_inspector']`: cosi'
verifichiamo il comportamento del tool (percorso, classificazione, pagine,
anteprima, errori) senza la libreria Rust e senza rete. Il solo caso "libreria
assente" usa `None` per simulare un import fallito.
"""
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

from shared import webui_tool_registry as registry
from shared.webui_custom_tools import ufficio_pdf_inspector as tool

TOOL_NAME = "classifica_pdf"


class _FakePdfError(Exception):
    pass


class _FakeResult:
    def __init__(self, pdf_type="text_based", confidence=0.99, page_count=1,
                 pages_needing_ocr=(), markdown=None, has_encoding_issues=False):
        self.pdf_type = pdf_type
        self.confidence = confidence
        self.page_count = page_count
        self.pages_needing_ocr = list(pages_needing_ocr)
        self.markdown = markdown
        self.has_encoding_issues = has_encoding_issues


def _fake_pdf_inspector(result=None, boom=None):
    module = types.ModuleType("pdf_inspector")
    module.PdfError = _FakePdfError

    def process_pdf(path, pages=None):
        if boom is not None:
            raise boom
        return result

    module.process_pdf = process_pdf
    return module


class PdfInspectorToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.share = Path(self.temp.name) / "share"
        self.share.mkdir()
        self._old_env = os.environ.get("WEBUI_SHARE_DIR")
        os.environ["WEBUI_SHARE_DIR"] = str(self.share)
        self.addCleanup(self._restore_env)
        self.addCleanup(self._clear_module)

    def _restore_env(self):
        if self._old_env is None:
            os.environ.pop("WEBUI_SHARE_DIR", None)
        else:
            os.environ["WEBUI_SHARE_DIR"] = self._old_env

    def _clear_module(self):
        sys.modules.pop("pdf_inspector", None)

    def _install(self, module):
        sys.modules["pdf_inspector"] = module

    def _pdf(self, name="report.pdf", data=b"%PDF-1.7"):
        path = self.share / name
        path.write_bytes(data)
        return path

    def test_tool_is_registered_with_a_bounded_schema(self):
        tools = registry.load_tools()
        self.assertIn(TOOL_NAME, tools)
        item = tools[TOOL_NAME]
        self.assertEqual(item.required, ["percorso"])
        self.assertEqual(item.properties["percorso"]["type"], "string")
        self.assertEqual(item.properties["estrai_markdown"]["type"], "boolean")
        self.assertEqual(item.properties["estrai_markdown"]["default"], False)
        self.assertEqual(item.properties["anteprima_caratteri"]["type"], "integer")
        self.assertEqual(item.properties["anteprima_caratteri"]["default"], tool.DEFAULT_PREVIEW_CHARS)

    def test_classification_reports_pages_needing_ocr(self):
        self._pdf()
        self._install(_fake_pdf_inspector(result=_FakeResult(
            pdf_type="mixed", confidence=0.75, page_count=5,
            pages_needing_ocr=(2, 4), has_encoding_issues=True)))
        result = tool.classifica_pdf("report.pdf")
        self.assertEqual(result["pdf_type"], "mixed")
        self.assertEqual(result["confidenza"], 0.75)
        self.assertEqual(result["pagine"], 5)
        self.assertEqual(result["pagine_senza_testo"], [2, 4])
        self.assertTrue(result["serve_ocr"])
        self.assertTrue(result["codifica_rotta"])
        self.assertEqual(result["caratteri"], 0)
        self.assertEqual(result["anteprima"], "")
        self.assertFalse(result["troncato"])

    def test_text_based_pdf_needs_no_ocr(self):
        self._pdf("nativo.pdf")
        self._install(_fake_pdf_inspector(result=_FakeResult(pdf_type="text_based", page_count=3)))
        result = tool.classifica_pdf("nativo.pdf")
        self.assertEqual(result["pagine_senza_testo"], [])
        self.assertFalse(result["serve_ocr"])

    def test_markdown_preview_is_bounded_when_requested(self):
        self._pdf()
        markdown = "# Titolo\n\n" + ("contenuto " * 500)
        self._install(_fake_pdf_inspector(result=_FakeResult(markdown=markdown, page_count=1)))
        result = tool.classifica_pdf("report.pdf", estrai_markdown=True, anteprima_caratteri=20)
        self.assertEqual(result["anteprima"], markdown[:20])
        self.assertEqual(result["caratteri"], len(markdown))
        self.assertTrue(result["troncato"])

    def test_markdown_not_returned_unless_requested(self):
        self._pdf()
        self._install(_fake_pdf_inspector(result=_FakeResult(markdown="testo" * 10)))
        result = tool.classifica_pdf("report.pdf")
        self.assertEqual(result["anteprima"], "")
        self.assertEqual(result["caratteri"], 0)

    def test_rejects_paths_outside_share_missing_and_unsupported(self):
        (self.share / "note.txt").write_text("ciao", encoding="utf-8")
        self._install(_fake_pdf_inspector(result=_FakeResult()))
        for percorso in ("../fuori.pdf", str(self.share.resolve() / "report.pdf"), "",
                         "manca.pdf", "note.txt"):
            with self.subTest(percorso=percorso), self.assertRaises(ValueError):
                tool.classifica_pdf(percorso)

    def test_preview_chars_is_validated(self):
        self._pdf()
        self._install(_fake_pdf_inspector(result=_FakeResult()))
        for value in (-1, tool.MAX_PREVIEW_CHARS + 1, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                tool.classifica_pdf("report.pdf", anteprima_caratteri=value)

    def test_missing_pdf_inspector_gives_an_actionable_error(self):
        self._pdf()
        sys.modules["pdf_inspector"] = None  # import fallito
        with self.assertRaises(ValueError) as caught:
            tool.classifica_pdf("report.pdf")
        self.assertIn("pdf-inspector", str(caught.exception))

    def test_library_error_is_reported_with_its_type(self):
        self._pdf()
        self._install(_fake_pdf_inspector(boom=_FakePdfError("PDF corrotto")))
        with self.assertRaises(ValueError) as caught:
            tool.classifica_pdf("report.pdf")
        self.assertIn("PdfError", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
