# SPDX-License-Identifier: Apache-2.0
# shared/db.py
# HyperSpace AGI v1.03 — SQLite persistence layer
# Tabelle: logs, nodes, tasks, federated_peers
# Usato dal control-plane per sostituire i log in-memory e per
# gestire l'allowlist dei control-plane federati.

import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime

def _default_db_path() -> str:
    env = os.getenv("DB_PATH")
    if env:
        return env
    if os.path.exists("./data/control-plane/hyperspace.db"):
        return "./data/control-plane/hyperspace.db"
    return "./data/hyperspace.db"


DB_PATH = _default_db_path()
_DB_LOCK = threading.RLock()


def _journal_mode():
    # WAL requires reliable shared-memory mmap/locking. Docker Desktop bind
    # mounts can SIGBUS during commit; rollback journal is the portable default.
    mode = os.getenv("SQLITE_JOURNAL_MODE", "DELETE").strip().upper()
    if mode not in {"DELETE", "WAL"}:
        raise ValueError("SQLITE_JOURNAL_MODE must be DELETE or WAL")
    return mode


def _ensure_dir():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)


@contextmanager
def _conn():
    with _DB_LOCK:
        _ensure_dir()
        con = sqlite3.connect(DB_PATH, timeout=30.0)
        try:
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA busy_timeout = 30000")
            con.execute("PRAGMA mmap_size = 0")
            con.execute(f"PRAGMA journal_mode = {_journal_mode()}")
            con.execute("PRAGMA synchronous = FULL")
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def init_db():
    """Crea le tabelle se non esistono."""
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS logs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                log_id     TEXT UNIQUE,
                ts         TEXT DEFAULT (datetime('now')),
                node_id    TEXT DEFAULT '',
                type       TEXT DEFAULT 'system',
                status     TEXT DEFAULT 'info',
                source     TEXT DEFAULT '',
                target     TEXT DEFAULT '',
                trace_id   TEXT DEFAULT '',
                summary    TEXT DEFAULT '',
                detail     TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_logs_type   ON logs(type);
            CREATE INDEX IF NOT EXISTS idx_logs_status ON logs(status);
            CREATE INDEX IF NOT EXISTS idx_logs_ts     ON logs(ts);

            CREATE TABLE IF NOT EXISTS nodes (
                node_id    TEXT PRIMARY KEY,
                endpoint   TEXT DEFAULT '',
                tier       TEXT DEFAULT 'leaf',
                pubkey     TEXT DEFAULT '',
                version    TEXT DEFAULT '',
                vram_gb    REAL DEFAULT 0.0,
                peers_active INTEGER DEFAULT 0,
                status     TEXT DEFAULT 'active',
                last_seen  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id      TEXT UNIQUE,
                created_at   TEXT DEFAULT (datetime('now')),
                completed_at TEXT,
                node_id      TEXT DEFAULT '',
                endpoint     TEXT DEFAULT '',
                prompt       TEXT DEFAULT '',
                model        TEXT DEFAULT '',
                status       TEXT DEFAULT 'created',
                result       TEXT DEFAULT '',
                error        TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS federated_peers (
                peer_id     TEXT PRIMARY KEY,
                label       TEXT DEFAULT '',
                pubkey      TEXT NOT NULL,
                endpoint    TEXT NOT NULL,
                enabled     INTEGER DEFAULT 1,
                added_at    TEXT DEFAULT (datetime('now')),
                last_seen   TEXT,
                last_status TEXT DEFAULT 'unknown'
            );
            CREATE TABLE IF NOT EXISTS node_aliases (
                node_id  TEXT PRIMARY KEY,
                alias    TEXT UNIQUE NOT NULL,
                set_at   TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS web_contacts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id TEXT UNIQUE,
                ts         TEXT DEFAULT (datetime('now')),
                name       TEXT NOT NULL,
                email      TEXT NOT NULL,
                subject    TEXT DEFAULT '',
                message    TEXT NOT NULL,
                ip         TEXT DEFAULT '',
                status     TEXT DEFAULT 'unread'
            );
            CREATE INDEX IF NOT EXISTS idx_web_contacts_ts ON web_contacts(ts);
            CREATE INDEX IF NOT EXISTS idx_web_contacts_status ON web_contacts(status);

            CREATE TABLE IF NOT EXISTS web_auth_keys (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                key_id     TEXT UNIQUE,
                auth_key   TEXT UNIQUE NOT NULL,
                label      TEXT DEFAULT '',
                email      TEXT DEFAULT '',
                role       TEXT DEFAULT 'member',
                status     TEXT DEFAULT 'active',
                created_at TEXT DEFAULT (datetime('now')),
                expires_at TEXT,
                last_used  TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_web_auth_keys_key ON web_auth_keys(auth_key);

            CREATE TABLE IF NOT EXISTS token_wallets (
                node_id         TEXT PRIMARY KEY,
                solana_address  TEXT DEFAULT '',
                balance         REAL DEFAULT 0.0,
                total_earned    REAL DEFAULT 0.0,
                tasks_completed INTEGER DEFAULT 0,
                uptime_seconds  INTEGER DEFAULT 0,
                tier            TEXT DEFAULT 'leaf',
                created_at      TEXT DEFAULT (datetime('now')),
                updated_at      TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_token_wallets_solana ON token_wallets(solana_address);

            CREATE TABLE IF NOT EXISTS token_transactions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_id           TEXT UNIQUE,
                node_id         TEXT NOT NULL,
                type            TEXT NOT NULL,
                amount          REAL NOT NULL,
                reference_id    TEXT DEFAULT '',
                memo            TEXT DEFAULT '',
                created_at      TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_token_tx_node ON token_transactions(node_id);
            CREATE INDEX IF NOT EXISTS idx_token_tx_created ON token_transactions(created_at);
        """)
    print(f"[DB] Initialized at {DB_PATH}")


# ── LOGS ──────────────────────────────────────────────────────────────────────

def insert_log(entry: dict):
    with _conn() as con:
        con.execute("""
            INSERT OR IGNORE INTO logs
              (log_id, ts, node_id, type, status, source, target, trace_id, summary, detail)
            VALUES
              (:id, :ts, :sourceNode, :type, :status, :sourceNode, :targetNode, :traceId, :summary, :detail)
        """, entry)


def query_logs(
    type_: str = "",
    status: str = "",
    node: str = "",
    q: str = "",
    page: int = 1,
    per_page: int = 100,
) -> list:
    clauses, params = [], []
    if type_:  clauses.append("type = ?");                params.append(type_)
    if status: clauses.append("status = ?");              params.append(status)
    if node:   clauses.append("(source LIKE ? OR target LIKE ?)"); params += [f"%{node}%", f"%{node}%"]
    if q:      clauses.append("(summary LIKE ? OR detail LIKE ?)"); params += [f"%{q}%", f"%{q}%"]

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    offset = (page - 1) * per_page
    sql = f"SELECT * FROM logs {where} ORDER BY id DESC LIMIT ? OFFSET ?"
    params += [per_page, offset]

    with _conn() as con:
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def count_logs(type_: str = "", status: str = "", node: str = "", q: str = "") -> int:
    clauses, params = [], []
    if type_:  clauses.append("type = ?");                params.append(type_)
    if status: clauses.append("status = ?");              params.append(status)
    if node:   clauses.append("(source LIKE ? OR target LIKE ?)"); params += [f"%{node}%", f"%{node}%"]
    if q:      clauses.append("(summary LIKE ? OR detail LIKE ?)"); params += [f"%{q}%", f"%{q}%"]
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _conn() as con:
        return con.execute(f"SELECT COUNT(*) FROM logs {where}", params).fetchone()[0]


def clear_logs():
    with _conn() as con:
        con.execute("DELETE FROM logs")


def export_logs(type_: str = "", status: str = "", node: str = "", q: str = "") -> list:
    return query_logs(type_=type_, status=status, node=node, q=q, page=1, per_page=100_000)


# ── NODES ─────────────────────────────────────────────────────────────────────

def upsert_node(info: dict):
    with _conn() as con:
        con.execute("""
            INSERT INTO nodes (node_id, endpoint, tier, pubkey, version, vram_gb, peers_active, status, last_seen)
            VALUES (:node_id, :endpoint, :tier, :pubkey, :version, :vram_gb, :peers_active, :status, :last_seen)
            ON CONFLICT(node_id) DO UPDATE SET
                endpoint     = excluded.endpoint,
                tier         = excluded.tier,
                pubkey       = excluded.pubkey,
                version      = excluded.version,
                vram_gb      = excluded.vram_gb,
                peers_active = excluded.peers_active,
                status       = excluded.status,
                last_seen    = excluded.last_seen
        """, {
            "node_id":      info.get("node_id", ""),
            "endpoint":     info.get("endpoint", ""),
            "tier":         info.get("tier", "leaf"),
            "pubkey":       info.get("pubkey", info.get("public_key", "")),
            "version":      info.get("version", ""),
            "vram_gb":      info.get("vram_gb", 0.0),
            "peers_active": info.get("peers_active", 0),
            "status":       info.get("status", "active"),
            "last_seen":    datetime.utcnow().isoformat(timespec="seconds") + "Z",
        })


def get_all_nodes() -> list:
    with _conn() as con:
        rows = con.execute("SELECT * FROM nodes ORDER BY last_seen DESC").fetchall()
    return [dict(r) for r in rows]


def delete_node(node_id: str) -> bool:
    """Remove a persisted mesh node and its optional alias."""
    with _conn() as con:
        con.execute("DELETE FROM node_aliases WHERE node_id = ?", (node_id,))
        cur = con.execute("DELETE FROM nodes WHERE node_id = ?", (node_id,))
        return cur.rowcount > 0


# ── TASKS ─────────────────────────────────────────────────────────────────────

def insert_task(task: dict):
    with _conn() as con:
        con.execute("""
            INSERT OR IGNORE INTO tasks
              (task_id, created_at, node_id, endpoint, prompt, model, status)
            VALUES (:task_id, :created_at, :node_id, :endpoint, :prompt, :model, :status)
        """, {
            "task_id":    task.get("id", ""),
            "created_at": task.get("created_at", datetime.utcnow().isoformat()),
            "node_id":    task.get("node", ""),
            "endpoint":   task.get("endpoint", ""),
            "prompt":     task.get("payload", {}).get("prompt", ""),
            "model":      task.get("payload", {}).get("model", ""),
            "status":     task.get("status", "created"),
        })


def update_task(task_id: str, status: str, result: str = "", error: str = "", node_id: str = "", endpoint: str = ""):
    with _conn() as con:
        con.execute("""
            UPDATE tasks SET
                status       = ?,
                result       = ?,
                error        = ?,
                node_id      = CASE WHEN ? != '' THEN ? ELSE node_id END,
                endpoint     = CASE WHEN ? != '' THEN ? ELSE endpoint END,
                completed_at = CASE WHEN ? IN ('done','failed') THEN datetime('now') ELSE completed_at END
            WHERE task_id = ?
        """, (status, result, error, node_id, node_id, endpoint, endpoint, status, task_id))


def get_all_tasks() -> list:
    with _conn() as con:
        rows = con.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


# ── FEDERATED PEERS ────────────────────────────────────────────────────────────
# Allowlist dei control-plane federati fidati. Un peer entra qui SOLO tramite
# pairing manuale (dashboard / API), mai per auto-discovery — a differenza
# dei nodi, che possono autoannunciarsi liberamente.

def upsert_federated_peer(peer: dict):
    with _conn() as con:
        con.execute("""
            INSERT INTO federated_peers (peer_id, label, pubkey, endpoint, enabled, last_seen, last_status)
            VALUES (:peer_id, :label, :pubkey, :endpoint, :enabled, :last_seen, :last_status)
            ON CONFLICT(peer_id) DO UPDATE SET
                label       = excluded.label,
                pubkey      = excluded.pubkey,
                endpoint    = excluded.endpoint,
                enabled     = excluded.enabled
        """, {
            "peer_id":     peer.get("peer_id", ""),
            "label":       peer.get("label", ""),
            "pubkey":      peer.get("pubkey", ""),
            "endpoint":    peer.get("endpoint", ""),
            "enabled":     int(peer.get("enabled", 1)),
            "last_seen":   peer.get("last_seen"),
            "last_status": peer.get("last_status", "unknown"),
        })


def get_all_federated_peers() -> list:
    with _conn() as con:
        rows = con.execute("SELECT * FROM federated_peers ORDER BY added_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_federated_peer(peer_id: str):
    with _conn() as con:
        row = con.execute("SELECT * FROM federated_peers WHERE peer_id = ?", (peer_id,)).fetchone()
    return dict(row) if row else None


def set_federated_peer_enabled(peer_id: str, enabled: bool):
    with _conn() as con:
        con.execute("UPDATE federated_peers SET enabled = ? WHERE peer_id = ?", (int(enabled), peer_id))


def delete_federated_peer(peer_id: str):
    with _conn() as con:
        con.execute("DELETE FROM federated_peers WHERE peer_id = ?", (peer_id,))


def touch_federated_peer(peer_id: str, status: str):
    with _conn() as con:
        con.execute(
            "UPDATE federated_peers SET last_seen = datetime('now'), last_status = ? WHERE peer_id = ?",
            (status, peer_id),
        )

# ── NODE ALIASES ────────────────────────────────────────────────────────────
# Alias leggibili per il routing esplicito "modello::alias" da Open WebUI.
# UNIQUE(alias) a livello DB come ultima rete di sicurezza contro le race
# condition; il controllo "primario" anti-collisione resta lato app
# (main.py verifica prima di chiamare set_node_alias).

def set_node_alias(node_id: str, alias: str):
    with _conn() as con:
        con.execute("""
            INSERT INTO node_aliases (node_id, alias, set_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(node_id) DO UPDATE SET
                alias  = excluded.alias,
                set_at = excluded.set_at
        """, (node_id, alias))


def get_node_id_by_alias(alias: str):
    with _conn() as con:
        row = con.execute(
            "SELECT node_id FROM node_aliases WHERE alias = ?", (alias,)
        ).fetchone()
    return row["node_id"] if row else None


def get_alias_map() -> dict:
    with _conn() as con:
        rows = con.execute("SELECT node_id, alias FROM node_aliases").fetchall()
    return {r["node_id"]: r["alias"] for r in rows}


def delete_node_alias(node_id: str):
    with _conn() as con:
        con.execute("DELETE FROM node_aliases WHERE node_id = ?", (node_id,))


# ── WEB CONTACTS ────────────────────────────────────────────────────────────

def insert_web_contact(name: str, email: str, message: str, subject: str = "", ip: str = "", contact_id: str | None = None) -> dict:
    cid = contact_id or f"cnt-{uuid.uuid4().hex[:12]}"
    with _conn() as con:
        con.execute("""
            INSERT INTO web_contacts (contact_id, name, email, subject, message, ip, status)
            VALUES (?, ?, ?, ?, ?, ?, 'unread')
        """, (cid, name.strip(), email.strip(), (subject or "").strip(), message.strip(), (ip or "").strip()))
        row = con.execute("SELECT * FROM web_contacts WHERE contact_id = ?", (cid,)).fetchone()
    return dict(row) if row else {
        "contact_id": cid, "name": name.strip(), "email": email.strip(),
        "subject": (subject or "").strip(), "message": message.strip(),
        "ip": (ip or "").strip(), "status": "unread"
    }


def list_web_contacts(limit: int = 50, offset: int = 0, status: str | None = None) -> list[dict]:
    clauses, params = [], []
    if status:
        clauses.append("status = ?")
        params.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM web_contacts {where} ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([max(1, limit), max(0, offset)])
    with _conn() as con:
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def update_web_contact_status(contact_id: str, status: str) -> bool:
    with _conn() as con:
        cur = con.execute(
            "UPDATE web_contacts SET status = ? WHERE contact_id = ?",
            (status, contact_id),
        )
    return cur.rowcount > 0


def get_web_contact(contact_id: str) -> dict | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM web_contacts WHERE contact_id = ?", (contact_id.strip(),)).fetchone()
        return dict(row) if row else None


def get_web_contact_by_email(email: str) -> dict | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM web_contacts WHERE email = ? ORDER BY id DESC LIMIT 1", (email.strip(),)).fetchone()
        return dict(row) if row else None


def count_web_contacts() -> dict:
    with _conn() as con:
        total = con.execute("SELECT COUNT(*) as c FROM web_contacts").fetchone()["c"]
        unread = con.execute("SELECT COUNT(*) as c FROM web_contacts WHERE status = 'unread'").fetchone()["c"]
    return {"total": total, "unread": unread}


# ── WEB AUTH KEYS ─────────────────────────────────────────────────────────────

def insert_auth_key(auth_key: str, label: str = "", email: str = "", role: str = "member", expires_at: str | None = None) -> dict:
    key_id = f"key-{uuid.uuid4().hex[:12]}"
    clean_key = auth_key.strip()
    with _conn() as con:
        con.execute("""
            INSERT INTO web_auth_keys (key_id, auth_key, label, email, role, status, expires_at)
            VALUES (?, ?, ?, ?, ?, 'active', ?)
        """, (key_id, clean_key, label.strip(), email.strip(), role.strip(), expires_at))
        row = con.execute("SELECT * FROM web_auth_keys WHERE auth_key = ?", (clean_key,)).fetchone()
    return dict(row) if row else {
        "key_id": key_id, "auth_key": clean_key, "label": label.strip(),
        "email": email.strip(), "role": role.strip(), "status": "active"
    }


def get_auth_key(auth_key: str) -> dict | None:
    clean_key = str(auth_key or "").strip()
    if not clean_key:
        return None
    with _conn() as con:
        row = con.execute("SELECT * FROM web_auth_keys WHERE auth_key = ?", (clean_key,)).fetchone()
        return dict(row) if row else None


def get_auth_key_by_email(email: str) -> dict | None:
    clean = str(email or "").strip()
    if not clean:
        return None
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM web_auth_keys WHERE email = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
            (clean,)
        ).fetchone()
        return dict(row) if row else None



def list_auth_keys(status: str | None = None) -> list[dict]:
    sql = "SELECT * FROM web_auth_keys"
    params = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY id DESC"
    with _conn() as con:
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def revoke_auth_key(auth_key: str) -> bool:
    clean = str(auth_key or "").strip()
    with _conn() as con:
        cur = con.execute(
            "UPDATE web_auth_keys SET status = 'revoked' WHERE auth_key = ? OR key_id = ?",
            (clean, clean),
        )
    return cur.rowcount > 0


def touch_auth_key(auth_key: str) -> None:
    clean = str(auth_key or "").strip()
    with _conn() as con:
        con.execute(
            "UPDATE web_auth_keys SET last_used = datetime('now') WHERE auth_key = ?",
            (clean,),
        )


# ── TOKENOMICS & NODE REWARDS ────────────────────────────────────────────────

def get_token_wallet(node_id: str) -> dict | None:
    nid = (node_id or "").strip()
    if not nid:
        return None
    with _conn() as con:
        row = con.execute("SELECT * FROM token_wallets WHERE node_id = ?", (nid,)).fetchone()
        return dict(row) if row else None


def upsert_token_wallet(node_id: str, tier: str = "leaf") -> dict:
    nid = (node_id or "").strip()
    if not nid:
        raise ValueError("node_id non può essere vuoto")
    with _conn() as con:
        con.execute("""
            INSERT INTO token_wallets (node_id, tier, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(node_id) DO UPDATE SET
                tier = CASE WHEN excluded.tier != '' THEN excluded.tier ELSE tier END,
                updated_at = datetime('now')
        """, (nid, tier))
        row = con.execute("SELECT * FROM token_wallets WHERE node_id = ?", (nid,)).fetchone()
        return dict(row) if row else {}


def credit_token_balance(node_id: str, amount: float, tx_type: str, reference_id: str = "", memo: str = "") -> dict:
    nid = (node_id or "").strip()
    if not nid:
        raise ValueError("node_id non può essere vuoto")
    tx_id = f"tx-{uuid.uuid4().hex[:14]}"
    clean_amount = round(float(amount), 4)

    with _conn() as con:
        # Assicura esistenza wallet
        con.execute("""
            INSERT OR IGNORE INTO token_wallets (node_id) VALUES (?)
        """, (nid,))

        # Incrementa bilancio e contatori
        task_inc = 1 if tx_type == "task_reward" else 0
        con.execute("""
            UPDATE token_wallets
            SET balance = ROUND(balance + ?, 4),
                total_earned = ROUND(total_earned + CASE WHEN ? > 0 THEN ? ELSE 0 END, 4),
                tasks_completed = tasks_completed + ?,
                updated_at = datetime('now')
            WHERE node_id = ?
        """, (clean_amount, clean_amount, clean_amount, task_inc, nid))

        # Registra transazione
        con.execute("""
            INSERT INTO token_transactions (tx_id, node_id, type, amount, reference_id, memo, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, (tx_id, nid, tx_type, clean_amount, (reference_id or "").strip(), (memo or "").strip()))

        row = con.execute("SELECT * FROM token_wallets WHERE node_id = ?", (nid,)).fetchone()
        return {
            "tx_id": tx_id,
            "node_id": nid,
            "amount": clean_amount,
            "type": tx_type,
            "new_balance": row["balance"] if row else 0.0,
            "total_earned": row["total_earned"] if row else 0.0,
        }


def set_node_solana_address(node_id: str, solana_address: str) -> bool:
    nid = (node_id or "").strip()
    addr = (solana_address or "").strip()
    if not nid:
        return False
    with _conn() as con:
        con.execute("INSERT OR IGNORE INTO token_wallets (node_id) VALUES (?)", (nid,))
        cur = con.execute("""
            UPDATE token_wallets
            SET solana_address = ?, updated_at = datetime('now')
            WHERE node_id = ?
        """, (addr, nid))
        return cur.rowcount > 0


def get_wallets_by_solana_address(solana_address: str) -> list[dict]:
    addr = (solana_address or "").strip()
    if not addr:
        return []
    with _conn() as con:
        rows = con.execute("SELECT * FROM token_wallets WHERE solana_address = ?", (addr,)).fetchall()
        return [dict(r) for r in rows]


def list_token_wallets(limit: int = 50, offset: int = 0) -> list[dict]:
    sql = "SELECT * FROM token_wallets ORDER BY balance DESC, tasks_completed DESC LIMIT ? OFFSET ?"
    with _conn() as con:
        rows = con.execute(sql, (max(1, limit), max(0, offset))).fetchall()
        return [dict(r) for r in rows]


def list_token_transactions(node_id: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
    clauses, params = [], []
    if node_id:
        clauses.append("node_id = ?")
        params.append(node_id.strip())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM token_transactions {where} ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([max(1, limit), max(0, offset)])
    with _conn() as con:
        rows = con.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_tokenomics_stats() -> dict:
    with _conn() as con:
        w_row = con.execute("""
            SELECT
                COUNT(*) as total_nodes,
                COALESCE(SUM(balance), 0.0) as total_circulating,
                COALESCE(SUM(total_earned), 0.0) as total_mined,
                COALESCE(SUM(tasks_completed), 0) as total_tasks_rewarded,
                COUNT(CASE WHEN solana_address != '' THEN 1 END) as nodes_with_solana_wallet
            FROM token_wallets
        """).fetchone()

        tx_row = con.execute("SELECT COUNT(*) as total_txs FROM token_transactions").fetchone()

        return {
            "token_symbol": "$00MESH",
            "token_name": "00MESH Network Token",
            "total_nodes_rewarded": w_row["total_nodes"] if w_row else 0,
            "total_circulating": round(w_row["total_circulating"] if w_row else 0.0, 4),
            "total_mined": round(w_row["total_mined"] if w_row else 0.0, 4),
            "total_tasks_rewarded": w_row["total_tasks_rewarded"] if w_row else 0,
            "nodes_with_solana_wallet": w_row["nodes_with_solana_wallet"] if w_row else 0,
            "total_transactions": tx_row["total_txs"] if tx_row else 0,
            "target_dex": "pump.fun (Solana SPL)",
        }

