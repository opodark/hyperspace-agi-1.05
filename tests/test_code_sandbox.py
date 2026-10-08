# SPDX-License-Identifier: Apache-2.0
import importlib.util
import ast
from types import SimpleNamespace
import json
import os
import re
import shutil
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from pathlib import Path

from shared.code_sandbox import CodeSandboxClient, HybridCodeSandboxClient, SandboxUnavailable


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("sandbox_runner", ROOT / "sandbox" / "runner.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)

# Il runner esegue i comandi con un gruppo di processi nuovo e `select()` sulle
# pipe: semantica POSIX. In produzione gira nel container Linux (vedi
# docs/code-sandbox.md), quindi i test che eseguono davvero qualcosa non hanno
# senso sul nodo Windows e vanno saltati dichiarandolo — non fatti passare.
POSIX_ONLY = unittest.skipUnless(
    os.name != "nt", "il runner esegue comandi solo nel container Linux (POSIX)")


def _minimal_pdf() -> str:
    """Un PDF di una pagina, con gli offset xref calcolati sul serio.

    Serve a `_inspect`: firma `%PDF`, una pagina, un filone di testo. Costruito a
    mano invece di dipendere da reportlab, cosi' il test vale anche dove reportlab
    non c'e'.
    """
    content = b"BT /F1 12 Tf 20 100 Td (hello) Tj ET\n"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
        b"/Resources 5 0 R /Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n"
        + content + b"endstream",
        b"<< /Font << /F1 6 0 R >> >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode("ascii")
    return out.decode("latin-1")


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.seed = root / "seed"
        self.exchange = root / "exchange"
        self.workspaces = root / "workspaces"
        self.seed.mkdir()
        self.exchange.mkdir()
        self.workspaces.mkdir()
        (self.seed / "app.py").write_text("print('old')\n", encoding="utf-8")
        (self.seed / ".env").write_text("SECRET=must-not-copy\n", encoding="utf-8")
        (self.seed / "data").mkdir()
        (self.seed / "data" / "runtime.txt").write_text("private", encoding="utf-8")
        runner.SEED = self.seed
        runner.EXCHANGE = self.exchange
        runner.WORKSPACES = self.workspaces
        runner.MAX_WORKSPACES = 6

    def create(self):
        return runner._create({"label": "test"})["workspace_id"]

    def test_inspect_reports_pdf_signature_pages_and_text(self):
        workspace_id = self.create()
        runner._write({"workspace_id": workspace_id, "path": "out/brief.pdf",
                       "content": _minimal_pdf()})
        result = runner._inspect({"workspace_id": workspace_id, "path": "out/brief.pdf"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["kind"], "pdf")
        self.assertTrue(result["magic_ok"])
        self.assertEqual(result["path"], "out/brief.pdf")
        try:
            import pypdf  # noqa: F401
        except ImportError:
            # pypdf e' opzionale: senza di lui firma e dimensione parlano ancora.
            self.assertIsNone(result["pages"])
            return
        self.assertEqual(result["pages"], 1)
        self.assertGreater(result["text_chars"], 0)

    def test_inspect_reads_a_file_that_is_not_a_pdf_without_failing(self):
        workspace_id = self.create()
        runner._write({"workspace_id": workspace_id, "path": "brief.pdf",
                       "content": "not really a pdf\n"})
        result = runner._inspect({"workspace_id": workspace_id, "path": "brief.pdf"})
        self.assertTrue(result["ok"])          # il file esiste ed e' leggibile
        self.assertFalse(result["magic_ok"])   # ma non e' un PDF
        self.assertEqual(result["kind"], "other")
        self.assertIsNone(result["pages"])

    def test_inspect_requires_an_existing_file(self):
        workspace_id = self.create()
        with self.assertRaises(FileNotFoundError):
            runner._inspect({"workspace_id": workspace_id, "path": "missing.pdf"})

    def test_workspace_is_a_sanitized_copy_not_the_source(self):
        workspace_id = self.create()
        repo = self.workspaces / workspace_id / "repo"
        self.assertEqual((repo / "app.py").read_text(encoding="utf-8"), "print('old')\n")
        self.assertFalse((repo / ".env").exists())
        self.assertFalse((repo / "data").exists())
        (repo / "app.py").write_text("changed", encoding="utf-8")
        self.assertEqual((self.seed / "app.py").read_text(encoding="utf-8"), "print('old')\n")

    @POSIX_ONLY
    def test_read_only_image_seed_produces_writable_disposable_workspace(self):
        import stat
        (self.seed / "app.py").chmod(0o444)
        self.seed.chmod(0o555)
        self.addCleanup(self.seed.chmod, 0o755)
        workspace_id = self.create()
        repo = self.workspaces / workspace_id / "repo"
        self.assertTrue(repo.stat().st_mode & stat.S_IWUSR)
        self.assertTrue((repo / "app.py").stat().st_mode & stat.S_IWUSR)
        result = runner._write({"workspace_id": workspace_id, "path": "new.py", "content": "x = 1\n"})
        self.assertTrue(result["ok"])
        self.assertTrue(runner._discard({"workspace_id": workspace_id})["ok"])
        self.assertFalse((self.workspaces / workspace_id).exists())
        self.assertFalse((self.seed / "app.py").stat().st_mode & stat.S_IWUSR)

    def test_path_traversal_and_absolute_paths_are_rejected(self):
        workspace_id = self.create()
        with self.assertRaises(ValueError):
            runner._read({"workspace_id": workspace_id, "path": "../../etc/passwd"})
        with self.assertRaises(ValueError):
            runner._write({"workspace_id": workspace_id, "path": "/tmp/escape", "content": "x"})

    def test_failed_read_gives_relative_path_hint_without_logging_path(self):
        workspace_id = self.create()
        (self.exchange / "results").mkdir()
        job = self.exchange / "bad-read.json"
        job.write_text(json.dumps({"job_id": "bad-read", "action": "read",
                                   "workspace_id": workspace_id,
                                   "path": "/private/secret.txt"}), encoding="utf-8")
        runner._process(job)
        result = json.loads((self.exchange / "results" / "bad-read.json").read_text())
        audit = (self.exchange / "audit.jsonl").read_text()
        self.assertEqual(result["error_code"], "invalid_path")
        self.assertIn("relative to the workspace root", result["hint"])
        self.assertIn('"path_kind": "absolute"', audit)
        self.assertNotIn("secret.txt", audit)

    def process(self, name, payload):
        """Runs one job file through `_process` and returns its JSON result."""
        (self.exchange / "results").mkdir(exist_ok=True)
        job = self.exchange / f"{name}.json"
        job.write_text(json.dumps({"job_id": name, **payload}), encoding="utf-8")
        runner._process(job)
        return json.loads((self.exchange / "results" / f"{name}.json").read_text())

    def test_unknown_workspace_is_reported_as_workspace_missing_not_path(self):
        # Un id che non esiste non e' un path sbagliato: il modello deve capire
        # che il difetto e' l'id, altrimenti "aggiusta" il path per sempre.
        result = self.process("bad-ws", {"action": "write",
                                         "workspace_id": "0123456789abcdef",
                                         "path": "note.py", "content": "x = 1\n"})
        self.assertEqual(result["error_code"], "workspace_missing")
        self.assertIn("create", result["hint"])
        self.assertNotIn("relative to the workspace root", result["hint"])

    def test_corrupt_workspace_id_gets_its_own_error_code(self):
        # Misurato nella prova PDF: un id riportato con un carattere spurio.
        result = self.process("corrupt-ws", {"action": "read",
                                             "workspace_id": "e91c901d-~d49",
                                             "path": "README.md"})
        self.assertEqual(result["error_code"], "invalid_workspace")
        self.assertIn("create", result["hint"])

    def test_missing_path_inside_a_real_workspace_is_still_path_missing(self):
        workspace_id = self.create()
        result = self.process("missing-path", {"action": "read",
                                               "workspace_id": workspace_id,
                                               "path": "nope/missing.md"})
        self.assertEqual(result["error_code"], "path_missing")
        self.assertIn("relative to the workspace root", result["hint"])

    def test_replace_is_exact_and_diff_is_reviewable(self):
        workspace_id = self.create()
        result = runner._replace({
            "workspace_id": workspace_id,
            "path": "app.py",
            "old": "old",
            "new": "new",
            "expected_occurrences": 1,
        })
        self.assertTrue(result["ok"])
        diff = runner._diff({"workspace_id": workspace_id})
        self.assertEqual(diff["changed_files"], ["app.py"])
        self.assertIn("-print('old')", diff["diff"])
        self.assertIn("+print('new')", diff["diff"])

    @POSIX_ONLY
    def test_generated_patch_applies_to_a_clean_workspace(self):
        proposal_id = self.create()
        runner._replace({
            "workspace_id": proposal_id,
            "path": "app.py",
            "old": "old",
            "new": "verified",
            "expected_occurrences": 1,
        })
        runner._write({"workspace_id": proposal_id, "path": "new_file.py",
                       "content": "VALUE = 42\n"})
        proposal = runner._diff({"workspace_id": proposal_id})

        verifier_id = self.create()
        runner._write({"workspace_id": verifier_id, "path": ".proposal.patch",
                       "content": proposal["diff"]})
        checked = runner._run({"workspace_id": verifier_id,
                               "argv": ["git", "apply", "--check", ".proposal.patch"]})
        self.assertTrue(checked["ok"], checked.get("output"))
        applied = runner._run({"workspace_id": verifier_id,
                               "argv": ["git", "apply", ".proposal.patch"]})
        self.assertTrue(applied["ok"], applied.get("output"))
        repo = self.workspaces / verifier_id / "repo"
        self.assertEqual((repo / "app.py").read_text(encoding="utf-8"),
                         "print('verified')\n")
        self.assertEqual((repo / "new_file.py").read_text(encoding="utf-8"),
                         "VALUE = 42\n")

    def test_command_allowlist_rejects_shells(self):
        workspace_id = self.create()
        with self.assertRaises(ValueError):
            runner._run({"workspace_id": workspace_id, "argv": ["sh", "-c", "echo unsafe"]})

    @POSIX_ONLY
    def test_allowed_command_runs_without_shell(self):
        workspace_id = self.create()
        # Il runner ammette sia `python` sia `python3` (vedi ALLOWED_EXECUTABLES):
        # nell'immagine sandbox Linux esiste `python`, su macOS solo `python3`.
        # Fissare "python" qui renderebbe il test non portatile fuori container.
        python_exe = "python" if shutil.which("python") else "python3"
        result = runner._run({
            "workspace_id": workspace_id,
            "argv": [python_exe, "-c", "print('sandbox-ok')"],
            "timeout": 5,
        })
        self.assertTrue(result["ok"])
        self.assertIn("sandbox-ok", result["output"])

    def test_workspace_limit_is_enforced(self):
        runner.MAX_WORKSPACES = 1
        self.create()
        with self.assertRaises(RuntimeError):
            self.create()

    def check(self, tool, source, path="sample.py", **kwargs):
        workspace_id = self.create()
        runner._write({"workspace_id": workspace_id, "path": path, "content": source})
        return runner._check({"workspace_id": workspace_id, "tool_id": tool,
                              "path": path, **kwargs})

    def test_catalog_reports_missing_dependency(self):
        original = runner.importlib.util.find_spec
        with patch.object(runner.importlib.util, "find_spec",
                          side_effect=lambda name: None if name == "bandit" else original(name)):
            catalog = runner._catalog({})
            self.assertFalse(next(x for x in catalog["tools"] if x["tool_id"] == "bandit")["available"])
            result = self.check("bandit", "x = 1\n")
        self.assertFalse(result["passed"])
        self.assertFalse(result["completed"])
        self.assertIn("unavailable", result["error"])

    @unittest.skipUnless(runner.importlib.util.find_spec("bandit"), "Bandit not installed")
    def test_bandit_finds_eval_and_accepts_clean_code(self):
        result = self.check("bandit", "value = eval(input())  # nosec\n")
        self.assertTrue(result["completed"], result)
        self.assertFalse(result["passed"])
        self.assertTrue(any(f["rule"] == "B307" and f["path"] == "sample.py"
                            and f["line"] == 1 for f in result["findings"]), result)
        clean = self.check("bandit", "value = 42\n")
        self.assertTrue(clean["passed"], clean)

    @unittest.skipUnless(runner.importlib.util.find_spec("bandit"), "Bandit not installed")
    def test_bandit_parse_errors_and_empty_scans_do_not_pass(self):
        for source in ("def broken(\n", "# nothing to scan\n"):
            result = self.check("bandit", source)
            self.assertFalse(result["passed"], result)
            self.assertFalse(result["completed"], result)

    def test_bandit_malformed_report_does_not_pass(self):
        with patch.object(runner, "_catalog", return_value={"tools": [
                {"tool_id": "bandit", "version": "test", "available": True}]}), \
             patch.object(runner, "_capture", return_value={"ok": True, "completed": True,
                 "exit_code": 0, "output": "not json", "stderr": "", "truncated": False}):
            result = self.check("bandit", "value = 42\n")
        self.assertFalse(result["passed"])
        self.assertFalse(result["completed"])

    @POSIX_ONLY
    def test_ruff_parses_findings_and_never_passes_invalid_reports(self):
        report = json.dumps([{
            "filename": "sample.py", "location": {"row": 1, "column": 1},
            "end_location": {"row": 1, "column": 2}, "code": "F401",
            "message": "unused import", "fix": None, "noqa_row": 1, "url": "https://example.test/F401",
        }])
        with patch.object(runner, "_catalog", return_value={"tools": [
                {"tool_id": "ruff", "version": "test", "available": True}]}), \
             patch.object(runner, "_capture", return_value={"ok": False, "completed": True,
                 "exit_code": 1, "output": report, "stderr": "", "truncated": False, "duration_ms": 1}):
            result = self.check("ruff", "import unused\n")
        self.assertTrue(result["completed"], result)
        self.assertFalse(result["passed"], result)
        self.assertEqual(result["findings"], [{"path": "sample.py", "line": 1,
                                                "rule": "F401", "message": "unused import"}])
        with patch.object(runner, "_catalog", return_value={"tools": [
                {"tool_id": "ruff", "version": "test", "available": True}]}), \
             patch.object(runner, "_capture", return_value={"ok": True, "completed": True,
                 "exit_code": 0, "output": "not json", "stderr": "", "truncated": False, "duration_ms": 1}):
            result = self.check("ruff", "value = 42\n")
        self.assertFalse(result["completed"], result)
        self.assertFalse(result["passed"], result)

    def test_check_presets_do_not_create_tool_caches_in_the_diff(self):
        workspace_id = self.create()
        repo = self.workspaces / workspace_id / "repo"
        (repo / "sample.py").write_text("VALUE = 42\n", encoding="utf-8")
        captured = []

        def fake_capture(argv, cwd, env, timeout):
            captured.append(argv)
            return {"ok": True, "completed": True, "exit_code": 0, "output": "[]",
                    "stderr": "", "truncated": False, "duration_ms": 1}

        with patch.object(runner, "_catalog", return_value={"tools": [
                {"tool_id": "ruff", "version": "test", "available": True}]}), \
             patch.object(runner, "_capture", side_effect=fake_capture):
            runner._check({"workspace_id": workspace_id, "tool_id": "ruff", "path": "sample.py"})
        self.assertIn("--no-cache", captured[0])

        with patch.object(runner, "_catalog", return_value={"tools": [
                {"tool_id": "pytest", "version": "test", "available": True}]}), \
             patch.object(runner, "_capture", side_effect=fake_capture):
            runner._check({"workspace_id": workspace_id, "tool_id": "pytest", "path": "."})
        self.assertIn("no:cacheprovider", captured[1])

    @unittest.skipUnless(runner.importlib.util.find_spec("ruff"), "Ruff not installed")
    def test_ruff_finds_lint_and_accepts_clean_code(self):
        result = self.check("ruff", "import unused\n")
        self.assertTrue(result["completed"], result)
        self.assertFalse(result["passed"], result)
        self.assertTrue(any(f["rule"] == "F401" for f in result["findings"]), result)
        clean = self.check("ruff", "value = 42\n")
        self.assertTrue(clean["passed"], clean)

    def test_verify_requires_every_explicit_check_to_pass(self):
        workspace_id = self.create()
        runner._write({"workspace_id": workspace_id, "path": "test_sample.py", "content":
                       "def test_ok():\n    assert True\n"})
        with patch.object(runner, "_check", side_effect=[
                {"tool_id": "pytest", "completed": True, "passed": True, "duration_ms": 2},
                {"tool_id": "bandit", "completed": True, "passed": False, "duration_ms": 3,
                 "findings": [{"rule": "B307"}]}]):
            result = runner._verify({"workspace_id": workspace_id, "checks": [
                {"tool_id": "pytest", "path": "test_sample.py"},
                {"tool_id": "bandit", "path": "."},
            ]})
        self.assertTrue(result["completed"])
        self.assertFalse(result["passed"])
        self.assertEqual(result["duration_ms"], 5)

    def test_verify_collects_unavailable_or_bad_paths_as_not_completed(self):
        workspace_id = self.create()
        result = runner._verify({"workspace_id": workspace_id, "checks": [
            {"tool_id": "ruff", "path": "missing.py"},
        ]})
        self.assertFalse(result["completed"])
        self.assertFalse(result["passed"])
        self.assertIn("path not found", result["checks"][0]["error"])
        with self.assertRaises(ValueError):
            runner._verify({"workspace_id": workspace_id, "checks": []})

    @POSIX_ONLY
    @unittest.skipUnless(runner.importlib.util.find_spec("pytest"), "pytest not installed")
    def test_pytest_pass_fail_and_no_tests(self):
        for source, passed, code in (("def test_ok(): assert 1 == 1\n", True, 0),
                                     ("def test_bad(): assert False\n", False, 1),
                                     ("value = 1\n", False, 5)):
            result = self.check("pytest", source, path="test_sample.py")
            self.assertTrue(result["completed"], result)
            self.assertEqual(result["passed"], passed, result)
            self.assertEqual(result["exit_code"], code, result)

    @POSIX_ONLY
    def test_profile_timeout_and_output_limit(self):
        result = self.check("profile", "sum(range(100))\n")
        self.assertTrue(result["passed"], result)
        self.assertIn("function calls", result["output"])
        timed = self.check("profile", "import time\ntime.sleep(10)\n", timeout=1)
        self.assertFalse(timed["completed"])
        self.assertFalse(timed["passed"])
        with patch.object(runner, "MAX_OUTPUT_BYTES", 1024):
            flooded = self.check("profile", "print('x' * 100000)\n")
        self.assertTrue(flooded["truncated"])
        self.assertFalse(flooded["passed"])
        self.assertLessEqual(len(flooded["output"]), 1024)

    def test_check_rejects_target_outside_workspace(self):
        workspace_id = self.create()
        for path in ("../../seed/app.py", str(self.seed / "app.py")):
            with self.assertRaises(ValueError):
                runner._check({"workspace_id": workspace_id, "tool_id": "profile", "path": path})

    @POSIX_ONLY
    def test_unittest_discovery_requires_tests(self):
        workspace_id = self.create()
        result = runner._check({"workspace_id": workspace_id, "tool_id": "unittest"})
        self.assertFalse(result["passed"], result)
        runner._write({"workspace_id": workspace_id, "path": "test_sample.py", "content":
                       "import unittest\nclass Example(unittest.TestCase):\n"
                       "    def test_ok(self): self.assertEqual(2 + 2, 4)\n"})
        result = runner._check({"workspace_id": workspace_id, "tool_id": "unittest"})
        self.assertTrue(result["passed"], result)

    @POSIX_ONLY
    @unittest.skipUnless(runner.importlib.util.find_spec("bandit"), "Bandit not installed")
    def test_bandit_rejects_nested_symlink_escape(self):
        workspace_id = self.create()
        repo = self.workspaces / workspace_id / "repo"
        (repo / "outside.py").symlink_to(self.seed / "app.py")
        with self.assertRaises(ValueError):
            runner._check({"workspace_id": workspace_id, "tool_id": "bandit"})

    @POSIX_ONLY
    def test_run_preserves_stderr_for_existing_callers(self):
        workspace_id = self.create()
        python_exe = "python" if shutil.which("python") else "python3"
        result = runner._run({"workspace_id": workspace_id, "argv": [
            python_exe, "-c", "import sys; print('diagnostic', file=sys.stderr); sys.exit(2)"]})
        self.assertFalse(result["ok"])
        self.assertEqual(result["exit_code"], 2)
        self.assertIn("diagnostic", result["output"])


class ControlPlanePresetTests(unittest.TestCase):
    def test_handler_forwards_preset_parameters(self):
        tree = ast.parse((ROOT / "control-plane/cp/tool.py").read_text(encoding="utf-8"))
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == "_tool_code_sandbox")
        backend = FakeBackend("docker", True)
        # `code_sandbox` arriva per contesto: lo scope isolato ne ha bisogno con
        # la stessa forma, o il test eserciterebbe un percorso che in produzione
        # non esiste.
        namespace = {"_contesto": SimpleNamespace(code_sandbox=backend), "json": json,
                     "push_log": lambda *args, **kwargs: None, "SandboxUnavailable": SandboxUnavailable}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "handler", "exec"), namespace)
        namespace["_tool_code_sandbox"]({"action": "check", "tool_id": "bandit",
                                         "path": "shared", "workspace_id": "docker:12345678"})
        self.assertEqual(backend.calls[-1], ("check", {"tool_id": "bandit", "path": "shared",
                                                        "workspace_id": "docker:12345678"}))

    def test_handler_forwards_verify_plan(self):
        tree = ast.parse((ROOT / "control-plane/cp/tool.py").read_text(encoding="utf-8"))
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == "_tool_code_sandbox")
        backend = FakeBackend("docker", True)
        # `code_sandbox` arriva per contesto: lo scope isolato ne ha bisogno con
        # la stessa forma, o il test eserciterebbe un percorso che in produzione
        # non esiste.
        namespace = {"_contesto": SimpleNamespace(code_sandbox=backend), "json": json,
                     "push_log": lambda *args, **kwargs: None, "SandboxUnavailable": SandboxUnavailable}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "handler", "exec"), namespace)
        plan = [{"tool_id": "ruff", "path": "shared"}, {"tool_id": "bandit", "path": "shared"}]
        namespace["_tool_code_sandbox"]({"action": "verify", "checks": plan,
                                         "workspace_id": "docker:12345678"})
        self.assertEqual(backend.calls[-1], ("verify", {"checks": plan,
                                                        "workspace_id": "docker:12345678"}))


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.exchange = Path(self.temp.name)
        (self.exchange / "jobs").mkdir()
        (self.exchange / "results").mkdir()
        (self.exchange / "heartbeat").write_text(str(time.time()), encoding="ascii")

    def test_disabled_client_never_submits_jobs(self):
        client = CodeSandboxClient(self.exchange, enabled=False)
        with self.assertRaises(SandboxUnavailable):
            client.call("status")
        self.assertEqual(list((self.exchange / "jobs").iterdir()), [])

    def test_file_queue_round_trip(self):
        client = CodeSandboxClient(self.exchange, enabled=True)

        def respond():
            deadline = time.time() + 2
            while time.time() < deadline:
                jobs = list((self.exchange / "jobs").glob("*.json"))
                if jobs:
                    job = json.loads(jobs[0].read_text(encoding="utf-8"))
                    (self.exchange / "results" / f"{job['job_id']}.json").write_text(
                        json.dumps({"ok": True, "job_id": job["job_id"]}), encoding="utf-8",
                    )
                    return
                time.sleep(0.01)

        thread = threading.Thread(target=respond)
        thread.start()
        result = client.call("status", timeout=2)
        thread.join()
        self.assertTrue(result["ok"])
        self.assertEqual(list((self.exchange / "results").iterdir()), [])


