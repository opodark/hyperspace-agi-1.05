#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# scripts/omen_dev_loop_247.py
"""Ciclo di Lavoro Continuo 24/7 per lo Sviluppo Autonomo su HP OMEN 16.

Questo worker cicla in background 24 ore su 24, 7 giorni su 7, eseguendo una serie
di task ad alto valore per lo sviluppo continuo dell'ecosistema HyperSpace AGI:

1. [QA & Invarianti] Esecuzione test veloci di regressione e licensing SPDX.
2. [Memoria Cognitiva] Consolidamento memorie Hermes e sogni sintetici su porta 8098.
3. [Knowledge Graph] Sincronizzazione incrementale Graphify AST se il codice è mutato.
4. [Distillazione Neurale] Generazione dataset CoT sintetici per fine-tuning (GPU RTX 3070).
5. [Diario Codebase] Registrazione delle metriche e delle lezioni apprese nel calendario.
6. [Guardia Termica] Pausa automatica di sicurezza se la GPU supera 82°C.

Uso:
    python scripts/omen_dev_loop_247.py --once
    python scripts/omen_dev_loop_247.py --daemon --interval 300
    python scripts/omen_dev_loop_247.py --task cot --cycles 5
"""

import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.codebase_journal import CodebaseJournal
from shared.harness_reflector import HarnessReflector
from shared.universal_model_parser import CavemanEngine, UniversalModelParser

DATA_DIR = ROOT / "data"
THERMAL_FLAG = DATA_DIR / "thermal_pause.flag"
SYNTHETIC_DATASET = DATA_DIR / "synthetic_cot_dataset.jsonl"
DEV_LOOP_LOG = DATA_DIR / "omen_dev_loop.jsonl"


def _log(tag: str, msg: str):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{tag}] {msg}")


def check_thermal_pause() -> bool:
    """Verifica se la macchina è in pausa termica per surriscaldamento."""
    if THERMAL_FLAG.exists():
        _log("THERMAL", "Allerta termica attiva: task di sviluppo pesante in pausa temporanea.")
        return True
    return False


# -----------------------------------------------------------------------------
# TASK 1: VERIFICA REGRESSIONI E INVARIANTI
# -----------------------------------------------------------------------------
def task_regression_check() -> Dict[str, Any]:
    _log("QA", "Esecuzione controlli rapidi invarianti e licensing...")
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_licensing.py",
        "tests/test_hermes_memory.py",
        "tests/test_codebase_journal.py",
        "tests/test_universal_model_parser.py",
        "-q",
    ]
    start = time.perf_counter()
    try:
        res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=60)
        elapsed = round(time.perf_counter() - start, 2)
        passed = "passed" in res.stdout and res.returncode == 0
        return {
            "task": "regression_check",
            "passed": passed,
            "elapsed_s": elapsed,
            "output": res.stdout.strip()[-150:] if res.stdout else res.stderr.strip()[-150:],
        }
    except Exception as e:
        return {"task": "regression_check", "passed": False, "error": str(e)}


# -----------------------------------------------------------------------------
# TASK 2: CONSOLIDAMENTO MEMORIA HERMES & SOGNI
# -----------------------------------------------------------------------------
def task_hermes_memory_consolidation(bridge_url: str = "http://127.0.0.1:8098") -> Dict[str, Any]:
    _log("HERMES", f"Controllo e consolidamento memoria su {bridge_url}...")
    token_file = DATA_DIR / "hermes-memory.token"
    token = token_file.read_text(encoding="utf-8").strip() if token_file.exists() else ""
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    try:
        r = requests.get(f"{bridge_url.rstrip('/')}/health", headers=headers, timeout=3)
        if r.status_code == 200:
            stats_r = requests.get(f"{bridge_url.rstrip('/')}/stats", headers=headers, timeout=3)
            stats = stats_r.json() if stats_r.status_code == 200 else {}
            return {"task": "hermes_memory", "online": True, "mode": r.json().get("mode", "unknown"), "stats": stats}
        return {"task": "hermes_memory", "online": False, "status_code": r.status_code}
    except Exception as e:
        return {"task": "hermes_memory", "online": False, "error": str(e)}


