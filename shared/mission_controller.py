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
from typing import Any, Dict, List, Optional

from shared import mission_policy
from shared.mission import TERMINAL_MISSION_STATUSES, task_review_status


class MissionController:
    def __init__(self, store, *, planner, worker, verifier, budget=None,
                 concurrency=None, clock=time.time, on_event=None,
                 review_required=mission_policy.review_required,
                 causal_graph: Optional[Any] = None):
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
        self.causal_graph = causal_graph

    # ── helpers ───────────────────────────────────────────────────────────────
    def _emit(self, event, mission_id, detail=None):
        if self.on_event:
            try:
                self.on_event(event, mission_id, detail or {})
            except Exception:
                pass

    def status(self):
        res = {"enabled": True, "running": self.running, "error": self.error,
                "last_mission": self.last_mission,
                "concurrency": self.budget["max_concurrency"],
                "budget": self.budget, "missions": self.store.status()}
        if self.causal_graph and hasattr(self.causal_graph, "export_graph_summary"):
            res["causal_graph"] = self.causal_graph.export_graph_summary()
        return res

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
        view["receipts"] = mission.get("receipts") or {}
        mission_id = mission["id"]
        view["_cancelled"] = lambda: (self.store.get(mission_id) or {}).get("status") in {"cancelled", "failed"}
        return view

    def _run_task(self, mission_id, task):
        attempt = task.get("attempts", 1)
        idempotency_key = f"{mission_id}:{task['task_id']}:{attempt}"
        receipt = getattr(self.store, "get_receipt", lambda mid, ikey: None)(mission_id, idempotency_key)
        if receipt and isinstance(receipt.get("result"), dict) and receipt["result"].get("ok"):
            return receipt["result"]

        task_view = dict(task)
        task_view["idempotency_key"] = idempotency_key
        try:
            outcome = self.worker(task_view, self._view(self.store.get(mission_id))) or {}
        except Exception as error:  # a worker crash is a task failure, not a crash
            outcome = {"ok": False, "error": str(error) or type(error).__name__}
        if not isinstance(outcome, dict):
            outcome = {"ok": False, "error": "worker returned a non-dict outcome"}
        if outcome.get("ok"):
            try:
                if hasattr(self.store, "record_receipt"):
                    self.store.record_receipt(mission_id, idempotency_key, "task_execution", outcome)
            except Exception:
                pass
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
        if self.causal_graph:
            self._record_apply_result_causality(mission_id, task, outcome, verdict)

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
            self._finish_mission(mission_id, "failed", f"planner error: {error}")
            return False
        caps = {t.get("role", "worker"): t.get("tools", []) for t in tasks if isinstance(t, dict)}
        try:
            self.store.set_plan(mission_id, tasks, plan={"roles": sorted(
                {t.get("role", "worker") for t in tasks if isinstance(t, dict)}),
                "capabilities": caps})
        except ValueError as error:
            self._finish_mission(mission_id, "failed", f"invalid plan: {error}")
            return False
        self._emit("plan", mission_id, {"tasks": len(tasks)})
        if self.causal_graph:
            self._record_plan_causality(mission_id, mission, tasks)
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
        if self.causal_graph:
            self._record_replan_causality(mission_id, mission, reason, tasks)
        return True

    def _conclude(self, mission_id):
        """All tasks are terminal: ask the verifier about the whole mission.

        Returns True when a replan was queued (the caller should keep looping).
        """
        mission = self.store.get(mission_id)
        verdict = self._verify("mission", mission)
        decision = verdict["verdict"]
        if decision == "pass":
            self._finish_mission(mission_id, "done")
            return False
        replans = mission.get("counters", {}).get("replans", 0)
        if decision == "replan" and replans < mission_policy.effective_budget(mission, self.budget)["max_replans"]:
            if self._replan(mission_id, mission, verdict.get("reason") or "mission not satisfied yet"):
                return True
        self._finish_mission(mission_id, "failed", verdict.get("reason") or "mission verification failed")
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
                self._finish_mission(mission_id, "failed", "budget exhausted: time limit")
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
                try:
                    from shared.harness_reflector import HarnessReflector
                    HarnessReflector().reflect_on_mission(mission_id, store=self.store)
                except Exception:
                    pass
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
                self._finish_mission(mission_id, "failed",
                                  "budget exhausted: steps={} replans={} elapsed={}s".format(
                                      counters.get("steps", 0), counters.get("replans", 0), int(elapsed)))
                return
            ready = self.store.ready_tasks(mission_id)
            if ready:
                if mission["counters"].get("steps", 0) >= mission_policy.effective_budget(mission, self.budget)["max_steps"]:
                    self._finish_mission(mission_id, "failed", "budget exhausted: no task attempts remaining")
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
                        self._finish_mission(mission_id, "failed", "replan budget exhausted")
                        return
                    self._replan(mission_id, mission, replan_reason)
                continue
            summary = self.store.summary(mission_id)
            if summary["all_terminal"]:
                if self._conclude(mission_id):
                    continue
                return
            self._finish_mission(mission_id, "failed",
                              "no runnable task: a dependency failed or was skipped")
            return

    def cancel(self, mission_id, reason="operator cancelled"):
        """Request cancellation; a running wave stops at the next checkpoint."""
        return self.store.cancel(mission_id, reason)

    # ── Causal Graph Integration ─────────────────────────────────────────────
    def _record_plan_causality(self, mission_id: str, mission: Dict[str, Any], tasks: List[Any]) -> None:
        goal_node = f"goal:{mission_id}"
        obj = mission.get("objective", "")
        for t in tasks:
            if not isinstance(t, dict):
                continue
            tid = t.get("task_id") or t.get("key")
            task_node = f"task:{mission_id}:{tid}"
            self.causal_graph.record_event(
                cause_id=goal_node,
                effect_id=task_node,
                weight=1.0,
                metadata={
                    "title": t.get("title", ""),
                    "role": t.get("role", "worker"),
                    "instruction": t.get("instruction", ""),
                    "objective": obj,
                },
            )
            for dep in t.get("dependencies", []):
                dep_node = f"task:{mission_id}:{dep}"
                self.causal_graph.record_event(
                    cause_id=dep_node,
                    effect_id=task_node,
                    weight=1.0,
                    metadata={"relation": "depends_on"},
                )

    def _record_replan_causality(self, mission_id: str, mission: Dict[str, Any], reason: str, tasks: List[Any]) -> None:
        replans = mission.get("counters", {}).get("replans", 0) + 1
        replan_node = f"replan:{mission_id}:{replans}"
        for t in tasks:
            if not isinstance(t, dict):
                continue
            tid = t.get("task_id") or t.get("key")
            task_node = f"task:{mission_id}:{tid}"
            self.causal_graph.record_event(
                cause_id=replan_node,
                effect_id=task_node,
                weight=0.9,
                metadata={
                    "title": t.get("title", ""),
                    "role": t.get("role", "worker"),
                    "replan_reason": reason,
                },
            )
            for dep in t.get("dependencies", []):
                dep_node = f"task:{mission_id}:{dep}"
                self.causal_graph.record_event(
                    cause_id=dep_node,
                    effect_id=task_node,
                    weight=1.0,
                    metadata={"relation": "replan_depends_on"},
                )

    def _record_apply_result_causality(self, mission_id: str, task: Dict[str, Any], outcome: Dict[str, Any], verdict: Dict[str, Any]) -> None:
        attempt = task.get("attempts", 1)
        task_id = task["task_id"]
        task_node = f"task:{mission_id}:{task_id}"
        exec_node = f"exec:{mission_id}:{task_id}:{attempt}"
        verdict_node = f"verdict:{mission_id}:{task_id}:{attempt}"

        ok = outcome.get("ok", False)
        exec_w = 1.0 if ok else 0.3
        self.causal_graph.record_event(
            cause_id=task_node,
            effect_id=exec_node,
            weight=exec_w,
            metadata={
                "attempt": attempt,
                "role": task.get("role", "worker"),
                "model": outcome.get("model", ""),
                "target": outcome.get("target", ""),
                "tokens": outcome.get("tokens", 0),
                "ok": ok,
                "error": outcome.get("error", ""),
            },
        )

        for art in outcome.get("artifacts") or []:
            art_id = art.get("path") or art.get("name") or art.get("type") or "artifact"
            art_node = f"artifact:{mission_id}:{art_id}"
            self.causal_graph.record_event(
                cause_id=exec_node,
                effect_id=art_node,
                weight=1.0,
                metadata={"type": art.get("type", ""), "applied": art.get("applied", False)},
            )

        dec = verdict.get("verdict", "fail")
        v_w = 1.0 if dec == "pass" else (0.5 if dec == "retry" else 0.1)
        self.causal_graph.record_event(
            cause_id=exec_node,
            effect_id=verdict_node,
            weight=v_w,
            metadata={"verdict": dec, "reason": verdict.get("reason", "")},
        )

        if dec == "pass":
            # Collega l'esito positivo ai task dipendenti
            mission = self.store.get(mission_id) or {}
            for t_down in mission.get("tasks", []):
                if task_id in t_down.get("dependencies", []):
                    down_node = f"task:{mission_id}:{t_down['task_id']}"
                    self.causal_graph.record_event(
                        cause_id=verdict_node,
                        effect_id=down_node,
                        weight=1.0,
                        metadata={"relation": "dependency_satisfied"},
                    )

    def _finish_mission(self, mission_id, status, reason=""):
        res = self.store.finish(mission_id, status, reason)
        if self.causal_graph:
            self._record_mission_terminal_causality(mission_id, status, reason)
        return res

    def _record_mission_terminal_causality(self, mission_id: str, status: str, reason: str = "") -> None:
        mission = self.store.get(mission_id) or {}
        terminal_node = f"mission:{mission_id}:{status}"
        tasks = mission.get("tasks", [])
        for t in tasks:
            tid = t["task_id"]
            t_status = t.get("status")
            attempt = t.get("attempts", 1)
            verdict_node = f"verdict:{mission_id}:{tid}:{attempt}"
            exec_node = f"exec:{mission_id}:{tid}:{attempt}"
            task_node = f"task:{mission_id}:{tid}"

            cause_node = task_node
            if verdict_node in self.causal_graph._reverse or verdict_node in self.causal_graph._forward:
                cause_node = verdict_node
            elif exec_node in self.causal_graph._reverse or exec_node in self.causal_graph._forward:
                cause_node = exec_node

            w = 1.0 if t_status == "done" else (0.1 if t_status == "failed" else 0.5)
            self.causal_graph.record_event(
                cause_id=cause_node,
                effect_id=terminal_node,
                weight=w,
                metadata={
                    "task_status": t_status,
                    "role": t.get("role"),
                    "mission_status": status,
                    "reason": reason,
                },
            )

        if not tasks:
            self.causal_graph.record_event(
                cause_id=f"goal:{mission_id}",
                effect_id=terminal_node,
                weight=0.0,
                metadata={"mission_status": status, "reason": reason},
            )

    def trace_task_lineage(self, mission_id: str, task_id: str) -> Dict[str, Any]:
        """Traccia la genealogia causale (upstream tasks, modelli, esecuzioni, goal) di un task."""
        if not self.causal_graph:
            return {"error": "no causal graph configured"}
        task_node = f"task:{mission_id}:{task_id}"
        return {
            "task_node": task_node,
            "lineage": self.causal_graph.trace_lineage(task_node),
            "forward_consequences": self.causal_graph.get_forward_consequences(task_node),
            "detailed_events": self.causal_graph.trace_detailed_lineage(task_node),
        }

    def diagnose_root_cause(self, mission_id: str, task_id: Optional[str] = None) -> Dict[str, Any]:
        """Identifica la causa radice del fallimento di un task o dell'intera missione."""
        if not self.causal_graph:
            return {"error": "no causal graph configured"}

        if task_id:
            target_node = f"task:{mission_id}:{task_id}"
            candidates = [
                e for e in self.causal_graph._forward.get(target_node, [])
                if e[0].startswith(f"exec:{mission_id}:{task_id}:")
            ]
            if candidates:
                exec_target = candidates[-1][0]
                verdict_candidates = [
                    v for v in self.causal_graph._forward.get(exec_target, [])
                    if v[0].startswith(f"verdict:{mission_id}:{task_id}:")
                ]
                target_node = verdict_candidates[-1][0] if verdict_candidates else exec_target
        else:
            target_node = f"mission:{mission_id}:failed"

        events = self.causal_graph.trace_detailed_lineage(target_node)

        failing_events = [
            e for e in events
            if e.get("metadata", {}).get("ok") is False
            or e.get("metadata", {}).get("verdict") in {"fail", "retry"}
            or e.get("weight", 1.0) < 0.5
        ]

        root_cause = failing_events[0] if failing_events else (events[0] if events else None)
        culprit = None
        if root_cause:
            meta = root_cause.get("metadata", {})
            culprit = {
                "cause_node": root_cause.get("cause_id"),
                "effect_node": root_cause.get("effect_id"),
                "model": meta.get("model") or meta.get("target"),
                "error": meta.get("error") or meta.get("reason") or "unspecified failure",
                "attempt": meta.get("attempt"),
            }

        return {
            "target": target_node,
            "total_lineage_events": len(events),
            "failing_events_count": len(failing_events),
            "root_cause_event": root_cause,
            "suspected_culprit": culprit,
        }

    def export_mission_causal_subgraph(self, mission_id: str) -> Dict[str, Any]:
        """Estrae il grafo causale dei soli nodi e archi associati a una determinata missione."""
        if not self.causal_graph:
            return {"nodes": [], "edges": [], "events": []}

        mid_marker = f":{mission_id}:"
        goal_marker = f"goal:{mission_id}"
        mission_marker = f"mission:{mission_id}:"

        relevant_events = [
            ev for ev in self.causal_graph._episodic_memory.values()
            if mid_marker in ev.get("cause_id", "") or mid_marker in ev.get("effect_id", "")
            or ev.get("cause_id") == goal_marker or ev.get("effect_id") == goal_marker
            or ev.get("cause_id", "").startswith(mission_marker) or ev.get("effect_id", "").startswith(mission_marker)
        ]

        nodes = set()
        edges = []
        for ev in relevant_events:
            c = ev["cause_id"]
            e = ev["effect_id"]
            nodes.add(c)
            nodes.add(e)
            edges.append({"from": c, "to": e, "weight": ev.get("weight", 1.0), "event_id": ev.get("event_id")})

        return {
            "mission_id": mission_id,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "nodes": sorted(list(nodes)),
            "edges": edges,
            "events": relevant_events,
        }

