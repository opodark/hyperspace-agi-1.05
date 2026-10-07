# SPDX-License-Identifier: Apache-2.0
import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "webui_tool.py"
spec = importlib.util.spec_from_file_location("webui_tool_cli", SCRIPT)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class CLITests(unittest.TestCase):
    def test_new_creates_one_editable_file_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            old = cli.PLUGIN_DIR
            cli.PLUGIN_DIR = Path(directory)
            try:
                path = cli.create("mio_tool")
                self.assertIn("def mio_tool", path.read_text())
                with self.assertRaises(FileExistsError):
                    cli.create("mio_tool")
                with self.assertRaises(ValueError):
                    cli.check()
            finally:
                cli.PLUGIN_DIR = old


if __name__ == "__main__":
    unittest.main()
