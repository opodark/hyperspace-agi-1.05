# SPDX-License-Identifier: Apache-2.0
"""Small invocation hooks shared by agent loops: authorize, bound, record evidence.

The context is constructed by the server, never from a client/model permission flag.
It does not install hooks or execute skill text.
"""

import json
import time


class ExecutionStopped(ValueError):
    """Cancellation/deadline/budget errors must not trigger a no-tools fallback."""


class Invocation:
    def __init__(self, role="", max_tokens=None, deadline=None, cancelled=None):
        self.role = role
        self.max_tokens = max_tokens
        self.deadline = deadline
        self.cancelled = cancelled or (lambda: False)
        self.tokens = 0
        self.reserved_tokens = 0
        self.usage_known = True
        self.results = []

    def checkpoint(self):
        if self.cancelled():
            raise ExecutionStopped("execution cancelled")
        if self.deadline is not None and time.time() >= self.deadline:
            raise ExecutionStopped("execution deadline exceeded")

    def model_payload(self, data):
        self.checkpoint()
        payload = dict(data)
        if self.max_tokens is not None:
            remaining = self.max_tokens - self.reserved_tokens
            if remaining <= 0:
                raise ExecutionStopped("task output-token budget exhausted")
            requested = payload.get("max_tokens", remaining)
            if type(requested) is not int or requested <= 0:
                raise ValueError("max_tokens must be a positive integer")
            payload["max_tokens"] = min(requested, remaining)
            options = dict(payload.get("options") or {})
            options["num_predict"] = payload["max_tokens"]
            payload["options"] = options
        return payload

    def model_failed(self, requested):
        # A transport failure may occur after generation; never assume it was free.
        if self.max_tokens is not None:
            self.usage_known = False
            self.reserved_tokens += requested.get("max_tokens", self.max_tokens)

    def model_result(self, response, requested):
        usage = response.get("usage") or {}
        count = usage.get("completion_tokens", response.get("eval_count"))
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            self.tokens += count
            self.reserved_tokens += count
        elif self.max_tokens is not None:
            # Missing usage is not zero cost. Stop further inference conservatively.
            self.usage_known = False
            self.reserved_tokens += requested.get("max_tokens", self.max_tokens)
        if self.max_tokens is not None and self.tokens > self.max_tokens:
            raise ExecutionStopped("backend exceeded task output-token budget")
        self.checkpoint()

    def authorize(self, name, arguments, offered):
        self.checkpoint()
        if name not in {t.get("function", {}).get("name") for t in offered}:
            raise ValueError("tool not allowed in this invocation")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except ValueError as error:
                raise ValueError("invalid tool arguments JSON") from error
        if not isinstance(arguments, dict):
            raise ValueError("tool arguments must be an object")
        if self.role == "verifier" and name == "code_sandbox":
            action = str(arguments.get("action", "status")).strip().lower()
            if action not in {
                "status",
                "catalog",
                "list",
                "read",
                "diff",
                "check",
                "verify",
            }:
                raise ValueError("sandbox action not allowed for verifier")
        return arguments

    def record(self, name, result):
        """Store structured evidence; no raw argument/result text goes to generic logs."""
        value = result
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                pass
        if isinstance(value, dict):
            ok = not (
                value.get("error")
                or value.get("ok") is False
                or value.get("completed") is False
                or value.get("passed") is False
            )
        else:
            lowered = str(value).strip().lower()
            ok = not (
                lowered.startswith(("errore", "error", "sandbox error", "shell error"))
                or "non gestito da nessun connector" in lowered
            )
        evidence = {"tool": name, "ok": ok}
        if isinstance(value, dict):
            for key in (
                "completed",
                "passed",
                "workspace_id",
                "project_id",
                "error",
            ):
                if key in value:
                    evidence[key] = value[key]
        self.results.append(evidence)
        return ok
