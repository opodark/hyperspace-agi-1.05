#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
HyperSpace Upstream Auto-Sync Engine.
Automatizza il monitoraggio, l'aggiornamento e la propagazione controllata
degli update provenienti dai repository e package esterni:
- REA (reverse engineering agents via npm global)
- Agency Agents (profili e prompt agentici in vendor/agency-agents/)
- Skills & Tools Forge (AnyDoc, Wayfinder, ECC)
- Hermes (integrità del vault di memoria e test del bridge)

Sicurezza e Guardrail (Self-Healing):
- Esecuzione non-regressiva immediata della suite di test per ciascun componente.
- Rollback istantaneo automatico in caso di fallimento del test.
- Logging delle operazioni in data/reports/auto_sync_history.jsonl.
- Stato globale in data/reports/auto_sync_status.json.
- Nessun git push automatico.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional
import urllib.request

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.integrations_manager import IntegrationsManager

REPORTS_DIR = REPO_ROOT / "data" / "reports"
HISTORY_FILE = REPORTS_DIR / "auto_sync_history.jsonl"
STATUS_FILE = REPORTS_DIR / "auto_sync_status.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def append_history(record: Dict[str, Any]):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def download_file(url: str, dest: Path, timeout_sec: int = 15) -> bool:
    """Scarica in modo affidabile un file remoto usando curl con i certificati di sistema."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    res = subprocess.run(
        ["curl", "-sL", "--fail", "-A", "HyperSpace-AutoSync", "-o", str(dest), url],
        capture_output=True,
        timeout=timeout_sec,
    )
    return res.returncode == 0


class UpstreamAutoSync:
    def __init__(self):
        self.manager = IntegrationsManager()

    # -------------------------------------------------------------
    # 1. REA (rea-agents via npm)
    # -------------------------------------------------------------
    def sync_rea(self, apply: bool = False) -> Dict[str, Any]:
        """Controlla ed eventualmente aggiorna il pacchetto globale rea-agents."""
        res: Dict[str, Any] = {"component": "rea_agents", "type": "npm_global"}

        # 1. Versione locale
        rea_bin = os.environ.get("REA_BIN", os.path.expanduser("~/.npm-global/bin/rea"))
        local_ver = None
        if Path(rea_bin).exists():
            try:
                proc = subprocess.run([rea_bin, "--version"], capture_output=True, text=True, timeout=5)
                if proc.returncode == 0:
                    local_ver = proc.stdout.strip().split()[-1]
            except Exception:
                pass
        res["local_version"] = local_ver

        # 2. Versione upstream su npm
        remote_ver = None
        try:
            proc = subprocess.run(["npm", "view", "rea-agents", "version"], capture_output=True, text=True, timeout=8)
            if proc.returncode == 0:
                remote_ver = proc.stdout.strip()
        except Exception:
            pass
        res["remote_version"] = remote_ver

        has_update = remote_ver and (local_ver != remote_ver)
        res["update_available"] = bool(has_update)

        if not has_update or not apply:
            res["applied"] = False
            res["status"] = "UPDATE_AVAILABLE" if has_update else "UP_TO_DATE"
            return res

        # 3. Applicazione con test e rollback automatico
        print(f"🔄 [REA] Aggiornamento {local_ver} → {remote_ver} via npm...")
        install_proc = subprocess.run(["npm", "install", "-g", f"rea-agents@{remote_ver}"], capture_output=True, text=True)
        if install_proc.returncode != 0:
            res["applied"] = False
            res["status"] = "INSTALL_FAILED"
            res["error"] = install_proc.stderr
            return res

        # Esegui test di non-regressione
        print("🧪 [REA] Esecuzione test di non-regressione (test_rea_surface.py)...")
        test_proc = subprocess.run(
            [str(REPO_ROOT / ".venv" / "bin" / "python"), "-m", "pytest", "tests/test_rea_surface.py", "-q"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )

        if test_proc.returncode == 0:
            print(f"✅ [REA] Aggiornamento completato con successo a v{remote_ver}!")
            self.manager.set_pin("rea_agents", remote_ver)
            res["applied"] = True
            res["status"] = "UPDATED_SUCCESS"
            res["new_version"] = remote_ver
            append_history({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "component": "rea_agents",
                "old_version": local_ver,
                "new_version": remote_ver,
                "status": "UPDATED_SUCCESS",
            })
        else:
            print(f"⚠️ [REA] Test fallito! Avvio rollback automatico a v{local_ver}...")
            if local_ver:
                subprocess.run(["npm", "install", "-g", f"rea-agents@{local_ver}"], capture_output=True, text=True)
            res["applied"] = False
            res["status"] = "ROLLBACK_TEST_FAILED"
            res["error"] = test_proc.stdout + "\n" + test_proc.stderr

        return res

    # -------------------------------------------------------------
    # 2. Agency Agents (vendor/agency-agents/)
    # -------------------------------------------------------------
    def sync_agency_agents(self, apply: bool = False) -> Dict[str, Any]:
        """Controlla ed eventualmente aggiorna i profili di Agency Agents in vendor/."""
        res: Dict[str, Any] = {"component": "agency_agents", "type": "forge_bundle"}
        bundle_dir = REPO_ROOT / "vendor" / "agency-agents"
        manifest_file = bundle_dir / "manifest.json"

        if not manifest_file.exists():
            res["status"] = "MANIFEST_MISSING"
            return res

        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        current_commit = manifest.get("commit")
        res["current_commit"] = current_commit

        # Query HEAD upstream
        upstream_repo = manifest.get("repository", "https://github.com/msitarzewski/agency-agents")
        remote_commit = self.manager.query_remote_ref(upstream_repo, "main", timeout_sec=8)
        res["remote_commit"] = remote_commit

        has_update = remote_commit and current_commit and (remote_commit != current_commit)
        res["update_available"] = bool(has_update)

        if not has_update or not apply:
            res["applied"] = False
            res["status"] = "UPDATE_AVAILABLE" if has_update else "UP_TO_DATE"
            return res

        print(f"🔄 [Agency Agents] Nuovo commit {remote_commit[:10]} (attuale: {current_commit[:10]}). Sincronizzazione...")
        backup_manifest = manifest_file.read_text(encoding="utf-8")

        try:
            # Scarica i file upstream specificati nel manifest
            upstream_files = [
                "engineering/engineering-multi-agent-systems-architect.md",
                "engineering/engineering-code-reviewer.md",
                "engineering/engineering-technical-writer.md",
            ]
            dest_mapping = {
                "engineering/engineering-multi-agent-systems-architect.md": bundle_dir / "upstream" / "engineering-multi-agent-systems-architect.md",
                "engineering/engineering-code-reviewer.md": bundle_dir / "upstream" / "engineering-code-reviewer.md",
                "engineering/engineering-technical-writer.md": bundle_dir / "upstream" / "engineering-technical-writer.md",
            }

            for u_path in upstream_files:
                raw_url = f"https://raw.githubusercontent.com/msitarzewski/agency-agents/{remote_commit}/{u_path}"
                dest_p = dest_mapping[u_path]
                if not download_file(raw_url, dest_p):
                    raise RuntimeError(f"Download fallito per {raw_url}")

            # Aggiorna gli hash SHA-256 nel manifest
            new_manifest = dict(manifest)
            new_manifest["commit"] = remote_commit
            for rel_file in new_manifest["files"].keys():
                file_p = bundle_dir / rel_file
                if file_p.exists():
                    new_manifest["files"][rel_file] = sha256_file(file_p)

            with open(manifest_file, "w", encoding="utf-8") as f:
                json.dump(new_manifest, f, indent=2)

            # Esegui test di non-regressione
            print("🧪 [Agency Agents] Esecuzione test di integrità Forge (test_forge_skills.py)...")
            test_proc = subprocess.run(
                [str(REPO_ROOT / ".venv" / "bin" / "python"), "-m", "pytest", "tests/test_forge_skills.py", "-k", "agency", "-q"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=30,
            )

            if test_proc.returncode == 0:
                print(f"✅ [Agency Agents] Sincronizzazione completata e verificata con successo!")
                self.manager.set_pin("agency_agents", remote_commit)
                res["applied"] = True
                res["status"] = "UPDATED_SUCCESS"
                res["new_commit"] = remote_commit
                append_history({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "component": "agency_agents",
                    "old_commit": current_commit,
                    "new_commit": remote_commit,
                    "status": "UPDATED_SUCCESS",
                })
            else:
                print(f"⚠️ [Agency Agents] Test fallito! Rollback manifest...")
                manifest_file.write_text(backup_manifest, encoding="utf-8")
                res["applied"] = False
                res["status"] = "ROLLBACK_TEST_FAILED"
                res["error"] = test_proc.stdout + "\n" + test_proc.stderr

        except Exception as exc:
            manifest_file.write_text(backup_manifest, encoding="utf-8")
            res["applied"] = False
            res["status"] = "ERROR"
            res["error"] = str(exc)

        return res

    # -------------------------------------------------------------
    # 3. AnyDoc Skills (vendor/anydoc/)
    # -------------------------------------------------------------
    def sync_anydoc(self, apply: bool = False) -> Dict[str, Any]:
        """Controlla ed eventualmente aggiorna i file AnyDoc."""
        res: Dict[str, Any] = {"component": "anydoc_skills", "type": "forge_bundle"}
        bundle_dir = REPO_ROOT / "vendor" / "anydoc"
        manifest_file = bundle_dir / "manifest.json"

        if not manifest_file.exists():
            res["status"] = "MANIFEST_MISSING"
            return res

        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        current_commit = manifest.get("commit")
        res["current_commit"] = current_commit

        upstream_repo = manifest.get("repository", "https://github.com/firecrawl/anydoc")
        remote_commit = self.manager.query_remote_ref(upstream_repo, "main", timeout_sec=8)
        res["remote_commit"] = remote_commit

        has_update = remote_commit and current_commit and (remote_commit != current_commit)
        res["update_available"] = bool(has_update)

        if not has_update or not apply:
            res["applied"] = False
            res["status"] = "UPDATE_AVAILABLE" if has_update else "UP_TO_DATE"
            return res

        print(f"🔄 [AnyDoc] Nuovo commit {remote_commit[:10]}. Sincronizzazione...")
        backup_manifest = manifest_file.read_text(encoding="utf-8")

        try:
            skill_dest = bundle_dir / "skills" / "convert-documents-to-markdown" / "SKILL.md"
            raw_url = f"https://raw.githubusercontent.com/firecrawl/anydoc/{remote_commit}/skills/convert-documents-to-markdown/SKILL.md"
            if not download_file(raw_url, skill_dest):
                raise RuntimeError(f"Download fallito per {raw_url}")

            new_manifest = dict(manifest)
            new_manifest["commit"] = remote_commit
            for rel_file in new_manifest["files"].keys():
                file_p = bundle_dir / rel_file
                if file_p.exists():
                    new_manifest["files"][rel_file] = sha256_file(file_p)

            with open(manifest_file, "w", encoding="utf-8") as f:
                json.dump(new_manifest, f, indent=2)

            test_proc = subprocess.run(
                [str(REPO_ROOT / ".venv" / "bin" / "python"), "-m", "pytest", "tests/test_forge_skills.py", "-k", "anydoc", "-q"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=30,
            )

            if test_proc.returncode == 0:
                print(f"✅ [AnyDoc] Sincronizzato con successo!")
                self.manager.set_pin("anydoc_skills", remote_commit)
                res["applied"] = True
                res["status"] = "UPDATED_SUCCESS"
                res["new_commit"] = remote_commit
                append_history({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "component": "anydoc_skills",
                    "old_commit": current_commit,
                    "new_commit": remote_commit,
                    "status": "UPDATED_SUCCESS",
                })
            else:
                manifest_file.write_text(backup_manifest, encoding="utf-8")
                res["applied"] = False
                res["status"] = "ROLLBACK_TEST_FAILED"

        except Exception as exc:
            manifest_file.write_text(backup_manifest, encoding="utf-8")
            res["applied"] = False
            res["status"] = "ERROR"
            res["error"] = str(exc)

        return res

    # -------------------------------------------------------------
    # 4. Hermes Memory Health & Resilience
    # -------------------------------------------------------------
    def check_hermes(self) -> Dict[str, Any]:
        """Esegue il controllo di salute e coerenza della memoria Hermes."""
        test_proc = subprocess.run(
            [str(REPO_ROOT / ".venv" / "bin" / "python"), "-m", "pytest", "tests/test_hermes_memory.py", "-q"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        passed = test_proc.returncode == 0
        return {
            "component": "hermes_memory",
            "type": "memory_engine",
            "status": "HEALTHY" if passed else "DEGRADED",
            "tests_passed": passed,
        }

    # -------------------------------------------------------------
    # 5. Open WebUI (Docker container & release audit)
    # -------------------------------------------------------------
    def check_open_webui(self) -> Dict[str, Any]:
        """Controlla lo stato e le nuove versioni disponibili per Open WebUI."""
        pinned = self.manager.integrations.get("open_webui", {}).get("pinned_ref", "v0.12.3")
        res: Dict[str, Any] = {
            "component": "open_webui",
            "type": "docker_service",
            "current_image": f"ghcr.io/open-webui/open-webui:{pinned}",
            "current_version": pinned,
        }
        # Rilevamento versione live dal container
        try:
            live_curl = subprocess.run(["curl", "-s", "--max-time", "2", "http://localhost:3000/api/version"], capture_output=True, text=True)
            if live_curl.returncode == 0 and live_curl.stdout.strip():
                live_data = json.loads(live_curl.stdout)
                res["live_running_version"] = f"v{live_data.get('version')}"
        except Exception:
            pass

        try:
            # Query release GitHub ufficiale
            curl_res = subprocess.run(
                ["curl", "-sL", "--fail", "-A", "HyperSpace-AutoSync", "https://api.github.com/repos/open-webui/open-webui/releases/latest"],
                capture_output=True,
                text=True,
                timeout=6,
            )
            if curl_res.returncode == 0 and curl_res.stdout.strip():
                data = json.loads(curl_res.stdout)
                latest_tag = data.get("tag_name")
                res["latest_version"] = latest_tag
                res["update_available"] = bool(latest_tag and latest_tag != res["current_version"])
                res["status"] = "UPDATE_AVAILABLE" if res["update_available"] else "UP_TO_DATE"
            else:
                res["status"] = "CHECK_OFFLINE"
        except Exception as exc:
            res["status"] = "CHECK_FAILED"
            res["error"] = str(exc)
        return res

    # -------------------------------------------------------------
    # Ciclo Globale
    # -------------------------------------------------------------
    def run_all(self, apply: bool = False) -> Dict[str, Any]:
        print(f"=== Esecuzione Auto-Sync Upstream (Modalità: {'APPLY' if apply else 'CHECK / DRY-RUN'}) ===")
        results = [
            self.sync_rea(apply=apply),
            self.sync_agency_agents(apply=apply),
            self.sync_anydoc(apply=apply),
            self.check_hermes(),
            self.check_open_webui(),
        ]

        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "apply_mode": apply,
            "components": results,
            "updates_detected": sum(1 for r in results if r.get("update_available")),
            "updates_applied": sum(1 for r in results if r.get("applied")),
        }

        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        if apply and summary["updates_applied"] > 0:
            append_history(summary)

        return summary


def main():
    parser = argparse.ArgumentParser(description="HyperSpace Upstream Auto-Sync Engine")
    parser.add_argument("--apply", action="store_true", help="Applica gli aggiornamenti disponibili con self-healing test")
    parser.add_argument("--component", choices=["rea", "agency", "anydoc", "hermes", "webui"], help="Sincronizza un solo componente")
    parser.add_argument("--json", action="store_true", help="Stampa l'output in formato JSON")
    args = parser.parse_args()

    engine = UpstreamAutoSync()

    if args.component == "rea":
        res = engine.sync_rea(apply=args.apply)
        print(json.dumps(res, indent=2))
    elif args.component == "agency":
        res = engine.sync_agency_agents(apply=args.apply)
        print(json.dumps(res, indent=2))
    elif args.component == "anydoc":
        res = engine.sync_anydoc(apply=args.apply)
        print(json.dumps(res, indent=2))
    elif args.component == "hermes":
        res = engine.check_hermes()
        print(json.dumps(res, indent=2))
    elif args.component == "webui":
        res = engine.check_open_webui()
        print(json.dumps(res, indent=2))
    else:
        summary = engine.run_all(apply=args.apply)
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print("\n=== Riepilogo Sincronizzazione ===")
            for c in summary["components"]:
                upd = "✨ Novità rilevata" if c.get("update_available") else "Allineato"
                app = " | Applicato ✅" if c.get("applied") else ""
                print(f"• {c['component']:<20} [{c.get('status')}]: {upd}{app}")


if __name__ == "__main__":
    main()
