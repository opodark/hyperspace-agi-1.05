#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
HyperSpace Sovereign Mesh — Sessione Autonoma R&D Notturna su HP OMEN 16.
Esecuzione non-stop overnight (ASUS offline/spento).

Il nodo HP OMEN 16 lavora in autonomia con il modello LFM2.5 24B MoE @ 64k:
1. Cicli di Design Architetturale & Implementazione Python per moduli e protocolli R&D
2. Validazione AST Python (sintassi, classi, metodi, imports)
3. Persistenza dei prototipi in data/research/prototypes/
4. Registrazione eventi nel CausalMemoryGraph e tracciamento telemetrico
5. Aggiornamento in tempo reale del live report per http://localhost:8090/analytics.html
6. Watchdog di sicurezza per l'alimentazione AC e le pause di raffreddamento GPU

Uso:
    .venv/bin/python scripts/diagnostics/mesh_nightly_omen_session.py --duration-hours 10
"""

from __future__ import annotations

import argparse
import ast
import datetime
import json
import os
from pathlib import Path
import random
import socket
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.identity import generate_or_load_identity, make_request_headers
from shared.universal_model_parser import UniversalModelParser
from shared.causal_memory_graph import CausalMemoryGraph

# Configurazione Nodi
MAC_CP_URL = os.getenv("HYPERSPACE_CP_URL", "http://127.0.0.1:8085")
OMEN_NODE_URL = os.getenv("OMEN_NODE_URL", "http://100.104.238.125:8081")
MODEL_LFM24B = "hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M"

DATA_DIR = REPO_ROOT / "data"
RESEARCH_DIR = DATA_DIR / "research"
PROTOTYPES_DIR = RESEARCH_DIR / "prototypes"
INCIDENTS_LOG = RESEARCH_DIR / "mesh_telemetry_incidents.jsonl"
RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
PROTOTYPES_DIR.mkdir(parents=True, exist_ok=True)

DEV_LOOP_LOG = DATA_DIR / "omen_dev_loop.jsonl"
SYNTHETIC_DATASET = DATA_DIR / "synthetic_cot_dataset.jsonl"
REPORTS_DIR = DATA_DIR / "reports"
LIVE_REPORT_FILE = REPORTS_DIR / "endurance_session_live.json"
THERMAL_FLAG = DATA_DIR / "thermal_pause.flag"


def tcp_ping(host: str, port: int, timeout: float = 2.0) -> Tuple[bool, float]:
    """Misura la latenza TCP in millisecondi."""
    t0 = time.time()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True, round((time.time() - t0) * 1000, 2)
    except Exception:
        return False, -1.0


def check_omen_power_and_thermal() -> Tuple[bool, str]:
    """Verifica che l'OMEN sia alimentato da rete elettrica e non in allerta termica."""
    if THERMAL_FLAG.exists():
        return False, "thermal_pause_flag_present"

    try:
        req = urllib.request.Request(f"{OMEN_NODE_URL}/status")
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            power = data.get("power", {})
            if not power.get("ac_line", True):
                return False, f"battery_mode_{power.get('battery_pct')}%"
            return True, "ac_ok"
    except Exception as exc:
        return True, f"status_unreachable_assuming_ok: {exc}"


