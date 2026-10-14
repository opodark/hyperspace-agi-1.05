#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Daemon di monitoraggio energetico continuo per host HyperSpace.

Rileva lo stato di alimentazione (rete elettrica AC vs batteria, percentuale di carica)
e lo persiste atomicamente in data/host_power.json e data/runtime/data/host_power.json
(visibile dentro il container Docker /app/data).
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.power_sense import detect_host_power, save_host_power


def run_monitor(interval_s: float = 60.0, once: bool = False) -> None:
    while True:
        try:
            status = detect_host_power()
            save_host_power(status)
            ac_str = "AC" if status.get("ac_line") else "BATTERIA"
            pct = status.get("battery_pct")
            pct_str = f" ({pct:.0f}%)" if pct is not None else ""
            print(f"[power_monitor] [{ac_str}{pct_str}] aggiornato host_power.json", flush=True)
        except Exception as e:
            print(f"[power_monitor] Errore rilevamento: {e}", file=sys.stderr, flush=True)

        if once:
            break
        time.sleep(interval_s)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor energetico host HyperSpace")
    parser.add_argument("--interval", type=float, default=60.0, help="Intervallo di polling in secondi (default: 60)")
    parser.add_argument("--once", action="store_true", help="Esegui una sola rilevazione ed esci")
    args = parser.parse_args()
    run_monitor(interval_s=args.interval, once=args.once)
