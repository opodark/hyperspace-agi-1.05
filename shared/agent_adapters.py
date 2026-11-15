# SPDX-License-Identifier: Apache-2.0
"""BYOA (Bring Your Own Agent) adapter layer for HyperSpace Company Org.

Translates a CompanyOrgStore heartbeat (agent + checked-out issue + Goal
Alignment context + persisted session_state) into an execution call for
heterogeneous agent harnesses:
  - ``local_mission``: queues/links a Mission Control mission
  - ``http_webhook``: POSTs the heartbeat envelope to a remote agent endpoint
  - ``claude_code``, ``codex``, ``gemini_cli``, ``shell``: CLI harnesses (gated
    behind ``ORG_EXTERNAL_ADAPTERS_ENABLED=true``; dry-run descriptor otherwise)
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import urllib.request
from typing import Any


def build_heartbeat_prompt(agent: dict, issue: dict, context: dict) -> str:
    """Build a concise prompt carrying the full Goal -> Project -> Issue chain."""
    parts = [f"Agent: {agent['name']} ({agent['role']})"]
    goal = context.get("goal")
    if goal:
        parts.append(f"Company Goal: {goal['title']}")
        if goal.get("description"):
            parts.append(f"Goal Why: {goal['description']}")
    project = context.get("project")
    if project:
        parts.append(f"Project: {project['name']}")
    parts.append(f"Issue [{issue['issue_id']}]: {issue['title']}")
    if issue.get("description"):
        parts.append(f"Details:\n{issue['description']}")
    session = context.get("session_state") or {}
    if session:
        parts.append(f"Saved Session State: {json.dumps(session, ensure_ascii=False)}")
    return "\n\n".join(parts)


def _external_adapters_enabled() -> bool:
    return os.getenv("ORG_EXTERNAL_ADAPTERS_ENABLED", "false").strip().lower() == "true"


def dispatch_heartbeat(
    agent: dict,
    issue: dict,
    context: dict,
    *,
    mission_creator=None,
) -> dict[str, Any]:
    """Execute one heartbeat window for ``agent`` on ``issue``."""
    adapter = agent.get("adapter") or "local_mission"
    cfg = agent.get("adapter_config") or {}
    prompt = build_heartbeat_prompt(agent, issue, context)

    if adapter == "local_mission":
        mission_id = None
        if mission_creator is not None:
            mission = mission_creator(
                objective=f"[{issue['issue_id']}] {issue['title']}\n\n{prompt}",
                criteria=[f"Resolve issue {issue['issue_id']}"],
                allowed_roles=[agent.get("role", "worker")] if agent.get("role") else None,
            )
            mission_id = mission.get("mission_id") if isinstance(mission, dict) else None
        return {
            "adapter": "local_mission",
            "mission_id": mission_id,
            "next_status": "in_review",
            "session_state": {"last_issue_id": issue["issue_id"]},
            "comment": f"Dispatched to local Mission Control (mission_id={mission_id or 'dry-run'}).",
        }

    if adapter == "http_webhook":
        url = str(cfg.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("http_webhook adapter requires adapter_config.url (http/https)")
        if not _external_adapters_enabled():
            return {
                "adapter": "http_webhook",
                "dry_run": True,
                "url": url,
                "next_status": "in_review",
                "session_state": {"last_issue_id": issue["issue_id"]},
                "comment": f"Dry-run webhook dispatch prepared for {url}.",
            }
        body = json.dumps(
            {"agent": agent, "issue": issue, "context": context, "prompt": prompt},
            ensure_ascii=False,
        ).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        timeout = max(2, min(60, int(cfg.get("timeout_s") or 15)))
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(65536).decode("utf-8", errors="replace")
        return {
            "adapter": "http_webhook",
            "http_status": resp.status,
            "response": raw[:1000],
            "next_status": "in_review",
            "session_state": {"last_issue_id": issue["issue_id"]},
        }

    cli_templates = {
        "claude_code": ["claude", "-p", prompt, "--output-format", "json"],
        "codex": ["codex", "exec", prompt],
        "gemini_cli": ["gemini", "-p", prompt],
    }
    if adapter in cli_templates:
        cmd = cli_templates[adapter]
    elif adapter == "shell":
        raw_cmd = str(cfg.get("command") or "").strip()
        if not raw_cmd:
            raise ValueError("shell adapter requires adapter_config.command")
        cmd = shlex.split(raw_cmd)
    else:
        raise ValueError(f"unsupported adapter: {adapter}")

    if not _external_adapters_enabled():
        return {
            "adapter": adapter,
            "dry_run": True,
            "command": cmd[0],
            "next_status": "in_review",
            "session_state": {"last_issue_id": issue["issue_id"]},
            "comment": f"Dry-run {adapter} heartbeat prepared (set ORG_EXTERNAL_ADAPTERS_ENABLED=true to execute).",
        }

    timeout = max(5, min(600, int(cfg.get("timeout_s") or 120)))
    env = os.environ.copy()
    env["HYPERSPACE_ISSUE_ID"] = issue["issue_id"]
    env["HYPERSPACE_AGENT_ID"] = agent["agent_id"]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cfg.get("cwd") or None,
        env=env,
    )
    return {
        "adapter": adapter,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-2000:],
        "next_status": "in_review" if proc.returncode == 0 else "blocked",
        "session_state": {"last_issue_id": issue["issue_id"], "last_returncode": proc.returncode},
        "comment": f"{adapter} exited with code {proc.returncode}.",
    }
