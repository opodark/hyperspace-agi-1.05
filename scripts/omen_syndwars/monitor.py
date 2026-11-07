#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Monitor delle prove di Syndicate Wars su OMEN: mosaico video dei display virtuali e avanzamento dei lavori.

Gira dentro la distro WSL dove gira `par_check.sh`. Ascolta solo su 127.0.0.1: il video mostra il gioco originale
(materiale EA/Bullfrog) e non deve uscire dalla macchina. Dal Mac:
    ssh -L 8099:127.0.0.1:8099 opoda@100.104.238.125     poi    http://127.0.0.1:8099/

Slot del mosaico, come in par_check.sh: missioni :30-:35, partita lunga :39, chiamate dirette :40-:43.
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("MONITOR_PORT", "8099"))
OUT = "/tmp/monitor"
SLOTS = [(30 + i, f"missione {i}") for i in range(6)] + [(39, "partita lunga")] + [(40 + k, f"chiamate {k}") for k in range(4)] + [(None, "")]
TILE = (480, 360)
COLUMNS = 4


def live_displays() -> list:
    """Display con un Xvfb in esecuzione (i socket in /tmp/.X11-unix non si vedono sempre sotto WSL)."""
    running = subprocess.run(["pgrep", "-a", "Xvfb"], capture_output=True, text=True).stdout
    found = {int(n) for n in re.findall(r"Xvfb :(\d+)", running)}
    return [d for d, _ in SLOTS if d in found]


def ffmpeg_command(displays: list) -> list:
    """Un solo processo: tutti i display presenti, segnaposto neri per gli altri, mosaico 4x3 in una JPEG aggiornata ogni secondo."""
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    filters = []
    for index, (display, _name) in enumerate(SLOTS):
        if display in displays:
            command += ["-f", "x11grab", "-framerate", "1", "-video_size", "1024x768", "-i", f":{display}"]
        else:
            command += ["-f", "lavfi", "-i", "color=c=0x101010:s=1024x768:r=1"]
        filters.append(f"[{index}:v]scale={TILE[0]}:{TILE[1]}[v{index}]")
    layout = "|".join(f"{(i % COLUMNS) * TILE[0]}_{(i // COLUMNS) * TILE[1]}" for i in range(len(SLOTS)))
    inputs = "".join(f"[v{i}]" for i in range(len(SLOTS)))
    filters.append(f"{inputs}xstack=inputs={len(SLOTS)}:layout={layout}[m]")
    command += ["-filter_complex", ";".join(filters), "-map", "[m]", "-update", "1", "-q:v", "5", f"{OUT}/mosaic.jpg"]
    return command


def capture_loop() -> None:
    os.makedirs(OUT, exist_ok=True)
    process = None
    current: list = []
    while True:
        displays = live_displays()
        if displays != current or (process and process.poll() is not None):
            if process and process.poll() is None:
                process.terminate()
                process.wait()
            current = displays
            process = subprocess.Popen(ffmpeg_command(displays)) if displays else None
        time.sleep(2)


def last_turn(pattern: str) -> int:
    turns = [int(m.group(1)) for f in glob.glob(pattern) if (m := re.search(r"_(\d+)_t\.bin$", f))]
    return max(turns) if turns else 0


def status() -> dict:
    runs = sorted(glob.glob("/tmp/par_*"), key=os.path.getmtime)
    tag = os.path.basename(runs[-1])[len("par_"):] if runs else ""
    jobs = []
    if tag:
        for f in sorted(glob.glob(f"/tmp/par_{tag}/*.done")):
            jobs.append({"lavoro": os.path.basename(f)[:-5], "esito": open(f).read().strip()})
        lines = {k: sum(1 for _ in open(p)) for p in glob.glob(f"/tmp/dc_{tag}_[0-9]*.txt") if (k := os.path.basename(p))}
    else:
        lines = {}
    games = subprocess.run(["pgrep", "-c", r"^game\."], capture_output=True, text=True).stdout.strip()
    return {"prova": tag, "giochi_attivi": int(games or 0), "display": live_displays(), "chiamate_dirette_righe": lines,
            "turno_partita_lunga": last_turn(f"/tmp/L_{tag}_*_t.bin") if tag else 0,
            "turni_missioni": {m: last_turn(f"/tmp/su_{tag}_{m}_*_t.bin") for m in ("0_1", "0_3", "0_5", "0_8", "0_20", "1_10")} if tag else {},
            "finiti": jobs, "ora": time.strftime("%H:%M:%S")}


PAGE = """<!doctype html><meta charset=utf-8><title>Prove Syndicate Wars</title>
<style>body{background:#111;color:#ddd;font:14px system-ui;margin:12px}img{width:100%;max-width:1920px;display:block}
pre{background:#1b1b1b;padding:8px;overflow:auto}</style>
<h3>Prove su OMEN</h3><img id=m src=mosaic.jpg><pre id=s>...</pre>
<p>Slot: righe dall'alto, missioni 0-5 e partita lunga; poi chiamate dirette 0-3; l'ultimo riquadro e' vuoto.</p>
<script>
setInterval(()=>{document.getElementById('m').src='mosaic.jpg?'+Date.now()},1000);
setInterval(()=>fetch('status').then(r=>r.json()).then(j=>{document.getElementById('s').textContent=JSON.stringify(j,null,1)}),2000);
</script>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args) -> None:
        pass

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        if path == "/":
            body, kind = PAGE.encode(), "text/html; charset=utf-8"
        elif path == "/status":
            body, kind = json.dumps(status()).encode(), "application/json"
        elif path == "/mosaic.jpg" and os.path.exists(f"{OUT}/mosaic.jpg"):
            body, kind = open(f"{OUT}/mosaic.jpg", "rb").read(), "image/jpeg"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    threading.Thread(target=capture_loop, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
