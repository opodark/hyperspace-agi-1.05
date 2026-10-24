# SPDX-License-Identifier: Apache-2.0
"""
Test per scripts/upstream_auto_sync.py.
Verifica i guardrail di sicurezza, la rilevazione degli update upstream,
la corretta esecuzione dei controlli di integrità e il report di stato.
"""

from pathlib import Path
import pytest

from scripts.upstream_auto_sync import UpstreamAutoSync, sha256_file, REPO_ROOT


def test_sha256_file():
    manifest_p = REPO_ROOT / "vendor" / "agency-agents" / "manifest.json"
    assert manifest_p.exists()
    digest = sha256_file(manifest_p)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_auto_sync_check_mode():
    engine = UpstreamAutoSync()
    summary = engine.run_all(apply=False)

    assert "timestamp" in summary
    assert summary["apply_mode"] is False
    assert "components" in summary
    assert len(summary["components"]) >= 4

    names = {c["component"] for c in summary["components"]}
    assert "rea_agents" in names
    assert "agency_agents" in names
    assert "anydoc_skills" in names
    assert "hermes_memory" in names
    assert "open_webui" in names


def test_open_webui_check():
    engine = UpstreamAutoSync()
    res = engine.check_open_webui()
    assert res["component"] == "open_webui"
    assert "current_version" in res
    assert "status" in res


def test_hermes_memory_check():
    engine = UpstreamAutoSync()
    res = engine.check_hermes()
    assert res["component"] == "hermes_memory"
    assert res["tests_passed"] is True
    assert res["status"] == "HEALTHY"
