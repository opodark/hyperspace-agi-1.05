# SPDX-License-Identifier: Apache-2.0
import unittest

from shared.memory_schema import (
    MEMORY_SCHEMA_VERSION,
    OPERATIVE,
    PERSISTENT,
    PLAUSIBLE,
    PROJECT,
    REFUTED,
    SOURCED,
    VERIFIED,
    classify_retention,
    entry_id,
    evidence_tier,
    normalize_entry,
    validate_entry,
    validate_evidence,
    with_evidence_tier,
)

SHA = "a" * 64
PASSING_CHECK = {
    "kind": "check",
    "command": "pytest tests/test_x.py::test_y",
    "exit_code": 0,
    "output_sha256": SHA,
    "at": "2026-11-01T10:00:00Z",
}


class MemorySchemaNormalizationTests(unittest.TestCase):
    def test_normalize_maps_legacy_fields_to_canonical_envelope(self):
        entry = {
            "ts": "2026-09-19T10:00:00Z",
            "event_type": "vault_note",
            "content": "decisione registrata",
            "plugin": "omega-memory",
            "status": "active",
        }
        normalized = normalize_entry(entry)
        self.assertEqual(normalized["schema"], MEMORY_SCHEMA_VERSION)
        self.assertEqual(normalized["type"], "vault_note")
        self.assertEqual(normalized["content"], "decisione registrata")
        self.assertEqual(normalized["source"], "omega-memory")
        self.assertEqual(normalized["priority"], 3)
        self.assertTrue(normalized["id"])

    def test_normalize_derives_content_from_prompt_and_response(self):
        normalized = normalize_entry({"prompt": "domanda", "response": "risposta"})
        self.assertEqual(normalized["content"], "User: domanda\nAssistant: risposta")

    def test_normalize_clamps_priority_and_defaults_status(self):
        normalized = normalize_entry({"content": "x", "priority": 99, "status": "unknown"})
        self.assertEqual(normalized["priority"], 5)
        self.assertEqual(normalized["status"], "active")

    def test_normalize_preserves_surface(self):
        normalized = normalize_entry({"content": "x", "surface": "channel:cam4:chat"})
        self.assertEqual(normalized["surface"], "channel:cam4:chat")

    def test_entry_id_is_stable_for_equivalent_entries(self):
        first = entry_id({"content": "stessa cosa"})
        second = entry_id({"content": "stessa cosa"})
        self.assertEqual(first, second)
        self.assertEqual(entry_id({"id": "m1", "content": "x"}), "m1")


class MemorySchemaValidationTests(unittest.TestCase):
    def test_empty_content_is_invalid(self):
        self.assertTrue(validate_entry({"type": "memory"}))
        self.assertFalse(validate_entry({"type": "memory", "content": "ok"}))

    def test_unknown_type_and_status_are_reported(self):
        errors = validate_entry({"content": "x", "type": "nope", "status": "nope"})
        self.assertEqual(errors[0], "unknown type: nope")
        self.assertEqual(errors[1], "unknown status: nope")

    def test_unparseable_timestamp_is_reported(self):
        self.assertTrue(validate_entry({"content": "x", "ts": "not-a-date"}))


class MemorySchemaRetentionTests(unittest.TestCase):
    def test_persistent_by_type(self):
        self.assertEqual(classify_retention({"type": "dream_insight"}), PERSISTENT)
        self.assertEqual(classify_retention({"type": "vault_note"}), PERSISTENT)

    def test_operative_by_type(self):
        self.assertEqual(classify_retention({"type": "memory"}), OPERATIVE)
        self.assertEqual(classify_retention({"type": "task_state"}), OPERATIVE)

    def test_project_by_default(self):
        self.assertEqual(classify_retention({"type": "dream"}), PROJECT)
        self.assertEqual(classify_retention({"type": "note"}), PROJECT)

    def test_explicit_retention_overrides_type(self):
        self.assertEqual(classify_retention({"type": "memory", "retention": "persistent"}), PERSISTENT)


