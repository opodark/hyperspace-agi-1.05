#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
HyperSpace Unified Integrations & Upstream Manager.
Strumento di monitoraggio, audit e verifica per tutti i repository e moduli
integrati nel mesh e nel runtime di HyperSpace.

Caratteristiche:
- Ispezione read-only e audit delle versioni locali vs pinned vs upstream.
- Rilevamento dello stato git (branch, commit SHA, modifiche uncommitted).
- Verifica non distruttiva degli upstream remoti via git ls-remote / API.
- Esecuzione controllata dei comandi di test di non-regressione.
- Esportazione report in formato JSON (per Cockpit API) o Markdown tabellare.

Regole di sicurezza (AGENTS.md & git-mesh-protocol.md):
- Nessun git push automatico.
- Nessun git commit automatico.
- Nessuna sovrascrittura distruttiva senza flag esplicito.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "integrations" / "integrations.manifest.yaml"


class IntegrationsManager:
    def __init__(self, manifest_path: Optional[Path] = None):
        self.manifest_path = manifest_path or DEFAULT_MANIFEST
        self.config = self._load_manifest()

    def _load_manifest(self) -> Dict[str, Any]:
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest non trovato: {self.manifest_path}")
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    @property
    def integrations(self) -> Dict[str, Any]:
        return self.config.get("integrations", {})

    def resolve_path(self, local_path_str: Optional[str]) -> Optional[Path]:
        if not local_path_str:
            return None
        # Supporto espansione variabili stile bash: ${VAR:-default}
        pattern = re.compile(r"\$\{([^}:]+)(?::-([^}]+))?\}")
        expanded = pattern.sub(lambda m: os.environ.get(m.group(1), m.group(2) or ""), local_path_str)
        expanded = os.path.expandvars(expanded)
        p = Path(os.path.expanduser(expanded))
        if p.is_absolute():
            return p
        return (REPO_ROOT / p).resolve()

    def get_git_info(self, path: Path) -> Dict[str, Any]:
        """Estrae informazioni git da una directory locale se è un repository git."""
        git_dir = path / ".git"
        if not git_dir.exists() and not (path / "HEAD").exists():
            return {"is_git": False}

        info: Dict[str, Any] = {"is_git": True}
        try:
            # Commit SHA corrente
            res_sha = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res_sha.returncode == 0:
                info["commit_sha"] = res_sha.stdout.strip()
                info["commit_short"] = info["commit_sha"][:8]
            else:
                info["commit_sha"] = None

            # Branch corrente
            res_branch = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res_branch.returncode == 0:
                info["branch"] = res_branch.stdout.strip()

            # Modifiche uncommitted / dirty
            res_status = subprocess.run(
                ["git", "-C", str(path), "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res_status.returncode == 0:
                dirty_lines = [l for l in res_status.stdout.splitlines() if l.strip()]
                info["is_dirty"] = len(dirty_lines) > 0
                info["dirty_count"] = len(dirty_lines)
            else:
                info["is_dirty"] = False
                info["dirty_count"] = 0

        except Exception as exc:
            info["error"] = str(exc)

        return info

    def query_remote_ref(self, upstream_url: str, ref_or_branch: str, timeout_sec: int = 8) -> Optional[str]:
        """Interroga in sola lettura il remote git (tramite git ls-remote) per ottenere l'hash SHA remoto."""
        if not upstream_url:
            return None

        # Normalizza url SSH github in HTTPS per evitare prompt di passphrase ssh batch
        query_url = upstream_url
        if query_url.startswith("git@github.com:"):
            query_url = query_url.replace("git@github.com:", "https://github.com/")

        env = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new",
        }

        try:
            res = subprocess.run(
                ["git", "ls-remote", query_url, ref_or_branch, f"refs/heads/{ref_or_branch}", f"refs/tags/{ref_or_branch}"],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                env=env,
            )
            if res.returncode == 0 and res.stdout.strip():
                # Il formato di ls-remote è: <sha>\t<ref>
                lines = res.stdout.strip().splitlines()
                first_line = lines[0]
                sha = first_line.split()[0]
                return sha
        except Exception:
            pass
        return None

    def status(self, integration_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Ispeziona lo stato locale di tutte le integrazioni o di una specifica."""
        results: List[Dict[str, Any]] = []
        targets = {integration_id: self.integrations[integration_id]} if integration_id else self.integrations

        for k, item in targets.items():
            path_key = item.get("local_path") or item.get("local_bin")
            local_path = self.resolve_path(path_key)
            exists = local_path.exists() if local_path else False

            record: Dict[str, Any] = {
                "id": k,
                "name": item.get("name", k),
                "category": item.get("category", "unknown"),
                "local_path": str(local_path) if local_path else None,
                "exists": exists,
                "pinned_ref": item.get("pinned_ref"),
                "upstream_url": item.get("upstream_url") or None,
                "pin_reason": item.get("pin_reason"),
                "test_command": item.get("test_command"),
                "auto_sync": item.get("auto_sync", False),
            }

            if item.get("category") == "docker_service":
                c_name = item.get("container_name", "")
                try:
                    res_c = subprocess.run(
                        ["docker", "ps", "--filter", f"name={c_name}", "--format", "{{.Image}}"],
                        capture_output=True,
                        text=True,
                        timeout=4,
                    )
                    if res_c.returncode == 0 and res_c.stdout.strip():
                        exists = True
                        record["exists"] = True
                        record["running_image"] = res_c.stdout.strip()
                        record["status_label"] = "DOCKER_RUNNING"
                    else:
                        record["status_label"] = "DOCKER_STOPPED"
                except Exception:
                    pass
            elif exists and local_path:
                git_info = self.get_git_info(local_path)
                record["git"] = git_info
                # Se è vendored all'interno del repo principale
                if item.get("category") == "vendored":
                    record["status_label"] = "VENDORED_LOCAL"
                elif item.get("category") == "npm_global":
                    record["status_label"] = "INSTALLED_NPM"
                elif git_info.get("is_git"):
                    current_sha = git_info.get("commit_sha")
                    pinned = item.get("pinned_ref")
                    if pinned and current_sha and (current_sha.startswith(pinned) or pinned.startswith(current_sha[:8])):
                        record["status_label"] = "PINNED_MATCH"
                    elif git_info.get("is_dirty"):
                        record["status_label"] = "LOCAL_DIRTY"
                    else:
                        record["status_label"] = "INSTALLED"
                else:
                    record["status_label"] = "INSTALLED_NO_GIT"
            else:
                record["git"] = {"is_git": False}
                record["status_label"] = "MISSING_LOCAL"

            results.append(record)

        return results

    def check_upstream(self, integration_id: Optional[str] = None, timeout_sec: int = 8) -> List[Dict[str, Any]]:
        """Verifica lo stato rispetto al repository upstream remoto."""
        statuses = self.status(integration_id)
        for entry in statuses:
            upstream_url = entry.get("upstream_url")
            pinned_ref = entry.get("pinned_ref")
            active_branch = self.integrations.get(entry["id"], {}).get("active_branch", "main")

            if not upstream_url:
                entry["upstream_status"] = "NO_UPSTREAM"
                entry["remote_sha"] = None
                continue

            remote_sha = self.query_remote_ref(upstream_url, active_branch, timeout_sec=timeout_sec)
            entry["remote_sha"] = remote_sha

            if not remote_sha:
                entry["upstream_status"] = "REMOTE_UNREACHABLE"
            elif pinned_ref:
                if remote_sha.startswith(pinned_ref) or pinned_ref.startswith(remote_sha[:8]):
                    entry["upstream_status"] = "UP_TO_DATE"
                else:
                    entry["upstream_status"] = "NEW_UPSTREAM_AVAILABLE"
            else:
                entry["upstream_status"] = "CHECKED"

        return statuses

    def diff(self, integration_id: str) -> Dict[str, Any]:
        """Confronta l'integrazione locale con la reference originaria o lo stato git."""
        if integration_id not in self.integrations:
            return {"id": integration_id, "error": f"Integrazione {integration_id} non trovata"}

        item = self.integrations[integration_id]
        local_path = self.resolve_path(item.get("local_path"))
        res: Dict[str, Any] = {"id": integration_id, "name": item.get("name")}

        # 1. Se è una cartella vendored con reference_path (es. tiktok_editor)
        ref_path_str = item.get("reference_path")
        if ref_path_str:
            ref_path = self.resolve_path(ref_path_str)
            res["reference_path"] = str(ref_path)
            if ref_path and ref_path.exists() and local_path and local_path.exists():
                diff_cmd = [
                    "diff", "-rq",
                    "-x", ".venv*", "-x", "__pycache__", "-x", "*.pyc", "-x", ".DS_Store", "-x", ".git*",
                    str(local_path), str(ref_path),
                ]
                run_diff = subprocess.run(diff_cmd, capture_output=True, text=True)
                lines = run_diff.stdout.splitlines()

                only_in_hyperspace = []
                only_in_reference = []
                differing = []

                for line in lines:
                    if f"Only in {local_path}" in line:
                        only_in_hyperspace.append(line.replace(f"Only in {local_path}: ", "").strip())
                    elif f"Only in {ref_path}" in line:
                        only_in_reference.append(line.replace(f"Only in {ref_path}: ", "").strip())
                    elif "differ" in line:
                        differing.append(line.strip())

                res["vendored_comparison"] = {
                    "custom_hyperspace_additions": only_in_hyperspace,
                    "reference_only_files": only_in_reference,
                    "modified_files": differing,
                }
            else:
                res["vendored_comparison"] = {"error": f"Percorso reference o locale non trovato ({ref_path_str})"}

        # 2. Se è un repository git locale
        if local_path and local_path.exists():
            git_info = self.get_git_info(local_path)
            if git_info.get("is_git"):
                res_diff_stat = subprocess.run(
                    ["git", "-C", str(local_path), "diff", "--stat"],
                    capture_output=True,
                    text=True,
                )
                res["git_diff_stat"] = res_diff_stat.stdout.strip()
                res_log = subprocess.run(
                    ["git", "-C", str(local_path), "log", "-n", "3", "--oneline"],
                    capture_output=True,
                    text=True,
                )
                res["git_recent_commits"] = res_log.stdout.splitlines()

        return res

    def set_pin(self, integration_id: str, new_ref: str) -> bool:
        """Aggiorna in modo controllato il pinned_ref nel manifest."""
        if integration_id not in self.integrations:
            raise KeyError(f"Integrazione {integration_id} non trovata nel manifest")

        self.config["integrations"][integration_id]["pinned_ref"] = new_ref
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.config, f, sort_keys=False)
        return True

    def run_verify(self, integration_id: str) -> Dict[str, Any]:
        """Esegue il test_command associato all'integrazione per verificarne l'integrità."""
        if integration_id not in self.integrations:
            return {"id": integration_id, "success": False, "error": f"Integrazione {integration_id} non registrata"}

        item = self.integrations[integration_id]
        cmd = item.get("test_command")
        if not cmd:
            return {"id": integration_id, "success": True, "skipped": True, "message": "Nessun test_command specificato"}

        try:
            start_t = subprocess.run(
                cmd,
                shell=True,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=120,
            )
            success = start_t.returncode == 0
            return {
                "id": integration_id,
                "command": cmd,
                "returncode": start_t.returncode,
                "success": success,
                "stdout_tail": "\n".join(start_t.stdout.splitlines()[-10:]),
                "stderr_tail": "\n".join(start_t.stderr.splitlines()[-10:]),
            }
        except subprocess.TimeoutExpired:
            return {"id": integration_id, "command": cmd, "success": False, "error": "Timeout scaduto (120s)"}
        except Exception as exc:
            return {"id": integration_id, "command": cmd, "success": False, "error": str(exc)}

    def format_table(self, data: List[Dict[str, Any]], with_upstream: bool = False) -> str:
        """Formatta i dati in una tabella markdown leggibile."""
        if with_upstream:
            headers = ["ID", "Categoria", "Presente", "Pinned Ref", "Local Commit", "Upstream", "Stato"]
            rows = []
            for d in data:
                exists_str = "Sì" if d.get("exists") else "No"
                git_info = d.get("git", {})
                local_commit = git_info.get("commit_short", "-") if git_info.get("is_git") else "-"
                pinned = d.get("pinned_ref", "-") or "-"
                upstream_st = d.get("upstream_status", "-")
                status_lbl = d.get("status_label", "-")
                rows.append([d["id"], d["category"], exists_str, pinned, local_commit, upstream_st, status_lbl])
        else:
            headers = ["ID", "Nome", "Categoria", "Presente", "Pinned Ref", "Git Dirty", "Stato"]
            rows = []
            for d in data:
                exists_str = "Sì" if d.get("exists") else "No"
                git_info = d.get("git", {})
                is_dirty = f"Sì ({git_info.get('dirty_count')})" if git_info.get("is_dirty") else "No"
                pinned = d.get("pinned_ref", "-") or "-"
                status_lbl = d.get("status_label", "-")
                rows.append([d["id"], d["name"], d["category"], exists_str, pinned, is_dirty, status_lbl])

        # Costruzione tabella markdown
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, val in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(val)))

        header_line = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"
        sep_line = "|-" + "-|-".join("-" * col_widths[i] for i in range(len(headers))) + "-|"
        body_lines = ["| " + " | ".join(str(val).ljust(col_widths[i]) for i, val in enumerate(row)) + " |" for row in rows]

        return "\n".join([header_line, sep_line] + body_lines)


