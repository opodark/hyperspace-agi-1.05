# SPDX-License-Identifier: Apache-2.0
"""Persistent local decision tracker; explicit handoff to the existing mission DAG.

SQLite transactions + optimistic revisions protect claims across threads/processes.
No model is invoked by this tracker. Operator routes are the human decision channel.
"""

import copy
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, jsonify, request
from shared.mission import validate_dag


class Conflict(ValueError):
    pass


def text(value, limit, label, required=False):
    if (
        not isinstance(value, str)
        or len(value) > limit
        or (required and not value.strip())
    ):
        raise ValueError(
            f"{label}: expected {'nonempty ' if required else ''}text, max {limit} characters"
        )
    return value.strip()


def strings(value, label):
    if not isinstance(value, list) or len(value) > 30:
        raise ValueError(f"{label}: expected at most 30 entries")
    return [text(v, 1000, label, True) for v in value]


def normalize(data, previous=None):
    if not isinstance(data, dict):
        raise ValueError("map must be an object")
    result = {
        "destination": text(data.get("destination"), 2000, "destination", True),
        "notes": text(data.get("notes", ""), 4000, "notes"),
        "fog": strings(data.get("fog", []), "fog"),
        "out_of_scope": strings(data.get("out_of_scope", []), "out_of_scope"),
    }
    raw = data.get("tickets", [])
    if not isinstance(raw, list) or len(raw) > 60:
        raise ValueError("tickets: expected at most 60 entries")
    old = {t["key"]: t for t in (previous or {}).get("tickets", [])}
    tickets = []
    for t in raw:
        if not isinstance(t, dict):
            raise ValueError("ticket must be an object")
        key = text(t.get("key"), 80, "ticket key", True)
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", key):
            raise ValueError("ticket keys use lowercase letters, digits and hyphens")
        kind, mode = t.get("kind", "grilling"), t.get("mode", "hitl")
        if not isinstance(kind, str) or not isinstance(mode, str):
            raise ValueError("ticket kind and mode must be strings")
        if kind not in {"research", "prototype", "grilling", "task"} or mode not in {
            "hitl",
            "afk",
        }:
            raise ValueError("invalid ticket kind or mode")
        if kind in {"prototype", "grilling"} and mode != "hitl":
            raise ValueError("prototype and grilling require human input")
        ticket = {
            "key": key,
            "title": text(t.get("title"), 200, "title", True),
            "question": text(t.get("question"), 4000, "question", True),
            "kind": kind,
            "mode": mode,
            "dependencies": strings(t.get("dependencies", []), "dependencies"),
        }
        prior = old.get(key)
        if prior and prior["mode"] == "hitl" and mode != "hitl":
            raise Conflict("human decision tickets cannot become autonomous")
        if prior and prior["status"] != "open":
            if any(ticket[k] != prior[k] for k in ticket):
                raise Conflict(
                    "resolved tickets are immutable; add a new decision ticket"
                )
        for name, default in (
            ("status", "open"),
            ("owner", ""),
            ("answer", ""),
            ("human_confirmed", False),
        ):
            # Lifecycle fields can only change through claim/resolve/exclude.
            ticket[name] = prior[name] if prior else default
        tickets.append(ticket)
    if set(old) - {t["key"] for t in tickets}:
        raise Conflict("retain tickets; use exclude to record an out-of-scope decision")
    if tickets:
        validate_dag(tickets)
    result["tickets"] = tickets
    return result


def public(record):
    result = copy.deepcopy(record)
    by_key = {t["key"]: t for t in record["tickets"]}
    result["frontier"] = [
        t["key"]
        for t in record["tickets"]
        if t["status"] == "open"
        and not t["owner"]
        and all(by_key[d]["status"] != "open" for d in t["dependencies"])
    ]
    result["ready"] = not record["fog"] and all(
        t["status"] != "open" for t in record["tickets"]
    )
    return result


