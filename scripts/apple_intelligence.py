#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Local Apple Foundation Models worker: explicit build, CLI and MCP stdio."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "data/apple-intelligence/worker"
SOURCE = ROOT / "integrations/apple-intelligence/worker.swift"
MAX_INPUT = 65536
PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
TOOLS = [
    {"name": "apple_intelligence_status",
     "description": "Check availability of the on-device Apple model on this Mac.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "apple_intelligence_text",
     "description": "Delegate a short text task to Apple's on-device model: summarization, "
                    "extraction or rewriting. Plain text output; no file access, shell, "
                    "image generation or cloud fallback. Apple guardrails apply. "
                    "Input may exceed the model context even below the byte limit.",
     "inputSchema": {"type": "object", "properties": {
         "prompt": {"type": "string", "minLength": 1},
         "instructions": {"type": "string", "default": ""},
         "max_tokens": {"type": "integer", "minimum": 1, "maximum": 1024, "default": 256}},
         "required": ["prompt"], "additionalProperties": False}},
]


def request_payload(arguments):
    if not isinstance(arguments, dict) or set(arguments) - {"prompt", "instructions", "max_tokens"}:
        raise ValueError("Expected prompt, optional instructions and max_tokens")
    prompt = arguments.get("prompt")
    instructions = arguments.get("instructions", "")
    tokens = arguments.get("max_tokens", 256)
    if not isinstance(prompt, str) or not prompt.strip() or not isinstance(instructions, str):
        raise ValueError("prompt must be nonempty text; instructions must be text")
    if type(tokens) is not int or not 1 <= tokens <= 1024:
        raise ValueError("max_tokens must be an integer from 1 to 1024")
    encoded = json.dumps({"prompt": prompt, "instructions": instructions,
                          "max_tokens": tokens}, ensure_ascii=False)
    if len(encoded.encode()) > MAX_INPUT:
        raise ValueError("input_too_large: maximum 65536 UTF-8 bytes")
    return encoded


def invoke(arguments=None):
    payload = None if arguments is None else request_payload(arguments)
    if not BINARY.is_file():
        return {"ok": False, "error": "worker_not_built",
                "action": "Run scripts/apple_intelligence.py --build on macOS 26+"}
    command = [str(BINARY)] + (["--check"] if arguments is None else [])
    try:
        result = subprocess.run(command, input=payload, capture_output=True, text=True,
                                timeout=20 if arguments is None else 90, check=False)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "worker_timeout"}
    except OSError:
        return {"ok": False, "error": "worker_unavailable"}
    if result.returncode:
        return {"ok": False, "error": "worker_failed", "exit_code": result.returncode}
    try:
        value = json.loads(result.stdout)
        if not isinstance(value, dict) or type(value.get("ok")) is not bool:
            raise ValueError("Invalid worker envelope")
        if value["ok"] and arguments is not None and not isinstance(value.get("text"), str):
            raise ValueError("Missing generated text")
        return value
    except (ValueError, TypeError):
        return {"ok": False, "error": "invalid_worker_output"}


def rpc(message, run=invoke):
    def error(code, text):
        return {"jsonrpc": "2.0", "id": message.get("id") if isinstance(message, dict) else None,
                "error": {"code": code, "message": text}}

    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return error(-32600, "Invalid request")
    method = message.get("method")
    if not isinstance(method, str):
        return error(-32600, "Invalid method")
    if "id" not in message:
        # Notifications must never trigger generation.
        return None
    params = message.get("params", {})
    if not isinstance(params, dict):
        return error(-32602, "params must be an object")
    if method == "initialize":
        requested = params.get("protocolVersion")
        result = {"protocolVersion": requested if requested in PROTOCOLS else PROTOCOLS[0],
                  "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": "hyperspace-apple-intelligence", "version": "0.1.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        name, args = params.get("name"), params.get("arguments", {})
        try:
            if name == "apple_intelligence_status":
                if args != {}:
                    raise ValueError("status accepts no arguments")
                value = run()
            elif name == "apple_intelligence_text":
                request_payload(args)
                value = run(args)
            else:
                return error(-32602, "Unknown tool")
        except ValueError as exc:
            return error(-32602, str(exc))
        result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}],
                  "isError": not value.get("ok", False)}
    else:
        return error(-32601, "Method not found")
    return {"jsonrpc": "2.0", "id": message["id"], "result": result}


def serve(source, destination):
    # Serial execution bounds model concurrency to one request per process.
    while True:
        line = source.readline(MAX_INPUT + 1)
        if not line:
            return
        if len(line) > MAX_INPUT:
            while line and not line.endswith(b"\n"):
                line = source.readline(MAX_INPUT + 1)
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32600, "message": "Request too large"}}
        else:
            try:
                response = rpc(json.loads(line))
            except (ValueError, UnicodeDecodeError):
                response = {"jsonrpc": "2.0", "id": None,
                            "error": {"code": -32700, "message": "Parse error"}}
        if response is not None:
            destination.write(json.dumps(response, ensure_ascii=False) + "\n")
            destination.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--mcp", action="store_true")
    mode.add_argument("--prompt")
    parser.add_argument("--instructions", default="")
    parser.add_argument("--max-tokens", type=int, default=256)
    args = parser.parse_args()
    if args.build:
        BINARY.parent.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run([
            "xcrun", "swiftc", "-parse-as-library", "-module-cache-path",
            str(BINARY.parent / "module-cache"), str(SOURCE), "-o", str(BINARY)], check=False)
        return completed.returncode
    if args.mcp:
        serve(sys.stdin.buffer, sys.stdout)
        return 0
    try:
        result = invoke() if args.check else invoke({"prompt": args.prompt,
                        "instructions": args.instructions, "max_tokens": args.max_tokens})
    except ValueError as exc:
        result = {"ok": False, "error": "invalid_input", "detail": str(exc)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
