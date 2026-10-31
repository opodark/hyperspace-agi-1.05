# SPDX-License-Identifier: Apache-2.0
"""
connectors/seo.py — Autonomous SEO & GEO (Generative Engine Optimization) Connector
Integrates Auriti-Labs/geo-optimizer, AminForou/mcp-gsc, and OpenSEO auditing
for HyperSpace AI agents to monitor and optimize www.zerozerocomputer.it.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .base import BaseConnector


class SeoConnector(BaseConnector):
    """Connettore per il monitoraggio SEO, indicizzazione e ottimizzazione per AI Search Engines (GEO)."""

    name: str = "seo"
    REQUIRED_ENV: tuple[str, ...] = ("CONNECTOR_SEO_ENABLED",)
    READ_TOOLS: tuple[str, ...] = ("seo_audit_site", "seo_get_latest_report", "seo_inspect_llms", "seo_generate_schema_jsonld")
    WRITE_TOOLS: tuple[str, ...] = ()

    def is_available(self) -> bool:
        # Abilitato se la variabile è esplicitamente accesa ('true', '1', 'yes')
        val = os.getenv("CONNECTOR_SEO_ENABLED", "").strip().lower()
        return val in ("true", "1", "yes")

    def __init__(self):
        self.geo_bin = os.getenv("GEO_BIN") or shutil.which("geo") or "/Users/opo/.local/bin/geo"
        self.default_url = os.getenv("SEO_TARGET_URL", "https://www.zerozerocomputer.it")

    def get_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "seo_audit_site",
                    "description": "Esegue un audit completo di Generative Engine Optimization (GEO) e indicizzazione su un URL del sito (es. www.zerozerocomputer.it).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "URL target del sito (default: https://www.zerozerocomputer.it).",
                                "default": "https://www.zerozerocomputer.it"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "seo_get_latest_report",
                    "description": "Restituisce l'ultimo report di audit GEO/SEO salvato con punteggio (0-100), check passati e priorità di correzione.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "seo_inspect_llms",
                    "description": "Verifica lo stato e la conformità del file /llms.txt per gli agenti e i motori di ricerca generativi (Perplexity, ChatGPT, Gemini).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "domain": {"type": "string", "description": "Dominio da verificare (default: www.zerozerocomputer.it).", "default": "www.zerozerocomputer.it"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "seo_generate_schema_jsonld",
                    "description": "Genera lo schema JSON-LD validato (Organization, WebSite, SoftwareApplication) per accrescere l'autorevolezza nel Knowledge Graph AI.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Nome del brand (default: ZeroZeroComputer).", "default": "ZeroZeroComputer"},
                            "url": {"type": "string", "description": "URL principale.", "default": "https://www.zerozerocomputer.it"}
                        }
                    }
                }
            }
        ]

    def _audit(self, url: str) -> str:
        target = url or self.default_url
        if os.path.isfile(self.geo_bin) and os.access(self.geo_bin, os.X_OK):
            try:
                proc = subprocess.run([self.geo_bin, "audit", "--url", target], capture_output=True, text=True, timeout=40)
                out = proc.stdout
                import re
                score_match = re.search(r"(\d{1,3})\s*/\s*100", out)
                score = int(score_match.group(1)) if score_match else None
                fixes = []
                capture = False
                for line in out.splitlines():
                    if "PRIORITY NEXT STEPS:" in line or "Top fixes" in line:
                        capture = True
                        continue
                    if capture:
                        if line.strip().startswith(("geo audit", "Free plan", "──", "Score bands:", "💡", "→")):
                            break
                        fix_m = re.match(r"^\s*(\d+)[\.\)]\s+(.+)", line)
                        if fix_m:
                            fixes.append(fix_m.group(2).strip())
                return json.dumps({
                    "ok": True,
                    "url": target,
                    "geo_score": score,
                    "priority_fixes": fixes[:10],
                    "raw_summary": out[:1200]
                }, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"ok": False, "error": f"Errore esecuzione audit geo: {e}"})

        # Fallback basico
        return json.dumps({"ok": False, "error": f"Tool geo non disponibile su percorso {self.geo_bin}"})

    def _get_report(self) -> str:
        paths = ["/app/data/reports/seo_geo_audit_latest.json", "data/reports/seo_geo_audit_latest.json"]
        found = None
        for p in paths:
            if os.path.isfile(p):
                found = p
                break
        if not found:
            return json.dumps({"ok": False, "error": "Nessun report SEO/GEO ancora generato"})
        try:
            with open(found, "r", encoding="utf-8") as f:
                data = json.load(f)
            return json.dumps({
                "ok": True,
                "url": data.get("url"),
                "geo_score": data.get("geo_score"),
                "timestamp": data.get("timestamp"),
                "priority_fixes": data.get("priority_fixes", []),
                "checks_passed": data.get("checks_passed"),
                "checks_warning_or_failed": data.get("checks_warning_or_failed")
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    def _inspect_llms(self, domain: str = "www.zerozerocomputer.it") -> str:
        import requests
        target = f"https://{domain.rstrip('/')}/llms.txt"
        try:
            resp = requests.get(target, timeout=10)
            if resp.status_code == 200:
                text = resp.text
                lines = text.splitlines()
                return json.dumps({
                    "ok": True,
                    "url": target,
                    "status_code": 200,
                    "lines_count": len(lines),
                    "bytes": len(text.encode("utf-8")),
                    "preview": "\n".join(lines[:15])
                }, ensure_ascii=False)
            return json.dumps({"ok": False, "status_code": resp.status_code, "error": "File non trovato o errore HTTP"})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    def _generate_schema(self, name: str = "ZeroZeroComputer", url: str = "https://www.zerozerocomputer.it") -> str:
        schema = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "Organization",
                    "@id": f"{url}/#organization",
                    "name": name,
                    "url": url,
                    "logo": f"{url}/logo.png",
                    "description": "Sovereign Operating System for Multi-Node AI Agents, Autonomous Creativity & Useful Work.",
                    "sameAs": [
                        "https://github.com/zerozerocomputer",
                        "https://instagram.com/aurora_hyperspace"
                    ]
                },
                {
                    "@type": "WebSite",
                    "@id": f"{url}/#website",
                    "url": url,
                    "name": name,
                    "publisher": {"@id": f"{url}/#organization"}
                },
                {
                    "@type": "SoftwareApplication",
                    "name": "HyperSpace AGI",
                    "applicationCategory": "BusinessApplication, ArtificialIntelligence",
                    "operatingSystem": "Linux, macOS, Windows",
                    "offers": {
                        "@type": "Offer",
                        "price": "0",
                        "priceCurrency": "EUR"
                    }
                }
            ]
        }
        return json.dumps({"ok": True, "schema_json": json.dumps(schema, indent=2, ensure_ascii=False)}, ensure_ascii=False)

    def execute(self, tool_name: str, args: dict[str, Any]) -> str:
        args = args or {}
        if tool_name == "seo_audit_site":
            return self._audit(args.get("url", ""))
        elif tool_name == "seo_get_latest_report":
            return self._get_report()
        elif tool_name == "seo_inspect_llms":
            return self._inspect_llms(args.get("domain", "www.zerozerocomputer.it"))
        elif tool_name == "seo_generate_schema_jsonld":
            return self._generate_schema(args.get("name", "ZeroZeroComputer"), args.get("url", "https://www.zerozerocomputer.it"))
        return json.dumps({"ok": False, "error": f"Tool '{tool_name}' non gestito da {self.name}"})
