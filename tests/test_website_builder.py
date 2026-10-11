# SPDX-License-Identifier: Apache-2.0
import ast
import json
import os
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from shared.website_builder import WebsiteStore, build_site, import_reference_html


class WebsiteBuilderTests(unittest.TestCase):
    def test_build_escapes_content_and_is_responsive(self):
        project = build_site("Studio <O>", "Siti & consulenza", headline="Cresci <ora>")
        page = project["files"]["index.html"]
        self.assertIn("&lt;ora&gt;", page)
        self.assertIn('name="viewport"', page)
        self.assertIn("@media", project["files"]["styles.css"])

    def test_save_and_zip(self):
        with tempfile.TemporaryDirectory() as root:
            store = WebsiteStore(root)
            project_id = store.save(build_site("Studio", "Una landing"))
            bundle = store.bundle(project_id)
            self.assertTrue(Path(bundle).is_file())
            with zipfile.ZipFile(bundle) as archive:
                self.assertEqual(set(archive.namelist()),
                                 {"index.html", "styles.css", "app.js", "manifest.json"})

    def test_store_restituisce_lo_stesso_id_del_manifest(self):
        """Regressione del tool create_website: l'ID non è al livello root."""
        with tempfile.TemporaryDirectory() as root:
            project = build_site("Atelier", "Portfolio creativo")
            project_id = WebsiteStore(root).save(project)
            self.assertEqual(project_id, project["manifest"]["id"])
            self.assertNotIn("id", project)

    def test_store_elenca_i_progetti_persistiti(self):
        with tempfile.TemporaryDirectory() as root:
            store = WebsiteStore(root)
            project = build_site("Studio", "Portfolio")
            store.save(project)
            listed = store.list()
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["id"], project["manifest"]["id"])

    def test_rejects_unknown_template(self):
        with self.assertRaises(ValueError):
            build_site("Studio", "Brief", template="wordpress")

    def test_importa_solo_immagini_citate_dall_html(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
            root = Path(source)
            (root / "HyperSpace").mkdir()
            (root / "HyperSpace" / "anna.jpg").write_bytes(b"jpeg-test")
            (root / "raccolta.html").write_text(
                '<img src="file:///Users/opo/ComfyUI-Shared/output/HyperSpace/anna.jpg">',
                encoding="utf-8")
            project = build_site("Anna", "Showcase")
            imported = import_reference_html(project, source, "raccolta.html")
            self.assertEqual(imported, ["assets/anna.jpg"])
            project_id = WebsiteStore(target).save(project)
            self.assertEqual((Path(target) / project_id / "assets" / "anna.jpg").read_bytes(),
                             b"jpeg-test")
            self.assertIn("assets/anna.jpg", project["files"]["index.html"])


class WebsiteStatusToolTests(unittest.TestCase):
    """Il verifier legge l'artefatto col tool, non con la prosa del coder.

    `create_website` scrive **fuori** dalla sandbox: senza un lettore dedicato il
    verifier della missione può solo credere a quel che il coder racconta (visto
    il 2026-10-06: il task di verifica è morto cercando un workspace sandbox che
    non esisteva). `_tool_website_status` è estratto dal VERO
    `control-plane/main.py` con `ast` ed eseguito su un sito scritto davvero:
    nessun import di Flask, nessun server.
    """

    @staticmethod
    def _status_tool(website_dir, base_url="http://localhost:8085"):
        source = (Path(__file__).parents[1] / "control-plane" / "main.py").read_text(
            encoding="utf-8")
        module = ast.Module(
            body=[node for node in ast.parse(source).body
                  if isinstance(node, ast.FunctionDef)
                  and node.name == "_tool_website_status"],
            type_ignores=[])
        namespace = {"WEBSITE_DIR": website_dir, "BUILDER_PUBLIC_BASE_URL": base_url,
                     "WebsiteStore": WebsiteStore, "os": os, "re": re, "json": json}
        exec(compile(module, "<website-status>", "exec"), namespace)
        return namespace["_tool_website_status"]

    @staticmethod
    def _site(source, target, images=3):
        root = Path(source)
        (root / "HyperSpace").mkdir(exist_ok=True)
        markup = []
        for index in range(images):
            (root / "HyperSpace" / f"anna{index}.jpg").write_bytes(b"jpeg-test")
            markup.append('<img src="file:///Users/opo/ComfyUI-Shared/output/'
                          f'HyperSpace/anna{index}.jpg">')
        (root / "raccolta.html").write_text("".join(markup), encoding="utf-8")
        project = build_site("Anna", "Showcase", template="showcase")
        import_reference_html(project, source, "raccolta.html")
        return WebsiteStore(target).save(project)

    def test_counts_the_images_the_page_really_has(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
            project_id = self._site(source, target, images=3)
            result = json.loads(self._status_tool(target)({"project_id": project_id}))
            self.assertTrue(result["ok"])
            self.assertEqual(result["project_id"], project_id)
            self.assertEqual(result["images_in_page"], 3)
            self.assertTrue(result["has_gallery"])
            self.assertEqual(result["assets_on_disk"], 3)
            self.assertEqual(result["source_html"], "raccolta.html")
            self.assertEqual(result["template"], "showcase")
            self.assertFalse(result["applied"])
            self.assertEqual(result["preview_url"],
                             f"http://localhost:8085/website/preview/{project_id}/")

    def test_a_traversal_attempt_is_reduced_to_a_clean_error(self):
        with tempfile.TemporaryDirectory() as target:
            result = json.loads(self._status_tool(target)({"project_id": "../../etc"}))
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"], "progetto non trovato")

    def test_without_a_project_id_it_lists_what_exists(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
            project_id = self._site(source, target, images=1)
            result = json.loads(self._status_tool(target)({}))
            self.assertFalse(result["ok"])
            self.assertEqual(result["projects"], [project_id])


if __name__ == "__main__":
    unittest.main()
