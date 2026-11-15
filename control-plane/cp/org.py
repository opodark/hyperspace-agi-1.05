# SPDX-License-Identifier: Apache-2.0
"""Company / Org Control Plane routes (`/org/*`).

Protected by the same operator token boundary as Mission Control
(`_dream_review_auth_error`) and intentionally excluded from `federation-gateway`.
"""
from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, jsonify, request

from cp.budget import _dream_review_auth_error
from shared.agent_adapters import dispatch_heartbeat
from shared.company_org import (
    BudgetPausedError,
    CheckoutConflictError,
    CompanyOrgStore,
    NotFoundError,
    OrgError,
)

_bp = Blueprint("org", __name__)
_org_store: CompanyOrgStore | None = None
_mission_creator = None


def _get_store() -> CompanyOrgStore:
    global _org_store
    if _org_store is None:
        data_dir = os.getenv("MISSION_DATA_DIR") or os.getenv("HYPERSPACE_DATA_DIR") or "/app/data"
        if not Path(data_dir).exists() and Path("data").exists():
            data_dir = "data"
        _org_store = CompanyOrgStore(data_dir)
    return _org_store


@_bp.before_request
def _require_operator_auth():
    auth_error = _dream_review_auth_error()
    if auth_error:
        return auth_error
    return None


def _handle_org_error(exc: Exception):
    if isinstance(exc, NotFoundError):
        return jsonify({"ok": False, "error": str(exc)}), 404
    if isinstance(exc, CheckoutConflictError):
        return jsonify({"ok": False, "error": str(exc)}), 409
    if isinstance(exc, BudgetPausedError):
        return jsonify({"ok": False, "error": str(exc)}), 402
    if isinstance(exc, OrgError):
        return jsonify({"ok": False, "error": str(exc)}), 400
    raise exc


@_bp.route("/org/status")
def org_status():
    return jsonify({"ok": True, "summary": _get_store().status_summary()})


@_bp.route("/org/goals", methods=["GET", "POST"])
def org_goals():
    store = _get_store()
    if request.method == "GET":
        status = str(request.args.get("status") or "").strip() or None
        return jsonify({"ok": True, "goals": store.list_goals(status=status)})
    data = request.get_json(force=True, silent=True) or {}
    try:
        goal = store.create_goal(
            title=data.get("title", ""),
            description=data.get("description", ""),
            owner_agent_id=data.get("owner_agent_id"),
            goal_id=data.get("goal_id"),
            actor=str(data.get("actor") or "board"),
        )
        return jsonify({"ok": True, "goal": goal}), 201
    except OrgError as exc:
        return _handle_org_error(exc)


@_bp.route("/org/projects", methods=["GET", "POST"])
def org_projects():
    store = _get_store()
    if request.method == "GET":
        goal_id = str(request.args.get("goal_id") or "").strip() or None
        return jsonify({"ok": True, "projects": store.list_projects(goal_id=goal_id)})
    data = request.get_json(force=True, silent=True) or {}
    try:
        project = store.create_project(
            name=data.get("name", ""),
            goal_id=data.get("goal_id"),
            description=data.get("description", ""),
            budget_usd_monthly=data.get("budget_usd_monthly", 0.0),
            project_id=data.get("project_id"),
            actor=str(data.get("actor") or "board"),
        )
        return jsonify({"ok": True, "project": project}), 201
    except OrgError as exc:
        return _handle_org_error(exc)


@_bp.route("/org/agents", methods=["GET", "POST"])
def org_agents():
    store = _get_store()
    if request.method == "GET":
        if str(request.args.get("tree") or "").lower() in ("1", "true", "yes"):
            return jsonify({"ok": True, "tree": store.org_tree()})
        status = str(request.args.get("status") or "").strip() or None
        return jsonify({"ok": True, "agents": store.list_agents(status=status)})
    data = request.get_json(force=True, silent=True) or {}
    try:
        agent = store.hire_agent(
            name=data.get("name", ""),
            role=data.get("role", "worker"),
            adapter=data.get("adapter", "local_mission"),
            reports_to=data.get("reports_to"),
            monthly_budget_usd=data.get("monthly_budget_usd", 0.0),
            heartbeat_interval_s=data.get("heartbeat_interval_s", 300),
            capabilities=data.get("capabilities"),
            adapter_config=data.get("adapter_config"),
            requires_approval=bool(data.get("requires_approval", False)),
            agent_id=data.get("agent_id"),
            actor=str(data.get("actor") or "board"),
        )
        return jsonify({"ok": True, "agent": agent}), 201
    except OrgError as exc:
        return _handle_org_error(exc)


@_bp.route("/org/agents/<agent_id>/approve", methods=["POST"])
def org_agent_approve(agent_id: str):
    data = request.get_json(force=True, silent=True) or {}
    try:
        agent = _get_store().approve_agent(
            agent_id,
            reviewer=str(data.get("reviewer") or "board"),
            rationale=str(data.get("rationale") or ""),
            new_budget_usd=data.get("new_budget_usd"),
        )
        return jsonify({"ok": True, "agent": agent})
    except OrgError as exc:
        return _handle_org_error(exc)


