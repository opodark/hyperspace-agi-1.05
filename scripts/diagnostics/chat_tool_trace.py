#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Summarize recent WebUI interactions matching a phrase, without printing chat text.

The Control Plane `/logs` endpoint is read-only. This script fetches bounded
recent `webui_interaction` entries and prints only timestamp/model/token counts
plus coarse indicators about the recorded tool transcript.

  python3 scripts/diagnostics/chat_tool_trace.py --contains moltbook.com
  python3 scripts/diagnostics/chat_tool_trace.py --base http://127.0.0.1:8085 --contains skill.md
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8085",
                        help="Base URL del Control Plane")
    parser.add_argument("--contains", required=True,
                        help="Testo da cercare nelle ultime interazioni WebUI")
    parser.add_argument("--limit", type=int, default=100,
                        help="Numero massimo di log da esaminare (max 200)")
    args = parser.parse_args()
    limit = max(1, min(args.limit, 200))
    query = urllib.parse.urlencode({"type": "webui_interaction", "per_page": limit,
                                    "page": 1})
    request = urllib.request.Request(args.base.rstrip("/") + "/logs?" + query,
                                     headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"Control Plane log endpoint non raggiungibile: {exc}")
        return 2

    needle = args.contains.casefold()
    rows = payload.get("logs") or []
    matches = []
    for row in rows:
        try:
            detail = row.get("detail") or "{}"
            detail = json.loads(detail) if isinstance(detail, str) else detail
        except (TypeError, ValueError):
            continue
        transcript = str(detail.get("prompt") or "")
        if needle not in transcript.casefold():
            continue
        matches.append((row, detail, transcript))

    if not matches:
        print(f"Nessuna interazione corrispondente nelle ultime {len(rows)} righe.")
        return 1
    for row, detail, transcript in matches[:10]:
        print("ts={ts} node={node} model={model} duration_ms={duration} tokens_in={tin} tokens_out={tout}".format(
            ts=row.get("ts", "?"), node=str(detail.get("node_id") or row.get("node_id") or "?")[:16],
            model=detail.get("model", "?"), duration=detail.get("duration_ms", "?"),
            tin=detail.get("tokens_in", "?"), tout=detail.get("tokens_out", "?")))
        print("  transcript markers: web_fetch={fetch}, web_search_results={search}, tool_error={error}".format(
            fetch="web_fetch" in transcript, search="Risultati web per" in transcript,
            error="Errore" in transcript or "error" in transcript.casefold()))
        response_text = str(detail.get("response") or "")
        print(f"  response_empty={not bool(response_text.strip())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
