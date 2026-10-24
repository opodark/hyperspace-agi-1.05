# SPDX-License-Identifier: Apache-2.0
"""Test per scripts/mcp_stdio_bridge.py e integrazione MCP con Control Plane."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestMcpBridge(unittest.TestCase):
    def test_mcp_stdio_bridge_init_and_list(self):
        script = str(REPO_ROOT / "scripts" / "mcp_stdio_bridge.py")
        proc = subprocess.Popen(
            [sys.executable, script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        init_msg = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "clientInfo": {"name": "openwork-test"},
            },
        }) + "\n"

        list_msg = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }) + "\n"

        stdout, stderr = proc.communicate(init_msg + list_msg, timeout=10)
        lines = [line.strip() for line in stdout.strip().split("\n") if line.strip()]
        self.assertGreaterEqual(len(lines), 2, f"Expected 2 lines, got: {stdout}")

        resp1 = json.loads(lines[0])
        self.assertEqual(resp1.get("id"), 1)
        self.assertIn("serverInfo", resp1.get("result", {}))

        resp2 = json.loads(lines[1])
        self.assertEqual(resp2.get("id"), 2)
        tools = resp2.get("result", {}).get("tools", [])
        self.assertIsInstance(tools, list)
        self.assertGreater(len(tools), 0)
        tool_names = [t["name"] for t in tools]
        self.assertIn("web_search", tool_names)
        self.assertIn("moltbook_status", tool_names)


if __name__ == "__main__":
    unittest.main()
