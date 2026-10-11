# SPDX-License-Identifier: Apache-2.0
"""Protocol, validation and failure behavior without loading an Apple model."""
import io
import json
import subprocess
from unittest.mock import patch

import pytest

from scripts import apple_intelligence as apple


def call(name, args=None):
    return {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
            "params": {"name": name, "arguments": {} if args is None else args}}


@pytest.mark.parametrize("args", [
    {}, {"prompt": " "}, {"prompt": []}, {"prompt": "ok", "instructions": 1},
    {"prompt": "ok", "max_tokens": True}, {"prompt": "ok", "max_tokens": 1025},
    {"prompt": "ok", "file": "/etc/passwd"}, {"prompt": "é" * 40000},
])
def test_invalid_inputs_never_invoke_worker(args):
    def forbidden(*_):
        pytest.fail("invalid request invoked worker")
    result = apple.rpc(call("apple_intelligence_text", args), run=forbidden)
    assert result["error"]["code"] == -32602


def test_initialize_and_tool_catalog():
    result = apple.rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "unknown"}})
    assert result["result"]["protocolVersion"] == apple.PROTOCOLS[0]
    assert result["result"]["capabilities"] == {"tools": {"listChanged": False}}
    assert len(apple.rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]) == 2


def test_generation_notification_cannot_execute():
    message = call("apple_intelligence_text", {"prompt": "hello"})
    del message["id"]
    def forbidden(*_):
        pytest.fail("notification invoked worker")
    assert apple.rpc(message, run=forbidden) is None


def test_native_errors_are_tool_errors_not_success():
    result = apple.rpc(call("apple_intelligence_text", {"prompt": "hello"}),
                       run=lambda _: {"ok": False, "error": "generation_failed", "detail": "guardrails"})
    assert result["result"]["isError"] is True
    assert "guardrails" in result["result"]["content"][0]["text"]


def test_success_preserves_native_text():
    result = apple.rpc(call("apple_intelligence_text", {"prompt": "hello"}),
                       run=lambda _: {"ok": True, "text": "Ciao"})
    assert result["result"]["isError"] is False
    assert json.loads(result["result"]["content"][0]["text"])["text"] == "Ciao"


def test_protocol_recovers_from_invalid_and_oversized_line():
    source = io.BytesIO(b"bad\n" + b"x" * (apple.MAX_INPUT + 1) + b"\n" +
                       b'{"jsonrpc":"2.0","id":3,"method":"ping"}\n')
    out = io.StringIO()
    apple.serve(source, out)
    messages = [json.loads(line) for line in out.getvalue().splitlines()]
    assert messages[0]["error"]["code"] == -32700
    assert messages[1]["error"]["code"] == -32600
    assert messages[2] == {"jsonrpc": "2.0", "id": 3, "result": {}}


@pytest.mark.parametrize("stdout", ["not json", "[]", '{"ok":true}', '{"ok":"yes"}'])
def test_invalid_worker_output_is_failure(tmp_path, stdout):
    binary = tmp_path / "worker"
    binary.touch()
    with patch.object(apple, "BINARY", binary), patch.object(apple.subprocess, "run") as run:
        run.return_value = subprocess.CompletedProcess([], 0, stdout, "")
        assert apple.invoke({"prompt": "hello"})["error"] == "invalid_worker_output"


def test_worker_timeout_is_bounded_and_no_retry(tmp_path):
    binary = tmp_path / "worker"
    binary.touch()
    with patch.object(apple, "BINARY", binary), patch.object(apple.subprocess, "run") as run:
        run.side_effect = subprocess.TimeoutExpired([str(binary)], 90)
        assert apple.invoke({"prompt": "hello"}) == {"ok": False, "error": "worker_timeout"}
        assert run.call_count == 1
        assert run.call_args.kwargs["timeout"] == 90


def test_missing_worker_has_build_instruction(tmp_path):
    with patch.object(apple, "BINARY", tmp_path / "absent"):
        assert apple.invoke()["error"] == "worker_not_built"
