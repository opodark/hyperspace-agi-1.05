#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# scripts/mesh_exec.py
"""CLI Sovrana HyperSpace per l'esecuzione di comandi remoti sui nodi della mesh.

Invia comandi shell autenticati con firma crittografica ECDSA / Ed25519
direttamente alle porte dei nodi Sovereign (:8081).

Uso:
  python scripts/mesh_exec.py --target omen -- "python -m pytest tests/test_resin_bridge.py"
  python scripts/mesh_exec.py --target asus -- "hostname"
  python scripts/mesh_exec.py --target http://100.104.238.125:8081 -- "dir"
  python scripts/mesh_exec.py --all -- "git status --short"
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.identity import generate_or_load_identity, make_request_headers, sign_message

NODE_ALIASES = {
    "omen": os.getenv("OMEN_NODE_URL", "http://100.104.238.125:8081").rstrip("/"),
    "asus": os.getenv("ASUS_NODE_URL", "http://100.64.31.18:8081").rstrip("/"),
    "mac": os.getenv("MAC_NODE_URL", "http://127.0.0.1:8084").rstrip("/"),
    "hub": os.getenv("MAC_NODE_URL", "http://127.0.0.1:8084").rstrip("/"),
}


def resolve_endpoint(target: str) -> str:
    cleaned = target.lower().strip().rstrip("/")
    if cleaned in NODE_ALIASES:
        return NODE_ALIASES[cleaned]
    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        return cleaned
    # Se è un IP o hostname puro, default porta 8081
    if ":" in cleaned:
        return f"http://{cleaned}"
    return f"http://{cleaned}:8081"


def execute_remote_cmd(
    endpoint: str,
    command: str,
    timeout: float = 60.0,
    cwd: str = "",
) -> dict:
    identity = generate_or_load_identity()
    url = f"{endpoint}/shell/exec"

    payload_data = {
        "command": command,
        "timeout": timeout,
        "cwd": cwd,
        "pubkey": identity["public_key"],
        "node_id": identity["node_id"],
        "timestamp": int(time.time()),
    }
    signed_payload = sign_message(payload_data, identity["_private_key"])
    body_bytes = json.dumps(signed_payload).encode("utf-8")

    headers = make_request_headers(
        node_id=identity["node_id"],
        pubkey_hex=identity["public_key"],
        private_key=identity["_private_key"],
        body=body_bytes,
    )
    headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout + 5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            data["http_code"] = resp.getcode()
            data["roundtrip_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
            return data
    except urllib.error.HTTPError as err:
        err_body = err.read().decode("utf-8", errors="replace")
        return {
            "error": f"HTTP {err.code}: {err_body}",
            "http_code": err.code,
            "exit_code": -1,
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "http_code": 0,
            "exit_code": -1,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="HyperSpace Mesh Remote Shell CLI (E2EE Signed Execution)"
    )
    parser.add_argument(
        "--target",
        "-t",
        default="omen",
        help="Target node: 'omen', 'asus', 'mac', oppure URL (es. http://100.104.238.125:8081)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Esegui il comando in sequenza su tutti i nodi noti (omen, asus)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Timeout in secondi per il comando remoto (default 60s)",
    )
    parser.add_argument(
        "--cwd",
        default="",
        help="Directory di lavoro remota (opzionale, default repo root)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Stampa la risposta grezza in formato JSON",
    )
    parser.add_argument(
        "cmd",
        nargs=argparse.REMAINDER,
        help="Comando da eseguire sul nodo remoto (usa '-- cmd')",
    )

    args = parser.parse_args()

    command_parts = args.cmd
    if command_parts and command_parts[0] == "--":
        command_parts = command_parts[1:]
    command_str = " ".join(command_parts).strip()

    if not command_str:
        parser.print_help()
        print("\nErrore: nessun comando specificato. Esempio: python scripts/mesh_exec.py -t omen -- dir")
        return 2

    targets = ["omen", "asus"] if args.all else [args.target]
    overall_exit = 0

    for tgt in targets:
        endpoint = resolve_endpoint(tgt)
        if not args.json:
            print(f"[{tgt.upper()} @ {endpoint}] > {command_str}")

        res = execute_remote_cmd(
            endpoint=endpoint,
            command=command_str,
            timeout=args.timeout,
            cwd=args.cwd,
        )

        if args.json:
            print(json.dumps(res, indent=2))
            if res.get("exit_code", 0) != 0:
                overall_exit = 1
            continue

        if "error" in res and res.get("http_code", 0) != 200:
            print(f"  ❌ Errore nodo: {res['error']}\n")
            overall_exit = 1
            continue

        stdout = res.get("stdout", "")
        stderr = res.get("stderr", "")
        exit_code = res.get("exit_code", 0)
        ms = res.get("elapsed_ms", res.get("roundtrip_ms", 0))

        if stdout:
            print(stdout.rstrip())
        if stderr:
            print(f"[stderr]:\n{stderr.rstrip()}", file=sys.stderr)

        badge = "🟢 OK" if exit_code == 0 else f"🔴 FAILED (code {exit_code})"
        print(f"  └─ {badge} in {ms} ms\n")
        if exit_code != 0:
            overall_exit = exit_code

    return overall_exit


if __name__ == "__main__":
    raise SystemExit(main())