class FakeBackend:
    default_timeout = 30

    def __init__(self, name, available):
        self.name, self.available = name, available
        self.calls = []

    def status(self):
        return {"enabled": True, "available": self.available, "backend": self.name}

    def call(self, action, arguments=None, timeout=None):
        self.calls.append((action, dict(arguments or {})))
        return {"ok": True, "workspace_id": "workspace-1"}


class HybridClientTests(unittest.TestCase):
    def test_development_checks_stay_on_explicit_backend(self):
        primary, fallback = FakeBackend("sbx", True), FakeBackend("docker", True)
        client = HybridCodeSandboxClient(primary, fallback, enabled=True)
        created = client.call("create", {"backend": "docker"})
        self.assertEqual(created["workspace_id"], "docker:workspace-1")
        client.call("catalog")
        client.call("check", {"workspace_id": created["workspace_id"], "tool_id": "bandit"})
        self.assertEqual(fallback.calls[-1][0], "check")
        unsupported = client.call("check", {"workspace_id": "sbx:workspace-1"})
        self.assertFalse(unsupported["passed"])
        unsupported = client.call("verify", {"workspace_id": "sbx:workspace-1", "checks": []})
        self.assertFalse(unsupported["passed"])
        self.assertEqual(primary.calls, [])

    def test_prefers_sbx_and_routes_tagged_workspace_back_to_it(self):
        primary, fallback = FakeBackend("sbx", True), FakeBackend("docker", True)
        client = HybridCodeSandboxClient(primary, fallback, enabled=True)
        created = client.call("create", {"label": "nightly"})
        self.assertEqual(created["workspace_id"], "sbx:workspace-1")
        client.call("diff", {"workspace_id": created["workspace_id"]})
        self.assertEqual(primary.calls[-1][1]["workspace_id"], "workspace-1")
        self.assertEqual(fallback.calls, [])

    def test_falls_back_when_creating_a_new_workspace(self):
        primary, fallback = FakeBackend("sbx", False), FakeBackend("docker", True)
        client = HybridCodeSandboxClient(primary, fallback, enabled=True)
        created = client.call("create", {})
        self.assertEqual(created["workspace_id"], "docker:workspace-1")
        self.assertEqual(len(fallback.calls), 1)


class ComposeIsolationTests(unittest.TestCase):
    def test_both_profiles_enforce_offline_container_boundaries(self):
        for filename in ("docker-compose.yml", "docker-compose.windows.yml"):
            text = (ROOT / filename).read_text(encoding="utf-8")
            match = re.search(r"(?ms)^  code-sandbox:\n.*?(?=^  \S|\Z)", text)
            self.assertIsNotNone(match, f"missing code-sandbox service in {filename}")
            section = match.group(0)
            with self.subTest(filename=filename):
                self.assertIn("network_mode: none", section)
                self.assertIn("read_only: true", section)
                self.assertIn("no-new-privileges:true", section)
                self.assertNotIn("docker.sock", section)

    def test_docker_build_context_excludes_runtime_secrets(self):
        text = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        self.assertIn(".env*", text)
        self.assertIn("data", text)
        self.assertIn(".git", text)


if __name__ == "__main__":
    unittest.main()
