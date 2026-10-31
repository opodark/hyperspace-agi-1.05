# SPDX-License-Identifier: Apache-2.0
"""Test di integrità e installazione delle skill vendorizzate teach,
marketing-psychology e anatomy (stesso schema di test_handoff_skill.py)."""

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SKILLS = {
    "teach": {
        "vendor_dir": REPO_ROOT / "vendor" / "teach-skill",
        "skill_file": REPO_ROOT / "vendor" / "teach-skill" / "skills" / "teach" / "SKILL.md",
        "name_marker": "name: teach",
    },
    "marketing-psychology": {
        "vendor_dir": REPO_ROOT / "vendor" / "marketing-psychology-skill",
        "skill_file": REPO_ROOT / "vendor" / "marketing-psychology-skill" / "skills"
        / "marketing-psychology" / "SKILL.md",
        "name_marker": "name: marketing-psychology",
    },
    "anatomy": {
        "vendor_dir": REPO_ROOT / "vendor" / "anatomy-skill",
        "skill_file": REPO_ROOT / "vendor" / "anatomy-skill" / "skills" / "anatomy" / "SKILL.md",
        "name_marker": "name: anatomy",
    },
    "last30days": {
        "vendor_dir": REPO_ROOT / "vendor" / "last30days-skill",
        "skill_file": REPO_ROOT / "vendor" / "last30days-skill" / "skills" / "last30days" / "SKILL.md",
        "name_marker": "name: last30days",
    },
}


def test_vendor_skills_files_exist():
    for skill_name, info in SKILLS.items():
        vendor_dir = info["vendor_dir"]
        assert vendor_dir.is_dir(), f"{skill_name}: vendor dir mancante"
        assert info["skill_file"].is_file(), f"{skill_name}: SKILL.md mancante"
        assert (vendor_dir / "manifest.json").is_file(), f"{skill_name}: manifest.json mancante"
        assert (vendor_dir / "LICENSE").is_file(), f"{skill_name}: LICENSE mancante"
        assert (vendor_dir / "install.sh").is_file(), f"{skill_name}: install.sh mancante"


def test_vendor_skills_manifest_hashes():
    for skill_name, info in SKILLS.items():
        manifest = json.loads((info["vendor_dir"] / "manifest.json").read_text(encoding="utf-8"))
        files = manifest.get("files", {})
        assert files, f"{skill_name}: manifest senza files"
        for rel_path, expected_hash in files.items():
            target = info["vendor_dir"] / rel_path
            assert target.is_file(), f"{skill_name}: file dichiarato mancante: {rel_path}"
            actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            assert actual_hash == expected_hash, (
                f"{skill_name}: hash non coincidente per {rel_path}: "
                f"{actual_hash} != {expected_hash}"
            )


def test_vendor_skills_frontmatter_content():
    for skill_name, info in SKILLS.items():
        content = info["skill_file"].read_text(encoding="utf-8")
        assert content.startswith("---"), f"{skill_name}: frontmatter mancante"
        assert info["name_marker"] in content, f"{skill_name}: 'name:' non coincide"
        assert "description:" in content, f"{skill_name}: description mancante"


def test_vendor_skills_symlinks_in_workspace():
    for skill_name, info in SKILLS.items():
        workspace_link = REPO_ROOT / ".agents" / "skills" / skill_name
        assert workspace_link.exists(), f"{skill_name}: link in .agents/skills/{skill_name} mancante"
        skill_dir = info["skill_file"].parent
        assert workspace_link.resolve() == skill_dir.resolve(), (
            f"{skill_name}: symlink non punta al percorso vendorizzato atteso"
        )
