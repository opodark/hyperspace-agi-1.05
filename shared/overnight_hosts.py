# SPDX-License-Identifier: Apache-2.0
"""Chi ha lavorato davvero stanotte: Mac (scheduler) e OMEN (Dev Loop 24/7), a confronto.

Il Mac va in sleep a coperchio chiuso e i suoi log si fermano; l'OMEN gira sempre e scrive sul
proprio disco, che il cockpit del Mac non vede. Qui si mettono i due fianco a fianco:
- `mac_sleep_gaps`: buchi nel log dello scheduler (un tick ogni `interval_s`, un buco = Mac sospeso
  o scheduler fermo);
- `omen_overnight_summary`: legge sull'OMEN, con un comando firmato (`scripts/mesh_exec.py`), i cicli
  del Dev Loop per ora e l'ultima riga dell'audit del ciclo sovrano.
"""
from __future__ import annotations

import base64
import datetime
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
SCHEDULER_LOG = ROOT / "data" / "nightly" / "substrate_scheduler.log"
OMEN_REPO_PATH = os.getenv("OMEN_REPO_PATH", "/repo")
_TICK_RE = re.compile(r"^\[scheduler\] (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})")

# Eseguito sull'OMEN (python3 del container del nodo): solo lettura, stampa un JSON.
_REMOTE_SCRIPT = '''
import collections, datetime, json, sys
repo, hours = sys.argv[1], int(sys.argv[2])
now = datetime.datetime.now(datetime.timezone.utc)
since = now - datetime.timedelta(hours=hours)

def parse(t):
    try:
        x = datetime.datetime.fromisoformat(t.replace("Z", "+00:00"))
        return x if x.tzinfo else x.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None

def stamps(path):
    try:
        for line in open(path, encoding="utf-8", errors="replace"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            x = parse(str(r.get("timestamp") or r.get("ts") or ""))
            if x:
                yield x
    except OSError:
        return

per_hour, last_loop = collections.Counter(), None
for x in stamps(repo + "/data/omen_dev_loop.jsonl"):
    last_loop = max(last_loop, x) if last_loop else x
    if x >= since:
        per_hour[x.strftime("%Y-%m-%dT%H")] += 1
last_audit = None
for x in stamps(repo + "/data/nightly/omen_audit.jsonl"):
    last_audit = max(last_audit, x) if last_audit else x
print(json.dumps({
    "now": now.isoformat(),
    "dev_loop_per_hour": dict(sorted(per_hour.items())),
    "dev_loop_last": last_loop.isoformat() if last_loop else None,
    "sovereign_last_audit": last_audit.isoformat() if last_audit else None,
}))
'''


def mac_sleep_gaps(
    log_path: Path = SCHEDULER_LOG, interval_s: int = 300, min_gap_s: Optional[int] = None,
    since: Optional[datetime.datetime] = None,
) -> List[Dict[str, Any]]:
    """Buchi fra due tick consecutivi dello scheduler più lunghi di `min_gap_s` (default 2 intervalli)."""
    min_gap_s = min_gap_s if min_gap_s is not None else 2 * interval_s
    ticks: List[datetime.datetime] = []
    try:
        for line in Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines():
            m = _TICK_RE.match(line)
            if m:
                ticks.append(datetime.datetime.fromisoformat(m.group(1)))
    except OSError:
        return []
    gaps = []
    for a, b in zip(ticks, ticks[1:]):
        secs = (b - a).total_seconds()
        if secs > min_gap_s and (since is None or b >= since):
            gaps.append({"from": a.isoformat(), "to": b.isoformat(), "hours": round(secs / 3600, 2)})
    return gaps


def omen_overnight_summary(
    hours: int = 12, runner: Optional[Callable[..., Dict[str, Any]]] = None, endpoint: Optional[str] = None,
) -> Dict[str, Any]:
    """Cicli del Dev Loop per ora e ultimo audit sovrano sull'OMEN. `error` valorizzato se non risponde."""
    if runner is None:
        from scripts.mesh_exec import execute_remote_cmd, resolve_endpoint
        runner = execute_remote_cmd
        endpoint = endpoint or resolve_endpoint("omen")
    payload = base64.b64encode(_REMOTE_SCRIPT.encode("utf-8")).decode("ascii")
    cmd = f"echo {payload} | base64 -d | python3 - {OMEN_REPO_PATH} {int(hours)}"
    res = runner(endpoint, cmd, timeout=30.0)
    if res.get("exit_code") != 0:
        return {"ok": False, "error": res.get("error") or (res.get("stderr") or "")[-200:] or "exit non zero"}
    try:
        data = json.loads(res.get("stdout", "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"ok": False, "error": "risposta non JSON"}
    data["ok"] = True
    data["dev_loop_cycles"] = sum(data["dev_loop_per_hour"].values())
    return data


_CACHE: Dict[str, Any] = {"ts": 0.0, "value": None}


def hosts_overview(hours: int = 12, ttl_s: float = 60.0) -> Dict[str, Any]:
    """Quadro Mac + OMEN, con cache breve: il cockpit lo interroga a ogni refresh e l'OMEN costa ~2 s."""
    if _CACHE["value"] is not None and time.time() - _CACHE["ts"] < ttl_s:
        return _CACHE["value"]
    since = datetime.datetime.now() - datetime.timedelta(hours=hours)
    value = {
        "hours": hours,
        "mac": {"sleep_gaps": mac_sleep_gaps(since=since)},
        "omen": omen_overnight_summary(hours),
    }
    _CACHE.update(ts=time.time(), value=value)
    return value
