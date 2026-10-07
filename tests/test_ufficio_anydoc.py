# SPDX-License-Identifier: Apache-2.0
"""Il tool `converti_documento_markdown`: documento d'ufficio -> Markdown con anydoc.

anydoc non e' installato nell'ambiente di test del repository, quindi i casi qui
iniettano un modulo finto in `sys.modules['anydoc']`: cosi' verifichiamo il
comportamento del tool (percorso, scrittura, anteprima, errori) senza la libreria
Rust e senza rete. Il solo caso "libreria assente" usa `None` per simulare un
import fallito.
"""
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

from shared import webui_tool_registry as registry
from shared.webui_custom_tools import ufficio_anydoc as tool

TOOL_NAME = "converti_documento_markdown"


class _FakeConvertError(Exception):
    pass


# Stesso nome della sottoclasse reale di anydoc: il tool riporta
# `type(error).__name__`, quindi il nome della classe finta deve coincidere.
_FakeNeedsOcr = type("NeedsOcrError", (_FakeConvertError,), {})


def _fake_anydoc(markdown="", boom=None):
    module = types.ModuleType("anydoc")
    module.ConvertError = _FakeConvertError
    module.NeedsOcrError = _FakeNeedsOcr

    def to_markdown(path, ocr=None):
        if boom is not None:
            raise boom
        return markdown

    module.to_markdown = to_markdown
    return module


class AnyDocToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.share = Path(self.temp.name) / "share"
        self.share.mkdir()
        self._old_env = os.environ.get("WEBUI_SHARE_DIR")
        os.environ["WEBUI_SHARE_DIR"] = str(self.share)
        self.addCleanup(self._restore_env)
        self.addCleanup(self._clear_anydoc)

    def _restore_env(self):
        if self._old_env is None:
            os.environ.pop("WEBUI_SHARE_DIR", None)
        else:
            os.environ["WEBUI_SHARE_DIR"] = self._old_env

    def _clear_anydoc(self):
        sys.modules.pop("anydoc", None)

    def _install(self, module):
        sys.modules["anydoc"] = module

    def _document(self, name="report.docx", data=b"documento"):
        path = self.share / name
        path.write_bytes(data)
        return path

    def test_tool_is_registered_with_a_bounded_schema(self):
        tools = registry.load_tools()
        self.assertIn(TOOL_NAME, tools)
        item = tools[TOOL_NAME]
        self.assertEqual(item.required, ["percorso"])
        self.assertEqual(item.properties["percorso"]["type"], "string")
        self.assertEqual(item.properties["scrivi_file"]["type"], "boolean")
        self.assertEqual(item.properties["sovrascrivi"]["type"], "boolean")
        self.assertEqual(item.properties["anteprima_caratteri"]["type"], "integer")
        self.assertEqual(item.properties["anteprima_caratteri"]["default"], tool.DEFAULT_PREVIEW_CHARS)

    def test_convert_writes_markdown_next_to_document_and_bounds_preview(self):
        self._document()
        markdown = "# Titolo\n\n" + ("contenuto " * 500)
        self._install(_fake_anydoc(markdown=markdown))
        result = tool.converti_documento_markdown("report.docx", anteprima_caratteri=20)
        self.assertEqual(result["file"], "report.md")
        self.assertEqual(result["formato"], "docx")
        self.assertEqual(result["caratteri"], len(markdown))
        self.assertEqual(result["byte"], len(markdown.encode("utf-8")))
        self.assertEqual(result["anteprima"], markdown[:20])
        self.assertTrue(result["troncato"])
        self.assertEqual((self.share / "report.md").read_text(encoding="utf-8"), markdown)

    def test_preview_not_truncated_when_short(self):
        self._document("breve.csv")
        self._install(_fake_anydoc(markdown="a,b\n1,2\n"))
        result = tool.converti_documento_markdown("breve.csv", anteprima_caratteri=100)
        self.assertFalse(result["troncato"])
        self.assertEqual(result["anteprima"], "a,b\n1,2\n")

    def test_existing_markdown_refused_unless_overwrite(self):
        self._document()
        (self.share / "report.md").write_text("vecchio", encoding="utf-8")
        self._install(_fake_anydoc(markdown="nuovo"))
        with self.assertRaises(ValueError):
            tool.converti_documento_markdown("report.docx")
        self.assertEqual((self.share / "report.md").read_text(encoding="utf-8"), "vecchio")
        result = tool.converti_documento_markdown("report.docx", sovrascrivi=True)
        self.assertEqual(result["file"], "report.md")
        self.assertEqual((self.share / "report.md").read_text(encoding="utf-8"), "nuovo")

    def test_scrivi_file_false_returns_preview_without_writing(self):
        self._document()
        self._install(_fake_anydoc(markdown="solo anteprima"))
        result = tool.converti_documento_markdown("report.docx", scrivi_file=False)
        self.assertIsNone(result["file"])
        self.assertEqual(result["anteprima"], "solo anteprima")
        self.assertFalse((self.share / "report.md").exists())

    def test_rejects_paths_outside_share_missing_and_unsupported(self):
        (self.share / "note.txt").write_text("ciao", encoding="utf-8")
        self._install(_fake_anydoc(markdown="x"))
        for percorso in ("../fuori.docx", str(self.share.resolve() / "report.docx"), "",
                         "manca.docx", "note.txt"):
            with self.subTest(percorso=percorso), self.assertRaises(ValueError):
                tool.converti_documento_markdown(percorso)

    def test_preview_chars_is_validated(self):
        self._document()
        self._install(_fake_anydoc(markdown="x"))
        for value in (-1, tool.MAX_PREVIEW_CHARS + 1, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                tool.converti_documento_markdown("report.docx", anteprima_caratteri=value)

    def test_missing_anydoc_gives_an_actionable_error(self):
        self._document()
        sys.modules["anydoc"] = None  # import fallito
        with self.assertRaises(ValueError) as caught:
            tool.converti_documento_markdown("report.docx")
        self.assertIn("firecrawl-anydoc", str(caught.exception))

    def test_conversion_error_is_reported_with_its_type(self):
        self._document("scansione.pdf")
        self._install(_fake_anydoc(boom=_FakeNeedsOcr("pagina 1 ha bisogno di OCR")))
        with self.assertRaises(ValueError) as caught:
            tool.converti_documento_markdown("scansione.pdf")
        self.assertIn("NeedsOcrError", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
