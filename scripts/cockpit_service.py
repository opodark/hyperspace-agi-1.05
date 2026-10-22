#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
HyperSpace Cockpit Live API & Web Service.
Fornisce il backend real-time per la dashboard Operations Cockpit su porta 8090:
- Serve i file statici di web-node/apps/playground/
- Espone /api/status per la telemetria live dei nodi (Mac, Omen, ASUS, Control Plane)
- Espone /api/ping per misurazioni reali di latenza round-trip
- Espone /api/exec per inferenza diretta via Liquid AI LFM2.5 con firma ECDSA
- Espone /api/missions per consultare e avviare missioni reali su Mission Control
- Espone /api/plan per generare piani DAG CoT tramite LFM2.5
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Carica identità per firma ECDSA inter-nodo
try:
    from shared.identity import generate_or_load_identity, make_request_headers
    NODE_IDENTITY = generate_or_load_identity()
except Exception as exc:
    NODE_IDENTITY = None
    print(f"[WARN] Identità locale non caricata: {exc}")

# Configurazione nodi
OMEN_URL = os.getenv("OMEN_NODE_URL", "http://100.104.238.125:8081")
ASUS_URL = os.getenv("ASUS_NODE_URL", "http://100.64.31.18:8081")
ASUS_OLLAMA_URL = os.getenv("ASUS_OLLAMA_URL", "http://100.64.31.18:11434")
MAC_OLLAMA_URL = os.getenv("MAC_OLLAMA_URL", "http://localhost:11434")
CP_URL = os.getenv("HYPERSPACE_CP_URL", "http://localhost:8085")
STATIC_DIR = REPO_ROOT / "web-node" / "apps" / "playground"

# Token per Mission Control
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except Exception:
    pass

DREAM_REVIEW_TOKEN = os.getenv("DREAM_REVIEW_TOKEN", "")
MISSIONS_FILE = REPO_ROOT / "data" / "missions.jsonl"