class MemorySchemaEvidenceTests(unittest.TestCase):
    def test_missing_or_unknown_evidence_is_plausible(self):
        self.assertEqual(evidence_tier({"content": "x"}), PLAUSIBLE)
        self.assertEqual(evidence_tier({"content": "x", "evidence": {"tier": "certo"}}), PLAUSIBLE)
        self.assertEqual(evidence_tier({"content": "x", "evidence": "verified"}), PLAUSIBLE)

    def test_claimed_tier_without_proof_is_plausible(self):
        self.assertEqual(evidence_tier({"content": "x", "evidence": {"tier": VERIFIED}}), PLAUSIBLE)
        failed = dict(PASSING_CHECK, exit_code=1)
        self.assertEqual(evidence_tier({"content": "x", "evidence": {"tier": VERIFIED, "basis": [failed]}}), PLAUSIBLE)

    def test_with_evidence_tier_labels_a_copy(self):
        entry = {"content": "x"}
        labelled = with_evidence_tier(entry)
        self.assertEqual(labelled["evidence_tier"], PLAUSIBLE)
        self.assertNotIn("evidence_tier", entry)

    def test_legacy_entry_without_evidence_stays_valid(self):
        self.assertEqual(validate_entry({"content": "x", "type": "dream_insight"}), [])

    def test_normalize_preserves_evidence(self):
        evidence = {"tier": VERIFIED, "basis": [PASSING_CHECK]}
        normalized = normalize_entry({"content": "x", "evidence": evidence})
        self.assertEqual(normalized["evidence"], evidence)
        self.assertEqual(evidence_tier(normalized), VERIFIED)

    def test_plausible_needs_no_basis(self):
        self.assertEqual(validate_evidence({"tier": PLAUSIBLE}), [])

    def test_verified_requires_a_passing_check(self):
        self.assertTrue(validate_evidence({"tier": VERIFIED}))
        self.assertEqual(validate_evidence({"tier": VERIFIED, "basis": [PASSING_CHECK]}), [])
        failed = dict(PASSING_CHECK, exit_code=1)
        errors = validate_evidence({"tier": VERIFIED, "basis": [failed]})
        self.assertTrue(any("did not pass" in error for error in errors))

    def test_check_needs_hash_and_timestamp(self):
        bad_hash = dict(PASSING_CHECK, output_sha256="abc")
        self.assertTrue(validate_evidence({"tier": VERIFIED, "basis": [bad_hash]}))
        no_time = {key: value for key, value in PASSING_CHECK.items() if key != "at"}
        self.assertTrue(validate_evidence({"tier": VERIFIED, "basis": [no_time]}))

    def test_critique_never_satisfies_a_tier(self):
        critique = {"kind": "critique", "by": "omen:granite", "content": "confermo"}
        errors = validate_evidence({"tier": VERIFIED, "basis": [critique]})
        self.assertTrue(any("requires a valid basis" in error for error in errors))
        self.assertEqual(validate_evidence({"tier": PLAUSIBLE, "basis": [critique]}), [])

    def test_sourced_accepts_hashed_source_or_review_with_sources(self):
        source = {"kind": "source", "ref": "https://example.org/doc", "content_sha256": SHA}
        self.assertEqual(validate_evidence({"tier": SOURCED, "basis": [source]}), [])
        review = {"kind": "review", "by": "operatore", "sources": ["memory-1"]}
        self.assertEqual(validate_evidence({"tier": SOURCED, "basis": [review]}), [])

    def test_review_without_sources_does_not_make_sourced(self):
        review = {"kind": "review", "by": "operatore", "sources": []}
        self.assertTrue(validate_evidence({"tier": SOURCED, "basis": [review]}))

    def test_refuted_requires_a_reason(self):
        self.assertTrue(validate_evidence({"tier": REFUTED}))
        refutation = {"kind": "refutation", "reason": "il test contrario fallisce"}
        self.assertEqual(validate_evidence({"tier": REFUTED, "basis": [refutation]}), [])

    def test_validate_entry_reports_evidence_errors(self):
        errors = validate_entry({"content": "x", "evidence": {"tier": "certo"}})
        self.assertEqual(errors, ["unknown evidence tier: certo"])


if __name__ == "__main__":
    unittest.main()
