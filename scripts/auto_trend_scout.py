#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Automated Periodic Trend Scout for HyperSpace Nocturnal Inspiration.

Runs on macOS host, queries Agent-Reach at regular intervals (default every 6h)
and at 23:30 (before nocturnal dream window), persisting fresh cultural echoes
into data/control-plane/trend_inspirations.json.
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
SCOUT_SCRIPT = BASE_DIR / "scripts" / "diagnostics" / "trend_scout_reach.py"
PYTHON_BIN = BASE_DIR / ".venv" / "bin" / "python"
LOG_FILE = BASE_DIR / "data" / "trend-scout.log"


def log(msg: str):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] [auto-scout] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run_scout_once() -> bool:
    py = str(PYTHON_BIN) if PYTHON_BIN.is_file() else sys.executable
    if not SCOUT_SCRIPT.is_file():
        log(f"Errore: {SCOUT_SCRIPT} non trovato")
        return False

    log("Avvio ciclo di scouting trend tematici...")
    cmd = [py, str(SCOUT_SCRIPT), "--save"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, cwd=str(BASE_DIR))
        if proc.returncode == 0:
            log("Ciclo di scouting completato con successo.")
            return True
        else:
            log(f"Scout fallito (exit {proc.returncode}): {proc.stderr[:300]}")
            return False
    except Exception as exc:
        log(f"Errore esecuzione scout: {exc}")
        return False


def run_daemon(interval_s: int = 21600):
    """Run scouting daemon every interval_s seconds (default 6h)."""
    log(f"Demone avviato (intervallo {interval_s}s)...")
    run_scout_once()
    while True:
        time.sleep(interval_s)
        run_scout_once()


def main():
    parser = argparse.ArgumentParser(description="HyperSpace Trend Scout Automator")
    parser.add_argument("--once", action="store_true", help="Esegui una sola scansione e termina")
    parser.add_argument("--interval", type=int, default=21600, help="Intervallo in secondi per il demone (default 21600 = 6h)")
    args = parser.parse_args()

    if args.once:
        ok = run_scout_once()
        sys.exit(0 if ok else 1)
    else:
        run_daemon(interval_s=args.interval)


if __name__ == "__main__":
    main()
