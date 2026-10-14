# SPDX-License-Identifier: Apache-2.0
# shared/node_telemetry.py
# HyperSpace AGI — Node Health & Codebase Telemetry Collector
#
# Raccoglie telemetria dettagliata, affidabile e a basso sovraccarico da ogni nodo mesh:
#   1. Codebase: commit hash (HEAD), branch, data commit, dirty status (modifiche non committate).
#   2. Graphify: freschezza e metriche del Knowledge Graph (nodi, archi, community).
#   3. Hardware: CPU, RAM di sistema (Windows/Linux/Mac), VRAM/GPU (NVIDIA / Apple Silicon).
#   4. Servizi: stato Ollama + modelli installati + modello attivo in VRAM, Laya, ComfyUI.

import os
import sys
import json
import time
import shutil
import platform
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from shared.power_sense import detect_host_power


# ── 1. STATO DEL CODEBASE (GIT & GRAPHIFY) ────────────────────────────────────

def _find_repo_root(hint_path: Optional[str] = None) -> Optional[Path]:
    """Cerca la radice della repository Git esaminando percorsi noti e directory padre."""
    candidates = []
    if hint_path:
        candidates.append(Path(hint_path))
    if os.getenv("REPO_DIR"):
        candidates.append(Path(os.getenv("REPO_DIR")))
    # Standard Docker mounts nel cluster HyperSpace
    candidates.extend([Path("/repo"), Path("."), Path("..")])

    for c in candidates:
        try:
            resolved = c.resolve()
            if (resolved / ".git").exists():
                return resolved
            if (resolved / "graphify-out").exists() or (resolved / "control-plane").exists():
                return resolved
        except Exception:
            continue
    return None


def _read_git_pure_python(git_dir: Path) -> Dict[str, Any]:
    """Estrae HEAD, branch e commit da .git senza dipendere dall'eseguibile git."""
    res = {
        "git_commit": "unknown",
        "git_commit_full": "unknown",
        "git_branch": "unknown",
        "git_commit_date": None,
        "git_commit_subject": None,
        "git_dirty": False,
        "dirty_files_count": 0,
        "dirty_summary": "clean (pure-python inspection)",
    }
    head_file = git_dir / "HEAD"
    if not head_file.exists():
        return res

    try:
        head_content = head_file.read_text(encoding="utf-8", errors="replace").strip()
        if head_content.startswith("ref: "):
            ref_path_rel = head_content[5:].strip()
            res["git_branch"] = ref_path_rel.replace("refs/heads/", "")
            target_file = git_dir / ref_path_rel
            if target_file.exists():
                sha = target_file.read_text(encoding="utf-8", errors="replace").strip()
                res["git_commit_full"] = sha
                res["git_commit"] = sha[:8]
            else:
                # Cerca in packed-refs
                packed = git_dir / "packed-refs"
                if packed.exists():
                    for line in packed.read_text(encoding="utf-8", errors="replace").splitlines():
                        parts = line.strip().split()
                        if len(parts) == 2 and parts[1] == ref_path_rel:
                            res["git_commit_full"] = parts[0]
                            res["git_commit"] = parts[0][:8]
                            break
        else:
            res["git_commit_full"] = head_content
            res["git_commit"] = head_content[:8]
            res["git_branch"] = "detached"
    except Exception:
        pass
    return res


