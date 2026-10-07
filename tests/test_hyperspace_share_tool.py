# SPDX-License-Identifier: Apache-2.0
import importlib.util
import tempfile
import unittest
from pathlib import Path


TOOL = Path(__file__).resolve().parents[1] / "openwebui-tools" / "hyperspace_share.py"
spec = importlib.util.spec_from_file_location("hyperspace_share_tool", TOOL)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ShareToolTests(unittest.TestCase):
    def test_create_read_and_reject_escape_or_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            original_root = module.ROOT
            module.ROOT = Path(directory)
            try:
                tool = module.Tools()
                self.assertIn("sottocartella", tool.Valves.model_fields)
                self.assertIn("max_lettura_byte", tool.Valves.model_fields)
                self.assertIn("Creato e verificato", tool.scrivi_testo_share("note/uno.txt", "ciao"))
                self.assertEqual(tool.leggi_testo_share("note/uno.txt"), "ciao")
                self.assertIn("FILE uno.txt", tool.elenco_share("note"))
                self.assertIn("File già esistente", tool.scrivi_testo_share("note/uno.txt", "altro"))
                self.assertEqual(tool.leggi_testo_share("note/uno.txt"), "ciao")
                self.assertIn("Percorso esterno", tool.scrivi_testo_share("../fuori.txt", "no"))
                tool.valves.sottocartella = "note"
                self.assertEqual(tool.leggi_testo_share("uno.txt"), "ciao")
                self.assertIn("Percorso esterno", tool.leggi_testo_share("../altro.txt"))
            finally:
                module.ROOT = original_root


if __name__ == "__main__":
    unittest.main()
