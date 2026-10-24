#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Trend Scout via Agent-Reach for HyperSpace dreams, art, and inspiration.

Queries open web, YouTube, Reddit, and GitHub through Agent-Reach (zero-API-fee)
to harvest thematic trends and cultural echoes, saving privacy-preserving snippets
for Anna & Aurora's nocturnal dream loop and creative generation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Paths
DEFAULT_OUT_PATH = Path("data/control-plane/trend_inspirations.json")
AGENT_REACH_BIN = os.getenv("AGENT_REACH_BIN") or shutil.which("agent-reach") or "/Users/opo/.local/bin/agent-reach"

# Default thematic queries for dream & creative inspiration
DEFAULT_THEMES = [
    {"topic": "artificial intelligence philosophy", "channel": "reddit", "query": "synthetic consciousness philosophy"},
    {"topic": "generative art & poetry", "channel": "web", "query": "generative art algorithmic poetry aesthetics"},
    {"topic": "cosmic space exploration", "channel": "youtube", "query": "space exploration cosmos discovery 2026"},
    {"topic": "open agent architectures", "channel": "github", "query": "autonomous agent architectures open source"},
]

_CLEAN_SPACES = re.compile(r"\s+")
_STRIP_URLS = re.compile(r"https?://\S+", re.IGNORECASE)
_STRIP_TAGS = re.compile(r"<[^>]+>")


def find_agent_reach() -> str | None:
    """Return path to executable agent-reach binary if available."""
    if os.path.isfile(AGENT_REACH_BIN) and os.access(AGENT_REACH_BIN, os.X_OK):
        return str(AGENT_REACH_BIN)
    found = shutil.which("agent-reach")
    return found if found and os.access(found, os.X_OK) else None


def run_agent_reach(args: list[str], timeout: int = 30) -> dict:
    """Execute agent-reach command and return parsed JSON."""
    bin_path = find_agent_reach()
    if not bin_path:
        return {"ok": False, "error": f"agent-reach executable not found at '{AGENT_REACH_BIN}' or PATH"}
    cmd = [bin_path] + args
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if not proc.stdout.strip():
            return {"ok": False, "error": f"Empty stdout, stderr: {proc.stderr[:200]}"}
        return json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Timeout expired ({timeout}s) running {cmd}"}
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"JSON decode error: {exc}", "raw": proc.stdout[:300]}
    except Exception as exc:
        return {"ok": False, "error": f"Execution error: {type(exc).__name__}: {exc}"}


def clean_snippet(text: str, max_chars: int = 240) -> str:
    """Normalize and redact unwanted noise from trend text for dream prompts."""
    text = _STRIP_TAGS.sub("", str(text or ""))
    text = _STRIP_URLS.sub("", text)
    text = _CLEAN_SPACES.sub(" ", text).strip()
    return text[:max_chars].rstrip()


def harvest_trend(channel: str, query: str, limit: int = 3) -> list[dict]:
    """Harvest snippets from a single channel query."""
    args = [channel, "search", query, "--limit", str(limit)]
    raw = run_agent_reach(args, timeout=25)
    items = []
    if not raw.get("ok"):
        return items
    for it in raw.get("items") or []:
        title = clean_snippet(it.get("title", ""), max_chars=120)
        snippet = clean_snippet(it.get("text", ""), max_chars=200)
        if title or snippet:
            summary = f"{title}: {snippet}" if title and snippet else (title or snippet)
            items.append({
                "channel": channel,
                "title": title,
                "snippet": snippet,
                "summary": summary,
                "url": it.get("url", ""),
                "ts": int(time.time()),
            })
    return items


def harvest_all_themes(themes: list[dict] | None = None, limit_per_theme: int = 2) -> dict:
    """Scout all default themes across channels."""
    themes = themes or DEFAULT_THEMES
    results: list[dict] = []
    errors: list[str] = []

    for th in themes:
        ch = th.get("channel", "web")
        q = th.get("query", "")
        topic = th.get("topic", q)
        harvested = harvest_trend(ch, q, limit=limit_per_theme)
        if harvested:
            for item in harvested:
                item["topic"] = topic
            results.extend(harvested)
        else:
            errors.append(f"Failed or empty on {ch}:{q}")

    inspirations = []
    for r in results:
        text = r.get("summary") or r.get("snippet") or r.get("title")
        if text and len(text) > 15:
            inspirations.append(text)

    return {
        "ok": len(results) > 0,
        "scouted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_items": len(results),
        "inspirations": inspirations[:10],
        "items": results,
        "errors": errors,
    }


def save_inspirations(data: dict, out_path: Path = DEFAULT_OUT_PATH) -> bool:
    """Persist harvested inspirations for the nocturnal dream loop."""
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as exc:
        print(f"[!] Errore salvataggio {out_path}: {exc}", file=sys.stderr)
        return False


def doctor() -> dict:
    """Run agent-reach doctor diagnostics."""
    return run_agent_reach(["doctor"])


def main():
    parser = argparse.ArgumentParser(description="HyperSpace Trend Scout via Agent-Reach")
    parser.add_argument("--doctor", action="store_true", help="Esegui agent-reach doctor")
    parser.add_argument("--query", "-q", type=str, help="Query personalizzata da cercare")
    parser.add_argument("--channel", "-c", type=str, default="web", choices=["web", "youtube", "reddit", "github", "v2ex"], help="Canale da interrogare")
    parser.add_argument("--limit", "-l", type=int, default=3, help="Numero massimo di risultati")
    parser.add_argument("--save", action="store_true", help="Salva l'output in data/control-plane/trend_inspirations.json")
    parser.add_argument("--json", action="store_true", help="Stampa l'output grezzo in JSON")
    args = parser.parse_args()

    bin_path = find_agent_reach()
    if not bin_path:
        print(f"❌ agent-reach non trovato in {AGENT_REACH_BIN} o PATH.", file=sys.stderr)
        sys.exit(1)

    if args.doctor:
        doc = doctor()
        print(json.dumps(doc, indent=2, ensure_ascii=False))
        sys.exit(0 if doc.get("ok") else 1)

    if args.query:
        print(f"[*] Scouting su '{args.channel}': {args.query}...")
        items = harvest_trend(args.channel, args.query, limit=args.limit)
        payload = {
            "ok": True,
            "scouted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_items": len(items),
            "inspirations": [it["summary"] for it in items if it.get("summary")],
            "items": items,
        }
    else:
        print("[*] Esecuzione Trend Scouting multi-canale (temi predefiniti)...")
        payload = harvest_all_themes(limit_per_theme=args.limit)

    if args.save:
        ok = save_inspirations(payload)
        if ok:
            print(f"✅ Ispirazioni salvate con successo in {DEFAULT_OUT_PATH} ({len(payload.get('inspirations', []))} elementi)")
        else:
            print(f"❌ Fallito salvataggio in {DEFAULT_OUT_PATH}")

    if args.json or not args.save:
        print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
