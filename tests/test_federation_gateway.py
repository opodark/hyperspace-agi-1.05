# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from shared.network_security import verify_client_ip


SOURCE = Path(__file__).parents[1] / "federation-gateway" / "main.py"
SPEC = importlib.util.spec_from_file_location("federation_gateway_main", SOURCE)
gateway = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gateway)


class FederationGatewayTests(unittest.TestCase):
    def setUp(self):
        gateway._rate_hits.clear()
        gateway._key_cache.clear()
        self.client = gateway.app.test_client()

    def test_public_surface_includes_only_safe_bottle_routes(self):
        self.assertIn(("POST", "/bottles/publish"), gateway.ALLOWED_ROUTES)
        self.assertIn(("GET", "/bottles/list"), gateway.ALLOWED_ROUTES)
        self.assertNotIn(("POST", "/bottles/announce"), gateway.ALLOWED_ROUTES)
        response = self.client.post("/bottles/announce")
        self.assertEqual(response.status_code, 404)

    def test_public_web_node_surface_has_worker_and_chat_routes(self):
        for path in ("/web/register", "/web/poll", "/web/result", "/web/search", "/web/sandbox/run", "/web/image/generate"):
            self.assertIn(("POST", path), gateway.ALLOWED_ROUTES)
            self.assertIn(("OPTIONS", path), gateway.ALLOWED_ROUTES)
            self.assertIn(path, gateway._RATE_LIMITS)
        self.assertIn(("GET", "/web/image/status"), gateway.ALLOWED_ROUTES)
        self.assertIn(("OPTIONS", "/web/image/status"), gateway.ALLOWED_ROUTES)
        self.assertIn(("GET", "/web/image/file"), gateway.ALLOWED_ROUTES)
        self.assertIn(("OPTIONS", "/web/image/file"), gateway.ALLOWED_ROUTES)
        self.assertIn("/web/image/status", gateway._RATE_LIMITS)
        self.assertIn("/web/image/file", gateway._RATE_LIMITS)
        self.assertNotIn(("POST", "/web/tasks"), gateway.ALLOWED_ROUTES)
        self.assertNotIn(("GET", "/web/status"), gateway.ALLOWED_ROUTES)
        self.assertIn(("GET", "/v1/models"), gateway.ALLOWED_ROUTES)
        self.assertIn(("OPTIONS", "/v1/models"), gateway.ALLOWED_ROUTES)
        self.assertIn(("POST", "/v1/chat/completions"), gateway.ALLOWED_ROUTES)
        self.assertIn(("OPTIONS", "/v1/chat/completions"), gateway.ALLOWED_ROUTES)
        self.assertIn("/v1/models", gateway._RATE_LIMITS)
        self.assertIn("/v1/chat/completions", gateway._RATE_LIMITS)
        self.assertNotIn(("GET", "/nodes/active"), gateway.ALLOWED_ROUTES)
        self.assertNotIn(("GET", "/logs"), gateway.ALLOWED_ROUTES)

    def test_root_endpoint_redirects_browser_and_serves_json_to_api(self):
        # Browser request with Accept: text/html -> redirects to mesh.html portal
        resp_html = self.client.get("/", headers={"Accept": "text/html,application/xhtml+xml"})
        self.assertEqual(resp_html.status_code, 302)
        self.assertIn("mesh.html", resp_html.headers.get("Location", ""))

        # API request without text/html -> returns discovery JSON
        resp_json = self.client.get("/", headers={"Accept": "application/json"})
        self.assertEqual(resp_json.status_code, 200)
        data = resp_json.get_json()
        self.assertEqual(data.get("status"), "online")
        self.assertIn("endpoints", data)

    def test_web_ping_endpoint_zero_cost(self):
        response = self.client.get("/web/ping")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("echo"), "pong")
        self.assertEqual(data.get("mesh"), "00MESH")
        # HEAD also works
        resp_head = self.client.head("/web/ping")
        self.assertEqual(resp_head.status_code, 200)

    def test_head_request_forwarded_for_get_routes(self):
        upstream = Mock(
            content=b"", status_code=200,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        )
        with patch.object(gateway, "_rate_check") as rate_check, \
             patch.object(gateway.requests, "request", return_value=upstream) as req:
            response = self.client.head("/web/topology")
        self.assertEqual(response.status_code, 200)
        req.assert_called_once()
        self.assertEqual(req.call_args.kwargs["method"], "HEAD")
        rate_check.assert_not_called()

    def test_web_node_preflight_does_not_consume_rate_limit(self):
        upstream = Mock(
            content=b"", status_code=204,
            headers={"Access-Control-Allow-Origin": "*"},
        )
        with patch.object(gateway, "_rate_check") as rate_check, \
             patch.object(gateway.requests, "request", return_value=upstream):
            response = self.client.options("/web/register")
        self.assertEqual(response.status_code, 204)
        rate_check.assert_not_called()

    def test_public_chat_uses_one_bounded_inference_and_exposes_sse(self):
        upstream = Mock(
            status_code=200,
            headers={"Content-Type": "application/json"},
        )
        upstream.json.return_value = {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]
        }
        with patch.object(gateway, "_rate_check", return_value=True), \
             patch.object(gateway.requests, "request", return_value=upstream) as request_call:
            response = self.client.post(
                "/v1/chat/completions",
                json={"model": "qwen3.5:4b", "stream": True, "max_tokens": 999})
            response_body = response.data
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"gateway connected", response_body)
        self.assertIn(b"[DONE]", response_body)
        self.assertTrue(request_call.call_args.kwargs["stream"])
        forwarded = json.loads(request_call.call_args.kwargs["data"])
        self.assertFalse(forwarded["stream"])
        self.assertFalse(forwarded["think"])
        self.assertEqual(forwarded["max_tokens"], 999)
        self.assertEqual(forwarded["options"]["num_ctx"], 4096)
        self.assertEqual(
            request_call.call_args.kwargs["headers"]["X-Hyperspace-Tools"], "off")
        self.assertEqual(request_call.call_args.kwargs["timeout"],
                         (10, gateway.CHAT_UPSTREAM_TIMEOUT_S))
        self.assertGreaterEqual(gateway.CHAT_UPSTREAM_TIMEOUT_S, 600)

    def test_public_chat_authenticated_allows_higher_token_ceiling(self):
        upstream = Mock(
            status_code=200,
            headers={"Content-Type": "application/json"},
        )
        upstream.json.return_value = {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]
        }
        with patch.object(gateway, "_rate_check", return_value=True), \
             patch.object(gateway, "_mesh_key_valid", return_value=True), \
             patch.object(gateway.requests, "request", return_value=upstream) as request_call:
            response = self.client.post(
                "/v1/chat/completions",
                headers={"Authorization": "Bearer hs-mesh-test-key"},
                json={"model": "qwen3.5:4b", "stream": True, "max_tokens": 3500,
                      "options": {"num_ctx": 16384}})
            _ = response.data
        self.assertEqual(response.status_code, 200)
        forwarded = json.loads(request_call.call_args.kwargs["data"])
        self.assertEqual(forwarded["max_tokens"], 3500)
        self.assertEqual(forwarded["options"]["num_ctx"], gateway.GATEWAY_CHAT_AUTH_MAX_CTX)

    def test_public_chat_unverified_key_stays_anonymous(self):
        # La sola presenza di un header Authorization non da' il tetto dei membri.
        upstream = Mock(status_code=200, headers={"Content-Type": "application/json"},
                        content=b'{"choices": []}')
        verify = Mock(status_code=401)
        verify.json.return_value = {"ok": False, "authenticated": False}
        with patch.object(gateway.requests, "post", return_value=verify) as verify_call, \
             patch.object(gateway.requests, "request", return_value=upstream) as request_call:
            response = self.client.post(
                "/v1/chat/completions",
                headers={"Authorization": "Bearer sk-qualsiasi"},
                json={"model": "qwen3:4b", "max_tokens": 3500, "options": {"num_ctx": 16384}})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(verify_call.call_args.args[0].endswith("/web/auth/verify"))
        forwarded = json.loads(request_call.call_args.kwargs["data"])
        self.assertEqual(forwarded["max_tokens"], gateway.GATEWAY_CHAT_MAX_TOKENS)
        self.assertEqual(forwarded["options"]["num_ctx"], 4096)

    def test_public_chat_valid_key_skips_anonymous_rate_limit(self):
        upstream = Mock(status_code=200, headers={"Content-Type": "application/json"},
                        content=b'{"choices": []}')
        verify = Mock(status_code=200)
        verify.json.return_value = {"ok": True, "authenticated": True, "role": "member"}
        anon_limit = gateway._RATE_LIMITS["/v1/chat/completions"][0]
        with patch.object(gateway.requests, "post", return_value=verify) as verify_call, \
             patch.object(gateway.requests, "request", return_value=upstream):
            codes = [self.client.post(
                "/v1/chat/completions",
                headers={"Authorization": "Bearer hs-mesh-member-key"},
                json={"model": "qwen3:4b"}).status_code for _ in range(anon_limit + 3)]
            anon = self.client.post("/v1/chat/completions", json={"model": "qwen3:4b"})
        self.assertEqual(set(codes), {200})
        # L'esito della verifica resta in cache: una chiamata al CP, non una per richiesta.
        self.assertEqual(verify_call.call_count, 1)
        self.assertEqual(anon.status_code, 200)

    def test_public_chat_without_stream_returns_standard_openai_json(self):
        upstream_payload = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "pong"}, "finish_reason": "stop"}],
        }
        upstream = Mock(
            status_code=200,
            content=json.dumps(upstream_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        upstream.json.return_value = upstream_payload
        with patch.object(gateway, "_rate_check", return_value=True), \
             patch.object(gateway.requests, "request", return_value=upstream):
            response = self.client.post(
                "/v1/chat/completions",
                json={"model": "qwen3.5:4b", "messages": [{"role": "user", "content": "ping"}]})
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response.headers.get("Content-Type", ""))
        self.assertEqual(response.get_json()["choices"][0]["message"]["content"], "pong")

    def test_public_chat_rejects_placeholder_model_with_404(self):
        with patch.object(gateway, "_rate_check", return_value=True), \
             patch.object(gateway.requests, "request") as request_call:
            response = self.client.post(
                "/v1/chat/completions",
                json={"model": "<id da /v1/models>", "messages": [{"role": "user", "content": "ping"}]})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"]["code"], "model_not_found")
        request_call.assert_not_called()

    def test_public_chat_preserves_upstream_404_model_not_found(self):
        err_payload = {"error": {"message": "model 'unknown' not found", "type": "model_not_found", "code": "model_not_found"}}
        upstream = Mock(
            status_code=404,
            content=json.dumps(err_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with patch.object(gateway, "_rate_check", return_value=True), \
             patch.object(gateway.requests, "request", return_value=upstream):
            response = self.client.post(
                "/v1/chat/completions",
                json={"model": "unknown", "messages": [{"role": "user", "content": "ping"}]})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"]["code"], "model_not_found")

    def test_public_chat_preflight_keeps_cors_headers(self):
        upstream = Mock(
            content=b"", status_code=204,
            headers={
                "Access-Control-Allow-Origin": "https://os.zerozerocomputer.it",
                "Access-Control-Allow-Headers": "content-type",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
            },
        )
        with patch.object(gateway.requests, "request", return_value=upstream):
            response = self.client.options(
                "/v1/chat/completions",
                headers={
                    "Origin": "https://os.zerozerocomputer.it",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers["Access-Control-Allow-Headers"], "content-type")
        self.assertIn("POST", response.headers["Access-Control-Allow-Methods"])

    def test_spoofed_attestation_is_replaced_with_gateway_signature(self):
        secret = "g" * 32
        upstream = Mock(
            content=b'{}', status_code=200,
            headers={"Content-Type": "application/json"},
        )
        with patch.dict(os.environ, {"BOTTLE_GATEWAY_SECRET": secret}), \
             patch.object(gateway, "_rate_check", return_value=True), \
             patch.object(gateway.time, "time", return_value=1000.0), \
             patch.object(gateway.requests, "request", return_value=upstream) as request_call:
            response = self.client.post(
                "/bottles/publish",
                headers={
                    "X-Hs-Client-Ip": "198.51.100.99",
                    "X-Hs-Client-Ts": "1",
                    "X-Hs-Client-Sig": "forged",
                },
                environ_base={"REMOTE_ADDR": "203.0.113.7"},
            )

        self.assertEqual(response.status_code, 200)
        headers = request_call.call_args.kwargs["headers"]
        self.assertEqual(headers["X-Hs-Client-Ip"], "203.0.113.7")
        self.assertTrue(verify_client_ip(
            secret,
            headers["X-Hs-Client-Ip"],
            headers["X-Hs-Client-Ts"],
            headers["X-Hs-Client-Sig"],
            now=1000,
        ))

    def test_rate_limits_are_independent_and_keep_their_own_windows(self):
        old_limits = gateway._RATE_LIMITS
        gateway._RATE_LIMITS = {
            "/bottles/publish": (1, 3600),
            "/bottles/list": (1, 60),
        }
        try:
            with patch.object(gateway.time, "time", return_value=1000):
                self.assertTrue(gateway._rate_check("/bottles/publish", "client"))
            with patch.object(gateway.time, "time", return_value=1100):
                self.assertTrue(gateway._rate_check("/bottles/list", "client"))
                self.assertFalse(gateway._rate_check("/bottles/publish", "client"))
            with patch.object(gateway.time, "time", return_value=1161):
                self.assertTrue(gateway._rate_check("/bottles/list", "client"))
                self.assertFalse(gateway._rate_check("/bottles/publish", "client"))
        finally:
            gateway._RATE_LIMITS = old_limits
            gateway._rate_hits.clear()


if __name__ == "__main__":
    unittest.main()
