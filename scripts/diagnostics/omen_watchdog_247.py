#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# scripts/diagnostics/omen_watchdog_247.py
"""Supervisore e Watchdog 24/7 per HP OMEN 16 (HyperSpace AGI).

Monitora salute dei servizi, latenza di rete, carico e temperature hardware.
Supporta esecuzione locale sull'host OMEN (con lettura nvidia-smi) o remota
dal Mac/mesh via Tailscale.

Funzionalità principali:
1. Health check HTTP/TCP delle superfici chiave (Node 8081, Ollama 11434, ComfyUI 8188, Hermes 8098, CP 8085).
2. Monitoraggio termico GPU/CPU con creazione flag di throttling (`data/thermal_pause.flag`).
3. Logging continuo per audit di affidabilità su `data/omen_247_telemetry.jsonl`.

Uso:
    python scripts/diagnostics/omen_watchdog_247.py
    python scripts/diagnostics/omen_watchdog_247.py --target 100.104.238.125
    python scripts/diagnostics/omen_watchdog_247.py --daemon --interval 30
    python scripts/diagnostics/omen_watchdog_247.py --json
"""

import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

import requests

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OMEN_IP = "100.104.238.125"
TELEMETRY_LOG = ROOT / "data" / "omen_247_telemetry.jsonl"
THERMAL_FLAG = ROOT / "data" / "thermal_pause.flag"

SERVICES_MAP = [
    {"name": "Node API (8081)", "port": 8081, "path": "/status", "critical": True},
    {"name": "Ollama LLM (11434)", "port": 11434, "path": "/api/tags", "critical": True},
    {"name": "ComfyUI (8188)", "port": 8188, "path": "/system_stats", "critical": False},
    {"name": "Hermes Memory (8098)", "port": 8098, "path": "/health", "critical": False},
    {"name": "Control Plane (8085)", "port": 8085, "path": "/health", "critical": False},
]


