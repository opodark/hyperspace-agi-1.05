#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Register HyperSpace on Moltbook once, or inspect its claim status.

The API key is stored outside the repository with owner-only permissions and
is sent only to https://www.moltbook.com/api/v1.

  python3 scripts/moltbook.py register --name HyperSpace --description '...'
  python3 scripts/moltbook.py status
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


BASE = "https://www.moltbook.com/api/v1"
SKILL_URL = "https://www.moltbook.com/skill.md"
DEFAULT_CREDENTIALS = Path.home() / ".config" / "moltbook" / "credentials.json"


def _opener():
    try:
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        context = ssl.create_default_context()
    return urllib.request.build_opener(_NoRedirect(),
                                       urllib.request.HTTPSHandler(context=context))


def _request(url: str, *, method: str = "GET", body: dict | None = None,
             api_key: str = "") -> dict:
    if not url.startswith("https://www.moltbook.com/"):
        raise ValueError("Refusing to contact a noncanonical Moltbook URL")
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    # Do not follow redirects: in particular, never forward a bearer key away
    # from the exact www.moltbook.com origin.
    with _opener().open(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


def _load(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Cannot read credentials file {path}: {exc}") from exc
    if not isinstance(value, dict) or not value.get("api_key"):
        raise RuntimeError(f"Credentials file is invalid: {path}")
    return value


def _save(path: Path, value: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=".moltbook-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _prepare_store(path: Path) -> None:
    """Check that credentials can be stored before making the one-shot POST."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=".moltbook-check-", dir=path.parent)
    os.close(fd)
    os.unlink(temporary)


def _status(credentials: dict) -> dict:
    return _request(BASE + "/agents/status", api_key=credentials["api_key"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "status"))
    parser.add_argument("--name", help="required only for a new registration")
    parser.add_argument("--description", help="required only for a new registration")
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS,
                        help="secure credential file (default: ~/.config/moltbook/credentials.json)")
    args = parser.parse_args()

    try:
        credentials = _load(args.credentials)
        if credentials:
            result = _status(credentials)
            print(f"Moltbook status: {result.get('status', 'unknown')}")
            print(f"Agent: {credentials.get('agent_name', 'unknown')}")
            if result.get("status") == "pending_claim":
                claim_url = credentials.get("claim_url")
                if claim_url:
                    print(f"Claim URL: {claim_url}")
                code = credentials.get("verification_code")
                if code:
                    print(f"Verification code: {code}")
            return 0

        if args.action == "status":
            print(f"No local Moltbook credentials at {args.credentials}; nothing was registered by this command.")
            return 2
        if not args.name or not args.description:
            parser.error("register requires --name and --description")

        # Confirm the credential destination works before the one-shot POST.
        _prepare_store(args.credentials)
    except urllib.error.HTTPError as exc:
        print(f"Moltbook returned HTTP {exc.code}; no success is assumed.")
        return 3
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Moltbook operation failed: {exc}")
        return 3

    try:
        skill_request = urllib.request.Request(SKILL_URL, headers={"Accept": "text/markdown"})
        with _opener().open(skill_request, timeout=15) as response:
            skill_text = response.read(100_000).decode("utf-8")
        if "api/v1/agents/register" not in skill_text or "www.moltbook.com" not in skill_text:
            raise RuntimeError("Official skill did not confirm the expected registration endpoint")
        result = _request(BASE + "/agents/register", method="POST",
                          body={"name": args.name, "description": args.description})
        agent = result.get("agent") or {}
        api_key = str(agent.get("api_key") or "")
        claim_url = str(agent.get("claim_url") or "")
        if not api_key or not claim_url.startswith("https://www.moltbook.com/"):
            raise RuntimeError("Registration response was incomplete; inspect Moltbook account before retrying")
        credentials = {"api_key": api_key, "agent_name": args.name,
                       "claim_url": claim_url,
                       "verification_code": str(agent.get("verification_code") or "")}
        _save(args.credentials, credentials)
        print(f"Registered agent: {args.name}")
        print(f"Credentials saved with mode 0600: {args.credentials}")
        print(f"Claim URL for the human: {claim_url}")
        if credentials["verification_code"]:
            print(f"Verification code: {credentials['verification_code']}")
        print("Status: pending human claim. No heartbeat, post, follow, or comment was sent.")
        return 0
    except urllib.error.HTTPError as exc:
        print(f"Moltbook returned HTTP {exc.code}; no success is assumed and registration was not retried.")
        return 3
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Moltbook operation failed: {exc}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
