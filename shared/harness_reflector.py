#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# shared/harness_reflector.py
"""Harness Reflector: Recursive Agent Harnessing per HyperSpace AGI.

Ispirato a Google Research Harness² (Dual-Level Recursion):
1. Task-Level: estrae contrasti ed evidenze da esecuzioni, tool errors e fallimenti.
2. Harness-Level: accumula lezioni apprese in `data/harness_experience.jsonl` e
   propone automaticamente DRAFT INERTI nella Tool & Skill Forge (status: 'draft')
   per i componenti dell'Harness (system_prompt, guardrail, tool_guidance, skill, memory).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Union

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DEFAULT_FORGE_DIR = DATA_DIR / "control-plane" / "forge"
EXPERIENCE_LOG = DATA_DIR / "harness_experience.jsonl"
EXPERIENCE_MD = ROOT / "docs" / "harness-experience.md"

# Mappatura dei componenti Harness² sul tipo base di archiviazione Forge
HARNESS_BASE_TYPE_MAP = {
    "system_prompt": "skill",
    "guardrail": "skill",
    "memory": "skill",
    "tool_guidance": "skill",
    "subagent": "skill",
    "skill": "skill",
    "script": "tool",
    "plugin": "patch",
}


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(text: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", str(text).strip().lower()).strip("-")
    return clean[:48] or "artifact"


class HarnessReflector:
    def __init__(
        self,
        forge_dir: Optional[Path] = None,
        experience_path: Optional[Path] = None,
        experience_md_path: Optional[Path] = None,
    ):
        env_forge = os.getenv("FORGE_DIR")
        if forge_dir:
            self.forge_dir = Path(forge_dir)
        elif env_forge:
            self.forge_dir = Path(env_forge)
        elif DEFAULT_FORGE_DIR.exists():
            self.forge_dir = DEFAULT_FORGE_DIR
        else:
            self.forge_dir = DATA_DIR / "forge"

        self.experience_path = experience_path or EXPERIENCE_LOG
        self.experience_md_path = experience_md_path or EXPERIENCE_MD
        self.forge_dir.mkdir(parents=True, exist_ok=True)
        self.experience_path.parent.mkdir(parents=True, exist_ok=True)

    def write_draft_artifact(
        self,
        name: str,
        source: str,
        component: str,
        description: str,
        generator: str = "harness-reflector",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Crea un artefatto inerte (status: 'draft') nella cartella Forge."""
        component = component.lower()
        if component not in HARNESS_BASE_TYPE_MAP:
            component = "tool_guidance"

        base_type = HARNESS_BASE_TYPE_MAP[component]
        slug_name = _slug(name)
        short_hash = hashlib.sha256(f"{name}:{source}:{_now_iso()}".encode()).hexdigest()[:6]
        artifact_id = f"harness-{component.replace('_', '-')}-{slug_name}-{short_hash}"

        now = _now_iso()
        item: Dict[str, Any] = {
            "id": artifact_id,
            "name": name[:120],
            "type": base_type,
            "harness_component": component,
            "description": description[:1000],
            "source": source,
            "permissions": [],
            "status": "draft",
            "version": 1,
            "created_at": now,
            "updated_at": now,
            "validation": {
                "valid": True,
                "issues": [],
                "warnings": [],
            },
            "generator": generator,
            "metadata": metadata or {},
        }

        # Scrive il file JSON dell'artefatto
        json_path = self.forge_dir / f"{artifact_id}.json"
        tmp_json = self.forge_dir / f"{artifact_id}.json.tmp"
        with open(tmp_json, "w", encoding="utf-8") as f:
            json.dump(item, f, ensure_ascii=False, indent=2)

        # Scrive il sidecar (Markdown, Python o Diff)
        ext = ".py" if base_type == "tool" else (".diff" if base_type == "patch" else ".md")
        sidecar_path = self.forge_dir / f"{artifact_id}{ext}"
        tmp_sidecar = self.forge_dir / f"{artifact_id}{ext}.tmp"
        with open(tmp_sidecar, "w", encoding="utf-8") as f:
            f.write(source)

        os.replace(tmp_sidecar, sidecar_path)
        os.replace(tmp_json, json_path)
        return item

    def record_experience(
        self,
        event_type: str,
        target_component: str,
        lesson_learned: str,
        context: Dict[str, Any],
        draft_artifact_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Registra l'esperienza accumulata in `data/harness_experience.jsonl`."""
        entry = {
            "timestamp": _now_iso(),
            "event_type": event_type,
            "target_component": target_component,
            "lesson_learned": lesson_learned,
            "draft_artifact_id": draft_artifact_id or "",
            "context": context,
        }

        with open(self.experience_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self.sync_markdown_experience()
        return entry

    def reflect_on_mission(
        self,
        mission_or_id: Union[str, Dict[str, Any]],
        store: Any = None,
    ) -> Optional[Dict[str, Any]]:
        """Estrae riflessioni e contromisure da una missione di Mission Control."""
        mission: Optional[Dict[str, Any]] = None
        if isinstance(mission_or_id, dict):
            mission = mission_or_id
        elif store is not None:
            mission = store.get(str(mission_or_id))
        else:
            # Prova a leggere da data/missions.jsonl
            missions_file = DATA_DIR / "missions.jsonl"
            if missions_file.exists():
                with open(missions_file, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        try:
                            m = json.loads(line)
                            if m.get("id") == str(mission_or_id):
                                mission = m
                                break
                        except Exception:
                            continue

        if not mission:
            return None

        mission_id = mission.get("id", "unknown-mission")
        status = mission.get("status", "unknown")
        objective = mission.get("objective", "")
        error_msg = mission.get("error", "")
        tasks = mission.get("tasks", {})
        counters = mission.get("counters", {})

        # Identifica problemi nei task o errori nel verifier
        failed_tasks = []
        tool_issues = []
        for task_id, task in tasks.items():
            t_status = task.get("status")
            if t_status == "failed" or task.get("error"):
                failed_tasks.append((task_id, task))
            output = str(task.get("output", ""))
            error_field = str(task.get("error", ""))
            combined = f"{output} {error_field}"
            if any(term in combined.lower() for term in ("invalid parameter", "unexpected argument", "syntaxerror", "modulenotfounderror", "keyerror", "unknown tool")):
                tool_issues.append((task_id, task.get("role", "worker"), combined[:240]))

        # Determina il componente target e la lezione
        draft: Optional[Dict[str, Any]] = None
        if tool_issues:
            # Caso 1: Errore d'uso o sintassi dei Tool -> Tool Guidance
            task_id, role, issue_desc = tool_issues[0]
            name = f"Tool Guidance: Ripristino Parametri per Ruolo {role}"
            description = f"Guida generata automaticamente dopo l'errore riscontrato nella missione {mission_id} (task {task_id})."
            source = (
                f"---\n"
                f"name: tool-guidance-{_slug(role)}\n"
                f"harness_component: tool_guidance\n"
                f"source_mission: {mission_id}\n"
                f"---\n\n"
                f"# Linee Guida Invocazione Tool per {role}\n\n"
                f"## Contesto dell'Anomalia Riscontrata\n"
                f"Durante la missione `{mission_id}`, il task `{task_id}` ha restituito un'anomalia di invocazione:\n"
                f"```text\n{issue_desc}\n```\n\n"
                f"## Regole Obbligatorie per l'Invocazione\n"
                f"1. Ispezionare rigorosamente lo schema JSON dei parametri prima di invocare il tool.\n"
                f"2. Non passare argomenti inventati o deprecati.\n"
                f"3. In caso di errore sintattico, verificare che i tipi (string, int, array) corrispondano al manifest.\n"
                f"4. Riportare esplicitamente i tool non disponibili senza simularne l'output.\n"
            )
            draft = self.write_draft_artifact(
                name=name,
                source=source,
                component="tool_guidance",
                description=description,
                metadata={"mission_id": mission_id, "role": role, "issue": issue_desc},
            )
            self.record_experience(
                event_type="mission_tool_error",
                target_component="tool_guidance",
                lesson_learned=f"[{mission_id}] Correzione parametri tool per {role} dopo errore: {issue_desc[:80]}",
                context={"mission_id": mission_id, "task_id": task_id, "role": role},
                draft_artifact_id=draft["id"],
            )

        elif status == "failed" and "budget exhausted" in error_msg.lower():
            # Caso 2: Esaurimento budget o loop -> Guardrail
            name = f"Guardrail: Limiti e Prevenzione Budget Exhaustion"
            description = f"Guardrail di sicurezza per prevenire l'esaurimento del budget rilevato nella missione {mission_id}."
            source = (
                f"---\n"
                f"name: guardrail-budget-protection\n"
                f"harness_component: guardrail\n"
                f"source_mission: {mission_id}\n"
                f"---\n\n"
                f"# Guardrail di Sicurezza: Prevenzione Loop e Budget\n\n"
                f"## Vincolo Invalicabile (NEVER / MUST NOT)\n"
                f"- L'agente **NON DEVE** reiterare il medesimo comando o piano se per due tentativi consecutivi l'output non avanza.\n"
                f"- **MAI** eseguire iterazioni a vuoto senza produrre un artefatto tangibile o una diagnosi strutturata.\n"
                f"- In caso di task bloccato, il verifier deve emettere un motivo esplicito e commutare su un piano alternativo.\n\n"
                f"## Metriche Rilevate\n"
                f"- Passi eseguiti: {counters.get('steps', 0)}\n"
                f"- Replan effettuati: {counters.get('replans', 0)}\n"
                f"- Tempo trascorso: {counters.get('elapsed_seconds', 0)}s\n"
            )
            draft = self.write_draft_artifact(
                name=name,
                source=source,
                component="guardrail",
                description=description,
                metadata={"mission_id": mission_id, "error": error_msg},
            )
            self.record_experience(
                event_type="mission_budget_exhaustion",
                target_component="guardrail",
                lesson_learned=f"Aggiunto guardrail anti-loop dopo esaurimento budget nella missione {mission_id}",
                context={"mission_id": mission_id, "counters": counters},
                draft_artifact_id=draft["id"],
            )

        elif status == "done" and len(tasks) >= 2:
            # Caso 3: Missione complessa conclusa con successo -> Skill riutilizzabile
            name = f"Skill: Workflow Verificato per {_slug(objective)[:32]}"
            description = f"Procedura operativa distillata con successo dalla missione {mission_id}."
            task_summary = "\n".join([f"- **Task `{tid}`** ({t.get('role')}): {t.get('description', '')}" for tid, t in tasks.items()])
            source = (
                f"---\n"
                f"name: skill-workflow-{_slug(objective)[:24]}\n"
                f"harness_component: skill\n"
                f"source_mission: {mission_id}\n"
                f"---\n\n"
                f"# Procedura Operativa: {objective}\n\n"
                f"## Obiettivo Validato\n"
                f"{objective}\n\n"
                f"## Fasi del DAG che hanno portato al successo\n"
                f"{task_summary}\n\n"
                f"## Criteri di Accettazione Soddisfatti\n"
                f"{mission.get('acceptance_criteria', 'N/D')}\n"
            )
            draft = self.write_draft_artifact(
                name=name,
                source=source,
                component="skill",
                description=description,
                metadata={"mission_id": mission_id, "objective": objective},
            )
            self.record_experience(
                event_type="mission_success_workflow",
                target_component="skill",
                lesson_learned=f"Distillata nuova skill riutilizzabile dalla missione completata {mission_id}",
                context={"mission_id": mission_id, "tasks_count": len(tasks)},
                draft_artifact_id=draft["id"],
            )

        return draft

    def reflect_on_dev_cycle(self, cycle_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Estrae riflessioni da un ciclo dev 24/7 (HP OMEN)."""
        tasks = cycle_data.get("tasks", {})
        qa = tasks.get("qa", {})
        distill = tasks.get("distillation", {})

        draft = None
        if qa and not qa.get("passed", True):
            # Regressione nei test -> Guardrail di regressione
            failed_tests = qa.get("output", "")[:300]
            name = "Guardrail: Prevenzione Regressione Test Suite"
            description = "Guardrail per prevenire la rottura degli invarianti rilevata dal ciclo QA notturno."
            source = (
                f"---\n"
                f"name: guardrail-qa-invariants\n"
                f"harness_component: guardrail\n"
                f"---\n\n"
                f"# Guardrail: Protezione Invarianti e Licensing\n\n"
                f"## Vincoli di Regressione\n"
                f"- **MAI** modificare i moduli core senza lanciare prima `pytest tests/test_licensing.py`.\n"
                f"- I file rimossi o rinominati non devono lasciare import orfani nella working tree.\n\n"
                f"## Ultimo Fallimento Tracciato\n"
                f"```text\n{failed_tests}\n```\n"
            )
            draft = self.write_draft_artifact(
                name=name,
                source=source,
                component="guardrail",
                description=description,
                metadata={"cycle_timestamp": cycle_data.get("timestamp")},
            )
            self.record_experience(
                event_type="devloop_qa_failure",
                target_component="guardrail",
                lesson_learned="Guardrail anti-regressione attivato dopo test QA falliti.",
                context={"qa": qa},
                draft_artifact_id=draft["id"],
            )
        return draft

    def sync_markdown_experience(self) -> None:
        """Rigenera il diario visuale `docs/harness-experience.md`."""
        if not self.experience_path.exists():
            return

        entries = []
        with open(self.experience_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        continue

        entries = list(reversed(entries[-100:]))

        md_content = [
            "# Diario delle Esperienze Harness² (Harness-Level Reflection)",
            "",
            "Questo registro sintetizza le **lezioni apprese** dagli agenti durante le missioni e i cicli autonomi.",
            "Ogni anomalia o successo viene analizzato per produrre **draft inerti** nella [Tool & Skill Forge](tool-skill-forge.md),",
            "evoluendo l'ambiente d'esecuzione (System Prompt, Guardrails, Tool Guidance, Skills, Memory) senza toccare i pesi dei modelli.",
            "",
            "| Data / Ora (UTC) | Evento | Componente Target | Lezione Appresa | Draft Forge Generato |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]

        for e in entries:
            ts = e.get("timestamp", "")[:19].replace("T", " ")
            ev = e.get("event_type", "")
            comp = f"`{e.get('target_component', '')}`"
            lesson = e.get("lesson_learned", "").replace("|", "/")[:120]
            draft_id = e.get("draft_artifact_id", "")
            draft_link = f"[{draft_id}](file:///Users/opo/hyperspace-agi-1.04/data/control-plane/forge/{draft_id}.json)" if draft_id else "-"
            md_content.append(f"| {ts} | `{ev}` | {comp} | {lesson} | {draft_link} |")

        md_content.append("")
        self.experience_md_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.experience_md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_content) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Harness Reflector CLI: estrazione lezioni e generazione draft Forge.")
    parser.add_argument("--mission", help="ID della missione su cui riflettere")
    parser.add_argument("--dev-cycle", action="store_true", help="Rifletti sull'ultimo ciclo dev di data/omen_dev_loop.jsonl")
    parser.add_argument("--sync-md", action="store_true", help="Sincronizza docs/harness-experience.md")
    parser.add_argument("--component", choices=list(HARNESS_BASE_TYPE_MAP.keys()), default="tool_guidance")
    parser.add_argument("--name", help="Nome per il draft manuale")
    parser.add_argument("--text", help="Testo o errore per creare un draft manuale")
    args = parser.parse_args()

    reflector = HarnessReflector()

    if args.sync_md:
        reflector.sync_markdown_experience()
        print(f"[OK] Sincronizzato {EXPERIENCE_MD}")
        return

    if args.mission:
        draft = reflector.reflect_on_mission(args.mission)
        if draft:
            print(f"[OK] Generato draft inerte: {draft['id']} ({draft['harness_component']})")
        else:
            print("[INFO] Nessun pattern azionabile o missione non trovata.")
        return

    if args.dev_cycle:
        log_path = DATA_DIR / "omen_dev_loop.jsonl"
        if not log_path.exists():
            print("[ERROR] data/omen_dev_loop.jsonl non trovato.")
            return
        with open(log_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        if not lines:
            print("[INFO] Nessun ciclo trovato.")
            return
        last_cycle = json.loads(lines[-1])
        draft = reflector.reflect_on_dev_cycle(last_cycle)
        if draft:
            print(f"[OK] Generato draft inerte: {draft['id']} ({draft['harness_component']})")
        else:
            print("[INFO] Ciclo nominale: nessuna anomalia da cui riflettere.")
        return

    if args.name and args.text:
        draft = reflector.write_draft_artifact(
            name=args.name,
            source=args.text,
            component=args.component,
            description="Draft creato manualmente via HarnessReflector CLI.",
        )
        reflector.record_experience(
            event_type="manual_reflection",
            target_component=args.component,
            lesson_learned=f"Draft manuale: {args.name}",
            context={},
            draft_artifact_id=draft["id"],
        )
        print(f"[OK] Generato draft inerte: {draft['id']} ({draft['harness_component']})")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
