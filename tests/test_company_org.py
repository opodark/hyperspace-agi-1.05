# SPDX-License-Identifier: Apache-2.0
"""Tests for Company / Org Control Plane (`shared/company_org.py`, `shared/agent_adapters.py`, `cp.org`)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
CP_DIR = ROOT / "control-plane"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(CP_DIR) not in sys.path:
    sys.path.insert(0, str(CP_DIR))

from shared.agent_adapters import build_heartbeat_prompt, dispatch_heartbeat
from shared.company_org import (
    BudgetPausedError,
    CheckoutConflictError,
    CompanyOrgStore,
)


class FakeClock:
    def __init__(self, start: float = 1_700_000_000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_goal_alignment_org_tree_and_hire_approval(tmp_path):
    store = CompanyOrgStore(tmp_path)
    ceo = store.hire_agent("CEO", role="ceo", adapter="claude_code", agent_id="ceo")
    eng = store.hire_agent(
        "Backend Eng",
        role="coder",
        adapter="codex",
        reports_to="ceo",
        requires_approval=True,
        agent_id="eng-1",
    )
    assert ceo["status"] == "active"
    assert eng["status"] == "pending_approval"

    with pytest.raises(BudgetPausedError):
        store.run_agent_heartbeat("eng-1")

    approved = store.approve_agent("eng-1", reviewer="board", rationale="approved headcount")
    assert approved["status"] == "active"

    tree = store.org_tree()
    assert len(tree) == 1
    assert tree[0]["agent_id"] == "ceo"
    assert [r["agent_id"] for r in tree[0]["reports"]] == ["eng-1"]

    goal = store.create_goal("Launch v2", description="Ship autonomous ops", owner_agent_id="ceo", goal_id="g-v2")
    proj = store.create_project("Core Mesh", goal_id=goal["goal_id"], budget_usd_monthly=100.0, project_id="p-mesh")
    issue = store.create_issue("Fix checkout lock", project_id=proj["project_id"], assignee_agent_id="eng-1", issue_id="iss-1")

    ctx = store.goal_alignment_context(issue["issue_id"])
    assert ctx["goal"]["goal_id"] == "g-v2"
    assert ctx["project"]["project_id"] == "p-mesh"
    assert ctx["issue"]["issue_id"] == "iss-1"


def test_atomic_checkout_conflict_and_lease_expiry(tmp_path):
    clock = FakeClock()
    store = CompanyOrgStore(tmp_path, clock=clock)
    store.hire_agent("A1", agent_id="a1")
    store.hire_agent("A2", agent_id="a2")
    store.create_issue("Shared task", issue_id="iss-lock")

    checked = store.checkout_issue("iss-lock", "a1", lease_seconds=60)
    assert checked["checked_out_by"] == "a1"
    assert checked["status"] == "in_progress"

    with pytest.raises(CheckoutConflictError):
        store.checkout_issue("iss-lock", "a2", lease_seconds=60)

    # Once the lease expires, a2 can atomically take over.
    clock.advance(61)
    taken = store.checkout_issue("iss-lock", "a2", lease_seconds=60)
    assert taken["checked_out_by"] == "a2"

    # Releasing by a1 fails while a2 holds the active lease.
    with pytest.raises(CheckoutConflictError):
        store.release_issue("iss-lock", "a1")

    done = store.release_issue("iss-lock", "a2", new_status="done")
    assert done["status"] == "done"
    assert done["checked_out_by"] is None


def test_finops_budget_enforcement_and_session_persistence(tmp_path):
    store = CompanyOrgStore(tmp_path)
    store.hire_agent("Coder", role="coder", monthly_budget_usd=5.0, agent_id="coder-1")
    proj = store.create_project("Alpha", project_id="p-alpha")
    store.create_issue("Implement feature", project_id="p-alpha", assignee_agent_id="coder-1", issue_id="iss-feat")

    def fake_exec(agent, issue, ctx):
        return {
            "next_status": "in_review",
            "tokens_in": 1200,
            "tokens_out": 400,
            "cost_usd": 5.25,
            "model": "qwen3-coder",
            "session_state": {"step": 1, "last_file": "main.py"},
            "comment": "Implemented draft, ready for review.",
        }

    out = store.run_agent_heartbeat("coder-1", executor=fake_exec)
    assert out["status"] == "executed"
    assert out["issue"]["status"] == "in_review"
    assert out["agent"]["status"] == "budget_paused"
    assert out["agent"]["tokens_in_month"] == 1200
    assert out["agent"]["tokens_out_month"] == 400

    # Reload from disk and verify session_state & budget_paused survived.
    reloaded = CompanyOrgStore(tmp_path)
    ag = reloaded.get_agent("coder-1")
    assert ag["status"] == "budget_paused"
    assert ag["session_state"] == {"step": 1, "last_file": "main.py"}
    assert reloaded.list_projects()[0]["spent_usd_month"] == 5.25

    with pytest.raises(BudgetPausedError):
        reloaded.run_agent_heartbeat("coder-1")

    # Board increases monthly budget and resumes agent.
    resumed = reloaded.approve_agent("coder-1", new_budget_usd=15.0, rationale="approved Q4 spend")
    assert resumed["status"] == "active"


def test_mentions_and_template_roundtrip(tmp_path):
    s1 = CompanyOrgStore(tmp_path / "src")
    s1.hire_agent("CEO", role="ceo", agent_id="ceo")
    s1.hire_agent("QA", role="verifier", reports_to="ceo", agent_id="qa")
    s1.create_goal("Quality 99%", owner_agent_id="ceo", goal_id="g-q")
    s1.create_project("Test Suite", goal_id="g-q", project_id="p-ts")
    iss = s1.create_issue("Check logs", project_id="p-ts", issue_id="iss-m")
    commented = s1.comment_issue(iss["issue_id"], "ceo", "Please verify @qa ASAP")
    assert "qa" in commented["unread_mentions"]

    tpl = s1.export_template("qa-org")
    s2 = CompanyOrgStore(tmp_path / "dst")
    counts = s2.import_template(tpl)
    assert counts == {"goals": 1, "projects": 1, "agents": 2}
    assert len(s2.org_tree()[0]["reports"]) == 1


def test_agent_adapters_prompt_and_dry_run():
    agent = {"agent_id": "c1", "name": "Coder", "role": "coder", "adapter": "claude_code"}
    issue = {"issue_id": "iss-9", "title": "Refactor router", "description": "Clean up routes"}
    ctx = {
        "goal": {"title": "Reliability", "description": "Zero 500s"},
        "project": {"name": "API v2"},
        "session_state": {"branch": "feat/router"},
    }
    prompt = build_heartbeat_prompt(agent, issue, ctx)
    assert "Company Goal: Reliability" in prompt
    assert "Project: API v2" in prompt
    assert "feat/router" in prompt

    res_cli = dispatch_heartbeat(agent, issue, ctx)
    assert res_cli["dry_run"] is True
    assert res_cli["command"] == "claude"

    local_agent = {"agent_id": "l1", "name": "Local", "role": "worker", "adapter": "local_mission"}
    res_local = dispatch_heartbeat(
        local_agent,
        issue,
        ctx,
        mission_creator=lambda **kw: {"mission_id": "mis-xyz"},
    )
    assert res_local["mission_id"] == "mis-xyz"


def test_org_flask_routes_auth_and_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("DREAM_REVIEW_TOKEN", "t" * 40)
    monkeypatch.setenv("LOCAL_OPERATOR_AUTH", "false")
    from cp.org import monta

    app = Flask(__name__)
    monta(app, data_dir=tmp_path)
    client = app.test_client()

    # Unauthenticated request must fail with 401.
    assert client.get("/org/status").status_code == 401

    headers = {"Authorization": f"Bearer {'t' * 40}"}
    assert client.post("/org/goals", json={"title": "Grow ARR"}, headers=headers).status_code == 201
    assert client.post("/org/agents", json={"name": "Worker1", "agent_id": "w1", "monthly_budget_usd": 2.0}, headers=headers).status_code == 201
    assert client.post("/org/agents", json={"name": "Worker2", "agent_id": "w2"}, headers=headers).status_code == 201
    assert client.post("/org/issues", json={"title": "Task A", "issue_id": "iss-a"}, headers=headers).status_code == 201

    # Atomic checkout + 409 conflict.
    assert client.post("/org/issues/iss-a/checkout", json={"agent_id": "w1"}, headers=headers).status_code == 200
    assert client.post("/org/issues/iss-a/checkout", json={"agent_id": "w2"}, headers=headers).status_code == 409

    # Usage triggers budget_paused -> heartbeat returns 402 -> approve unpauses.
    u = client.post("/org/agents/w1/usage", json={"tokens_in": 500, "tokens_out": 200, "cost_usd": 2.5}, headers=headers)
    assert u.status_code == 200
    assert u.get_json()["agent"]["status"] == "budget_paused"
    assert client.post("/org/agents/w1/heartbeat", json={}, headers=headers).status_code == 402
    assert client.post("/org/agents/w1/approve", json={"new_budget_usd": 10.0}, headers=headers).status_code == 200

    # Template export & audit log.
    assert client.get("/org/template", headers=headers).status_code == 200
    audit = client.get("/org/audit", headers=headers).get_json()["audit_log"]
    assert len(audit) >= 4


def test_company_ui_routes_and_assets_registered():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    cockpit_css = root / "control-plane" / "cockpit.css"
    company_html = root / "control-plane" / "company.html"
    main_py = (root / "control-plane" / "main.py").read_text(encoding="utf-8")
    dockerfile = (root / "control-plane" / "Dockerfile").read_text(encoding="utf-8")
    dashboard = (root / "control-plane" / "dashboard.html").read_text(encoding="utf-8")

    assert cockpit_css.is_file()
    assert company_html.is_file()
    assert "SPDX-License-Identifier: Apache-2.0" in cockpit_css.read_text(encoding="utf-8")
    assert "SPDX-License-Identifier: Apache-2.0" in company_html.read_text(encoding="utf-8")
    assert "@app.route('/cockpit.css')" in main_py
    assert "@app.route('/company')" in main_py
    assert '"id": "company"' in main_py
    assert "COPY control-plane/cockpit.css ." in dockerfile
    assert "COPY control-plane/company.html ." in dockerfile
    assert 'id="panel-company"' in dashboard
    assert 'href="/company"' in dashboard
