# SPDX-License-Identifier: Apache-2.0
"""Offline code workspace runner.

The runner has no network and no Docker socket. It consumes JSON jobs from a
shared volume, works only in disposable copies of the sanitized image seed,
and never writes back to the source checkout.
"""
from __future__ import annotations

import difflib
import fnmatch
import json
import importlib.metadata
import importlib.util
import os
import re
import selectors
import signal
import stat
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path


SEED = Path(os.getenv("SANDBOX_SEED_DIR", "/seed"))
EXCHANGE = Path(os.getenv("SANDBOX_EXCHANGE_DIR", "/exchange"))
WORKSPACES = Path(os.getenv("SANDBOX_WORKSPACE_DIR", "/workspaces"))
MAX_WORKSPACES = max(1, int(os.getenv("SANDBOX_MAX_WORKSPACES", "12")))
WORKSPACE_TTL_DAYS = max(1, int(os.getenv("SANDBOX_WORKSPACE_TTL_DAYS", "30")))
GC_INTERVAL_S = 3600
MAX_FILE_BYTES = max(1024, int(os.getenv("SANDBOX_MAX_FILE_BYTES", "1048576")))
MAX_OUTPUT_BYTES = max(4096, int(os.getenv("SANDBOX_MAX_OUTPUT_BYTES", "131072")))
MAX_DIFF_BYTES = max(4096, int(os.getenv("SANDBOX_MAX_DIFF_BYTES", "262144")))
MAX_TIMEOUT = max(1, int(os.getenv("SANDBOX_MAX_TIMEOUT", "120")))
WORKSPACE_RE = re.compile(r"^[a-f0-9-]{8,64}$")
ALLOWED_EXECUTABLES = {
    item.strip() for item in os.getenv(
        "SANDBOX_ALLOWED_EXECUTABLES",
        "python,python3,node,npm,npx,pytest,unittest,git",
    ).split(",") if item.strip()
}


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def _audit(job: dict, result: dict) -> None:
    record = {
        "ts": time.time(),
        "job_id": job.get("job_id"),
        "action": job.get("action"),
        "workspace_id": job.get("workspace_id"),
        "ok": result.get("ok", False),
    }
    if job.get("action") == "read":
        path = str(job.get("path") or "")
        parts = Path(path).parts
        record["path_kind"] = ("empty" if not path else
                               "absolute" if Path(path).is_absolute() else
                               "parent" if ".." in parts else
                               "repo_prefix" if parts and parts[0] in {"repo", "seed"} else
                               "relative")
    if result.get("error_code"):
        record["error_code"] = result["error_code"]
    with (EXCHANGE / "audit.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


class WorkspaceMissing(FileNotFoundError):
    """The referenced workspace does not exist, as opposed to a file inside it.

    Without this distinction a wrong `workspace_id` looked identical to a wrong
    `path` (both `path_missing`), so an 8B model kept "fixing" the path while the
    real error was the id. Measured on the PDF trial: `create` returned one id and
    the next `write` used a different, non-existent one.
    """


class PathMissing(FileNotFoundError):
    """A path inside an existing workspace does not exist."""


def _workspace(workspace_id: str) -> Path:
    if not WORKSPACE_RE.fullmatch(str(workspace_id or "")):
        raise ValueError("invalid workspace_id")
    root = (WORKSPACES / workspace_id).resolve()
    if not root.is_dir():
        raise WorkspaceMissing("workspace not found")
    return root


def _safe_path(root: Path, relative: str, *, must_exist: bool = False) -> Path:
    relative = str(relative or ".")
    if len(relative) > 500 or Path(relative).is_absolute():
        raise ValueError("invalid relative path")
    # Resolve without strict mode first, so containment is checked before the
    # host filesystem can leak whether an escaped path exists.
    target = (root / relative).resolve(strict=False)
    if target != root and root not in target.parents:
        raise ValueError("path escapes workspace")
    if must_exist and not target.exists():
        raise PathMissing("path not found")
    return target


def _ignore(_directory, names):
    ignored = set()
    for name in names:
        if name in {".git", ".env", ".worktrees", "data", "node_modules", "__pycache__"}:
            ignored.add(name)
        elif name.endswith((".pyc", ".pyo")):
            ignored.add(name)
    return ignored


def _gc_expired(now: float | None = None) -> list[str]:
    """Svuota i workspace piu' vecchi di WORKSPACE_TTL_DAYS giorni.

    L'eta' e' `created_at` dei metadati (data di modifica della cartella se i
    metadati mancano o sono illeggibili). Ritorna gli id eliminati.
    """
    now = time.time() if now is None else now
    limit = WORKSPACE_TTL_DAYS * 86400
    removed = []
    for root in WORKSPACES.iterdir():
        if not root.is_dir() or not WORKSPACE_RE.match(root.name):
            continue
        try:
            created = float(json.loads((root / "metadata.json").read_text(encoding="utf-8"))["created_at"])
        except (OSError, ValueError, KeyError, TypeError):
            created = root.stat().st_mtime
        if now - created > limit:
            shutil.rmtree(root, ignore_errors=True)
            removed.append(root.name)
    return removed


def _create(job: dict) -> dict:
    _gc_expired()
    existing = [item for item in WORKSPACES.iterdir() if item.is_dir()]
    if len(existing) >= MAX_WORKSPACES:
        raise RuntimeError("workspace limit reached; discard an old workspace")
    workspace_id = str(uuid.uuid4())
    root = WORKSPACES / workspace_id
    base = root / "base"
    repo = root / "repo"
    shutil.copytree(SEED, base, ignore=_ignore, symlinks=True)
    shutil.copytree(base, repo, symlinks=True)
    # copytree preserves the image seed's read-only modes. The runner owns the
    # copies: restore directory writes for cleanup and repo file writes for tools.
    # Never chmod symlinks, whose targets may be outside this workspace.
    for tree in (base, repo):
        for path in [tree, *tree.rglob("*")]:
            if path.is_symlink():
                continue
            if path.is_dir() or tree == repo:
                mode = stat.S_IMODE(path.stat().st_mode) | stat.S_IRUSR | stat.S_IWUSR
                if path.is_dir():
                    mode |= stat.S_IXUSR
                path.chmod(mode)
    metadata = {
        "workspace_id": workspace_id,
        "label": str(job.get("label", ""))[:120],
        "created_at": time.time(),
    }
    _atomic_json(root / "metadata.json", metadata)
    return {"ok": True, **metadata}


def _reuse(job: dict) -> dict:
    """Restituisce un workspace ESISTENTE invece di crearne un altro.

    Il workspace usa-e-getta e' la memoria condivisa della missione: un passo che
    ricreava il workspace buttava via i file dei passi a monte e il PDF finiva in
    un sandbox diverso da quello verificato. Misurato il 2026-10-07: quattro task
    coder, quattro workspace, zero PDF nel diff finale. `reuse` e' la `create`
    idempotente della catena: stesso contratto di ritorno, nessun copytree.
    """
    root = _workspace(job.get("workspace_id"))
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    return {"ok": True, **metadata, "reused": True}


def _list(job: dict) -> dict:
    repo = _workspace(job.get("workspace_id")) / "repo"
    pattern = str(job.get("pattern") or "*")[:200]
    limit = max(1, min(int(job.get("limit", 200)), 1000))
    files = []
    for path in repo.rglob("*"):
        if path.is_file():
            relative = path.relative_to(repo).as_posix()
            if fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(path.name, pattern):
                files.append(relative)
                if len(files) >= limit:
                    break
    return {"ok": True, "files": files, "truncated": len(files) >= limit}


def _read(job: dict) -> dict:
    repo = _workspace(job.get("workspace_id")) / "repo"
    path = _safe_path(repo, job.get("path"), must_exist=True)
    if not path.is_file():
        raise ValueError("path is not a file")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("file exceeds read limit")
    return {"ok": True, "path": path.relative_to(repo).as_posix(),
            "content": path.read_text(encoding="utf-8", errors="replace")}


def _write(job: dict) -> dict:
    repo = _workspace(job.get("workspace_id")) / "repo"
    path = _safe_path(repo, job.get("path"))
    content = str(job.get("content", ""))
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_FILE_BYTES:
        raise ValueError("content exceeds write limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.is_symlink():
        raise ValueError("refusing to write through symlink")
    temporary = path.with_suffix(path.suffix + ".sandbox-tmp")
    # Preserve the supplied line endings byte-for-byte.  In particular, a
    # unified diff may contain CRLF context from a Windows checkout; implicit
    # text-mode conversion would turn it into CRCRLF and make git apply fail.
    temporary.write_text(content, encoding="utf-8", newline="")
    temporary.replace(path)
    return {"ok": True, "path": path.relative_to(repo).as_posix(), "bytes": len(encoded)}


def _replace(job: dict) -> dict:
    repo = _workspace(job.get("workspace_id")) / "repo"
    path = _safe_path(repo, job.get("path"), must_exist=True)
    old = str(job.get("old", ""))
    new = str(job.get("new", ""))
    if not old:
        raise ValueError("old text is required")
    text = path.read_text(encoding="utf-8")
    occurrences = text.count(old)
    expected = int(job.get("expected_occurrences", 1))
    if occurrences != expected:
        raise ValueError(f"expected {expected} occurrence(s), found {occurrences}")
    job = dict(job, content=text.replace(old, new, expected))
    return {**_write(job), "replacements": expected}


def _capture(argv, cwd, env, timeout):
    """Bound output while reading and terminate the whole job on timeout/overflow."""
    started = time.monotonic()
    buffers = {"output": bytearray(), "stderr": bytearray()}
    error = None
    with subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          start_new_session=True) as process:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "output")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            try:
                while selector.get_map() or process.poll() is None:
                    remaining = timeout - (time.monotonic() - started)
                    if remaining <= 0:
                        error = "command timed out"
                        break
                    for key, _ in selector.select(min(remaining, 0.1)):
                        chunk = os.read(key.fileobj.fileno(), 8192)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        room = MAX_OUTPUT_BYTES - sum(map(len, buffers.values()))
                        buffers[key.data].extend(chunk[:room])
                        if len(chunk) > room:
                            error = "output limit exceeded"
                            break
                    if error:
                        break
            finally:
                # Also clean up background descendants after a successful parent exit.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
    result = {name: value.decode("utf-8", errors="replace")
              for name, value in buffers.items()}
    result.update(ok=not error and process.returncode == 0,
                  completed=not bool(error), exit_code=process.returncode,
                  truncated=error == "output limit exceeded",
                  duration_ms=round((time.monotonic() - started) * 1000))
    if error:
        result["error"] = error
    return result


