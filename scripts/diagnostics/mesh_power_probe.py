#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# scripts/diagnostics/mesh_power_probe.py
# HyperSpace AGI — Energy & Blackout Resilience Diagnostic Probe
"""Sonda diagnostica riutilizzabile per il monitoraggio dello stato energetico
e della resilienza a blackout della mesh HyperSpace.

Uso:
    python scripts/diagnostics/mesh_power_probe.py [--cp-url http://localhost:8085] [--json]

Non stampa credenziali né segreti.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import requests

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.power_sense import detect_host_power


def inspect_mesh_power(cp_url: str = "http://localhost:8085") -> Dict[str, Any]:
    cp_url = cp_url.rstrip("/")
    local_power = detect_host_power()

    res: Dict[str, Any] = {
        "local_host": {
            "power": local_power,
            "ac_line": local_power.get("ac_line", True),
            "battery_pct": local_power.get("battery_pct"),
            "source": local_power.get("source", "unknown"),
        },
        "nodes": [],
        "cp_reachable": False,
        "grid_status": "unknown",
        "ac_count": 0,
        "battery_count": 0,
    }

    try:
        r = requests.get(f"{cp_url}/doctor", timeout=5)
        if r.status_code == 200:
            res["cp_reachable"] = True
            doc_data = r.json()
            telemetries = doc_data.get("mesh_telemetry", [])

            ac_count = 0
            battery_count = 0

            for t in telemetries:
                hw = t.get("hardware", {})
                pwr = hw.get("power", {})
                ac = pwr.get("ac_line", hw.get("ac_line", True))
                pct = pwr.get("battery_pct", hw.get("battery_pct"))
                alias = t.get("alias") or t.get("node_id", "?")[:12]
                if t.get("is_local"):
                    alias += " [Local/CP]"

                if ac:
                    ac_count += 1
                else:
                    battery_count += 1

                res["nodes"].append({
                    "node_id": t.get("node_id"),
                    "alias": alias,
                    "endpoint": t.get("endpoint"),
                    "tier": t.get("tier"),
                    "channel": t.get("channel"),
                    "ac_line": ac,
                    "battery_pct": pct,
                    "source": pwr.get("source", "unknown"),
                })

            res["ac_count"] = ac_count
            res["battery_count"] = battery_count

            if battery_count == 0:
                res["grid_status"] = "all_ac"
            elif ac_count > 0:
                res["grid_status"] = "mixed_safe"
            else:
                res["grid_status"] = "blackout_alert"

    except Exception as exc:
        res["error"] = str(exc)

    return res


def main():
    parser = argparse.ArgumentParser(description="HyperSpace Mesh Power & Blackout Diagnostic Probe")
    parser.add_argument("--cp-url", default="http://localhost:8085", help="URL del Control Plane locale")
    parser.add_argument("--json", action="store_true", help="Output in formato JSON puro")
    args = parser.parse_args()

    data = inspect_mesh_power(args.cp_url)

    if args.json:
        print(json.dumps(data, indent=2))
        return

    print("=" * 68)
    print(" ⚡️ HYPERSPACE AGI — GESTIONE ENERGETICA & RESILIENZA BLACKOUT")
    print("=" * 68)

    loc = data["local_host"]
    loc_ac = loc["ac_line"]
    loc_pct = loc.get("battery_pct")
    pwr_sym = "🔌 AC (Rete Elettrica)" if loc_ac else f"🔋 Batteria ({loc_pct:.0f}%)"
    print(f"\n[HOST LOCALE]")
    print(f"  Stato alimentazione : {pwr_sym}")
    print(f"  Fonte rilevamento   : {loc.get('source')}")

    print(f"\n[STATO MESH]")
    if not data["cp_reachable"]:
        print(f"  ⚠️  Control Plane ({args.cp_url}) non raggiungibile.")
    else:
        st_map = {
            "all_ac": "🟢 RETE STABILE: Tutti i nodi sono alimentati da presa fissa (AC)",
            "mixed_safe": "🟡 RETE MISTA: Alcuni nodi a batteria, carico convogliato verso i nodi a presa",
            "blackout_alert": "🔴 ALLERTA BLACKOUT: Tutti i nodi a batteria! Ripartizione proporzionale",
        }
        print(f"  Diagnosi rete : {st_map.get(data['grid_status'], data['grid_status'])}")
        print(f"  Nodi su AC    : {data['ac_count']}")
        print(f"  Nodi batteria : {data['battery_count']}\n")

        print(f"{'Nodo / Alias':<22} {'Tier':<8} {'Alimentazione':<20} {'Endpoint':<25}")
        print("-" * 75)
        for n in data["nodes"]:
            ac = n["ac_line"]
            pct = n.get("battery_pct")
            sym = "🔌 AC (Rete)" if ac else f"🔋 Batt: {pct:.0f}%" if pct is not None else "🔋 Batteria"
            ep = n.get("endpoint") or "internal"
            print(f"{n['alias']:<22} {n.get('tier', 'leaf'):<8} {sym:<20} {ep:<25}")

    print("=" * 68)


if __name__ == "__main__":
    main()
