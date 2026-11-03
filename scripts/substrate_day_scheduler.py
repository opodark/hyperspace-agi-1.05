#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Alterna CPU/GPU del Mac fra ciclo R&D notturno e lavori sul substrato (Resin/Qwenputer).

`omen_allnight_sovereign.py --daemon` non si ferma mai da solo (il nome è storico: gira
24/7). Finché Resin e Qwenputer erano solo analisi non c'era contesa; ora che richiedono
build Rust (`cargo build --release`, minuti di CPU piena) e benchmark reali sui nodi mesh,
farli girare insieme al ciclo R&D li fa solo rallentare a vicenda.

Questo script decide, in base all'ora locale, chi ha la priorità:
- **notte** (default 21:00-07:00): il ciclo R&D (`omen_allnight_sovereign.py --daemon`) resta
  attivo; se non lo è, lo avvia.
- **giorno**: il ciclo R&D viene fermato (SIGTERM, lo stato riprende dal WAL al prossimo
  avvio, come un riavvio manuale) e al suo posto gira la batteria di verifica Resin +
  Qwenputer (`resin_mesh_probe.py`, `qwenputer_mesh_probe.py`), loggata in
  `data/nightly/day_battery_log.jsonl`.

Uso:
  python scripts/substrate_day_scheduler.py --status
  python scripts/substrate_day_scheduler.py --once
  python scripts/substrate_day_scheduler.py --daemon --interval 300
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"
NIGHTLY_DIR = DATA_DIR / "nightly"
NIGHTLY_LOG = NIGHTLY_DIR / "omen_allnight_daemon.log"
BATTERY_LOG = NIGHTLY_DIR / "day_battery_log.jsonl"
NIGHTLY_SCRIPT = ROOT / "scripts" / "omen_allnight_sovereign.py"

NIGHT_START_HOUR = int(os.getenv("SUBSTRATE_NIGHT_START_HOUR", "21"))
NIGHT_END_HOUR = int(os.getenv("SUBSTRATE_NIGHT_END_HOUR", "7"))
BATTERY_INTERVAL_S = int(os.getenv("SUBSTRATE_BATTERY_INTERVAL_S", "3600"))
NIGHTLY_INTERVAL_S = int(os.getenv("SUBSTRATE_NIGHTLY_INTERVAL_S", "30"))
# Dove gira il ciclo R&D: "local" (default, questo Mac) oppure "omen" (attività pianificata
# sull'OMEN, sempre acceso). Con "omen" lo scheduler non lo avvia mai e ferma un'eventuale copia
# locale: due demoni sugli stessi modelli si rallentano a vicenda. Resta solo la batteria diurna.
RD_HOST = os.getenv("SUBSTRATE_RD_HOST", "local").strip().lower()


def is_night_hour(hour: int, start: int = NIGHT_START_HOUR, end: int = NIGHT_END_HOUR) -> bool:
    """True se `hour` (0-23) cade nella finestra notturna, anche se questa attraversa la mezzanotte."""
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def current_mode(now: Optional[datetime.datetime] = None) -> str:
    now = now or datetime.datetime.now()
    return "notte" if is_night_hour(now.hour) else "giorno"


def _find_nightly_daemon_pid() -> Optional[int]:
    try:
        out = subprocess.run(
            ["pgrep", "-f", f"{NIGHTLY_SCRIPT.name} --daemon"],
            capture_output=True, text=True, check=False,
        ).stdout.strip()
    except FileNotFoundError:
        return None
    for line in out.splitlines():
        try:
            pid = int(line.strip())
            if pid != os.getpid():
                return pid
        except ValueError:
            continue
    return None


def stop_nightly_daemon() -> bool:
    """Ferma il ciclo R&D, se attivo. Nessuna perdita di stato: riprende dal WAL."""
    pid = _find_nightly_daemon_pid()
    if pid is None:
        return False
    os.kill(pid, signal.SIGTERM)
    return True


def start_nightly_daemon() -> bool:
    """Avvia il ciclo R&D, se non è già attivo."""
    if _find_nightly_daemon_pid() is not None:
        return False
    NIGHTLY_DIR.mkdir(parents=True, exist_ok=True)
    with open(NIGHTLY_LOG, "a", encoding="utf-8") as log_f:
        subprocess.Popen(
            [sys.executable, str(NIGHTLY_SCRIPT), "--daemon", "--interval", str(NIGHTLY_INTERVAL_S)],
            stdout=log_f, stderr=subprocess.STDOUT, cwd=str(ROOT), start_new_session=True,
        )
    return True


def run_day_battery() -> Dict[str, Any]:
    """Un giro della batteria di verifica Resin + Qwenputer, loggato per il digest diurno."""
    record: Dict[str, Any] = {"timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    for name, script in (
        ("resin", ROOT / "scripts" / "diagnostics" / "resin_mesh_probe.py"),
        ("qwenputer", ROOT / "scripts" / "diagnostics" / "qwenputer_mesh_probe.py"),
    ):
        try:
            proc = subprocess.run(
                [sys.executable, str(script), "--all-nodes", "--json"],
                capture_output=True, text=True, timeout=180, cwd=str(ROOT),
            )
            record[name] = {"exit_code": proc.returncode, "stdout_tail": proc.stdout[-4000:]}
        except Exception as exc:
            record[name] = {"error": str(exc)}

    NIGHTLY_DIR.mkdir(parents=True, exist_ok=True)
    with open(BATTERY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def tick(last_mode: Optional[str], last_battery_ts: float) -> tuple[str, float]:
    """Un passo dello scheduler: transizione se il modo è cambiato, batteria se è giorno
    (subito alla transizione, poi ogni BATTERY_INTERVAL_S mentre resta giorno)."""
    mode = current_mode()
    transitioned = mode != last_mode
    if transitioned:
        if mode == "notte" and RD_HOST == "local":
            start_nightly_daemon()
        else:
            stop_nightly_daemon()
    now = time.time()
    due = mode == "giorno" and (transitioned or now - last_battery_ts >= BATTERY_INTERVAL_S)
    if due:
        run_day_battery()
        last_battery_ts = now
    return mode, last_battery_ts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--daemon", action="store_true", help="Loop continuo")
    ap.add_argument("--interval", type=int, default=300, help="Secondi fra un controllo e il successivo")
    ap.add_argument("--once", action="store_true", help="Un solo controllo/transizione e uscita")
    ap.add_argument("--status", action="store_true", help="Stampa modo attuale e stato del demone R&D, sola lettura")
    args = ap.parse_args()

    if args.status:
        pid = _find_nightly_daemon_pid()
        print(json.dumps({
            "modo": current_mode(),
            "finestra_notte": f"{NIGHT_START_HOUR:02d}:00-{NIGHT_END_HOUR:02d}:00",
            "rd_host": RD_HOST,
            "demone_rd_attivo": pid is not None,
            "demone_rd_pid": pid,
        }, indent=2, ensure_ascii=False))
        return 0

    if args.once:
        mode, _ = tick(None, 0.0)
        print(f"[scheduler] modo: {mode}")
        return 0

    if args.daemon:
        print(f"[scheduler] avviato, finestra notte {NIGHT_START_HOUR:02d}:00-{NIGHT_END_HOUR:02d}:00, "
              f"controllo ogni {args.interval}s", flush=True)
        last_mode: Optional[str] = None
        last_battery_ts = 0.0
        while True:
            last_mode, last_battery_ts = tick(last_mode, last_battery_ts)
            print(f"[scheduler] {datetime.datetime.now().isoformat()} modo={last_mode}", flush=True)
            time.sleep(args.interval)

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
