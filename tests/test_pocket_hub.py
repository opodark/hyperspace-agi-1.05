# SPDX-License-Identifier: Apache-2.0
"""Pocket Hub: registro a sola aggiunta e servizio di failover (node/pocket_hub.py)."""

import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).parents[1]
for p in (ROOT, ROOT / "node"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from fastapi.testclient import TestClient  # noqa: E402

from node.pocket_hub import PocketHub, create_app  # noqa: E402
from shared.pocket_hub_guard import PocketHubGuard, PocketHubState  # noqa: E402
from shared.pocket_hub_outbox import Outbox  # noqa: E402


# ── Outbox ───────────────────────────────────────────────────────────────────
def test_outbox_flush_in_order_and_compacts(tmp_path):
    ob = Outbox(tmp_path)
    ids = [ob.append("chat", {"n": i}) for i in range(3)]
    seen = []
    res = ob.flush(lambda e: seen.append(e["id"]) or True)
    assert seen == ids and res == {"sent": 3, "remaining": 0}
    assert not (tmp_path / "outbox.ndjson").exists()  # tutto confermato: si ripulisce


def test_outbox_stops_at_first_failure_and_resumes(tmp_path):
    ob = Outbox(tmp_path)
    ids = [ob.append("chat", {"n": i}) for i in range(4)]
    calls = {"n": 0}

    def flaky(entry):
        calls["n"] += 1
        return calls["n"] <= 2  # il CP cade alla terza

    assert ob.flush(flaky) == {"sent": 2, "remaining": 2}
    # riavvio simulato: nuovo oggetto sulla stessa directory
    again = []
    res = Outbox(tmp_path).flush(lambda e: again.append(e["id"]) or True)
    assert again == ids[2:] and res["remaining"] == 0


def test_outbox_survives_truncated_line(tmp_path):
    ob = Outbox(tmp_path)
    ob.append("state", {"to": "active_failover"})
    with open(tmp_path / "outbox.ndjson", "a") as fh:
        fh.write('{"id": "rotta", "ts"')  # crash a metà scrittura
    assert len(ob.pending()) == 1


def test_outbox_cap_drops_oldest_and_says_so(tmp_path):
    ob = Outbox(tmp_path, max_pending=10)
    for i in range(14):
        ob.append("chat", {"n": i})
    pend = ob.pending()
    assert pend[0]["kind"] == "outbox_overflow" and pend[0]["data"]["dropped"] == 4
    assert len(pend) == 11


# ── Hub ──────────────────────────────────────────────────────────────────────
def make_hub(tmp_path):
    guard = PocketHubGuard(primary_cp_url="http://cp.test", enabled=True, failover_threshold_misses=3,
                           recovery_threshold_hits=2)
    return PocketHub(guard, Outbox(tmp_path), node_id="s24", ollama_url="http://ollama.test")


def test_standby_refuses_hub_endpoints_but_health_answers(tmp_path):
    hub = make_hub(tmp_path)
    hub.guard.tick(force_probe_result=True)
    c = TestClient(create_app(hub))
    assert c.get("/health").json()["state"] == "standby"
    assert c.get("/nodes/active").status_code == 503
    assert c.post("/mesh/announce", json={"node_id": "x"}).status_code == 503
    assert c.post("/v1/chat/completions", json={"messages": []}).status_code == 503


def test_failover_registry_and_single_announce_event(tmp_path):
    hub = make_hub(tmp_path)
    for _ in range(3):
        hub.guard.tick(force_probe_result=False)
    assert hub.guard.state == PocketHubState.ACTIVE_FAILOVER
    c = TestClient(create_app(hub))
    for _ in range(3):  # heartbeat ripetuti: un solo evento nel registro
        assert c.post("/mesh/announce", json={"node_id": "omen", "endpoint": "http://o:1"}).json()["ok"]
    assert [n["node_id"] for n in c.get("/nodes/active").json()] == ["omen"]
    kinds = [e["kind"] for e in hub.outbox.pending()]
    assert kinds.count("announce") == 1 and kinds.count("state") == 1


def test_chat_in_failover_is_forwarded_and_logged(tmp_path, monkeypatch):
    hub = make_hub(tmp_path)
    for _ in range(3):
        hub.guard.tick(force_probe_result=False)
    sent = {}

    async def fake_get(self, url, **kw):
        return httpx.Response(200, json={"models": [{"name": "qwen3:4b"}]}, request=httpx.Request("GET", url))

    async def fake_post(self, url, json=None, **kw):
        sent["body"] = json
        return httpx.Response(200, request=httpx.Request("POST", url),
                              json={"choices": [{"message": {"role": "assistant", "content": "ciao, sono qui"}}]})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    c = TestClient(create_app(hub))
    r = c.post("/v1/chat/completions", json={"model": "grande:70b", "stream": True,
                                             "messages": [{"role": "user", "content": "ci sei?"}]})
    assert r.status_code == 200
    assert sent["body"]["model"] == "qwen3:4b"          # il modello che il telefono ha davvero
    assert sent["body"]["stream"] is False
    assert sent["body"]["messages"][0]["role"] == "system"  # prompt di emergenza
    chat = [e for e in hub.outbox.pending() if e["kind"] == "chat"][0]
    assert chat["data"]["prompt"] == "ci sei?" and chat["data"]["response"] == "ciao, sono qui"


def test_flush_only_when_primary_answers_and_uses_memory_push(tmp_path, monkeypatch):
    hub = make_hub(tmp_path)
    hub.outbox.append("chat", {"model": "m", "prompt": "p", "response": "r"})
    posted = []

    def fake_post(url, json=None, **kw):
        posted.append((url, json))
        return httpx.Response(200, json={"ok": True}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    for _ in range(3):
        hub.guard.tick(force_probe_result=False)
    posted.clear()
    assert hub.flush()["sent"] == 0 and not posted       # CP ancora giù: non si prova nemmeno
    hub.guard.tick(force_probe_result=True)
    res = hub.flush()
    assert res["sent"] >= 1
    url, payload = posted[0]
    assert url == "http://cp.test/memory/push" and payload["node_id"] == "s24"
    assert payload["entry"]["source"] == "pocket_hub" and payload["entry"]["interaction_id"]


def test_flush_keeps_entries_when_cp_returns_error(tmp_path, monkeypatch):
    hub = make_hub(tmp_path)
    hub.outbox.append("chat", {"prompt": "p", "response": "r"})
    hub.guard.tick(force_probe_result=True)
    monkeypatch.setattr(httpx, "post", lambda url, **kw: httpx.Response(503, request=httpx.Request("POST", url)))
    assert hub.flush() == {"sent": 0, "remaining": 1}


def test_single_missed_probe_does_not_make_phone_serve(tmp_path):
    """Sostituire il CP è l'eccezione: un controllo andato male non deve bastare."""
    hub = make_hub(tmp_path)
    hub.guard.tick(force_probe_result=False)
    assert hub.guard.state == PocketHubState.STANDBY and not hub.serving()
    c = TestClient(create_app(hub))
    assert c.post("/v1/chat/completions", json={"messages": []}).status_code == 503
    for _ in range(2):
        hub.guard.tick(force_probe_result=False)
    assert hub.serving()
