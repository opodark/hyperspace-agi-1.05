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
