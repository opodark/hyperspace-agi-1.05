#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Inspect the HyperSpace image queue and memory gate; optionally close one stale claim.

Read-only by default. `--close-stale JOB_ID` sends a failed result only when the
local ComfyUI endpoint is unreachable and JOB_ID is still an active image claim.
The claim is never reset to pending, so cleanup cannot trigger a duplicate render.

  python3 scripts/diagnostics/image_gate.py
  python3 scripts/diagnostics/image_gate.py --close-stale bb9d132b3819

The channel token is read from CHANNEL_CLIENTS in the repository `.env` or from
HYPERSPACE_CHANNEL_TOKEN. Neither is printed.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


def _channel_token() -> str:
    token = os.getenv("HYPERSPACE_CHANNEL_TOKEN", "").strip()
    if token:
        return token
    env_path = Path(os.getenv("HYPERSPACE_ENV_FILE", ".env"))
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    raw = next((line.partition("=")[2].strip().strip('"').strip("'")
                for line in lines if line.startswith("CHANNEL_CLIENTS=")), "")
    for item in raw.split(";"):
        name, sep, value = item.partition("=")
        if sep and name.strip().lower() == "comfy":
            return value.strip()
    return ""


def _get_json(url: str, *, token: str = "", timeout: float = 4.0) -> dict:
    headers = {"Accept": "application/json"}
    if token:
        headers["X-Hyperspace-Channel-Token"] = token
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=os.getenv("HYPERSPACE_CP_URL", "http://127.0.0.1:8085"))
    parser.add_argument("--comfy", default=os.getenv(
        "COMFYUI_URL", "http://host.docker.internal:8188"))
    parser.add_argument("--close-stale", metavar="JOB_ID",
                        help="mark exactly this running job failed if ComfyUI is unreachable")
    args = parser.parse_args()
    base, comfy = args.base.rstrip("/"), args.comfy.rstrip("/")
    token = _channel_token()
    if not token:
        print("Token canale Comfy non trovato: imposta HYPERSPACE_CHANNEL_TOKEN o controlla .env.")
        return 2
    try:
        status = _get_json(base + "/image/status", token=token)
    except Exception as exc:
        print(f"Control Plane /image/status non raggiungibile: {exc}")
        return 2

    active = status.get("attivi") or []
    gate = status.get("memory_gate") or {}
    print("images queued={queued} running={running} paused={paused} auto_paused={auto}".format(
        queued=status.get("in_coda", "?"), running=status.get("in_esecuzione", "?"),
        paused=status.get("paused", "?"), auto=status.get("auto_paused", "?")))
    print("memory gate owner={owner} active_chats={chats} lease_remaining_s={lease}".format(
        owner=gate.get("image_job") or "none", chats=gate.get("active_chats", "?"),
        lease=gate.get("lease_remaining_s", "?")))
    for job in active:
        print("active job id={id} state={state} family={family}".format(
            id=job.get("id", "?"), state=job.get("stato", "?"), family=job.get("famiglia", "?")))

    try:
        _get_json(comfy + "/system_stats", timeout=2.0)
        comfy_online = True
        print("ComfyUI: reachable; automatic stale-claim cleanup is disabled.")
    except urllib.error.HTTPError as exc:
        # Any HTTP response proves that a server answers at the ComfyUI address;
        # a changed endpoint/status must never be mistaken for a stopped renderer.
        comfy_online = True
        print(f"ComfyUI: server responds with HTTP {exc.code}; cleanup disabled.")
    except ValueError as exc:
        comfy_online = True
        print(f"ComfyUI: server responds with non-JSON data ({exc}); cleanup disabled.")
    except (OSError, urllib.error.URLError) as exc:
        comfy_online = False
        print(f"ComfyUI: unreachable ({exc}).")

    if not args.close_stale:
        return 0
    if comfy_online:
        print("Cleanup refused: ComfyUI responds. Inspect the active render first.")
        return 3
    match = next((job for job in active if str(job.get("id")) == args.close_stale
                  and job.get("stato") == "running"), None)
    if not match:
        print("Cleanup refused: requested id is not a currently running image job.")
        return 3
    body = json.dumps({"id": args.close_stale, "ok": False,
                       "errore": "stale image claim closed by operator diagnostic"}).encode("utf-8")
    request = urllib.request.Request(base + "/image/result", data=body,
                                     headers={"Content-Type": "application/json",
                                              "X-Hyperspace-Channel-Token": token},
                                     method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5.0) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"Cleanup failed: {exc}")
        return 4
    job = result.get("job") or {}
    print("closed job id={id} state={state}".format(
        id=job.get("id", args.close_stale), state=job.get("stato", "?")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
