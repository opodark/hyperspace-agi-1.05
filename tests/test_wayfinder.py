# SPDX-License-Identifier: Apache-2.0
import ast
import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, Flask, jsonify, request
from shared.forge_skills import (
    WAYFINDER_BUNDLE_DIR,
    load_wayfinder_bundle,
    attach_skills,
    source_hash,
    wayfinder_references,
)
from shared.mission import MissionStore
from shared.mission_policy import parse_budget
from shared.wayfinder import WayfinderStore, Conflict, agent_action, register_wayfinder


def draft():
    return {
        "destination": "Build a reviewed gallery",
        "fog": ["Image storage?"],
        "tickets": [
            {
                "key": "research",
                "title": "Formats",
                "question": "Which formats are supported?",
                "kind": "research",
                "mode": "afk",
                "dependencies": [],
            },
            {
                "key": "design",
                "title": "Layout",
                "question": "Which layout does the user want?",
                "kind": "grilling",
                "mode": "hitl",
                "dependencies": ["research"],
            },
        ],
    }


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = WayfinderStore(self.tmp.name)
        self.map = self.store.create(draft())

    def change(self, key, action, **kw):
        self.map = self.store.change(
            self.map["id"],
            dict(revision=self.map["revision"], owner="agent", **kw),
            action,
            key,
        )
        return self.map

    def resolve_all(self):
        self.change("research", "claim")
        self.change("research", "resolve", answer="JPEG files, checked source")
        self.change("design", "claim")
        self.change(
            "design",
            "resolve",
            answer="Grid, as requested by the user",
            human_confirmed=True,
        )
        self.map["fog"] = []
        self.map = self.store.change(self.map["id"], self.map)

    def test_frontier_dependencies_and_human_decisions(self):
        self.assertEqual(self.map["frontier"], ["research"])
        with self.assertRaises(Conflict):
            self.change("design", "claim")
        self.change("research", "claim")
        self.assertEqual(self.map["frontier"], [])
        self.change("research", "resolve", answer="JPEG")
        self.assertEqual(self.map["frontier"], ["design"])
        self.change("design", "claim")
        with self.assertRaises(Conflict):
            self.change("design", "resolve", answer="Invented")
        self.change("design", "resolve", answer="User chose grid", human_confirmed=True)
        self.assertFalse(self.map["ready"])  # fog is still open
        self.assertEqual(WayfinderStore(self.tmp.name).get(self.map["id"]), self.map)

    def test_agent_cannot_resolve_human_or_downgrade_or_start_mission(self):
        self.change("research", "claim")
        self.change("research", "resolve", answer="JPEG")
        self.change("design", "claim")
        with self.assertRaises(Conflict):
            agent_action(
                self.tmp.name,
                dict(
                    action="resolve",
                    map_id=self.map["id"],
                    ticket_key="design",
                    data=dict(
                        revision=self.map["revision"],
                        owner="agent",
                        answer="Fake",
                        human_confirmed=True,
                    ),
                ),
            )
        for action in ["handoff", "approve"]:
            with self.assertRaises(ValueError):
                agent_action(self.tmp.name, {"action": action})
        altered = copy.deepcopy(self.map)
        altered["tickets"][1].update(kind="task", mode="afk")
        with self.assertRaises(Conflict):
            self.store.change(self.map["id"], altered)

    def test_exclusion_is_recorded_in_mission_scope_and_claim_can_release(self):
        self.change("research", "claim")
        self.change("research", "release")
        self.assertEqual(self.map["frontier"], ["research"])
        self.change("research", "claim")
        self.change("research", "exclude", answer="Existing storage is sufficient")
        self.change("design", "claim")
        self.change("design", "resolve", answer="Grid", human_confirmed=True)
        self.map["fog"] = []
        self.map = self.store.change(self.map["id"], self.map)
        _, mission = self.store.handoff(
            self.map["id"],
            dict(revision=self.map["revision"], confirm_execution=True),
            MissionStore(self.tmp.name),
            {},
        )
        self.assertIn("Formats: Existing storage is sufficient", mission["objective"])

    def test_agent_can_resolve_afk(self):
        for action in ["claim", "resolve"]:
            self.map = agent_action(
                self.tmp.name,
                dict(
                    action=action,
                    map_id=self.map["id"],
                    ticket_key="research",
                    data=dict(
                        revision=self.map["revision"], owner="agent", answer="JPEG"
                    ),
                ),
            )["map"]
        self.assertEqual(self.map["tickets"][0]["status"], "resolved")

    def test_concurrent_claim_has_one_winner_across_store_instances(self):
        def claim(_):
            try:
                WayfinderStore(self.tmp.name).change(
                    self.map["id"],
                    {"revision": 1, "owner": "agent"},
                    "claim",
                    "research",
                )
                return True
            except Conflict:
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(claim, range(2))), 1)

    def test_invalid_graph_and_lifecycle_cannot_be_injected(self):
        for dependencies in [["missing"], ["design"]]:
            data = draft()
            data["tickets"][0]["dependencies"] = dependencies
            with self.assertRaises(ValueError):
                self.store.create(data)
        data = draft()
        data["tickets"][0].update(
            status="resolved", answer="injected", human_confirmed=True
        )
        self.assertEqual(self.store.create(data)["tickets"][0]["status"], "open")
        changed = copy.deepcopy(self.map)
        changed["tickets"] = []
        with self.assertRaises(Conflict):
            self.store.change(self.map["id"], changed)

    def test_handoff_gates_snapshot_idempotence_and_resume(self):
        missions = MissionStore(self.tmp.name)
        args = dict(revision=self.map["revision"], confirm_execution=True)
        with self.assertRaises(Conflict):
            self.store.handoff(self.map["id"], args, missions, {})
        self.resolve_all()
        args["revision"] = self.map["revision"]
        with self.assertRaises(Conflict):
            self.store.handoff(
                self.map["id"], {"revision": args["revision"]}, missions, {}
            )
        record, mission = self.store.handoff(
            self.map["id"], args, missions, parse_budget()
        )
        self.assertIn("JPEG", mission["objective"])
        self.assertEqual(mission["policy"]["wayfinder"]["map_id"], record["id"])
        again, same = WayfinderStore(self.tmp.name).handoff(
            record["id"], args, missions, {}
        )
        self.assertEqual(same["trace_id"], mission["trace_id"])
        self.assertEqual(len(missions.list()), 1)
        with self.assertRaises(Conflict):
            self.store.change(record["id"], record)

    def test_failed_handoff_can_retry_without_duplicate(self):
        self.resolve_all()
        missions = MissionStore(self.tmp.name)
        original = missions.create

        def fail(*args, **kw):
            raise OSError("disk unavailable")

        missions.create = fail
        args = dict(revision=self.map["revision"], confirm_execution=True)
        with self.assertRaises(OSError):
            self.store.handoff(self.map["id"], args, missions, {})
        missions.create = original
        _, mission = self.store.handoff(self.map["id"], args, missions, {})
        self.assertEqual(len(missions.list()), 1)
        self.assertEqual(mission["status"], "planned")

    def test_no_silent_context_truncation(self):
        self.resolve_all()
        self.map["notes"] = "x" * 4000
        self.map = self.store.change(self.map["id"], self.map)
        with self.assertRaises(ValueError):
            self.store.handoff(
                self.map["id"],
                dict(revision=self.map["revision"], confirm_execution=True),
                MissionStore(self.tmp.name),
                {},
            )
        self.assertIsNone(self.store.get(self.map["id"])["mission_id"])


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        app = Flask(__name__)
        app.testing = True

        def auth():
            if request.headers.get("Authorization") != "Bearer test":
                return jsonify(error="unauthorized"), 401

        self.missions = MissionStore(self.tmp.name)
        register_wayfinder(
            app, lambda: self.tmp.name, auth, lambda: self.missions, parse_budget
        )
        self.client = app.test_client()
        self.headers = {"Authorization": "Bearer test"}

    def test_auth_validation_and_conflict(self):
        for path, method in [
            ("/wayfinder/maps", "get"),
            ("/wayfinder/maps", "post"),
            ("/wayfinder/maps/a", "get"),
            ("/wayfinder/maps/a", "put"),
            ("/wayfinder/maps/a/handoff", "post"),
            ("/wayfinder/maps/a/tickets/b/resolve", "post"),
            ("/wayfinder/references", "get"),
        ]:
            self.assertEqual(
                getattr(self.client, method)(path, json={}).status_code, 401
            )
        self.assertEqual(
            self.client.post(
                "/wayfinder/maps", headers=self.headers, json=[]
            ).status_code,
            400,
        )
        m = self.client.post(
            "/wayfinder/maps", headers=self.headers, json=draft()
        ).json["map"]
        path = "/wayfinder/maps/" + m["id"]
        self.assertEqual(self.client.get(path, headers=self.headers).json["map"], m)
        m["revision"] = 0
        self.assertEqual(
            self.client.put(path, headers=self.headers, json=m).status_code, 409
        )
        self.assertEqual(
            self.client.get("/wayfinder/maps/nope", headers=self.headers).status_code,
            404,
        )
        self.assertEqual(
            len(
                self.client.get("/wayfinder/references", headers=self.headers).json[
                    "references"
                ]
            ),
            4,
        )


