# SPDX-License-Identifier: Apache-2.0
"""La coda social: claim atomici, idempotenza, recupero dell'esito incerto."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.social_queue import SocialQueue  # noqa: E402


def queue(tmp_path):
    return SocialQueue(str(tmp_path / "social.db"))


def voce_item(**overrides):
    base = dict(item_id="sogno-abc:instagram", content_id="sogno-abc",
                canale="instagram", tipo="sogno", persona="anna",
                testo="un sogno", caption="🌙 Sogno di Anna\n\nun sogno\n\n#AIDreams",
                publish_after=time.time() - 1)
    base.update(overrides)
    return base


def test_enqueue_claim_publish_roundtrip(tmp_path):
    q = queue(tmp_path)
    item_id, motivo = q.enqueue(**voce_item())
    assert motivo == ""
    item = q.claim_due(time.time())
    assert item and item["item_id"] == item_id
    assert q.get(item_id)["status"] == "publishing"
    assert q.mark_published(item_id, remote_id="media-1")
    riga = q.get(item_id)
    assert riga["status"] == "published"
    assert riga["remote_id"] == "media-1"


def test_enqueue_e_idempotente(tmp_path):
    q = queue(tmp_path)
    primo, _ = q.enqueue(**voce_item())
    secondo, motivo = q.enqueue(**voce_item())
    assert primo == secondo
    assert "già in coda" in motivo
    assert len(q.list()) == 1


def test_claim_rispetta_il_publish_after_futuro(tmp_path):
    q = queue(tmp_path)
    q.enqueue(**voce_item(publish_after=time.time() + 3600))
    assert q.claim_due(time.time()) is None


def test_interrupted_publish_recovers_as_needs_review(tmp_path):
    q = queue(tmp_path)
    item_id, _ = q.enqueue(**voce_item())
    q.claim_due(time.time())
    q2 = queue(tmp_path)  # simula un crash senza mark_published
    assert q2.get(item_id)["status"] == "needs_review"


def test_reschedule_restores_scheduled_and_counts_attempt(tmp_path):
    q = queue(tmp_path)
    item_id, _ = q.enqueue(**voce_item())
    q.claim_due(time.time())
    assert q.reschedule(item_id, time.time() + 60, error="429")
    riga = q.get(item_id)
    assert riga["status"] == "scheduled"
    assert riga["attempts"] == 1


def test_cancel_and_reject_are_terminal(tmp_path):
    q = queue(tmp_path)
    item_id, _ = q.enqueue(**voce_item())
    assert q.cancel(item_id, reviewer="operatore", reason="doppione")
    assert q.get(item_id)["status"] == "cancelled"
    altro, _ = q.enqueue(**voce_item(item_id="x:ig", content_id="x"))
    assert q.reject(altro, reason="non adatto")
    assert q.get(altro)["status"] == "rejected"


def test_dry_run_is_terminal_without_remote_id(tmp_path):
    q = queue(tmp_path)
    item_id, _ = q.enqueue(**voce_item(dry_run=True))
    q.claim_due(time.time())
    assert q.mark_dry_run(item_id)
    riga = q.get(item_id)
    assert riga["status"] == "dry_run"
    assert riga["remote_id"] == ""


def test_stats_counts_and_due_now(tmp_path):
    q = queue(tmp_path)
    q.enqueue(**voce_item())
    s = q.stats()
    assert s["counts"]["scheduled"] == 1
    assert s["due_now"] == 1
