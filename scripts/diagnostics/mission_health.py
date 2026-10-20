#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Read-only diagnostic for HyperSpace Mission Control and model inference.

Checks the configured local Control Plane, mission engine and mesh endpoints,
then probes the configured inference URL and Ollama's loaded-model endpoint.
No service state is modified. Tokens are read from the environment and never
printed.

Examples:
  DREAM_REVIEW_TOKEN=... python scripts/diagnostics/mission_health.py
  python scripts/diagnostics/mission_health.py --base http://127.0.0.1:8085
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


def fetch_json(url: str, *, token: str = "", timeout: float = 5.0) -> Any:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def report(label: str, url: str, *, token: str = "", timeout: float = 5.0) -> Any | None:
    try:
        data = fetch_json(url, token=token, timeout=timeout)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        print(f"{label}: NON RAGGIUNGIBILE ({exc})")
        return None
    print(f"{label}: OK")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=os.getenv("HYPERSPACE_CP_URL", "http://127.0.0.1:8085"),
                        help="Base URL del Control Plane (default: %(default)s)")
    parser.add_argument("--inference-url", default=os.getenv("MISSION_INFERENCE_URL", ""),
                        help="Endpoint OpenAI-compatible configurato per Mission Control")
    parser.add_argument("--ollama-url", default=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
                        help="Base URL Ollama per controllare i modelli caricati")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()
    base = args.base.rstrip("/")
    token = os.getenv("DREAM_REVIEW_TOKEN", "")

    # Keep each probe independent so one inaccessible subsystem does not hide others.
    health = report("Control Plane /health", f"{base}/health", timeout=args.timeout)
    status = report("Mission Control /missions/status", f"{base}/missions/status", token=token, timeout=args.timeout)
    missions = report("Mission Control /missions", f"{base}/missions?limit=100", token=token, timeout=args.timeout)
    nodes = report("Mesh /mesh/nodes", f"{base}/mesh/nodes", timeout=args.timeout)

    if isinstance(health, dict):
        print("  status={status}, active_nodes={nodes}, memories={memories}, memory_pending={pending}".format(
            status=health.get("status", "?"), nodes=health.get("nodes_active", "?"),
            memories=health.get("memories", "?"), pending=health.get("memory_pending", "?")))
    if isinstance(status, dict):
        counts = status.get("missions") or {}
        print("  running={running}, last_mission={last}, counts={counts}".format(
            running=status.get("running", "?"), last=status.get("last_mission") or "none",
            counts=counts.get("by_status", {})))
    if isinstance(missions, dict):
        rows = missions.get("missions") or []
        rows.sort(key=lambda row: row.get("created_at", ""), reverse=True)
        print(f"  newest_mission_count={len(rows)}")
        for row in rows[:5]:
            print("  mission id={id} status={status} created={created} error={error}".format(
                id=row.get("id", "?"), status=row.get("status", "?"),
                created=row.get("created_at", "?"), error=row.get("error") or "none"))
    if isinstance(nodes, list):
        for node in nodes:
            print("  node alias={alias} status={status} running={running} active={active} queued={queued} degraded={degraded} vram_gb={vram}".format(
                alias=node.get("alias") or node.get("node_id", "?"),
                status=node.get("status", "?"), running=node.get("running", "?"),
                active=node.get("active_requests", "?"), queued=node.get("queued_requests", "?"),
                degraded=node.get("degraded", "?"), vram=node.get("vram_gb", "?")))

    if args.inference_url:
        endpoint = args.inference_url.rstrip("/") + "/models"
        report("Mission inference /models", endpoint, timeout=args.timeout)
    else:
        print("Mission inference: MISSION_INFERENCE_URL non impostata; usare l'endpoint Ollama configurato dal CP")

    ollama_url = args.ollama_url.rstrip("/")
    loaded = report("Ollama /api/ps", ollama_url + "/api/ps", timeout=args.timeout)
    if isinstance(loaded, dict):
        models = loaded.get("models") or []
        print(f"  loaded_models={len(models)}")
        for model in models:
            print("  model={name} size_vram={vram}".format(
                name=model.get("name", "?"), vram=model.get("size_vram", "?")))

    return 0


if __name__ == "__main__":
    sys.exit(main())
