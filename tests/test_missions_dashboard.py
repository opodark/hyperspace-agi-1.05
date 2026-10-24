# SPDX-License-Identifier: Apache-2.0
"""Test suite per la dashboard Mission Control & Scouting Radar."""

import urllib.request
import json
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MISSIONS_HTML = REPO_ROOT / "web-node" / "apps" / "playground" / "missions.html"
DIST_MISSIONS_HTML = REPO_ROOT / "dist" / "web-node-aruba" / "apps" / "playground" / "missions.html"


def test_missions_html_exists():
    assert MISSIONS_HTML.exists(), "web-node/apps/playground/missions.html deve esistere"
    assert DIST_MISSIONS_HTML.exists(), "dist/web-node-aruba/apps/playground/missions.html deve esistere"

    content = MISSIONS_HTML.read_text(encoding="utf-8")
    assert "Mission Control & Scouting Radar" in content
    assert "Radar Scouting" in content
    assert "Task DAG" in content
    assert "Mappa Flusso Cognitivo" in content
    assert "Agent-Reach" in content


def test_cockpit_service_missions_and_scouting_routes():
    # Test HTTP 8090 se il cockpit service è attivo
    try:
        req = urllib.request.Request("http://127.0.0.1:8090/missions.html")
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 200
            html = resp.read().decode("utf-8")
            assert "HyperSpace Sovereign Mesh" in html

        req_scout = urllib.request.Request("http://127.0.0.1:8090/api/mesh-scouting")
        with urllib.request.urlopen(req_scout, timeout=3) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("ok") is True

        req_missions = urllib.request.Request("http://127.0.0.1:8090/api/missions")
        with urllib.request.urlopen(req_missions, timeout=3) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert "missions" in data
    except urllib.error.URLError:
        pytest.skip("Cockpit service su porta 8090 non attivo in questo worker, test locale saltato")
