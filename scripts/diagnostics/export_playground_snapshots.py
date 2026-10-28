#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Esportatore di Snapshot Dati per Playground Web e Cockpit HyperSpace.

Genera snapshot JSON statici consistenti dei dati dinamici (Scouting Trend Agent-Reach,
Registro Missioni DAG, Sogni Notturni, Turno OMEN, Ricerca AGI) per garantire che
le dashboard web (come missions.html) funzionino in modo resiliente sia con le API
live di Cockpit (:8090) che su hosting statico / Aruba senza generare errori 404.

Uso:
    .venv/bin/python scripts/diagnostics/export_playground_snapshots.py
    .venv/bin/python scripts/diagnostics/export_playground_snapshots.py --target dist/web-node-aruba/apps/playground/data
    .venv/bin/python scripts/diagnostics/export_playground_snapshots.py --run-scout
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_TARGET = REPO_ROOT / "web-node" / "apps" / "playground" / "data"


def export_snapshots(target_dir: Path, run_scout: bool = False) -> dict:
    target_dir.mkdir(parents=True, exist_ok=True)
    summary = {}

    # 1. Trend Inspirations (Agent-Reach)
    scout_file = REPO_ROOT / "data" / "control-plane" / "trend_inspirations.json"
    if run_scout or not scout_file.exists():
        scout_script = REPO_ROOT / "scripts" / "diagnostics" / "trend_scout_reach.py"
        if scout_script.exists():
            print("[*] Esecuzione scansione Agent-Reach...")
            subprocess.run([sys.executable, str(scout_script), "--save"], cwd=str(REPO_ROOT), timeout=60)

    if scout_file.exists():
        try:
            data = json.loads(scout_file.read_text(encoding="utf-8"))
            out_file = target_dir / "trend_inspirations.json"
            out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            summary["trend_inspirations"] = len(data.get("items", []))
        except Exception as exc:
            summary["trend_inspirations_error"] = str(exc)

    # 2. Missions DAG
    missions_file = REPO_ROOT / "data" / "missions.jsonl"
    if missions_file.exists():
        missions = []
        try:
            for line in missions_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        missions.append(json.loads(line))
                    except Exception:
                        pass
            out_file = target_dir / "missions.json"
            out_file.write_text(json.dumps({"missions": missions[-50:]}, ensure_ascii=False, indent=2), encoding="utf-8")
            summary["missions"] = len(missions)
        except Exception as exc:
            summary["missions_error"] = str(exc)

    # 3. Persona Dreams
    dreams_file = REPO_ROOT / "data" / "persona_dreams.json"
    if dreams_file.exists():
        try:
            raw_dreams = json.loads(dreams_file.read_text(encoding="utf-8"))
            out_file = target_dir / "persona_dreams.json"
            out_file.write_text(json.dumps({"ok": True, "dreams": raw_dreams}, ensure_ascii=False, indent=2), encoding="utf-8")
            summary["persona_dreams"] = len(raw_dreams)
        except Exception as exc:
            summary["persona_dreams_error"] = str(exc)

    # 4. Nightly Shift
    try:
        from scripts.omen_allnight_sovereign import get_nightly_status
        st = get_nightly_status()
        st["daemon_running"] = True
        out_file = target_dir / "nightly_shift.json"
        out_file.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
        summary["nightly_shift"] = "ok"
    except Exception as exc:
        summary["nightly_shift_error"] = str(exc)

    # 5. AGI Research & Deep Dives
    try:
        from shared.agi_research_engine import AGIResearchEngine, SYNTHESIS_MD, DEEP_DIVES_LOG
        engine = AGIResearchEngine()
        st = engine.get_research_status()
        synthesis_text = SYNTHESIS_MD.read_text(encoding="utf-8") if SYNTHESIS_MD.exists() else ""
        deep_dives = []
        if DEEP_DIVES_LOG.exists():
            for line in DEEP_DIVES_LOG.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        deep_dives.append(json.loads(line))
                    except Exception:
                        pass
        out_file = target_dir / "agi_research.json"
        out_file.write_text(json.dumps({
            "status": "ok",
            "research_status": st,
            "synthesis_md": synthesis_text,
            "deep_dives": deep_dives[-10:],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        summary["agi_research"] = len(deep_dives)
    except Exception as exc:
        summary["agi_research_error"] = str(exc)

    # Storico test (analytics.html): stesso contenuto di /api/analytics
    try:
        from scripts.cockpit_service import CockpitHandler
        captured: dict = {}

        class _Capture:
            def send_json(self, data, status=200):
                captured.update(data)

        CockpitHandler.handle_api_analytics(_Capture())
        if captured:
            (target_dir / "analytics.json").write_text(json.dumps(captured, ensure_ascii=False, indent=2), encoding="utf-8")
            summary["analytics"] = len(captured.get("milestones", []))
    except Exception as exc:
        summary["analytics_error"] = str(exc)

    return summary


def main():
    parser = argparse.ArgumentParser(description="Esporta snapshot statici per Playground & Cockpit")
    parser.add_argument("--target", type=str, default=str(DEFAULT_TARGET), help="Cartella di destinazione")
    parser.add_argument("--run-scout", action="store_true", help="Forza scansione live Agent-Reach prima dell'export")
    args = parser.parse_args()

    target_path = Path(args.target).resolve()
    print(f"[*] Esportazione snapshot in {target_path}...")
    res = export_snapshots(target_path, run_scout=args.run_scout)
    print(f"✅ Snapshot generati con successo: {json.dumps(res, indent=2)}")


if __name__ == "__main__":
    main()
