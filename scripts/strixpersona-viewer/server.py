# SPDX-License-Identifier: Apache-2.0
# Rotte e modello di sicurezza (bundle statico + token/cookie di sessione) ispirati
# a usestrix/strix, strix/interface/viewer/server.py (Copyright 2025 OmniSecure Inc.,
# Apache-2.0 — vedi LICENSE-strix-viewer-upstream.txt). Stesso bundle SPA, stessi nomi
# di rotta che il frontend già chiama; dietro non c'è più il motore di Strix ma il
# nostro CP + persona, e niente email/OTP/telemetria/relay di report: quelle rotte
# rispondono 404, il frontend le usa solo su un click esplicito che qui non arriva mai.
"""Server locale, solo stdlib: serve la SPA di Strix e le rotte /api/* a cui attinge,
con dietro la nostra `TuiLiveView` pilotata dal vivo dal driver persona+shell."""

from __future__ import annotations

import json
import logging
import mimetypes
import secrets
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urlsplit

logger = logging.getLogger("strixpersona.viewer")

STATIC_DIR = Path(__file__).resolve().parent / "static"
SESSION_COOKIE_PREFIX = "strixpersona_viewer_session"


class ViewerState:
    """Stato condiviso fra il driver (thread persona+shell) e l'HTTP server.

    `lock` protegge le letture/scritture di `live_view`, `run_record` e del
    turno di conferma in sospeso (`pending_confirm`). `confirm_event` è il
    semaforo con cui `/api/agents/steer` sveglia il driver fermo in attesa.
    """

    def __init__(self, live_view, run_record: dict[str, Any]) -> None:
        self.lock = threading.RLock()
        self.live_view = live_view
        self.run_record = run_record
        self.pending_confirm: dict[str, Any] | None = None
        self.confirm_event = threading.Event()
        self.confirm_answer: bool | None = None
        self.session_token = secrets.token_urlsafe(32)
        self.cookie_name = SESSION_COOKIE_PREFIX

    def ask_confirmation(self, agent_id: str, command: str, explanation: str) -> bool:
        """Chiamato dal driver: espone il comando in sospeso e aspetta la risposta
        dell'operatore via /api/agents/steer (il box 'Send a live prompt' del
        frontend). Ritorna True/False; False anche allo scadere del timeout."""
        with self.lock:
            self.pending_confirm = {"agent_id": agent_id, "command": command,
                                    "explanation": explanation}
            self.confirm_event.clear()
            self.confirm_answer = None
        got = self.confirm_event.wait(timeout=600)
        with self.lock:
            self.pending_confirm = None
            answer = self.confirm_answer if got else False
        return bool(answer)

    def steer(self, message: str) -> bool:
        """POST /api/agents/steer: interpreta il messaggio come risposta sì/no
        se c'è una conferma in sospeso. Un messaggio fuori contesto è ignorato
        (torna False, 'not_delivered', coerente col contratto del frontend)."""
        with self.lock:
            if self.pending_confirm is None:
                return False
            testo = message.strip().lower()
            self.confirm_answer = testo in ("si", "sì", "s", "yes", "y", "ok", "esegui", "e")
            self.confirm_event.set()
            return True


