# SPDX-License-Identifier: Apache-2.0
"""Guardie delle route web node e del confine di indirizzabilita'.

Niente Flask qui: le funzioni vengono estratte dal VERO control-plane/main.py
con ast ed eseguite in isolamento (stesso approccio di tests/test_local_nodes.py).
Cosi' il test gira anche dove flask/cryptography non sono installati, mentre la
verifica end-to-end completa vive in scripts/verify_web_node_e2e.py.
"""
import ast

from tests import cp_source
import json
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]

WEB_ROUTES = {
    "web_register": "/web/register",
    "web_poll": "/web/poll",
    "web_result": "/web/result",
    "web_enqueue": "/web/tasks",
    "web_status": "/web/status",
    "web_contact": "/web/contact",
    "web_contacts_list": "/web/contacts",
    "web_contact_update": "/web/contacts/<contact_id>",
    "web_auth_verify": "/web/auth/verify",
    "web_topology": "/web/topology",
    "web_search_endpoint": "/web/search",
    "web_sandbox_run": "/web/sandbox/run",
    "web_image_generate": "/web/image/generate",
    "web_image_status": "/web/image/status",
    "web_image_file": "/web/image/file",
}


class EndpointAddressabilityTests(unittest.TestCase):
    """Il gate `_best_endpoint` e' l'unico posto che decide se un nodo e'
    chiamabile: se un web node lo superasse, il CP proverebbe a fare una POST
    su http://browser://<id>/v1/chat/completions."""

    @classmethod
    def setUpClass(cls):
        tree = cp_source.albero()
        wanted = ("_normalize_endpoint", "_ep_to_url", "_best_endpoint")
        nodes = [n for n in tree.body
                 if isinstance(n, ast.FunctionDef) and n.name in wanted]
        cls.scope = {}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "cp", "exec"),
             cls.scope)

    def test_web_node_has_no_callable_endpoint(self):
        best = self.scope["_best_endpoint"]
        self.assertEqual(best({"endpoint": "browser://abc"}), "")
        self.assertEqual(best({"endpoint": "browser://abc", "is_web_node": True}), "")
        self.assertEqual(best({"endpoint": "", "is_web_node": True}), "")

    def test_web_public_endpoint_is_ignored_too(self):
        best = self.scope["_best_endpoint"]
        self.assertEqual(best({"endpoint": "", "public_endpoint": "browser://abc"}), "")

    def test_regular_nodes_still_resolve(self):
        best = self.scope["_best_endpoint"]
        self.assertEqual(best({"endpoint": "http://mac:8084"}), "http://mac:8084")
        self.assertEqual(best({"endpoint": "mac:8084"}), "http://mac:8084")
        self.assertEqual(best({"endpoint": "https://node.example"}), "https://node.example")
        self.assertEqual(best({"endpoint": "", "public_endpoint": "https://pub.example"}),
                         "https://pub.example")
        self.assertEqual(best({"endpoint": ""}), "")


class WebRouteGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = cp_source.albero()
        cls.functions = {n.name: n for n in cls.tree.body if isinstance(n, ast.FunctionDef)}

    def test_routes_are_defined(self):
        for name, path in WEB_ROUTES.items():
            with self.subTest(route=name):
                self.assertIn(name, self.functions)
                source = ast.unparse(self.functions[name].decorator_list)
                self.assertIn(path, source)

    def test_enqueue_requires_the_operator_token(self):
        calls = [n.func.id for n in ast.walk(self.functions["web_enqueue"])
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        self.assertIn("_network_admin_error", calls)

    def test_read_only_routes_do_not_require_the_operator_token(self):
        for name in ("web_register", "web_poll", "web_result", "web_status", "web_contact", "web_auth_verify", "web_topology", "web_search_endpoint", "web_sandbox_run"):
            with self.subTest(route=name):
                calls = [n.func.id for n in ast.walk(self.functions[name])
                         if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
                self.assertNotIn("_network_admin_error", calls)

    def test_contact_management_routes_require_operator_token(self):
        for name in ("web_contacts_list", "web_contact_update"):
            with self.subTest(route=name):
                calls = [n.func.id for n in ast.walk(self.functions[name])
                         if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
                self.assertIn("_network_admin_error", calls)

    def test_contact_db_roundtrip(self):
        import shared.db as db
        db.init_db()
        cnt = db.insert_web_contact(
            name="Test User",
            email="test@example.com",
            message="Questo è un messaggio di test unitario",
            subject="Test Oggetto",
            ip="127.0.0.1",
        )
        self.assertTrue(cnt["contact_id"].startswith("cnt-"))
        self.assertEqual(cnt["status"], "unread")

        lista = db.list_web_contacts(limit=10)
        self.assertTrue(any(c["contact_id"] == cnt["contact_id"] for c in lista))

        aggiornato = db.update_web_contact_status(cnt["contact_id"], "read")
        self.assertTrue(aggiornato)

        conteggi = db.count_web_contacts()
        self.assertGreaterEqual(conteggi["total"], 1)

    def _temp_db(self):
        # Mai il DB della mesh: una chiave creata da un test sarebbe una chiave vera.
        import tempfile
        import shared.db as db
        tmp = tempfile.TemporaryDirectory()
        old_path = db.DB_PATH
        db.DB_PATH = os.path.join(tmp.name, "hyperspace.db")
        self.addCleanup(tmp.cleanup)
        self.addCleanup(setattr, db, "DB_PATH", old_path)
        db.init_db()
        return db

    def test_contact_route_returns_key_only_once_per_email(self):
        import secrets
        from flask import Flask
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control-plane"))
        import cp.webnode as webnode
        db = self._temp_db()
        app = Flask(__name__)
        app.register_blueprint(webnode._bp)
        unique_email = f"once-{secrets.token_hex(4)}@example.com"
        payload = {
            "name": "Claude Agent",
            "email": unique_email,
            "subject": "Handshake",
            "message": "Primo messaggio di registrazione",
        }
        with app.test_client() as client:
            first = client.post("/web/contact", json=payload)
            self.assertEqual(first.status_code, 201)
            first_json = first.get_json()
            self.assertTrue(first_json["ok"])
            self.assertFalse(first_json.get("key_already_issued"))
            self.assertTrue(str(first_json.get("auth_key", "")).startswith("hs-mesh-"))

            second = client.post("/web/contact", json=payload)
            self.assertEqual(second.status_code, 200)
            second_json = second.get_json()
            self.assertTrue(second_json["ok"])
            self.assertTrue(second_json.get("key_already_issued"))
            self.assertNotIn("auth_key", second_json)

            # Nel DB resta solo l'hash, e la chiave in chiaro continua a valere.
            issued = first_json["auth_key"]
            record = db.get_auth_key_by_email(unique_email)
            self.assertTrue(record["auth_key"].startswith("sha256:"))
            self.assertNotIn(issued, json.dumps(record))
            verified = client.post("/web/auth/verify", json={"token": issued})
            self.assertEqual(verified.status_code, 200)
            self.assertTrue(verified.get_json()["authenticated"])
            stolen = client.post("/web/auth/verify", json={"token": record["auth_key"]})
            self.assertEqual(stolen.status_code, 401)

    def test_plaintext_auth_keys_are_migrated_to_hash(self):
        import secrets
        db = self._temp_db()
        legacy = f"hs-mesh-legacy-{secrets.token_hex(4)}"
        with db._conn() as con:
            con.execute("INSERT INTO web_auth_keys (key_id, auth_key, email) VALUES (?, ?, ?)",
                        (f"key-{secrets.token_hex(6)}", legacy, "legacy@example.com"))
        db.init_db()
        with db._conn() as con:
            plain = con.execute("SELECT COUNT(*) FROM web_auth_keys WHERE auth_key = ?",
                                (legacy,)).fetchone()[0]
        self.assertEqual(plain, 0)
        record = db.get_auth_key(legacy)
        self.assertIsNotNone(record)
        self.assertTrue(record["key_hint"].startswith("hs-mesh-legacy-"))
        self.assertTrue(db.revoke_auth_key(legacy))
        self.assertEqual(db.get_auth_key(legacy)["status"], "revoked")

    def test_registry_is_built_from_env_limits(self):
        source = cp_source.SORGENTE()
        self.assertIn("from shared.web_node import", source)
        self.assertIn("web_registry = WebNodeRegistry(", source)
        for key in ("WEB_NODE_MAX_QUEUE", "WEB_NODE_TASK_TTL_S", "WEB_NODE_MAX_POLL_S"):
            self.assertIn(key, source)

    def test_task_types_come_from_the_shared_whitelist(self):
        shared_source = (ROOT / "shared" / "web_node.py").read_text(encoding="utf-8")
        self.assertIn("WEB_SAFE_TASK_TYPES = {", shared_source)
        # Nessun elenco duplicato nel CP: i tipi ammessi vivono in un solo posto.
        # La variabile non si chiama `cp_source`: quello e' il modulo, e un
        # `cp_source = ...` qui dentro lo ombreggerebbe (UnboundLocalError).
        testo_cp = cp_source.SORGENTE()
        self.assertNotIn("WEB_SAFE_TASK_TYPES = {", testo_cp)


    def test_web_node_tokenomics_routes(self):
        source = cp_source.SORGENTE()
        self.assertIn("@_bp.route('/web/node/wallet'", source)
        self.assertIn("@_bp.route('/web/node/balance'", source)
        self.assertIn("@_bp.route('/web/tokenomics/status'", source)
        self.assertIn("@_bp.route('/web/tokenomics/leaderboard'", source)


if __name__ == "__main__":
    unittest.main()
