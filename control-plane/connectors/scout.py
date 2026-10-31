# SPDX-License-Identifier: Apache-2.0
"""
connectors/scout.py — Trend Scout & Web Research Connector for HyperSpace-AGI
Provides AI agents with zero-cost trend harvesting, web reading, and social search.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from typing import Any
import requests

from .base import BaseConnector

_SPACE = re.compile(r"\s+")
_URL = re.compile(r"https?://\S+", re.IGNORECASE)


class ScoutConnector(BaseConnector):
    """Connettore per trend scouting, lettura web pulita e ricerca social no-key."""

    name: str = "scout"
    REQUIRED_ENV: tuple[str, ...] = ("CONNECTOR_SCOUT_ENABLED",)
    READ_TOOLS: tuple[str, ...] = ("scout_web_read", "scout_get_trends", "scout_harvest_trends")
    WRITE_TOOLS: tuple[str, ...] = ()

    def is_available(self) -> bool:
        # Abilitato se la variabile è esplicitamente accesa ('true', '1', 'yes')
        val = os.getenv("CONNECTOR_SCOUT_ENABLED", "").strip().lower()
        return val in ("true", "1", "yes")

    def __init__(self):
        self.reach_bin = os.getenv("AGENT_REACH_BIN") or shutil.which("agent-reach") or "/Users/opo/.local/bin/agent-reach"

    def get_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "scout_web_read",
                    "description": "Legge qualsiasi pagina web restituendo testo pulito in Markdown (senza pubblicità/cookie wall via Jina/Agent-Reach).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "L'URL pubblico della pagina da leggere."}
                        },
                        "required": ["url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "scout_get_trends",
                    "description": "Restituisce le ultime tendenze culturali e oniriche salvate su HyperSpace per ispirazione e scrittura.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Numero massimo di tendenze da restituire (default 5).", "default": 5}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "scout_harvest_trends",
                    "description": "Avvia una ricognizione di trend su un tema e canale specifico aggiornando il serbatoio delle ispirazioni.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "topic": {"type": "string", "description": "Tema da esplorare (es. 'quantum consciousness', 'generative poetry', 'mycelium network routing')."},
                            "channel": {"type": "string", "description": "Canale di ricerca: 'web', 'reddit', 'youtube', 'github', 'arxiv', 'scholar'.", "default": "web"}
                        },
                        "required": ["topic"]
                    }
                }
            }
        ]

    def _call_reach(self, args: list[str], timeout: int = 25) -> dict:
        if os.path.isfile(self.reach_bin) and os.access(self.reach_bin, os.X_OK):
            try:
                proc = subprocess.run([self.reach_bin] + args, capture_output=True, text=True, timeout=timeout)
                if proc.stdout.strip():
                    return json.loads(proc.stdout)
            except Exception:
                pass
        return {}

    def _read_web(self, url: str) -> str:
        url = str(url or "").strip()
        if not url:
            return json.dumps({"ok": False, "error": "URL mancante"})
        
        # 1. Prova via Agent-Reach se disponibile
        res = self._call_reach(["web", "read", url])
        if res.get("ok") and res.get("items"):
            item = res["items"][0]
            return json.dumps({"ok": True, "title": item.get("title"), "text": item.get("text", "")[:4000]}, ensure_ascii=False)

        # 2. Fallback diretto HTTP su Jina Reader
        try:
            target = f"https://r.jina.ai/{url}"
            resp = requests.get(target, timeout=20, headers={"User-Agent": "HyperSpace-Scout/1.0"})
            if resp.status_code == 200:
                text = resp.text[:4000]
                return json.dumps({"ok": True, "source": "jina-direct", "text": text}, ensure_ascii=False)
            return json.dumps({"ok": False, "error": f"HTTP {resp.status_code} da Jina"})
        except Exception as e:
            return json.dumps({"ok": False, "error": f"Errore lettura: {str(e)}"})

    def _get_trends(self, limit: int = 5) -> str:
        paths = ["/app/data/trend_inspirations.json", "data/control-plane/trend_inspirations.json"]
        found = None
        for p in paths:
            if os.path.isfile(p):
                found = p
                break
        if not found:
            return json.dumps({"ok": True, "inspirations": [], "count": 0, "note": "Nessun trend ancora salvato"})
        try:
            with open(found, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = (data.get("inspirations") or [])[:limit]
            return json.dumps({"ok": True, "inspirations": items, "count": len(items), "scouted_at": data.get("scouted_at")}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    def _harvest(self, topic: str, channel: str = "web") -> str:
        topic = str(topic or "").strip()
        ch = str(channel or "web").strip().lower()

        # Supporto canali scientifici dedicati (arXiv, Google Scholar, OpenAlex)
        if ch in ("arxiv", "scholar", "science", "google_scholar"):
            try:
                from scripts.diagnostics.trend_scout_reach import harvest_trend
                items = harvest_trend(ch, topic, limit=3)
                summaries = [it.get("summary") or it.get("title") for it in items if it.get("summary") or it.get("title")]
                if summaries:
                    return json.dumps({"ok": True, "topic": topic, "channel": ch, "harvested": summaries, "items": items}, ensure_ascii=False)
            except Exception as e:
                pass

        res = self._call_reach([ch, "search", topic, "--limit", "3"])
        if res.get("ok"):
            items = []
            for it in res.get("items", []):
                t = it.get("title", "")
                s = it.get("text", "")[:200]
                summary = f"{t}: {s}" if t and s else (t or s)
                if summary:
                    items.append(summary)
            return json.dumps({"ok": True, "topic": topic, "channel": ch, "harvested": items}, ensure_ascii=False)

        # Fallback ricerca web se reach CLI non risponde
        return json.dumps({"ok": False, "error": "Scouting fallito o agent-reach non raggiungibile"})

    def execute(self, tool_name: str, args: dict[str, Any]) -> str:
        args = args or {}
        if tool_name == "scout_web_read":
            return self._read_web(args.get("url", ""))
        elif tool_name == "scout_get_trends":
            return self._get_trends(int(args.get("limit", 5)))
        elif tool_name == "scout_harvest_trends":
            return self._harvest(args.get("topic", ""), args.get("channel", "web"))
        return json.dumps({"ok": False, "error": f"Tool '{tool_name}' non gestito da {self.name}"})