def _run(job: dict) -> dict:
    root = _workspace(job.get("workspace_id"))
    repo = root / "repo"
    argv = job.get("argv")
    if not isinstance(argv, list) or not argv or len(argv) > 32:
        raise ValueError("argv must be a non-empty list of at most 32 items")
    argv = [str(item)[:1000] for item in argv]
    executable = Path(argv[0]).name
    if argv[0] != executable or executable not in ALLOWED_EXECUTABLES:
        raise ValueError(f"executable not allowed: {argv[0]}")
    cwd = _safe_path(repo, job.get("cwd", "."), must_exist=True)
    if not cwd.is_dir():
        raise ValueError("cwd is not a directory")
    timeout = max(1, min(int(job.get("timeout", 30)), MAX_TIMEOUT))
    env = {
        "PATH": os.getenv("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(root),
        "TMPDIR": "/tmp",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "npm_config_cache": "/tmp/npm-cache",
        "NO_COLOR": "1",
    }
    result = _capture(argv, cwd, env, timeout)
    # Preserve the legacy run contract (diagnostics in output).
    result["output"] += result.pop("stderr")
    return result


TOOL_MODULES = {"pytest": "pytest", "unittest": "unittest",
                "profile": "cProfile", "bandit": "bandit", "ruff": "ruff"}


def _python_files(repo: Path, target: Path) -> list[Path]:
    """Return scan candidates and reject symlink escapes before a tool sees them."""
    if target.is_file():
        if target.suffix != ".py":
            raise ValueError("path must be a Python file or a directory")
        return [target]
    if not target.is_dir():
        raise ValueError("path is not a file or directory")
    files = []
    for path in target.rglob("*"):
        if path.is_symlink():
            _safe_path(repo, path.relative_to(repo).as_posix(), must_exist=True)
        elif path.is_file() and path.suffix == ".py":
            files.append(path)
    if not files:
        raise ValueError("no Python files found")
    return files


def _catalog(_job: dict) -> dict:
    items = []
    for tool, module in TOOL_MODULES.items():
        available = (Path(sys.executable).name in ALLOWED_EXECUTABLES
                     and importlib.util.find_spec(module) is not None)
        try:
            version = importlib.metadata.version(module) if tool in {"pytest", "bandit", "ruff"} else sys.version.split()[0]
        except importlib.metadata.PackageNotFoundError:
            version = None
        items.append({"tool_id": tool, "available": available, "version": version})
    return {"ok": True, "tools": items, "backend": "docker", "network": "disabled"}


def _check(job: dict) -> dict:
    tool = job.get("tool_id")
    if tool not in TOOL_MODULES:
        raise ValueError("unknown tool_id")
    root = _workspace(job.get("workspace_id"))
    repo = root / "repo"
    target = _safe_path(repo, job.get("path", "."), must_exist=True)
    capability = next(item for item in _catalog({})["tools"] if item["tool_id"] == tool)
    result = {"tool_id": tool, "version": capability["version"], "findings": [],
              "passed": False, "completed": False, "ok": False, "exit_code": None,
              "truncated": False, "duration_ms": 0}
    if not capability["available"]:
        return {**result, "error": "tool unavailable; rebuild the sandbox image"}
    argv = [sys.executable] + (["-I"] if tool == "bandit" else []) + ["-m", TOOL_MODULES[tool]]
    if tool == "pytest":
        argv += ["-q", "-p", "no:cacheprovider", "--", str(target)]
    elif tool == "unittest":
        if not target.is_dir():
            raise ValueError("unittest path must be a discovery directory")
        argv += ["discover", "-s", str(target)]
    elif tool == "profile":
        if not target.is_file() or target.suffix != ".py":
            raise ValueError("profile path must be a Python file")
        argv += ["-s", "cumulative", str(target)]
    elif tool == "bandit":
        _python_files(repo, target)
        # Ignore repo-controlled suppressions and do not mix diagnostics into JSON.
        argv += ["-r", "-f", "json", "--ignore-nosec", "--ini", os.devnull, str(target)]
    else:
        _python_files(repo, target)
        argv += ["check", "--no-cache", "--output-format", "json", str(target)]
    env = {"PATH": os.defpath, "HOME": str(root), "TMPDIR": "/tmp",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1",
           "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "NO_COLOR": "1"}
    timeout = max(1, min(int(job.get("timeout", 30)), MAX_TIMEOUT))
    execution = _capture(argv, repo, env, timeout)
    result.update(execution)
    result["passed"] = execution["ok"]
    if tool == "unittest" and execution["completed"]:
        summary = re.search(r"^Ran (\d+) tests? in ", execution["stderr"], re.M)
        if not summary or int(summary.group(1)) == 0:
            result.update(ok=False, passed=False, error="no verified unittest results")
    if tool not in {"bandit", "ruff"} or not execution["completed"]:
        return result
    try:
        report = json.loads(execution["output"])
        if tool == "ruff":
            if not isinstance(report, list):
                raise ValueError("invalid report structure")
            findings = []
            for issue in report:
                path = Path(issue["filename"])
                if not path.is_absolute():
                    path = repo / path
                relative = path.resolve().relative_to(repo.resolve()).as_posix()
                location = issue.get("location", {})
                line = location.get("row")
                if not isinstance(line, int) or line < 1 or not path.is_file():
                    raise ValueError("invalid finding location")
                findings.append({"path": relative, "line": line, "rule": issue["code"],
                                 "message": issue["message"]})
            completed = execution["exit_code"] in {0, 1}
            result.update(findings=findings, completed=completed, ok=completed,
                          passed=completed and not findings and execution["exit_code"] == 0)
            result.pop("output", None)
            if not completed:
                result["error"] = "incomplete Ruff scan"
            return result
        if not isinstance(report, dict) or not isinstance(report.get("results"), list) or not isinstance(report.get("errors"), list):
            raise ValueError("invalid report structure")
        metrics = report.get("metrics", {}).get("_totals", {})
        if not isinstance(metrics.get("loc"), (int, float)) or metrics["loc"] <= 0:
            raise ValueError("no Python lines scanned")
        findings = []
        for issue in report["results"]:
            path = Path(issue["filename"])
            if not path.is_absolute():
                path = repo / path
            relative = path.resolve().relative_to(repo.resolve()).as_posix()
            line = issue["line_number"]
            if not isinstance(line, int) or line < 1 or not path.is_file():
                raise ValueError("invalid finding location")
            findings.append({"path": relative, "line": line, "rule": issue["test_id"],
                             "severity": issue["issue_severity"],
                             "confidence": issue["issue_confidence"],
                             "message": issue["issue_text"]})
        completed = execution["exit_code"] in {0, 1} and not report["errors"]
        result.update(findings=findings, completed=completed, ok=completed,
                      passed=completed and not findings and execution["exit_code"] == 0,
                      scan_errors=report["errors"])
        # Do not forward source snippets embedded in Bandit's raw report.
        result.pop("output", None)
        if not completed:
            result["error"] = "incomplete Bandit scan"
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        result.update(ok=False, completed=False, passed=False,
                      error=f"invalid Bandit report: {error}")
        result.pop("output", None)
    return result


def _verify(job: dict) -> dict:
    """Run an explicit, bounded verification plan inside one disposable workspace."""
    checks = job.get("checks")
    if not isinstance(checks, list) or not 1 <= len(checks) <= 6:
        raise ValueError("checks must contain between one and six checks")
    workspace_id = job.get("workspace_id")
    results = []
    total_duration = 0
    for requested in checks:
        if not isinstance(requested, dict):
            raise ValueError("each check must be an object")
        tool_id, path = requested.get("tool_id"), requested.get("path", ".")
        if tool_id not in TOOL_MODULES or not isinstance(path, str):
            raise ValueError("each check requires a known tool_id and path")
        check_job = {"workspace_id": workspace_id, "tool_id": tool_id, "path": path}
        if "timeout" in requested:
            check_job["timeout"] = requested["timeout"]
        try:
            checked = _check(check_job)
        except (OSError, ValueError, TypeError) as error:
            checked = {"tool_id": tool_id, "path": path, "ok": False, "completed": False,
                       "passed": False, "findings": [], "error": str(error), "duration_ms": 0}
        checked["path"] = path
        total_duration += int(checked.get("duration_ms", 0))
        results.append(checked)
    complete = all(item.get("completed") for item in results)
    passed = complete and all(item.get("passed") for item in results)
    return {"ok": complete, "completed": complete, "passed": passed,
            "checks": results, "duration_ms": total_duration}


def _file_map(root: Path) -> dict[str, Path]:
    return {path.relative_to(root).as_posix(): path for path in root.rglob("*")
            if path.is_file() and not path.is_symlink()}


def _diff(job: dict) -> dict:
    root = _workspace(job.get("workspace_id"))
    base, repo = root / "base", root / "repo"
    base_files, repo_files = _file_map(base), _file_map(repo)
    chunks = []
    changed = []
    for relative in sorted(set(base_files) | set(repo_files)):
        before_path, after_path = base_files.get(relative), repo_files.get(relative)
        before = before_path.read_bytes() if before_path else b""
        after = after_path.read_bytes() if after_path else b""
        if before == after:
            continue
        changed.append(relative)
        try:
            before_lines = before.decode("utf-8").splitlines(keepends=True)
            after_lines = after.decode("utf-8").splitlines(keepends=True)
        except UnicodeDecodeError:
            chunks.append(f"Binary files differ: {relative}\n")
            continue
        chunks.extend(difflib.unified_diff(
            before_lines, after_lines,
            fromfile=f"a/{relative}", tofile=f"b/{relative}", n=3,
        ))
        if sum(len(item.encode("utf-8")) for item in chunks) >= MAX_DIFF_BYTES:
            break
    text = "".join(chunks)
    encoded = text.encode("utf-8")
    return {"ok": True, "changed_files": changed, "diff": encoded[:MAX_DIFF_BYTES].decode("utf-8", errors="ignore"),
            "truncated": len(encoded) > MAX_DIFF_BYTES}


def _discard(job: dict) -> dict:
    root = _workspace(job.get("workspace_id"))
    shutil.rmtree(root)
    return {"ok": True, "discarded": job.get("workspace_id")}


def _status(_job: dict) -> dict:
    workspaces = []
    for root in WORKSPACES.iterdir():
        metadata = root / "metadata.json"
        if root.is_dir() and metadata.exists():
            try:
                workspaces.append(json.loads(metadata.read_text(encoding="utf-8")))
            except ValueError:
                pass
    return {"ok": True, "network": "disabled", "docker_socket": False,
            "workspace_count": len(workspaces), "workspace_limit": MAX_WORKSPACES,
            "allowed_executables": sorted(ALLOWED_EXECUTABLES), "workspaces": workspaces}


def _inspect(job: dict) -> dict:
    """Probe read-only dell'artifact: fatti di formato, nessun modello nel mezzo.

    Per un PDF riporta la firma `%PDF`, il numero di pagine e quanti caratteri si
    estraggono con pypdf, cosi' una missione si giudica sul file e non sulla prosa
    del worker. pypdf e' opzionale: senza di lui firma e dimensione parlano ancora.
    """
    repo = _workspace(job.get("workspace_id")) / "repo"
    path = _safe_path(repo, job.get("path"), must_exist=True)
    if not path.is_file():
        raise ValueError("path is not a file")
    with path.open("rb") as stream:
        head = stream.read(8)
    magic = head.startswith(b"%PDF-")
    result = {"ok": True, "path": path.relative_to(repo).as_posix(),
              "size": path.stat().st_size, "kind": "pdf" if magic else "other",
              "magic_ok": magic, "pages": None, "text_chars": None,
              "pdf_reader": False}
    if not magic:
        return result
    try:
        import pypdf
    except ImportError:
        return result
    try:
        reader = pypdf.PdfReader(str(path))
        pages = reader.pages
        result["pdf_reader"] = True
        result["pages"] = len(pages)
        text = 0
        for page in pages:
            try:
                text += len(page.extract_text() or "")
            except Exception:
                continue
        result["text_chars"] = text
    except Exception as error:
        result["ok"] = False
        result["error"] = f"pypdf could not read the file: {error}"
    return result


ACTIONS = {
    "inspect": _inspect,
    "catalog": _catalog,
    "check": _check,
    "verify": _verify,
    "create": _create,
    "reuse": _reuse,
    "list": _list,
    "read": _read,
    "write": _write,
    "replace": _replace,
    "run": _run,
    "diff": _diff,
    "discard": _discard,
    "status": _status,
}


def _process(path: Path) -> None:
    try:
        job = json.loads(path.read_text(encoding="utf-8"))
        action = str(job.get("action", ""))
        handler = ACTIONS.get(action)
        if not handler:
            raise ValueError(f"unknown action: {action}")
        result = handler(job)
    except Exception as error:
        text = str(error)
        # A missing workspace is NOT a missing file: keep the two codes apart so
        # the model repairs the right thing. A mis-typed id used to surface as
        # `path_missing`, which sent it hunting for a path bug that did not exist.
        if isinstance(error, WorkspaceMissing):
            code = "workspace_missing"
        elif isinstance(error, PathMissing):
            code = "path_missing"
        elif isinstance(error, ValueError) and "workspace_id" in text:
            code = "invalid_workspace"
        elif isinstance(error, ValueError) and any(
                word in text for word in ("path", "relative")):
            code = "invalid_path"
        elif "read limit" in text:
            code = "read_limit"
        else:
            code = "runner_error"
        result = {"ok": False, "error": text or type(error).__name__,
                  "error_code": code}
        try:
            job
        except NameError:
            job = {"job_id": path.stem, "action": "invalid"}
        if code in {"workspace_missing", "invalid_workspace"}:
            result["hint"] = ("That workspace_id does not exist. Call code_sandbox "
                              "with action='create' and pass the exact workspace_id "
                              "it returns to every later action: do not invent, "
                              "shorten or retype the id.")
        elif (job.get("action") in {"read", "list", "inspect"}
                and code in {"path_missing", "invalid_path"}):
            result["hint"] = ("Use the exact path relative to the workspace root, "
                              "for example README.md or docs/mission-control.md. "
                              "Do not prefix /seed, /repo or the workspace ID. "
                              "Use list if the path is uncertain.")
    result["job_id"] = job.get("job_id", path.stem)
    _atomic_json(EXCHANGE / "results" / f"{result['job_id']}.json", result)
    _audit(job, result)
    path.unlink(missing_ok=True)


def main() -> None:
    jobs = EXCHANGE / "jobs"
    results = EXCHANGE / "results"
    jobs.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    WORKSPACES.mkdir(parents=True, exist_ok=True)
    next_gc = 0.0
    while True:
        if time.time() >= next_gc:
            _gc_expired()
            next_gc = time.time() + GC_INTERVAL_S
        (EXCHANGE / "heartbeat").write_text(str(time.time()), encoding="ascii")
        for path in sorted(jobs.glob("*.json")):
            _process(path)
        time.sleep(0.1)


if __name__ == "__main__":
    main()
