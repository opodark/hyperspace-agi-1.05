# SPDX-License-Identifier: Apache-2.0
"""Company / Org Control Plane store for HyperSpace.

Brings Paperclip-style organizational orchestration on top of HyperSpace's
existing mesh and Mission Control primitives:
  - Goal Alignment hierarchy: Goal -> Project -> Issue
  - Persistent Org Chart: named Agents with reporting lines, adapters, and
    saved session_state across heartbeats
  - Issue Queue with Atomic Checkout (lease-based locking to prevent duplicate work)
  - FinOps Budget Enforcement: cumulative input/output tokens and USD spend per
    agent & project, with automatic ``budget_paused`` hard-stop
  - Board Governance & Immutable Audit Trail
  - Portable Company Templates (export / import)
"""
from __future__ import annotations

import copy
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

AGENT_STATUSES = {"active", "paused", "budget_paused", "pending_approval", "terminated"}
ISSUE_STATUSES = {"backlog", "todo", "in_progress", "in_review", "done", "blocked", "cancelled"}
TERMINAL_ISSUE_STATUSES = {"done", "cancelled"}
GOAL_STATUSES = {"active", "achieved", "archived"}
PROJECT_STATUSES = {"active", "paused", "completed"}
KNOWN_ADAPTERS = {"local_mission", "claude_code", "codex", "gemini_cli", "http_webhook", "shell"}

_MENTION_RE = re.compile(r"@([a-zA-Z0-9][a-zA-Z0-9._-]{0,63})")


class OrgError(ValueError):
    """Base validation/state error for CompanyOrgStore."""


class NotFoundError(OrgError):
    """Raised when a referenced goal, project, agent or issue does not exist."""


class CheckoutConflictError(OrgError):
    """Raised when an issue is already checked out by another active agent."""


class BudgetPausedError(OrgError):
    """Raised when an agent cannot run because it is paused or awaiting approval."""


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).astimezone().isoformat()


def _clean(value, limit: int = 4000) -> str:
    return str(value or "").strip()[:limit]


def _slug_id(prefix: str, raw: str | None = None) -> str:
    if raw:
        cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(raw).strip().lower()).strip("-")
        if cleaned:
            return cleaned[:64]
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def extract_mentions(text: str) -> list[str]:
    seen = []
    for match in _MENTION_RE.findall(str(text or "")):
        if match not in seen:
            seen.append(match)
    return seen


