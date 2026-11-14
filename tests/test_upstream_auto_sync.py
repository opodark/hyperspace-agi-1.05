# SPDX-License-Identifier: Apache-2.0
"""
Test per scripts/upstream_auto_sync.py.
Verifica i guardrail di sicurezza, la rilevazione degli update upstream,
la corretta esecuzione dei controlli di integrità e il report di stato.
"""

from pathlib import Path
import pytest

import scripts.upstream_auto_sync as auto_sync
from scripts.upstream_auto_sync import (
    UpstreamAutoSync,
    sha256_file,
    snapshot_files,
    restore_files,
    REPO_ROOT,
)


@pytest.fixture(autouse=True)
def _reports_in_tmp(tmp_path, monkeypatch):
    """I test non devono riscrivere i veri data/reports/auto_sync_*."""
    monkeypatch.setattr(auto_sync, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(auto_sync, "STATUS_FILE", tmp_path / "auto_sync_status.json")
    monkeypatch.setattr(auto_sync, "HISTORY_FILE", tmp_path / "auto_sync_history.jsonl")


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
    assert (auto_sync.STATUS_FILE).exists()


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


def test_rollback_restores_files_not_only_manifest(tmp_path):
    existing = tmp_path / "bundle" / "SKILL.md"
    existing.parent.mkdir()
    existing.write_text("vecchio")
    missing = tmp_path / "bundle" / "nuovo.md"

    snap = snapshot_files([existing, missing])
    existing.write_text("scaricato dall'upstream")
    missing.write_text("file che prima non c'era")
    restore_files(snap)

    assert existing.read_text() == "vecchio"
    assert not missing.exists()
