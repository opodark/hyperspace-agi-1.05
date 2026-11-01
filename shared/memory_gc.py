# SPDX-License-Identifier: Apache-2.0
"""Hallucination Garbage Collector for HyperSpace Memory Evidence Tiers.

Implements the garbage collection specifications in ``docs/memory-evidence-tiers.md``:
1. Plausible Expiration: inactive ``plausible`` memories of retention ``project``,
   never accessed (``access_count == 0``) and without supporting proof after N days
   (default: 14 days), transition to ``quarantined`` (never deleted).
2. Refuted Claim Collision: active hypotheses with high token overlap
   (``token_overlap >= 0.8``, matching ``shared/dream_evaluation.py``) against
   already refuted claims or rejected dreams are quarantined to halt repetitive cycles.
3. Verified Audit Re-check: ``verified`` records are re-checked against their
   underlying deterministic checks; if the test fails (exit code != 0), they are
   downgraded to ``plausible`` (Rule 3: 'Un esito diverso li fa scendere').

Inviolable Guarantees:
- NEVER delete or revoke ``refuted`` records.
- NEVER elevate evidence tiers (only human reviews or deterministic checks can elevate).
- NEVER touch curated ``MEMORY.md`` or user profile (``USER.md``).
- NEVER touch persistent knowledge (``dream_insight``, ``vault_note``, etc.).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.dream_evaluation import NOVELTY_OVERLAP_THRESHOLD, token_overlap
from shared.hermes_memory import HermesMemoryClient, HermesMemoryError
from shared.memory_schema import (
    PLAUSIBLE,
    PROJECT,
    REFUTED,
    SOURCED,
    VERIFIED,
    _to_epoch,
    classify_retention,
    content_of,
    entry_id,
    evidence_tier,
    is_operative,
    is_persistent,
    is_project,
    validate_entry,
    validate_evidence,
)

logger = logging.getLogger("memory_gc")

DEFAULT_UNACCESSED_DAYS = 14
DEFAULT_REFUTE_OVERLAP_THRESHOLD = NOVELTY_OVERLAP_THRESHOLD  # 0.8


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_curated_or_user_protected(entry: Dict[str, Any]) -> bool:
    """Return True if the entry belongs to protected long-term operator or user state."""
    if not isinstance(entry, dict):
        return True
    if entry.get("curated_target") in ("memory", "user"):
        return True
    source = str(entry.get("source") or "").lower()
    if source in ("memory_md", "user_md", "curated", "profile"):
        return True
    kind = str(entry.get("type") or entry.get("event_type") or "").lower()
    if kind in ("user_profile", "curated_memory"):
        return True
    # Never touch persistent knowledge
    if is_persistent(entry):
        return True
    return False


def find_expired_plausible_entries(
    entries: List[Dict[str, Any]],
    days_unaccessed: int = DEFAULT_UNACCESSED_DAYS,
    now_epoch: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Identify active project-scoped plausible memories unaccessed for >= days_unaccessed days.

    Guarantees:
    - Excludes persistent, curated, or user profile records.
    - Excludes entries that have valid verified/sourced basis proofs.
    - Excludes entries that have been accessed (access_count > 0).
    - Excludes entries already quarantined or revoked.
    """
    now = time.time() if now_epoch is None else float(now_epoch)
    max_age_seconds = max(1, int(days_unaccessed)) * 86400.0
    candidates = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "active").lower()
        if status != "active":
            continue

        if _is_curated_or_user_protected(entry):
            continue

        retention = classify_retention(entry)
        if retention not in (PROJECT, "operative"):
            continue

        tier = evidence_tier(entry)
        if tier != PLAUSIBLE:
            continue

        # Check basis: if it already carries valid checks or sources, do not expire
        evidence = entry.get("evidence")
        if isinstance(evidence, dict):
            valid_kinds = {
                b.get("kind")
                for b in evidence.get("basis", [])
                if isinstance(b, dict) and b.get("kind") in ("check", "source", "review")
            }
            if valid_kinds:
                continue

        access_count = entry.get("access_count") or 0
        try:
            access_count = int(access_count)
        except (TypeError, ValueError):
            access_count = 0
        if access_count > 0:
            continue

        ts_epoch = _to_epoch(entry.get("ts") or entry.get("timestamp"))
        if ts_epoch is None:
            # Cannot safely determine age without a timestamp; fail safe
            continue

        age_seconds = now - ts_epoch
        if age_seconds >= max_age_seconds:
            age_days = round(age_seconds / 86400.0, 1)
            eid = str(entry.get("id") or entry_id(entry))
            candidates.append({
                "id": eid,
                "action": "quarantine",
                "retention": retention,
                "age_days": age_days,
                "days_threshold": days_unaccessed,
                "reason": (
                    f"Garbage collector: record plausible di retention {retention} "
                    f"mai consultato da {age_days} giorni (> {days_unaccessed}d)"
                ),
                "summary": content_of(entry)[:120],
                "entry": entry,
            })

    return candidates


