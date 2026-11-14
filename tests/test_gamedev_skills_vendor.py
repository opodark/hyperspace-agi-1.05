# SPDX-License-Identifier: Apache-2.0
"""Test di integrità, manifest, symlink e frontmatter per vendor/gamedev-skills."""

import hashlib
import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = REPO_ROOT / "vendor" / "gamedev-skills"
MANIFEST_FILE = VENDOR_DIR / "manifest.json"
ROUTER_SKILL_FILE = VENDOR_DIR / "router" / "SKILL.md"
INTEGRATIONS_MANIFEST = REPO_ROOT / "integrations" / "integrations.manifest.yaml"

EXPECTED_CATEGORIES = {
    "disciplines",
    "ebitengine",
    "genres",
    "godot",
    "other-engines",
    "unity",
    "unreal",
    "web-engines",
    "workflows",
}


def test_gamedev_skills_files_and_categories_exist():
    assert VENDOR_DIR.is_dir()
    assert (VENDOR_DIR / "LICENSE").is_file()
    assert (VENDOR_DIR / "NOTICE").is_file()
    assert MANIFEST_FILE.is_file()
    assert (VENDOR_DIR / "install.sh").is_file()
    assert ROUTER_SKILL_FILE.is_file()

    skills_root = VENDOR_DIR / "skills"
    assert skills_root.is_dir()
    found_categories = {p.name for p in skills_root.iterdir() if p.is_dir()}
    assert found_categories == EXPECTED_CATEGORIES


def test_gamedev_skills_count_is_79_plus_router():
    skill_files = sorted((VENDOR_DIR / "skills").glob("*/*/SKILL.md"))
    assert len(skill_files) == 79
    all_skill_mds = [ROUTER_SKILL_FILE] + skill_files
    assert len(all_skill_mds) == 80


def test_gamedev_skills_manifest_hashes():
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    assert manifest.get("repository") == "https://github.com/gamedev-skills/awesome-gamedev-agent-skills"
    assert manifest.get("commit") == "c6ca6c41c839b68319ffc08430b99ab768debc32"

    files = manifest.get("files", {})
    assert len(files) == 254

    for rel_path, expected_hash in files.items():
        target = VENDOR_DIR / rel_path
        assert target.is_file(), f"File dichiarato mancante: {rel_path}"
        actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        assert actual_hash == expected_hash, (
            f"Hash non coincidente per {rel_path}: {actual_hash} != {expected_hash}"
        )


def test_gamedev_skills_frontmatter_valid():
    skill_files = [ROUTER_SKILL_FILE] + sorted((VENDOR_DIR / "skills").glob("*/*/SKILL.md"))
    for skill_file in skill_files:
        content = skill_file.read_text(encoding="utf-8")
        assert content.startswith("---"), f"Frontmatter mancante in {skill_file}"
        parts = content.split("---", 2)
        assert len(parts) >= 3, f"Frontmatter YAML non chiuso in {skill_file}"
        meta = yaml.safe_load(parts[1])
        assert isinstance(meta, dict), f"Frontmatter YAML invalido in {skill_file}"
        assert isinstance(meta.get("name"), str) and meta["name"].strip(), (
            f"Campo 'name:' mancante in {skill_file}"
        )
        assert isinstance(meta.get("description"), str) and meta["description"].strip(), (
            f"Campo 'description:' mancante in {skill_file}"
        )


def test_gamedev_router_workspace_symlink():
    link = REPO_ROOT / ".agents" / "skills" / "router"
    assert link.exists(), "Symlink .agents/skills/router mancante"
    assert link.resolve() == (VENDOR_DIR / "router").resolve()


def test_gamedev_skills_registered_in_integrations_manifest():
    data = yaml.safe_load(INTEGRATIONS_MANIFEST.read_text(encoding="utf-8"))
    integrations = data.get("integrations", {})
    assert "gamedev_skills" in integrations
    entry = integrations["gamedev_skills"]
    assert entry["local_path"] == "vendor/gamedev-skills"
    assert entry["pinned_ref"] == "c6ca6c41c839b68319ffc08430b99ab768debc32"
