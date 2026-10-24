#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Automated Continuous SEO & GEO Optimizer for www.zerozerocomputer.it.

Runs periodic generative engine and search console health audits,
tracking visibility improvements across ChatGPT, Perplexity, Gemini, and Google.
"""

from __future__ import annotations

import argparse
import datetime
import os
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
OPTIMIZER_SCRIPT = BASE_DIR / "scripts" / "diagnostics" / "site_seo_optimizer.py"
PYTHON_BIN = BASE_DIR / ".venv" / "bin" / "python"
LOG_FILE = BASE_DIR / "data" / "seo-optimizer.log"


def log(msg: str):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] [auto-seo] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run_audit_once() -> bool:
    py = str(PYTHON_BIN) if PYTHON_BIN.is_file() else sys.executable
    if not OPTIMIZER_SCRIPT.is_file():
        log(f"Errore: {OPTIMIZER_SCRIPT} non trovato")
        return False

    log("Avvio ciclo di audit SEO/GEO autonomo...")
    cmd = [py, str(OPTIMIZER_SCRIPT), "--save", "--access-check"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, cwd=str(BASE_DIR))
        if proc.returncode == 0:
            log("Audit completato con successo.")
            return True
        else:
            log(f"Audit fallito (exit {proc.returncode}): {proc.stderr[:300]}")
            return False
    except Exception as exc:
        log(f"Errore esecuzione audit: {exc}")
        return False


def run_daemon(interval_s: int = 43200):
    """Run SEO/GEO audit daemon every interval_s seconds (default 12h = 43200s)."""
    log(f"Demone SEO/GEO avviato (intervallo {interval_s}s)...")
    run_audit_once()
    while True:
        time.sleep(interval_s)
        run_audit_once()


def main():
    parser = argparse.ArgumentParser(description="HyperSpace Autonomous SEO Optimizer")
    parser.add_argument("--once", action="store_true", help="Esegui una sola scansione e termina")
    parser.add_argument("--interval", type=int, default=43200, help="Intervallo in secondi per il demone (default 43200 = 12h)")
    args = parser.parse_args()

    if args.once:
        ok = run_audit_once()
        sys.exit(0 if ok else 1)
    else:
        run_daemon(interval_s=args.interval)


if __name__ == "__main__":
    main()