# -----------------------------------------------------------------------------
# TASK 2b: APPLICAZIONE PATCH MESH & DIGESTIONE PROTOCOLLO AGENTI
# -----------------------------------------------------------------------------
def task_apply_mesh_patches() -> Dict[str, Any]:
    """Scansiona e applica patch P2P arrivate via Git Mesh (/mesh/sync/patch)."""
    from shared.mesh_sync import apply_mesh_update

    patch_dirs = [
        DATA_DIR / "node-1" / "mesh-patches",
        DATA_DIR / "mesh-patches",
    ]
    applied_count = 0
    errors = []

    for p_dir in patch_dirs:
        if not p_dir.exists():
            continue
        for patch_file in p_dir.glob("*.json"):
            if patch_file.name.endswith(".result.json"):
                continue
            res_file = patch_file.with_name(f"{patch_file.stem}.result.json")
            if res_file.exists():
                continue

            try:
                raw = json.loads(patch_file.read_text(encoding="utf-8"))
                update_payload = raw.get("update", raw)
                res = apply_mesh_update(update_payload, repo_dir=str(ROOT))
                res_file.write_text(json.dumps(res, indent=2), encoding="utf-8")
                if res.get("success"):
                    applied_count += 1
                    _log("PATCH", f"Applicata patch mesh {patch_file.stem}: {len(res.get('applied_files', []))} file aggiornati.")
                else:
                    errors.extend(res.get("errors", []))
            except Exception as e:
                errors.append(f"Errore applicazione {patch_file.name}: {e}")

    return {"task": "apply_patches", "applied_count": applied_count, "errors": errors}


def task_digest_and_align(bridge_url: str = "http://127.0.0.1:8098") -> Dict[str, Any]:
    """Digerisce gli aggiornamenti di AGENT-LOG e Chronicle memorizzandoli in Hermes Shadow Memory."""
    _log("DIGEST", "Compressione e digestione protocollo agenti via Caveman Engine...")
    journal = CodebaseJournal()
    recent_mutations = journal.get_timeline(limit=5)
    if not recent_mutations:
        return {"task": "digest_align", "digested_count": 0, "reason": "nessuna mutazione trovata"}

    token_file = DATA_DIR / "hermes-memory.token"
    token = token_file.read_text(encoding="utf-8").strip() if token_file.exists() else ""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"} if token else {"Content-Type": "application/json"}

    digested = 0
    for m in recent_mutations:
        m_id = m.get("id", "mut-unknown")
        agent = m.get("agent", "AI")
        intent = m.get("intent", "")
        lessons = m.get("lessons_learned", "")
        text_raw = f"[{agent}] Intento: {intent}. Lezione: {lessons}"
        compressed = CavemanEngine.compress(text_raw)["compressed"]

        payload = {
            "entry": {
                "id": f"agent-digest-{m_id}",
                "text": compressed,
                "event_type": "decision",
                "source": "mesh-channel",
                "model": "lfm2.5-orchestrator",
                "status": "active",
                "tags": ["agent-protocol", "orchestration", agent.lower()]
            }
        }
        try:
            r = requests.post(f"{bridge_url.rstrip('/')}/store", json=payload, headers=headers, timeout=5)
            if r.status_code == 200:
                digested += 1
        except Exception:
            pass

    _log("DIGEST", f"Digestate ed allineate {digested} mutazioni in Hermes Memory.")
    return {"task": "digest_align", "digested_count": digested}


# -----------------------------------------------------------------------------
# TASK 3: KNOWLEDGE GRAPH REFRESH INCREMENTALE
# -----------------------------------------------------------------------------
def task_graphify_incremental() -> Dict[str, Any]:
    _log("GRAPHIFY", "Verifica freschezza Knowledge Graph...")
    graphify_script = ROOT / "scripts" / "graphify.sh"
    if not graphify_script.exists():
        return {"task": "graphify", "skipped": True}

    cmd = ["bash", str(graphify_script), "update", "."]
    start = time.perf_counter()
    try:
        res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=120)
        elapsed = round(time.perf_counter() - start, 2)
        return {"task": "graphify", "success": res.returncode == 0, "elapsed_s": elapsed}
    except Exception as e:
        return {"task": "graphify", "success": False, "error": str(e)}


