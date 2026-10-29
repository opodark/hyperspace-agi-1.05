# SPDX-License-Identifier: Apache-2.0
"""Motion Reels: ogni reel in `integrations/tiktok_editor/motion/reels/` deve comporsi.

Non registra video (servirebbero Chromium e ffmpeg): verifica che il build
produca una pagina autonoma e, se `node` c'è, che lo script assemblato sia
JavaScript valido. Gira con l'interprete del repository, senza dipendenze extra.
"""
import importlib.util
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOTION = ROOT / "integrations" / "tiktok_editor" / "motion"

_spec = importlib.util.spec_from_file_location("motion_build", MOTION / "build.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)


class TestMotionReels(unittest.TestCase):
    def test_ci_sono_reel(self):
        self.assertIn("rd-2026-10-27", build.reel_ids())
        self.assertIn("resilienza-2026-10-28", build.reel_ids())

    def _pagine(self):
        for rid in build.reel_ids():
            js = (MOTION / "reels" / f"{rid}.js").read_text(encoding="utf-8")
            for fmt in build.read_meta(js, rid)["formats"]:
                yield rid, fmt

    def test_ogni_reel_si_compone(self):
        for rid, fmt in self._pagine():
            with self.subTest(reel=rid, formato=fmt):
                page, meta = build.build_page(rid, fmt)
                w, h = build.SIZES[fmt]
                self.assertIn(f'width="{w}" height="{h}"', page)
                self.assertIn(f'"dur": {meta["dur"]}', page)
                self.assertIn(f"<title>{meta['title']}</title>", page)
                self.assertNotIn("{{", page, "segnaposto non sostituito")
                self.assertEqual(page.count("@font-face"), len(build.FONTS))
                self.assertIn("window.__renderAt = frame", page)
                self.assertIn("const REEL = {", page)
                self.assertNotIn("SPDX-License-Identifier", page.split("<script>", 1)[1])

    def test_scene_e_tagli_in_ordine(self):
        for rid in build.reel_ids():
            js = (MOTION / "reels" / f"{rid}.js").read_text(encoding="utf-8")
            with self.subTest(reel=rid):
                dur = build.read_meta(js, rid)["dur"]
                tagli = [float(v) for v in re.search(r"cuts: \[([^\]]*)\]", js).group(1).split(",")]
                self.assertEqual(tagli, sorted(tagli))
                self.assertTrue(all(0 < v < dur for v in tagli))
                scene = re.search(r"scenes: \[([^\]]*)\]", js).group(1).split(",")
                for nome in scene:
                    self.assertRegex(js, rf"function {nome.strip()}\(t\)")

    @unittest.skipUnless(shutil.which("node"), "node non disponibile")
    def test_script_assemblato_e_valido(self):
        for rid, fmt in self._pagine():
            page, _ = build.build_page(rid, fmt)
            script = page.split("<script>", 1)[1].rsplit("</script>", 1)[0]
            with tempfile.TemporaryDirectory() as tmp, self.subTest(reel=rid, formato=fmt):
                f = Path(tmp) / "reel.js"
                f.write_text(script, encoding="utf-8")
                esito = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
                self.assertEqual(esito.returncode, 0, esito.stderr)

    def test_le_parti_esistono_e_non_si_annidano(self):
        for rid in build.reel_ids():
            meta = build.read_meta((MOTION / "reels" / f"{rid}.js").read_text(encoding="utf-8"), rid)
            for parte in meta["parts"]:
                with self.subTest(reel=rid, parte=parte):
                    self.assertIn(parte, build.reel_ids())
                    js = (MOTION / "reels" / f"{parte}.js").read_text(encoding="utf-8")
                    self.assertEqual(build.read_meta(js, parte)["parts"], [])

    def test_formato_sconosciuto_rifiutato(self):
        with self.assertRaises(SystemExit):
            build.build_page("rd-2026-10-27", "16:9")

    def test_i_font_hanno_la_licenza(self):
        for nome in ("LICENSE-Inter.txt", "LICENSE-DejaVu.txt"):
            self.assertTrue((MOTION / "fonts" / nome).exists(), nome)


if __name__ == "__main__":
    unittest.main()