@_bp.route("/org/agents/<agent_id>/usage", methods=["POST"])
def org_agent_usage(agent_id: str):
    data = request.get_json(force=True, silent=True) or {}
    try:
        agent = _get_store().record_usage(
            agent_id,
            tokens_in=data.get("tokens_in", 0),
            tokens_out=data.get("tokens_out", 0),
            cost_usd=data.get("cost_usd", 0.0),
            project_id=data.get("project_id"),
            model=str(data.get("model") or ""),
            source=str(data.get("source") or "api"),
        )
        return jsonify({"ok": True, "agent": agent})
    except OrgError as exc:
        return _handle_org_error(exc)


@_bp.route("/org/agents/<agent_id>/heartbeat", methods=["POST"])
def org_agent_heartbeat(agent_id: str):
    data = request.get_json(force=True, silent=True) or {}
    try:
        lease = int(data.get("lease_seconds") or 300)
        outcome = _get_store().run_agent_heartbeat(
            agent_id,
            executor=lambda ag, iss, ctx: dispatch_heartbeat(ag, iss, ctx, mission_creator=_mission_creator),
            lease_seconds=lease,
        )
        return jsonify({"ok": True, **outcome})
    except OrgError as exc:
        return _handle_org_error(exc)


@_bp.route("/org/issues", methods=["GET", "POST"])
def org_issues():
    store = _get_store()
    if request.method == "GET":
        return jsonify(
            {
                "ok": True,
                "issues": store.list_issues(
                    status=str(request.args.get("status") or "").strip() or None,
                    assignee_agent_id=str(request.args.get("assignee_agent_id") or "").strip() or None,
                    project_id=str(request.args.get("project_id") or "").strip() or None,
                ),
            }
        )
    data = request.get_json(force=True, silent=True) or {}
    try:
        issue = store.create_issue(
            title=data.get("title", ""),
            description=data.get("description", ""),
            project_id=data.get("project_id"),
            assignee_agent_id=data.get("assignee_agent_id"),
            priority=data.get("priority", 2),
            status=data.get("status", "todo"),
            mission_id=data.get("mission_id"),
            issue_id=data.get("issue_id"),
            actor=str(data.get("actor") or "board"),
        )
        return jsonify({"ok": True, "issue": issue}), 201
    except OrgError as exc:
        return _handle_org_error(exc)


@_bp.route("/org/issues/<issue_id>/checkout", methods=["POST"])
def org_issue_checkout(issue_id: str):
    data = request.get_json(force=True, silent=True) or {}
    agent_id = str(data.get("agent_id") or "").strip()
    if not agent_id:
        return jsonify({"ok": False, "error": "agent_id is required"}), 400
    try:
        issue = _get_store().checkout_issue(
            issue_id,
            agent_id=agent_id,
            lease_seconds=int(data.get("lease_seconds") or 300),
        )
        return jsonify({"ok": True, "issue": issue})
    except OrgError as exc:
        return _handle_org_error(exc)


@_bp.route("/org/issues/<issue_id>/release", methods=["POST"])
def org_issue_release(issue_id: str):
    data = request.get_json(force=True, silent=True) or {}
    agent_id = str(data.get("agent_id") or "").strip()
    if not agent_id:
        return jsonify({"ok": False, "error": "agent_id is required"}), 400
    try:
        issue = _get_store().release_issue(
            issue_id,
            agent_id=agent_id,
            new_status=data.get("status"),
            mission_id=data.get("mission_id"),
        )
        return jsonify({"ok": True, "issue": issue})
    except OrgError as exc:
        return _handle_org_error(exc)


@_bp.route("/org/issues/<issue_id>/comments", methods=["POST"])
def org_issue_comments(issue_id: str):
    data = request.get_json(force=True, silent=True) or {}
    try:
        issue = _get_store().comment_issue(
            issue_id,
            author=str(data.get("author") or "board"),
            text=str(data.get("text") or ""),
        )
        return jsonify({"ok": True, "issue": issue}), 201
    except OrgError as exc:
        return _handle_org_error(exc)


@_bp.route("/org/audit")
def org_audit():
    try:
        limit = int(request.args.get("limit") or 100)
    except ValueError:
        limit = 100
    return jsonify({"ok": True, "audit_log": _get_store().audit_log(limit=limit)})


@_bp.route("/org/template", methods=["GET", "POST"])
def org_template():
    store = _get_store()
    if request.method == "GET":
        name = str(request.args.get("name") or "hyperspace-company")
        return jsonify({"ok": True, "template": store.export_template(name=name)})
    data = request.get_json(force=True, silent=True) or {}
    template = data.get("template") if isinstance(data.get("template"), dict) else data
    try:
        counts = store.import_template(template, actor=str(data.get("actor") or "board"))
        return jsonify({"ok": True, "imported": counts}), 201
    except OrgError as exc:
        return _handle_org_error(exc)


def monta(app, *, data_dir=None, mission_creator=None):
    global _org_store, _mission_creator
    if data_dir is not None:
        _org_store = CompanyOrgStore(data_dir)
    _mission_creator = mission_creator
    app.register_blueprint(_bp)
