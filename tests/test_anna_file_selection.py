# SPDX-License-Identifier: Apache-2.0
"""Il tool Open WebUI deve copiare solo immagini della cartella condivisa."""

import importlib.util
import tempfile
import unittest
from pathlib import Path


TOOL = Path(__file__).resolve().parents[1] / "openwebui-tools" / "anna_file_selection.py"
spec = importlib.util.spec_from_file_location("anna_file_selection", TOOL)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SelectionTests(unittest.TestCase):
    def test_copia_verificata_e_protezione_percorsi(self):
        with tempfile.TemporaryDirectory() as directory:
            original_root = module.ROOT
            module.ROOT = Path(directory)
            try:
                (module.ROOT / "anna.jpg").write_bytes(b"image")
                tool = module.Tools()
                self.assertIn("anna.jpg", tool.elenco_immagini_anna())
                self.assertIn("Copiate e verificate 1/1",
                              tool.copia_immagini_anna(["anna.jpg"], "selezionate"))
                self.assertEqual((module.ROOT / "Anna_selezionate" / "anna.jpg").read_bytes(), b"image")
                self.assertTrue((module.ROOT / "anna.jpg").exists())
                self.assertIn("Nome file non valido",
                              tool.copia_immagini_anna(["../anna.jpg"], "da_rivedere"))
                self.assertFalse((module.ROOT / "Anna_da_rivedere").exists())
            finally:
                module.ROOT = original_root


if __name__ == "__main__":
    unittest.main()
