# SPDX-License-Identifier: Apache-2.0
"""Mission Control store: an objective decomposed into a task DAG.

A *mission* is a durable, review-gated objective. It carries the natural-language
goal, a set of success criteria, a budget, a per-role capability policy and the
DAG of tasks that the controller dispatches. Everything the controller needs to
resume after a restart lives here, and every record keeps provenance (model,
target, timestamps, trace id).

The store is deliberately dependency-free and filesystem-backed, mirroring the
`DevelopmentDreamJournal` pattern: a single append-friendly JSONL where the last
record for an id wins, rewritten atomically and capped to a bounded window of
missions. Task state lives *inside* the mission record so a claim/complete is a
single atomic rewrite — there is no cross-file consistency to reason about.
"""
from __future__ import annotations

import json
import hashlib
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

MISSION_STATUSES = {"planned", "running", "blocked", "done", "failed", "cancelled"}
TASK_STATUSES = {"pending", "ready", "running", "done", "failed", "skipped"}
TERMINAL_MISSION_STATUSES = {"done", "failed", "cancelled"}
TERMINAL_TASK_STATUSES = {"done", "failed", "skipped"}
# Una missione `blocked` è viva: sta aspettando una revisione umana, non è
# fallita. Resta riavviabile quando il controller torna a girare.
RESUMABLE_MISSION_STATUSES = {"planned", "running", "blocked"}


def _iso(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).astimezone().isoformat()


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _clean(value, limit=8000):
    return str(value or "").strip()[:limit]


def _task_key(raw, index):
    key = _clean(raw, 80).lower().replace(" ", "-")
    return key or f"task-{index + 1}"


def validate_dag(tasks):
    """Validate a task list and return it with dependencies normalized.

    Each incoming task may use a short ``key`` for its identity and reference
    other tasks by key from ``dependencies``. We accept an explicit ``task_id``
    too (used by replans). Raises ``ValueError`` on duplicate ids, unknown
    dependencies, self-loops or cycles — a DAG that cannot be scheduled is a
    planner bug, not something to paper over at dispatch time.
    """
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("plan must be a non-empty list of tasks")
    ids, normalized = [], []
    for index, raw in enumerate(tasks):
        if not isinstance(raw, dict):
            raise ValueError("each task must be an object")
        task_id = _clean(raw.get("task_id") or raw.get("key"), 80) or _task_key(raw.get("title"), index)
        if task_id in ids:
            raise ValueError(f"duplicate task id: {task_id}")
        ids.append(task_id)
        normalized.append((task_id, raw))

    known = set(ids)
    result = []
    for task_id, raw in normalized:
        dependencies = raw.get("dependencies") or []
        if not isinstance(dependencies, list):
            raise ValueError(f"dependencies of {task_id} must be a list")
        dependencies = [_clean(d, 80) for d in dependencies if _clean(d, 80)]
        for dependency in dependencies:
            if dependency == task_id:
                raise ValueError(f"task {task_id} depends on itself")
            if dependency not in known:
                raise ValueError(f"task {task_id} depends on unknown task {dependency}")
        result.append((task_id, raw, dependencies))

    # Kahn: un ciclo significherebbe un grado di dipendenza sempre > 0.
    remaining = {task_id: set(deps) for task_id, _, deps in result}
    while remaining:
        free = [task_id for task_id, deps in remaining.items() if not deps]
        if not free:
            raise ValueError("task graph contains a cycle")
        for task_id in free:
            remaining.pop(task_id)
        for deps in remaining.values():
            deps.difference_update(free)
    return [(task_id, raw, deps) for task_id, raw, deps in result]


def artifact_revision(task):
    """Bind a review to the exact captured artifact metadata and worker output."""
    evidence = {"artifacts": task.get("artifacts", []), "output": task.get("output", "")}
    return hashlib.sha256(_json(evidence).encode("utf-8")).hexdigest()


