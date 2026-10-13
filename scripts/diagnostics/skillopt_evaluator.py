#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Valutatore offline e Validation Gate per skill Forge (Pattern SkillOpt).

Analizza documenti skill Markdown destinati a HyperSpace Forge, verifica i
limiti architetturali (dimensione UTF-8 <= 24.000 byte, SHA-256, frontmatter),
ispeziona la conformità di sicurezza (assenza di token o percorsi assoluti host)
e applica un Validation Gate deterministico per prevenire regressioni.

Esempi:
  # Verifica una skill con report sintetico
  python scripts/diagnostics/skillopt_evaluator.py docs/skills/pdf-mission-coder-skill.md

  # Confronto A/B tra baseline e candidata ottimizzata
  python scripts/diagnostics/skillopt_evaluator.py candidata.md --compare baseline.md

  # Esporta in formato JSON bozza inerte per Tool & Skill Forge
  python scripts/diagnostics/skillopt_evaluator.py docs/skills/pdf-mission-coder-skill.md --export-forge-draft
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

FORGE_MAX_BYTES = 24_000

SECRET_PATTERNS = [
    re.compile(r"(?:bearer|token|apikey|api_key|password|secret)[\s:=]+['\"]?([a-zA-Z0-9_\-\.]{16,})['\"]?", re.IGNORECASE),
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),
]

FORBIDDEN_PATH_PATTERNS = [
    re.compile(r"/(?:Users|home)/[a-zA-Z0-9_\-]+", re.IGNORECASE),
    re.compile(r"[A-Z]:\\[a-zA-Z0-9_\-]+", re.IGNORECASE),
]


def compute_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_frontmatter(content: str) -> Tuple[Dict[str, str], str]:
    """Estrae frontmatter YAML delimitato da --- e corpo markdown."""
    frontmatter: Dict[str, str] = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            raw_meta = parts[1].strip()
            body = parts[2].strip()
            for line in raw_meta.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    key, val = line.split(":", 1)
                    frontmatter[key.strip()] = val.strip().strip("'\"")
    return frontmatter, body


def scan_safety(content: str) -> List[str]:
    """Verifica assenza di segreti cablati e percorsi host non sicuri."""
    issues = []
    for pattern in SECRET_PATTERNS:
        match = pattern.search(content)
        if match:
            issues.append(f"Possibile credenziale o token rilevato nel testo: '{match.group(0)[:15]}...'")
    for pattern in FORBIDDEN_PATH_PATTERNS:
        match = pattern.search(content)
        if match:
            issues.append(f"Percorso host assoluto non consentito trovato: '{match.group(0)}'")
    return issues


def evaluate_skill_gate(content: str, frontmatter: Dict[str, str]) -> Dict[str, Any]:
    """Applica il Validation Gate deterministico su parametri operativi."""
    checks: List[Dict[str, Any]] = []
    score = 0.0

    # 1. Metadati essenziali
    has_name = bool(frontmatter.get("name"))
    has_desc = bool(frontmatter.get("description"))
    checks.append({
        "check": "Frontmatter name & description",
        "passed": has_name and has_desc,
        "detail": f"name='{frontmatter.get('name', '')}', desc len={len(frontmatter.get('description', ''))}"
    })
    if has_name and has_desc:
        score += 20.0

    # 2. Dimensione entro il budget Forge
    byte_len = len(content.encode("utf-8"))
    under_budget = byte_len <= FORGE_MAX_BYTES
    checks.append({
        "check": f"Budget dimensione Forge (<= {FORGE_MAX_BYTES} bytes)",
        "passed": under_budget,
        "detail": f"Dimensione reale: {byte_len} bytes ({byte_len / FORGE_MAX_BYTES * 100:.1f}%)"
    })
    if under_budget:
        score += 20.0

    # 3. Sicurezza (zero leak e zero path host)
    safety_issues = scan_safety(content)
    safety_passed = len(safety_issues) == 0
    checks.append({
        "check": "Sicurezza statica (zero token, zero path host assoluti)",
        "passed": safety_passed,
        "detail": "Nessuna anomalia rilevata" if safety_passed else "; ".join(safety_issues)
    })
    if safety_passed:
        score += 20.0

    # 4. Vincoli procedurali e tool guidance
    has_relative_path_rule = any(w in content.lower() for w in ("relativi", "relative path", "percorsi relativi"))
    has_budget_or_step_rule = any(w in content.lower() for w in ("budget", "passo", "step", "limita"))
    checks.append({
        "check": "Vincoli operativi espliciti (path relativi & budget iterazioni)",
        "passed": has_relative_path_rule and has_budget_or_step_rule,
        "detail": f"relative_path={has_relative_path_rule}, budget/step={has_budget_or_step_rule}"
    })
    if has_relative_path_rule:
        score += 10.0
    if has_budget_or_step_rule:
        score += 10.0

    # 5. Gate di autoverifica deterministica dell'artefatto
    has_artifact_check = any(w in content.lower() for w in ("assert", "gate", "verifica", "exit code", "gate_verified"))
    checks.append({
        "check": "Gate di verifica deterministica dell'artefatto/output",
        "passed": has_artifact_check,
        "detail": f"presenza clausola di verifica: {has_artifact_check}"
    })
    if has_artifact_check:
        score += 20.0

    all_passed = all(c["passed"] for c in checks)
    return {
        "score": score,
        "passed": all_passed,
        "checks": checks,
        "byte_len": byte_len,
        "sha256": compute_sha256(content),
    }


