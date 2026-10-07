# SPDX-License-Identifier: Apache-2.0
"""Mission Control engine: plan -> dispatch -> execute -> verify -> replan.

The controller is deliberately free of any control-plane import so it can be
tested with fake planner/worker/verifier callables (the same trick the nightly
development dream uses with an injected agent). It owns *no* policy of its own:
budgets come from `mission_policy`, and the four collaborators below are the only
things that can reach the outside world.

    planner(mission, reason="")      -> list[task dict]
    worker(task, mission)            -> {"ok", "output", "artifacts", "model",
                                         "target", "tokens", "error"}
    verifier(scope, mission=..., task=..., outcome=...) -> {"verdict", "reason"}

`verdict` is one of: `pass`, `retry`, `replan`, `fail`. Everything is bounded by
the budget; nothing is ever auto-applied — artifacts stay review-gated.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, wait

from shared import mission_policy
from shared.mission import TERMINAL_MISSION_STATUSES, task_review_status


class MissionController:
    def __init__(self, store, *, planner, worker, verifier, budget=None,
                 concurrency=None, clock=time.time, on_event=None,
                 review_required=mission_policy.review_required):
        self.store = store
        self.planner = planner
        self.worker = worker
        self.verifier = verifier
        self.clock = clock
        self.on_event = on_event
        self.review_required = review_required
        self.budget = dict(budget) if budget else mission_policy.parse_budget()
        if concurrency is not None:
            ceiling = mission_policy.MAX_CONCURRENCY_CEILING
            self.budget["max_concurrency"] = max(1, min(int(concurrency), ceiling))
        self.running = False
        self.error = ""
        self.last_mission = ""

    # ── helpers ───────────────────────────────────────────────────────────────
    def _emit(self, event, mission_id, detail=None):
        if self.on_event:
            try:
                self.on_event(event, mission_id, detail or {})
            except Exception:
                pass

    def status(self):
        return {"enabled": True, "running": self.running, "error": self.error,
                "last_mission": self.last_mission,
                "concurrency": self.budget["max_concurrency"],
                "budget": self.budget, "missions": self.store.status()}

    def _elapsed(self, mission, start):
        return max(0.0, self.clock() - start) + mission.get("counters", {}).get("elapsed_seconds", 0)

    def _budget_exhausted(self, mission, elapsed):
        counters = mission.get("counters", {})
        return mission_policy.budget_exhausted(
            mission_policy.effective_budget(mission, self.budget), steps=counters.get("steps", 0),
            replans=counters.get("replans", 0), elapsed_seconds=elapsed)

    def pending_review(self, mission):
        """Tasks whose artifacts still wait for a human — always `applied: False`."""
        return [task for task in (mission or {}).get("tasks", [])
                if task.get("status") == "done" and task.get("artifacts")
                and self.review_required(task.get("role", ""))
                and task_review_status(mission, task) != "approve"]

    # ── dispatch ──────────────────────────────────────────────────────────────
    def _view(self, mission):
        view = dict(mission)
        view["_execution_budget"] = mission_policy.effective_budget(mission, self.budget)
        view["_deadline"] = getattr(self, "_deadline", None)
        mission_id = mission["id"]
        view["_cancelled"] = lambda: (self.store.get(mission_id) or {}).get("status") in {"cancelled", "failed"}
        return view

    def _run_task(self, mission_id, task):
        try:
            outcome = self.worker(task, self._view(self.store.get(mission_id))) or {}
        except Exception as error:  # a worker crash is a task failure, not a crash
            outcome = {"ok": False, "error": str(error) or type(error).__name__}
        if not isinstance(outcome, dict):
            outcome = {"ok": False, "error": "worker returned a non-dict outcome"}
        return outcome

    def _dispatch_wave(self, mission_id, tasks, deadline, pool):
        """Claim and run a wave of ready tasks, bounded by concurrency/deadline."""
        futures = {}
        mission = self.store.get(mission_id)
        budget = mission_policy.effective_budget(mission, self.budget)
        remaining = max(0, budget["max_steps"] - mission.get("counters", {}).get("steps", 0))
        for task in tasks[:min(remaining, budget["max_concurrency"])]:
            if self.clock() >= deadline or self.store.get(mission_id)["status"] == "cancelled":
                break
            claimed = self.store.claim(mission_id, task["task_id"])
            if not claimed:
                continue
            futures[pool.submit(self._run_task, mission_id, claimed)] = claimed
        results = {}
        pending = set(futures)
        while pending:
            done, pending = wait(pending, timeout=0.5)
            for future in done:
                results[futures[future]["task_id"]] = (futures[future], future.result())
            mission = self.store.get(mission_id)
            if mission is None or mission["status"] == "cancelled" or self.clock() > deadline:
                for future in pending:
                    future.cancel()
                break
        return results

    def _verify(self, scope, mission, task=None, outcome=None):
        try:
            verdict = self.verifier(scope, mission=self._view(mission), task=task, outcome=outcome) or {}
        except Exception as error:
            verdict = {"verdict": "fail", "reason": f"verifier error: {error}"}
        if not isinstance(verdict, dict):
            verdict = {"verdict": "fail", "reason": "invalid verifier response"}
        if verdict.get("verdict") not in {"pass", "retry", "replan", "fail"}:
            verdict = {"verdict": "fail", "reason": verdict.get("reason") or "invalid verdict"}
        return verdict

    def _apply_result(self, mission_id, task, outcome):
        """Turn a worker outcome + verifier verdict into a stored transition.

        Returns the replan reason (a non-empty string) when the mission should
        replan, or None otherwise.
        """
        mission = self.store.get(mission_id)
        if mission is None or mission["status"] == "cancelled":
            return None
        self.store.record_attempt_usage(mission_id, task["task_id"], outcome)
        if not outcome.get("ok"):
            reason = outcome.get("error") or "worker reported failure"
            verdict = {"verdict": "retry", "reason": reason}
        else:
            verdict = self._verify("task", mission, task=task, outcome=outcome)
            self.store.set_verification(mission_id, task["task_id"], verdict)

        decision = verdict["verdict"]
        if decision == "pass":
            self.store.complete(
                mission_id, task["task_id"], output=outcome.get("output", ""),
                artifacts=outcome.get("artifacts") or [], model=outcome.get("model", ""),
                target=outcome.get("target", ""), tokens=None,
                tool_evidence=outcome.get("tool_evidence"), usage_known=outcome.get("usage_known"))
            self._emit("task_done", mission_id, {"task": task["task_id"], "role": task["role"]})
        elif decision == "retry":
            budget = mission_policy.effective_budget(mission, self.budget)
            current = next(t for t in self.store.get(mission_id)["tasks"] if t["task_id"] == task["task_id"])
            retry = (task.get("attempts", 0) < budget["max_task_attempts"]
                     and current.get("charged_tokens", 0) < budget["max_tokens_per_task"])
            result = self.store.fail(mission_id, task["task_id"], verdict.get("reason", ""), retry=retry)
            self._emit("task_retry" if result["status"] == "pending" else "task_failed",
                       mission_id, {"task": task["task_id"]})
        elif decision == "replan":
            self.store.fail(mission_id, task["task_id"], verdict.get("reason", ""))
            return verdict.get("reason") or "verifier requested a replan"
        else:
            self.store.fail(mission_id, task["task_id"], verdict.get("reason", "verification failed"))
            self._emit("task_failed", mission_id, {"task": task["task_id"]})
        return None


    # ── planning / replanning ─────────────────────────────────────────────────
    def _plan(self, mission_id, mission):
        try:
            tasks = self.planner(self._view(mission), "") or []
        except Exception as error:
            self.store.finish(mission_id, "failed", f"planner error: {error}")
            return False
        try:
            self.store.set_plan(mission_id, tasks, plan={"roles": sorted(
                {t.get("role", "worker") for t in tasks if isinstance(t, dict)})})
        except ValueError as error:
            self.store.finish(mission_id, "failed", f"invalid plan: {error}")
            return False
        self._emit("plan", mission_id, {"tasks": len(tasks)})
        return True

    def _replan(self, mission_id, mission, reason):
        try:
            tasks = self.planner(self._view(mission), reason) or []
        except Exception as error:
            self.error = f"replan error: {error}"
            return False
        if not tasks:
            return False
        try:
            self.store.add_replan(mission_id, tasks, plan={"reason": reason})
        except ValueError as error:
            self.error = f"invalid replan: {error}"
            return False
        self._emit("replan", mission_id, {"tasks": len(tasks), "reason": reason})
        return True

    def _conclude(self, mission_id):
        """All tasks are terminal: ask the verifier about the whole mission.

        Returns True when a replan was queued (the caller should keep looping).
        """
        mission = self.store.get(mission_id)
        verdict = self._verify("mission", mission)
        decision = verdict["verdict"]
        if decision == "pass":
            self.store.finish(mission_id, "done")
            return False
        replans = mission.get("counters", {}).get("replans", 0)
        if decision == "replan" and replans < mission_policy.effective_budget(mission, self.budget)["max_replans"]:
            if self._replan(mission_id, mission, verdict.get("reason") or "mission not satisfied yet"):
                return True
        self.store.finish(mission_id, "failed", verdict.get("reason") or "mission verification failed")
        return False

    # ── main loop ─────────────────────────────────────────────────────────────
    def run(self, mission_id):
        mission = self.store.get(mission_id)
        if mission is None:
            raise KeyError(mission_id)
        if mission["status"] in TERMINAL_MISSION_STATUSES:
            return self.store.summary(mission_id)

        self.running, self.error, self.last_mission = True, "", mission_id
        start = self.clock()
        budget = mission_policy.effective_budget(mission, self.budget)
        deadline = start + max(0, budget["max_wall_seconds"] - mission.get("counters", {}).get("elapsed_seconds", 0))
        self._deadline = deadline
        try:
            if deadline <= start:
                self.store.finish(mission_id, "failed", "budget exhausted: time limit")
                return self.store.summary(mission_id)
            if not mission.get("tasks"):
                if not self._plan(mission_id, mission):
                    return self.store.summary(mission_id)
            else:
                # Ripresa: i task `running` rimasti da un processo morto non
                # hanno più un thread — tornano `pending` e ripartono.
                self.store.reclaim_orphans(mission_id)
                self.store.finish(mission_id, "running")
            with ThreadPoolExecutor(max_workers=budget["max_concurrency"]) as pool:
                self._loop(mission_id, start, deadline, pool)
            self._emit("mission_end", mission_id, {})
            return self.store.summary(mission_id)
        finally:
            try:
                self.store.record_runtime(mission_id, max(0, self.clock() - start))
            finally:
                self.running = False


    def _loop(self, mission_id, start, deadline, pool):
        while True:
            mission = self.store.get(mission_id)
            if mission is None or mission["status"] in TERMINAL_MISSION_STATUSES:
                return
            elapsed = self._elapsed(mission, start)
            if self._budget_exhausted(mission, elapsed):
                counters = mission["counters"]
                self.store.finish(mission_id, "failed",
                                  "budget exhausted: steps={} replans={} elapsed={}s".format(
                                      counters.get("steps", 0), counters.get("replans", 0), int(elapsed)))
                return
            ready = self.store.ready_tasks(mission_id)
            if ready:
                if mission["counters"].get("steps", 0) >= mission_policy.effective_budget(mission, self.budget)["max_steps"]:
                    self.store.finish(mission_id, "failed", "budget exhausted: no task attempts remaining")
                    return
                results = self._dispatch_wave(mission_id, ready, deadline, pool)
                replan_reason = None
                for task, outcome in results.values():
                    reason = self._apply_result(mission_id, task, outcome)
                    if reason:
                        replan_reason = reason
                if replan_reason:
                    mission = self.store.get(mission_id)
                    if mission["counters"].get("replans", 0) >= mission_policy.effective_budget(mission, self.budget)["max_replans"]:
                        self.store.finish(mission_id, "failed", "replan budget exhausted")
                        return
                    self._replan(mission_id, mission, replan_reason)
                continue
            summary = self.store.summary(mission_id)
            if summary["all_terminal"]:
                if self._conclude(mission_id):
                    continue
                return
            self.store.finish(mission_id, "failed",
                              "no runnable task: a dependency failed or was skipped")
            return

    def cancel(self, mission_id, reason="operator cancelled"):
        """Request cancellation; a running wave stops at the next checkpoint."""
        return self.store.cancel(mission_id, reason)

