# SPDX-License-Identifier: Apache-2.0
"""Test suite per l'adattatore dataset Unsloth (shared/unsloth_dataset_adapter.py)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from shared.unsloth_dataset_adapter import UnslothDatasetAdapter, SYSTEM_PROMPT_DEFAULT


class TestUnslothDatasetAdapter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir)
        self.traces_dir = self.data_dir / "traces"
        self.traces_dir.mkdir(parents=True, exist_ok=True)

        # File CoT sintetico simulato
        synthetic_file = self.data_dir / "synthetic_cot_dataset.jsonl"
        with open(synthetic_file, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "prompt_topic": "Crea una classe di lock distribuito",
                "distilled_cot": "class DistributedLock: pass",
                "verified": True,
            }) + "\n")
            f.write(json.dumps({
                "prompt_topic": "Codice non valido da scartare",
                "distilled_cot": "broken",
                "verified": False,
            }) + "\n")

        # Traccia NDJSON simulata
        trace_file = self.traces_dir / "test_session.ndjson"
        with open(trace_file, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "event": "tool_call",
                "tool": "code_sandbox",
                "arguments": {"action": "read", "path": "main.py"},
                "result_summary": "file_contents",
                "ok": True,
            }) + "\n")
            f.write(json.dumps({
                "event": "tool_call",
                "tool": "broken_tool",
                "arguments": {},
                "ok": False,
            }) + "\n")

        self.adapter = UnslothDatasetAdapter(data_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_extract_from_synthetic_cot(self):
        samples = self.adapter.extract_from_synthetic_cot()
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0]["instruction"], "Crea una classe di lock distribuito")
        self.assertEqual(samples[0]["output"], "class DistributedLock: pass")
        self.assertEqual(samples[0]["system"], SYSTEM_PROMPT_DEFAULT)

    def test_extract_from_ndjson_traces(self):
        samples = self.adapter.extract_from_ndjson_traces()
        self.assertEqual(len(samples), 1)
        self.assertIn("code_sandbox", samples[0]["instruction"])
        self.assertIn("file_contents", samples[0]["output"])

    def test_export_alpaca_json(self):
        out_file = self.data_dir / "alpaca.json"
        count = self.adapter.export_alpaca_json(str(out_file), include_traces=True)
        self.assertEqual(count, 2)
        self.assertTrue(out_file.exists())

        with open(out_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data), 2)
        self.assertIn("instruction", data[0])
        self.assertIn("output", data[0])


if __name__ == "__main__":
    unittest.main()
