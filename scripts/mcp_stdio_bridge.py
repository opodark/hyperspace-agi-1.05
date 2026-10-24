#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
HyperSpace MCP Stdio Bridge.

Collega un client MCP standard (OpenWork, Claude Desktop, Cursor)
all'endpoint HTTP /mcp del Control Plane HyperSpace (http://localhost:8085/mcp).

Uso:
  .venv/bin/python scripts/mcp_stdio_bridge.py
  .venv/bin/python scripts/mcp_stdio_bridge.py --endpoint http://localhost:8085/mcp
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_ENDPOINT = os.getenv("MCP_ENDPOINT", "http://localhost:8085/mcp")
DEFAULT_TOKEN = os.getenv(
    "MCP_TOKEN", "hyperspace_openwork_local_client_token_32chars"
)


def main():
    parser = argparse.ArgumentParser(description="HyperSpace MCP Stdio Bridge")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="URL dell'endpoint /mcp")
    parser.add_argument("--token", default=DEFAULT_TOKEN, help="Token Bearer per autenticazione MCP")
    args = parser.parse_args()

    endpoint = args.endpoint
    token = args.token

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            req_data = json.loads(line)
        except Exception as exc:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc}"},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()
            continue

        is_notification = ("id" not in req_data) or (req_data.get("id") is None)
        method = req_data.get("method", "")

        try:
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(req_data).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8").strip()
                if body:
                    sys.stdout.write(body + "\n")
                    sys.stdout.flush()
                elif not is_notification:
                    # In caso di body vuoto ma richiesta non-notifica
                    ok_resp = {"jsonrpc": "2.0", "id": req_data.get("id"), "result": {}}
                    sys.stdout.write(json.dumps(ok_resp) + "\n")
                    sys.stdout.flush()
        except urllib.error.HTTPError as http_err:
            try:
                err_body = http_err.read().decode("utf-8")
                sys.stdout.write(err_body + "\n")
            except Exception:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": req_data.get("id"),
                    "error": {"code": -32603, "message": f"HTTP {http_err.code}: {http_err.reason}"},
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()
        except Exception as exc:
            err_resp = {
                "jsonrpc": "2.0",
                "id": req_data.get("id"),
                "error": {"code": -32603, "message": f"Bridge error: {exc}"},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