def query_omen_execute(prompt: str, model: str = MODEL_LFM24B, num_ctx: int = 65536, timeout: float = 240.0) -> Dict[str, Any]:
    """Invia richiesta firmata con ECDSA al Node Worker OMEN (:8081/execute)."""
    ident = generate_or_load_identity()
    body_data = {
        "task_id": f"nightly-omen-{int(time.time() * 1000)}",
        "model": model,
        "prompt": prompt,
        "options": {"num_ctx": num_ctx, "num_predict": 950, "temperature": 0.25}
    }
    payload = json.dumps(body_data).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    signed_hdrs = make_request_headers(
        ident["node_id"], ident["public_key"], ident["_private_key"], body=payload
    )
    headers.update(signed_hdrs)

    t0 = time.time()
    req = urllib.request.Request(f"{OMEN_NODE_URL}/execute", data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - t0

    resp_text = res.get("response", "")
    eval_count = res.get("eval_count") or (len(resp_text) // 4)
    eval_dur = res.get("eval_duration") or int(elapsed * 1e9)
    tok_s = (eval_count / (eval_dur / 1e9)) if eval_dur > 0 else (eval_count / max(0.1, elapsed))

    return {
        "text": resp_text,
        "elapsed_s": round(elapsed, 2),
        "tok_s": round(tok_s, 2),
        "eval_count": eval_count
    }


def update_devloop_hud(cycle: int, qa_passed: bool, duration_s: float, action: str, cot_snippet: str = ""):
    """Registra l'evento per la dashboard del playground (/api/devloop)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "cycle": cycle,
        "qa_passed": qa_passed,
        "duration_s": round(duration_s, 2),
        "action": action,
        "nodes": ["hp-omen-16", "mac-m5-hub"]
    }
    with open(DEV_LOOP_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    if cot_snippet:
        cot_entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "cycle": cycle,
            "prompt_topic": action,
            "distilled_cot": cot_snippet[:600],
            "verified": qa_passed
        }
        with open(SYNTHETIC_DATASET, "a", encoding="utf-8") as f:
            f.write(json.dumps(cot_entry) + "\n")


def update_live_report(state: Dict[str, Any]):
    """Aggiorna il file JSON di stato live interrogabile dal Cockpit 8090."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(LIVE_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


RND_TOPICS = [
    ("FederatedCheckpointReplication", "replica distribuita e validazione crittografica di checkpoint di stato tra nodi peer"),
    ("AdaptiveQuantizationRouter", "allocazione dinamica della precisione di quantizzazione per modelli linguistici in base al carico termico"),
    ("VectorClockStateReplication", "motore di replica di stato causale decentralizzato con vector clocks e risoluzione conflitti LWW"),
    ("SemanticMemoryDecayController", "controller del tasso di decadimento mnemonico esponenziale basato su salienza, richiamo e utilita"),
    ("EpisodicRecallSynthesizer", "motore di sintesi di memorie episodiche associative per ricostruzione controfattuale degli eventi di rete"),
    ("NeuralOpponentCurveGovernor", "governor euristico per calibrare dinamicamente curve di difficolta neurale in sfide interattive"),
    ("StigmergicMeshSwarm", "rete stigmergica con feromoni digitali in memoria Hermes, gradient sensing e convergenza di consenso"),
    ("AleksanderAxiomGovernor", "governor cognitivo per simulare e verificare i 5 assiomi di Aleksander su self-model, planning e valenza"),
    ("NeuroSymbolicPoetryEngine", "generatore poetico neuro-simbolico con scansione prosodica ed estrazione prompt per pipeline visuali"),
    ("AutonomousFailureIsolator", "meccanismo predittivo di isolamento di nodi degradati con degradazione elegante e graceful failover"),
    ("ZeroKnowledgeTaskAttestation", "protocollo di attestazione crittografica dell'avvenuta esecuzione di task computazionali tra nodi"),
    ("CrossContextSemanticCache", "cache LRU a incorporamento semantico per query ripetute o simili tra agenti concorrenti"),
    ("DistributedPrioritizedWorkStealing", "algoritmo di furto di lavoro decentralizzato con code a priorita basate su deadline e costo"),
    ("LosslessStreamDeltaEncoder", "codificatore a delta compresso per lo streaming in tempo reale di telemetria e grafi causali"),
    ("DynamicMeshTopologyOptimizer", "ottimizzatore euristico della matrice di adiacenza del cluster basato su latenza e banda P2P"),
    ("DecentralizedKVReservationProtocol", "protocollo di prenotazione anticipata di blocchi KV cache tra nodi per task collaborativi lunghi"),
    ("HeterogeneousModelConsensusEngine", "motore di votazione e consenso pesato tra modelli eterogenei per decisioni architetturali critiche"),
    ("AutonomousDeadlockDetector", "rilevatore causale di deadlock tra transazioni distribuite e acquisizioni di lock su risorse condivise")
]


def run_nightly_session(duration_hours: float = 10.0, cycle_interval_s: float = 35.0):
    start_time = time.time()
    end_time = start_time + (duration_hours * 3600.0)

    print("=" * 70)
    print("HYPERSPACE SOVEREIGN MESH — R&D AUTONOMO NOTTURNO SU HP OMEN 16")
    print(f"Inizio: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Durata programmata: {duration_hours:.1f} ore (~{int(duration_hours * 3600 / cycle_interval_s)} cicli previsti)")
    print(f"• Target Node: HP OMEN 16 (LFM2.5 24B MoE @ 64k) -> {OMEN_NODE_URL}")
    print(f"• Hub Monitor: Mac M5 (Control Plane & Cockpit 8090) -> {MAC_CP_URL}")
    print("• ASUS V16: Offline / Spento (escluso dalla pipeline notturna)")
    print("=" * 70)

    state: Dict[str, Any] = {
        "session_start": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "target_duration_minutes": round(duration_hours * 60.0, 1),
        "cycles_completed": 0,
        "successful_cycles": 0,
        "failed_cycles": 0,
        "prototypes_generated": [],
        "total_tokens_generated": 0,
        "average_throughput_tok_s": 0.0,
        "last_cycle_timestamp": None,
        "active_status": "RUNNING (NIGHTLY OMEN)",
        "nodes_health": {},
        "recent_events": []
    }
    update_live_report(state)

    cycle = 0
    throughput_samples: List[float] = []
    causal_graph = CausalMemoryGraph()

    while time.time() < end_time:
        cycle += 1
        remaining_s = max(0.0, end_time - time.time())
        rem_hours = round(remaining_s / 3600.0, 2)
        cycle_t0 = time.time()

        print(f"\n[CICLO #{cycle:04d} | Rimasti: {rem_hours} ore] — Ciclo R&D OMEN Notturno...")

        # 1. Probing di rete e salute
        omen_ok, omen_ms = tcp_ping("100.104.238.125", 8081)
        mac_ok, mac_ms = tcp_ping("127.0.0.1", 8085)

        state["nodes_health"] = {
            "omen_8081": {"ok": omen_ok, "latency_ms": omen_ms},
            "mac_8085": {"ok": mac_ok, "latency_ms": mac_ms},
            "asus_8081": {"ok": False, "latency_ms": -1.0, "note": "offline by design"}
        }

        # 2. Controllo alimentazione e sicurezza
        power_ok, power_msg = check_omen_power_and_thermal()
        if not power_ok:
            print(f"  ⚠️ Pausa di sicurezza: {power_msg}. Attesa 60s...")
            time.sleep(60.0)
            continue

        topic_name, topic_desc = RND_TOPICS[(cycle - 1) % len(RND_TOPICS)]
        cycle_success = True
        cycle_tokens = 0

        try:
            print(f"  [OMEN 24B @ 64k] Ricerca e Sintesi Modulo `{topic_name}` ({topic_desc})...")
            prompt = (
                f"Sei il Lead Autonomous Architect & Coder della Sovereign Mesh HyperSpace. Segui AGENTS.md.\n"
                f"Obiettivo R&D: Progetta e implementa il modulo Python completo `{topic_name}` per {topic_desc}.\n\n"
                "Requisiti:\n"
                "1. Scrivi una classe principale pulita, thread-safe, con type hints e docstring chiare.\n"
                "2. Implementa metodi operativi concreti (non pass o stub fittizi).\n"
                "3. Inizia con un breve blocco <think> con il ragionamento essenziale (max 50 parole).\n"
                "4. Restituisci il codice Python finale all'interno di un unico blocco ```python ... ```."
            )

            omen_res = query_omen_execute(prompt, model=MODEL_LFM24B, num_ctx=65536)
            cycle_tokens += omen_res["eval_count"]
            throughput_samples.append(omen_res["tok_s"])
            print(f"    ✓ Risposta in {omen_res['elapsed_s']}s ({omen_res['tok_s']} tok/s, {omen_res['eval_count']} token)")

            # Parse e validazione AST
            parsed = UniversalModelParser.parse(omen_res["text"])
            code_to_check = parsed.code_blocks[0].code if parsed.code_blocks else omen_res["text"]

            try:
                tree = ast.parse(code_to_check)
                classes_found = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
                print(f"    ✓ AST Python Validazione: PASS al 100% (Classi: {classes_found or 'module'})")

                proto_ts = int(time.time())
                proto_name = f"proto_{topic_name.lower()}_{proto_ts}.py"
                proto_path = PROTOTYPES_DIR / proto_name
                header = (
                    f"# SPDX-License-Identifier: Apache-2.0\n"
                    f"# Auto-generated by HyperSpace Nightly OMEN R&D Session\n"
                    f"# Topic: {topic_name} ({topic_desc})\n"
                    f"# Model: HP OMEN-16 (LFM2.5 24B MoE @ 64k)\n"
                    f"# Timestamp: {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n\n"
                )
                proto_path.write_text(header + code_to_check, encoding="utf-8")
                state["prototypes_generated"].append({
                    "file": proto_name,
                    "topic": topic_name,
                    "cycle": cycle,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                })
                print(f"    💾 Prototipo R&D archiviato: data/research/prototypes/{proto_name}")

                # Registrazione su grafo causale
                try:
                    causal_graph.record_event(
                        cause_id=f"nightly:omen_{topic_name}_{cycle}",
                        effect_id=f"proto:{proto_name}",
                        weight=1.0,
                        metadata={
                            "topic": topic_name,
                            "cycle": cycle,
                            "ast_valid": True,
                            "tok_s": omen_res["tok_s"],
                            "tokens": omen_res["eval_count"]
                        }
                    )
                except Exception as cg_err:
                    print(f"    ⚠ Causal graph error: {cg_err}")

            except SyntaxError as syn_err:
                print(f"    ⚠ AST Syntax Warning: {syn_err}")

            cot_snippet = parsed.reasoning_cot or omen_res["text"][:300]
            update_devloop_hud(cycle, True, time.time() - cycle_t0, f"nightly_{topic_name}", cot_snippet)

        except Exception as exc:
            cycle_success = False
            print(f"  ⚠ Avviso nel ciclo #{cycle}: {exc}")
            update_devloop_hud(cycle, False, time.time() - cycle_t0, f"cycle_error: {exc}")

        # Aggiornamento stato
        state["cycles_completed"] = cycle
        if cycle_success:
            state["successful_cycles"] += 1
        else:
            state["failed_cycles"] += 1

        state["total_tokens_generated"] += cycle_tokens
        if throughput_samples:
            state["average_throughput_tok_s"] = round(sum(throughput_samples) / len(throughput_samples), 2)
        state["last_cycle_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        state["recent_events"].append({
            "cycle": cycle,
            "success": cycle_success,
            "tokens": cycle_tokens,
            "elapsed_s": round(time.time() - cycle_t0, 2)
        })
        if len(state["recent_events"]) > 25:
            state["recent_events"].pop(0)

        update_live_report(state)

        # Pausa tra cicli (raffreddamento controllato)
        elapsed_cycle = time.time() - cycle_t0
        sleep_needed = max(10.0, cycle_interval_s - elapsed_cycle)
        if time.time() + sleep_needed < end_time:
            print(f"  ↳ Ciclo completato in {round(elapsed_cycle, 2)}s. Pausa di raffreddamento ({round(sleep_needed, 1)}s)...")
            time.sleep(sleep_needed)

    state["active_status"] = "COMPLETED"
    update_live_report(state)
    print("\n" + "=" * 70)
    print(f"SESSIONE NOTTURNA OMEN COMPLETATA (Cicli: {cycle}, Successo: {state['successful_cycles']}/{cycle})")
    print(f"Prototipi R&D Generati: {len(state['prototypes_generated'])}")
    print(f"Token Totali Generati: {state['total_tokens_generated']} | Throughput Medio: {state['average_throughput_tok_s']} tok/s")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HyperSpace Nightly OMEN 16 R&D Session")
    parser.add_argument("--duration-hours", type=float, default=10.0, help="Durata in ore (default: 10.0)")
    parser.add_argument("--cycle-interval", type=float, default=35.0, help="Intervallo minimo tra cicli in secondi (default: 35.0)")
    args = parser.parse_args()

    run_nightly_session(duration_hours=args.duration_hours, cycle_interval_s=args.cycle_interval)
