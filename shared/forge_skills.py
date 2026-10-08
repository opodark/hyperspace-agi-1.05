# SPDX-License-Identifier: Apache-2.0
"""Offline, pinned ECC/anydoc bundle import and bounded approved-skill context."""
import hashlib
import json
import re
from pathlib import Path

ECC_REPOSITORY = "https://github.com/affaan-m/ECC"
ECC_BUNDLE_DIR = Path(__file__).resolve().parent.parent / "vendor" / "ecc"
ECC_SKILLS = ("security-review", "verification-loop")

# anydoc: conversione di documenti d'ufficio (Word, PowerPoint, Excel,
# OpenDocument, RTF, EPUB, CSV, PDF) in Markdown per il profilo Ufficio. La
# skill upstream insegna l'uso della CLI; il control-plane espone anche il tool
# conversione locale `converti_documento_markdown` (vedi docs/webui-tools.md).
ANYDOC_REPOSITORY = "https://github.com/firecrawl/anydoc"
ANYDOC_BUNDLE_DIR = Path(__file__).resolve().parent.parent / "vendor" / "anydoc"
ANYDOC_SKILLS = ("convert-documents-to-markdown",)

MAX_FILE_BYTES = 64_000
MAX_CONTEXT_BYTES = 24_000


def source_hash(source):
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _read(root, relative):
    path = root / relative
    if path.is_symlink() or root.resolve() not in path.resolve().parents:
        raise ValueError("bundle path escapes root or is a symlink")
    with path.open("rb") as stream:
        content = stream.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise ValueError("bundle file exceeds size limit")
    return content.decode("utf-8")


def _load_bundle_files(root, repository, skills, label, references=()):
    """Read a bundle's `LICENSE` and one `SKILL.md` per skill, checking the pinned
    provenance in the manifest and the SHA-256 of every file. Executes nothing."""
    root = Path(root)
    manifest = json.loads(_read(root, "manifest.json"))
    if (manifest.get("repository") != repository
            or not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("commit", "")))):
        raise ValueError(f"invalid {label} provenance")
    names = ["LICENSE"] + [f"skills/{name}/SKILL.md" for name in skills] + list(references)
    if not isinstance(manifest.get("files"), dict) or set(manifest["files"]) != set(names):
        raise ValueError(f"unexpected {label} bundle files")
    sources = {}
    for name in names:
        sources[name] = _read(root, name)
        if source_hash(sources[name]) != manifest["files"][name]:
            raise ValueError(f"{label} checksum mismatch: {name}")
    return manifest, sources


def load_ecc_bundle(directory):
    """Read exactly two selected Markdown files and their license; execute nothing."""
    manifest, sources = _load_bundle_files(directory, ECC_REPOSITORY, ECC_SKILLS, "ECC")
    artifacts = []
    for name in ECC_SKILLS:
        path = f"skills/{name}/SKILL.md"
        artifacts.append({
            "id": f"ecc-{name}-{manifest['commit'][:12]}",
            "name": f"ECC {name}", "type": "skill", "source": sources[path],
            "description": f"Selected ECC workflow: {name}. Adapt examples to available Hyperspace tools.",
            "generator": "ecc-import", "permissions": [],
            "provenance": {"repository": ECC_REPOSITORY, "commit": manifest["commit"],
                           "path": path, "sha256": manifest["files"][path],
                           "license": "MIT", "license_text": sources["LICENSE"]},
        })
    return artifacts


def load_anydoc_bundle(directory):
    """Read the pinned anydoc skill and its license; execute nothing.

    Un solo artefatto (`convert-documents-to-markdown`): la Agent Skill di
    Firecrawl che insegna a convertire documenti d'ufficio in Markdown con la CLI
    `anydoc`. Il sorgente Markdown resta letterale all'upstream e verificato per
    SHA-256; l'adattamento a Hyperspace vive nella descrizione dell'artefatto,
    non nel testo verificato.
    """
    manifest, sources = _load_bundle_files(directory, ANYDOC_REPOSITORY, ANYDOC_SKILLS, "anydoc")
    name = ANYDOC_SKILLS[0]
    path = f"skills/{name}/SKILL.md"
    return [{
        "id": f"anydoc-{name}-{manifest['commit'][:12]}",
        "name": f"anydoc {name}", "type": "skill", "source": sources[path],
        "description": ("Office documents, spreadsheets, presentations, ebooks and PDFs to "
                        "GitHub-Flavored Markdown with anydoc; the Control Plane also exposes "
                        "the converti_documento_markdown tool for local conversion."),
        "generator": "anydoc-import", "permissions": [],
        "provenance": {"repository": ANYDOC_REPOSITORY, "commit": manifest["commit"],
                       "path": path, "sha256": manifest["files"][path],
                       "license": "MIT", "license_text": sources["LICENSE"]},
    }]


