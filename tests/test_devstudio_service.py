# SPDX-License-Identifier: Apache-2.0
"""Test suite per HyperDev Sovereign Studio (Antigravity Mesh Console)."""

import json
import urllib.request
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEVSTUDIO_HTML = REPO_ROOT / "web-node" / "apps" / "playground" / "devstudio.html"
DIST_DEVSTUDIO_HTML = REPO_ROOT / "dist" / "web-node-aruba" / "apps" / "playground" / "devstudio.html"


def test_devstudio_html_exists():
    assert DEVSTUDIO_HTML.exists(), "web-node/apps/playground/devstudio.html deve esistere"
    assert DIST_DEVSTUDIO_HTML.exists(), "dist/web-node-aruba/apps/playground/devstudio.html deve esistere"

    content = DEVSTUDIO_HTML.read_text(encoding="utf-8")
    assert "HyperDev Sovereign Studio" in content
    assert "Mission DAG" in content
    assert "Sandbox Diff" in content
    assert "Pytest Console" in content


def test_devstudio_service_endpoints():
    try:
        # 1. Test HTML route
        req = urllib.request.Request("http://127.0.0.1:8090/devstudio.html")
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert "HyperDev Sovereign Studio" in html

        # 2. Test Run Tests API
        req_tests = urllib.request.Request(
            "http://127.0.0.1:8090/api/devstudio/run-tests",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req_tests, timeout=10) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert "exit_code" in data
            assert data["exit_code"] == 0

        # 3. Test DevStudio Chat API
        chat_payload = json.dumps({"prompt": "Esegui test pytest"}).encode("utf-8")
        req_chat = urllib.request.Request(
            "http://127.0.0.1:8090/api/devstudio/chat",
            data=chat_payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req_chat, timeout=10) as resp:
            assert resp.status == 200
            chat_data = json.loads(resp.read().decode("utf-8"))
            assert chat_data.get("ok") is True
            assert "response" in chat_data

        # 4. Test Apply Diff API
        diff_payload = json.dumps({"diff": "+ # HyperSpace Sovereign Test Diff"}).encode("utf-8")
        req_diff = urllib.request.Request(
            "http://127.0.0.1:8090/api/devstudio/apply-diff",
            data=diff_payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req_diff, timeout=5) as resp:
            assert resp.status == 200
            diff_data = json.loads(resp.read().decode("utf-8"))
            assert diff_data.get("ok") is True
    except urllib.error.URLError:
        pytest.skip("Cockpit service su porta 8090 non attivo in questo worker, test locale saltato")