class BundleTests(unittest.TestCase):
    def test_bundle_literal_hashes_and_context_budget(self):
        items = load_wayfinder_bundle(WAYFINDER_BUNDLE_DIR)
        self.assertEqual(len(items), 5)
        item = next(i for i in items if i["name"] == "Wayfinder wayfinder")
        item.update(
            status="approved", approved_source_sha256=source_hash(item["source"])
        )
        payload = attach_skills({"hyperspace_skills": [item["id"]]}, lambda _: item)
        self.assertIn(item["source"], payload["messages"][0]["content"])
        self.assertIn("# HyperSpace adapter", payload["messages"][0]["content"])
        self.assertEqual(len(wayfinder_references()), 4)

    def test_tampered_support_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "bundle"
            shutil.copytree(WAYFINDER_BUNDLE_DIR, root)
            (root / "skills/prototype/UI.md").write_text("tampered")
            with self.assertRaises(ValueError):
                load_wayfinder_bundle(root)

    def test_import_route_preserves_existing_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Flask(__name__)
            app.testing = True
            ns = dict(
                globals(),
                json=json,
                os=os,
                re=re,
                hashlib=hashlib,
                datetime=datetime,
                timezone=timezone,
                app=app,
                _bp=Blueprint("forge-wayfinder-test", __name__),
                FORGE_DIR=tmp,
                FORGE_ADMIN_TOKEN="test",
                _forge_lock=threading.Lock(),
                _FORGE_TYPES={"tool", "skill", "patch"},
                _FORGE_STATES={"draft", "review", "approved", "disabled"},
            )
            source = Path("control-plane/cp/forge.py").read_text()
            names = {
                "_forge_path",
                "_forge_write",
                "_forge_authorized",
                "_forge_validate",
                "_forge_read_skill",
                "forge_import_wayfinder",
            }
            nodes = [
                n
                for n in ast.parse(source).body
                if isinstance(n, ast.FunctionDef) and n.name in names
            ]
            exec(
                compile(ast.Module(body=nodes, type_ignores=[]), "main.py", "exec"), ns
            )
            app.register_blueprint(ns["_bp"])
            client = app.test_client()
            path = "/forge/import/wayfinder"
            headers = {"X-Hyperspace-Forge-Token": "test"}
            self.assertEqual(client.post(path).status_code, 403)
            first = client.post(path, headers=headers)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(len(first.json["artifacts"]), 5)
            key = first.json["artifacts"][0]["id"]
            item = ns["_forge_read_skill"](key)
            self.assertEqual(item["status"], "draft")
            item["source"] = "local edit"
            ns["_forge_write"](item)
            self.assertFalse(
                any(
                    i["created"]
                    for i in client.post(path, headers=headers).json["artifacts"]
                )
            )
            self.assertEqual(ns["_forge_read_skill"](key)["source"], "local edit")


if __name__ == "__main__":
    unittest.main()