def get_codebase_status(repo_hint: Optional[str] = None) -> Dict[str, Any]:
    """Rileva lo stato del repository git e la freschezza del Knowledge Graph."""
    repo_root = _find_repo_root(repo_hint)
    if not repo_root:
        return {
            "found": False,
            "error": "Repository root non trovata",
            "git_commit": "unknown",
            "git_branch": "unknown",
            "git_dirty": False,
            "graphify": {"available": False, "freshness": "missing"},
        }

    info: Dict[str, Any] = {
        "found": True,
        "path": str(repo_root),
        "git_commit": "unknown",
        "git_commit_full": "unknown",
        "git_branch": "unknown",
        "git_commit_date": None,
        "git_commit_author": None,
        "git_commit_subject": None,
        "git_dirty": False,
        "dirty_files_count": 0,
        "dirty_summary": "clean",
    }

    git_bin = shutil.which("git")
    git_dir = repo_root / ".git"

    if git_bin and git_dir.exists():
        try:
            # Commit hash
            p = subprocess.run([git_bin, "-C", str(repo_root), "rev-parse", "HEAD"],
                               capture_output=True, text=True, timeout=3)
            if p.returncode == 0:
                sha = p.stdout.strip()
                info["git_commit_full"] = sha
                info["git_commit"] = sha[:8]

            # Branch
            p = subprocess.run([git_bin, "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
                               capture_output=True, text=True, timeout=3)
            if p.returncode == 0:
                info["git_branch"] = p.stdout.strip()

            # Ultimo commit info
            p = subprocess.run([git_bin, "-C", str(repo_root), "log", "-1", "--format=%cI|%an|%s"],
                               capture_output=True, text=True, timeout=3)
            if p.returncode == 0 and "|" in p.stdout:
                parts = p.stdout.strip().split("|", 2)
                info["git_commit_date"] = parts[0]
                info["git_commit_author"] = parts[1]
                info["git_commit_subject"] = parts[2] if len(parts) > 2 else ""

            # Dirty state
            p = subprocess.run([git_bin, "-C", str(repo_root), "status", "--porcelain"],
                               capture_output=True, text=True, timeout=4)
            if p.returncode == 0:
                lines = [l for l in p.stdout.splitlines() if l.strip()]
                info["dirty_files_count"] = len(lines)
                info["git_dirty"] = len(lines) > 0
                if lines:
                    info["dirty_summary"] = f"{len(lines)} file non committati (es. {lines[0][:30]}...)"
                else:
                    info["dirty_summary"] = "working tree pulito"
        except Exception:
            # Fallback pure-python se git subprocess fallisce
            pure_info = _read_git_pure_python(git_dir)
            info.update(pure_info)
    elif git_dir.exists():
        pure_info = _read_git_pure_python(git_dir)
        info.update(pure_info)

    # ── Graphify status ──────────────────────────────────────────────
    graph_dir = repo_root / "graphify-out"
    graph_json = graph_dir / "graph.json"
    analysis_json = graph_dir / ".graphify_analysis.json"

    graph_info: Dict[str, Any] = {
        "available": graph_json.exists(),
        "freshness": "missing",
        "nodes_count": 0,
        "edges_count": 0,
        "communities_count": 0,
        "size_bytes": 0,
        "mtime": None,
    }

    if graph_json.exists():
        try:
            stat = graph_json.stat()
            graph_info["size_bytes"] = stat.st_size
            graph_info["mtime"] = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()

            # Se l'analisi ha il numero di community
            if analysis_json.exists():
                try:
                    with open(analysis_json, "r", encoding="utf-8") as f:
                        an = json.load(f)
                        graph_info["communities_count"] = len(an.get("communities", {}))
                except Exception:
                    pass

            # Stima della freschezza rispetto all'orario di modifica
            age_hours = (time.time() - stat.st_mtime) / 3600.0
            if age_hours < 48:
                graph_info["freshness"] = "fresh"
            else:
                graph_info["freshness"] = "stale"
        except Exception:
            graph_info["freshness"] = "error"

    info["graphify"] = graph_info
    return info


# ── 2. STATO HARDWARE & RISORSE (RAM / VRAM / CPU) ───────────────────────────

def get_system_hardware() -> Dict[str, Any]:
    """Rileva metriche hardware (CPU, RAM totale/disponibile, GPU/VRAM)."""
    hw: Dict[str, Any] = {
        "os": platform.system(),
        "os_release": platform.release(),
        "arch": platform.machine(),
        "cpu_count": os.cpu_count() or 1,
        "ram_total_gb": 0.0,
        "ram_free_gb": 0.0,
        "ram_used_pct": 0.0,
        "gpu_name": "unknown",
        "vram_total_gb": 0.0,
        "vram_free_gb": 0.0,
    }

    # RAM Detection
    sys_name = platform.system()
    if sys_name == "Windows":
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                hw["ram_total_gb"] = round(stat.ullTotalPhys / (1024**3), 2)
                hw["ram_free_gb"] = round(stat.ullAvailPhys / (1024**3), 2)
                hw["ram_used_pct"] = float(stat.dwMemoryLoad)
        except Exception:
            pass
    elif sys_name == "Linux":
        try:
            meminfo = Path("/proc/meminfo").read_text()
            total_kb, avail_kb = 0, 0
            for line in meminfo.splitlines():
                if line.startswith("MemTotal:"):
                    total_kb = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    avail_kb = int(line.split()[1])
            if total_kb > 0:
                hw["ram_total_gb"] = round(total_kb / (1024**2), 2)
                hw["ram_free_gb"] = round(avail_kb / (1024**2), 2)
                hw["ram_used_pct"] = round((1.0 - (avail_kb / total_kb)) * 100, 1)
        except Exception:
            pass
    elif sys_name == "Darwin":
        try:
            p = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=2)
            if p.returncode == 0:
                total_bytes = int(p.stdout.strip())
                hw["ram_total_gb"] = round(total_bytes / (1024**3), 2)
                hw["ram_free_gb"] = hw["ram_total_gb"] * 0.4  # stima conservative su Mac Unified
                hw["ram_used_pct"] = 60.0
                hw["gpu_name"] = "Apple Silicon Unified Memory"
                hw["vram_total_gb"] = hw["ram_total_gb"]
                hw["vram_free_gb"] = hw["ram_free_gb"]
        except Exception:
            pass

    # GPU / VRAM Detection (se non già rilevato da Mac)
    if hw["vram_total_gb"] == 0.0:
        smi = shutil.which("nvidia-smi")
        if smi:
            try:
                p = subprocess.run(
                    [smi, "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=3,
                )
                if p.returncode == 0 and p.stdout.strip():
                    parts = [x.strip() for x in p.stdout.strip().splitlines()[0].split(",")]
                    hw["gpu_name"] = parts[0]
                    hw["vram_total_gb"] = round(float(parts[1]) / 1024.0, 2)
                    hw["vram_free_gb"] = round(float(parts[2]) / 1024.0, 2)
            except Exception:
                pass

    # Override da env se configurato esplicitamente
    env_vram = os.getenv("VRAM_GB") or os.getenv("NODE_VRAM_GB")
    if env_vram:
        try:
            hw["vram_total_gb"] = float(env_vram)
            if hw["gpu_name"] == "unknown":
                hw["gpu_name"] = "Configured (VRAM_GB)"
        except Exception:
            pass

    # Rilevamento stato energetico (AC vs Batteria)
    power_info = detect_host_power()
    hw["power"] = power_info
    hw["ac_line"] = power_info.get("ac_line", True)
    hw["battery_pct"] = power_info.get("battery_pct")

    return hw


# ── 3. STATO SERVIZI (OLLAMA, LAYA, COMFYUI) ──────────────────────────────────

def get_services_status(
    ollama_url: Optional[str] = None,
    laya_url: Optional[str] = None,
    comfy_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Interroga lo stato dei servizi IA locali: Ollama, Laya Decision Engine, ComfyUI."""
    res: Dict[str, Any] = {
        "ollama": {"online": False, "models": [], "active_in_vram": []},
        "laya": {"online": False, "latency_ms": None, "engine": "none"},
        "comfyui": {"online": False},
    }

    ollama_ep = ollama_url or os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    laya_ep = laya_url or os.getenv("LAYA_URL", "http://127.0.0.1:8098").rstrip("/")
    comfy_ep = comfy_url or os.getenv("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")

    # Ollama
    try:
        r = requests.get(f"{ollama_ep}/api/tags", timeout=1.5)
        if r.status_code == 200:
            res["ollama"]["online"] = True
            models = []
            for m in r.json().get("models", []):
                size_gb = round(m.get("size", 0) / (1024**3), 2)
                models.append({
                    "name": m.get("name"),
                    "size_gb": size_gb,
                    "modified_at": m.get("modified_at"),
                })
            res["ollama"]["models"] = models
    except Exception:
        pass

    try:
        r = requests.get(f"{ollama_ep}/api/ps", timeout=1.5)
        if r.status_code == 200:
            active = []
            for m in r.json().get("models", []):
                vram_gb = round(m.get("size_vram", 0) / (1024**3), 2)
                active.append({
                    "name": m.get("name"),
                    "vram_gb": vram_gb,
                    "expires_at": m.get("expires_at"),
                })
            res["ollama"]["active_in_vram"] = active
    except Exception:
        pass

    # Laya Decision Engine
    try:
        t0 = time.perf_counter()
        r = requests.get(f"{laya_ep}/health", timeout=1.0)
        if r.status_code != 200:
            r = requests.get(f"{laya_ep}/v1/systemone/health", timeout=1.0)
        if r.status_code == 200:
            latency = round((time.perf_counter() - t0) * 1000, 2)
            res["laya"]["online"] = True
            res["laya"]["latency_ms"] = latency
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            res["laya"]["engine"] = data.get("model", "laya-decision-v1")
    except Exception:
        pass

    # ComfyUI
    try:
        r = requests.get(f"{comfy_ep}/system_stats", timeout=1.0)
        if r.status_code == 200:
            res["comfyui"]["online"] = True
    except Exception:
        pass

    return res


# ── 4. PACCHETTO COMPLETO TELEMETRIA NODO ─────────────────────────────────────

def collect_full_node_telemetry(
    node_id: str,
    public_key_hex: str,
    tier: str = "leaf",
    runtime_info: Optional[Dict[str, Any]] = None,
    repo_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Assembla l'intero pacchetto telemetria di un nodo (codebase, hardware, servizi, QoS)."""
    return {
        "node_id": node_id,
        "public_key": public_key_hex,
        "tier": tier,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "codebase": get_codebase_status(repo_hint),
        "hardware": get_system_hardware(),
        "services": get_services_status(),
        "runtime": runtime_info or {},
    }
