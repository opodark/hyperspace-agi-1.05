# SPDX-License-Identifier: Apache-2.0
"""Modelli che ragionano sempre (qwen3:4b build 2507): il CP chiede think=true
e non ricopia il ragionamento in `content`.

Sulla mesh pubblica, il 2026-10-27, `qwen3:4b` con think=false rispondeva
"Okay, the user is saying..." per 800 token senza mai arrivare alla risposta.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control-plane"))

import cp.model_caps as model_caps  # noqa: E402


def _show(values):
    risposta = Mock(ok=True)
    risposta.json.return_value = {"capabilities": ["completion", "thinking"],
                                  "thinking": {"values": values, "default": True}}
    return risposta


class ThinkingOnlyModelTests(unittest.TestCase):
    def setUp(self):
        model_caps._THINKING_ONLY_CACHE.clear()
        self.addCleanup(model_caps._THINKING_ONLY_CACHE.clear)

    def test_ollama_show_with_only_true_means_thinking_only(self):
        with patch("requests.post", return_value=_show([True])):
            self.assertTrue(model_caps._model_thinking_only("qwen3:4b"))

    def test_hybrid_model_is_not_thinking_only(self):
        with patch("requests.post", return_value=_show([False, True])):
            self.assertFalse(model_caps._model_thinking_only("qwen3:8b"))

    def test_model_without_thinking_and_unreachable_ollama(self):
        senza = Mock(ok=True)
        senza.json.return_value = {"capabilities": ["completion", "tools"]}
        with patch("requests.post", return_value=senza):
            self.assertFalse(model_caps._model_thinking_only("granite3.3:8b"))
        with patch("requests.post", side_effect=OSError("down")):
            self.assertFalse(model_caps._model_thinking_only("remoto:7b"))

    def test_result_is_cached(self):
        with patch("requests.post", return_value=_show([True])) as show:
            model_caps._model_thinking_only("qwen3:4b")
            model_caps._model_thinking_only("qwen3:4b")
        self.assertEqual(show.call_count, 1)

    def test_env_override(self):
        with patch.object(model_caps, "_THINKING_ONLY_OVERRIDE", "qwen3:4b"), \
             patch("requests.post") as show:
            self.assertTrue(model_caps._model_thinking_only("qwen3:4b"))
            self.assertFalse(model_caps._model_thinking_only("qwen3:8b"))
        show.assert_not_called()
        with patch.object(model_caps, "_THINKING_ONLY_OVERRIDE", "off"), \
             patch("requests.post", return_value=_show([True])):
            self.assertFalse(model_caps._model_thinking_only("qwen3:4b"))


class ChatUsesThinkingOnlyTests(unittest.TestCase):
    """Il cablaggio in cp/chat.py, letto dal sorgente come fanno gli altri test
    del contratto chat: importare il modulo richiede tutto il CP."""

    SORGENTE = (Path(__file__).resolve().parents[1] / "control-plane" / "cp" / "chat.py").read_text()

    def test_think_forced_on_for_thinking_only_models(self):
        decisione = self.SORGENTE.index('data["think"] = _decide_thinking(')
        forzatura = self.SORGENTE.index('if not data["think"] and _model_thinking_only(model):')
        self.assertLess(decisione, forzatura)

    def test_reasoning_not_copied_into_content(self):
        self.assertIn("not _model_thinking_only(model):\n        _normalize_assistant_message(",
                      self.SORGENTE)
        self.assertIn('str(messaggio.get("content") or "") if _model_thinking_only(model)',
                      self.SORGENTE)


if __name__ == "__main__":
    unittest.main()
