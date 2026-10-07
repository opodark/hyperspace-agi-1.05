# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "register_webui_tool_server.py"
spec = importlib.util.spec_from_file_location("register_webui_tool_server", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RegistrationTests(unittest.TestCase):
    def test_upsert_preserves_other_connections(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "webui.db"
            with sqlite3.connect(db_path) as db:
                db.execute("CREATE TABLE config (key TEXT PRIMARY KEY, value JSON NOT NULL, updated_at BIGINT)")
                db.execute("INSERT INTO config VALUES (?, ?, 0)",
                           (module.KEY, json.dumps([{"info": {"id": "other"}}])))
                db.execute("INSERT INTO config VALUES (?, ?, 0)",
                           (module.BANNER_KEY, json.dumps([{"id": "user-banner", "content": "mio"}])))
            self.assertTrue(module.register(db_path, "x" * 32))
            self.assertTrue(module.register(db_path, "y" * 32))
            with sqlite3.connect(db_path) as db:
                entries = json.loads(db.execute("SELECT value FROM config WHERE key=?", (module.KEY,)).fetchone()[0])
                banners = json.loads(db.execute("SELECT value FROM config WHERE key=?", (module.BANNER_KEY,)).fetchone()[0])
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0]["info"]["id"], "other")
            self.assertEqual(entries[1]["key"], "y" * 32)
            self.assertEqual([b["id"] for b in banners], ["user-banner", module.BANNER_ID])
            self.assertIn("/activity", banners[1]["content"])

    def test_updates_only_managed_filter(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "webui.db"
            source = Path(directory) / "filter.py"
            source.write_text(module.MANAGED_MARKER + "\n# v2\n")
            with sqlite3.connect(db_path) as db:
                db.execute("CREATE TABLE config (key TEXT PRIMARY KEY, value JSON NOT NULL, updated_at BIGINT)")
                db.execute("CREATE TABLE function (id TEXT PRIMARY KEY, content TEXT, updated_at BIGINT)")
                db.execute("INSERT INTO function VALUES (?, ?, 0)",
                           (module.FILTER_ID, "# custom user filter"))
            module.register(db_path, "x" * 32, source)
            with sqlite3.connect(db_path) as db:
                self.assertEqual(db.execute("SELECT content FROM function").fetchone()[0],
                                 "# custom user filter")
                db.execute("UPDATE function SET content = ?", (module.MANAGED_MARKER,))
            module.register(db_path, "x" * 32, source)
            with sqlite3.connect(db_path) as db:
                self.assertIn("# v2", db.execute("SELECT content FROM function").fetchone()[0])

    def test_registers_and_updates_managed_pipe(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "webui.db"
            source = Path(directory) / "pipe.py"
            source.write_text(module.MANAGED_MARKER + "\n# v1\n")
            with sqlite3.connect(db_path) as db:
                db.execute("CREATE TABLE config (key TEXT PRIMARY KEY, value JSON NOT NULL, updated_at BIGINT)")
                db.execute("CREATE TABLE user (id TEXT PRIMARY KEY, role TEXT)")
                db.execute("INSERT INTO user VALUES ('admin-id', 'admin')")
                db.execute("CREATE TABLE function (id TEXT PRIMARY KEY, user_id TEXT, name TEXT, "
                           "type TEXT, content TEXT, meta TEXT, valves TEXT, is_active BOOLEAN, "
                           "is_global BOOLEAN, updated_at BIGINT, created_at BIGINT)")
            module.register(db_path, "x" * 32, pipe_path=source)
            source.write_text(module.MANAGED_MARKER + "\n# v2\n")
            module.register(db_path, "x" * 32, pipe_path=source)
            with sqlite3.connect(db_path) as db:
                row = db.execute("SELECT user_id,type,content,is_active,is_global FROM function "
                                 "WHERE id=?", (module.PIPE_ID,)).fetchone()
            self.assertEqual(row, ("admin-id", "pipe", module.MANAGED_MARKER + "\n# v2\n", 1, 1))


if __name__ == "__main__":
    unittest.main()
