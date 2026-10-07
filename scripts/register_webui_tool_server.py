# SPDX-License-Identifier: Apache-2.0
"""Upsert the HyperSpace OpenAPI connection into Open WebUI's persistent config.

This runs before WebUI starts because its saved ConfigVar otherwise overrides
TOOL_SERVER_CONNECTIONS from the environment on existing installations.
"""

import json
import hashlib
import os
import sqlite3
import sys
import time
from pathlib import Path


KEY = "tool_server.connections"
BANNER_KEY = "ui.banners"
BANNER_ID = "hyperspace-activity"
ID = "hyperspace-files"
FILTER_ID = "anna_tool_filter"
PIPE_ID = "anna_batch_direct"
LEGACY_FILTER_SHA256 = "be9f5cd156aaabda2b13a0e8ec03d74dcb781bdc4a169242fb917730c0452564"
MANAGED_MARKER = "# Managed by HyperSpace webui-tools-register."


def connection(token):
    if len(token) < 32:
        raise ValueError("WEBUI_TOOLS_TOKEN deve avere almeno 32 caratteri")
    return {
        "type": "openapi", "url": "http://control-plane:8085",
        "spec_type": "url", "spec": "", "path": "webui-tools/openapi.json",
        "auth_type": "bearer", "key": token,
        "config": {"enable": True},
        "info": {"id": ID, "name": "HyperSpace Files",
                 "description": "Cartelle condivise e immagini di Anna"},
    }


def activity_banner():
    return {"id": BANNER_ID, "type": "info", "title": "Anna Batch: monitor attività",
            "content": "[Apri il monitor in tempo reale](http://127.0.0.1:8085/activity) — nessuna connessione Terminale necessaria.",
            "dismissible": False, "timestamp": 0}


def register(db_path, token, filter_path=None, pipe_path=None):
    entry = connection(token)
    db_path = Path(db_path)
    if not db_path.is_file():
        print("Database WebUI non ancora creato; userà TOOL_SERVER_CONNECTIONS al primo avvio")
        return False
    with sqlite3.connect(db_path, timeout=10) as db:
        row = db.execute("SELECT value FROM config WHERE key = ?", (KEY,)).fetchone()
        current = json.loads(row[0]) if row else []
        if not isinstance(current, list):
            raise ValueError("La configurazione dei tool server non è una lista")
        updated = [item for item in current
                   if not (isinstance(item, dict) and item.get("info", {}).get("id") == ID)]
        updated.append(entry)
        db.execute(
            "INSERT INTO config (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (KEY, json.dumps(updated, separators=(",", ":")), int(time.time())),
        )
        row = db.execute("SELECT value FROM config WHERE key = ?", (BANNER_KEY,)).fetchone()
        banners = json.loads(row[0]) if row else []
        if not isinstance(banners, list):
            raise ValueError("La configurazione dei banner non è una lista")
        banners = [item for item in banners if not
                   (isinstance(item, dict) and item.get("id") == BANNER_ID)]
        banners.append(activity_banner())
        db.execute(
            "INSERT INTO config (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (BANNER_KEY, json.dumps(banners, ensure_ascii=False, separators=(",", ":")),
             int(time.time())),
        )
        if filter_path:
            row = db.execute("SELECT content FROM function WHERE id = ?", (FILTER_ID,)).fetchone()
            if row:
                old_content = row[0] or ""
                old_hash = hashlib.sha256(old_content.encode("utf-8")).hexdigest()
                if old_hash == LEGACY_FILTER_SHA256 or MANAGED_MARKER in old_content:
                    content = Path(filter_path).read_text(encoding="utf-8")
                    db.execute("UPDATE function SET content = ?, updated_at = ? WHERE id = ?",
                               (content, int(time.time()), FILTER_ID))
                    print("Filtro Gemma aggiornato")
                else:
                    print("Filtro Gemma personalizzato: aggiornamento saltato")
        if pipe_path:
            content = Path(pipe_path).read_text(encoding="utf-8")
            row = db.execute("SELECT content FROM function WHERE id = ?", (PIPE_ID,)).fetchone()
            now = int(time.time())
            if row:
                if MANAGED_MARKER in (row[0] or ""):
                    db.execute("UPDATE function SET content = ?, updated_at = ? WHERE id = ?",
                               (content, now, PIPE_ID))
                else:
                    print("Anna Batch diretto personalizzato: aggiornamento saltato")
            else:
                admin = db.execute("SELECT id FROM user WHERE role = 'admin' LIMIT 1").fetchone()
                if not admin:
                    raise ValueError("Nessun amministratore WebUI per registrare Anna Batch diretto")
                db.execute("INSERT INTO function "
                           "(id, user_id, name, type, content, meta, valves, is_active, is_global, updated_at, created_at) "
                           "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (PIPE_ID, admin[0], "Anna Batch diretto", "pipe", content,
                            json.dumps({"description": "Accoda fino a 50 scene numerate senza LLM"}),
                            "{}", 1, 1, now, now))
    print(f"Registrato {ID}; connessioni totali: {len(updated)}; monitor Anna Batch in WebUI")
    return True


if __name__ == "__main__":
    try:
        register(sys.argv[1] if len(sys.argv) > 1 else "/app/backend/data/webui.db",
                 os.environ.get("WEBUI_TOOLS_TOKEN", ""),
                 os.environ.get("WEBUI_FILTER_SOURCE"),
                 os.environ.get("WEBUI_PIPE_SOURCE"))
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"Registrazione Open WebUI fallita: {exc}", file=sys.stderr)
        sys.exit(1)
