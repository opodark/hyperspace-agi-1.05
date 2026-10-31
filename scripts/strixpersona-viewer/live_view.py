# SPDX-License-Identifier: Apache-2.0
# Vendorizzato da usestrix/strix, strix/interface/tui/live_view.py
# (Copyright 2025 OmniSecure Inc., Apache-2.0 — vedi LICENSE-strix-viewer-upstream.txt),
# ridotto ai soli metodi "primitivi" (dizionari semplici, nessuna dipendenza dall'SDK
# di agenti di Strix né da agents.json/agents.db su disco): è la stessa proiezione
# agenti+eventi che il loro frontend consuma via /api/transcript, pilotata qui a mano
# dal nostro loop persona+shell invece che dal loro orchestratore.
"""Proiezione in memoria: agenti + eventi, nello schema che il viewer SPA si aspetta."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


class TuiLiveView:
    def __init__(self) -> None:
        self.agents: dict[str, dict[str, Any]] = {}
        self.events: list[dict[str, Any]] = []
        self._next_event_id = 1
        self._tool_event_by_agent_and_call_id: dict[tuple[str, str], dict[str, Any]] = {}

    def upsert_agent(
        self,
        agent_id: str,
        *,
        name: str | None = None,
        parent_id: str | None = None,
        status: str | None = None,
        error_message: str | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        current = self.agents.setdefault(
            agent_id,
            {
                "id": agent_id,
                "name": name or agent_id,
                "parent_id": parent_id,
                "status": status or "running",
                "created_at": now,
                "updated_at": now,
            },
        )
        if name is not None:
            current["name"] = name
        if parent_id is not None or "parent_id" not in current:
            current["parent_id"] = parent_id
        if status is not None:
            current["status"] = status
        if error_message is not None:
            current["error_message"] = error_message
        current["updated_at"] = now

    def record_user_message(self, agent_id: str, content: str) -> None:
        self._append_event(
            agent_id, "chat",
            {"role": "user", "content": content, "metadata": {"source": "tui_user"}},
        )

    def record_assistant_message(self, agent_id: str, content: str) -> None:
        if not content:
            return
        self._append_event(
            agent_id, "chat",
            {"role": "assistant", "content": content,
             "metadata": {"source": "sdk_stream", "streaming": False}},
        )

    def record_agent_error(self, agent_id: str, error: str) -> None:
        self._append_event(
            agent_id, "chat",
            {"role": "assistant",
             "content": f"Si è verificato un errore: {error}\nIn attesa di nuove istruzioni.",
             "metadata": {"source": "agent_error"}},
        )

    def record_tool_call(self, agent_id: str, call_id: str, tool_name: str,
                         args: dict[str, Any]) -> None:
        event_key = (agent_id, call_id)
        tool_data = {"tool_name": tool_name, "args": args, "status": "running",
                    "agent_id": agent_id, "call_id": call_id}
        existing = self._tool_event_by_agent_and_call_id.get(event_key)
        if existing is None:
            event = self._append_event(agent_id, "tool", tool_data)
            self._tool_event_by_agent_and_call_id[event_key] = event
        else:
            existing["data"].update(tool_data)
            self._bump_event(existing)

    def record_tool_output(self, agent_id: str, call_id: str, tool_name: str,
                           result: Any, *, status: str = "completed") -> None:
        event_key = (agent_id, call_id)
        event = self._tool_event_by_agent_and_call_id.get(event_key)
        if event is None:
            event = self._append_event(
                agent_id, "tool",
                {"tool_name": tool_name, "args": {}, "status": status,
                 "agent_id": agent_id, "call_id": call_id},
            )
            self._tool_event_by_agent_and_call_id[event_key] = event
        event["data"]["result"] = result
        event["data"]["status"] = status
        self._bump_event(event)

    def _append_event(self, agent_id: str, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        event = {
            "id": f"{event_type}_{self._next_event_id}",
            "type": event_type,
            "agent_id": agent_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "version": 0,
            "data": data,
        }
        self._next_event_id += 1
        self.events.append(event)
        return event

    @staticmethod
    def _bump_event(event: dict[str, Any]) -> None:
        event["version"] = int(event.get("version", 0)) + 1
        event["timestamp"] = datetime.now(UTC).isoformat()
