# SPDX-License-Identifier: Apache-2.0
import io
import json
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

import shared.laya_client as laya


class LayaClientUnitTests(unittest.TestCase):
    def setUp(self):
        self.original_enabled = laya.LAYA_ENABLED
        laya.LAYA_ENABLED = True

    def tearDown(self):
        laya.LAYA_ENABLED = self.original_enabled

    @patch("urllib.request.urlopen")
    def test_is_available_when_healthy(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        self.assertTrue(laya.is_available("http://127.0.0.1:8098"))

    @patch("urllib.request.urlopen")
    def test_is_available_when_offline(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        self.assertFalse(laya.is_available("http://127.0.0.1:8098"))

    def test_disabled_by_env_returns_false_or_none(self):
        laya.LAYA_ENABLED = False
        self.assertFalse(laya.is_available())
        self.assertIsNone(laya.predict("test", {}))
        self.assertIsNone(laya.decide_choice("test", {"a": "c"}, "inst"))
        self.assertIsNone(laya.decide_noul("test", "inst"))
        self.assertIsNone(laya.decide_score("test", ["a", "b"], "inst"))

    @patch("urllib.request.urlopen")
    def test_decide_choice_success(self, mock_urlopen):
        payload = {
            "answers": {
                "verdict": {
                    "choice": "pass",
                    "confidence": 0.95,
                    "probabilities": {"pass": 0.95, "retry": 0.05},
                    "abstention": False,
                }
            },
            "routing": {"model": "english"},
        }
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = laya.decide_choice(
            "Task is complete and verified",
            {"pass": "complete", "retry": "incomplete"},
            "Judge task status",
            question_id="verdict",
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["choice"], "pass")
        self.assertAlmostEqual(res["confidence"], 0.95)
        self.assertFalse(res["abstention"])
        self.assertEqual(res["model_used"], "english")

    @patch("urllib.request.urlopen")
    def test_decide_noul_success(self, mock_urlopen):
        payload = {
            "answers": {
                "is_urgent": {
                    "noul": 0.89,
                    "confidence": 0.78,
                    "abstention": False,
                }
            },
            "routing": {"model": "multilingual"},
        }
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = laya.decide_noul(
            "Sistema fermo in produzione, serve intervento immediato",
            "Is this an urgent production emergency?",
            question_id="is_urgent",
        )
        self.assertIsNotNone(res)
        self.assertTrue(res["is_yes"])
        self.assertAlmostEqual(res["noul"], 0.89)
        self.assertEqual(res["model_used"], "multilingual")

    @patch("urllib.request.urlopen")
    def test_decide_score_success(self, mock_urlopen):
        payload = {
            "answers": {
                "priority": {
                    "score": 2.1,
                    "confidence": 0.82,
                }
            },
            "routing": {"model": "english"},
        }
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        levels = ["low", "medium", "critical"]
        res = laya.decide_score(
            "Critical security vulnerability found",
            levels,
            "Assess vulnerability severity",
            question_id="priority",
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["level_index"], 2)
        self.assertEqual(res["level_label"], "critical")
        self.assertAlmostEqual(res["score"], 2.1)

    @patch("urllib.request.urlopen")
    def test_abstention_flag_propagated(self, mock_urlopen):
        payload = {
            "answers": {
                "decision": {
                    "choice": "uncertain",
                    "confidence": 0.35,
                    "abstention": True,
                }
            },
            "routing": {"model": "multilingual"},
        }
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = laya.decide_choice("test", {"a": "c1", "b": "c2"}, "instructions")
        self.assertIsNotNone(res)
        self.assertTrue(res["abstention"])

    @patch("urllib.request.urlopen")
    def test_predict_batch(self, mock_urlopen):
        payload = [
            {"answers": {"q1": {"choice": "a"}}, "routing": {"model": "english"}},
            {"answers": {"q1": {"choice": "b"}}, "routing": {"model": "multilingual"}},
        ]
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        batch = [
            {"state": "first text", "questions": {"q1": {"type": "choice"}}},
            {"state": "second text", "questions": {"q1": {"type": "choice"}}},
        ]
        res = laya.predict_batch(batch)
        self.assertIsNotNone(res)
        self.assertEqual(len(res), 2)


if __name__ == "__main__":
    unittest.main()
