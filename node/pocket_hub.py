# SPDX-License-Identifier: Apache-2.0
"""Pocket Hub: il telefono come control-plane di riserva.

Collega `shared/pocket_hub_guard.py` (macchina a stati) a un piccolo servizio:

  - sorveglia il CP principale (`POCKET_HUB_PRIMARY_CP`, di norma il Mac);
  - quando il CP non risponde (promosso dopo N mancate risposte) serve il minimo:
        GET  /nodes/active            registro dei nodi che si annunciano
        POST /mesh/announce           annuncio/heartbeat dei peer
        POST /v1/chat/completions     chat, inoltrata all'Ollama del telefono
  - scrive in un registro a sola aggiunta (`shared/pocket_hub_outbox.py`) le
    transizioni, gli annunci e le conversazioni avvenute nel frattempo;
  - quando il CP torna, riconsegna il registro a `POST /memory/push`, da dove
    entra in Hermes. Una voce è considerata spedita solo se il CP risponde 2xx.

In STANDBY (e finché il primario non è fuori da N controlli di fila) questi endpoint rispondono 503: il telefono non si finge hub quando il
primario funziona. `/health` e `/pocket/status` rispondono sempre.

Avvio (lo fa `00mesh start` con POCKET_HUB_ENABLED=true):
    uvicorn pocket_hub:create_app --factory --host <ip-tailscale> --port 8086

Limiti dichiarati: il modello è quello piccolo del telefono (non la persona
completa del CP: Anna qui ha solo un prompt di emergenza); i peer devono avere
l'URL del telefono come fallback per trovarlo; il traffico è fidato perché sta
sulla tailnet, come per il resto della mesh.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.pocket_hub_guard import PocketHubGuard, PocketHubState  # noqa: E402
from shared.pocket_hub_outbox import Outbox  # noqa: E402

logger = logging.getLogger("hyperspace.pocket_hub")

EMERGENCY_SYSTEM = (
    "Sei Anna, in console di debug d'emergenza sul telefono: il control-plane principale "
    "è irraggiungibile e hai un modello piccolo, senza la tua memoria completa. Serve a "
    "capire cosa è successo e a rimettere in piedi la mesh, non a sostituirla. Sii onesta "
    "sui tuoi limiti, breve e concreta. Tutto quello che ci diciamo qui verrà riconsegnato "
    "alla memoria quando il Mac torna."
)


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


class PocketHub:
    def __init__(
        self,
        guard: PocketHubGuard,
        outbox: Outbox,
        *,
        node_id: str = "pocket-hub",
        node_tier: str = "mobile",
        ollama_url: str = "http://127.0.0.1:11434",
        model: str = "",
        flush_interval_s: float = 60.0,
    ) -> None:
        self.guard = guard
        self.outbox = outbox
        self.node_id = node_id
        self.node_tier = node_tier
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model
        self.flush_interval_s = flush_interval_s
        self.registry: Dict[str, Dict[str, Any]] = {}
        self._announced: set = set()  # un solo evento per nodo ed episodio di failover
        self._flush_lock = threading.Lock()
        self._stop = threading.Event()
        self._flusher: Optional[threading.Thread] = None
        guard.on_state_change = self._on_state_change

    # ── stato ────────────────────────────────────────────────────────────
    def serving(self) -> bool:
        """Solo quando il telefono è davvero hub attivo (CP giù per N controlli di fila).
        Sostituire il CP è l'eccezione: un controllo andato male non basta."""
        return bool(self.guard.snapshot()["is_active_hub"])

    def _on_state_change(self, old: PocketHubState, new: PocketHubState) -> None:
        self.outbox.append("state", {"from": old.value, "to": new.value})
        if new == PocketHubState.ACTIVE_FAILOVER:
            self._announced.clear()
        elif new in (PocketHubState.RECOVERING, PocketHubState.STANDBY):
            threading.Thread(target=self.flush, daemon=True).start()

    # ── riconsegna a Hermes (via CP) ─────────────────────────────────────
    def _entry_for(self, item: Dict[str, Any]) -> Dict[str, Any]:
        data = item.get("data", {})
        base = {
            "interaction_id": item["id"],
            "ts": _iso(item["ts"]),
            "node_id": self.node_id,
            "node_tier": self.node_tier,
            "source": "pocket_hub",
        }
        if item.get("kind") == "chat":
            return {**base, "model": data.get("model", ""), "prompt": data.get("prompt", ""),
                    "response": str(data.get("response", ""))[:2000]}
        return {**base, "model": "", "prompt": f"[pocket_hub:{item.get('kind')}]",
                "response": json.dumps(data, ensure_ascii=False)[:2000]}

    def _send(self, item: Dict[str, Any]) -> bool:
        base = self.guard.primary_cp_url
        if not base:
            return False
        r = httpx.post(f"{base}/memory/push", timeout=10.0,
                       json={"node_id": self.node_id, "entry": self._entry_for(item)})
        return 200 <= r.status_code < 300

    def flush(self) -> Dict[str, int]:
        """Una sola riconsegna alla volta; solo se il primario risponde adesso."""
        if not self._flush_lock.acquire(blocking=False):
            return {"sent": 0, "remaining": self.outbox.stats()["pending"]}
        try:
            if self.guard.snapshot()["last_probe_ok"] is not True:
                return {"sent": 0, "remaining": self.outbox.stats()["pending"]}
            res = self.outbox.flush(self._send)
            if res["sent"]:
                logger.info("[PocketHub] riconsegnate %d voci, ne restano %d", res["sent"], res["remaining"])
            return res
        finally:
            self._flush_lock.release()

    def _flush_loop(self) -> None:
        while not self._stop.wait(self.flush_interval_s):
            try:
                if self.outbox.stats()["pending"]:
                    self.flush()
            except Exception:  # un giro andato male non ferma il successivo
                logger.exception("[PocketHub] errore nel giro di riconsegna")

    def start(self) -> None:
        self.guard.start_watchdog()
        self._flusher = threading.Thread(target=self._flush_loop, daemon=True)
        self._flusher.start()

    def stop(self) -> None:
        self._stop.set()
        self.guard.stop_watchdog()

    # ── chat ─────────────────────────────────────────────────────────────
    async def pick_model(self, client: httpx.AsyncClient, wanted: str) -> str:
        if self.model:
            return self.model
        try:
            tags = (await client.get(f"{self.ollama_url}/api/tags", timeout=5.0)).json()
            names = [m["name"] for m in tags.get("models", [])]
        except Exception:
            names = []
        if wanted in names:
            return wanted
        return names[0] if names else wanted


