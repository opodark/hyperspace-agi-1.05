# SPDX-License-Identifier: Apache-2.0
"""
scripts/bonsai_server_service.py
Service manager for Prism ML Ternary Bonsai 2 27B (Abliterated) using CUDA llama-server.
Supports: start, stop, status
"""
import os
import sys
import time
import subprocess
import urllib.request
import json

BIN_DIR = r"C:\HyperSpace\bin\bonsai"
SERVER_EXE = os.path.join(BIN_DIR, "llama-server.exe")
MODEL_PATH = r"C:\HyperSpace\models\Ternary-Bonsai-2-27B-Uncensored-Heretic-PQ2_0.gguf"
LOG_DIR = r"C:\HyperSpace\logs"
LOG_FILE = os.path.join(LOG_DIR, "bonsai-server.log")
PID_FILE = os.path.join(LOG_DIR, "bonsai-server.pid")
PORT = 8082
HOST = "127.0.0.1"

def check_health(timeout=2):
    try:
        url = f"http://{HOST}:{PORT}/health"
        req = urllib.request.urlopen(url, timeout=timeout)
        data = json.loads(req.read().decode())
        return data.get("status") == "ok" or req.getcode() == 200
    except Exception:
        return False

def stop():
    if os.path.isfile(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
            os.kill(pid, 9)
            print(f"[OK] Killed Bonsai 2 server PID {pid}")
        except Exception as e:
            print(f"[INFO] PID {pid} was not running: {e}")
        try:
            os.remove(PID_FILE)
        except Exception:
            pass

    # Also kill any leftover llama-server.exe on port 8082
    subprocess.run(["powershell", "-Command", "Get-Process -Name 'llama-server' -ErrorAction SilentlyContinue | Stop-Process -Force"], capture_output=True)
    time.sleep(1)

def start():
    if not os.path.isfile(SERVER_EXE):
        print(f"[ERR] Server executable not found at {SERVER_EXE}")
        return False
    if not os.path.isfile(MODEL_PATH):
        print(f"[ERR] Model GGUF not found at {MODEL_PATH}")
        return False

    if check_health():
        print(f"[OK] Bonsai 2 server already running and healthy at http://{HOST}:{PORT}")
        return True

    os.makedirs(LOG_DIR, exist_ok=True)
    stop() # Ensure no zombie on port 8082

    env = os.environ.copy()
    env["PATH"] = f"{BIN_DIR};" + env.get("PATH", "")

    cmd = [
        SERVER_EXE,
        "-m", MODEL_PATH,
        "--host", HOST,
        "--port", str(PORT),
        "-ngl", "99",
        "--ctx-size", "8192",
        "--alias", "bonsai-2-abliterated",
        "--temp", "0.7",
        "--top-p", "0.95",
        "--jinja"
    ]

    log_fd = open(LOG_FILE, "w", encoding="utf-8")
    flags = (
        subprocess.DETACHED_PROCESS
        | subprocess.CREATE_NEW_PROCESS_GROUP
        | subprocess.CREATE_NO_WINDOW
    )

    print(f"Launching detached Bonsai 2 daemon on {HOST}:{PORT} (logs -> {LOG_FILE})...")
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=log_fd,
        stderr=subprocess.STDOUT,
        creationflags=flags
    )

    with open(PID_FILE, "w") as f:
        f.write(str(proc.pid))

    print(f"Bonsai 2 server process started with PID {proc.pid}. Waiting for VRAM load...")
    start_time = time.time()
    while time.time() - start_time < 60:
        if check_health(timeout=1):
            print(f"[SUCCESS] Bonsai 2 server is live and healthy at http://{HOST}:{PORT}")
            return True
        time.sleep(2)

    print("[WARN] Timed out waiting for Bonsai 2 server health check. Check logs at:", LOG_FILE)
    return False

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "start"
    if action == "stop":
        stop()
    elif action == "status":
        print(f"Healthy: {check_health()}")
    else:
        success = start()
        sys.exit(0 if success else 1)
