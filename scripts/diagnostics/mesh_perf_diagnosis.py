#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
scripts/diagnostics/mesh_perf_diagnosis.py
Diagnostica rapida delle prestazioni della mesh HyperSpace e dei nodi.
Verifica:
1. Stato del battito cardiaco del Control Plane (frequenza tick, thread vivo o congelato).
2. Nodi zombie / offline ancora segnati come 'active' che causano timeout sincroni.
3. Latenza effettiva e porte dei nodi registrati (Mac, Tailscale, Docker).
4. Carico VRAM e model fit per ogni nodo (identifica CPU memory spilling).
"""

import sys
import time
import json
import urllib.request
import urllib.error

CP_URL = "http://localhost:8085"


def fetch_json(url, timeout=3):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HyperSpace-PerfDiag/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return 0, str(e)


def main():
    print("=" * 65)
    print(" 🚀 DIAGNOSTICA PRESTAZIONI E LATENZA MESHYPERSPACE")
    print("=" * 65)

    # 1. Control Plane Health & Heartbeat
    status_code, hb = fetch_json(f"{CP_URL}/hb/status", timeout=2)
    if status_code != 200 or not isinstance(hb, dict):
        print(f"❌ Control Plane non risponde su {CP_URL}/hb/status (code={status_code})")
        return 1

    print("\n[1] Control Plane Heartbeat:")
    last_tick = hb.get("last_tick")
    cycle = hb.get("cycle")
    running = hb.get("running")
    print(f"    - Ciclo: {cycle}")
    print(f"    - In esecuzione dichiarata: {running}")
    print(f"    - Ultimo tick: {last_tick}")

    # Check if tick is stale (> 60s)
    if last_tick:
        try:
            import datetime
            # format e.g. 2026-10-18T07:54:38Z
            t_str = last_tick.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(t_str)
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            delta_s = (now_dt - dt).total_seconds()
            if delta_s > 60:
                print(f"    ⚠️ ALLERTA: Heartbeat congelato da {int(delta_s)} secondi! Il thread è morto o bloccato.")
            else:
                print(f"    ✅ Heartbeat attivo (ultimo tick {int(delta_s)}s fa).")
        except Exception:
            pass

    # 2. Nodi registrati e latenza
    print("\n[2] Analisi Nodi Attivi:")
    _, active_nodes = fetch_json(f"{CP_URL}/nodes/active", timeout=2)
    if not isinstance(active_nodes, list):
        print("    ❌ Impossibile leggere i nodi attivi.")
        return 1

    for idx, node in enumerate(active_nodes, 1):
        nid = node.get("node_id", "?")[:12]
        alias = node.get("alias") or ("Mac/Local" if node.get("is_local") else "Remoto")
        ep = node.get("endpoint", "")
        tier = node.get("tier", "leaf")
        vram = node.get("vram_gb", 0)
        fit = node.get("model_fit", {})

        print(f"\n  👉 Nodo #{idx}: {alias} ({nid}) [Tier: {tier}, VRAM: {vram} GB]")
        print(f"     Endpoint: {ep or '(locale)'}")

        if not ep or ep.startswith("browser://"):
            print("     Tipo: nodo interno o browser web-node (non indirizzabile HTTP)")
            continue

        # Test reachability and latency
        t0 = time.time()
        c_code, c_resp = fetch_json(f"{ep}/health", timeout=3)
        lat_ms = int((time.time() - t0) * 1000)

        if c_code == 200:
            print(f"     ✅ Raggiungibile in {lat_ms} ms")
        else:
            print(f"     ❌ NON RAGGIUNGIBILE! (code={c_code}, latenza={lat_ms}ms) -> BLOCCA IL ROUTING E GENERA TIMEOUT!")

        if fit:
            m_name = fit.get("model", "")
            m_fits = fit.get("fits", True)
            verdict = fit.get("verdict", "")
            if not m_fits:
                print(f"     ⚠️ SFORO VRAM: Modello '{m_name}' NON ENTRA: {verdict}")

    print("\n" + "=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(main())
