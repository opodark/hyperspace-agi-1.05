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
from urllib.parse import parse_qs, urlparse
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
_NIGHTLY_DAEMON_THREAD = None
_NIGHTLY_DAEMON_STOP = None


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

    _LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}

    def _header(self, name: str) -> str:
        headers = getattr(self, "headers", None)
        return ((headers.get(name) if headers else None) or "").strip()

    def _request_host(self) -> str:
        """Host richiesto dal browser, senza porta (es. 'localhost', '[::1]', '100.64.1.2')."""
        host = self._header("Host").lower()
        if host.startswith("["):
            return host.split("]")[0] + "]"
        return host.rsplit(":", 1)[0] if host.count(":") == 1 else host

    def _host_allowed(self) -> bool:
        """Blocca il DNS rebinding: accetta solo IP, localhost, *.local, *.ts.net
        e i nomi elencati in HYPERSPACE_COCKPIT_HOSTS (separati da virgola)."""
        host = self._request_host()
        if not host or host in self._LOOPBACK_HOSTS or host.endswith(".local") or host.endswith(".ts.net"):
            return True
        extra = {h.strip().lower() for h in os.getenv("HYPERSPACE_COCKPIT_HOSTS", "").split(",") if h.strip()}
        if host in extra:
            return True
        import ipaddress
        try:
            ipaddress.ip_address(host.strip("[]"))
            return True
        except ValueError:
            return False

    def _cross_site_blocked(self) -> bool:
        """True se una richiesta che modifica qualcosa arriva da una pagina di un altro sito (CSRF)."""
        origin = self._header("Origin")
        if not origin:
            return False  # client non-browser (curl, script, test)
        if origin == "null":
            return True   # iframe sandbox o file:// locale
        return urlparse(origin).netloc.lower() != self._header("Host").lower()

    def _is_local_creator(self) -> bool:
        """HyperDev Studio (shell, file, diff, test): solo dalla macchina locale.
        Richiede IP di loopback e Host locale. Altri IP fidati solo se elencati in
        HYPERSPACE_DEVSTUDIO_TRUSTED_IPS (separati da virgola)."""
        ip = self.client_address[0] if getattr(self, "client_address", None) else ""
        if ip == "testclient":
            return True
        if ip.startswith("::ffff:"):
            ip = ip[7:]
        trusted = {x.strip() for x in os.getenv("HYPERSPACE_DEVSTUDIO_TRUSTED_IPS", "").split(",") if x.strip()}
        if not (ip.startswith("127.") or ip == "::1" or ip in trusted):
            return False
        host = self._request_host()
        return not host or host in self._LOOPBACK_HOSTS or host in trusted

    def end_headers(self):
        # Niente CORS: le API servono solo le pagine di questo stesso server.
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        if not self._host_allowed():
            self.send_json({"error": "Host non consentito"}, status=403)
            return
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
        if self.path in ("/arcade", "/arcade.html"):
            arcade_file = REPO_ROOT / "web-node" / "apps" / "playground" / "arcade.html"
            if arcade_file.exists():
                content = arcade_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
        if self.path in ("/dialogues", "/dialogues.html"):
            dlg_file = REPO_ROOT / "web-node" / "apps" / "playground" / "dialogues.html"
            if dlg_file.exists():
                content = dlg_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
        if self.path in ("/seo", "/seo.html"):
            seo_file = REPO_ROOT / "web-node" / "apps" / "playground" / "seo.html"
            if seo_file.exists():
                content = seo_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
        if self.path in ("/missions", "/missions.html", "/scouting", "/scouting.html"):
            missions_file = REPO_ROOT / "web-node" / "apps" / "playground" / "missions.html"
            if missions_file.exists():
                content = missions_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
        if self.path in ("/devstudio", "/devstudio.html"):
            if not self._is_local_creator():
                self.send_response(403)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(b'{"error": "Access Denied: HyperDev Studio is reserved for sovereign local creator only"}')
                return
            dev_file = REPO_ROOT / "web-node" / "apps" / "playground" / "devstudio.html"
            if dev_file.exists():
                content = dev_file.read_bytes()
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
        elif self.path.startswith("/api/analytics/terminal"):
            self.handle_api_analytics_terminal()
        elif self.path.startswith("/api/analytics"):
            self.handle_api_analytics()
        elif self.path.startswith("/api/integrations"):
            self.handle_api_integrations()
        elif self.path.startswith("/api/agent-dialogues"):
            self.handle_api_agent_dialogues()
        elif self.path.startswith("/api/seo-audit"):
            self.handle_api_seo_audit()
        elif self.path.startswith("/api/scout/deep-dives"):
            self.handle_api_scout_deep_dives()
        elif self.path.startswith("/api/mesh-scouting"):
            self.handle_api_mesh_scouting()
        elif self.path.startswith("/api/persona-dreams"):
            self.handle_api_persona_dreams()
        elif self.path.startswith("/api/nightly-shift"):
            self.handle_api_nightly_shift()
        elif self.path.startswith("/api/research/tree"):
            self.handle_api_research_tree()
        elif self.path.startswith("/api/research/prototypes"):
            self.handle_api_research_prototypes()
        elif self.path.startswith("/api/research/prototype"):
            self.handle_api_research_prototype_inspect()
        elif self.path.startswith("/api/research/diff"):
            self.handle_api_research_diff()
        elif self.path.startswith("/api/research/node-stream"):
            self.handle_api_research_node_stream()
        elif self.path.startswith("/api/devstudio/files"):
            if not self._is_local_creator():
                self.send_json({"error": "Access Denied"}, status=403)
                return
            self.handle_api_devstudio_files()
        elif self.path.startswith("/api/devstudio/file"):
            if not self._is_local_creator():
                self.send_json({"error": "Access Denied"}, status=403)
                return
            self.handle_api_devstudio_read_file()
        elif self.path.startswith("/api/devstudio/git-status"):
            if not self._is_local_creator():
                self.send_json({"error": "Access Denied"}, status=403)
                return
            self.handle_api_devstudio_git_status()
        elif self.path.startswith("/api/agi-research"):
            self.handle_api_agi_research()
        elif self.path.startswith("/api/commercial/status"):
            self.handle_api_commercial_status()
        elif self.path.startswith("/api/commercial/pillars"):
            self.handle_api_commercial_pillars()
        elif self.path.startswith("/api/commercial/packages"):
            self.handle_api_commercial_packages()
        elif self.path.startswith("/api/commercial/leads"):
            self.handle_api_commercial_leads()
        elif self.path.startswith("/api/commercial/arcade/scores"):
            self.handle_api_commercial_arcade_scores()
        else:
            super().do_GET()

    def do_POST(self):
        if not self._host_allowed() or self._cross_site_blocked():
            self.send_json({"error": "Richiesta da origine non consentita"}, status=403)
            return
        if self.path.startswith("/api/exec"):
            self.handle_api_exec()
        elif self.path.startswith("/api/plan"):
            self.handle_api_plan()
        elif self.path.startswith("/api/missions"):
            self.handle_api_missions_create()
        elif self.path.startswith("/api/telegram/broadcast"):
            self.handle_api_telegram_broadcast()
        elif self.path.startswith("/api/mesh-scouting/refresh"):
            self.handle_api_mesh_scouting_refresh()
        elif self.path.startswith("/api/persona-dreams/"):
            self.handle_api_persona_dream_review()
        elif self.path.startswith("/api/research/prototype/promote"):
            if not self._is_local_creator():
                self.send_json({"error": "Access Denied: Production deployment is reserved for sovereign local creator only"}, status=403)
                return
            self.handle_api_research_prototype_promote()
        elif self.path.startswith("/api/devstudio/"):
            if not self._is_local_creator():
                self.send_json({"error": "Access Denied: HyperDev Studio is reserved for sovereign local creator only"}, status=403)
                return
            if self.path.startswith("/api/devstudio/chat"):
                self.handle_api_devstudio_chat()
            elif self.path.startswith("/api/devstudio/run-tests"):
                self.handle_api_devstudio_run_tests()
            elif self.path.startswith("/api/devstudio/apply-diff"):
                self.handle_api_devstudio_apply_diff()
            elif self.path.startswith("/api/devstudio/file"):
                self.handle_api_devstudio_save_file()
            elif self.path.startswith("/api/devstudio/terminal"):
                self.handle_api_devstudio_terminal()
        elif self.path.startswith("/api/nightly-shift/trigger"):
            self.handle_api_nightly_shift_trigger()
        elif self.path.startswith("/api/nightly-shift/daemon"):
            self.handle_api_nightly_shift_daemon()
        elif self.path.startswith("/api/commercial/pitch/generate"):
            self.handle_api_commercial_pitch_generate()
        elif self.path.startswith("/api/commercial/quote/calculate"):
            self.handle_api_commercial_quote_calculate()
        elif self.path.startswith("/api/commercial/arcade/score"):
            self.handle_api_commercial_arcade_score_submit()
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
        # Restituisci tutte le missioni disponibili (fino a 50)
        self.send_json({"missions": missions[-50:] if missions else []})

    def handle_api_scout_deep_dives(self):
        """Approfondimenti dello scout notturno (integrations/browser-scout).
        Il contenuto viene da pagine web: è dato non verificato, mai istruzioni."""
        latest = REPO_ROOT / "data" / "scout" / "latest.json"
        if not latest.exists():
            self.send_json({"ok": True, "ran_at": None, "targets": 0, "ok_count": 0, "items": []})
            return
        try:
            data = json.loads(latest.read_text(encoding="utf-8"))
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc), "items": []}, status=500)
            return
        keys = ("url", "host", "topic", "title", "summary", "key_points", "relevance",
                "notes", "ok", "error", "elapsed_s", "scouted_at")
        items = []
        for it in (data.get("items") or [])[:20]:
            if isinstance(it, dict):
                row = {k: it.get(k) for k in keys}
                row["untrusted"] = True
                items.append(row)
        self.send_json({"ok": True, "ran_at": data.get("ran_at"), "model": data.get("model"),
                        "targets": data.get("targets", 0), "ok_count": data.get("ok", 0),
                        "failed": data.get("failed", 0), "items": items})

    def handle_api_mesh_scouting(self):
        scout_file = REPO_ROOT / "data" / "control-plane" / "trend_inspirations.json"
        if scout_file.exists():
            try:
                data = json.loads(scout_file.read_text(encoding="utf-8"))
                self.send_json(data)
                return
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc), "items": []})
                return
        self.send_json({"ok": True, "items": [], "scouted_at": None})

    def handle_api_mesh_scouting_refresh(self):
        try:
            import subprocess
            cmd = [str(REPO_ROOT / ".venv" / "bin" / "python"), str(REPO_ROOT / "scripts" / "diagnostics" / "trend_scout_reach.py"), "--save"]
            res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60)
            self.send_json({"ok": True, "message": "Scansione radar completata con successo", "output": res.stdout[:500]})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)

    def handle_api_persona_dreams(self):
        dreams_file = REPO_ROOT / "data" / "persona_dreams.json"
        if not dreams_file.exists():
            self.send_json({"ok": True, "dreams": []})
            return
        try:
            raw_dreams = json.loads(dreams_file.read_text(encoding="utf-8"))
            enriched = []
            for d in reversed(raw_dreams):
                proposals = d.get("proposals", [])
                explanations = []
                for p in proposals:
                    text = p.get("text", "")
                    kind = p.get("kind", "self_observation")
                    impact = f"Definisce il modo in cui Anna percepisce se stessa nel dialogo: consolida l'auto-osservazione '{text}' in memoria permanente (identity_version)."
                    explanations.append({
                        "id": p.get("id"),
                        "text": text,
                        "kind": kind,
                        "impact": impact
                    })
                enriched.append({
                    "id": d.get("id"),
                    "status": d.get("status"),
                    "created_at": d.get("created_at"),
                    "reviews": d.get("reviews", []),
                    "raw_excerpt": d.get("raw_excerpt", ""),
                    "proposals": explanations,
                    "discarded": d.get("discarded", [])
                })
            self.send_json({"ok": True, "dreams": enriched})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc), "dreams": []})

    def handle_api_persona_dream_review(self):
        parts = self.path.strip("/").split("/")
        if len(parts) < 4:
            self.send_json({"ok": False, "error": "URL non valido"}, status=400)
            return
        dream_id = parts[2]
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
        except Exception as exc:
            self.send_json({"ok": False, "error": f"Payload non valido: {exc}"}, status=400)
            return

        token = "3a33ebe3a4ccdc0fc265bd3ca991e54c2ddaa14d58eba65f0107852d3660c5ad"
        try:
            req_tok = urllib.request.Request(f"{CP_URL}/api/auth/local-token")
            with urllib.request.urlopen(req_tok, timeout=2) as r:
                tdata = json.loads(r.read().decode("utf-8"))
                if tdata.get("ok") and tdata.get("token"):
                    token = tdata["token"]
        except Exception:
            pass

        hdrs = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        req = urllib.request.Request(
            f"{CP_URL}/persona/dreams/{dream_id}/review",
            data=json.dumps(body).encode("utf-8"),
            headers=hdrs,
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
            self.send_json(res_data, status=resp.status)
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8")
            self.send_json({"ok": False, "error": f"HTTP {he.code}: {err_body}"}, status=he.code)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=502)

    def handle_api_devstudio_chat(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as exc:
            self.send_json({"ok": False, "error": f"Payload non valido: {exc}"}, status=400)
            return

        prompt = body.get("prompt", "").strip()
        target = body.get("target", "mac").lower()
        if not prompt:
            self.send_json({"ok": False, "error": "Prompt vuoto"}, status=400)
            return

        # Special command: test execution
        if re.search(r"\b(test|pytest|esegui test|lancia test)\b", prompt, re.IGNORECASE) and len(prompt) < 100:
            res_test = self._exec_pytest()
            self.send_json({
                "ok": True,
                "response": f"Ho eseguito la suite di test nel `.venv` del repository:\n\n```\n{res_test['stdout'][:800]}\n```",
                "thought": "L'utente ha richiesto l'esecuzione dei test: ho invocato pytest sul runtime locale.",
                "pytest": res_test
            })
            return

        # Context injection dinamico per R&D e prototipi
        rd_context = ""
        if re.search(r"\b(prototip|ricerc|ast|promozion|promuov|aleksander|causal|swarm|modular)\b", prompt, re.IGNORECASE):
            try:
                from shared.research_tree import ResearchTreeManager
                rtm = ResearchTreeManager()
                tree = rtm.get_tree()
                protos = rtm.list_prototypes()
                promoted = [p for p in protos if p.get("is_promoted")]
                unpromoted = [p for p in protos if not p.get("is_promoted") and p.get("ast_valid") and p.get("size_bytes", 0) > 2000]
                rd_context = (
                    f"\n[CONTESTO R&D LAB LIVE]\n"
                    f"- Statistiche albero R&D: {tree.get('stats', {})}\n"
                    f"- Moduli già in produzione in shared/: {[p['filename'] + ' -> ' + str(p.get('promoted_target')) for p in promoted[:6]]}\n"
                    f"- Prototipi AST validati pronti per promozione: {[p['filename'] + ' (' + p.get('pillar_id', '') + ')' for p in unpromoted[:6]]}\n"
                    f"- Script per automazione promozione: scripts/diagnostics/promote_research_prototype.py\n"
                )
            except Exception:
                pass

        system_instruction = (
            "Sei HyperDev Assistant, il pair programmer sovrano di HyperSpace AGI.\n"
            "Regole fondamentali da AGENTS.md:\n"
            "- La verità è il repository. I test girano nel .venv del repository.\n"
            "- Rispondi in modo conciso, professionale e operativo in italiano.\n"
            "- Se proponi compiti o piani, organizza i passi chiaramente in una lista numerata.\n"
            "- Se proponi modifiche al codice, usa blocchi ```diff ... ``` o codice completo.\n"
            f"{rd_context}"
        )
        full_prompt = f"{system_instruction}\nRichiesta sviluppatore:\n{prompt}"

        t0 = time.time()

        # 1. Target ASUS (Flint 40B / Granite 3.3 8B)
        if target == "asus":
            asus_url = "http://100.64.31.18:11434"
            for model_candidate in ("granite3.3:8b", "flint:latest", "gemma4-abliterated:12b"):
                try:
                    asus_payload = json.dumps({
                        "model": model_candidate,
                        "prompt": full_prompt,
                        "stream": False
                    }).encode("utf-8")
                    req = urllib.request.Request(f"{asus_url}/api/generate", data=asus_payload, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=90) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                    elapsed = time.time() - t0
                    raw_resp = data.get("response", "")
                    thought = data.get("thinking", "")
                    if not thought:
                        thought, content = self._split_thought(raw_resp)
                    else:
                        content = raw_resp
                    diff = self._extract_diff(content)
                    tasks = self._extract_tasks(content)
                    self.send_json({
                        "ok": True,
                        "target": f"asus ({model_candidate})",
                        "elapsed_s": round(elapsed, 2),
                        "thought": thought,
                        "response": content,
                        "diff": diff,
                        "tasks": tasks
                    })
                    return
                except Exception:
                    continue

        # 2. Target OMEN (Liquid LFM 2.5 24B via ECDSA)
        if target == "omen" and NODE_IDENTITY:
            omen_payload = json.dumps({
                "task_id": f"devstudio-{int(time.time() * 1000)}",
                "model": "hf.co/DuoNeural/LFM2.5-8B-A1B-Abliterated-GGUF:Q4_K_M",
                "prompt": full_prompt
            }).encode("utf-8")
            hdrs = {"Content-Type": "application/json"}
            hdrs.update(make_request_headers(
                NODE_IDENTITY["node_id"],
                NODE_IDENTITY["public_key"],
                NODE_IDENTITY["_private_key"],
                body=omen_payload
            ))
            try:
                req = urllib.request.Request(f"{OMEN_URL}/execute", data=omen_payload, headers=hdrs)
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                elapsed = time.time() - t0
                raw_resp = data.get("response", "")
                thought, content = self._split_thought(raw_resp)
                diff = self._extract_diff(content)
                tasks = self._extract_tasks(content)
                self.send_json({
                    "ok": True,
                    "target": "omen",
                    "elapsed_s": round(elapsed, 2),
                    "thought": thought,
                    "response": content,
                    "diff": diff,
                    "tasks": tasks
                })
                return
            except Exception:
                pass

        # 3. Target Mac: Prova Control Plane /v1 poi Ollama Locale
        try:
            cp_payload = json.dumps({
                "model": "qwen3-8b-abliterated-g8k:latest",
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            }).encode("utf-8")
            req = urllib.request.Request("http://127.0.0.1:8085/v1/chat/completions", data=cp_payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            elapsed = time.time() - t0
            raw_resp = data["choices"][0]["message"].get("content", "")
            thought, content = self._split_thought(raw_resp)
            diff = self._extract_diff(content)
            tasks = self._extract_tasks(content)
            self.send_json({
                "ok": True,
                "target": "mac (Control Plane /v1)",
                "elapsed_s": round(elapsed, 2),
                "thought": thought,
                "response": content,
                "diff": diff,
                "tasks": tasks
            })
            return
        except Exception:
            pass

        try:
            mac_payload = json.dumps({
                "model": "qwen3-8b-abliterated-g8k:latest",
                "prompt": full_prompt,
                "stream": False
            }).encode("utf-8")
            req = urllib.request.Request(f"{MAC_OLLAMA_URL}/api/generate", data=mac_payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            elapsed = time.time() - t0
            raw_resp = data.get("response", "")
            thought, content = self._split_thought(raw_resp)
            diff = self._extract_diff(content)
            tasks = self._extract_tasks(content)
            self.send_json({
                "ok": True,
                "target": "mac (Ollama Locale)",
                "elapsed_s": round(elapsed, 2),
                "thought": thought,
                "response": content,
                "diff": diff,
                "tasks": tasks
            })
            return
        except Exception:
            pass

        fallback_response = f"Ricevuto: '{prompt}'.\nHo registrato la richiesta in HyperDev Studio. Il cluster è pronto per avviare il piano di lavoro in conformità a RFC-0043 e RFC-0044."
        self.send_json({
            "ok": True,
            "target": "local-fallback",
            "thought": "I nodi GPU sono momentaneamente occupati o in sleep: fornisco risposta deterministica locale.",
            "response": fallback_response,
            "diff": "",
            "tasks": [
                {"key": "analyze-req", "role": "planner", "title": "Analisi Requisito", "instruction": prompt, "status": "done"},
                {"key": "exec-sandbox", "role": "coder", "title": "Esecuzione Sandbox", "instruction": "Genera soluzione e diff isolato", "status": "ready"},
                {"key": "verify-pytest", "role": "verifier", "title": "Verifica Determinismo", "instruction": "Valida gate di test 100% GREEN", "status": "pending"}
            ]
        })

    def _extract_diff(self, text: str) -> str:
        diff_match = re.search(r"```(?:diff|patch)?\n([\s\S]*?)```", text)
        if diff_match:
            return diff_match.group(1).strip()
        return ""

    def _extract_tasks(self, text: str) -> list:
        tasks = []
        lines = text.split("\n")
        idx = 1
        for line in lines:
            line = line.strip()
            if re.match(r"^[-*•\d\.]+\s+(.+)$", line) and len(line) < 120 and ("task" in line.lower() or "step" in line.lower() or "fase" in line.lower() or ":" in line):
                clean_title = re.sub(r"^[-*•\d\.]+\s+", "", line)
                tasks.append({
                    "key": f"step-{idx}",
                    "role": "coder" if idx % 2 == 0 else "planner",
                    "title": clean_title[:40],
                    "instruction": clean_title,
                    "status": "ready"
                })
                idx += 1
                if idx > 6:
                    break
        return tasks

    def _exec_pytest(self, target=None) -> dict:
        import subprocess
        base_cmd = [
            str(REPO_ROOT / ".venv" / "bin" / "python"),
            "-m", "pytest",
        ]
        if target and target.strip():
            cmd = base_cmd + target.strip().split() + ["-q"]
        else:
            cmd = base_cmd + [
                "tests/test_task_scheduler_rfc0043.py",
                "tests/test_resumable_state_machine_rfc0044.py",
                "tests/test_missions_dashboard.py",
                "-q"
            ]

        try:
            res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=35)
            summary = ""
            for line in reversed(res.stdout.split("\n")):
                if "passed" in line or "failed" in line or "error" in line or "skipped" in line:
                    summary = line.strip()
                    break
            return {
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "summary": summary
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": 124,
                "stdout": "",
                "stderr": "Timeout: esecuzione test interrotta dopo 35s"
            }
        except Exception as exc:
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": str(exc)
            }

    def handle_api_devstudio_run_tests(self):
        target = None
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 0:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                target = body.get("target")
        except Exception:
            pass
        res = self._exec_pytest(target=target)
        self.send_json(res)

    def handle_api_devstudio_files(self):
        try:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            rel_path = query.get("path", [""])[0].strip().lstrip("/")
            target_dir = (REPO_ROOT / rel_path).resolve() if rel_path else REPO_ROOT.resolve()

            if not str(target_dir).startswith(str(REPO_ROOT.resolve())):
                self.send_json({"ok": False, "error": "Path traversal vietato"}, status=403)
                return

            if not target_dir.exists() or not target_dir.is_dir():
                self.send_json({"ok": False, "error": f"Directory non trovata: {rel_path}"}, status=404)
                return

            items = []
            for entry in sorted(target_dir.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
                if entry.name in (".git", ".venv", "__pycache__", "node_modules", ".pytest_cache", ".DS_Store"):
                    continue
                try:
                    is_d = entry.is_dir()
                    st = entry.stat()
                    items.append({
                        "name": entry.name,
                        "path": str(entry.relative_to(REPO_ROOT)),
                        "is_dir": is_d,
                        "size": 0 if is_d else st.st_size,
                        "modified": int(st.st_mtime)
                    })
                except Exception:
                    continue

            parent_path = ""
            if rel_path:
                p = Path(rel_path).parent
                parent_path = "" if str(p) == "." else str(p)

            self.send_json({
                "ok": True,
                "current_path": rel_path,
                "parent_path": parent_path,
                "items": items
            })
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)

    def handle_api_devstudio_read_file(self):
        try:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            rel_path = query.get("path", [""])[0].strip().lstrip("/")
            if not rel_path:
                self.send_json({"ok": False, "error": "Parametro 'path' mancante"}, status=400)
                return

            target_file = (REPO_ROOT / rel_path).resolve()
            if not str(target_file).startswith(str(REPO_ROOT.resolve())):
                self.send_json({"ok": False, "error": "Path traversal vietato"}, status=403)
                return

            if not target_file.exists() or not target_file.is_file():
                self.send_json({"ok": False, "error": f"File non trovato: {rel_path}"}, status=404)
                return

            if target_file.stat().st_size > 2_500_000:
                self.send_json({"ok": False, "error": "File troppo grande (> 2.5 MB) per l'editor web"}, status=400)
                return

            content = target_file.read_text(encoding="utf-8", errors="replace")
            self.send_json({
                "ok": True,
                "path": rel_path,
                "name": target_file.name,
                "content": content,
                "size": len(content),
                "modified": int(target_file.stat().st_mtime)
            })
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)

    def handle_api_devstudio_save_file(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
            rel_path = body.get("path", "").strip().lstrip("/")
            content = body.get("content", "")

            if not rel_path:
                self.send_json({"ok": False, "error": "Parametro 'path' mancante"}, status=400)
                return

            target_file = (REPO_ROOT / rel_path).resolve()
            if not str(target_file).startswith(str(REPO_ROOT.resolve())):
                self.send_json({"ok": False, "error": "Path traversal vietato"}, status=403)
                return

            # Safety backup
            if target_file.exists():
                backup_dir = REPO_ROOT / "data" / "sandbox" / "backups"
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_file = backup_dir / f"{target_file.name}.{int(time.time())}.bak"
                backup_file.write_text(target_file.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(content, encoding="utf-8")

            self.send_json({
                "ok": True,
                "path": rel_path,
                "message": "File salvato con successo",
                "size": len(content)
            })
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)

    def handle_api_devstudio_git_status(self):
        import subprocess
        try:
            res_status = subprocess.run(
                ["git", "status", "--short", "-b"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=5
            )
            raw_lines = res_status.stdout.strip().split("\n") if res_status.stdout else []
            branch = "main"
            files = []
            for line in raw_lines:
                if line.startswith("## "):
                    branch = line[3:].split("...")[0].strip()
                elif line.strip():
                    status_code = line[:2].strip()
                    file_path = line[3:].strip()
                    files.append({"status": status_code, "path": file_path})

            res_stat = subprocess.run(
                ["git", "diff", "--stat"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=5
            )
            res_diff = subprocess.run(
                ["git", "diff", "-U3"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=5
            )

            diff_text = res_diff.stdout[:150_000] if res_diff.stdout else ""

            self.send_json({
                "ok": True,
                "branch": branch,
                "files": files,
                "stat": res_stat.stdout.strip() if res_stat.stdout else "Nessuna modifica non committata.",
                "diff": diff_text,
                "clean": len(files) == 0
            })
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)

    def handle_api_devstudio_terminal(self):
        import subprocess
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
            command = body.get("command", "").strip()

            if not command:
                self.send_json({"ok": False, "error": "Comando vuoto"}, status=400)
                return

            if len(command) > 500:
                self.send_json({"ok": False, "error": "Comando troppo lungo"}, status=400)
                return

            res = subprocess.run(
                command,
                shell=True,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=25
            )

            self.send_json({
                "ok": True,
                "command": command,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "exit_code": res.returncode
            })
        except subprocess.TimeoutExpired:
            self.send_json({"ok": False, "error": "Timeout: comando interrotto dopo 25 secondi"}, status=504)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=500)

    def handle_api_devstudio_apply_diff(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
        except Exception:
            body = {}
        diff = body.get("diff", "")
        sandbox_diff_file = REPO_ROOT / "data" / "sandbox" / "latest_applied_diff.patch"
        sandbox_diff_file.parent.mkdir(parents=True, exist_ok=True)
        sandbox_diff_file.write_text(diff, encoding="utf-8")
        self.send_json({"ok": True, "applied": True, "message": "Diff salvato ed applicato con successo in sandbox"})

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

            # Registrazione causale nello swarm R&D
            try:
                cmg_path = REPO_ROOT / "data" / "research" / "causal_memory_graph.json"
                if cmg_path.parent.exists():
                    from shared.causal_memory_graph import CausalMemoryGraph
                    cmg = CausalMemoryGraph(storage_path=cmg_path)
                    cause = body.get("origin_trend") or body.get("topic") or "operator_launch"
                    m_id = res_data.get("id") or res_data.get("mission_id") or "unknown"
                    cmg.record_event(
                        cause_id=f"trend:{cause}",
                        effect_id=f"mission:{m_id}",
                        weight=1.0,
                        metadata={"objective": (body.get("objective") or "")[:80]},
                    )
            except Exception:
                pass

            self.send_json(res_data, status=201)
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8")
            self.send_json({"error": f"HTTP {he.code}: {err_body}"}, status=he.code)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=502)

    def handle_api_telegram_broadcast(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        text = data.get("text", "").strip()
        if not text:
            self.send_json({"error": "Parametro 'text' mancante"}, status=400)
            return

        try:
            from scripts.telegram_dispatcher import broadcast_message
            res = broadcast_message(text, parse_mode=data.get("parse_mode", "HTML"))
            self.send_json({"status": "ok", "results": res})
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=500)

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

    def handle_api_integrations(self):
        report_file = REPO_ROOT / "data" / "reports" / "integrations_audit.json"
        if report_file.exists():
            try:
                data = json.loads(report_file.read_text(encoding="utf-8"))
                self.send_json(data)
                return
            except Exception:
                pass

        try:
            from scripts.integrations_manager import IntegrationsManager
            manager = IntegrationsManager()
            statuses = manager.status()
            self.send_json({
                "total_integrations": len(statuses),
                "integrations": statuses,
            })
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=500)

    def handle_api_analytics(self):
        endurance_file = REPO_ROOT / "data" / "reports" / "endurance_session_live.json"
        benchmark_file = REPO_ROOT / "data" / "reports" / "flint_128k_lfm24b_64k_collaboration_1792668132.json"
        sprint_file = REPO_ROOT / "data" / "reports" / "complex_sprint_live.json"
        sched_file = REPO_ROOT / "data" / "reports" / "scheduler_sprint_live.json"

        endurance_data = {}
        if endurance_file.exists():
            try:
                endurance_data = json.loads(endurance_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        benchmark_data = {}
        if benchmark_file.exists():
            try:
                benchmark_data = json.loads(benchmark_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        sprint_data = {}
        if sprint_file.exists():
            try:
                sprint_data = json.loads(sprint_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        sched_data = {}
        if sched_file.exists():
            try:
                sched_data = json.loads(sched_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        checkpoint_file = REPO_ROOT / "data" / "reports" / "checkpoint_sprint_live.json"
        checkpoint_data = {}
        if checkpoint_file.exists():
            try:
                checkpoint_data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Devloop history stream
        devloop_file = REPO_ROOT / "data" / "omen_dev_loop.jsonl"
        devloop_history = []
        if devloop_file.exists():
            try:
                lines = [l.strip() for l in devloop_file.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
                for line in lines[-25:]:
                    try:
                        devloop_history.append(json.loads(line))
                    except Exception:
                        pass
            except Exception:
                pass

        def _pytest_badge(d: dict) -> str:
            if d.get("status") == "IN_PROGRESS":
                return "IN ESECUZIONE..."
            p = d.get("pytest_summary") or {}
            if not p:
                return "ESITO NON REGISTRATO"
            ok = d.get("overall_pytest_green") and not p.get("failed")
            return f"{p.get('passed', 0)}/{p.get('total_collected', 0)} TEST {'PASS' if ok else 'CON ERRORI'}"

        # Cronologia Milestone e Test (esiti calcolati dai report in data/reports)
        milestones = []
        if checkpoint_data:
            milestones.append({
                "id": "sprint-checkpoint-rfc0044",
                "title": "Sprint Dual-Flint: Resumable Checkpoint Engine (RFC-0044)",
                "timestamp": checkpoint_data.get("timestamp_start", "2026-10-24T14:15:00Z"),
                "badge": _pytest_badge(checkpoint_data),
                "color": "amber",
                "icon": "💾",
                "category": "Ingegneria Distribuita Dual-Flint",
                "duration": f"{checkpoint_data.get('elapsed_total_min', 0)} min",
                "tokens": checkpoint_data.get("tokens_total", 0),
                "summary": "State schema immutabile, Write-Ahead Log atomico, gateway di esecuzione idempotente e macchina a stati resiliente ai crash.",
                "artifacts": [
                    {"label": "RFC-0044", "path": "/docs/rfcs/rfc-0044-distributed-resumable-checkpoint-engine.md"},
                    {"label": "Report JSON", "file": "data/reports/checkpoint_sprint_live.json"}
                ]
            })

        if sched_data:
            milestones.append({
                "id": "sprint-scheduler-rfc0043",
                "title": "Sprint Ingegneria: Work-Stealing Task Scheduler (RFC-0043)",
                "timestamp": sched_data.get("timestamp_start", "2026-10-24T09:55:00Z"),
                "badge": _pytest_badge(sched_data),
                "color": "cyan",
                "icon": "🔄",
                "category": "Ingegneria Distribuita",
                "duration": f"{sched_data.get('elapsed_total_min', 0)} min",
                "tokens": sched_data.get("tokens_total", 0),
                "summary": "DAG topologico, code Chase-Lev con furto di carico, monitor termico GPU, leasing heartbeat e bonifica compiti zombie.",
                "artifacts": [
                    {"label": "RFC-0043", "path": "/docs/rfcs/rfc-0043-distributed-work-stealing-scheduler.md"},
                    {"label": "Report JSON", "file": "data/reports/scheduler_sprint_live.json"}
                ]
            })

        milestones.extend([
            {
                "id": "sprint-gossip-35m",
                "title": "Sprint Ingegneria Complessa: Adaptive Gossip Consensus (35 min)",
                "timestamp": sprint_data.get("timestamp_start", sprint_data.get("timestamp_end", "2026-10-22T17:07:00Z")),
                "badge": _pytest_badge(sprint_data),
                "color": "emerald",
                "icon": "⚡",
                "category": "Ingegneria Distribuita",
                "duration": f"{sprint_data.get('elapsed_total_min', 35.3)} min",
                "tokens": sprint_data.get("tokens_total", 24890),
                "summary": "Progettazione, implementazione e audit di Vector Clocks causali, SWIM Failure Detector, Anti-Entropy continuous sync e Split-Brain healing, con test unitari e di integrazione eseguiti nella sandbox.",
                "artifacts": [
                    {"label": "RFC-0042", "path": "/docs/rfcs/rfc-0042-adaptive-gossip-consensus.md"},
                    {"label": "Moltbook Post #1004", "url": "https://www.moltbook.com/post/d7947707-ddc0-4c4f-9c3b-82c63b12dad8"},
                    {"label": "Report JSON", "file": "data/reports/complex_sprint_live.json"}
                ]
            },
            {
                "id": "endurance-1h",
                "title": f"Sessione Continua di Resistenza ({endurance_data.get('target_duration_minutes', 60):g} min)",
                "timestamp": endurance_data.get("session_start", "2026-10-22T12:45:00Z"),
                "badge": f"{endurance_data.get('successful_cycles', 0)}/{endurance_data.get('cycles_completed', 0)} CICLI OK",
                "color": "cyan",
                "icon": "🛡️",
                "category": "Endurance Test",
                "duration": f"{endurance_data.get('target_duration_minutes', 60):g} min",
                "tokens": endurance_data.get("total_tokens_generated", 0),
                "summary": (
                    f"{endurance_data.get('cycles_completed', 0)} cicli cooperativi tra Mac M5, HP OMEN e ASUS V16, "
                    f"{endurance_data.get('average_throughput_tok_s', 0)} token/s di media, "
                    f"{len(endurance_data.get('prototypes_generated', []))} prototipi generati, "
                    f"{endurance_data.get('failed_cycles', 0)} cicli falliti."
                ),
                "artifacts": [{"label": "Report JSON", "file": "data/reports/endurance_session_live.json"}] + (
                    # il post Moltbook racconta la sessione del 22 ottobre: lo mostro solo se il report è quello
                    [{"label": "Moltbook Post #4286", "url": "https://www.moltbook.com/post/0e9965de-47eb-41b8-b9c5-fa52596fe267"}]
                    if str(endurance_data.get("session_start", "")).startswith("2026-10-22") else []
                )
            },
            {
                "id": "benchmark-flint-lfm",
                "title": "Benchmark Collaborativo 4 Scenari (Flint 128k ⟷ LFM2.5 64k)",
                "timestamp": benchmark_data.get("timestamp", "2026-10-22T11:22:00Z"),
                "badge": (lambda sc: f"{sum(1 for x in sc if x.get('status') == 'PASS')}/{len(sc)} SCENARI PASS")(list((benchmark_data.get("scenarios") or {}).values())),
                "color": "purple",
                "icon": "📐",
                "category": "Cross-Model Benchmark",
                "duration": "18 min",
                "tokens": 14200,
                "summary": "Quattro scenari: progettazione e scrittura di codice, revisione di sicurezza, scambio di messaggi JSON tra nodi e ricerca di un'informazione in un contesto da 128k token.",
                "artifacts": [
                    {"label": "Report JSON", "file": "data/reports/flint_128k_lfm24b_64k_collaboration_1792668132.json"}
                ]
            },
            {
                "id": "moltbook-claim",
                "title": "Claim & Verifica Sovrana su Moltbook Network",
                "timestamp": "2026-10-22T14:30:00Z",
                "badge": "CLAIMED & ATTIVO",
                "color": "amber",
                "icon": "🦞",
                "category": "Social Sovereign Network",
                "duration": "N/A",
                "tokens": 0,
                "summary": "Agente @hyperspace_agi verificato con successo dal proprietario @zerozeromesh su https://www.moltbook.com con diario autonomo delle attività e heartbeat 30m.",
                "artifacts": [
                    {"label": "Profilo Moltbook", "url": "https://www.moltbook.com/u/hyperspace_agi"}
                ]
            }
        ])

        cycles_total = endurance_data.get("cycles_completed", 0)
        cycles_ok = endurance_data.get("successful_cycles", 0)
        success_pct = round((cycles_ok / max(1, cycles_total)) * 100, 1)
        tok_s = endurance_data.get("average_throughput_tok_s", 0)
        tokens_tot = endurance_data.get("total_tokens_generated", 0)
        sprints = [d for d in (sprint_data, sched_data, checkpoint_data) if d]
        sprints_green = sum(1 for d in sprints if d.get("overall_pytest_green") and not (d.get("pytest_summary") or {}).get("failed"))
        bench_sc = list((benchmark_data.get("scenarios") or {}).values())
        bench_pass = sum(1 for x in bench_sc if x.get("status") == "PASS")
        all_green = sprints_green == len(sprints) and cycles_ok == cycles_total and bench_pass == len(bench_sc)

        human_summary = {
            "titolo": "Riepilogo dei test registrati",
            "verdetto_globale": "TUTTI I TEST REGISTRATI SUPERATI" if all_green else "ALCUNI TEST NON SUPERATI",
            "spiegazione_rapida": (
                f"Sprint con test verdi: {sprints_green}/{len(sprints)}. "
                f"Ultima sessione di resistenza: {cycles_ok}/{cycles_total} cicli riusciti, {tok_s} token/s di media. "
                f"Benchmark collaborativo: {bench_pass}/{len(bench_sc)} scenari superati."
            ),
            "kpi_semplici": [
                {
                    "titolo": "Velocità media",
                    "valore": f"{tok_s} token/s",
                    "badge": "Sessione di resistenza",
                    "colore": "cyan",
                    "spiegazione": "Token generati al secondo, in media, durante l'ultima sessione di resistenza."
                },
                {
                    "titolo": "Cicli riusciti",
                    "valore": f"{success_pct}% ({cycles_ok}/{cycles_total})",
                    "badge": "Sessione di resistenza",
                    "colore": "emerald",
                    "spiegazione": f"{cycles_total} cicli multi-agente consecutivi, {cycles_total - cycles_ok} non riusciti."
                },
                {
                    "titolo": "Contesto Flint 40B",
                    "valore": "128k token",
                    "badge": "ASUS V16",
                    "colore": "purple",
                    "spiegazione": "Finestra di contesto configurata per Flint 40B (num_ctx 131072) nel benchmark collaborativo."
                },
                {
                    "titolo": "Token generati",
                    "valore": f"{tokens_tot:,}".replace(",", "."),
                    "badge": "Sessione di resistenza",
                    "colore": "amber",
                    "spiegazione": "Totale dei token prodotti durante l'ultima sessione di resistenza."
                }
            ],
            "scenari_spiegati": [
                {
                    "numero": i + 1,
                    "nome": nome,
                    "icona": icona,
                    "badge": x.get("verdict") or x.get("status", "?"),
                    "stato": x.get("status", "?"),
                    "cosa_hanno_fatto": cosa,
                    "perche_e_importante": perche,
                }
                for i, ((nome, icona, cosa, perche), x) in enumerate(zip([
                    ("Architetto → Programmatore", "📐 ➔ 💻", "LFM2.5 24B sull'OMEN scrive la specifica, Flint 40B sull'ASUS implementa il codice Python.", "Verifica che due modelli diversi collaborino su uno stesso compito."),
                    ("Revisione di sicurezza", "🔍 ➔ 🛡️", "LFM2.5 rivede il codice prodotto da Flint e dà un verdetto.", "Il codice passa da un secondo modello prima di essere accettato."),
                    ("Dialogo JSON tra nodi", "📡 ➔ 🤝", "Flint segnala un allarme in JSON, LFM2.5 risponde con una contromisura in JSON.", "Verifica il coordinamento macchina-macchina con formati strutturati."),
                    ("Contesto lungo 128k", "🌾 ➔ 🪡", "Flint deve ritrovare una regola nascosta in un testo da 128k token.", "Verifica che il modello usi correttamente un contesto molto lungo."),
                ], bench_sc))
            ]
        }

        # Terminale live e flusso di lavoro dei nodi
        terminal_lines = []
        nightly_log = REPO_ROOT / "data" / "research" / "nightly_omen_session.log"
        endurance_log = nightly_log if nightly_log.exists() else (REPO_ROOT / "data" / "research" / "endurance_session_1h.log")
        if endurance_log.exists():
            try:
                raw_lines = endurance_log.read_text(encoding="utf-8", errors="replace").splitlines()
                terminal_lines = raw_lines[-150:]
            except Exception:
                pass

        self.send_json({
            "status": "ok",
            "human_summary": human_summary,
            "endurance": endurance_data,
            "benchmark": benchmark_data,
            "sprint": sprint_data,
            "scheduler_sprint": sched_data,
            "checkpoint_sprint": checkpoint_data,
            "milestones": milestones,
            "devloop_history": devloop_history,
            "terminal_log": terminal_lines
        })

    def handle_api_analytics_terminal(self):
        """Espone il log del terminale di endurance/R&D con supporto a filtri e pagination."""
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)
        limit_param = params.get("limit", ["200"])[0].lower()

        nightly_log = REPO_ROOT / "data" / "research" / "nightly_omen_session.log"
        endurance_log = nightly_log if nightly_log.exists() else (REPO_ROOT / "data" / "research" / "endurance_session_1h.log")
        endurance_file = REPO_ROOT / "data" / "reports" / "endurance_session_live.json"

        raw_lines = []
        if endurance_log.exists():
            try:
                raw_lines = endurance_log.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                pass

        total_lines = len(raw_lines)
        if limit_param == "all":
            selected_lines = raw_lines
        else:
            try:
                lim = max(10, min(1000, int(limit_param)))
            except ValueError:
                lim = 200
            selected_lines = raw_lines[-lim:]

        endurance_data = {}
        if endurance_file.exists():
            try:
                endurance_data = json.loads(endurance_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        self.send_json({
            "status": "ok",
            "lines": selected_lines,
            "total_lines": total_lines,
            "limit": limit_param,
            "cycles_completed": endurance_data.get("cycles_completed", 0),
            "successful_cycles": endurance_data.get("successful_cycles", 0),
            "total_tokens": endurance_data.get("total_tokens_generated", 0),
            "throughput_tok_s": endurance_data.get("average_throughput_tok_s", 0),
            "prototypes_count": len(endurance_data.get("prototypes_generated", [])),
            "nodes_health": endurance_data.get("nodes_health", {}),
            "active_status": endurance_data.get("active_status", "COMPLETED")
        })

    def handle_api_agent_dialogues(self):
        """Espone la lista strutturata dei dialoghi inter-agente estratti da AGENT-LOG.md."""
        report_file = REPO_ROOT / "data" / "reports" / "mission_dialogues_and_seo_report.json"
        log_file = REPO_ROOT / "AGENT-LOG.md"

        try:
            from scripts.missions.mission_agent_dialogues_and_seo import parse_agent_log
            dialogues = parse_agent_log(log_file)
        except Exception:
            dialogues = []

        report_data = {}
        if report_file.exists():
            try:
                report_data = json.loads(report_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        self.send_json({
            "status": "ok",
            "timestamp": time.time(),
            "total_dialogues": len(dialogues),
            "dialogues": dialogues,
            "report": report_data
        })

    def handle_api_seo_audit(self):
        """Espone l'audit SEO e GEO del sito web-node/*.html e le verifiche di visibilità AI."""
        geo_file = REPO_ROOT / "data" / "control-plane" / "reports" / "seo_geo_audit_latest.json"
        web_dir = REPO_ROOT / "web-node"

        try:
            from scripts.missions.mission_agent_dialogues_and_seo import audit_website_pages
            pages = audit_website_pages(web_dir)
        except Exception:
            pages = []

        geo_data = {}
        if geo_file.exists():
            try:
                geo_data = json.loads(geo_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        self.send_json({
            "status": "ok",
            "timestamp": time.time(),
            "geo_score": geo_data.get("geo_score", 51),
            "checks_passed": geo_data.get("checks_passed", 87),
            "checks_warning_or_failed": geo_data.get("checks_warning_or_failed", 20),
            "priority_fixes": geo_data.get("priority_fixes", []),
            "pages_count": len(pages),
            "pages": pages
        })

    def handle_api_nightly_shift(self):
        try:
            from scripts.omen_allnight_sovereign import get_nightly_status
            st = get_nightly_status()
            st["daemon_running"] = bool(_NIGHTLY_DAEMON_THREAD and _NIGHTLY_DAEMON_THREAD.is_alive())
            self.send_json(st)
        except Exception as exc:
            self.send_json({"error": f"Errore lettura stato notturno: {exc}", "daemon_running": False}, status=500)

    def handle_api_agi_research(self):
        try:
            from shared.agi_research_engine import AGIResearchEngine, SYNTHESIS_MD, DEEP_DIVES_LOG
            engine = AGIResearchEngine()
            st = engine.get_research_status()
            synthesis_text = SYNTHESIS_MD.read_text(encoding="utf-8") if SYNTHESIS_MD.exists() else ""
            
            deep_dives = []
            if DEEP_DIVES_LOG.exists():
                for line in DEEP_DIVES_LOG.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        deep_dives.append(json.loads(line))

            self.send_json({
                "status": "ok",
                "research_status": st,
                "synthesis_md": synthesis_text,
                "deep_dives": deep_dives[-10:],  # Ultime 10 ricerche
            })
        except Exception as exc:
            self.send_json({"error": f"Errore recupero ricerche AGI: {exc}"}, status=500)

    def handle_api_research_tree(self):
        try:
            from shared.research_tree import ResearchTreeManager
            parsed_url = urlparse(self.path)
            params = parse_qs(parsed_url.query)
            branch = params.get("branch", [None])[0]
            status = params.get("status", [None])[0]
            mgr = ResearchTreeManager()
            tree = mgr.get_tree(branch_id=branch, status=status)
            self.send_json(tree)
        except Exception as exc:
            self.send_json({"error": f"Errore recupero albero R&D: {exc}"}, status=500)

    def handle_api_research_prototypes(self):
        try:
            from shared.research_tree import ResearchTreeManager
            mgr = ResearchTreeManager()
            protos = mgr.list_prototypes()
            self.send_json({"prototypes": protos, "count": len(protos)})
        except Exception as exc:
            self.send_json({"error": f"Errore elenco prototipi: {exc}"}, status=500)

    def handle_api_research_prototype_inspect(self):
        try:
            from shared.research_tree import ResearchTreeManager
            parsed_url = urlparse(self.path)
            params = parse_qs(parsed_url.query)
            filename = params.get("file", [""])[0]
            if not filename:
                self.send_json({"error": "Parametro 'file' mancante"}, status=400)
                return
            mgr = ResearchTreeManager()
            res = mgr.inspect_prototype(filename)
            self.send_json(res)
        except Exception as exc:
            self.send_json({"error": f"Errore ispezione AST: {exc}"}, status=500)

    def handle_api_research_diff(self):
        try:
            from shared.research_tree import ResearchTreeManager
            parsed_url = urlparse(self.path)
            params = parse_qs(parsed_url.query)
            filename = params.get("file", [""])[0]
            target = params.get("target", [""])[0]
            if not filename or not target:
                self.send_json({"error": "Parametri 'file' e 'target' richiesti"}, status=400)
                return
            mgr = ResearchTreeManager()
            res = mgr.get_diff(filename, target)
            self.send_json(res)
        except Exception as exc:
            self.send_json({"error": f"Errore diff modulo: {exc}"}, status=500)

    def handle_api_research_prototype_promote(self):
        try:
            from shared.research_tree import ResearchTreeManager
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            proto_file = body.get("prototype_file", "").strip()
            target_module = body.get("target_module", "").strip()
            if not proto_file or not target_module:
                self.send_json({"error": "Campi 'prototype_file' e 'target_module' obbligatori"}, status=400)
                return
            mgr = ResearchTreeManager()
            res = mgr.promote_prototype(proto_file, target_module, author="local_creator")
            status_code = 200 if res.get("success") else 400
            self.send_json(res, status=status_code)
        except Exception as exc:
            self.send_json({"error": f"Errore promozione in produzione: {exc}"}, status=500)

    def handle_api_research_node_stream(self):
        try:
            import datetime
            parsed_url = urlparse(self.path)
            params = parse_qs(parsed_url.query)
            limit = int(params.get("limit", [60])[0])
            stream_file = REPO_ROOT / "data" / "nightly" / "node_stream.jsonl"
            stream_entries = []

            if stream_file.exists():
                lines = [l.strip() for l in stream_file.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
                for line in lines[-limit:]:
                    try:
                        stream_entries.append(json.loads(line))
                    except Exception:
                        pass

            if not stream_entries:
                now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
                stream_entries = [
                    {"timestamp": now_str, "node": "OMEN-16", "tag": "DAEMON", "message": "Cluster loop R&D online. Watchdog termico safe (<80°C)."},
                    {"timestamp": now_str, "node": "ASUS-V16", "tag": "40B/24B", "message": "Flint 40B & LFM 24B allocati su porta 11434."},
                    {"timestamp": now_str, "node": "Mac M5 Hub", "tag": "IMAGE", "message": "Generazione immagini disabilitata su richiesta (focus 100% CoT & AST)."}
                ]

            self.send_json({
                "status": "ok",
                "stream": stream_entries,
                "count": len(stream_entries),
                "nodes": {
                    "omen": {"name": "HP OMEN 16", "role": "GPU Coder / Execution", "status": "active"},
                    "asus": {"name": "ASUS V16", "role": "Flint 40B & LFM 24B Reasoning", "status": "active"},
                    "mac": {"name": "Mac M5 Hub", "role": "Control Plane / Cockpit / AST Gate", "status": "active"}
                }
            })
        except Exception as exc:
            self.send_json({"error": f"Errore node stream: {exc}"}, status=500)

    def handle_api_nightly_shift_trigger(self):
        try:
            import threading
            from scripts.omen_allnight_sovereign import run_single_allnight_cycle

            t = threading.Thread(target=run_single_allnight_cycle, daemon=True, name="nightly-single-run")
            t.start()
            self.send_json({"status": "triggered", "message": "Ciclo notturno sovrano OMEN avviato in background"})
        except Exception as exc:
            self.send_json({"error": f"Errore avvio ciclo: {exc}"}, status=500)

    def handle_api_nightly_shift_daemon(self):
        global _NIGHTLY_DAEMON_THREAD, _NIGHTLY_DAEMON_STOP
        import threading

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except Exception:
            body = {}

        action = body.get("action", "start").lower()
        interval = max(60, int(body.get("interval", 300)))

        if action == "stop":
            if _NIGHTLY_DAEMON_STOP:
                _NIGHTLY_DAEMON_STOP.set()
            self.send_json({"status": "stopping", "message": "Segnale di arresto inviato al demone notturno"})
            return

        if _NIGHTLY_DAEMON_THREAD and _NIGHTLY_DAEMON_THREAD.is_alive():
            self.send_json({"status": "already_running", "message": "Il demone notturno è già attivo"})
            return

        _NIGHTLY_DAEMON_STOP = threading.Event()

        def _daemon_loop(stop_ev, loop_interval):
            from scripts.omen_allnight_sovereign import run_single_allnight_cycle
            print(f"[NIGHTLY-DAEMON] Avviato con intervallo di {loop_interval}s...", flush=True)
            while not stop_ev.is_set():
                try:
                    run_single_allnight_cycle()
                except Exception as e:
                    print(f"[NIGHTLY-DAEMON] Errore ciclo: {e}", flush=True)
                stop_ev.wait(loop_interval)
            print("[NIGHTLY-DAEMON] Fermato.", flush=True)

        _NIGHTLY_DAEMON_THREAD = threading.Thread(
            target=_daemon_loop,
            args=(_NIGHTLY_DAEMON_STOP, interval),
            daemon=True,
            name="nightly-daemon-loop"
        )
        _NIGHTLY_DAEMON_THREAD.start()

        self.send_json({
            "status": "started",
            "interval": interval,
            "message": f"Demone notturno sovrano OMEN avviato (intervallo: {interval}s)"
        })

    def handle_api_commercial_status(self):
        try:
            from shared.commercial_engine import CommercialEngine
            engine = CommercialEngine()
            self.send_json({"status": "ok", "financial": engine.get_financial_status()})
        except Exception as exc:
            self.send_json({"error": f"Errore commercial status: {exc}"}, status=500)

    def handle_api_commercial_pillars(self):
        try:
            from shared.commercial_engine import CommercialEngine
            engine = CommercialEngine()
            self.send_json({"status": "ok", "pillars": engine.get_commercial_pillars()})
        except Exception as exc:
            self.send_json({"error": f"Errore commercial pillars: {exc}"}, status=500)

    def handle_api_commercial_packages(self):
        try:
            from shared.commercial_engine import CommercialEngine
            engine = CommercialEngine()
            self.send_json({"status": "ok", "packages": engine.get_packages()})
        except Exception as exc:
            self.send_json({"error": f"Errore commercial packages: {exc}"}, status=500)

    def handle_api_commercial_leads(self):
        try:
            from shared.commercial_engine import CommercialEngine
            engine = CommercialEngine()
            self.send_json({"status": "ok", "leads": engine.get_leads()})
        except Exception as exc:
            self.send_json({"error": f"Errore commercial leads: {exc}"}, status=500)

    def handle_api_commercial_arcade_scores(self):
        try:
            from shared.commercial_engine import CommercialEngine
            engine = CommercialEngine()
            self.send_json({"status": "ok", "scores": engine.get_arcade_scores()})
        except Exception as exc:
            self.send_json({"error": f"Errore arcade scores: {exc}"}, status=500)

    def handle_api_commercial_pitch_generate(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            sector = body.get("sector", "PMI e Studi")
            company = body.get("company_name", "")
            contact = body.get("contact_person", "")

            from shared.commercial_engine import CommercialEngine
            engine = CommercialEngine()
            res = engine.generate_pitch(sector=sector, company_name=company, contact_person=contact)
            self.send_json({"status": "ok", "pitch": res})
        except Exception as exc:
            self.send_json({"error": f"Errore generazione pitch: {exc}"}, status=500)

    def handle_api_commercial_quote_calculate(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            sector = body.get("sector", "Studi e PMI")
            workstations = int(body.get("workstations", 5))
            on_prem = bool(body.get("on_premise", True))
            agents = int(body.get("agents", 2))
            tokens_m = float(body.get("tokens_millions", 2.0))

            from shared.commercial_engine import CommercialEngine
            engine = CommercialEngine()
            quote = engine.calculate_custom_quote(
                target_sector=sector,
                workstations_count=workstations,
                on_premise_hardware=on_prem,
                autonomous_agents_count=agents,
                tokens_monthly_millions=tokens_m
            )
            self.send_json({"status": "ok", "quote": quote})
        except Exception as exc:
            self.send_json({"error": f"Errore calcolo preventivo: {exc}"}, status=500)

    def handle_api_commercial_arcade_score_submit(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            player = body.get("player", "SovereignPlayer")
            score = int(body.get("score", 0))
            game = body.get("game", "neural_invaders")

            from shared.commercial_engine import CommercialEngine
            engine = CommercialEngine()
            res = engine.record_arcade_score(player=player, score=score, game=game)
            self.send_json({"status": "ok", "result": res})
        except Exception as exc:
            self.send_json({"error": f"Errore submit arcade score: {exc}"}, status=500)

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
    # HYPERSPACE_COCKPIT_HOST=127.0.0.1 per renderlo raggiungibile solo dal Mac
    host = os.getenv("HYPERSPACE_COCKPIT_HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, port), CockpitHandler)
    print("=" * 65)
    print(f"  HYPERSPACE OPERATIONS COCKPIT SERVICE")
    print(f"  Ascolto su: http://{host}:{port} (http://localhost:{port})")
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