def create_app(hub: Optional[PocketHub] = None) -> FastAPI:
    if hub is None:
        hub = hub_from_env()
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        hub.start()
        try:
            yield
        finally:
            hub.stop()

    app = FastAPI(title="HyperSpace Pocket Hub", version="1.0.0", lifespan=lifespan)
    app.state.hub = hub

    def standby() -> JSONResponse:
        return JSONResponse({"error": "standby", "detail": "il control-plane principale risponde"}, status_code=503)

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {"ok": True, "role": "pocket_hub", "state": hub.guard.snapshot()["state"]}

    @app.get("/pocket/status")
    def status() -> Dict[str, Any]:
        return {**hub.guard.snapshot(), "serving": hub.serving(), "outbox": hub.outbox.stats(),
                "registry_nodes": len(hub.registry)}

    @app.post("/pocket/flush")
    def flush_now() -> Dict[str, int]:
        return hub.flush()

    @app.get("/nodes/active")
    def nodes_active():
        if not hub.serving():
            return standby()
        return [n for n in hub.registry.values() if n.get("status") == "active"]

    @app.post("/mesh/announce")
    async def announce(request: Request):
        if not hub.serving():
            return standby()
        data = await request.json()
        nid = str(data.get("node_id", ""))
        if not nid:
            return JSONResponse({"ok": False, "error": "missing node_id"}, status_code=400)
        hub.registry[nid] = {**data, "status": "active",
                             "last_seen": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        if nid not in hub._announced:
            hub._announced.add(nid)
            hub.outbox.append("announce", {"node_id": nid, "endpoint": str(data.get("endpoint", ""))})
        return {"ok": True, "hub": "pocket"}

    @app.post("/v1/chat/completions")
    async def chat(request: Request):
        if not hub.serving():
            return standby()
        body = await request.json()
        body["stream"] = False  # un'unica risposta: semplice da registrare e da inoltrare
        messages = list(body.get("messages") or [])
        if not any(m.get("role") == "system" for m in messages):
            messages.insert(0, {"role": "system", "content": os.getenv("POCKET_HUB_SYSTEM", EMERGENCY_SYSTEM)})
        body["messages"] = messages
        async with httpx.AsyncClient(timeout=300.0) as client:
            body["model"] = await hub.pick_model(client, str(body.get("model", "")))
            try:
                r = await client.post(f"{hub.ollama_url}/v1/chat/completions", json=body)
            except httpx.HTTPError as exc:
                return JSONResponse({"error": f"Ollama del telefono non raggiungibile: {exc}"}, status_code=502)
        if r.status_code >= 400:
            return JSONResponse({"error": r.text[:400]}, status_code=r.status_code)
        out = r.json()
        try:
            reply = out["choices"][0]["message"].get("content") or ""
            prompt = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
            hub.outbox.append("chat", {"model": body["model"], "prompt": str(prompt)[:4000], "response": reply})
        except (KeyError, IndexError, TypeError):
            pass  # risposta senza testo (es. solo tool_call): niente da registrare
        return out

    return app


def hub_from_env() -> PocketHub:
    primary = os.getenv("POCKET_HUB_PRIMARY_CP") or os.getenv("CONTROL_PLANE_URL", "")
    guard = PocketHubGuard(
        primary_cp_url=primary,
        enabled=True,
        check_interval_s=float(os.getenv("POCKET_HUB_CHECK_S", "30")),
        failover_threshold_misses=int(os.getenv("POCKET_HUB_MISSES", "3")),
    )
    outbox = Outbox(os.getenv("POCKET_HUB_DIR") or Path.home() / ".00mesh" / "pocket_hub")
    return PocketHub(
        guard, outbox,
        node_id=os.getenv("NODE_ID", "pocket-hub"),
        node_tier=os.getenv("NODE_TIER", "mobile"),
        ollama_url=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
        model=os.getenv("POCKET_HUB_MODEL", ""),
    )