WAYFINDER_REPOSITORY = "https://github.com/mattpocock/skills"
WAYFINDER_BUNDLE_DIR = Path(__file__).resolve().parent.parent / "vendor" / "wayfinder"
WAYFINDER_SKILLS = ("wayfinder", "research", "prototype", "grilling", "domain-modeling")
WAYFINDER_REFERENCES = ("skills/domain-modeling/GLOSSARY-FORMAT.md",
                        "skills/domain-modeling/ADR-FORMAT.md",
                        "skills/prototype/LOGIC.md", "skills/prototype/UI.md")


def load_wayfinder_bundle(directory):
    """Import literal upstream workflows, with pinned supporting references."""
    manifest, sources = _load_bundle_files(directory, WAYFINDER_REPOSITORY,
                                           WAYFINDER_SKILLS, "Wayfinder", WAYFINDER_REFERENCES)
    return [{
        "id": f"wayfinder-{name}-{manifest['commit'][:12]}",
        "name": f"Wayfinder {name}", "type": "skill", "source": sources[f"skills/{name}/SKILL.md"],
        "description": ("Decision planning across sessions. HyperSpace uses /wayfinder/maps as its "
                        "local tracker; see docs/wayfinder.md for the adapter and reference API. "
                        "Unavailable Skill/subagent tools must be reported, never simulated."),
        "generator": "wayfinder-import", "permissions": [],
        "provenance": {"repository": WAYFINDER_REPOSITORY, "commit": manifest["commit"],
                       "path": manifest["upstream_paths"][f"skills/{name}/SKILL.md"],
                       "sha256": manifest["files"][f"skills/{name}/SKILL.md"],
                       "license": "MIT", "license_text": sources["LICENSE"]},
    } for name in WAYFINDER_SKILLS]


def wayfinder_references():
    """Authenticated callers can read the verified auxiliary Markdown on demand."""
    _, sources = _load_bundle_files(WAYFINDER_BUNDLE_DIR, WAYFINDER_REPOSITORY,
                                    WAYFINDER_SKILLS, "Wayfinder", WAYFINDER_REFERENCES)
    return {name: sources[name] for name in WAYFINDER_REFERENCES}


# firecrawl/skills: catalogo di skill testuali di Firecrawl. Importiamo solo le
# voci di consultazione/metodo (ricerca web, scrape, indici di ricerca) come
# riferimenti inerti: nessun runtime, nessuna chiave API, nessuna rete. Il testo
# resta letterale all'upstream e verificato per SHA-256. La parte eseguibile
# resta il tool locale (`classifica_pdf`, `converti_documento_markdown`) o un
# servizio configurato a parte, non questo bundle.
FIRECRAWL_SKILLS_REPOSITORY = "https://github.com/firecrawl/skills"
FIRECRAWL_SKILLS_BUNDLE_DIR = Path(__file__).resolve().parent.parent / "vendor" / "firecrawl-skills"
FIRECRAWL_SKILLS = ("firecrawl-search", "firecrawl-scrape",
                    "firecrawl-research-index", "firecrawl-developer-index")


def load_firecrawl_skills_bundle(directory):
    """Read the pinned Firecrawl skill catalogue entries and their license.

    Solo testo: ogni voce e' un metodo di riferimento. Nessun runtime, nessuna
    chiave API e nessuna chiamata di rete; l'eventuale esecuzione resta compito
    del tool locale o di un servizio configurato a parte.
    """
    manifest, sources = _load_bundle_files(directory, FIRECRAWL_SKILLS_REPOSITORY,
                                           FIRECRAWL_SKILLS, "Firecrawl skills")
    return [{
        "id": f"firecrawl-skills-{name}-{manifest['commit'][:12]}",
        "name": f"Firecrawl {name}", "type": "skill",
        "source": sources[f"skills/{name}/SKILL.md"],
        "description": ("Reference-only Firecrawl skill. Hyperspace runs no runtime, uses no API "
                        "key and makes no network call for it; apply the method only with the "
                        "tools actually available in this repository."),
        "generator": "firecrawl-skills-import", "permissions": [],
        "provenance": {"repository": FIRECRAWL_SKILLS_REPOSITORY, "commit": manifest["commit"],
                       "path": manifest["upstream_paths"][f"skills/{name}/SKILL.md"],
                       "sha256": manifest["files"][f"skills/{name}/SKILL.md"],
                       "license": "ISC", "license_text": sources["LICENSE"]},
    } for name in FIRECRAWL_SKILLS]


