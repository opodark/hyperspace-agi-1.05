# SPDX-License-Identifier: Apache-2.0
"""Capability manifest and budget policy for Mission Control.

Two guardrails live here and nowhere else:

* **which tools a role may ever see** — the manifest is the single source of
  truth, and the control plane binds only the intersection of the manifest with
  its own native catalog, so a role literally cannot call a tool it does not own;
* **how much a mission may spend** — steps, wall clock, tokens, replans and
  concurrency, parsed once from the environment;
* **how a model-written plan becomes a valid DAG** — a task key and every
  `dependencies` entry that points at it go through the *same* normalization, so
  a model that writes `check_page_includes` in one place and `check-page-includes`
  in another cannot make the store reject the whole plan.

Unknown roles fall back to the conservative `worker` manifest rather than the
most powerful one: a typo in a plan must not silently hand a planner the sandbox.
"""
from __future__ import annotations

import os
import re

# Tool names refer to the control-plane native catalog (`_NATIVE_TOOLS`). A role
# that names a tool which does not exist simply gets nothing for it — the
# intersection is taken at bind time, never assumed here.
ROLE_MANIFESTS = {
    "planner": {
        "title": "Planner",
        "description": "Decomposes the objective into a DAG. Reasons only; touches nothing.",
        "tools": [],
        "max_iterations": 1,
        "model_class": "reasoning",
        "requires_review": False,
    },
    "repo-analyst": {
        "title": "Repository analyst",
        "description": "Read-only inspection of code, docs, memory and mesh state.",
        "tools": ["web_search", "omega_query", "get_mesh_status"],
        "max_iterations": 8,
        "model_class": "general",
        "requires_review": False,
    },
    "coder": {
        "title": "Coder",
        "description": "Writes code inside the disposable sandbox and proposes a diff; also the only role that can build a static website draft with its image gallery from the approved pictures. Nothing is ever applied.",
        # `create_website` è l'unico tool del coder che scrive **fuori** dalla
        # sandbox: genera una bozza statica in `WEBSITE_DIR` leggendo le immagini
        # — in sola lettura — da `DIARIO_IMMAGINI_DIR`. Il sandbox non monta la
        # raccolta ComfyUI (`/seed`, `/workspaces`, `/exchange` e basta), quindi
        # senza questo tool una missione non può costruire una pagina con la
        # galleria delle foto di Anna. L'esito resta un artifact `applied: False`
        # e `requires_review` è già `True`: mai applicato, sempre da rivedere.
        "tools": ["code_sandbox", "create_website"],
        "max_iterations": 16,
        "model_class": "code",
        "requires_review": True,
    },
    "verifier": {
        "title": "Verifier",
        "description": "Runs checks and inspects diffs in the sandbox. Never edits.",
        # `website_status` è sola lettura: il verifier deve poter guardare
        # l'artefatto che il coder ha scritto **fuori** dalla sandbox (un sito in
        # `WEBSITE_DIR`), altrimenti può solo credere alla prosa del coder.
        "tools": ["code_sandbox", "get_mesh_status", "website_status"],
        "max_iterations": 8,
        "model_class": "code",
        "requires_review": False,
    },
    "memory-agent": {
        "title": "Memory agent",
        "description": "Reads memory to inform the mission. Write-back stays gated.",
        "tools": ["omega_query"],
        "max_iterations": 4,
        "model_class": "general",
        "requires_review": False,
    },
    "ops-agent": {
        "title": "Operations agent",
        "description": "Host operations. Disabled unless OPS_AGENT_ENABLED unlocks it.",
        "tools": [],
        "max_iterations": 4,
        "model_class": "code",
        "requires_review": True,
    },
    "worker": {
        "title": "Worker",
        "description": "Default, conservative role for generic steps.",
        "tools": ["web_search", "omega_query", "get_mesh_status"],
        "max_iterations": 6,
        "model_class": "general",
        "requires_review": False,
    },
}
DEFAULT_ROLE = "worker"

# The only tools an ops-agent may ever be granted, and only with an explicit
# opt-in flag. Even then the manifest never auto-approves anything it does.
OPS_AGENT_TOOLS = ["shell_run", "get_mesh_status"]

BUDGET_DEFAULTS = {
    "max_steps": 40,
    "max_wall_seconds": 3600,
    "max_tokens_per_task": 4096,
    "max_concurrency": 2,
    "max_replans": 3,
    "max_task_attempts": 2,
}
# Hard ceiling for concurrency: the long pole is inference, not scheduling, so
# piling on workers only queues GPU work. Operators may lower it, not raise it
# past this without editing code.
MAX_CONCURRENCY_CEILING = 8


def _ops_agent_enabled():
    return os.getenv("MISSION_OPS_AGENT_ENABLED", "false").strip().lower() == "true"