# -----------------------------------------------------------------------------
# TASK 4: GENERAZIONE DATASET SINTETICI CoT & PoUW
# -----------------------------------------------------------------------------
DEV_TOPICS = [
    {
        "domain": "mesh_routing",
        "prompt": "Crea una funzione Python `route_task_by_vram(task_requirements, nodes_list)` che calcola lo score di idoneità in base alla VRAM libera e all'alimentazione AC/Batteria. Mostra prima il ragionamento CoT in <think>, poi restituisci il codice completo con type hinting."
    },
    {
        "domain": "memory_sync",
        "prompt": "Scrivi una classe `ShadowMemoryCache` in Python che salva le ultime N voci di memoria in un file JSON compresso gzip con scrittura atomica temporanea (.tmp -> rename). Mostra prima il ragionamento in <think> poi il codice."
    },
    {
        "domain": "security_tokens",
        "prompt": "Crea una funzione Python `sanitize_environment_output(env_dict, sensitive_keys)` che maschera token, password e chiavi API mostrando solo i primi 4 e ultimi 4 caratteri. Mostra il ragionamento in <think> poi il codice."
    },
    {
        "domain": "pouw_benchmark",
        "prompt": "Implementa un algoritmo Python `verify_pouw_work(nonce, target_difficulty, payload_hash)` che convalida la prova di calcolo utile restituendo True se l'hash soddisfa la difficoltà. Mostra prima <think> poi il codice."
    }
]


def task_synthetic_cot_distillation(node_url: str = "http://127.0.0.1:8081", cycles: int = 1) -> Dict[str, Any]:
    """Genera campioni sintetici ragionati <think> con validazione AST."""
    _log("DISTILL", f"Generazione {cycles} campioni sintetici CoT su {node_url}...")
    samples_created = 0

    for i in range(cycles):
        topic = DEV_TOPICS[i % len(DEV_TOPICS)]
        compressed = CavemanEngine.compress(topic["prompt"])["compressed"]

        payload = {
            "model": "hf.co/DuoNeural/LFM2.5-8B-A1B-Abliterated-GGUF:Q4_K_M",
            "prompt": compressed,
            "max_tokens": 1200,
            "temperature": 0.4,
        }

        try:
            r = requests.post(f"{node_url.rstrip('/')}/v1/chat/completions", json={
                "messages": [{"role": "user", "content": payload["prompt"]}],
                "max_tokens": payload["max_tokens"],
                "temperature": payload["temperature"],
            }, timeout=45)

            if r.status_code == 200:
                raw_response = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                parsed = UniversalModelParser.parse(raw_response)

                # Salva solo se c'è CoT e codice AST valido
                valid_code_blocks = [b.code for b in parsed.code_blocks if b.is_valid_ast]
                if valid_code_blocks:
                    dataset_entry = {
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "domain": topic["domain"],
                        "prompt": topic["prompt"],
                        "reasoning_cot": parsed.reasoning_cot,
                        "code": valid_code_blocks[0],
                        "ast_valid": True,
                    }
                    SYNTHETIC_DATASET.parent.mkdir(parents=True, exist_ok=True)
                    with open(SYNTHETIC_DATASET, "a", encoding="utf-8") as f:
                        f.write(json.dumps(dataset_entry, ensure_ascii=False) + "\n")
                    samples_created += 1
                    _log("DISTILL", f"Campione validato AST per dominio '{topic['domain']}' salvato in dataset.")
        except Exception as e:
            _log("DISTILL", f"Errore inferenza distillazione: {e}")

    return {"task": "cot_distillation", "samples_created": samples_created}


