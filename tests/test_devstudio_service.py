# SPDX-License-Identifier: Apache-2.0
"""Test suite per HyperDev Sovereign Studio 2.0 (Antigravity Mesh IDE)."""

import json
import urllib.request
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEVSTUDIO_HTML = REPO_ROOT / "web-node" / "apps" / "playground" / "devstudio.html"
DIST_DEVSTUDIO_HTML = REPO_ROOT / "dist" / "web-node-aruba" / "apps" / "playground" / "devstudio.html"


def test_devstudio_html_exists():
    assert DEVSTUDIO_HTML.exists(), "web-node/apps/playground/devstudio.html deve esistere per il Creatore locale"
    assert not DIST_DEVSTUDIO_HTML.exists(), "dist/web-node-aruba non deve contenere devstudio.html per sicurezza (solo locale)"

    content = DEVSTUDIO_HTML.read_text(encoding="utf-8")
    assert "HyperDev Sovereign Studio" in content
    assert "Code Editor" in content
    assert "Repository Files" in content
    assert "Git & Diff" in content
    assert "Pytest" in content
    assert "Shell" in content
    assert "Access Denied" in content


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

        # 5. Test Files API (Directory Explorer)
        req_files = urllib.request.Request("http://127.0.0.1:8090/api/devstudio/files?path=tests")
        with urllib.request.urlopen(req_files, timeout=5) as resp:
            assert resp.status == 200
            files_data = json.loads(resp.read().decode("utf-8"))
            assert files_data.get("ok") is True
            assert len(files_data.get("items", [])) > 0

        # 6. Test File Read API
        req_file = urllib.request.Request("http://127.0.0.1:8090/api/devstudio/file?path=tests/test_devstudio_service.py")
        with urllib.request.urlopen(req_file, timeout=5) as resp:
            assert resp.status == 200
            file_data = json.loads(resp.read().decode("utf-8"))
            assert file_data.get("ok") is True
            assert "HyperDev" in file_data.get("content", "")

        # 7. Test Git Status API
        req_git = urllib.request.Request("http://127.0.0.1:8090/api/devstudio/git-status")
        with urllib.request.urlopen(req_git, timeout=5) as resp:
            assert resp.status == 200
            git_data = json.loads(resp.read().decode("utf-8"))
            assert git_data.get("ok") is True
            assert "branch" in git_data

        # 8. Test Terminal Command API
        term_payload = json.dumps({"command": "echo 'sovereign-devstudio-ok'"}).encode("utf-8")
        req_term = urllib.request.Request(
            "http://127.0.0.1:8090/api/devstudio/terminal",
            data=term_payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req_term, timeout=5) as resp:
            assert resp.status == 200
            term_data = json.loads(resp.read().decode("utf-8"))
            assert term_data.get("ok") is True
            assert "sovereign-devstudio-ok" in term_data.get("stdout", "")
    except urllib.error.URLError:
        pytest.skip("Cockpit service su porta 8090 non attivo in questo worker, test locale saltato")
