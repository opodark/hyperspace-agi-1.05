# SPDX-License-Identifier: Apache-2.0
"""Test per il modulo di scansione approfondita siti web (shared/website_reader.py)."""

import unittest
from unittest.mock import MagicMock, patch

from shared.website_reader import _clean_html_text, crawl_entire_website, fetch_page_markdown


class WebsiteReaderTests(unittest.TestCase):
    def test_clean_html_text(self):
        html = "<html><body><h1>Titolo</h1><script>alert(1)</script><p>Paragrafo di prova</p></body></html>"
        text = _clean_html_text(html)
        self.assertIn("Titolo", text)
        self.assertIn("Paragrafo di prova", text)
        self.assertNotIn("alert(1)", text)

    @patch("requests.get")
    def test_fetch_page_markdown_jina(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "# Pagina di Test\nContenuto estratto da Jina"
        mock_get.return_value = mock_resp

        res = fetch_page_markdown("https://example.com")
        self.assertIn("Pagina di Test", res)

    @patch("requests.get")
    def test_crawl_entire_website(self, mock_get):
        def fake_get(url, *args, **kwargs):
            m = MagicMock()
            m.status_code = 200
            if "r.jina.ai" in url:
                m.text = "Contenuto markdown di " + url
            else:
                m.text = """
                <html>
                <body>
                    <a href="/chi-siamo">Chi Siamo</a>
                    <a href="/servizi">Nostri Servizi</a>
                    <a href="https://esterna.com/altrosito">Esterno</a>
                    <p>Benvenuti nella homepage dell'azienda</p>
                </body>
                </html>
                """
            return m

        mock_get.side_effect = fake_get

        res = crawl_entire_website("https://mia-azienda.it", max_pages=3)
        self.assertTrue(res["ok"])
        self.assertEqual(res["site"], "https://mia-azienda.it")
        self.assertGreaterEqual(res["pages_crawled"], 1)
        self.assertIn("Analisi del Sito Web", res["digest"])


if __name__ == "__main__":
    unittest.main()
