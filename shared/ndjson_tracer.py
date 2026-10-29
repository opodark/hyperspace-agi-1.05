# SPDX-License-Identifier: Apache-2.0
"""NDJSON Execution Tracer per HyperSpace Mesh & Mission Control.

Ispirato al sistema di tracce riproducibili di Atomic Agent:
registra ogni evento (inferenze LLM, chiamate tool, proposte mutanti, verifiche AST)
in un flusso Newline-Delimited JSON (NDJSON) immutabile, tracciabile e replayabile.
"""

from __future__ import annotations

import datetime
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional


class NDJSONTracer:
    """Tracer thread-safe per stream NDJSON di sessioni ed esperimenti."""

    def __init__(self, trace_dir: str = "data/traces", session_id: Optional[str] = None):
        self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id or f"session_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
        self.file_path = self.trace_dir / f"{self.session_id}.ndjson"
        self._lock = threading.RLock()
        self._event_count = 0

    def log_event(
        self,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
        level: str = "INFO",
    ) -> Dict[str, Any]:
        """Registra un evento atomico nello stream NDJSON."""
        now = time.time()
        iso = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).isoformat()

        record: Dict[str, Any] = {
            "ts": now,
            "iso": iso,
            "seq": self._event_count,
            "session_id": self.session_id,
            "event": event_type,
            "level": level.upper(),
        }
        if data:
            record.update(data)

        line = json.dumps(record, ensure_ascii=False) + "\n"

        with self._lock:
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(line)
            self._event_count += 1

        return record

    def log_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        duration_ms: float = 0.0,
        ok: bool = True,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Registra una specifica chiamata tool con latenza ed esito."""
        data: Dict[str, Any] = {
            "tool": tool_name,
            "arguments": arguments,
            "result_summary": str(result)[:300] if result is not None else None,
            "duration_ms": round(duration_ms, 2),
            "ok": ok,
        }
        if error:
            data["error"] = str(error)
        return self.log_event("tool_call", data, level="INFO" if ok else "ERROR")

    def log_llm_call(
        self,
        node: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        duration_ms: float = 0.0,
        status: str = "ok",
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Registra una transazione di inferenza con un nodo mesh o provider cloud."""
        data: Dict[str, Any] = {
            "node": node,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "duration_ms": round(duration_ms, 2),
            "status": status,
        }
        if temperature is not None:
            data["temperature"] = temperature
        return self.log_event("llm_call", data, level="INFO" if status == "ok" else "WARNING")

    def replay(self) -> Generator[Dict[str, Any], None, None]:
        """Itera su tutti gli eventi registrati nello stream in ordine sequenziale."""
        if not self.file_path.exists():
            return

        with self._lock:
            with open(self.file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue

    def get_summary(self) -> Dict[str, Any]:
        """Elabora statistiche riassuntive sull'intera sessione."""
        total_events = 0
        tool_calls = 0
        tool_errors = 0
        total_tokens = 0
        total_duration_ms = 0.0
        events_by_type: Dict[str, int] = {}

        for evt in self.replay():
            total_events += 1
            etype = evt.get("event", "unknown")
            events_by_type[etype] = events_by_type.get(etype, 0) + 1

            if etype == "tool_call":
                tool_calls += 1
                if not evt.get("ok", True):
                    tool_errors += 1
                total_duration_ms += evt.get("duration_ms", 0.0)

            elif etype == "llm_call":
                total_tokens += evt.get("total_tokens", 0)
                total_duration_ms += evt.get("duration_ms", 0.0)

        return {
            "session_id": self.session_id,
            "trace_file": str(self.file_path),
            "total_events": total_events,
            "tool_calls": tool_calls,
            "tool_errors": tool_errors,
            "tool_success_rate": (
                round((tool_calls - tool_errors) / tool_calls, 3)
                if tool_calls > 0
                else 1.0
            ),
            "total_tokens": total_tokens,
            "total_duration_ms": round(total_duration_ms, 2),
            "events_distribution": events_by_type,
        }
