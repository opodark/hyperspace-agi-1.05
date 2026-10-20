#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# shared/codebase_journal.py
"""Diario e Calendario dell'Evoluzione della Codebase per Agenti Autonomi.

Questo modulo permette agli agenti di HyperSpace (Antigravity, Cline, Codex,
Mission Control Coder, Nightly Orchestrator) di:
1. Registrare ogni mutazione architetturale in un registro immutabile append-only (`data/codebase_chronicle.jsonl`).
2. Generare un calendario/timeline visuale cronologico in `docs/codebase-calendar.md`.
3. Interrogare la memoria storica e le "lezioni apprese" prima di toccare un modulo per evitare regressioni.
4. Sincronizzare gli eventi con la Shadow Memory di Hermes per persistenza cognitiva inter-agente.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CHRONICLE_FILE = DATA_DIR / "codebase_chronicle.jsonl"
CALENDAR_MD = ROOT / "docs" / "codebase-calendar.md"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _today_date() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


class CodebaseJournal:
    def __init__(self, chronicle_path: Optional[Path] = None, calendar_path: Optional[Path] = None):
        self.chronicle_path = chronicle_path or CHRONICLE_FILE
        self.calendar_path = calendar_path or CALENDAR_MD
        self.chronicle_path.parent.mkdir(parents=True, exist_ok=True)

    def record_mutation(
        self,
        agent: str,
        intent: str,
        files_touched: List[str],
        action_type: str = "feature",
        test_status: str = "passed",
        lessons_learned: str = "",
        graph_nodes_impacted: Optional[List[str]] = None,
        commit_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Registra una modifica architetturale effettuata da un agente."""
        now = _now_iso()
        entry_id = f"mut-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}-{os.urandom(3).hex()}"

        entry: Dict[str, Any] = {
            "id": entry_id,
            "timestamp": now,
            "date": now[:10],
            "agent": str(agent).strip() or "anonymous-agent",
            "action_type": action_type if action_type in {"feature", "fix", "refactor", "hardening", "test", "benchmark"} else "feature",
            "intent": str(intent).strip(),
            "files_touched": [str(f).replace("\\", "/") for f in files_touched],
            "graph_nodes_impacted": graph_nodes_impacted or [],
            "test_status": str(test_status).strip() or "untested",
            "lessons_learned": str(lessons_learned).strip(),
            "commit_hash": str(commit_hash).strip() if commit_hash else "",
        }

        # Scrittura atomica append su jsonl
        with open(self.chronicle_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Rigenera la timeline markdown
        self.sync_markdown_calendar()
        return entry

    def get_timeline(
        self,
        limit: int = 50,
        agent: Optional[str] = None,
        action_type: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Recupera la sequenza temporale degli eventi filtrata per criteri."""
        if not self.chronicle_path.exists():
            return []

        entries: List[Dict[str, Any]] = []
        with open(self.chronicle_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if not isinstance(data, dict):
                        continue
                except ValueError:
                    continue

                if agent and data.get("agent", "").lower() != agent.lower():
                    continue
                if action_type and data.get("action_type", "").lower() != action_type.lower():
                    continue
                if file_path:
                    norm_path = file_path.replace("\\", "/").lower()
                    touched = [f.lower() for f in data.get("files_touched", [])]
                    if not any(norm_path in t for t in touched):
                        continue

                entries.append(data)

        # Ordine cronologico inverso (più recenti prima)
        entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return entries[:limit]

    def query_lessons(self, query: str = "", file_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Interroga la memoria storica per recuperare lezioni apprese prima di una modifica."""
        all_entries = self.get_timeline(limit=200, file_path=file_path)
        needle = query.lower().strip()
        matched = []
        for e in all_entries:
            lessons = e.get("lessons_learned", "")
            intent = e.get("intent", "")
            if not lessons:
                continue
            if not needle or needle in lessons.lower() or needle in intent.lower():
                matched.append({
                    "date": e.get("date"),
                    "agent": e.get("agent"),
                    "intent": e.get("intent"),
                    "files": e.get("files_touched"),
                    "lessons_learned": lessons,
                    "test_status": e.get("test_status"),
                })
        return matched

    def sync_markdown_calendar(self) -> Path:
        """Sintetizza le voci del diario in una vista calendario e timeline Markdown leggibile."""
        entries = self.get_timeline(limit=100)

        # Raggruppa per data
        by_date: Dict[str, List[Dict[str, Any]]] = {}
        for e in entries:
            d = e.get("date", "Data non definita")
            by_date.setdefault(d, []).append(e)

        lines = [
            "# Calendario ed Evoluzione Autonoma della Codebase (HyperSpace AGI)",
            "",
            "> Questo documento viene aggiornato automaticamente dagli agenti e dagli strumenti di HyperSpace.",
            "> Consulta questo storico prima di avviare refactor o modifiche architetturali.",
            "",
            "## 📅 Calendario delle Modifiche Recenti",
            "",
        ]

        if not by_date:
            lines.append("*Nessuna mutazione architetturale ancora registrata nel diario.*")
        else:
            for date_str in sorted(by_date.keys(), reverse=True):
                items = by_date[date_str]
                lines.append(f"### {date_str} ({len(items)} eventi)")
                for item in items:
                    icon = {
                        "feature": "✨",
                        "fix": "🐛",
                        "refactor": "♻️",
                        "hardening": "🛡️",
                        "test": "🧪",
                        "benchmark": "⚡",
                    }.get(item.get("action_type", ""), "📝")

                    commit_tag = f" `[{item['commit_hash'][:7]}]`" if item.get("commit_hash") else ""
                    lines.append(f"- **{icon} [{item.get('agent')}]**{commit_tag}: {item.get('intent')}")
                    if item.get("files_touched"):
                        files_str = ", ".join(f"`{f}`" for f in item["files_touched"][:5])
                        if len(item["files_touched"]) > 5:
                            files_str += f" (+{len(item['files_touched']) - 5} altri)"
                        lines.append(f"  - **File:** {files_str}")
                    if item.get("lessons_learned"):
                        lines.append(f"  - **💡 Lezione Appresa:** {item['lessons_learned']}")
                    if item.get("test_status"):
                        lines.append(f"  - **Verifica Test:** `{item['test_status']}`")
                lines.append("")

        lines.extend([
            "---",
            "## 🧠 Indice delle Regole e Lezioni Critiche",
            "",
            "- **Mount Docker Read-Only**: sui container dei nodi (`node-1`), `/repo` è in sola lettura. Ogni patch/file deve passare dal watcher host o da Git commit.",
            "- **Gestione VRAM & Context Window**: su GPU con 8 GB VRAM (RTX 3070 OMEN / Asus V16), compattare i prompt e gli output tool per non provocare OOM.",
            "- **Hermes Shadow Memory**: su nodi Windows privi di runtime nativo `hermes-agent`, il bridge `hermes_memory_bridge.py` deve girare in modalità Shadow (porta 8098 con SQLite FTS5).",
            "- **Salvaguardia Batteria Laptop**: su nodi AC operativi 24/7, mantenere abilitato il limite di carica all'80% nel BIOS/OMEN Hub e sollevare il telaio di 3-5 cm.",
            "",
        ])

        self.calendar_path.parent.mkdir(parents=True, exist_ok=True)
        self.calendar_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return self.calendar_path


def main():
    parser = argparse.ArgumentParser(description="Gestore del Diario e Calendario della Codebase")
    parser.add_argument("--record", action="store_true", help="Registra un nuovo evento")
    parser.add_argument("--agent", default="agent", help="Nome dell'agente")
    parser.add_argument("--intent", default="", help="Motivazione della modifica")
    parser.add_argument("--files", nargs="*", default=[], help="File toccati")
    parser.add_argument("--type", default="feature", help="Tipo di azione (feature, fix, refactor, hardening, test)")
    parser.add_argument("--tests", default="passed", help="Esito test")
    parser.add_argument("--lesson", default="", help="Lezione appresa")
    parser.add_argument("--list", action="store_true", help="Mostra timeline recente")
    parser.add_argument("--lessons", action="store_true", help="Mostra lezioni apprese")
    parser.add_argument("--query", default="", help="Termine di ricerca lezioni")
    args = parser.parse_args()

    journal = CodebaseJournal()

    if args.record and args.intent:
        entry = journal.record_mutation(
            agent=args.agent,
            intent=args.intent,
            files_touched=args.files,
            action_type=args.type,
            test_status=args.tests,
            lessons_learned=args.lesson,
        )
        print(f"✅ Registrata mutazione: {entry['id']} ({entry['intent']})")
    elif args.lessons:
        lessons = journal.query_lessons(query=args.query)
        print(f"Found {len(lessons)} lessons:")
        for l in lessons:
            print(f"- [{l['date']}] ({l['agent']}): {l['lessons_learned']} (Intent: {l['intent']})")
    else:
        entries = journal.get_timeline(limit=15)
        print("=" * 64)
        print(f" 📖 CODEBASE CHRONICLE TIMELINE ({len(entries)} eventi)")
        print("=" * 64)
        for e in entries:
            print(f" [{e['date']}] {e['agent']} ({e['action_type']}): {e['intent']}")
            if e.get("lessons_learned"):
                print(f"   💡 {e['lessons_learned']}")


if __name__ == "__main__":
    main()