def _make_handler(state: ViewerState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "StrixpersonaViewer/0.1"

        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A002
            logger.debug("%s - %s", self.address_string(), fmt % args)

        def do_GET(self) -> None:
            parts = urlsplit(self.path)
            try:
                if parts.path.startswith("/api/"):
                    self._handle_api(parts.path, parse_qs(parts.query))
                else:
                    self._handle_static(parts.path, parse_qs(parts.query))
            except BrokenPipeError:
                pass
            except Exception:
                logger.exception("richiesta fallita: %s", parts.path)
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal error"})

        def do_POST(self) -> None:
            path = urlsplit(self.path).path
            try:
                if path == "/api/agents/steer":
                    self._handle_steer()
                else:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})
            except BrokenPipeError:
                pass
            except Exception:
                logger.exception("richiesta fallita: POST %s", path)
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal error"})

        # ── /api/* ────────────────────────────────────────────────────────
        def _handle_api(self, path: str, query: dict[str, list[str]]) -> None:
            if path == "/api/capabilities":
                self._json(HTTPStatus.OK, {"can_steer": True})
                return
            if path == "/api/auth/status":
                # Non blocca mai il run live: la verifica serve solo allo storico.
                self._json(HTTPStatus.OK, {"verified": False, "email": None})
                return
            if path == "/api/runs":
                self._json(HTTPStatus.OK, {"locked": True, "count": 1, "runs": []})
                return
            if not self._has_session():
                self._json(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
                return
            if path == "/api/run":
                with state.lock:
                    self._json(HTTPStatus.OK, dict(state.run_record))
                return
            if path == "/api/transcript":
                with state.lock:
                    payload = {"agents": list(state.live_view.agents.values()),
                              "events": list(state.live_view.events)}
                self._json(HTTPStatus.OK, payload)
                return
            if path == "/api/vulnerabilities":
                self._json(HTTPStatus.OK, [])  # non facciamo report di vulnerabilità
                return
            if path == "/api/report":
                self._json(HTTPStatus.OK, {"markdown": ""})
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})

        def _handle_steer(self) -> None:
            if not self._has_session():
                self._json(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
                return
            body = self._read_body()
            message = body.get("message")
            if not isinstance(message, str) or not message.strip():
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_message"})
                return
            delivered = state.steer(message)
            self._json(HTTPStatus.OK, {"ok": delivered})

        # ── file statici + sessione ──────────────────────────────────────
        def _has_session(self) -> bool:
            supplied = self._cookies().get(state.cookie_name, "")
            return bool(supplied) and secrets.compare_digest(supplied, state.session_token)

        def _token_presented(self, query: dict[str, list[str]]) -> bool:
            supplied = (query.get("token") or [""])[0]
            return bool(supplied) and secrets.compare_digest(supplied, state.session_token)

        def _cookies(self) -> dict[str, str]:
            jar: dict[str, str] = {}
            for chunk in (self.headers.get("Cookie") or "").split(";"):
                name, sep, value = chunk.strip().partition("=")
                if sep:
                    jar[name] = value
            return jar

        def _handle_static(self, path: str, query: dict[str, list[str]]) -> None:
            target = self._resolve_asset(path)
            if target is None:
                target = STATIC_DIR / "index.html"  # fallback SPA
            is_index = target.name == "index.html"
            if not target.is_file():
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            content = target.read_bytes()
            content_type, _ = mimetypes.guess_type(str(target))
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            if is_index and self._token_presented(query):
                self.send_header(
                    "Set-Cookie",
                    f"{state.cookie_name}={state.session_token}; Path=/; HttpOnly; SameSite=Strict",
                )
            self.end_headers()
            self.wfile.write(content)

        def _resolve_asset(self, path: str) -> Path | None:
            rel = unquote(path).lstrip("/")
            if not rel or rel.endswith("/"):
                return None
            root = STATIC_DIR.resolve()
            candidate = (root / rel).resolve()
            if root != candidate and root not in candidate.parents:
                logger.warning("tentativo di traversal rifiutato: %s", path)
                return None
            return candidate if candidate.is_file() else None

        def _read_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return {}
            return body if isinstance(body, dict) else {}

        def _json(self, status: HTTPStatus, payload: Any) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def authorized_url(base_url: str, token: str) -> str:
    return f"{base_url}/?{urlencode({'token': token})}"


def serve(state: ViewerState, *, host: str = "127.0.0.1", port: int = 0,
         open_browser: bool = True) -> tuple[ThreadingHTTPServer, str]:
    handler = _make_handler(state)
    httpd = ThreadingHTTPServer((host, port), handler)
    httpd.daemon_threads = True
    bound_port = int(httpd.server_address[1])
    state.cookie_name = f"{SESSION_COOKIE_PREFIX}_{bound_port}"
    url = f"http://{host}:{bound_port}"
    thread = threading.Thread(target=httpd.serve_forever, name="strixpersona-viewer", daemon=True)
    thread.start()
    link = authorized_url(url, state.session_token)
    if open_browser:
        try:
            webbrowser.open(link)
        except Exception:
            logger.debug("impossibile aprire il browser", exc_info=True)
    return httpd, link
