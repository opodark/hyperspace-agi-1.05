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
    def __init__(self, role="", max_tokens=None, deadline=None, cancelled=None,
                 workspace_id=""):
        self.role = role
        self.max_tokens = max_tokens
        self.deadline = deadline
        self.cancelled = cancelled or (lambda: False)
        # Workspace della catena: se un task a monte ne ha gia' creato uno, va
        # riusato invece di ricrearne un altro (memoria condivisa della missione).
        self.workspace_id = str(workspace_id or "")
        self.tokens = 0
        self.reserved_tokens = 0
        self.usage_known = True
        self.results = []

    def checkpoint(self):
        if self.cancelled():
            raise ExecutionStopped("execution cancelled")
        if self.deadline is not None and time.time() >= self.deadline:
            raise ExecutionStopped("execution deadline exceeded")

    @staticmethod
    def compact_messages(messages, keep_recent=4, max_old_chars=1200):
        """Compatta gli output tool piu' vecchi per non saturare la finestra di contesto/VRAM."""
        if not isinstance(messages, list):
            return messages
        tool_indices = [
            idx for idx, msg in enumerate(messages)
            if isinstance(msg, dict) and msg.get("role") == "tool"
        ]
        if len(tool_indices) <= keep_recent:
            return messages
        older_set = set(tool_indices[:-keep_recent] if keep_recent > 0 else tool_indices)
        head_chars = max(200, int(max_old_chars * 0.5))
        tail_chars = max(120, int(max_old_chars * 0.25))
        compacted = []
        changed = False
        for idx, msg in enumerate(messages):
            if idx in older_set and isinstance(msg, dict):
                content = msg.get("content")
                if isinstance(content, str) and len(content) > max_old_chars:
                    omitted = len(content) - (head_chars + tail_chars)
                    if omitted > 80:
                        new_msg = dict(msg)
                        new_msg["content"] = (
                            f"{content[:head_chars]}\n"
                            f"...[output compattato: {omitted} caratteri omessi per preservare contesto VRAM]...\n"
                            f"{content[-tail_chars:]}"
                        )
                        compacted.append(new_msg)
                        changed = True
                        continue
            compacted.append(msg)
        return compacted if changed else messages

    def model_payload(self, data):
        self.checkpoint()
        payload = dict(data)
        if isinstance(payload.get("messages"), list):
            payload["messages"] = self.compact_messages(payload["messages"])
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
        # `options` e' la forma nativa di Ollama: un backend OpenAI-compatibile
        # (llama.cpp/llama-server, vLLM, LM Studio) la ignora e applica il proprio
        # sampling. La temperatura va anche nel campo di primo livello. Misurato il
        # 2026-10-08 su Bonsai 2 27B: il planner della missione (temperature=0.2)
        # girava col sampling del server (temp 1.0) e a volte rispondeva senza
        # JSON, facendo fallire la missione su "invalid plan".
        if "temperature" not in payload:
            temperature = (payload.get("options") or {}).get("temperature")
            if isinstance(temperature, (int, float)) and not isinstance(temperature, bool):
                payload["temperature"] = temperature
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
                "inspect",
                "list",
                "read",
                "diff",
                "check",
                "verify",
            }:
                raise ValueError("sandbox action not allowed for verifier")
        # Riuso deterministico del workspace della catena. Il prompt lo chiede al
        # modello, ma un 8B lo disattende: se un task a monte ha gia' creato il
        # workspace, QUI si forza l'id su ogni azione e la seconda `create`
        # diventa `reuse`, cosi' i file dei passi a monte non si perdono e il PDF
        # resta nello stesso sandbox che il gate ispeziona. Misurato il
        # 2026-10-07: quattro task coder, quattro workspace, zero PDF nel diff.
        if name == "code_sandbox" and self.workspace_id:
            action = str(arguments.get("action", "status")).strip().lower()
            if action == "create":
                arguments = {"action": "reuse", "workspace_id": self.workspace_id}
            elif action in ("list", "read", "write", "replace", "run", "diff",
                            "inspect", "check", "verify"):
                arguments = {**arguments, "workspace_id": self.workspace_id}
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
