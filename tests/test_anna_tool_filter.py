# SPDX-License-Identifier: Apache-2.0
import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "openwebui-tools" / "anna_tool_filter.py"
spec = importlib.util.spec_from_file_location("anna_tool_filter_test", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FilterTests(unittest.TestCase):
    def test_gemma_receives_server_once(self):
        body = {"model": "🕸️ huihui_ai/gemma-4-abliterated:12b", "tool_ids": []}
        filter_ = module.Filter()
        filter_.inlet(body)
        filter_.inlet(body)
        self.assertEqual(body["tool_ids"], ["server:hyperspace-files"])

    def test_other_models_are_unchanged(self):
        body = {"model": "altro-modello", "tool_ids": []}
        module.Filter().inlet(body)
        self.assertEqual(body["tool_ids"], [])


if __name__ == "__main__":
    unittest.main()