class CompanyOrgStore:
    """Durable, thread-safe JSON state store for the HyperSpace Company Org."""

    def __init__(self, directory, max_audit: int = 1000, clock=time.time):
        self.directory = Path(directory)
        self.path = self.directory / "company_org.json"
        self.max_audit = max(50, int(max_audit))
        self._clock = clock
        self._lock = threading.RLock()
        self._state = self._load()

    def _empty_state(self) -> dict:
        return {
            "version": 1,
            "goals": {},
            "projects": {},
            "agents": {},
            "issues": {},
            "audit_log": [],
        }

    def _load(self) -> dict:
        if not self.path.exists():
            return self._empty_state()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._empty_state()
        if not isinstance(data, dict):
            return self._empty_state()
        base = self._empty_state()
        for key in ("goals", "projects", "agents", "issues"):
            if isinstance(data.get(key), dict):
                base[key] = data[key]
        if isinstance(data.get("audit_log"), list):
            base["audit_log"] = data["audit_log"][-self.max_audit :]
        return base

    def _save(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        tmp = self.directory / f".{self.path.name}.{uuid.uuid4().hex[:8]}.tmp"
        payload = json.dumps(self._state, ensure_ascii=False, indent=2)
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, self.path)

    def _audit(self, action: str, actor: str, target: str, details: dict | None = None) -> dict:
        now = self._clock()
        entry = {
            "id": f"aud-{uuid.uuid4().hex[:10]}",
            "ts": now,
            "at": _iso(now),
            "action": action,
            "actor": actor,
            "target": target,
            "details": details or {},
        }
        self._state["audit_log"].append(entry)
        if len(self._state["audit_log"]) > self.max_audit:
            self._state["audit_log"] = self._state["audit_log"][-self.max_audit :]
        return entry

    # ------------------------------------------------------------------
    # Goals & Projects (Goal Alignment)
    # ------------------------------------------------------------------

    def create_goal(
        self,
        title: str,
        description: str = "",
        owner_agent_id: str | None = None,
        goal_id: str | None = None,
        actor: str = "board",
    ) -> dict:
        title = _clean(title, 200)
        if not title:
            raise OrgError("goal title is required")
        with self._lock:
            gid = _slug_id("goal", goal_id)
            if gid in self._state["goals"]:
                raise OrgError(f"goal {gid} already exists")
            if owner_agent_id and owner_agent_id not in self._state["agents"]:
                raise NotFoundError(f"owner agent {owner_agent_id} not found")
            now = self._clock()
            goal = {
                "goal_id": gid,
                "title": title,
                "description": _clean(description, 4000),
                "status": "active",
                "owner_agent_id": owner_agent_id,
                "created_at": _iso(now),
                "updated_at": _iso(now),
            }
            self._state["goals"][gid] = goal
            self._audit("goal.created", actor, gid, {"title": title})
            self._save()
            return copy.deepcopy(goal)

    def list_goals(self, status: str | None = None) -> list[dict]:
        with self._lock:
            items = list(self._state["goals"].values())
            if status:
                items = [g for g in items if g["status"] == status]
            return copy.deepcopy(items)

    def create_project(
        self,
        name: str,
        goal_id: str | None = None,
        description: str = "",
        budget_usd_monthly: float = 0.0,
        project_id: str | None = None,
        actor: str = "board",
    ) -> dict:
        name = _clean(name, 200)
        if not name:
            raise OrgError("project name is required")
        with self._lock:
            if goal_id and goal_id not in self._state["goals"]:
                raise NotFoundError(f"goal {goal_id} not found")
            pid = _slug_id("proj", project_id)
            if pid in self._state["projects"]:
                raise OrgError(f"project {pid} already exists")
            now = self._clock()
            project = {
                "project_id": pid,
                "goal_id": goal_id,
                "name": name,
                "description": _clean(description, 4000),
                "status": "active",
                "budget_usd_monthly": max(0.0, float(budget_usd_monthly or 0.0)),
                "spent_usd_month": 0.0,
                "created_at": _iso(now),
                "updated_at": _iso(now),
            }
            self._state["projects"][pid] = project
            self._audit("project.created", actor, pid, {"name": name, "goal_id": goal_id})
            self._save()
            return copy.deepcopy(project)

    def list_projects(self, goal_id: str | None = None) -> list[dict]:
        with self._lock:
            items = list(self._state["projects"].values())
            if goal_id:
                items = [p for p in items if p.get("goal_id") == goal_id]
            return copy.deepcopy(items)

    # ------------------------------------------------------------------
    # Persistent Agents & Org Chart
    # ------------------------------------------------------------------

    def hire_agent(
        self,
        name: str,
        role: str = "worker",
        adapter: str = "local_mission",
        reports_to: str | None = None,
        monthly_budget_usd: float = 0.0,
        heartbeat_interval_s: int = 300,
        capabilities: list[str] | None = None,
        adapter_config: dict | None = None,
        requires_approval: bool = False,
        agent_id: str | None = None,
        actor: str = "board",
    ) -> dict:
        name = _clean(name, 120)
        if not name:
            raise OrgError("agent name is required")
        adapter = _clean(adapter, 40) or "local_mission"
        if adapter not in KNOWN_ADAPTERS:
            raise OrgError(f"unsupported adapter '{adapter}'; expected one of {sorted(KNOWN_ADAPTERS)}")
        with self._lock:
            aid = _slug_id("agent", agent_id or name)
            if aid in self._state["agents"]:
                raise OrgError(f"agent {aid} already exists")
            if reports_to and reports_to not in self._state["agents"]:
                raise NotFoundError(f"manager agent {reports_to} not found")
            now = self._clock()
            status = "pending_approval" if requires_approval else "active"
            agent = {
                "agent_id": aid,
                "name": name,
                "role": _clean(role, 64) or "worker",
                "adapter": adapter,
                "adapter_config": dict(adapter_config or {}),
                "reports_to": reports_to,
                "status": status,
                "heartbeat_interval_s": max(15, int(heartbeat_interval_s or 300)),
                "last_heartbeat_at": None,
                "last_heartbeat_ts": 0.0,
                "session_state": {},
                "monthly_budget_usd": max(0.0, float(monthly_budget_usd or 0.0)),
                "spent_usd_month": 0.0,
                "tokens_in_month": 0,
                "tokens_out_month": 0,
                "capabilities": [str(c).strip() for c in (capabilities or []) if str(c).strip()],
                "created_at": _iso(now),
                "updated_at": _iso(now),
            }
            self._state["agents"][aid] = agent
            self._audit("agent.hired", actor, aid, {"role": agent["role"], "adapter": adapter, "status": status})
            self._save()
            return copy.deepcopy(agent)

    def get_agent(self, agent_id: str) -> dict:
        with self._lock:
            agent = self._state["agents"].get(agent_id)
            if not agent:
                raise NotFoundError(f"agent {agent_id} not found")
            return copy.deepcopy(agent)

    def list_agents(self, status: str | None = None) -> list[dict]:
        with self._lock:
            items = list(self._state["agents"].values())
            if status:
                items = [a for a in items if a["status"] == status]
            return copy.deepcopy(items)

    def org_tree(self) -> list[dict]:
        """Return nested org chart starting from top-level agents (reports_to=None)."""
        with self._lock:
            nodes = {
                aid: {
                    "agent_id": a["agent_id"],
                    "name": a["name"],
                    "role": a["role"],
                    "adapter": a["adapter"],
                    "status": a["status"],
                    "reports_to": a.get("reports_to"),
                    "spent_usd_month": a["spent_usd_month"],
                    "monthly_budget_usd": a["monthly_budget_usd"],
                    "reports": [],
                }
                for aid, a in self._state["agents"].items()
            }
            roots = []
            for node in nodes.values():
                parent_id = node["reports_to"]
                if parent_id and parent_id in nodes:
                    nodes[parent_id]["reports"].append(node)
                else:
                    roots.append(node)
            return roots

    def approve_agent(
        self,
        agent_id: str,
        reviewer: str = "board",
        rationale: str = "",
        new_budget_usd: float | None = None,
    ) -> dict:
        """Board approval: activates a pending hire or unpauses a budget_paused agent."""
        with self._lock:
            agent = self._state["agents"].get(agent_id)
            if not agent:
                raise NotFoundError(f"agent {agent_id} not found")
            if agent["status"] == "terminated":
                raise OrgError(f"cannot approve terminated agent {agent_id}")
            if new_budget_usd is not None:
                agent["monthly_budget_usd"] = max(0.0, float(new_budget_usd))
            prev = agent["status"]
            agent["status"] = "active"
            agent["updated_at"] = _iso(self._clock())
            self._audit(
                "agent.approved",
                reviewer,
                agent_id,
                {"from_status": prev, "new_budget_usd": agent["monthly_budget_usd"], "rationale": _clean(rationale, 500)},
            )
            self._save()
            return copy.deepcopy(agent)

    def set_agent_status(self, agent_id: str, status: str, actor: str = "board", reason: str = "") -> dict:
        if status not in AGENT_STATUSES:
            raise OrgError(f"invalid agent status '{status}'")
        with self._lock:
            agent = self._state["agents"].get(agent_id)
            if not agent:
                raise NotFoundError(f"agent {agent_id} not found")
            prev = agent["status"]
            agent["status"] = status
            agent["updated_at"] = _iso(self._clock())
            self._audit("agent.status_changed", actor, agent_id, {"from": prev, "to": status, "reason": _clean(reason, 400)})
            self._save()
            return copy.deepcopy(agent)

    # ------------------------------------------------------------------
    # FinOps: Token (Input+Output) & Cost Tracking + Budget Enforcement
    # ------------------------------------------------------------------

    def record_usage(
        self,
        agent_id: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
        project_id: str | None = None,
        model: str = "",
        source: str = "heartbeat",
    ) -> dict:
        with self._lock:
            agent = self._state["agents"].get(agent_id)
            if not agent:
                raise NotFoundError(f"agent {agent_id} not found")
            t_in = max(0, int(tokens_in or 0))
            t_out = max(0, int(tokens_out or 0))
            cost = max(0.0, float(cost_usd or 0.0))

            agent["tokens_in_month"] += t_in
            agent["tokens_out_month"] += t_out
            agent["spent_usd_month"] = round(agent["spent_usd_month"] + cost, 6)
            agent["updated_at"] = _iso(self._clock())

            if project_id and project_id in self._state["projects"]:
                proj = self._state["projects"][project_id]
                proj["spent_usd_month"] = round(proj["spent_usd_month"] + cost, 6)
                proj["updated_at"] = _iso(self._clock())

            self._audit(
                "usage.recorded",
                agent_id,
                project_id or agent_id,
                {"tokens_in": t_in, "tokens_out": t_out, "cost_usd": cost, "model": model, "source": source},
            )

            cap = float(agent.get("monthly_budget_usd") or 0.0)
            if cap > 0.0 and agent["spent_usd_month"] >= cap and agent["status"] == "active":
                agent["status"] = "budget_paused"
                self._audit(
                    "agent.budget_paused",
                    "system",
                    agent_id,
                    {"spent_usd_month": agent["spent_usd_month"], "monthly_budget_usd": cap},
                )

            self._save()
            return copy.deepcopy(agent)

    # ------------------------------------------------------------------
    # Issue Queue, Atomic Checkout, Comments & Goal Alignment
    # ------------------------------------------------------------------

    def create_issue(
        self,
        title: str,
        description: str = "",
        project_id: str | None = None,
        assignee_agent_id: str | None = None,
        priority: int = 2,
        status: str = "todo",
        mission_id: str | None = None,
        issue_id: str | None = None,
        actor: str = "board",
    ) -> dict:
        title = _clean(title, 240)
        if not title:
            raise OrgError("issue title is required")
        if status not in ISSUE_STATUSES:
            raise OrgError(f"invalid issue status '{status}'")
        with self._lock:
            goal_id = None
            if project_id:
                proj = self._state["projects"].get(project_id)
                if not proj:
                    raise NotFoundError(f"project {project_id} not found")
                goal_id = proj.get("goal_id")
            if assignee_agent_id and assignee_agent_id not in self._state["agents"]:
                raise NotFoundError(f"assignee agent {assignee_agent_id} not found")
            iid = _slug_id("iss", issue_id)
            if iid in self._state["issues"]:
                raise OrgError(f"issue {iid} already exists")
            now = self._clock()
            issue = {
                "issue_id": iid,
                "project_id": project_id,
                "goal_id": goal_id,
                "title": title,
                "description": _clean(description, 8000),
                "priority": max(0, min(3, int(priority))),
                "status": status,
                "assignee_agent_id": assignee_agent_id,
                "checked_out_by": None,
                "checkout_expires_ts": 0.0,
                "checkout_expires_at": None,
                "mission_id": mission_id,
                "comments": [],
                "unread_mentions": [],
                "created_at": _iso(now),
                "updated_at": _iso(now),
            }
            self._state["issues"][iid] = issue
            self._audit("issue.created", actor, iid, {"title": title, "project_id": project_id, "assignee": assignee_agent_id})
            self._save()
            return copy.deepcopy(issue)

    def list_issues(self, status: str | None = None, assignee_agent_id: str | None = None, project_id: str | None = None) -> list[dict]:
        with self._lock:
            items = list(self._state["issues"].values())
            if status:
                items = [i for i in items if i["status"] == status]
            if assignee_agent_id:
                items = [i for i in items if i.get("assignee_agent_id") == assignee_agent_id]
            if project_id:
                items = [i for i in items if i.get("project_id") == project_id]
            items.sort(key=lambda i: (i.get("priority", 2), i.get("created_at", "")))
            return copy.deepcopy(items)

    def checkout_issue(self, issue_id: str, agent_id: str, lease_seconds: int = 300) -> dict:
        """Atomically lock an issue for an agent; raises CheckoutConflictError if held by another."""
        with self._lock:
            issue = self._state["issues"].get(issue_id)
            if not issue:
                raise NotFoundError(f"issue {issue_id} not found")
            if agent_id not in self._state["agents"]:
                raise NotFoundError(f"agent {agent_id} not found")
            if issue["status"] in TERMINAL_ISSUE_STATUSES:
                raise OrgError(f"issue {issue_id} is already terminal ({issue['status']})")

            now = self._clock()
            holder = issue.get("checked_out_by")
            expires_ts = float(issue.get("checkout_expires_ts") or 0.0)
            if holder and holder != agent_id and expires_ts > now:
                raise CheckoutConflictError(f"issue {issue_id} is already checked out by {holder}")

            lease = max(10, int(lease_seconds or 300))
            issue["checked_out_by"] = agent_id
            issue["assignee_agent_id"] = issue.get("assignee_agent_id") or agent_id
            issue["checkout_expires_ts"] = now + lease
            issue["checkout_expires_at"] = _iso(now + lease)
            issue["status"] = "in_progress"
            issue["updated_at"] = _iso(now)
            # Clear mention notification for this agent once checked out.
            issue["unread_mentions"] = [m for m in issue.get("unread_mentions", []) if m != agent_id]
            self._audit("issue.checked_out", agent_id, issue_id, {"lease_seconds": lease})
            self._save()
            return copy.deepcopy(issue)

    def release_issue(
        self,
        issue_id: str,
        agent_id: str,
        new_status: str | None = None,
        mission_id: str | None = None,
    ) -> dict:
        if new_status and new_status not in ISSUE_STATUSES:
            raise OrgError(f"invalid issue status '{new_status}'")
        with self._lock:
            issue = self._state["issues"].get(issue_id)
            if not issue:
                raise NotFoundError(f"issue {issue_id} not found")
            holder = issue.get("checked_out_by")
            if holder and holder != agent_id:
                raise CheckoutConflictError(f"issue {issue_id} is checked out by {holder}, not {agent_id}")
            issue["checked_out_by"] = None
            issue["checkout_expires_ts"] = 0.0
            issue["checkout_expires_at"] = None
            if new_status:
                issue["status"] = new_status
            elif issue["status"] == "in_progress":
                issue["status"] = "todo"
            if mission_id:
                issue["mission_id"] = mission_id
            issue["updated_at"] = _iso(self._clock())
            self._audit("issue.released", agent_id, issue_id, {"status": issue["status"], "mission_id": mission_id})
            self._save()
            return copy.deepcopy(issue)

    def comment_issue(self, issue_id: str, author: str, text: str) -> dict:
        text = _clean(text, 4000)
        if not text:
            raise OrgError("comment text is required")
        with self._lock:
            issue = self._state["issues"].get(issue_id)
            if not issue:
                raise NotFoundError(f"issue {issue_id} not found")
            now = self._clock()
            mentions = [m for m in extract_mentions(text) if m in self._state["agents"]]
            comment = {
                "comment_id": f"cmt-{uuid.uuid4().hex[:8]}",
                "author": _clean(author, 80) or "board",
                "text": text,
                "mentions": mentions,
                "created_at": _iso(now),
            }
            issue["comments"].append(comment)
            for m in mentions:
                if m not in issue["unread_mentions"]:
                    issue["unread_mentions"].append(m)
            issue["updated_at"] = _iso(now)
            self._audit("issue.commented", comment["author"], issue_id, {"mentions": mentions})
            self._save()
            return copy.deepcopy(issue)

    def goal_alignment_context(self, issue_id: str) -> dict:
        """Build the Goal -> Project -> Issue chain so an agent knows the strategic 'why'."""
        with self._lock:
            issue = self._state["issues"].get(issue_id)
            if not issue:
                raise NotFoundError(f"issue {issue_id} not found")
            project = self._state["projects"].get(issue.get("project_id") or "")
            goal_id = issue.get("goal_id") or (project.get("goal_id") if project else None)
            goal = self._state["goals"].get(goal_id or "")
            return {
                "goal": copy.deepcopy(goal),
                "project": copy.deepcopy(project),
                "issue": copy.deepcopy(issue),
            }

    # ------------------------------------------------------------------
    # Heartbeat Execution
    # ------------------------------------------------------------------

    def _pick_next_issue_for(self, agent_id: str) -> dict | None:
        now = self._clock()
        candidates = []
        for issue in self._state["issues"].values():
            if issue["status"] in TERMINAL_ISSUE_STATUSES or issue["status"] == "blocked":
                continue
            holder = issue.get("checked_out_by")
            if holder and holder != agent_id and float(issue.get("checkout_expires_ts") or 0.0) > now:
                continue
            mentioned = agent_id in issue.get("unread_mentions", [])
            assigned = issue.get("assignee_agent_id") == agent_id
            unassigned_todo = issue.get("assignee_agent_id") is None and issue["status"] == "todo"
            if mentioned or assigned or unassigned_todo:
                rank = (0 if mentioned else (1 if assigned else 2), issue.get("priority", 2), issue.get("created_at", ""))
                candidates.append((rank, issue))
        if not candidates:
            return None
        candidates.sort(key=lambda pair: pair[0])
        return candidates[0][1]

    def run_agent_heartbeat(self, agent_id: str, executor=None, lease_seconds: int = 300) -> dict:
        """Wake an agent, atomically claim its next issue, run executor, and persist session_state."""
        with self._lock:
            agent = self._state["agents"].get(agent_id)
            if not agent:
                raise NotFoundError(f"agent {agent_id} not found")
            if agent["status"] != "active":
                raise BudgetPausedError(f"agent {agent_id} cannot run heartbeat while status={agent['status']}")

            now = self._clock()
            agent["last_heartbeat_ts"] = now
            agent["last_heartbeat_at"] = _iso(now)
            issue = self._pick_next_issue_for(agent_id)
            if not issue:
                agent["updated_at"] = _iso(now)
                self._audit("heartbeat.idle", agent_id, agent_id, {})
                self._save()
                return {"status": "idle", "agent": copy.deepcopy(agent), "issue": None, "result": None}

            checked = self.checkout_issue(issue["issue_id"], agent_id, lease_seconds=lease_seconds)
            context = self.goal_alignment_context(checked["issue_id"])
            context["session_state"] = copy.deepcopy(agent.get("session_state", {}))

        # Execute outside the lock so concurrent heartbeats on other issues don't block.
        result = {}
        next_status = "in_review"
        try:
            if executor is not None:
                result = executor(copy.deepcopy(agent), checked, context) or {}
            next_status = result.get("next_status") or "in_review"
            if next_status not in ISSUE_STATUSES:
                next_status = "in_review"
        except Exception as exc:
            result = {"error": str(exc)}
            next_status = "blocked"

        with self._lock:
            ag = self._state["agents"][agent_id]
            if isinstance(result.get("session_state"), dict):
                ag["session_state"].update(result["session_state"])
            if result.get("tokens_in") or result.get("tokens_out") or result.get("cost_usd"):
                self.record_usage(
                    agent_id,
                    tokens_in=result.get("tokens_in", 0),
                    tokens_out=result.get("tokens_out", 0),
                    cost_usd=result.get("cost_usd", 0.0),
                    project_id=checked.get("project_id"),
                    model=str(result.get("model", "")),
                    source="heartbeat",
                )
            if result.get("comment"):
                self.comment_issue(checked["issue_id"], agent_id, str(result["comment"]))
            released = self.release_issue(
                checked["issue_id"],
                agent_id,
                new_status=next_status,
                mission_id=result.get("mission_id"),
            )
            self._audit("heartbeat.completed", agent_id, checked["issue_id"], {"next_status": next_status})
            self._save()
            return {
                "status": "executed",
                "agent": copy.deepcopy(self._state["agents"][agent_id]),
                "issue": released,
                "result": result,
            }

    # ------------------------------------------------------------------
    # Company Templates (Blueprint Export / Import) & Status
    # ------------------------------------------------------------------

    def export_template(self, name: str = "hyperspace-company") -> dict:
        with self._lock:
            return {
                "schema": "hyperspace.company_template.v1",
                "name": _clean(name, 120) or "hyperspace-company",
                "exported_at": _iso(self._clock()),
                "goals": [
                    {k: g[k] for k in ("goal_id", "title", "description", "owner_agent_id")}
                    for g in self._state["goals"].values()
                ],
                "projects": [
                    {k: p[k] for k in ("project_id", "goal_id", "name", "description", "budget_usd_monthly")}
                    for p in self._state["projects"].values()
                ],
                "agents": [
                    {
                        k: a[k]
                        for k in (
                            "agent_id",
                            "name",
                            "role",
                            "adapter",
                            "adapter_config",
                            "reports_to",
                            "monthly_budget_usd",
                            "heartbeat_interval_s",
                            "capabilities",
                        )
                    }
                    for a in self._state["agents"].values()
                ],
            }

    def import_template(self, template: dict, actor: str = "board") -> dict:
        if not isinstance(template, dict):
            raise OrgError("template must be a JSON object")
        counts = {"goals": 0, "projects": 0, "agents": 0}
        # Import agents first (roots before subordinates) so owner/reports_to references resolve.
        agents = list(template.get("agents") or [])
        pending = list(agents)
        with self._lock:
            for _ in range(len(agents) + 1):
                if not pending:
                    break
                next_pending = []
                progressed = False
                for a in pending:
                    aid = a.get("agent_id") or _slug_id("agent", a.get("name"))
                    parent = a.get("reports_to")
                    if parent and parent not in self._state["agents"]:
                        next_pending.append(a)
                        continue
                    if aid not in self._state["agents"]:
                        self.hire_agent(
                            name=a.get("name", aid),
                            role=a.get("role", "worker"),
                            adapter=a.get("adapter", "local_mission"),
                            reports_to=parent,
                            monthly_budget_usd=a.get("monthly_budget_usd", 0.0),
                            heartbeat_interval_s=a.get("heartbeat_interval_s", 300),
                            capabilities=a.get("capabilities"),
                            adapter_config=a.get("adapter_config"),
                            agent_id=aid,
                            actor=actor,
                        )
                        counts["agents"] += 1
                    progressed = True
                pending = next_pending
                if not progressed:
                    raise OrgError("template contains cyclic or unresolved reports_to references")

            for g in template.get("goals") or []:
                gid = g.get("goal_id")
                if gid and gid in self._state["goals"]:
                    continue
                self.create_goal(
                    title=g.get("title", ""),
                    description=g.get("description", ""),
                    owner_agent_id=g.get("owner_agent_id"),
                    goal_id=gid,
                    actor=actor,
                )
                counts["goals"] += 1

            for p in template.get("projects") or []:
                pid = p.get("project_id")
                if pid and pid in self._state["projects"]:
                    continue
                self.create_project(
                    name=p.get("name", ""),
                    goal_id=p.get("goal_id"),
                    description=p.get("description", ""),
                    budget_usd_monthly=p.get("budget_usd_monthly", 0.0),
                    project_id=pid,
                    actor=actor,
                )
                counts["projects"] += 1

            self._audit("template.imported", actor, template.get("name", "template"), counts)
            self._save()
        return counts

    def audit_log(self, limit: int = 100) -> list[dict]:
        with self._lock:
            n = max(1, min(self.max_audit, int(limit or 100)))
            return copy.deepcopy(list(reversed(self._state["audit_log"][-n:])))

    def status_summary(self) -> dict:
        with self._lock:
            agents = list(self._state["agents"].values())
            issues = list(self._state["issues"].values())
            return {
                "goals": len(self._state["goals"]),
                "projects": len(self._state["projects"]),
                "agents": {
                    "total": len(agents),
                    "active": sum(1 for a in agents if a["status"] == "active"),
                    "budget_paused": sum(1 for a in agents if a["status"] == "budget_paused"),
                    "pending_approval": sum(1 for a in agents if a["status"] == "pending_approval"),
                },
                "issues": {
                    "total": len(issues),
                    "todo": sum(1 for i in issues if i["status"] == "todo"),
                    "in_progress": sum(1 for i in issues if i["status"] == "in_progress"),
                    "in_review": sum(1 for i in issues if i["status"] == "in_review"),
                    "done": sum(1 for i in issues if i["status"] == "done"),
                    "blocked": sum(1 for i in issues if i["status"] == "blocked"),
                },
                "spend": {
                    "total_usd_month": round(sum(a["spent_usd_month"] for a in agents), 6),
                    "total_tokens_in_month": sum(a["tokens_in_month"] for a in agents),
                    "total_tokens_out_month": sum(a["tokens_out_month"] for a in agents),
                },
            }
