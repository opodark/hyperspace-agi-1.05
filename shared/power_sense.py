# SPDX-License-Identifier: Apache-2.0
# shared/power_sense.py
# HyperSpace AGI — Energy Management & Power Sensing
"""Rilevamento dello stato energetico (AC vs Batteria, percentuale di carica)
per nodi portatili della mesh su macOS, Linux, Windows e ambienti containerizzati (Docker/WSL2)."""

import json
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_FRESHNESS_S = 60.0


def _parse_mac_pmset() -> Optional[Dict[str, Any]]:
    """Esegue pmset su macOS per rilevare AC Power vs Battery Power."""
    pmset = shutil.which("pmset")
    if not pmset:
        return None
    try:
        p = subprocess.run([pmset, "-g", "batt"], capture_output=True, text=True, timeout=2)
        if p.returncode != 0:
            return None
        out = p.stdout
        # 'AC Power' indica alimentatore collegato
        ac_line = "AC Power" in out
        m_pct = re.search(r"(\d+)%", out)
        pct = float(m_pct.group(1)) if m_pct else None
        is_batt = "InternalBattery" in out or pct is not None
        charging = "charging" in out.lower() and "discharging" not in out.lower()
        discharging = "discharging" in out.lower()
        return {
            "ac_line": ac_line,
            "battery_pct": pct,
            "is_battery": is_batt,
            "charging": charging,
            "discharging": discharging,
            "source": "pmset",
        }
    except Exception:
        return None


def _parse_linux_sysfs() -> Optional[Dict[str, Any]]:
    """Ispeziona /sys/class/power_supply/ su Linux."""
    base = Path("/sys/class/power_supply")
    if not base.exists() or not base.is_dir():
        return None

    ac_line = None
    pct = None
    is_batt = False
    charging = False
    discharging = False

    try:
        for entry in base.iterdir():
            name = entry.name.upper()
            # Alimentatori di rete (AC, ADP, ACAD)
            if any(name.startswith(p) for p in ("AC", "ADP", "MAINS")):
                online_file = entry / "online"
                if online_file.exists():
                    try:
                        ac_line = int(online_file.read_text().strip()) == 1
                    except Exception:
                        pass
            # Batterie (BAT0, BAT1, etc.)
            elif name.startswith("BAT"):
                is_batt = True
                cap_file = entry / "capacity"
                if cap_file.exists():
                    try:
                        pct = float(cap_file.read_text().strip())
                    except Exception:
                        pass
                status_file = entry / "status"
                if status_file.exists():
                    try:
                        st = status_file.read_text().strip().lower()
                        charging = (st == "charging")
                        discharging = (st == "discharging")
                    except Exception:
                        pass

        if ac_line is not None or is_batt:
            return {
                "ac_line": bool(ac_line if ac_line is not None else (not discharging)),
                "battery_pct": pct,
                "is_battery": is_batt,
                "charging": charging,
                "discharging": discharging,
                "source": "sysfs",
            }
    except Exception:
        pass
    return None


def _parse_windows_ctypes() -> Optional[Dict[str, Any]]:
    """Usa GetSystemPowerStatus su Windows nativo."""
    if platform.system() != "Windows":
        return None
    try:
        import ctypes
        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", ctypes.c_byte),
                ("BatteryFlag", ctypes.c_byte),
                ("BatteryLifePercent", ctypes.c_byte),
                ("SystemStatusFlag", ctypes.c_byte),
                ("BatteryLifeTime", ctypes.c_ulong),
                ("BatteryFullLifeTime", ctypes.c_ulong),
            ]
        stat = SYSTEM_POWER_STATUS()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(stat)):
            ac_line = (stat.ACLineStatus == 1)
            raw_pct = int(stat.BatteryLifePercent)
            pct = float(raw_pct) if raw_pct <= 100 else None
            is_batt = (stat.BatteryFlag != 128 and pct is not None)
            charging = bool(stat.BatteryFlag & 8)
            return {
                "ac_line": ac_line,
                "battery_pct": pct,
                "is_battery": is_batt,
                "charging": charging,
                "discharging": (not ac_line and is_batt),
                "source": "win32_api",
            }
    except Exception:
        pass
    return None


