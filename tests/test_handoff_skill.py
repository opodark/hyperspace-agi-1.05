# SPDX-License-Identifier: Apache-2.0
"""Test di integrità e installazione della skill universale handoff."""

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = REPO_ROOT / "vendor" / "handoff-skill"
SKILL_FILE = VENDOR_DIR / "skills" / "handoff" / "SKILL.md"
MANIFEST_FILE = VENDOR_DIR / "manifest.json"
LICENSE_FILE = VENDOR_DIR / "LICENSE"


def test_handoff_skill_files_exist():
    assert VENDOR_DIR.is_dir()
    assert SKILL_FILE.is_file()
    assert MANIFEST_FILE.is_file()
    assert LICENSE_FILE.is_file()


def test_handoff_skill_manifest_hashes():
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    files = manifest.get("files", {})

    for rel_path, expected_hash in files.items():
        target = VENDOR_DIR / rel_path
        assert target.is_file(), f"File dichiarato mancante: {rel_path}"
        actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        assert actual_hash == expected_hash, f"Hash non coincidente per {rel_path}: {actual_hash} != {expected_hash}"


def test_handoff_skill_frontmatter_content():
    content = SKILL_FILE.read_text(encoding="utf-8")
    assert content.startswith("---")
    assert "name: handoff" in content
    assert "description:" in content
    assert "$TMPDIR" in content or "/tmp" in content
    assert "suggested skills" in content


def test_handoff_symlink_in_workspace():
    workspace_link = REPO_ROOT / ".agents" / "skills" / "handoff"
    assert workspace_link.exists(), "Link in .agents/skills/handoff mancante"
    resolved = workspace_link.resolve()
    assert resolved == (VENDOR_DIR / "skills" / "handoff").resolve()