def fetch_json(url: str, headers: dict | None = None, timeout: float = 3.0) -> dict | None:
    hdrs = {"Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def probe_node_ping(host_port: str, timeout: float = 2.0) -> dict:
    parts = host_port.replace("http://", "").replace("https://", "").split(":")
    host = parts[0]
    port = int(parts[1]) if len(parts) > 1 else 80
    t0 = time.time()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        elapsed_ms = round((time.time() - t0) * 1000, 2)
        return {"reachable": True, "latency_ms": elapsed_ms, "host": host, "port": port}
    except Exception as exc:
        return {"reachable": False, "error": str(exc), "host": host, "port": port}


class CockpitHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == "/lite" or self.path == "/lite.html":
            lite_file = REPO_ROOT / "web-node" / "apps" / "playground" / "lite.html"
            if lite_file.exists():
                content = lite_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
        if self.path.startswith("/api/status"):
            self.handle_api_status()
        elif self.path.startswith("/api/ping"):
            self.handle_api_ping()
        elif self.path.startswith("/api/missions"):
            self.handle_api_missions()
        elif self.path.startswith("/api/devloop"):
            self.handle_api_devloop()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/exec"):
            self.handle_api_exec()
        elif self.path.startswith("/api/plan"):
            self.handle_api_plan()
        elif self.path.startswith("/api/missions"):
            self.handle_api_missions_create()
        else:
            self.send_error(404, "Endpoint non trovato")

    def handle_api_status(self):
        # 1. Mac local power & status
        power_path = REPO_ROOT / "data" / "host_power.json"
        mac_power = {}
        if power_path.exists():
            try:
                mac_power = json.loads(power_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # 2. HP Omen status
        omen_status = fetch_json(f"{OMEN_URL}/status", timeout=2.5)

        # 3. ASUS status
        asus_status = fetch_json(f"{ASUS_URL}/status", timeout=1.5)

        # 4. Control Plane status
        cp_health = fetch_json(f"{CP_URL}/health", timeout=1.5)

        response_data = {
            "timestamp": time.time(),
            "nodes": {
                "mac": {
                    "id": "mac",
                    "name": "Mac M5 Hub",
                    "role": "Authority Control Plane",
                    "status": "ONLINE",
                    "hardware": "16 GB Unified Memory (Metal)",
                    "power": mac_power.get("source", "AC Power"),
                    "battery_pct": mac_power.get("battery_pct", 36),
                    "ac_line": mac_power.get("ac_line", True),
                    "active_model": "LFM2.5-8B-A1B-Abliterated",
                    "endpoint": "http://127.0.0.1:8085"
                },
                "omen": {
                    "id": "omen",
                    "name": "HP Omen 16",
                    "role": "GPU Worker (Architect & Gate)",
                    "status": "ONLINE" if omen_status else "OFFLINE",
                    "hardware": f"RTX 3070 {omen_status.get('vram_gb', 8.0)}GB VRAM + 32GB RAM" if omen_status else "RTX 3070 8GB VRAM",
                    "power": "AC Line Power" if (omen_status and omen_status.get("ac_line")) else "Battery",
                    "battery_pct": omen_status.get("battery_pct", 100) if omen_status else 100,
                    "ac_line": omen_status.get("ac_line", True) if omen_status else True,
                    "active_model": "LFM2.5-24B-A2B-Uncensored (64k)",
                    "saturation": omen_status.get("saturation", 0.0) if omen_status else 0.0,
                    "uptime_s": omen_status.get("uptime_s", 0) if omen_status else 0,
                    "endpoint": OMEN_URL
                },
                "asus": {
                    "id": "asus",
                    "name": "ASUS V16",
                    "role": "Lead Coder (40B MoE @ 128k)",
                    "status": "ONLINE" if asus_status else "STANDBY / SLEEP",
                    "hardware": f"RTX 5060 {asus_status.get('vram_gb', 8.0)}GB + 48GB RAM" if asus_status else "48GB RAM + RTX 5060 8GB",
                    "power": "AC Power" if (asus_status and asus_status.get("ac_line", True)) else "Battery",
                    "battery_pct": asus_status.get("battery_pct", 100) if asus_status else 100,
                    "ac_line": asus_status.get("ac_line", True) if asus_status else True,
                    "active_model": "Flint-40B-MoE (128k, NVFP4)",
                    "endpoint": ASUS_URL
                }
            },
            "control_plane": {
                "status": "ONLINE" if cp_health else "OFFLINE",
                "version": cp_health.get("version", "1.05.0") if cp_health else "unknown",
                "memories": cp_health.get("memories", 0) if cp_health else 0,
                "nodes_active": cp_health.get("nodes_active", 0) if cp_health else 0
            }
        }
        self.send_json(response_data)

    def handle_api_ping(self):
        # Legge il target dai query params
        target = "omen"
        if "?" in self.path:
            query = self.path.split("?", 1)[1]
            for part in query.split("&"):
                if part.startswith("node="):
                    target = part.split("=")[1].lower()

        endpoints = {
            "omen": OMEN_URL,
            "asus": ASUS_URL,
            "mac": "http://127.0.0.1:11434",
            "cp": CP_URL
        }
        url = endpoints.get(target, OMEN_URL)
        ping_res = probe_node_ping(url)
        ping_res["target"] = target
        ping_res["url"] = url
        self.send_json(ping_res)

    def handle_api_exec(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as exc:
            self.send_json({"error": f"Payload non valido: {exc}"}, status=400)
            return

        prompt = body.get("prompt", "").strip()
        target = body.get("target", "omen").lower()
        model = body.get("model", "hf.co/DuoNeural/LFM2.5-8B-A1B-Abliterated-GGUF:Q4_K_M")

        if not prompt:
            self.send_json({"error": "Prompt vuoto"}, status=400)
            return

        t0 = time.time()
        # Chiamata a HP Omen con firma crittografica
        if target == "omen" and NODE_IDENTITY:
            omen_payload = json.dumps({
                "task_id": f"cockpit-exec-{int(time.time() * 1000)}",
                "model": model,
                "prompt": prompt
            }).encode("utf-8")

            hdrs = {"Content-Type": "application/json"}
            hdrs.update(make_request_headers(
                NODE_IDENTITY["node_id"],
                NODE_IDENTITY["public_key"],
                NODE_IDENTITY["_private_key"],
                body=omen_payload
            ))

            req = urllib.request.Request(f"{OMEN_URL}/execute", data=omen_payload, headers=hdrs)
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                elapsed = time.time() - t0
                raw_resp = data.get("response", "")
                thought, content = self._split_thought(raw_resp)
                self.send_json({
                    "status": "ok",
                    "target": "omen",
                    "elapsed_s": round(elapsed, 2),
                    "thought": thought,
                    "response": content
                })
            except Exception as exc:
                self.send_json({"error": f"Errore inferenza Omen: {exc}", "elapsed_s": round(time.time() - t0, 2)}, status=502)
        elif target == "asus":
            # Chiamata ad ASUS V16 (Flint 40B @ 128k su Ollama o Node Worker)
            asus_model = model if model != "hf.co/DuoNeural/LFM2.5-8B-A1B-Abliterated-GGUF:Q4_K_M" else "flint:latest"
            asus_payload = json.dumps({
                "model": asus_model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_ctx": 131072, "num_predict": 1500}
            }).encode("utf-8")
            req = urllib.request.Request(f"{ASUS_OLLAMA_URL}/api/generate", data=asus_payload, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=180) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                elapsed = time.time() - t0
                raw_resp = data.get("response", "")
                thought, content = self._split_thought(raw_resp)
                self.send_json({
                    "status": "ok",
                    "target": "asus",
                    "model": asus_model,
                    "elapsed_s": round(elapsed, 2),
                    "thought": thought,
                    "response": content
                })
            except Exception as exc:
                self.send_json({"error": f"Errore inferenza ASUS: {exc}", "elapsed_s": round(time.time() - t0, 2)}, status=502)
        else:
            # Fallback Mac Ollama
            mac_payload = json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False
            }).encode("utf-8")
            req = urllib.request.Request(f"{MAC_OLLAMA_URL}/api/generate", data=mac_payload, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                elapsed = time.time() - t0
                raw_resp = data.get("response", "")
                thought, content = self._split_thought(raw_resp)
                self.send_json({
                    "status": "ok",
                    "target": "mac",
                    "elapsed_s": round(elapsed, 2),
                    "thought": thought,
                    "response": content
                })
            except Exception as exc:
                self.send_json({"error": f"Errore inferenza Mac: {exc}", "elapsed_s": round(time.time() - t0, 2)}, status=502)

    def handle_api_plan(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as exc:
            self.send_json({"error": f"Payload non valido: {exc}"}, status=400)
            return

        objective = body.get("objective", "").strip()
        criteria = body.get("criteria", [])
        if not objective:
            self.send_json({"error": "Obiettivo mancante"}, status=400)
            return

        crit_str = "\n".join(f"- {c}" for c in criteria) if criteria else "- Verifica conformità e funzionamento"
        plan_prompt = (
            "You are the planner of a bounded, auditable mission on HyperSpace AGI. Segui rigorosamente AGENTS.md.\n"
            f"Objective: {objective}\n"
            f"Success criteria:\n{crit_str}\n\n"
            "Return STRICT JSON with no prose:\n"
            '{"tasks":[{"key":"kebab-id","role":"coder","title":"short title","instruction":"precise work order","dependencies":[],"max_attempts":2}]}\n'
        )

        model = "hf.co/DuoNeural/LFM2.5-8B-A1B-Abliterated-GGUF:Q4_K_M"
        payload = json.dumps({"task_id": f"plan-{int(time.time()*1000)}", "model": model, "prompt": plan_prompt}).encode("utf-8")
        hdrs = {"Content-Type": "application/json"}
        if NODE_IDENTITY:
            hdrs.update(make_request_headers(NODE_IDENTITY["node_id"], NODE_IDENTITY["public_key"], NODE_IDENTITY["_private_key"], body=payload))

        t0 = time.time()
        try:
            req = urllib.request.Request(f"{OMEN_URL}/execute", data=payload, headers=hdrs)
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            elapsed = time.time() - t0
            raw_resp = data.get("response", "")
            thought, content = self._split_thought(raw_resp)

            # Estrai JSON puro
            json_match = re.search(r"(\{.*\})", content, re.DOTALL)
            parsed_plan = {}
            if json_match:
                try:
                    parsed_plan = json.loads(json_match.group(1))
                except Exception:
                    parsed_plan = {"raw": content}
            else:
                parsed_plan = {"raw": content}

            self.send_json({
                "status": "ok",
                "elapsed_s": round(elapsed, 2),
                "thought": thought,
                "plan": parsed_plan
            })
        except Exception as exc:
            self.send_json({"error": f"Errore pianificazione: {exc}"}, status=502)

    def handle_api_missions(self):
        missions = []
        if MISSIONS_FILE.exists():
            try:
                for line in MISSIONS_FILE.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line:
                        missions.append(json.loads(line))
            except Exception:
                pass
        # Restituisci le ultime 10 missioni
        self.send_json({"missions": missions[-10:] if missions else []})

    def handle_api_missions_create(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as exc:
            self.send_json({"error": f"Payload non valido: {exc}"}, status=400)
            return

        hdrs = {"Content-Type": "application/json"}
        if DREAM_REVIEW_TOKEN:
            hdrs["Authorization"] = f"Bearer {DREAM_REVIEW_TOKEN}"

        req = urllib.request.Request(f"{CP_URL}/missions", data=json.dumps(body).encode("utf-8"), headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
            self.send_json(res_data, status=201)
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8")
            self.send_json({"error": f"HTTP {he.code}: {err_body}"}, status=he.code)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=502)

    def handle_api_devloop(self):
        dev_loop_file = REPO_ROOT / "data" / "omen_dev_loop.jsonl"
        recent_cycles = []
        if dev_loop_file.exists():
            try:
                for line in dev_loop_file.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]:
                    if line.strip():
                        recent_cycles.append(json.loads(line))
            except Exception:
                pass

        dataset_file = REPO_ROOT / "data" / "synthetic_cot_dataset.jsonl"
        cot_samples_count = 0
        latest_sample = None
        if dataset_file.exists():
            try:
                lines = [l for l in dataset_file.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
                cot_samples_count = len(lines)
                if lines:
                    latest_sample = json.loads(lines[-1])
            except Exception:
                pass

        chronicle_file = REPO_ROOT / "data" / "codebase_chronicle.jsonl"
        recent_chronicles = []
        if chronicle_file.exists():
            try:
                for line in chronicle_file.read_text(encoding="utf-8", errors="replace").splitlines()[-10:]:
                    if line.strip():
                        recent_chronicles.append(json.loads(line))
            except Exception:
                pass

        telemetry_file = REPO_ROOT / "data" / "omen_247_telemetry.jsonl"
        thermal_status = {"temp_c": None, "alert": False}
        if telemetry_file.exists():
            try:
                lines = [l for l in telemetry_file.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
                if lines:
                    last_t = json.loads(lines[-1])
                    if last_t.get("gpu"):
                        thermal_status["temp_c"] = last_t["gpu"].get("temp_c")
                    thermal_status["alert"] = last_t.get("thermal_alert", False)
            except Exception:
                pass

        self.send_json({
            "status": "ok",
            "timestamp": time.time(),
            "total_cycles": len(recent_cycles),
            "recent_cycles": recent_cycles[-5:],
            "cot_samples_count": cot_samples_count,
            "latest_sample": latest_sample,
            "recent_chronicles": recent_chronicles[-5:],
            "thermal": thermal_status,
        })

    def _split_thought(self, text: str) -> tuple[str, str]:
        if "</think>" in text:
            parts = text.split("</think>")
            thought = parts[0].replace("<think>", "").strip()
            content = parts[-1].strip()
            return thought, content
        return "", text.strip()

    def send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_service(port: int = 8090):
    server = ThreadingHTTPServer(("0.0.0.0", port), CockpitHandler)
    print("=" * 65)
    print(f"  HYPERSPACE OPERATIONS COCKPIT SERVICE")
    print(f"  Ascolto su: http://0.0.0.0:{port} (http://localhost:{port})")
    print(f"  Target Mesh: {OMEN_URL} (Omen) | {ASUS_URL} (Asus)")
    print(f"  Control Plane: {CP_URL}")
    print("=" * 65)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    run_service(port)
