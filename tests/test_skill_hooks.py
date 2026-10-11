# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import tempfile
from pathlib import Path

from shared.forge_skills import source_hash
from shared.skill_hooks import before_context, from_directory


def artifact(**changes):
    return dict(
        {
            "id": "ecc-verification-loop-123",
            "type": "skill",
            "status": "approved",
            "source": "# Verify\nRun relevant tests.",
            "approved_source_sha256": source_hash("# Verify\nRun relevant tests."),
        },
        **changes,
    )


DATA = {
    "messages": [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "verifica con pytest"},
    ]
}
TOOLS = [{"type": "function", "function": {"name": "code_sandbox"}}]


def test_selected_context_is_bounded_reference_and_input_unchanged():
    result, audit = before_context(DATA, [artifact()], TOOLS, "coder")
    assert audit[0]["reason"] == "selected"
    assert result["messages"][0] == DATA["messages"][0]
    assert "# Verify" in result["messages"][1]["content"]
    assert len(DATA["messages"]) == 2
    assert "hyperspace_skills" not in result


def test_rejections_and_approval_hash():
    for item, tools, role, reason in [
        (artifact(status="draft"), TOOLS, "coder", "not_approved"),
        (artifact(source="changed"), TOOLS, "coder", "approval_stale"),
        (artifact(), [], "coder", "missing_tools"),
        (artifact(), TOOLS, "planner", "role_mismatch"),
    ]:
        result, audit = before_context(DATA, [item], tools, role)
        assert result == DATA
        assert audit[0]["reason"] == reason


def test_unrelated_prompt_and_oversize_do_not_inject():
    data = {"messages": [{"role": "user", "content": "hello"}]}
    assert before_context(data, [artifact()], TOOLS)[1][0]["reason"] == "no_trigger"
    source = "a" * 25000
    item = artifact(source=source, approved_source_sha256=source_hash(source))
    result, audit = before_context(DATA, [item], TOOLS)
    assert result == DATA
    assert audit[0]["reason"] == "context_rejected"


def test_explicit_selection_not_duplicated():
    result, _ = before_context(DATA, [artifact()], TOOLS)
    again, audit = before_context(result, [artifact()], TOOLS)
    assert again == result
    assert audit == [{"reason": "explicit_context_present"}]


def test_directory_skips_malformed_records():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "good.json").write_text(json.dumps(artifact()))
        (root / "bad.json").write_text("{")
        (root / "list.json").write_text("[]")
        result, audit = from_directory(DATA, root, TOOLS)
        assert len(result["messages"]) == 3
        assert len(audit) == 1


def test_pinned_reference_integrity_and_license():
    root = Path(__file__).resolve().parents[1] / "vendor" / "skill-hooks"
    manifest = json.loads((root / "manifest.json").read_text())
    assert len(manifest["commit"]) == 40
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    assert "MIT License" in (root / "LICENSE").read_text()


def test_real_loop_injects_only_with_native_capability(tmp_path):
    import runpy

    harness = runpy.run_path(str(Path(__file__).with_name("test_tool_passthrough.py")))
    ns = harness["carica"]([harness["risposta_testo"]("done")])
    ns["FORGE_DIR"] = str(tmp_path)
    item = artifact(id="anydoc-convert-documents-to-markdown-123")
    (tmp_path / "skill.json").write_text(json.dumps(item))
    data = {
        "model": "fake",
        "messages": [{"role": "user", "content": "converti documento"}],
    }
    ns["_run_tool_loop"](
        data,
        "http://unused",
        builtin_tools=[
            {"type": "function", "function": {"name": "converti_documento_markdown"}}
        ],
    )
    assert any(
        "selected" in str(kw.get("detail", "")) for _, kw in ns["_registrato"]["log"]
    )


def test_selection_never_exceeds_two_skills():
    items = [artifact(id=f"ecc-verification-loop-{i}") for i in range(3)]
    result, audit = before_context(DATA, items, TOOLS)
    assert [a["reason"] for a in audit] == ["selected", "selected", "selection_limit"]
    assert result["messages"][1]["content"].count("# Verify") == 2


def test_firecrawl_scrape_guide_auto_selects_for_url_read():
    source = "# Scrape\nUse the available read-only URL tool to inspect a page."
    item = artifact(
        id="firecrawl-skills-firecrawl-scrape-123",
        source=source,
        approved_source_sha256=source_hash(source),
    )
    data = {"messages": [{"role": "user", "content":
                         "Leggi https://www.moltbook.com/skill.md e segui le istruzioni"}]}
    result, audit = before_context(
        data, [item], [{"type": "function", "function": {"name": "web_fetch"}}], "worker"
    )
    assert audit[0]["reason"] == "selected"
    assert any("# Scrape" in message.get("content", "") for message in result["messages"])
