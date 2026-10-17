# SPDX-License-Identifier: Apache-2.0
"""Test suite per HyperSpace Marketing & Adoption Engine."""

import json
from pathlib import Path

import pytest

from scripts.marketing.content_factory import ContentDraft, ContentFactory
from scripts.marketing.devrel_changelog import CommitItem, DevRelChangelogGenerator
from scripts.marketing.lead_nurturing import LeadNurturingManager
from scripts.marketing.telegram_gate import TelegramGate


# ── TEST CONTENT FACTORY ─────────────────────────────────────────────────────

def test_content_factory_creative_draft(tmp_path):
    drafts_file = tmp_path / "drafts.json"
    factory = ContentFactory(drafts_path=drafts_file)

    draft = factory.generate_creative_draft(theme_idx=0, author="Aurora")
    assert draft.track == "creative"
    assert draft.category in ("sogno", "poesia", "reel_concept")
    assert len(draft.tags) > 0
    assert "telegram" in draft.channel_targets
    assert draft.status == "draft"

    # Verifica persistenza su file
    loaded = factory.get_draft(draft.draft_id)
    assert loaded is not None
    assert loaded.title == draft.title
    assert loaded.text == draft.text


def test_content_factory_tech_draft(tmp_path):
    drafts_file = tmp_path / "drafts.json"
    factory = ContentFactory(drafts_path=drafts_file)

    draft = factory.generate_tech_draft(theme_idx=1)
    assert draft.track == "tech"
    assert "Bonsai 2" in draft.title or "Mesh" in draft.title or "Hermes" in draft.title
    assert len(draft.channel_targets) >= 2


def test_content_factory_status_lifecycle(tmp_path):
    drafts_file = tmp_path / "drafts.json"
    factory = ContentFactory(drafts_path=drafts_file)

    draft = factory.generate_creative_draft()
    assert draft.status == "draft"

    ok = factory.update_status(draft.draft_id, "queued_approval")
    assert ok is True
    assert factory.get_draft(draft.draft_id).status == "queued_approval"

    ok = factory.update_status(draft.draft_id, "approved")
    assert ok is True
    assert factory.get_draft(draft.draft_id).status == "approved"

    with pytest.raises(ValueError):
        factory.update_status(draft.draft_id, "stato_inventato")


# ── TEST LEAD NURTURING ──────────────────────────────────────────────────────

def test_lead_nurturing_classification():
    mgr = LeadNurturingManager()

    # Dev / Mesh intent
    assert mgr.classify_intent("Richiesta info", "Come faccio a connettere un nodo GPU con Ollama alla mesh?") == "dev_mesh"
    assert mgr.classify_intent("VRAM limits", "Quali modelli girano su RTX 3070?") == "dev_mesh"

    # Access Key intent
    assert mgr.classify_intent("Chiave", "Non riesco a trovare il token di auth per la chat") == "access_key"

    # Partnership
    assert mgr.classify_intent("Collaborazione aziendale", "Vorremmo valutare una partnership e i costi per un deployment custom") == "partnership_project"

    # General
    assert mgr.classify_intent("Ciao", "Volevo solo provare la demo") == "general_curiosity"


def test_lead_nurturing_reply_generation(tmp_path):
    state_file = tmp_path / "leads_state.json"
    mgr = LeadNurturingManager(state_path=state_file)

    reply = mgr.compose_onboarding_reply(
        name="Marco Rossi",
        email="marco@example.com",
        subject="Info nodi",
        message="Voglio configurare un nodo Mac",
        auth_key="hs-mesh-marco-1234",
        intent="dev_mesh"
    )

    assert "Ciao Marco," in reply
    assert "hs-mesh-marco-1234" in reply
    assert "https://www.zerozerocomputer.it/chat.html?key=hs-mesh-marco-1234" in reply
    assert "HyperSpace" in reply


# ── TEST DEVREL CHANGELOG ────────────────────────────────────────────────────

def test_devrel_changelog_categorization():
    generator = DevRelChangelogGenerator()
    assert generator._categorize_message("feat(mesh): add p2p sync") == "feature"
    assert generator._categorize_message("fix: resolve mobile autofill trap") == "fix"
    assert generator._categorize_message("perf(vram): evaluate MoE models on 8GB") == "perf"
    assert generator._categorize_message("docs: update architecture guide") == "docs"


def test_devrel_changelog_formatting():
    generator = DevRelChangelogGenerator()
    dummy_commits = [
        CommitItem("1234567", "feat(p2p): encrypted mesh channel", "Antigravity", "2026-10-15", "feature"),
        CommitItem("89abcde", "perf(gpu): ternary Bonsai 2 27B quantization", "Antigravity", "2026-10-15", "perf"),
        CommitItem("fedcba9", "fix: mobile contact form honeypot bypass", "Antigravity", "2026-10-15", "fix"),
    ]

    # 1. GitHub Release Notes
    release_md = generator.format_github_release("1.05.5", dummy_commits)
    assert "# 🚀 HyperSpace v1.05.5" in release_md
    assert "1234567" in release_md
    assert "Prestazioni & Hardware Acceleration" in release_md
    assert "https://www.zerozerocomputer.it" in release_md

    # 2. Social Thread
    thread = generator.format_social_thread(dummy_commits)
    assert len(thread) == 3
    assert "1/3" in thread[0]
    assert "2/3" in thread[1]
    assert "3/3" in thread[2]
    assert "https://www.zerozerocomputer.it" in thread[2]

    # 3. Reddit Post
    reddit = generator.format_reddit_post(dummy_commits)
    assert "r/LocalLLaMA" in reddit
    assert "Bonsai 2 & Runtime Ternario" in reddit
    assert "1234567" in reddit


# ── TEST TELEGRAM GATE & HUMAN-IN-THE-LOOP ───────────────────────────────────

def test_telegram_gate_dry_run_and_callback(tmp_path):
    drafts_file = tmp_path / "drafts.json"
    state_file = tmp_path / "leads_state.json"

    factory = ContentFactory(drafts_path=drafts_file)
    lead_mgr = LeadNurturingManager(state_path=state_file)
    gate = TelegramGate(bot_token="", chat_id="", factory=factory, lead_mgr=lead_mgr)

    assert not gate.is_configured

    # Creazione bozza e invio revisione (dry-run)
    draft = factory.generate_creative_draft()
    res = gate.send_content_review(draft)
    assert res.get("ok") is True
    assert res.get("dry_run") is True
    assert factory.get_draft(draft.draft_id).status == "queued_approval"

    # Callback approvazione
    cb_res = gate.handle_callback(f"approve_draft:{draft.draft_id}")
    assert cb_res.get("ok") is True
    assert factory.get_draft(draft.draft_id).status == "approved"

    # Callback rifiuto
    cb_rej = gate.handle_callback(f"reject_draft:{draft.draft_id}")
    assert cb_rej.get("ok") is True
    assert factory.get_draft(draft.draft_id).status == "rejected"