class WayfinderStore:
    def __init__(self, directory):
        self.path = Path(directory) / "wayfinder.sqlite3"

    @contextmanager
    def transaction(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute(
                "CREATE TABLE IF NOT EXISTS maps (id TEXT PRIMARY KEY, body TEXT NOT NULL)"
            )
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _read(self, db, map_id):
        if not isinstance(map_id, str):
            raise ValueError("map_id must be a string")
        row = db.execute("SELECT body FROM maps WHERE id=?", (map_id,)).fetchone()
        if row is None:
            raise KeyError(map_id)
        return json.loads(row[0])

    def _write(self, db, record):
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        db.execute(
            "INSERT OR REPLACE INTO maps VALUES (?, ?)",
            (record["id"], json.dumps(record, ensure_ascii=False)),
        )

    def list(self):
        with self.transaction() as db:
            return [
                public(json.loads(row[0]))
                for row in db.execute(
                    "SELECT body FROM maps ORDER BY rowid DESC LIMIT 100"
                )
            ]

    def get(self, map_id):
        with self.transaction() as db:
            return public(self._read(db, map_id))

    def create(self, data):
        record = normalize(data)
        record.update(id="map-" + uuid.uuid4().hex, revision=1, mission_id=None)
        with self.transaction() as db:
            self._write(db, record)
        return public(record)

    def change(
        self, map_id, data, action="update", ticket_key=None, human_channel=True
    ):
        with self.transaction() as db:
            record = self._read(db, map_id)
            if (
                type(data.get("revision")) is not int
                or data["revision"] != record["revision"]
            ):
                raise Conflict("map changed; reload before saving")
            if record["mission_id"]:
                raise Conflict("map handed off; create a new map for further decisions")
            if action == "update":
                record.update(normalize(data, record))
            else:
                ticket = next(
                    (t for t in record["tickets"] if t["key"] == ticket_key), None
                )
                if ticket is None:
                    raise KeyError(ticket_key)
                if ticket["status"] != "open":
                    raise Conflict("ticket already closed")
                owner = text(data.get("owner"), 120, "owner", True)
                if action == "claim":
                    if ticket["key"] not in public(record)["frontier"]:
                        raise Conflict("ticket is blocked or already claimed")
                    ticket["owner"] = owner
                elif action == "release":
                    if ticket["owner"] != owner:
                        raise Conflict("claim belongs to another owner")
                    ticket["owner"] = ""
                elif action in {"resolve", "exclude"}:
                    if ticket["owner"] != owner:
                        raise Conflict("claim the ticket before resolving it")
                    by_key = {t["key"]: t for t in record["tickets"]}
                    if any(
                        by_key[d]["status"] == "open" for d in ticket["dependencies"]
                    ):
                        raise Conflict("ticket dependencies are still open")
                    if ticket["mode"] == "hitl" and (
                        not human_channel or data.get("human_confirmed") is not True
                    ):
                        raise Conflict(
                            "human decision required; do not invent the user's answer"
                        )
                    ticket["answer"] = text(data.get("answer"), 4000, "answer", True)
                    ticket["human_confirmed"] = data.get("human_confirmed") is True
                    ticket["status"] = "resolved" if action == "resolve" else "excluded"
                    # Exclusion rationale stays on the ticket and enters handoff scope.
                else:
                    raise ValueError("unknown action")
            record["revision"] += 1
            self._write(db, record)
            return public(record)

    def handoff(self, map_id, data, missions, budget):
        """Persist deterministic link before creating a mission: retries recover safely.

        Linked maps cannot change. A failed mission creation can be retried with
        the same revision/id, including after a process restart.
        """
        with self.transaction() as db:
            record = self._read(db, map_id)
            if (
                type(data.get("revision")) is not int
                or record["revision"] != data["revision"]
            ):
                raise Conflict("map changed; reload before handoff")
            if not public(record)["ready"]:
                raise Conflict(
                    "resolve open tickets and clarify remaining fog before handoff"
                )
            if data.get("confirm_execution") is not True:
                raise Conflict(
                    "confirm_execution is required: the mission loop may start immediately"
                )
            objective = (
                "Destination: "
                + record["destination"]
                + "\nDecisions:\n"
                + "\n".join(
                    t["title"] + ": " + t["answer"]
                    for t in record["tickets"]
                    if t["status"] == "resolved"
                )
            )
            objective += (
                "\nNotes: "
                + record["notes"]
                + "\nOut of scope:\n"
                + "\n".join(
                    record["out_of_scope"]
                    + [
                        t["title"] + ": " + t["answer"]
                        for t in record["tickets"]
                        if t["status"] == "excluded"
                    ]
                )
            )
            if len(objective) > 4000:
                raise ValueError(
                    "handoff exceeds the mission's 4000-character objective limit; use a smaller map"
                )
            if not record["mission_id"]:
                record["mission_id"] = "mission-wayfinder-" + record["id"][4:]
                record["handoff_budget"] = budget
                self._write(db, record)
        # Serialize concurrent retry/create against this same local tracker DB.
        with self.transaction() as db:
            mission = missions.get(record["mission_id"])
            if mission is None:
                mission = missions.create(
                    objective,
                    [
                        "Respect the recorded decisions and scope; verify artifacts before review."
                    ],
                    budget=record["handoff_budget"],
                    policy={
                        "wayfinder": {
                            "map_id": map_id,
                            "revision": record["revision"],
                            "snapshot": record,
                        }
                    },
                    mission_id=record["mission_id"],
                )
        return public(record), mission


def register_wayfinder(app, directory, authorize, mission_store, parse_budget):
    bp = Blueprint("wayfinder", __name__)

    @bp.before_request
    def auth():
        return authorize()

    @bp.errorhandler(KeyError)
    def missing(error):
        return jsonify(error="map or ticket not found"), 404

    @bp.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error=str(error)), 409 if isinstance(error, Conflict) else 400

    def store():
        return WayfinderStore(directory())

    def body():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object")
        return data

    @bp.route("/wayfinder/maps", methods=["GET", "POST"])
    def collection():
        if request.method == "GET":
            return jsonify(maps=store().list())
        return jsonify(map=store().create(body())), 201

    @bp.route("/wayfinder/maps/<map_id>", methods=["GET", "PUT"])
    def detail(map_id):
        if request.method == "GET":
            return jsonify(map=store().get(map_id))
        return jsonify(map=store().change(map_id, body()))

    @bp.route("/wayfinder/maps/<map_id>/tickets/<key>/<action>", methods=["POST"])
    def ticket(map_id, key, action):
        if action not in {"claim", "release", "resolve", "exclude"}:
            raise ValueError("unknown ticket action")
        return jsonify(map=store().change(map_id, body(), action, key))

    @bp.route("/wayfinder/maps/<map_id>/handoff", methods=["POST"])
    def handoff(map_id):
        missions = mission_store()
        if missions is None:
            return jsonify(error="mission control is not initialized"), 503
        data = body()
        overrides = data.get("budget", {})
        if not isinstance(overrides, dict):
            raise ValueError("budget must be an object")
        budget = parse_budget(overrides=overrides)
        record, mission = store().handoff(map_id, data, missions, budget)
        return jsonify(
            map=record,
            mission_id=mission["id"],
            status=mission["status"],
            applied=False,
        )

    @bp.route("/wayfinder/references")
    def references():
        from shared.forge_skills import wayfinder_references

        return jsonify(references=wayfinder_references())

    app.register_blueprint(bp)


def agent_action(directory, args):
    """Agent capability: planning and AFK resolutions only, never human sign-off/handoff."""
    if not isinstance(args, dict):
        raise ValueError("arguments must be an object")
    store = WayfinderStore(directory)
    action = args.get("action", "list")
    if not isinstance(action, str):
        raise ValueError("action must be a string")
    if action == "list":
        return {
            "maps": [
                {
                    "id": m["id"],
                    "destination": m["destination"],
                    "revision": m["revision"],
                    "frontier": m["frontier"],
                    "ready": m["ready"],
                }
                for m in store.list()
            ]
        }
    if action == "get":
        return {"map": store.get(args.get("map_id"))}
    if action == "references":
        from shared.forge_skills import wayfinder_references

        return {"references": wayfinder_references()}
    data = args.get("data", {})
    if not isinstance(data, dict):
        raise ValueError("data must be an object")
    if action == "create":
        return {"map": store.create(data)}
    if action in {"update", "claim", "release", "resolve", "exclude"}:
        return {
            "map": store.change(
                args.get("map_id"),
                data,
                action,
                args.get("ticket_key"),
                human_channel=False,
            )
        }
    raise ValueError(
        "unsupported agent action; human decisions and execution handoff use the operator dashboard"
    )
