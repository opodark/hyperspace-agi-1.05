# SPDX-License-Identifier: Apache-2.0
"""
Test per scripts/integrations_manager.py e integrations/integrations.manifest.yaml.
Verifica il parsing del manifest, la risoluzione dei percorsi, il controllo dello stato
e la sicurezza operativa (read-only, nessuna mutazione incontrollata).
"""

from pathlib import Path
import tempfile
import pytest
import yaml

from scripts.integrations_manager import IntegrationsManager, REPO_ROOT


def test_manifest_loads_and_has_keys():
    manager = IntegrationsManager()
    assert "version" in manager.config
    assert "integrations" in manager.config
    integrations = manager.integrations
    assert len(integrations) >= 5
    assert "tiktok_editor" in integrations
    assert "comfyui_ipadapter_plus" in integrations
    assert "chrome_extension" in integrations


def test_path_resolution_with_bash_syntax(monkeypatch):
    manager = IntegrationsManager()
    # Test path standard
    p = manager.resolve_path("integrations/tiktok_editor/app")
    assert p is not None
    assert p.is_dir()

    # Test espansione ${VAR:-default}
    monkeypatch.delenv("TEST_CUSTOM_DIR", raising=False)
    resolved_default = manager.resolve_path("${TEST_CUSTOM_DIR:-/tmp/my_default_dir}/sub")
    assert resolved_default == Path("/tmp/my_default_dir/sub")

    monkeypatch.setenv("TEST_CUSTOM_DIR", "/custom/override")
    resolved_env = manager.resolve_path("${TEST_CUSTOM_DIR:-/tmp/my_default_dir}/sub")
    assert resolved_env == Path("/custom/override/sub")


def test_status_returns_valid_structure():
    manager = IntegrationsManager()
    statuses = manager.status()
    assert isinstance(statuses, list)
    assert len(statuses) > 0

    tiktok_status = next(s for s in statuses if s["id"] == "tiktok_editor")
    assert tiktok_status["exists"] is True
    assert tiktok_status["category"] == "vendored"
    assert tiktok_status["status_label"] == "VENDORED_LOCAL"


def test_custom_temporary_manifest():
    with tempfile.NamedTemporaryFile("w+", suffix=".yaml", delete=False) as tmp:
        sample_data = {
            "version": "1.0-test",
            "integrations": {
                "dummy_module": {
                    "name": "Dummy Test Module",
                    "category": "test",
                    "local_path": "tests",
                    "pinned_ref": "v1.0",
                    "test_command": "echo 'ok test'",
                }
            },
        }
        yaml.safe_dump(sample_data, tmp)
        tmp_path = Path(tmp.name)

    try:
        manager = IntegrationsManager(manifest_path=tmp_path)
        statuses = manager.status()
        assert len(statuses) == 1
        assert statuses[0]["id"] == "dummy_module"
        assert statuses[0]["exists"] is True

        # Test verify
        res = manager.run_verify("dummy_module")
        assert res["success"] is True

        # Test set_pin
        manager.set_pin("dummy_module", "v2.0-new")
        updated_manager = IntegrationsManager(manifest_path=tmp_path)
        assert updated_manager.integrations["dummy_module"]["pinned_ref"] == "v2.0-new"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_format_table():
    manager = IntegrationsManager()
    statuses = manager.status()
    table = manager.format_table(statuses, with_upstream=False)
    assert "| ID " in table
    assert "tiktok_editor" in table


def _check_with(monkeypatch, pinned_ref, local_sha, remote_sha):
    """Esegue check_upstream su una sola voce finta, senza rete né filesystem."""
    manager = IntegrationsManager()
    manager.config = {"integrations": {"x": {"upstream_url": "https://example.invalid/x.git", "pinned_ref": pinned_ref}}}
    entry = {"id": "x", "upstream_url": "https://example.invalid/x.git", "pinned_ref": pinned_ref,
             "git": {"is_git": bool(local_sha), "commit_sha": local_sha}}
    monkeypatch.setattr(manager, "status", lambda integration_id=None: [dict(entry)])
    monkeypatch.setattr(manager, "query_remote_ref", lambda *a, **k: remote_sha)
    return manager.check_upstream()[0]["upstream_status"]


def test_check_upstream_compares_the_right_reference(monkeypatch):
    a, b = "a" * 40, "b" * 40
    # pin su un ramo/tag/versione: conta il commit locale, non la stringa del pin
    assert _check_with(monkeypatch, "main", a, a) == "UP_TO_DATE"
    assert _check_with(monkeypatch, "main", a, b) == "NEW_UPSTREAM_AVAILABLE"
    assert _check_with(monkeypatch, "v0.12.0", a, a) == "UP_TO_DATE"
    # pin su un commit: conta il pin, anche abbreviato
    assert _check_with(monkeypatch, a, None, a) == "UP_TO_DATE"
    assert _check_with(monkeypatch, a[:8], None, a) == "UP_TO_DATE"
    assert _check_with(monkeypatch, a, None, b) == "NEW_UPSTREAM_AVAILABLE"
    # né commit locale né pin su commit: raggiungibile ma non confrontabile
    assert _check_with(monkeypatch, "main", None, a) == "CHECKED"
    assert _check_with(monkeypatch, "6.7.0", None, a) == "CHECKED"
    assert _check_with(monkeypatch, "main", a, None) == "REMOTE_UNREACHABLE"