def task_review_status(mission, task):
    revision = artifact_revision(task)
    for review in reversed(mission.get("reviews", [])):
        if review.get("artifacts", {}).get(task["task_id"]) == revision:
            return review.get("action", "pending")
    return "pending"


class MissionStore:
    """Durable mission + task-DAG state, safe for concurrent threads."""

    def __init__(self, directory, max_missions=200, clock=time.time):
        self.path = Path(directory) / "missions.jsonl"
        self._lock = threading.RLock()
        self.max_missions = max(1, int(max_missions))
        self.clock = clock

    # ── storage ───────────────────────────────────────────────────────────────
    def _read(self):
        if not self.path.exists():
            return {}
        missions = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and row.get("id"):
                missions[row["id"]] = row  # l'ultimo record per id vince
        return missions

    def _write(self, missions):
        ordered = sorted(missions.values(), key=lambda row: row.get("updated_at", ""))
        ordered = ordered[-self.max_missions:]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text("".join(_json(row) + "\n" for row in ordered), encoding="utf-8")
        temporary.replace(self.path)

    def _mutate(self, mission_id, mutator):
        with self._lock:
            missions = self._read()
            mission = missions.get(mission_id)
            if mission is None:
                raise KeyError(mission_id)
            mutator(mission)
            mission["updated_at"] = _iso(self.clock())
            missions[mission_id] = mission
            self._write(missions)
            return mission

    # ── lifecycle ─────────────────────────────────────────────────────────────
    def create(self, objective, success_criteria=None, budget=None, policy=None, mission_id="", capabilities=None):
        now = self.clock()
        mission_id = _clean(mission_id, 80) or "mission-" + uuid.uuid4().hex[:16]
        criteria = [_clean(c, 500) for c in (success_criteria or []) if _clean(c, 500)]
        record = {
            "schema_version": 2,
            "id": mission_id,
            "trace_id": "trace-" + uuid.uuid4().hex[:12],
            "objective": _clean(objective, 4000),
            "success_criteria": criteria,
            "status": "planned",
            "budget": dict(budget or {}),
            "policy": dict(policy or {}),
            "plan_version": 1,
            "capabilities_snapshot": dict(capabilities or {}),
            "receipts": {},
            "tasks": [],
            "plan_log": [],
            "reviews": [],
            "counters": {"steps": 0, "tokens": 0, "replans": 0},
            "created_at": _iso(now),
            "updated_at": _iso(now),
            "started_at": None,
            "finished_at": None,
            "error": "",
        }
        with self._lock:
            missions = self._read()
            missions[mission_id] = record
            self._write(missions)
        return record

    def get(self, mission_id):
        with self._lock:
            return self._read().get(mission_id)

    def list(self, status="", limit=50):
        with self._lock:
            missions = list(self._read().values())
        if status:
            missions = [m for m in missions if m.get("status") == status]
        missions.sort(key=lambda m: m.get("updated_at", ""), reverse=True)
        return missions[: max(1, min(int(limit), self.max_missions))]

    def status(self):
        with self._lock:
            missions = list(self._read().values())
        counts = {}
        for mission in missions:
            key = mission.get("status", "unknown")
            counts[key] = counts.get(key, 0) + 1
        return {"total": len(missions), "by_status": counts}


    # ── planning ──────────────────────────────────────────────────────────────
    def _build_task(self, task_id, raw, dependencies, now):
        return {
            "task_id": task_id,
            "role": _clean(raw.get("role"), 40) or "worker",
            "title": _clean(raw.get("title"), 200),
            "instruction": _clean(raw.get("instruction") or raw.get("description"), 6000),
            "dependencies": list(dependencies),
            "status": "pending",
            "attempts": 0,
            "max_attempts": max(1, int(raw.get("max_attempts", 2))),
            "artifacts": [],
            "output": "",
            "error": "",
            "verification": {},
            "model": "",
            "target": "",
            "tokens": 0,
            "trace_id": "trace-" + uuid.uuid4().hex[:12],
            "created_at": _iso(now),
            "updated_at": _iso(now),
            "started_at": None,
            "finished_at": None,
        }

    def set_plan(self, mission_id, tasks, plan=None, capabilities=None):
        """Replace the mission's DAG (first plan). Validates the graph."""
        validated = validate_dag(tasks)
        now = self.clock()

        def mutate(mission):
            if mission["tasks"]:
                raise ValueError("mission already has a plan")
            mission["tasks"] = [self._build_task(tid, raw, deps, now) for tid, raw, deps in validated]
            mission["plan_version"] = 1
            if capabilities:
                mission["capabilities_snapshot"] = dict(capabilities)
            elif isinstance(plan, dict) and "capabilities" in plan:
                mission["capabilities_snapshot"] = dict(plan.get("capabilities") or {})
            mission["plan_log"].append({"at": _iso(now), "kind": "plan", **(plan or {})})

        return self._mutate(mission_id, mutate)

    def add_replan(self, mission_id, tasks, plan=None):
        """Append new tasks (a replan) and bump the replan counter."""
        existing = self.get(mission_id)
        if existing is None:
            raise KeyError(mission_id)
        known = {task["task_id"] for task in existing.get("tasks", [])}
        for raw in tasks or []:
            if isinstance(raw, dict) and _clean(raw.get("task_id") or raw.get("key"), 80) in known:
                raise ValueError("replan reused an existing task id")
        validated = validate_dag(tasks)
        now = self.clock()

        def mutate(mission):
            mission["tasks"].extend(
                self._build_task(tid, raw, deps, now) for tid, raw, deps in validated)
            mission["counters"]["replans"] = mission["counters"].get("replans", 0) + 1
            mission["plan_version"] = mission.get("plan_version", 1) + 1
            mission["plan_log"].append({"at": _iso(now), "kind": "replan", **(plan or {})})

        return self._mutate(mission_id, mutate)

    def _task(self, mission, task_id):
        return next((task for task in mission.get("tasks", []) if task["task_id"] == task_id), None)

    def ready_tasks(self, mission_id):
        """Pending tasks whose dependencies have all completed."""
        mission = self.get(mission_id)
        if mission is None:
            raise KeyError(mission_id)
        done = {task["task_id"] for task in mission["tasks"] if task["status"] == "done"}
        return [task for task in mission["tasks"]
                if task["status"] in {"pending", "ready"} and set(task["dependencies"]) <= done]


    # ── task transitions (each an atomic rewrite) ─────────────────────────────
    def claim(self, mission_id, task_id):
        """Atomically move a ready task to `running`. Returns the claimed task
        copy, or None if it was not claimable (e.g. already running)."""
        claimed = {}

        def mutate(mission):
            task = self._task(mission, task_id)
            if task is None or task["status"] not in {"pending", "ready"}:
                return
            done = {t["task_id"] for t in mission["tasks"] if t["status"] == "done"}
            if not set(task["dependencies"]) <= done:
                return
            now = self.clock()
            was_interrupted = task.pop("interrupted", False)
            task["status"] = "running"
            task["attempts"] += 1
            task["started_at"] = _iso(now)
            task["updated_at"] = _iso(now)
            mission["status"] = "running"
            mission["started_at"] = mission.get("started_at") or _iso(now)
            if not was_interrupted:
                mission["counters"]["steps"] = mission["counters"].get("steps", 0) + 1
            claimed.update(task)

        self._mutate(mission_id, mutate)
        return claimed or None

    def complete(self, mission_id, task_id, output="", artifacts=None, model="", target="", tokens=0, tool_evidence=None, usage_known=None):
        def mutate(mission):
            task = self._task(mission, task_id)
            if task is None:
                raise KeyError(task_id)
            now = self.clock()
            task["status"] = "done"
            task["output"] = _clean(output, 20000)
            task["artifacts"] = list(artifacts or [])
            task["model"] = _clean(model, 120)
            task["target"] = _clean(target, 120)
            if tokens is not None:
                task["tokens"] = int(tokens or 0)
            task["tool_evidence"] = list(tool_evidence or [])
            if usage_known is not None:
                task["usage_known"] = usage_known
            task["error"] = ""
            task["updated_at"] = _iso(now)
            task["finished_at"] = _iso(now)
            mission["counters"]["tokens"] = mission["counters"].get("tokens", 0) + int(tokens or 0)

        return self._mutate(mission_id, mutate)

    def fail(self, mission_id, task_id, error="", retry=False):
        result = {}

        def mutate(mission):
            task = self._task(mission, task_id)
            if task is None:
                raise KeyError(task_id)
            now = self.clock()
            task["error"] = _clean(error, 4000)
            task["updated_at"] = _iso(now)
            if retry and task["attempts"] < task["max_attempts"]:
                task["status"] = "pending"
                task["finished_at"] = None
                result["status"] = "pending"
            else:
                task["status"] = "failed"
                task["finished_at"] = _iso(now)
                result["status"] = "failed"
                self._skip_dependents(mission, task_id, now)

        self._mutate(mission_id, mutate)
        return result

    def _skip_dependents(self, mission, failed_id, now, seen=None):
        """Cascade-skip tasks whose dependency can no longer complete.

        A task that waits on a failed or skipped task is not runnable; leaving it
        `pending` forever would deadlock the DAG. Standard DAG semantics: mark it
        skipped (with the reason) and recurse into its own dependents.
        """
        seen = seen if seen is not None else set()
        for task in mission["tasks"]:
            if task["task_id"] in seen:
                continue
            if failed_id in task["dependencies"] and task["status"] in {"pending", "ready"}:
                task["status"] = "skipped"
                task["error"] = _clean(f"dependency {failed_id} did not complete", 2000)
                task["updated_at"] = _iso(now)
                task["finished_at"] = _iso(now)
                seen.add(task["task_id"])
                self._skip_dependents(mission, task["task_id"], now, seen)

    def skip(self, mission_id, task_id, reason=""):
        def mutate(mission):
            task = self._task(mission, task_id)
            if task is None:
                raise KeyError(task_id)
            now = self.clock()
            task["status"] = "skipped"
            task["error"] = _clean(reason, 2000)
            task["updated_at"] = _iso(now)
            task["finished_at"] = _iso(now)
            self._skip_dependents(mission, task_id, now)

        return self._mutate(mission_id, mutate)

    def reclaim_orphans(self, mission_id):
        """Reset `running` tasks left behind by a crashed or restarted process.

        Called once at the start of a resumed run, when no other controller is
        driving the mission: a `running` task at that moment is an orphan, not a
        live thread. Attempts are preserved so the retry budget still applies,
        but the task is marked as interrupted so step counters aren't double-charged.
        """
        def mutate(mission):
            now = self.clock()
            for task in mission["tasks"]:
                if task["status"] == "running":
                    task["status"] = "pending"
                    task["started_at"] = None
                    task["updated_at"] = _iso(now)
                    task["interrupted"] = True

        return self._mutate(mission_id, mutate)

    def record_receipt(self, mission_id, idempotency_key, action, result):
        """Record an action receipt tied to an idempotency key."""
        now = self.clock()
        receipt = {
            "idempotency_key": _clean(idempotency_key, 160),
            "action": _clean(action, 80),
            "result": result,
            "at": _iso(now),
        }

        def mutate(mission):
            receipts = mission.setdefault("receipts", {})
            receipts[receipt["idempotency_key"]] = receipt

        self._mutate(mission_id, mutate)
        return receipt

    def get_receipt(self, mission_id, idempotency_key):
        """Retrieve a stored receipt, or None."""
        mission = self.get(mission_id)
        if not mission:
            return None
        return (mission.get("receipts") or {}).get(idempotency_key)

    def set_verification(self, mission_id, task_id, verification):
        def mutate(mission):
            task = self._task(mission, task_id)
            if task is None:
                raise KeyError(task_id)
            task["verification"] = dict(verification or {})
            task["updated_at"] = _iso(self.clock())

        return self._mutate(mission_id, mutate)



    # ── mission-level transitions ─────────────────────────────────────────────
    def summary(self, mission_id):
        mission = self.get(mission_id)
        if mission is None:
            raise KeyError(mission_id)
        counts = {}
        for task in mission["tasks"]:
            counts[task["status"]] = counts.get(task["status"], 0) + 1
        return {"id": mission["id"], "status": mission["status"],
                "tasks": counts, "counters": mission["counters"],
                "all_terminal": all(t["status"] in TERMINAL_TASK_STATUSES for t in mission["tasks"])}

    def finish(self, mission_id, status, error=""):
        if status not in MISSION_STATUSES:
            raise ValueError(f"unknown mission status: {status}")

        def mutate(mission):
            now = self.clock()
            mission["status"] = status
            mission["error"] = _clean(error, 4000)
            mission["finished_at"] = _iso(now) if status in TERMINAL_MISSION_STATUSES else None

        return self._mutate(mission_id, mutate)

    def cancel(self, mission_id, reason=""):
        def mutate(mission):
            now = self.clock()
            mission["status"] = "cancelled"
            mission["error"] = _clean(reason, 2000)
            mission["finished_at"] = _iso(now)
            for task in mission["tasks"]:
                if task["status"] in {"pending", "ready", "running"}:
                    task["status"] = "skipped"
                    task["updated_at"] = _iso(now)
                    task["finished_at"] = _iso(now)

        return self._mutate(mission_id, mutate)

    def record_attempt_usage(self, mission_id, task_id, outcome):
        def mutate(mission):
            task = self._task(mission, task_id)
            tokens = max(0, int(outcome.get("tokens") or 0))
            charged = max(tokens, int(outcome.get("charged_tokens") or 0))
            task["tokens"] = task.get("tokens", 0) + tokens
            task["charged_tokens"] = task.get("charged_tokens", 0) + charged
            task["usage_known"] = task.get("usage_known", True) and outcome.get("usage_known", True)
            task["tool_evidence"] = list(outcome.get("tool_evidence") or [])
            mission["counters"]["tokens"] = mission["counters"].get("tokens", 0) + tokens
        return self._mutate(mission_id, mutate)

    def record_runtime(self, mission_id, seconds):
        def mutate(mission):
            counters = mission["counters"]
            counters["elapsed_seconds"] = counters.get("elapsed_seconds", 0) + max(0, seconds)
        return self._mutate(mission_id, mutate)

    def review(self, mission_id, action, reviewer, rationale):
        """Record a human review of the mission's review-gated artifacts.

        Non applica nulla: `applied` resta sempre False, come per il development
        dream. Registra solo chi ha deciso, cosa e perché.
        """
        action = _clean(action, 20).lower()
        rationale = _clean(rationale, 2000)
        if action not in {"approve", "reject", "defer", "reopen"}:
            raise ValueError("unknown mission review action")
        if not rationale:
            raise ValueError("review rationale is required")

        def mutate(mission):
            now = self.clock()
            mission["reviews"].append({
                "action": action,
                "reviewer": _clean(reviewer, 120) or "operator",
                "rationale": rationale,
                "at": _iso(now),
                "applied": False,
                "artifacts": {task["task_id"]: artifact_revision(task)
                              for task in mission["tasks"]
                              if task["status"] == "done" and task.get("artifacts")},
            })
            if mission["status"] == "blocked" and action == "approve":
                mission["status"] = "planned"

        return self._mutate(mission_id, mutate)
