# SPDX-License-Identifier: Apache-2.0
"""Coda SQLite della pubblicazione social: stato operativo, non contenuto.

I contenuti restano nel diario e nel feed; qui vive lo stato di ogni invio:
quando può partire, cosa è successo, se serve review. Scritta dal control-plane
e letta da dashboard/CLI: SQLite (stesso DB del CP, `shared/db.py`) per claim
atomici, idempotenza e conteggi. Un invio interrotto dopo `publishing` è esito
incerto: si recupera come `needs_review`, mai ritentato alla cieca (stessa
regola di `shared/instagram_outbox.py`).
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from shared import db as _db

STATI = ("scheduled", "publishing", "published", "needs_review",
         "cancelled", "rejected", "dry_run")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS social_queue (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id          TEXT UNIQUE NOT NULL,
    content_id       TEXT NOT NULL,
    canale           TEXT NOT NULL,
    tipo             TEXT NOT NULL,
    persona          TEXT NOT NULL,
    testo            TEXT NOT NULL,
    caption          TEXT DEFAULT '',
    media_path       TEXT DEFAULT '',
    image_url        TEXT DEFAULT '',
    idempotency_key  TEXT UNIQUE NOT NULL,
    status           TEXT NOT NULL DEFAULT 'scheduled',
    publish_after    REAL NOT NULL,
    attempts         INTEGER NOT NULL DEFAULT 0,
    reviewer         TEXT NOT NULL DEFAULT 'auto',
    dry_run          INTEGER NOT NULL DEFAULT 0,
    error            TEXT DEFAULT '',
    remote_id        TEXT DEFAULT '',
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_social_queue_status ON social_queue(status);
CREATE INDEX IF NOT EXISTS idx_social_queue_due    ON social_queue(publish_after);
"""


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def idempotency_key(content_id: str, canale: str, testo: str,
                    media_path: str = "") -> str:
    """L'identità dell'invio: stesso contenuto, stesso canale, stesso hash."""
    blob = "\x1f".join([str(content_id or ""), str(canale or ""),
                        " ".join(str(testo or "").split()), str(media_path or "")])
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class SocialQueue:
    """La coda degli invii social, con claim atomici e recupero esito incerto."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or _db.DB_PATH
        self._lock = threading.RLock()
        self._init()

    @contextmanager
    def _open(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        con = sqlite3.connect(self.db_path, timeout=30.0)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout = 30000")
        con.execute("PRAGMA mmap_size = 0")
        con.execute("PRAGMA journal_mode = DELETE")
        con.execute("PRAGMA synchronous = FULL")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def _init(self):
        with self._lock, self._open() as con:
            con.executescript(_SCHEMA)
            con.execute("UPDATE social_queue SET status='needs_review', "
                        "error='invio interrotto: esito incerto', updated_at=? "
                        "WHERE status='publishing'", (_stamp(),))

    def enqueue(self, *, item_id, content_id, canale, tipo, persona, testo,
                caption="", media_path="", image_url="", publish_after,
                reviewer="auto", dry_run=False) -> tuple[str, str]:
        """(item_id, motivo) — deduplicato per idempotency_key."""
        if not item_id or not content_id or not canale or not tipo:
            return "", "campi obbligatori mancanti"
        key = idempotency_key(content_id, canale, testo, media_path)
        adesso = _stamp()
        with self._lock, self._open() as con:
            gia = con.execute("SELECT item_id, status FROM social_queue "
                              "WHERE idempotency_key=?", (key,)).fetchone()
            if gia:
                return str(gia["item_id"]), f"già in coda ({gia['status']})"
            con.execute(
                "INSERT INTO social_queue (item_id, content_id, canale, tipo, "
                "persona, testo, caption, media_path, image_url, idempotency_key, "
                "status, publish_after, reviewer, dry_run, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,'scheduled',?,?,?,?,?)",
                (item_id, content_id, canale, tipo, persona, testo[:4000],
                 caption[:2200], media_path, image_url, key, float(publish_after),
                 reviewer, 1 if dry_run else 0, adesso, adesso))
        return item_id, ""

    def claim_due(self, adesso: float) -> dict | None:
        with self._lock, self._open() as con:
            row = con.execute("SELECT * FROM social_queue WHERE status='scheduled' "
                              "AND publish_after<=? ORDER BY publish_after, id LIMIT 1",
                              (float(adesso),)).fetchone()
            if row is None:
                return None
            cur = con.execute("UPDATE social_queue SET status='publishing', "
                              "updated_at=? WHERE item_id=? AND status='scheduled'",
                              (_stamp(), row["item_id"]))
            return dict(row) if cur.rowcount == 1 else None

    def _transizione(self, item_id, *, da=None, a, remote_id="", error="",
                     publish_after=None, attempts=None) -> bool:
        with self._lock, self._open() as con:
            campi, valori = ["status=?", "updated_at=?"], [a, _stamp()]
            if remote_id:
                campi.append("remote_id=?")
                valori.append(remote_id[:128])
            if error:
                campi.append("error=?")
                valori.append(error[:300])
            if publish_after is not None:
                campi.append("publish_after=?")
                valori.append(float(publish_after))
            if attempts is not None:
                campi.append("attempts=?")
                valori.append(int(attempts))
            query = "UPDATE social_queue SET " + ", ".join(campi) + " WHERE item_id=?"
            valori.append(item_id)
            if da:
                query += " AND status=?"
                valori.append(da)
            return con.execute(query, valori).rowcount == 1

    def mark_published(self, item_id, remote_id="") -> bool:
        return self._transizione(item_id, da="publishing", a="published",
                                 remote_id=remote_id, error="")

    def mark_dry_run(self, item_id) -> bool:
        return self._transizione(item_id, da="publishing", a="dry_run", error="")

    def mark_needs_review(self, item_id, error) -> bool:
        return self._transizione(item_id, da="publishing", a="needs_review", error=error)

    def reschedule(self, item_id, publish_after, error="") -> bool:
        with self._lock, self._open() as con:
            row = con.execute("SELECT attempts FROM social_queue WHERE item_id=?",
                              (item_id,)).fetchone()
            tentativi = 0 if row is None else int(row["attempts"]) + 1
        return self._transizione(item_id, da="publishing", a="scheduled",
                                 publish_after=float(publish_after), error=error,
                                 attempts=tentativi)

    def _terminale(self, item_id, a, reviewer, reason) -> bool:
        with self._lock, self._open() as con:
            con.execute("UPDATE social_queue SET reviewer=? WHERE item_id=?",
                        (reviewer[:64], item_id))
        return self._transizione(item_id, da="scheduled", a=a, error=reason)

    def cancel(self, item_id, reviewer="operator", reason="") -> bool:
        return self._terminale(item_id, "cancelled", reviewer, reason)

    def reject(self, item_id, reviewer="operator", reason="") -> bool:
        return self._terminale(item_id, "rejected", reviewer, reason)

    def get(self, item_id) -> dict | None:
        with self._lock, self._open() as con:
            row = con.execute("SELECT * FROM social_queue WHERE item_id=?",
                              (item_id,)).fetchone()
        return dict(row) if row else None

    def list(self, *, status=None, canale=None, limit=200) -> list[dict]:
        query, where, valori = "SELECT * FROM social_queue", [], []
        if status:
            where.append("status=?")
            valori.append(status)
        if canale:
            where.append("canale=?")
            valori.append(canale)
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY id DESC LIMIT ?"
        valori.append(max(0, int(limit)))
        with self._lock, self._open() as con:
            rows = con.execute(query, valori).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        with self._lock, self._open() as con:
            rows = con.execute("SELECT status, COUNT(*) AS n FROM social_queue "
                               "GROUP BY status").fetchall()
            due = con.execute("SELECT COUNT(*) AS n FROM social_queue WHERE "
                              "status='scheduled' AND publish_after<=?",
                              (datetime.now(timezone.utc).timestamp(),)).fetchone()
        conteggi = {s: 0 for s in STATI}
        for r in rows:
            conteggi[r["status"]] = int(r["n"])
        return {"counts": conteggi, "due_now": int(due["n"] if due else 0)}