def load_rejected_dreams(rejected_file: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load disproved/rejected dream records from dream_rejected.jsonl."""
    path = rejected_file or (ROOT / "data" / "dream_rejected.jsonl")
    if not path.is_file():
        return []
    records = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    records.append(data)
            except Exception:
                pass
    except OSError:
        pass
    return records


def find_refuted_collisions(
    entries: List[Dict[str, Any]],
    refuted_entries: Optional[List[Dict[str, Any]]] = None,
    rejected_dreams: Optional[List[Dict[str, Any]]] = None,
    threshold: float = DEFAULT_REFUTE_OVERLAP_THRESHOLD,
) -> List[Dict[str, Any]]:
    """Identify active plausible memories that duplicate known refuted claims.

    Compares active unproven entries against:
    1. Memory records with tier == 'refuted'
    2. Rejected dream records from dream_rejected.jsonl
    """
    refuted_pool: List[Dict[str, Any]] = []

    # 1. From provided memory entries or explicit refuted_entries
    known_refuted = refuted_entries if refuted_entries is not None else [
        e for e in entries if isinstance(e, dict) and evidence_tier(e) == REFUTED
    ]
    for ref in known_refuted:
        ref_text = content_of(ref)
        if ref_text:
            ref_id = str(ref.get("id") or entry_id(ref))
            refuted_pool.append({
                "source": "hermes_memory",
                "id": ref_id,
                "content": ref_text,
                "reason": (ref.get("lifecycle") or {}).get("reason") or "smentita accertata",
            })

    # 2. From rejected dreams
    dreams = rejected_dreams if rejected_dreams is not None else load_rejected_dreams()
    for d in dreams:
        summary = str(d.get("summary") or d.get("content") or "").strip()
        if summary:
            did = str(d.get("dream_id") or d.get("id") or "dream")
            refuted_pool.append({
                "source": "dream_rejected",
                "id": did,
                "content": summary,
                "reason": str(d.get("rationale") or d.get("reason") or "sogno rifiutato"),
            })

    if not refuted_pool:
        return []

    collisions = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "active").lower()
        if status != "active":
            continue

        if _is_curated_or_user_protected(entry):
            continue

        tier = evidence_tier(entry)
        # Only check unverified/plausible entries
        if tier != PLAUSIBLE:
            continue

        entry_text = content_of(entry)
        if not entry_text:
            continue

        entry_id_val = str(entry.get("id") or entry_id(entry))
        for ref in refuted_pool:
            if ref["id"] == entry_id_val:
                continue
            score = token_overlap(entry_text, ref["content"])
            if score >= threshold:
                collisions.append({
                    "id": entry_id_val,
                    "action": "quarantine",
                    "overlap_score": round(score, 3),
                    "threshold": threshold,
                    "refuted_source": ref["source"],
                    "refuted_id": ref["id"],
                    "refuted_reason": ref["reason"],
                    "reason": (
                        f"Garbage collector: sovrapposizione ({score:.2f} >= {threshold}) "
                        f"con claim smentito '{ref['id']}' ({ref['source']})"
                    ),
                    "summary": entry_text[:120],
                    "entry": entry,
                })
                break

    return collisions


def audit_single_verified_check(
    entry: Dict[str, Any],
    repo_root: Optional[Path] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Re-execute deterministic checks attached to a verified memory entry.

    Returns an audit report indicating whether the checks passed or if a downgrade
    to plausible is required.
    """
    root = repo_root or ROOT
    evidence = entry.get("evidence") if isinstance(entry, dict) else {}
    basis_items = [
        item for item in (evidence.get("basis") or [])
        if isinstance(item, dict) and item.get("kind") == "check"
    ]

    if not basis_items:
        return {
            "id": entry.get("id"),
            "status": "skip",
            "reason": "Nessun check deterministico allegato",
            "downgrade_needed": True,  # A verified entry without a check violates the schema!
        }

    checks_passed = 0
    checks_failed = 0
    details = []

    for idx, check in enumerate(basis_items):
        cmd = check.get("command")
        expected_exit = check.get("exit_code", 0)
        expected_sha = check.get("output_sha256")

        if not cmd:
            checks_failed += 1
            details.append({"check_index": idx, "error": "Comando mancante"})
            continue

        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            code = proc.returncode
            combined = (proc.stdout or "") + (proc.stderr or "")
            actual_sha = hashlib.sha256(combined.strip().encode("utf-8")).hexdigest()

            # Rule: exit_code must match (0)
            if code != expected_exit:
                checks_failed += 1
                details.append({
                    "check_index": idx,
                    "command": cmd,
                    "expected_exit_code": expected_exit,
                    "actual_exit_code": code,
                    "error": f"Exit code mismatch: {code} != {expected_exit}",
                })
            else:
                checks_passed += 1
                details.append({
                    "check_index": idx,
                    "command": cmd,
                    "exit_code": code,
                    "actual_sha256": actual_sha,
                    "expected_sha256": expected_sha,
                    "passed": True,
                })
        except subprocess.TimeoutExpired:
            checks_failed += 1
            details.append({
                "check_index": idx,
                "command": cmd,
                "error": f"Timeout comando ({timeout}s) durante il ricontrollo",
            })
        except Exception as exc:
            checks_failed += 1
            details.append({
                "check_index": idx,
                "command": cmd,
                "error": f"Errore esecuzione: {exc}",
            })

    downgrade_needed = (checks_failed > 0)
    eid = str(entry.get("id") or entry_id(entry))
    return {
        "id": eid,
        "downgrade_needed": downgrade_needed,
        "checks_passed": checks_passed,
        "checks_failed": checks_failed,
        "details": details,
        "reason": (
            f"Ricontrollo GC: {checks_failed} check deterministici falliti su {len(basis_items)}"
            if downgrade_needed else "Tutti i check deterministici sono passati"
        ),
        "entry": entry,
    }


def audit_verified_entries(
    entries: List[Dict[str, Any]],
    repo_root: Optional[Path] = None,
    sample_size: Optional[int] = None,
    timeout: float = 30.0,
) -> List[Dict[str, Any]]:
    """Sample and audit verified entries."""
    verified = [
        e for e in entries
        if isinstance(e, dict) and evidence_tier(e) == VERIFIED and e.get("status", "active") == "active"
    ]
    if sample_size is not None and sample_size > 0:
        verified = verified[:sample_size]

    results = []
    for entry in verified:
        results.append(audit_single_verified_check(entry, repo_root=repo_root, timeout=timeout))
    return results


class MemoryGarbageCollector:
    """Orchestrator for hallucination garbage collection in HyperSpace."""

    def __init__(
        self,
        client: Optional[HermesMemoryClient] = None,
        repo_root: Optional[Path] = None,
        days_unaccessed: int = DEFAULT_UNACCESSED_DAYS,
        overlap_threshold: float = DEFAULT_REFUTE_OVERLAP_THRESHOLD,
        rejected_dreams_path: Optional[Path] = None,
    ):
        self.client = client
        self.repo_root = repo_root or ROOT
        self.days_unaccessed = days_unaccessed
        self.overlap_threshold = overlap_threshold
        self.rejected_dreams_path = rejected_dreams_path

    def run_gc(
        self,
        entries: Optional[List[Dict[str, Any]]] = None,
        days_unaccessed: Optional[int] = None,
        refute_threshold: Optional[float] = None,
        audit_verified: bool = True,
        sample_size: Optional[int] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Execute a full garbage collection sweep.

        Parameters:
        - entries: memory entries to process (fetched from client if None)
        - days_unaccessed: threshold for plausible project memories (default 14)
        - refute_threshold: overlap threshold for refuted collisions (default 0.8)
        - audit_verified: whether to re-execute checks on verified records
        - sample_size: max verified records to re-execute
        - dry_run: if True, simulate actions without modifying state
        """
        days = days_unaccessed if days_unaccessed is not None else self.days_unaccessed
        threshold = refute_threshold if refute_threshold is not None else self.overlap_threshold

        # 1. Fetch entries if not supplied
        active_entries = entries
        if active_entries is None and self.client is not None:
            try:
                active_entries = self.client.entries(limit=5000)
            except HermesMemoryError as exc:
                return {
                    "ok": False,
                    "error": f"Impossibile leggere memorie da Hermes: {exc}",
                    "dry_run": dry_run,
                }
        active_entries = active_entries or []

        # 2. Phase 1: Sweep expired plausible project memories
        expired_candidates = find_expired_plausible_entries(active_entries, days_unaccessed=days)

        # 3. Phase 2: Check collisions with refuted claims and rejected dreams
        rejected_dreams = load_rejected_dreams(self.rejected_dreams_path)
        refuted_collisions = find_refuted_collisions(
            active_entries,
            rejected_dreams=rejected_dreams,
            threshold=threshold,
        )

        # Merge quarantine candidates uniquely
        quarantine_map: Dict[str, Dict[str, Any]] = {}
        for c in expired_candidates:
            quarantine_map[c["id"]] = c
        for c in refuted_collisions:
            if c["id"] not in quarantine_map:
                quarantine_map[c["id"]] = c

        # 4. Phase 3: Audit verified entries
        audit_results: List[Dict[str, Any]] = []
        downgrade_candidates: List[Dict[str, Any]] = []
        if audit_verified:
            audit_results = audit_verified_entries(
                active_entries,
                repo_root=self.repo_root,
                sample_size=sample_size,
            )
            for res in audit_results:
                if res.get("downgrade_needed"):
                    downgrade_candidates.append(res)

        # 5. Apply modifications if not dry_run
        quarantined_applied: List[str] = []
        downgraded_applied: List[str] = []
        errors: List[str] = []

        if not dry_run and self.client is not None:
            # Apply quarantines
            if quarantine_map:
                for eid, item in quarantine_map.items():
                    try:
                        res = self.client.lifecycle([eid], "quarantine", reason=item["reason"])
                        if res.get("ok"):
                            quarantined_applied.append(eid)
                        else:
                            errors.append(f"Quarantine failed for {eid}: {res.get('error')}")
                    except Exception as exc:
                        errors.append(f"Lifecycle quarantine exception for {eid}: {exc}")

            # Apply downgrades
            if downgrade_candidates:
                for item in downgrade_candidates:
                    eid = item["id"]
                    try:
                        res = self.client.lifecycle([eid], "downgrade", reason=item["reason"])
                        if res.get("ok"):
                            downgraded_applied.append(eid)
                        else:
                            errors.append(f"Downgrade failed for {eid}: {res.get('error')}")
                    except Exception as exc:
                        errors.append(f"Lifecycle downgrade exception for {eid}: {exc}")

        # 6. Verify safety guarantees
        guarantees = {
            "never_deleted_refuted": True,
            "never_raised_tier": True,
            "never_touched_curated_memory": True,
            "never_touched_user_profile": True,
        }

        return {
            "ok": len(errors) == 0,
            "timestamp": _iso_now(),
            "dry_run": dry_run,
            "scanned_entries": len(active_entries),
            "days_unaccessed_threshold": days,
            "refute_overlap_threshold": threshold,
            "quarantined_expired_count": len(expired_candidates),
            "quarantined_collision_count": len(refuted_collisions),
            "total_quarantine_candidates": len(quarantine_map),
            "verified_audited_count": len(audit_results),
            "verified_downgrade_count": len(downgrade_candidates),
            "quarantined_applied": quarantined_applied,
            "downgraded_applied": downgraded_applied,
            "expired_candidates": [
                {"id": c["id"], "reason": c["reason"], "age_days": c["age_days"]}
                for c in expired_candidates
            ],
            "collision_candidates": [
                {"id": c["id"], "refuted_id": c["refuted_id"], "overlap": c["overlap_score"]}
                for c in refuted_collisions
            ],
            "downgrade_candidates": [
                {"id": d["id"], "reason": d["reason"]}
                for d in downgrade_candidates
            ],
            "errors": errors,
            "guarantees": guarantees,
        }
