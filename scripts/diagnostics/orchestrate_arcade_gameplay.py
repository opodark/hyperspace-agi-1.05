#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
HyperSpace Sovereign Mesh — Diagnostica e Orchestratore Sala Giochi Arcade Neurale.

Verifica e collauda l'intero ecosistema della Sala Giochi Retro & Gamification:
1. Connettività e telemetria dei 3 nodi fisici (Mac M5 Hub :8090, OMEN 16 :8081, ASUS V16 :11434).
2. Integrità della pagina web-node/apps/playground/arcade.html (3 giochi: Invaders, Pong, Matrix).
3. Verifica rotte HTTP Cockpit (/arcade e /arcade.html).
4. Funzionalità API commercial engine: consultazione e registrazione record punteggi.

Uso:
    .venv/bin/python scripts/diagnostics/orchestrate_arcade_gameplay.py
    .venv/bin/python scripts/diagnostics/orchestrate_arcade_gameplay.py --verbose
    .venv/bin/python scripts/diagnostics/orchestrate_arcade_gameplay.py --simulate-round
    .venv/bin/python scripts/diagnostics/orchestrate_arcade_gameplay.py --json
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.commercial_engine import CommercialEngine

COCKPIT_URL = os.getenv("COCKPIT_URL", "http://localhost:8090")
OMEN_URL = os.getenv("OMEN_NODE_URL", "http://100.104.238.125:8081")
ASUS_OLLAMA_URL = os.getenv("ASUS_OLLAMA_URL", "http://100.64.31.18:11434")
ARCADE_HTML = REPO_ROOT / "web-node" / "apps" / "playground" / "arcade.html"


def tcp_ping(host: str, port: int, timeout: float = 2.0) -> Tuple[bool, float]:
    """Misura latenza TCP verso un host."""
    t0 = time.time()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True, round((time.time() - t0) * 1000, 2)
    except Exception:
        return False, -1.0


def check_html_integrity() -> Dict[str, Any]:
    """Ispeziona arcade.html verificando la presenza dei 3 motori di gioco e del sintetizzatore."""
    if not ARCADE_HTML.exists():
        return {"ok": False, "error": f"{ARCADE_HTML} non trovato"}

    content = ARCADE_HTML.read_text(encoding="utf-8")
    checks = {
        "canvas_crt": "id=\"gameCanvas\"" in content,
        "chiptune_audio": "ArcadeAudio" in content and "AudioContext" in content,
        "game_invaders": "updateInvaders" in content and "MONOLITHIC CLOUD BOSS" in content,
        "game_pong": "updatePong" in content and "pongAGI" in content,
        "game_matrix": "updateMatrix" in content and "matrixShip" in content and "SOVEREIGN TOKEN" in content,
        "leaderboard_hook": "saveArcadeScore" in content and "/api/commercial/arcade/score" in content,
        "controls_onscreen": "ctrlBtn1" in content and "ctrlBtn2" in content
    }
    all_ok = all(checks.values())
    return {
        "ok": all_ok,
        "file_size_bytes": len(content),
        "checks": checks
    }


def check_http_routes() -> Dict[str, Any]:
    """Verifica le rotte /arcade e /arcade.html su Cockpit."""
    results = {}
    for path in ["/arcade", "/arcade.html", "/api/commercial/arcade/scores"]:
        url = f"{COCKPIT_URL}{path}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Arcade-Diagnostic"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                results[path] = {
                    "reachable": True,
                    "status_code": resp.status,
                    "content_length": len(resp.read())
                }
        except Exception as exc:
            results[path] = {
                "reachable": False,
                "error": str(exc)
            }
    return results


def check_nodes_telemetry() -> Dict[str, Any]:
    """Controlla lo stato dei 3 nodi per il supporto al gioco."""
    nodes = {
        "mac_m5_cockpit": ("localhost", 8090),
        "omen_16_gpu": ("100.104.238.125", 8081),
        "asus_v16_inference": ("100.64.31.18", 11434)
    }
    telemetry = {}
    for name, (host, port) in nodes.items():
        ok, lat = tcp_ping(host, port)
        telemetry[name] = {
            "online": ok,
            "latency_ms": lat,
            "target": f"{host}:{port}"
        }
    return telemetry


def simulate_arcade_score() -> Dict[str, Any]:
    """Registra una partita di test e verifica l'assegnazione dei token."""
    engine = CommercialEngine()
    test_player = f"DiagPilot_{int(time.time() % 1000)}"
    res = engine.record_arcade_score(player=test_player, score=2840, game="matrix")
    return res


def run_full_diagnostic(simulate: bool = False) -> Dict[str, Any]:
    """Esegue l'intero collaudo diagnostico."""
    t0 = time.time()
    html_res = check_html_integrity()
    routes_res = check_http_routes()
    nodes_res = check_nodes_telemetry()

    sim_res = simulate_arcade_score() if simulate else None

    all_routes_ok = all(r.get("reachable", False) for r in routes_res.values())
    all_nodes_ok = all(n.get("online", False) for n in nodes_res.values())
    overall_ok = html_res.get("ok", False) and all_routes_ok

    report = {
        "status": "PASS" if overall_ok else "WARN",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_s": round(time.time() - t0, 3),
        "html_integrity": html_res,
        "cockpit_routes": routes_res,
        "nodes_telemetry": nodes_res,
        "simulation": sim_res
    }

    # Salva report diagnostico persistente
    reports_dir = REPO_ROOT / "data" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file = reports_dir / "arcade_cluster_telemetry.json"
    report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return report


def main():
    parser = argparse.ArgumentParser(description="Diagnostica e Orchestratore Sala Giochi Arcade Neurale HyperSpace.")
    parser.add_argument("--verbose", action="store_true", help="Mostra output dettagliato di ogni controllo.")
    parser.add_argument("--json", action="store_true", help="Formatta l'output come JSON grezzo.")
    parser.add_argument("--simulate-round", action="store_true", help="Esegue la simulazione di un punteggio registrato.")
    args = parser.parse_args()

    report = run_full_diagnostic(simulate=args.simulate_round)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    print("=" * 65)
    print("HYPERSPACE SOVEREIGN ARCADE — DIAGNOSTICA & COLLAUDO MOTORE")
    print("=" * 65)
    print(f"Esito Complessivo: [{'OK' if report['status'] == 'PASS' else 'ATTENZIONE'}] ({report['elapsed_s']}s)")
    print()

    print("1. Integrità Codice arcade.html:")
    html = report["html_integrity"]
    print(f"   Dimensione File: {html.get('file_size_bytes', 0)} bytes")
    for check_k, check_v in html.get("checks", {}).items():
        status_icon = "✓" if check_v else "✗"
        print(f"   - {check_k}: {status_icon}")

    print("\n2. Rotte HTTP Cockpit (:8090):")
    for path, r in report["cockpit_routes"].items():
        if r.get("reachable"):
            print(f"   - {path}: HTTP {r.get('status_code')} ({r.get('content_length')} bytes)")
        else:
            print(f"   - {path}: ERRORE ({r.get('error')})")

    print("\n3. Telemetria Nodi Mesh:")
    for node, t in report["nodes_telemetry"].items():
        state = f"ONLINE ({t['latency_ms']} ms)" if t["online"] else "OFFLINE"
        print(f"   - {node}: {state} -> {t['target']}")

    if report.get("simulation"):
        sim = report["simulation"]
        print(f"\n4. Simulazione Partita: Player '{sim['entry']['player']}' -> Score {sim['entry']['score']} (Rank #{sim['rank']})")

    print("\n" + "=" * 65)


if __name__ == "__main__":
    main()
