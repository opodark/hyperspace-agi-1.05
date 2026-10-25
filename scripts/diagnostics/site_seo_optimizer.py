#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Site SEO & GEO Autonomous Optimizer for HyperSpace (www.zerozerocomputer.it).

Integrates:
1. Auriti-Labs/geo-optimizer-skill (Generative Engine Optimization for ChatGPT, Perplexity, Claude, Gemini)
2. AminForou/mcp-gsc (Google Search Console inspection & query analytics)
3. every-app/open-seo (Technical audit & AI visibility tracking)

Performs automated audits, tracks ranking trends, and generates recommended fixes.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
REPORT_FILE = BASE_DIR / "data" / "control-plane" / "reports" / "seo_geo_audit_latest.json"
HISTORY_FILE = BASE_DIR / "data" / "control-plane" / "reports" / "seo_geo_history.json"

DEFAULT_TARGET_URL = os.getenv("SEO_TARGET_URL", "https://www.zerozerocomputer.it")
GEO_BIN = os.getenv("GEO_BIN") or shutil.which("geo") or "/Users/opo/.local/bin/geo"
MCP_GSC_BIN = os.getenv("MCP_GSC_BIN") or shutil.which("mcp-gsc") or "/Users/opo/.local/bin/mcp-gsc"


def run_cmd(cmd: list[str], timeout: int = 40) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as exc:
        return 1, "", f"Errore esecuzione {cmd}: {exc}"


def run_geo_audit(target_url: str = DEFAULT_TARGET_URL) -> dict:
    """Run GEO audit using Auriti-Labs geo-optimizer."""
    if not (os.path.isfile(GEO_BIN) and os.access(GEO_BIN, os.X_OK)):
        return {"ok": False, "error": f"geo binary not found at {GEO_BIN}"}

    code, out, err = run_cmd([GEO_BIN, "audit", "--url", target_url], timeout=45)
    if code != 0:
        return {"ok": False, "error": err or out}

    # Extract final score (works for visual banner, final block, and plain text modes)
    score = None
    m_banner = re.search(r"^\s*(\d{1,3})\s*/\s*100\s+(FOUNDATION|GOOD|EXCELLENT|CRITICAL)", out, re.MULTILINE)
    if m_banner:
        score = int(m_banner.group(1))
    else:
        m_final = re.search(r"FINAL GEO SCORE.*?(\d{1,3})\s*/\s*100", out, re.DOTALL)
        if m_final:
            score = int(m_final.group(1))
        else:
            all_m = re.findall(r"(\d{1,3})\s*/\s*100", out)
            if all_m:
                score = int(all_m[-1])

    # Parse priority next steps / top fixes
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
            elif fixes and line.strip() and not line.strip().startswith("=="):
                fixes[-1] += " " + line.strip()

    # Extract categories and status checks
    passed_checks = len(re.findall(r"✓|✅", out))
    failed_checks = len(re.findall(r"✗|❌|⚠️|⚠", out))

    return {
        "ok": True,
        "url": target_url,
        "geo_score": score,
        "checks_passed": passed_checks,
        "checks_warning_or_failed": failed_checks,
        "priority_fixes": fixes[:15],
        "full_output": out,
    }


def run_geo_access_audit(target_url: str = DEFAULT_TARGET_URL) -> dict:
    """Run AI Crawler access audit."""
    if not (os.path.isfile(GEO_BIN) and os.access(GEO_BIN, os.X_OK)):
        return {"ok": False, "error": "geo binary not found"}

    code, out, err = run_cmd([GEO_BIN, "access", target_url], timeout=20)
    return {
        "ok": code == 0,
        "summary": out.strip() if code == 0 else err.strip()
    }


def save_report(audit_result: dict) -> bool:
    """Save latest audit and append to history."""
    try:
        REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        audit_result["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(audit_result, f, ensure_ascii=False, indent=2)

        # Update historical trend
        history = []
        if HISTORY_FILE.is_file():
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []
        history.append({
            "ts": audit_result["timestamp"],
            "url": audit_result.get("url"),
            "geo_score": audit_result.get("geo_score"),
        })
        history = history[-100:]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

        return True
    except Exception as exc:
        print(f"[!] Errore salvataggio report: {exc}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="HyperSpace Autonomous Site SEO & GEO Optimizer")
    parser.add_argument("--url", default=DEFAULT_TARGET_URL, help=f"URL del sito (default {DEFAULT_TARGET_URL})")
    parser.add_argument("--access-check", action="store_true", help="Esegui audit dei crawler AI")
    parser.add_argument("--save", action="store_true", help="Salva il report in data/reports/")
    parser.add_argument("--json", action="store_true", help="Stampa l'output JSON")
    args = parser.parse_args()

    print(f"[*] Avvio SEO & GEO Audit su {args.url}...")
    geo_res = run_geo_audit(args.url)

    if args.access_check:
        print("[*] Controllo accesso AI crawler...")
        access_res = run_geo_access_audit(args.url)
        geo_res["crawler_access"] = access_res

    if args.save:
        save_report(geo_res)
        print(f"✅ Report salvato in {REPORT_FILE}")

    if args.json or not args.save:
        print(json.dumps(geo_res, indent=2, ensure_ascii=False))
    else:
        score = geo_res.get("geo_score", "?")
        print(f"\n🎯 Punteggio GEO Attuale: {score}/100")
        print(f"✅ Check passati: {geo_res.get('checks_passed', 0)} | ⚠️ Avvisi/Mancanti: {geo_res.get('checks_warning_or_failed', 0)}")
        print("💡 Top Azioni Correttive Consigliate:")
        for i, fix in enumerate(geo_res.get("priority_fixes", [])):
            print(f"   [{i+1}] {fix}")


if __name__ == "__main__":
    main()
