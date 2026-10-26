#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Strumento di Promozione Automatizzata dei Prototipi di Ricerca Sovrana HyperSpace AGI.

Gestisce la transizione sicura da prototipo R&D (data/research/prototypes/) a modulo
di produzione (shared/) con:
1. Validazione AST preventiva obbligatoria (fail-closed su errori sintattici).
2. Backup atomico con timestamp (.bak) del modulo esistente in shared/.
3. Iniezione degli header sovrani Apache-2.0 e metadati di tracciabilità.
4. Verifica compilazione Python a caldo (`compile(..., "exec")`).
5. Esecuzione suite Pytest di verifica automatica post-deploy con ROLLBACK istantaneo
   in caso di regressione o test falliti.
6. Registrazione permanente in data/research/promotions.jsonl e aggiornamento dell'albero
   genealogico in data/research/research_tree.json.

Uso:
  python scripts/diagnostics/promote_research_prototype.py --list
  python scripts/diagnostics/promote_research_prototype.py --auto-recommended
  python scripts/diagnostics/promote_research_prototype.py --prototype proto_aleksander_axioms_1792931402.py --target synthetic_consciousness_governor.py
"""
from __future__ import annotations

import argparse
import datetime
import difflib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.research_tree import ASTInspector, ResearchTreeManager

PROTOTYPES_DIR = ROOT / "data" / "research" / "prototypes"
SHARED_DIR = ROOT / "shared"
PROMOTIONS_FILE = ROOT / "data" / "research" / "promotions.jsonl"
TREE_FILE = ROOT / "data" / "research" / "research_tree.json"

# Candidati raccomandati per la produzione
RECOMMENDED_PROMOTIONS = [
    {
        "prototype": "proto_aleksander_axioms_1792931402.py",
        "target": "synthetic_consciousness_governor.py",
        "pillar": "aleksander_axioms",
        "description": "Upgrade modulare: DreamEngine, TaskScheduler RFC-0043, CheckpointManager RFC-0044 e misurazione 5 assiomi Aleksander con piena retrocompatibilità.",
    },
    {
        "prototype": "proto_symbolic_causal_mesh_1792927875.py",
        "target": "causal_memory_graph.py",
        "pillar": "symbolic_causal_mesh",
        "description": "Integrazione SQLite WAL + indicizzazione full-text FTS5 e risalita lineage multi-hop per root-cause analysis degli agenti.",
    },
    {
        "prototype": "proto_modular_intellect_1793002957.py",
        "target": "modular_intellect.py",
        "pillar": "modular_intellect",
        "description": "Memoria tri-modale (documenti, interazioni, note ricorsive), BFS graph traversal e Alignment Auditor deontologico.",
    },
    {
        "prototype": "proto_vectorclockstatereplication_1793010377.py",
        "target": "vector_clock_replication.py",
        "pillar": "symbolic_causal_mesh",
        "description": "Motore di replica distribuito con Vector Clocks causali per nodi eterogenei e merge commutativo.",
    },
    {
        "prototype": "proto_semanticmemorydecaycontroller_1793010783.py",
        "target": "semantic_memory_decay.py",
        "pillar": "symbolic_causal_mesh",
        "description": "Decadimento mnemonico esponenziale basato su salienza e frequenza di richiamo per Hermes FTS5.",
    },
]


def run_pytest_verification() -> Tuple[bool, str]:
    """Esegue la verifica dei test di regressione nel runtime del repository."""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_promoted_rd_modules.py",
        "tests/test_research_prototypes_validation.py",
        "tests/test_causal_memory_graph.py",
        "tests/test_causal_memory_modules.py",
        "-q",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
        )
        return (proc.returncode == 0, proc.stdout.strip())
    except Exception as exc:
        return (False, f"Errore esecuzione pytest: {exc}")


class PrototypePromoter:
    def __init__(self, author: str = "antigravity_sovereign"):
        self.author = author
        self.mgr = ResearchTreeManager()

    def list_candidates(self) -> List[Dict[str, Any]]:
        """Elenca i prototipi validi con dettagli AST e raccomandazioni di produzione."""
        protos = self.mgr.list_prototypes()
        candidates = []
        for p in protos:
            if not p.get("ast_valid"):
                continue
            is_rec = any(r["prototype"] == p["filename"] for r in RECOMMENDED_PROMOTIONS)
            candidates.append({
                "filename": p["filename"],
                "size_bytes": p["size_bytes"],
                "pillar_id": p["pillar_id"],
                "classes": p["classes"],
                "node_count": p["node_count"],
                "is_promoted": p["is_promoted"],
                "promoted_target": p.get("promoted_target"),
                "recommended": is_rec,
            })
        return candidates

    def promote_single(
        self,
        prototype_filename: str,
        target_name: str,
        verify_pytest: bool = True,
    ) -> Dict[str, Any]:
        """Promuove un prototipo in produzione con backup, deploy, test e rollback automatico."""
        proto_path = PROTOTYPES_DIR / prototype_filename
        if not proto_path.exists():
            return {"success": False, "error": f"Prototipo '{prototype_filename}' non trovato."}

        # 1. Ispezione AST
        ast_info = ASTInspector.inspect_file(proto_path)
        if not ast_info.get("valid"):
            return {
                "success": False,
                "error": f"AST Gate rifiutato: errore di sintassi nel prototipo ({ast_info.get('error')})",
            }

        safe_target = Path(target_name).name
        if not safe_target.endswith(".py"):
            safe_target += ".py"

        target_path = SHARED_DIR / safe_target
        backup_path = None
        backup_file = None

        # 2. Backup se il file di destinazione esiste già
        if target_path.exists():
            ts = int(time.time())
            backup_file = f"{safe_target}.{ts}.bak"
            backup_path = target_path.parent / backup_file
            shutil.copy2(target_path, backup_path)

        # 3. Composizione codice finale
        raw_source = proto_path.read_text(encoding="utf-8")
        clean_source = re.sub(r"^(#.*\n)+", "", raw_source).strip()

        header = (
            f"#!/usr/bin/env python3\n"
            f"# SPDX-License-Identifier: Apache-2.0\n"
            f"# shared/{safe_target}\n"
            f"# Modulo promosso in produzione da HyperSpace R&D Sovereign Lab\n"
            f"# Prototipo sorgente: {prototype_filename}\n"
            f"# Data promozione: {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n"
            f"# Autore: {self.author}\n\n"
        )
        final_code = header + clean_source + "\n"

        # 4. Verifica compilazione preventiva
        try:
            compile(final_code, str(target_path), "exec")
        except Exception as comp_err:
            if backup_path and backup_path.exists():
                backup_path.unlink()
            return {"success": False, "error": f"Errore compilazione pre-deploy: {comp_err}"}

        # 5. Scrittura su shared/
        target_path.write_text(final_code, encoding="utf-8")

        # 6. Verifica Pytest con Rollback Automatico
        if verify_pytest:
            passed, test_output = run_pytest_verification()
            if not passed:
                # Ripristina backup immediato
                if backup_path and backup_path.exists():
                    shutil.copy2(backup_path, target_path)
                    rollback_msg = "Ripristinato backup precedente."
                else:
                    target_path.unlink()
                    rollback_msg = "Rimosso file deployato (nessun backup precedente)."
                return {
                    "success": False,
                    "error": f"Verifica Pytest fallita. Eseguito ROLLBACK automatico: {rollback_msg}\nLog test:\n{test_output}",
                }

        # 7. Registrazione permanente in promotions.jsonl
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        record = {
            "timestamp": now_iso,
            "prototype_file": prototype_filename,
            "target_module": f"shared/{safe_target}",
            "author": self.author,
            "backup_file": backup_file,
            "classes_promoted": [c["name"] for c in ast_info.get("classes", [])],
            "functions_promoted": [fn["name"] for fn in ast_info.get("functions", [])],
            "node_count": ast_info.get("node_count", 0),
        }
        with open(PROMOTIONS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # 8. Aggiorna research_tree.json
        self._update_tree_after_promotion(prototype_filename, f"shared/{safe_target}")

        return {
            "success": True,
            "prototype": prototype_filename,
            "target": str(target_path),
            "backup_file": backup_file,
            "classes": record["classes_promoted"],
            "node_count": record["node_count"],
        }

    def _update_tree_after_promotion(self, prototype_filename: str, target_module: str):
        try:
            if not TREE_FILE.exists():
                return
            tree = json.loads(TREE_FILE.read_text(encoding="utf-8"))
            nodes = tree.get("nodes", [])
            for n in nodes:
                if n.get("prototype_file") == prototype_filename:
                    n["status"] = "production"
                    n["promoted"] = True
                    n["production_target"] = target_module
                    n["promoted_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            tree["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            TREE_FILE.write_text(json.dumps(tree, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", "-l", action="store_true", help="Elenca prototipi convalidati e candidati alla promozione")
    parser.add_argument("--auto-recommended", action="store_true", help="Promuove automaticamente i candidati raccomandati testati")
    parser.add_argument("--prototype", "-p", help="Nome file del prototipo da promuovere")
    parser.add_argument("--target", "-t", help="Nome del modulo di destinazione in shared/ (es. synthetic_consciousness_governor.py)")
    parser.add_argument("--skip-pytest", action="store_true", help="Salta la verifica Pytest post-deploy (sconsigliato)")
    args = parser.parse_args()

    promoter = PrototypePromoter()

    if args.list:
        candidates = promoter.list_candidates()
        print("=" * 70)
        print("  HYPERSPACE R&D — PROTOTIPI CONVALIDATI CANDIDATI ALLA PRODUZIONE")
        print("=" * 70)
        for c in candidates:
            rec_tag = " [RACCOMANDATO] ⭐" if c["recommended"] else ""
            prom_tag = f" (Già in shared/{c['promoted_target']})" if c["is_promoted"] else ""
            print(f"• {c['filename']} ({c['size_bytes']} bytes, {c['node_count']} nodi AST){rec_tag}{prom_tag}")
            print(f"  Pilone: {c['pillar_id']} | Classi: {', '.join(c['classes']) if c['classes'] else 'Nessuna'}")
        print("=" * 70)
        return 0

    if args.auto_recommended:
        print("=" * 70)
        print("  AVVIO PROMOZIONE AUTOMATIZZATA DEI PROTOTIPI RACCOMANDATI")
        print("=" * 70)
        all_ok = True
        for rec in RECOMMENDED_PROMOTIONS:
            print(f"\n▶ Promozione: {rec['prototype']} ➔ shared/{rec['target']}")
            print(f"  Razionale: {rec['description']}")
            res = promoter.promote_single(
                rec["prototype"],
                rec["target"],
                verify_pytest=not args.skip_pytest,
            )
            if res.get("success"):
                print(f"  ✅ SUCCESSO: Promosso con successo!")
                if res.get("backup_file"):
                    print(f"     Backup creato: {res['backup_file']}")
                print(f"     Classi: {', '.join(res.get('classes', []))}")
            else:
                print(f"  ❌ FALLITO: {res.get('error')}")
                all_ok = False

        print("\n" + "=" * 70)
        if all_ok:
            print("TUTTE LE PROMOZIONI RACCOMANDATE SONO ANDATE A BUON FINE! 🚀")
            return 0
        else:
            print("ATTENZIONE: ALCUNE PROMOZIONI NON SONO STATE COMPLETATE.")
            return 1

    if args.prototype and args.target:
        print(f"Promozione manuale: {args.prototype} ➔ shared/{args.target}")
        res = promoter.promote_single(args.prototype, args.target, verify_pytest=not args.skip_pytest)
        if res.get("success"):
            print(f"✅ Promosso con successo in {res['target']}")
            return 0
        else:
            print(f"❌ Errore durante la promozione: {res.get('error')}")
            return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