def task_harness_reflection(cycle_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Task 6: Riflessione Ricorsiva Harness² per auto-miglioramento continuo."""
    _log("HARNESS", "Valutazione riflessiva Harness² (Harness-Level Reflection)...")
    try:
        reflector = HarnessReflector()
        draft = reflector.reflect_on_dev_cycle(cycle_data or {})
        if draft:
            _log("HARNESS", f"Generato draft inerte Forge: {draft['id']} ({draft['harness_component']})")
            return {"task": "harness_reflection", "draft_generated": True, "draft_id": draft["id"], "component": draft["harness_component"]}
        return {"task": "harness_reflection", "draft_generated": False}
    except Exception as e:
        _log("HARNESS", f"Errore riflessione Harness: {e}")
        return {"task": "harness_reflection", "error": str(e)}


# -----------------------------------------------------------------------------
# MAIN CYCLE RUNNER
# -----------------------------------------------------------------------------
def run_dev_cycle(node_url: str, bridge_url: str, cycles_distill: int = 1) -> Dict[str, Any]:
    _log("CYCLE", "=== Avvio Ciclo Sviluppo 24/7 su HP OMEN ===")
    cycle_start = time.perf_counter()

    if check_thermal_pause():
        return {"status": "paused_thermal"}

    results: Dict[str, Any] = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "tasks": {},
    }

    # 1. QA & Invarianti
    results["tasks"]["qa"] = task_regression_check()

    # 2. Patch P2P Git Mesh & Digestione Protocollo Agenti
    results["tasks"]["apply_patches"] = task_apply_mesh_patches()
    results["tasks"]["digest_align"] = task_digest_and_align(bridge_url)

    # 3. Hermes Memory
    results["tasks"]["hermes"] = task_hermes_memory_consolidation(bridge_url)

    # 4. Knowledge Graph
    results["tasks"]["graphify"] = task_graphify_incremental()

    # 5. Distillazione CoT & PoUW
    results["tasks"]["distillation"] = task_synthetic_cot_distillation(node_url, cycles=cycles_distill)

    # 6. Riflessione Cognitiva Harness² (Self-Improvement Forge)
    results["tasks"]["harness_reflection"] = task_harness_reflection(results)

    results["elapsed_total_s"] = round(time.perf_counter() - cycle_start, 2)

    # Registra nel log locale
    DEV_LOOP_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(DEV_LOOP_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(results, ensure_ascii=False) + "\n")

    _log("CYCLE", f"Ciclo completato in {results['elapsed_total_s']}s.")
    return results


def main():
    parser = argparse.ArgumentParser(description="Worker di Sviluppo Continuo 24/7 per HP OMEN")
    parser.add_argument("--node-url", default="http://127.0.0.1:8081", help="URL del nodo OMEN")
    parser.add_argument("--bridge-url", default="http://127.0.0.1:8098", help="URL Hermes Bridge")
    parser.add_argument("--task", choices=["all", "qa", "hermes", "graphify", "cot", "digest", "patch", "reflection"], default="all")
    parser.add_argument("--cycles", type=int, default=1, help="Cicli CoT da distillare")
    parser.add_argument("--daemon", action="store_true", help="Esegui in loop continuo 24/7")
    parser.add_argument("--interval", type=int, default=300, help="Intervallo fra cicli in secondi (default: 300s / 5 min)")
    args = parser.parse_args()

    while True:
        if args.task == "all":
            run_dev_cycle(args.node_url, args.bridge_url, cycles_distill=args.cycles)
        elif args.task == "qa":
            print(json.dumps(task_regression_check(), indent=2))
        elif args.task == "patch":
            print(json.dumps(task_apply_mesh_patches(), indent=2))
        elif args.task == "digest":
            print(json.dumps(task_digest_and_align(args.bridge_url), indent=2))
        elif args.task == "hermes":
            print(json.dumps(task_hermes_memory_consolidation(args.bridge_url), indent=2))
        elif args.task == "graphify":
            print(json.dumps(task_graphify_incremental(), indent=2))
        elif args.task == "cot":
            print(json.dumps(task_synthetic_cot_distillation(args.node_url, cycles=args.cycles), indent=2))
        elif args.task == "reflection":
            print(json.dumps(task_harness_reflection(), indent=2))

        if args.daemon:
            _log("DAEMON", f"Attesa di {args.interval}s prima del prossimo ciclo...")
            time.sleep(args.interval)
        else:
            break


if __name__ == "__main__":
    main()
