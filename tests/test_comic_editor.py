# SPDX-License-Identifier: Apache-2.0
import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ComicEditorIntegrationTests(unittest.TestCase):
    def test_vendor_editor_is_pinned_and_keeps_mit_license(self):
        vendor = ROOT / "control-plane" / "vendor" / "panel-foundry"
        self.assertTrue((vendor / "index.html").is_file())
        self.assertIn("MIT License", (vendor / "LICENSE").read_text(encoding="utf-8"))

    def test_image_copies_the_editor_in_the_same_path_used_by_the_route(self):
        dockerfile = (ROOT / "control-plane" / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY control-plane/vendor ./vendor", dockerfile)

    def test_editor_uses_hyperspace_storage_and_generation(self):
        page = (ROOT / "control-plane" / "vendor" / "panel-foundry" / "index.html").read_text(encoding="utf-8")
        self.assertIn("/editor-data", page)
        self.assertIn("/generate`,", page)
        self.assertIn("btn-hs-save", page)
        self.assertIn("generateImage=async function(panel)", page)
        self.assertIn("ACCODA IMMAGINE", page)
        self.assertIn("modal-guide", page)
        self.assertIn("/panels/${panel.hsPanelNumber}/render", page)
        self.assertIn("p.hsEpisodeId=page.episodeId", page)

    def test_control_plane_exposes_catalog_and_editor(self):
        source = (ROOT / "control-plane" / "main.py").read_text(encoding="utf-8")
        self.assertIn("@app.route('/comics')", source)
        self.assertIn("@app.route('/comic/editor')", source)
        self.assertIn("/editor-data", source)
        self.assertIn('"vendor", "panel-foundry"', source)
        self.assertIn("def _reconcile_comic_project", source)
        self.assertIn("if _reconcile_comic_project(project):", source)

    def test_catalog_can_create_a_project_before_opening_the_editor(self):
        page = (ROOT / "control-plane" / "comics.html").read_text(encoding="utf-8")
        self.assertIn('id="create"', page)
        self.assertIn("method:'POST'", page)
        self.assertIn("/comic/editor?project=", page)

    def test_tool_uses_keyword_only_builder_contract(self):
        source = (ROOT / "control-plane" / "main.py").read_text(encoding="utf-8")
        self.assertIn('comic_add_character(project, name=', source)
        self.assertIn('comic_add_episode(project,\n                                title=', source)

    def test_chat_tool_queues_panels_unless_storyboard_is_requested(self):
        source = ((ROOT / "control-plane" / "main.py").read_text(encoding="utf-8")
                  + (ROOT / "control-plane" / "cp" / "tools_defs.py").read_text(encoding="utf-8"))
        self.assertIn('args.get("render_panels", True)', source)
        self.assertIn('"queued_jobs": queued', source)
        tree = ast.parse((ROOT / "control-plane" / "cp" / "tools_defs.py").read_text(encoding="utf-8"))
        extension = next(n for n in tree.body if isinstance(n, ast.Expr)
                         and isinstance(n.value, ast.Call)
                         and isinstance(n.value.func, ast.Attribute)
                         and n.value.func.attr == "extend")
        comic = next(tool for tool in ast.literal_eval(extension.value.args[0])
                     if tool["function"]["name"] == "create_comic")
        self.assertEqual(comic["function"]["parameters"]["properties"]["render_panels"]["default"], True)


if __name__ == "__main__":
    unittest.main()