def format_forge_draft(path: Path, content: str, frontmatter: Dict[str, str]) -> Dict[str, Any]:
    """Genera payload JSON pronto per POST /forge/artifacts."""
    name = frontmatter.get("name") or path.stem
    desc = frontmatter.get("description") or f"Skill ottimizzata da {path.name}"
    artifact_id = f"skill-{re.sub(r'[^a-zA-Z0-9_\-]', '-', name.lower())}-{compute_sha256(content)[:8]}"
    return {
        "id": artifact_id,
        "name": name,
        "type": "skill",
        "description": desc,
        "source": content,
        "generator": "skillopt-evaluator",
        "permissions": [],
        "provenance": {
            "source_file": str(path.name),
            "sha256": compute_sha256(content),
            "byte_size": len(content.encode("utf-8")),
            "license": "Apache-2.0"
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", type=Path, help="Percorso del file Markdown della skill")
    parser.add_argument("--compare", type=Path, default=None, help="File Markdown baseline con cui confrontare")
    parser.add_argument("--export-forge-draft", action="store_true", help="Stampa JSON compatibile con l'API Forge")
    parser.add_argument("--json", action="store_true", help="Output diagnostico completo in formato JSON")
    args = parser.parse_args()

    if not args.file.exists():
        print(f"ERRORE: File non trovato: {args.file}", file=sys.stderr)
        return 1

    content = args.file.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(content)
    result = evaluate_skill_gate(content, meta)

    if args.export_forge_draft:
        draft = format_forge_draft(args.file, content, meta)
        print(json.dumps(draft, indent=2, ensure_ascii=False))
        return 0

    if args.compare:
        if not args.compare.exists():
            print(f"ERRORE: Baseline non trovata: {args.compare}", file=sys.stderr)
            return 1
        base_content = args.compare.read_text(encoding="utf-8")
        base_meta, _ = parse_frontmatter(base_content)
        base_result = evaluate_skill_gate(base_content, base_meta)

        diff_score = result["score"] - base_result["score"]
        accepted = result["passed"] and (diff_score > 0 or (diff_score == 0 and result["byte_len"] < base_result["byte_len"]))

        if args.json:
            print(json.dumps({
                "candidate": {"file": str(args.file), "result": result},
                "baseline": {"file": str(args.compare), "result": base_result},
                "diff_score": diff_score,
                "validation_verdict": "ACCEPT" if accepted else "REJECT"
            }, indent=2))
        else:
            print(f"=== VALIDATION GATE COMPARISON (SkillOpt) ===")
            print(f"Candidata : {args.file.name} (Score: {result['score']}/100, Bytes: {result['byte_len']})")
            print(f"Baseline  : {args.compare.name} (Score: {base_result['score']}/100, Bytes: {base_result['byte_len']})")
            print(f"Delta     : {'+' if diff_score > 0 else ''}{diff_score} punti")
            print(f"Verdetto  : {'✅ ACCEPT (Candidata promossa)' if accepted else '❌ REJECT (Parità o regressione)'}")
        return 0 if accepted else 2

    if args.json:
        print(json.dumps({
            "file": str(args.file),
            "frontmatter": meta,
            "gate_result": result
        }, indent=2))
        return 0 if result["passed"] else 1

    print(f"=== ISPEZIONE FORGE SKILL: {args.file.name} ===")
    print(f"SHA-256   : {result['sha256']}")
    print(f"Dimensione: {result['byte_len']} byte (max Forge: {FORGE_MAX_BYTES})")
    print(f"Punteggio : {result['score']}/100")
    print("\nControlli del Validation Gate:")
    for c in result["checks"]:
        icon = "  [✓]" if c["passed"] else "  [✗]"
        print(f"{icon} {c['check']}: {c['detail']}")

    if result["passed"]:
        print(f"\nEsito: ✅ CONFORME. La skill soddisfa i criteri del Validation Gate.")
        return 0
    else:
        print(f"\nEsito: ❌ NON CONFORME. Correggere le violazioni evidenziate prima dell'approvazione.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
