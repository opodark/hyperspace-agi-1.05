# SPDX-License-Identifier: Apache-2.0
"""Test di integrità e verifica della skill vendorizzata CLI-Anything (HKUDS)."""

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = REPO_ROOT / "vendor" / "cli-anything"
SKILL_FILE = VENDOR_DIR / "skills" / "cli-hub-meta-skill" / "SKILL.md"
MANIFEST_FILE = VENDOR_DIR / "manifest.json"
LICENSE_FILE = VENDOR_DIR / "LICENSE"


def test_cli_anything_files_exist():
    assert VENDOR_DIR.is_dir()
    assert SKILL_FILE.is_file()
    assert MANIFEST_FILE.is_file()
    assert LICENSE_FILE.is_file()


def test_cli_anything_manifest_hashes():
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    files = manifest.get("files", {})

    for rel_path, expected_hash in files.items():
        target = VENDOR_DIR / rel_path
        assert target.is_file(), f"File dichiarato mancante: {rel_path}"
        actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        assert actual_hash == expected_hash, f"Hash non coincidente per {rel_path}: {actual_hash} != {expected_hash}"


def test_cli_anything_frontmatter():
    content = SKILL_FILE.read_text(encoding="utf-8")
    assert content.startswith("---")
    assert "name: cli-hub-meta-skill" in content
    assert "description:" in content
    assert "cli-hub" in content


def test_cli_anything_workspace_symlink():
    link = REPO_ROOT / ".agents" / "skills" / "cli-hub-meta-skill"
    assert link.exists()
    assert link.resolve() == (VENDOR_DIR / "skills" / "cli-hub-meta-skill").resolve()
