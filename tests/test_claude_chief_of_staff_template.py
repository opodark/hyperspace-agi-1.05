# SPDX-License-Identifier: Apache-2.0
"""Test di integrità del template prodotto 'AI Chief of Staff' (vendor/claude-chief-of-staff).

Non è una Agent Skill per i nostri agenti: niente symlink da verificare in
.agents/skills/, solo l'integrità del template da fornire ai clienti.
"""

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = REPO_ROOT / "vendor" / "claude-chief-of-staff"
MANIFEST_FILE = VENDOR_DIR / "manifest.json"
LICENSE_FILE = VENDOR_DIR / "LICENSE"
INSTALL_SCRIPT = VENDOR_DIR / "install.sh"


def test_claude_chief_of_staff_files_exist():
    assert VENDOR_DIR.is_dir()
    assert MANIFEST_FILE.is_file()
    assert LICENSE_FILE.is_file()
    assert INSTALL_SCRIPT.is_file()
    for rel in ("CLAUDE.md", "goals.yaml", "my-tasks.yaml", "schedules.yaml",
                "commands/gm.md", "commands/triage.md", "commands/my-tasks.md",
                "commands/enrich.md", "contacts/example-contact.md"):
        assert (VENDOR_DIR / rel).is_file(), f"file template mancante: {rel}"


def test_claude_chief_of_staff_manifest_hashes():
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    files = manifest.get("files", {})
    assert files
    for rel_path, expected_hash in files.items():
        target = VENDOR_DIR / rel_path
        assert target.is_file(), f"File dichiarato mancante: {rel_path}"
        actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        assert actual_hash == expected_hash, f"Hash non coincidente per {rel_path}"


def test_claude_chief_of_staff_install_script_targets_client_home():
    content = INSTALL_SCRIPT.read_text(encoding="utf-8")
    assert "$HOME/.claude" in content
