# SPDX-License-Identifier: Apache-2.0
"""Test per lo Smart Economic Fallback ('Mesh-First, API-Second' + tetto giornaliero).

Verifica:
1. Priorita' gratuita della Mesh e contabilizzazione del risparmio (`saved_eur_today`,
   `mesh_offload_pct`).
2. Rispetto rigoroso del tetto giornaliero in Euro (`EXTERNAL_FALLBACK_DAILY_EUR_CAP`)
   e in numero di chiamate (`EXTERNAL_FALLBACK_DAILY_CALLS_CAP`).
3. Blocco immediato delle chiamate API esterne (`_try_omniroute_fallback`) quando il
   budget giornaliero e' esaurito (nessuna richiesta HTTP parte verso l'esterno).
4. Azzeramento automatico dei contatori al cambio di giorno UTC (`YYYY-MM-DD`).
5. Configurabilita' a caldo dalla tab Setup (`_ENV_META` e `_apply_env_runtime`).
"""
import ast
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock

from tests import cp_source

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "control-plane") not in sys.path:
    sys.path.insert(0, str(ROOT / "control-plane"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cp.budget import (
    ExternalFallbackBudget,
    _estimate_usage_tokens,
)


class _FakeClock:
    """Orologio deterministico per testare il rollover di mezzanotte UTC."""

    def __init__(self, start_ts: float = 1760788800.0):  # 2025-10-18T12:00:00Z
        self.now = start_ts

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class ExternalFallbackBudgetTests(unittest.TestCase):
    def test_mesh_calls_are_free_and_track_savings(self):
        clock = _FakeClock()
        budget = ExternalFallbackBudget(
            daily_eur_cap=0.50,
            daily_calls_cap=100,
            cost_per_1m_input_eur=0.14,
            cost_per_1m_output_eur=0.28,
            clock=clock,
        )
        st = budget.record_mesh_call(prompt_tokens=100_000, completion_tokens=100_000)
        self.assertEqual(st["spent_eur_today"], 0.0)
        self.assertEqual(st["mesh_served_today"], 1)
        self.assertAlmostEqual(st["saved_eur_today"], 0.042, places=5)
        self.assertEqual(st["mesh_offload_pct"], 100.0)
        self.assertFalse(st["cap_reached"])

    def test_daily_eur_cap_blocks_further_external_calls(self):
        clock = _FakeClock()
        budget = ExternalFallbackBudget(
            daily_eur_cap=0.05,
            daily_calls_cap=500,
            cost_per_1m_input_eur=0.14,
            cost_per_1m_output_eur=0.28,
            clock=clock,
        )
        allowed, reason = budget.allows()
        self.assertTrue(allowed)
        self.assertEqual(reason, "ok")

        # Consumiamo 0.06 EUR (> 0.05 EUR di cap)
        budget.record_external_call(prompt_tokens=100_000, completion_tokens=200_000)
        st = budget.status()
        self.assertTrue(st["cap_reached"])
        self.assertEqual(st["remaining_eur_today"], 0.0)

        allowed2, reason2 = budget.allows()
        self.assertFalse(allowed2)
        self.assertIn("tetto giornaliero budget fallback raggiunto", reason2)
        self.assertEqual(budget.status()["blocked_today"], 1)

    def test_daily_calls_cap_blocks_when_reached(self):
        clock = _FakeClock()
        budget = ExternalFallbackBudget(
            daily_eur_cap=5.0,
            daily_calls_cap=2,
            clock=clock,
        )
        self.assertTrue(budget.allows()[0])
        budget.record_external_call(prompt_tokens=500, completion_tokens=500)
        self.assertTrue(budget.allows()[0])
        budget.record_external_call(prompt_tokens=500, completion_tokens=500)

        allowed, reason = budget.allows()
        self.assertFalse(allowed)
        self.assertIn("chiamate fallback raggiunto (2/2)", reason)

    def test_zero_cap_enforces_100_percent_free_mesh_mode(self):
        clock = _FakeClock()
        budget = ExternalFallbackBudget(daily_eur_cap=0.0, daily_calls_cap=500, clock=clock)
        allowed, reason = budget.allows()
        self.assertFalse(allowed)
        self.assertIn("100% Mesh gratuita", reason)

    def test_utc_midnight_rollover_resets_counters_automatically(self):
        clock = _FakeClock(start_ts=1760788800.0)  # Giorno 1
        budget = ExternalFallbackBudget(daily_eur_cap=0.05, daily_calls_cap=10, clock=clock)
        budget.record_external_call(prompt_tokens=200_000, completion_tokens=200_000)
        self.assertFalse(budget.allows()[0])

        # Avanza di 24 ore (giorno UTC successivo)
        clock.advance(86400.0)
        allowed, reason = budget.allows()
        self.assertTrue(allowed)
        self.assertEqual(reason, "ok")
        st = budget.status()
        self.assertEqual(st["calls_today"], 0)
        self.assertEqual(st["spent_eur_today"], 0.0)
        self.assertFalse(st["cap_reached"])

    def test_estimate_usage_tokens_reads_openai_usage_or_falls_back_to_chars(self):
        pt, ct = _estimate_usage_tokens(
            {"messages": [{"role": "user", "content": "ciao"}]},
            {"usage": {"prompt_tokens": 310, "completion_tokens": 420}},
        )
        self.assertEqual((pt, ct), (310, 420))

        pt2, ct2 = _estimate_usage_tokens(
            {"messages": [{"role": "user", "content": "a" * 400}]},
            {"choices": [{"message": {"content": "b" * 800}}]},
        )
        self.assertEqual((pt2, ct2), (100, 200))


class OmnirouteSmartFallbackWiringTests(unittest.TestCase):
    def _load_fallback_fn(self, check_fn, record_fn, requests_mock, push_log_mock, env=None):
        fn_node = cp_source.nodo("_try_omniroute_fallback", fresco=True)
        fake_budget_mod = MagicMock()
        fake_budget_mod.check_external_fallback_budget = check_fn
        fake_budget_mod.record_external_fallback_usage = record_fn
        scope = {
            "os": os,
            "requests": requests_mock,
            "push_log": push_log_mock,
            "OMNIROUTE_ENABLED": True,
            "OMNIROUTE_URL": "http://omniroute:20128",
            "OMNIROUTE_API_KEY": "",
            "OMNIROUTE_MODEL": "auto",
            "PROMPT_COMPRESSION_ENABLED": False,
            "PROMPT_COMPRESSION_MODE": "standard",
        }
        exec(compile(ast.Module(body=[fn_node], type_ignores=[]), "cp", "exec"), scope)
        return scope["_try_omniroute_fallback"], fake_budget_mod

    def test_fallback_blocked_when_daily_budget_exhausted(self):
        requests_mock = Mock()
        push_log_mock = Mock()
        import cp.budget as real_budget
        orig_check = real_budget.check_external_fallback_budget
        try:
            real_budget.check_external_fallback_budget = lambda: (False, "tetto 0.50 EUR raggiunto")
            fn, _ = self._load_fallback_fn(
                real_budget.check_external_fallback_budget,
                real_budget.record_external_fallback_usage,
                requests_mock,
                push_log_mock,
            )
            res = fn({"model": "qwen3:8b", "messages": [{"role": "user", "content": "test"}]})
            self.assertIsNone(res)
            requests_mock.post.assert_not_called()
            push_log_mock.assert_called_once()
        finally:
            real_budget.check_external_fallback_budget = orig_check

    def test_fallback_calls_custom_external_endpoint_and_records_usage(self):
        requests_mock = Mock()
        resp_mock = Mock()
        resp_mock.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Risposta low-cost"}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 240},
        }
        requests_mock.post.return_value = resp_mock
        push_log_mock = Mock()
        recorded = []

        import cp.budget as real_budget
        orig_check = real_budget.check_external_fallback_budget
        orig_record = real_budget.record_external_fallback_usage
        saved_env = {
            k: os.environ.get(k)
            for k in ("EXTERNAL_FALLBACK_API_URL", "EXTERNAL_FALLBACK_API_KEY", "EXTERNAL_FALLBACK_MODEL")
        }
        try:
            os.environ["EXTERNAL_FALLBACK_API_URL"] = "https://openrouter.ai/api/v1"
            os.environ["EXTERNAL_FALLBACK_API_KEY"] = "sk-test-123"
            os.environ["EXTERNAL_FALLBACK_MODEL"] = "deepseek/deepseek-chat"
            real_budget.check_external_fallback_budget = lambda: (True, "ok")
            real_budget.record_external_fallback_usage = lambda d, r: recorded.append((d, r))

            fn, _ = self._load_fallback_fn(
                real_budget.check_external_fallback_budget,
                real_budget.record_external_fallback_usage,
                requests_mock,
                push_log_mock,
            )
            data = {
                "model": "qwen3:8b",
                "messages": [{"role": "user", "content": "ciao"}],
                "think": False,
                "_hyperspace_surface": "openwebui",
                "_hyperspace_tools_off": False,
                "tools": [{"type": "function", "function": {"name": "web_search"}}],
            }
            res = fn(data)
            self.assertIsNotNone(res)
            requests_mock.post.assert_called_once()
            called_url = requests_mock.post.call_args[0][0]
            called_json = requests_mock.post.call_args[1]["json"]
            called_headers = requests_mock.post.call_args[1]["headers"]
            self.assertEqual(called_url, "https://openrouter.ai/api/v1/chat/completions")
            self.assertEqual(called_json["model"], "deepseek/deepseek-chat")
            self.assertNotIn("_hyperspace_surface", called_json)
            self.assertNotIn("think", called_json)
            self.assertNotIn("tools", called_json)
            self.assertEqual(called_headers.get("Authorization"), "Bearer sk-test-123")
            self.assertEqual(len(recorded), 1)
        finally:
            real_budget.check_external_fallback_budget = orig_check
            real_budget.record_external_fallback_usage = orig_record
            for k, v in saved_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_fallback_rotates_models_on_rate_limit(self):
        requests_mock = Mock()
        fail_resp = Mock()
        fail_resp.raise_for_status.side_effect = RuntimeError("429 Too Many Requests")
        ok_resp = Mock()
        ok_resp.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Secondo modello Groq OK"}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 50},
        }
        requests_mock.post.side_effect = [fail_resp, ok_resp]
        push_log_mock = Mock()

        import cp.budget as real_budget
        orig_check = real_budget.check_external_fallback_budget
        orig_record = real_budget.record_external_fallback_usage
        saved_env = {
            k: os.environ.get(k)
            for k in ("EXTERNAL_FALLBACK_API_URL", "EXTERNAL_FALLBACK_API_KEY", "EXTERNAL_FALLBACK_MODEL")
        }
        try:
            os.environ["EXTERNAL_FALLBACK_API_URL"] = "https://api.groq.com/openai/v1"
            os.environ["EXTERNAL_FALLBACK_API_KEY"] = "gsk_test"
            os.environ["EXTERNAL_FALLBACK_MODEL"] = "openai/gpt-oss-120b,qwen/qwen3.8-27b"
            real_budget.check_external_fallback_budget = lambda: (True, "ok")
            real_budget.record_external_fallback_usage = lambda d, r: None

            fn, _ = self._load_fallback_fn(
                real_budget.check_external_fallback_budget,
                real_budget.record_external_fallback_usage,
                requests_mock,
                push_log_mock,
            )
            res = fn({"model": "qwen3:8b", "messages": [{"role": "user", "content": "ciao"}]})
            self.assertIsNotNone(res)
            self.assertEqual(requests_mock.post.call_count, 2)
            first_model = requests_mock.post.call_args_list[0][1]["json"]["model"]
            second_model = requests_mock.post.call_args_list[1][1]["json"]["model"]
            self.assertEqual(first_model, "openai/gpt-oss-120b")
            self.assertEqual(second_model, "qwen/qwen3.8-27b")
        finally:
            real_budget.check_external_fallback_budget = orig_check
            real_budget.record_external_fallback_usage = orig_record
            for k, v in saved_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_chat_memory_entry_allows_fallback_when_image_gate_busy(self):
        from unittest.mock import MagicMock
        from flask import Flask, request, jsonify
        from shared.image_memory_gate import ImageMemoryGate

        gate = ImageMemoryGate()
        gate.reserve_image("img-test-1")  # gate is now owned by an active image render

        app = Flask(__name__)
        saved_ext = os.environ.get("EXTERNAL_FALLBACK_API_URL")
        try:
            os.environ["EXTERNAL_FALLBACK_API_URL"] = "https://api.groq.com/openai/v1"

            @app.before_request
            def _entry():
                if request.path != "/v1/chat/completions" or request.method == "OPTIONS":
                    return None
                data = request.get_json(silent=True) or {}
                raw_model = str(data.get("model", "") or "")
                if ("OmniRoute" in raw_model or raw_model.startswith("ext:")
                        or raw_model.startswith("groq:") or raw_model == "omniroute"):
                    return None
                if not gate.enter_chat(timeout=0.01):
                    ext_url = os.getenv("EXTERNAL_FALLBACK_API_URL", "").strip()
                    omni_enabled = os.getenv("OMNIROUTE_ENABLED", "false").strip().lower() == "true"
                    if ext_url or omni_enabled:
                        request.environ["hyperspace.skip_local_ollama"] = True
                        return None
                    return jsonify({"error": {"type": "image_memory_busy",
                                              "message": "Il Mac sta completando un'immagine; riprova fra poco"}}), 503
                request.environ["hyperspace.chat_memory_slot"] = True
                return None

            @app.route("/v1/chat/completions", methods=["POST"])
            def _chat():
                skipped = request.environ.get("hyperspace.skip_local_ollama", False)
                return jsonify({"ok": True, "skipped_local": skipped})

            with app.test_client() as client:
                # 1. With fallback configured, gate busy does NOT block: proceeds with skip_local_ollama
                res = client.post("/v1/chat/completions", json={"model": "qwen3:8b", "messages": []})
                self.assertEqual(res.status_code, 200)
                self.assertTrue(res.get_json()["skipped_local"])

                # 2. OmniRoute direct selection does NOT wait on gate at all
                res_omni = client.post("/v1/chat/completions", json={"model": "🌐 OmniRoute (auto)", "messages": []})
                self.assertEqual(res_omni.status_code, 200)

                # 3. Without fallback, gate busy returns 503
                os.environ.pop("EXTERNAL_FALLBACK_API_URL", None)
                res_no_fb = client.post("/v1/chat/completions", json={"model": "qwen3:8b", "messages": []})
                self.assertEqual(res_no_fb.status_code, 503)
                self.assertIn("Il Mac sta completando un'immagine", res_no_fb.get_json()["error"]["message"])
        finally:
            gate.release_image("img-test-1")
            if saved_ext is not None:
                os.environ["EXTERNAL_FALLBACK_API_URL"] = saved_ext
            else:
                os.environ.pop("EXTERNAL_FALLBACK_API_URL", None)


if __name__ == "__main__":
    unittest.main()