def resolve_manifest(role=None):
    """Return a copy of a role's manifest, falling back to the worker manifest."""
    key = str(role or "").strip().lower() or DEFAULT_ROLE
    manifest = dict(ROLE_MANIFESTS.get(key, ROLE_MANIFESTS[DEFAULT_ROLE]))
    manifest["role"] = key if key in ROLE_MANIFESTS else DEFAULT_ROLE
    if manifest["role"] == "ops-agent" and _ops_agent_enabled():
        manifest["tools"] = list(OPS_AGENT_TOOLS)
    return manifest


def tools_for_role(role, catalog):
    """Filter a tool catalog down to what the role's manifest allows.

    `catalog` is the control plane's own list of tool dicts (OpenAI schema). The
    result preserves catalog order and is the *only* set of builtins a worker for
    that role is ever handed.
    """
    allowed = set(resolve_manifest(role).get("tools", []))
    if not allowed:
        return []
    return [tool for tool in catalog
            if tool.get("function", {}).get("name") in allowed]


def parse_budget(env=None, overrides=None):
    """Merge defaults, environment variables and per-mission overrides.

    Precedence: defaults < environment < explicit request overrides. Values are
    clamped to sane ranges so a malformed request cannot disable a guardrail.
    """
    env = os.environ if env is None else env
    budget = dict(BUDGET_DEFAULTS)
    for key, default in BUDGET_DEFAULTS.items():
        raw = env.get("MISSION_" + key.upper())
        if raw not in (None, ""):
            try:
                budget[key] = int(raw)
            except (TypeError, ValueError):
                budget[key] = default
    for key, value in (overrides or {}).items():
        if key not in BUDGET_DEFAULTS:
            continue
        try:
            budget[key] = int(value)
        except (TypeError, ValueError):
            continue
    budget["max_steps"] = max(1, min(budget["max_steps"], 1000))
    budget["max_wall_seconds"] = max(30, min(budget["max_wall_seconds"], 86400))
    budget["max_tokens_per_task"] = max(256, min(budget["max_tokens_per_task"], 200000))
    budget["max_concurrency"] = max(1, min(budget["max_concurrency"], MAX_CONCURRENCY_CEILING))
    budget["max_replans"] = max(0, min(budget["max_replans"], 20))
    budget["max_task_attempts"] = max(1, min(budget["max_task_attempts"], 5))
    return budget


def budget_exhausted(budget, *, steps, replans, elapsed_seconds):
    """True when the mission must stop. Checked before each dispatch wave."""
    return (steps > budget["max_steps"]
            or replans > budget["max_replans"]
            or elapsed_seconds > budget["max_wall_seconds"])


def review_required(role):
    return bool(resolve_manifest(role).get("requires_review"))


# ── NORMALIZZAZIONE DEL PIANO ─────────────────────────────────────────────────
# Un modello da 8B scrive i tasti dei task come gli viene: `check_page_includes`
# oggi, `check-page-includes` domani. Normalizzare solo il tasto lascia indietro
# le `dependencies`: il modello nomina lo stesso task in due modi e `validate_dag`
# rifiuta l'intero piano con "depends on unknown task". La regola è quindi UNA e
# vale per entrambi i lati.
KEY_RE = re.compile(r"[^a-z0-9-]")
KEY_MAX = 60


def task_key(raw, fallback=""):
    """Il tasto di un task in kebab: `Check_Page Includes` -> `check-page-includes`."""
    return (KEY_RE.sub("-", str(raw or "").lower()).strip("-")[:KEY_MAX]
            or str(fallback or ""))


def resolve_dependencies(tasks, alias=None):
    """Riporta ogni dipendenza al tasto reale del piano, scartando i riferimenti nel vuoto.

    `alias` mappa ciò che il modello ha scritto — nella forma originale o già
    normalizzata — al tasto finale: è l'unico modo per collegare
    `check_page_includes` a `check-page-includes`. Una dipendenza che non
    corrisponde a nessun task viene tolta: un DAG coerente con una dipendenza in
    meno è meglio di un piano rifiutato in blocco. Chi chiama riceve i task
    puliti e può registrare cosa è cambiato.
    """
    alias = dict(alias or {})
    known = {str(task.get("key")) for task in tasks if task.get("key")}
    cleaned = []
    for task in tasks:
        row = dict(task)
        key = str(row.get("key") or "")
        dependencies, seen = [], set()
        for dependency in row.get("dependencies") or []:
            written = str(dependency).strip()
            target = alias.get(written, alias.get(task_key(written), written))
            if target in known and target != key and target not in seen:
                seen.add(target)
                dependencies.append(target)
        row["dependencies"] = dependencies
        cleaned.append(row)
    return cleaned


def effective_budget(mission, ceiling=None):
    """A mission may lower the configured limits, never raise them."""
    limits = parse_budget(overrides=ceiling or {})
    requested = parse_budget(env={}, overrides=(mission or {}).get("budget") or {})
    explicit = (mission or {}).get("budget") or {}
    return {key: min(value, requested[key]) if key in explicit else value
            for key, value in limits.items()}