def _parse_wsl_powershell() -> Optional[Dict[str, Any]]:
    """Esegue powershell.exe dall'interno di WSL2 per interrogare Win32_Battery."""
    ps = shutil.which("powershell.exe")
    if not ps:
        return None
    try:
        cmd = [
            ps, "-NoProfile", "-NonInteractive", "-Command",
            "(Get-CimInstance Win32_Battery).EstimatedChargeRemaining; (Get-CimInstance Win32_Battery).BatteryStatus"
        ]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        if p.returncode == 0 and p.stdout.strip():
            lines = [l.strip() for l in p.stdout.splitlines() if l.strip()]
            if lines:
                pct = float(lines[0])
                status_code = int(lines[1]) if len(lines) > 1 and lines[1].isdigit() else 1
                # BatteryStatus: 1 = Other, 2 = Unknown, 3 = Fully Charged, 6 = Charging, 7 = Charging and High
                ac_line = status_code in (2, 3, 6, 7)
                return {
                    "ac_line": ac_line,
                    "battery_pct": pct,
                    "is_battery": True,
                    "charging": status_code in (6, 7),
                    "discharging": status_code in (1, 4, 5),
                    "source": "wsl_powershell",
                }
    except Exception:
        pass
    return None


def _read_host_power_file(data_dir: Optional[Path] = None, max_age_s: float = DEFAULT_FRESHNESS_S) -> Optional[Dict[str, Any]]:
    """Cerca host_power.json nelle directory dati condivise."""
    candidates = []
    if data_dir:
        candidates.append(Path(data_dir) / "host_power.json")
    candidates.extend([
        Path("data/host_power.json"),
        Path("/repo/data/host_power.json"),
        Path("/app/data/host_power.json"),
        Path("./host_power.json"),
    ])

    for p in candidates:
        if p.exists() and p.is_file():
            try:
                stat = p.stat()
                age = time.time() - stat.st_mtime
                if age <= max_age_s:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and "ac_line" in data:
                        data["file_age_s"] = round(age, 1)
                        data["source"] = f"file:{p.name}"
                        return data
            except Exception:
                pass
    return None


def save_host_power(status: Dict[str, Any], data_dir: Optional[Path] = None) -> Path:
    """Salva lo stato energetico su file condiviso per renderlo visibile ai container Docker."""
    target_dir = Path(data_dir) if data_dir else Path("data")
    target_dir.mkdir(parents=True, exist_ok=True)
    out_file = target_dir / "host_power.json"
    temp_file = target_dir / f"host_power.{os.getpid()}.tmp"

    payload = {
        **status,
        "timestamp": int(time.time()),
        "iso_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    temp_file.replace(out_file)
    return out_file


def detect_host_power(data_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Funzione principale: rileva lo stato energetico con fallback intelligente.

    Ordine di risoluzione:
      1. File condiviso host_power.json (se recente < 60s, vitale per container Docker)
      2. Rilevamento nativo host (pmset su Mac, sysfs su Linux, Win32 API su Windows, PowerShell su WSL2)
      3. Fallback di sicurezza: alimentazione da rete presunta (ac_line=True, is_battery=False).
    """
    # 1. File host condiviso
    file_status = _read_host_power_file(data_dir=data_dir)
    if file_status:
        return file_status

    # 2. Rilevamento nativo per OS
    sys_name = platform.system()
    if sys_name == "Darwin":
        res = _parse_mac_pmset()
        if res:
            return res
    elif sys_name == "Linux":
        # Tentativo WSL2 powershell prima di sysfs
        if "microsoft" in platform.release().lower():
            res_wsl = _parse_wsl_powershell()
            if res_wsl:
                return res_wsl
        res_linux = _parse_linux_sysfs()
        if res_linux:
            return res_linux
    elif sys_name == "Windows":
        res_win = _parse_windows_ctypes()
        if res_win:
            return res_win

    # 3. Fallback default (desktop fisso o macchina collegata)
    return {
        "ac_line": True,
        "battery_pct": None,
        "is_battery": False,
        "charging": False,
        "discharging": False,
        "source": "default_ac",
    }