def main():
    parser = argparse.ArgumentParser(description="HyperSpace Integrations & Upstream Manager")
    parser.add_argument("action", choices=["list", "status", "check", "verify", "diff", "set-pin", "report"], default="status", nargs="?")
    parser.add_argument("--id", help="ID dell'integrazione specifica su cui operare")
    parser.add_argument("--ref", help="Nuovo ref/tag/commit per l'azione set-pin")
    parser.add_argument("--manifest", type=Path, help="Percorso alternativo del manifest")
    parser.add_argument("--json", action="store_true", help="Stampa l'output in formato JSON")
    parser.add_argument("--timeout", type=int, default=8, help="Timeout in secondi per le interrogazioni remote (default 8s)")
    args = parser.parse_args()

    manager = IntegrationsManager(manifest_path=args.manifest)

    if args.action == "list":
        items = [
            {"id": k, "name": v.get("name"), "category": v.get("category"), "path": v.get("local_path")}
            for k, v in manager.integrations.items()
        ]
        if args.json:
            print(json.dumps(items, indent=2))
        else:
            for item in items:
                print(f"• {item['id']:<24} [{item['category']:<14}] {item['name']}")

    elif args.action == "status":
        results = manager.status(integration_id=args.id)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"=== Stato Integrazioni HyperSpace ({len(results)} componenti registrati) ===")
            print(manager.format_table(results, with_upstream=False))

    elif args.action == "check":
        results = manager.check_upstream(integration_id=args.id, timeout_sec=args.timeout)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"=== Verifica Upstream Remoti ({len(results)} componenti) ===")
            print(manager.format_table(results, with_upstream=True))

    elif args.action == "verify":
        if args.id:
            targets = [args.id]
        else:
            targets = list(manager.integrations.keys())

        verify_results = []
        for tid in targets:
            res = manager.run_verify(tid)
            verify_results.append(res)
            if not args.json:
                symbol = "✅" if res.get("success") else ("⚠️" if res.get("skipped") else "❌")
                print(f"{symbol} [{tid}]: {res.get('message') or ('PASS' if res.get('success') else res.get('error', 'FAIL'))}")

        if args.json:
            print(json.dumps(verify_results, indent=2))

    elif args.action == "diff":
        if not args.id:
            print("Errore: specifica --id <nome_integrazione> per visualizzare il diff")
            sys.exit(1)
        res = manager.diff(args.id)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"=== Audit Diff per [{args.id}] ===")
            comp = res.get("vendored_comparison")
            if comp:
                print("\n[Modifiche Custom HyperSpace / Nuovi file]:")
                for f in comp.get("custom_hyperspace_additions", []):
                    print(f"  + {f}")
                print("\n[File modificati rispetto alla reference]:")
                for f in comp.get("modified_files", []):
                    print(f"  ~ {f}")
                print("\n[File presenti solo nella reference]:")
                for f in comp.get("reference_only_files", []):
                    print(f"  - {f}")
            if res.get("git_diff_stat"):
                print("\n[Git diff stat locale]:")
                print(res["git_diff_stat"])
            if res.get("git_recent_commits"):
                print("\n[Ultimi commit git]:")
                for c in res["git_recent_commits"]:
                    print(f"  {c}")

    elif args.action == "set-pin":
        if not args.id or not args.ref:
            print("Errore: specifica sia --id <nome> sia --ref <nuovo_commit_o_tag>")
            sys.exit(1)
        manager.set_pin(args.id, args.ref)
        print(f"✅ Aggiornato pinned_ref per [{args.id}] a '{args.ref}' nel manifest {manager.manifest_path}")

    elif args.action == "report":
        data = manager.check_upstream(integration_id=args.id, timeout_sec=args.timeout)
        report_data = {
            "version": manager.config.get("version", "1.0"),
            "timestamp": "now",
            "total_integrations": len(data),
            "integrations": data,
        }
        if args.json:
            print(json.dumps(report_data, indent=2))
        else:
            print(f"# Report Integrazioni e Upstream HyperSpace")
            print(manager.format_table(data, with_upstream=True))


if __name__ == "__main__":
    main()
