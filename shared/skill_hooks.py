# SPDX-License-Identifier: Apache-2.0
"""Bounded, deterministic before-context hook. Never executes upstream scripts.

Keyword-trigger design informed by diet103's MIT reference in vendor/skill-hooks.
Rules are server-owned; skill text cannot grant capabilities or alter selection.
"""

import json
import re
from pathlib import Path

from shared.forge_skills import attach_skills, source_hash

# (artifact prefix, terms, required native tools, allowed roles)
RULES = (
    (
        "ecc-security-review-",
        ("security", "sicurezza", "vulnerability", "vulnerabilità"),
        ("code_sandbox",),
        ("coder", "verifier", "chat"),
    ),
    (
        "ecc-verification-loop-",
        ("test", "tests", "pytest", "verifica", "regression", "regressione"),
        ("code_sandbox",),
        ("coder", "verifier", "chat"),
    ),
    (
        "anydoc-convert-documents-to-markdown-",
        ("converti", "convert", "conversione"),
        ("converti_documento_markdown",),
        ("worker", "chat"),
    ),
    (
        "wayfinder-wayfinder-",
        ("wayfinder", "pianifica", "planning"),
        ("wayfinder_map",),
        ("chat",),
    ),
)


def before_context(data, items, tools, role="chat"):
    """Return new model data and an audit list; approval is rechecked at injection."""
    # Explicitly attached workflows take precedence; do not stack another budget.
    messages = data.get("messages", [])
    if any(
        isinstance(m.get("content"), str)
        and m["content"].startswith("Selected reference workflows for this task.")
        for m in messages
    ):
        return dict(data), [{"reason": "explicit_context_present"}]
    prompt = next(
        (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
        "",
    )
    if not isinstance(prompt, str):
        return dict(data), [{"reason": "unsupported_prompt"}]
    words = set(re.findall(r"\w+", prompt.casefold()))
    available = {t.get("function", {}).get("name") for t in tools}
    selected, audit, snapshots = [], [], {}
    result = dict(data)
    for item in sorted(
        (i for i in items if isinstance(i, dict)), key=lambda i: str(i.get("id", ""))
    ):
        ident = item.get("id", "")
        if not isinstance(ident, str):
            continue
        rule = next((r for r in RULES if ident.startswith(r[0])), None)
        if rule is None or item.get("type") != "skill":
            continue
        _, terms, required, roles = rule
        matched = sorted(words.intersection(terms))
        reason = None
        source = item.get("source")
        if item.get("status") != "approved":
            reason = "not_approved"
        elif (
            not isinstance(source, str)
            or not source.strip()
            or source_hash(source) != item.get("approved_source_sha256")
        ):
            reason = "approval_stale"
        elif role not in roles:
            reason = "role_mismatch"
        elif not set(required).issubset(available):
            reason = "missing_tools"
        elif not matched:
            reason = "no_trigger"
        elif len(selected) >= 2:
            reason = "selection_limit"
        else:
            snapshots[ident] = item
            try:
                candidate = attach_skills(
                    {**data, "hyperspace_skills": selected + [ident]},
                    snapshots.__getitem__,
                )
            except (ValueError, OSError, TypeError):
                reason = "context_rejected"
            else:
                selected.append(ident)
                result = candidate
                reason = "selected"
        audit.append(
            {
                "id": ident,
                "reason": reason,
                "matched": matched,
                "missing_tools": sorted(set(required) - available),
            }
        )
    return result, audit


def from_directory(data, directory, tools, role="chat"):
    """Read a bounded local Forge snapshot; corrupt records never stop inference."""
    items = []
    root = Path(directory)
    if root.is_dir():
        for path in sorted(root.glob("*.json"))[:1000]:
            try:
                if path.is_symlink() or path.stat().st_size > 512_000:
                    continue
                items.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError, UnicodeError):
                continue
    return before_context(data, items, tools, role)