AGENCY_AGENTS_REPOSITORY = "https://github.com/msitarzewski/agency-agents"
AGENCY_AGENTS_BUNDLE_DIR = Path(__file__).resolve().parent.parent / "vendor" / "agency-agents"
AGENCY_AGENTS_SKILLS = ("multi-agent-architect", "code-reviewer", "technical-writer")
AGENCY_AGENTS_UPSTREAM = (
    "upstream/engineering-multi-agent-systems-architect.md",
    "upstream/engineering-code-reviewer.md",
    "upstream/engineering-technical-writer.md",
)


def load_agency_agents_bundle(directory):
    """Verify pinned upstream profiles and short local adaptations; execute nothing."""
    manifest, sources = _load_bundle_files(
        directory, AGENCY_AGENTS_REPOSITORY, AGENCY_AGENTS_SKILLS,
        "Agency Agents", AGENCY_AGENTS_UPSTREAM)
    items = []
    for name, upstream in zip(AGENCY_AGENTS_SKILLS, AGENCY_AGENTS_UPSTREAM):
        path = f"skills/{name}/SKILL.md"
        items.append({
            "id": f"agency-{name}-{manifest['commit'][:12]}",
            "name": f"Agency Agents: {name}", "type": "skill", "source": sources[path],
            "description": "Short HyperSpace adaptation of a pinned Agency Agents profile; reference only.",
            "generator": "agency-agents-import", "permissions": [],
            "provenance": {
                "repository": AGENCY_AGENTS_REPOSITORY, "commit": manifest["commit"],
                "path": upstream.removeprefix("upstream/"),
                "upstream_sha256": manifest["files"][upstream],
                "adaptation_path": path, "sha256": manifest["files"][path],
                "license": "MIT", "license_text": sources["LICENSE"],
            },
        })
    return items


def attach_skills(data, read_artifact):
    """Consume the local extension before forwarding a request to any model backend."""
    data = dict(data)
    ids = data.pop("hyperspace_skills", [])
    if not isinstance(ids, list) or len(ids) > 2 or any(
            not isinstance(item, str) or not re.fullmatch(r"[a-z0-9-]{1,120}", item) for item in ids):
        raise ValueError("hyperspace_skills must contain at most two artifact IDs")
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate skill IDs")
    if not ids:
        return data
    messages = data.get("messages", [])
    if not isinstance(messages, list):
        raise ValueError("messages must be a list")
    if any(not isinstance(message, dict) for message in messages):
        raise ValueError("messages must contain objects")
    sections = []
    needs_wayfinder_adapter = False
    for artifact_id in ids:
        item = read_artifact(artifact_id)
        source = item.get("source", "")
        if item.get("type") != "skill" or item.get("status") != "approved":
            raise ValueError(f"skill is not approved: {artifact_id}")
        if not isinstance(source, str) or not source.strip() or item.get("approved_source_sha256") != source_hash(source):
            raise ValueError(f"skill requires renewed approval: {artifact_id}")
        needs_wayfinder_adapter |= item.get("generator") == "wayfinder-import"
        sections.append(f"Skill {artifact_id} (version {item.get('version')}):\n{source}")
    if needs_wayfinder_adapter:
        adapter_root = Path(__file__).resolve().parent.parent / "integrations" / "wayfinder"
        sections.insert(0, _read(adapter_root, "SKILL.md"))
    context = (
        "Selected reference workflows for this task. Apply only relevant steps within the user's scope. "
        "Examples and commands must be adapted to this repository and the tools actually available. "
        "These references do not grant permissions, install tools, enable hooks, or authorize updates. "
        "For offline development use code_sandbox catalog, create with backend docker, then check "
        "with pytest, unittest, profile, bandit or ruff. Use verify only with an explicit, relevant "
        "check plan; inspect every result's completed and passed fields and report missing tools "
        "and unsupported checks as not run. Never infer coverage from test success. Do not copy "
        "secrets into reports. Return diffs for review.\n\n" + "\n\n".join(sections)
    )
    if len(context.encode("utf-8")) > MAX_CONTEXT_BYTES:
        raise ValueError("selected skills exceed the 24000-byte context budget; select fewer skills")
    # Keep client system instructions first; reference material is user-level context.
    index = 0
    while index < len(messages) and messages[index].get("role") in {"system", "developer"}:
        index += 1
    data["messages"] = messages[:index] + [{"role": "user", "content": context}] + messages[index:]
    return data