def check_tcp_port(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def probe_http_service(host: str, port: int, path: str = "", timeout: float = 2.5) -> Dict[str, Any]:
    url = f"http://{host}:{port}{path}"
    start = time.perf_counter()
    res: Dict[str, Any] = {
        "url": url,
        "reachable": False,
        "status_code": None,
        "latency_ms": None,
        "details": None,
    }
    try:
        r = requests.get(url, timeout=timeout)
        elapsed = (time.perf_counter() - start) * 1000.0
        res["reachable"] = True
        res["status_code"] = r.status_code
        res["latency_ms"] = round(elapsed, 1)
        if r.status_code == 200:
            try:
                res["details"] = r.json()
            except Exception:
                res["details"] = r.text[:80]
    except Exception as e:
        res["error"] = str(e)
    return res


def read_local_gpu_metrics() -> Optional[Dict[str, Any]]:
    nvsmi = shutil.which("nvidia-smi")
    if not nvsmi:
        return None
    try:
        cmd = [
            nvsmi,
            "--query-gpu=temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.used",
            "--format=csv,noheader,nounits",
        ]
        out = subprocess.check_output(cmd, text=True, timeout=2.0).strip()
        parts = [p.strip() for p in out.split(",")]
        if len(parts) >= 5:
            return {
                "temp_c": int(parts[0]),
                "gpu_util_pct": int(parts[1]),
                "mem_util_pct": int(parts[2]),
                "vram_total_mb": int(parts[3]),
                "vram_used_mb": int(parts[4]),
            }
    except Exception:
        pass
    return None


def read_local_cpu_metrics() -> Dict[str, Any]:
    metrics: Dict[str, Any] = {"load_1m": None, "cpu_count": os.cpu_count()}
    try:
        if hasattr(os, "getloadavg"):
            metrics["load_1m"] = round(os.getloadavg()[0], 2)
    except Exception:
        pass
    return metrics


def evaluate_thermal_guard(gpu_metrics: Optional[Dict[str, Any]], max_gpu_temp: int = 82) -> bool:
    """Restituisce True se c'è surriscaldamento attivo e aggiorna il flag di pausa."""
    if not gpu_metrics:
        return False
    temp = gpu_metrics.get("temp_c", 0)
    if temp >= max_gpu_temp:
        THERMAL_FLAG.parent.mkdir(parents=True, exist_ok=True)
        THERMAL_FLAG.write_text(f"GPU_OVERHEAT:{temp}C at {datetime.datetime.now().isoformat()}\n", encoding="utf-8")
        return True
    elif temp < (max_gpu_temp - 10) and THERMAL_FLAG.exists():
        try:
            THERMAL_FLAG.unlink()
        except OSError:
            pass
    return False


def run_single_probe(host: str, max_gpu_temp: int = 82) -> Dict[str, Any]:
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    is_local = host in ("127.0.0.1", "localhost", socket.gethostname())

    gpu_info = read_local_gpu_metrics() if is_local else None
    cpu_info = read_local_cpu_metrics() if is_local else None
    thermal_alert = evaluate_thermal_guard(gpu_info, max_gpu_temp)

    services_results = []
    all_critical_ok = True

    for s in SERVICES_MAP:
        port = s["port"]
        name = s["name"]
        path = s["path"]
        critical = s["critical"]

        port_open = check_tcp_port(host, port)
        http_data = probe_http_service(host, port, path) if port_open else None

        ok = port_open and (http_data is not None and http_data.get("status_code") in (200, 404))
        if critical and not ok:
            all_critical_ok = False

        services_results.append({
            "service": name,
            "port": port,
            "port_open": port_open,
            "ok": ok,
            "latency_ms": http_data.get("latency_ms") if http_data else None,
            "status_code": http_data.get("status_code") if http_data else None,
        })

    report: Dict[str, Any] = {
        "timestamp": timestamp,
        "target_host": host,
        "is_local": is_local,
        "status": "HEALTHY" if all_critical_ok else "DEGRADED",
        "thermal_alert": thermal_alert,
        "gpu": gpu_info,
        "cpu": cpu_info,
        "services": services_results,
    }
    return report


def print_cli_summary(report: Dict[str, Any]):
    print("=" * 64)
    status_icon = "🟢" if report["status"] == "HEALTHY" else "🔴"
    print(f" {status_icon} HP OMEN 16 - 24/7 WATCHDOG REPORT | Stato: {report['status']}")
    print(f"    Target: {report['target_host']} | Timestamp: {report['timestamp']}")
    print("=" * 64)

    if report.get("gpu"):
        g = report["gpu"]
        t_icon = "🔥" if report["thermal_alert"] else "❄️"
        print(f" [GPU RTX 3070] Temp: {t_icon} {g['temp_c']}°C | Carico: {g['gpu_util_pct']}% | VRAM: {g['vram_used_mb']}/{g['vram_total_mb']} MB")
        if report["thermal_alert"]:
            print(" ⚠️ ALLERTA TERMICA ATTIVA: carichi batch e sogni messi in pausa temporanea.")
    else:
        print(" [GPU/CPU] Monitoraggio hardware host attivo in locale o da telemetria interna.")

    print("\n Servizi Supervisionati:")
    print(" ----------------------------------------------------------------")
    print(f" {'SERVIZIO':<24} | {'PORTA':<6} | {'STATO':<8} | {'LATENZA':<10}")
    print(" ----------------------------------------------------------------")
    for s in report["services"]:
        s_icon = "OK " if s["ok"] else "FAIL"
        lat = f"{s['latency_ms']} ms" if s['latency_ms'] is not None else "--"
        print(f" {s['service']:<24} | {s['port']:<6} | {s_icon:<8} | {lat:<10}")
    print("=" * 64)


def main():
    parser = argparse.ArgumentParser(description="Watchdog e Supervisore 24/7 per HP OMEN 16")
    parser.add_argument("--target", default=DEFAULT_OMEN_IP, help=f"Host/IP target (default: {DEFAULT_OMEN_IP})")
    parser.add_argument("--max-gpu-temp", type=int, default=82, help="Soglia termica GPU massima in °C (default: 82)")
    parser.add_argument("--daemon", action="store_true", help="Esegui in loop continuo di monitoraggio")
    parser.add_argument("--interval", type=int, default=30, help="Intervallo in secondi fra i check (default: 30)")
    parser.add_argument("--json", action="store_true", help="Output in formato JSON puro")
    args = parser.parse_args()

    while True:
        report = run_single_probe(args.target, max_gpu_temp=args.max_gpu_temp)

        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_cli_summary(report)

        if args.daemon:
            TELEMETRY_LOG.parent.mkdir(parents=True, exist_ok=True)
            with TELEMETRY_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(report) + "\n")
            time.sleep(args.interval)
        else:
            break


if __name__ == "__main__":
    main()
