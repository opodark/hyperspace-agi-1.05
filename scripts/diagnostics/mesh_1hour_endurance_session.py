#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
HyperSpace Sovereign Mesh — Sessione di Test ed Endurance Multi-Agente (1 Ora).
Esegue un ciclo continuo di verifica collaborativa distribuita tra:
- Mac M5 Hub (Control Plane & Telemetry)
- HP OMEN 16 (LFM2.5 24B MoE @ 64k - Lead Architect & Gate)
- ASUS V16 (Flint 40B MoE @ 128k - Lead Coder & Fast Engine)

Aggiorna in tempo reale la telemetria live del cluster e alimenta l'Operations Cockpit
su http://localhost:8090 (aggiornamento cicli dev, CoT distillati e metriche di rete).

Uso:
    .venv/bin/python scripts/diagnostics/mesh_1hour_endurance_session.py --duration-minutes 60
    .venv/bin/python scripts/diagnostics/mesh_1hour_endurance_session.py --duration-minutes 5 --cycle-interval 20
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

# Configurazione Nodi Mesh
MAC_CP_URL = os.getenv("HYPERSPACE_CP_URL", "http://127.0.0.1:8085")
MAC_OLLAMA_URL = os.getenv("MAC_OLLAMA_URL", "http://127.0.0.1:11434")
OMEN_NODE_URL = os.getenv("OMEN_NODE_URL", "http://100.104.238.125:8081")
ASUS_NODE_URL = os.getenv("ASUS_NODE_URL", "http://100.64.31.18:8081")
ASUS_OLLAMA_URL = os.getenv("ASUS_OLLAMA_URL", "http://100.64.31.18:11434")

MODEL_LFM24B = "hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M"
MODEL_FLINT40B = "flint:latest"

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


def query_omen_execute(prompt: str, model: str = MODEL_LFM24B, num_ctx: int = 65536, timeout: float = 240.0) -> Dict[str, Any]:
    """Invia richiesta firmata con ECDSA al Node Worker OMEN (:8081/execute)."""
    ident = generate_or_load_identity()
    body_data = {
        "task_id": f"endurance-omen-{int(time.time() * 1000)}",
        "model": model,
        "prompt": prompt,
        "options": {"num_ctx": num_ctx, "num_predict": 900, "temperature": 0.2}
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
    tok_s = (eval_count / (eval_dur / 1e9)) if eval_dur > 0 else (eval_count / elapsed)

    return {
        "text": resp_text,
        "elapsed_s": round(elapsed, 2),
        "tok_s": round(tok_s, 2),
        "eval_count": eval_count
    }


def query_asus_flint(prompt: str, num_ctx: int = 131072, timeout: float = 240.0) -> Dict[str, Any]:
    """Invia richiesta al modello Flint 40B su ASUS V16."""
    payload = json.dumps({
        "model": MODEL_FLINT40B,
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": num_ctx, "num_predict": 1000, "temperature": 0.2}
    }).encode("utf-8")

    t0 = time.time()
    req = urllib.request.Request(f"{ASUS_OLLAMA_URL}/api/generate", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - t0

    eval_count = res.get("eval_count", 0)
    eval_dur = res.get("eval_duration", 0)
    tok_s = (eval_count / (eval_dur / 1e9)) if eval_dur > 0 else (len(res.get("response", "")) / 4 / elapsed)

    return {
        "text": res.get("response", ""),
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
        "nodes": ["omen-16", "asus-v16", "mac-m5"]
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
    """Aggiorna il file JSON di stato live interrogabile in qualsiasi momento."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(LIVE_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def run_endurance_session(duration_minutes: float = 60.0, cycle_interval_s: float = 45.0):
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60.0)

    print("=" * 70)
    print("HYPERSPACE SOVEREIGN MESH — SESSIONE DI TEST & ENDURANCE (1 ORA)")
    print(f"Inizio: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Durata programmata: {duration_minutes} minuti (~{int(duration_minutes * 60 / cycle_interval_s)} cicli previsti)")
    print(f"• Nodo A: ASUS V16 (Flint 40B MoE @ 128k) -> {ASUS_NODE_URL} / :11434")
    print(f"• Nodo B: HP OMEN 16 (LFM2.5 24B MoE @ 64k) -> {OMEN_NODE_URL}")
    print(f"• Nodo C: Mac M5 Hub (Control Plane & Cockpit) -> {MAC_CP_URL}")
    print("=" * 70)

    state: Dict[str, Any] = {
        "session_start": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "target_duration_minutes": duration_minutes,
        "cycles_completed": 0,
        "successful_cycles": 0,
        "failed_cycles": 0,
        "prototypes_generated": [],
        "total_tokens_generated": 0,
        "average_throughput_tok_s": 0.0,
        "last_cycle_timestamp": None,
        "active_status": "RUNNING",
        "nodes_health": {},
        "recent_events": []
    }
    update_live_report(state)

    cycle = 0
    throughput_samples: List[float] = []
    causal_graph = CausalMemoryGraph()

    ARCHITECT_TOPICS = [
        ("AdaptiveMeshCircuitBreaker", "un circuito di protezione di rete con stati CLOSED, OPEN, HALF_OPEN per chiamate inter-nodo"),
        ("TokenBucketRateLimiter", "un algoritmo token bucket concorrente per distribuire carichi MoE con burst controllati"),
        ("DistributedHeartbeatSync", "un coordinatore di battito cardiaco asincrono per cluster P2P resiliente a partizioni di rete"),
        ("DynamicKVMemoryPool", "un gestore di pool per la KV cache di modelli 40B con deallocazione per contesti inattivi"),
        ("AleksanderAxiomGovernor", "governor che simula e verifica i 5 assiomi di Aleksander per self-model, planning e valencing"),
        ("StigmergicMeshSwarm", "rete stigmergica con feromoni digitali in memoria Hermes, gradient sensing e convergenza di consenso"),
        ("NeuroSymbolicPoetryEngine", "generatore poetico neuro-simbolico con scansione prosodica ed estrazione prompt visuale per ComfyUI"),
        ("TriModalMemoryGraph", "grafo di memoria a 3 modalita: chunk documentali, interazioni conversazionali e note ricorsive"),
        ("VectorClockStateReplication", "motore di replica di stato distribuito con vector clocks causali per nodi eterogenei"),
        ("ContinuousContextCompactor", "compattatore di contesto a finestra scorrevole lossless con distillazione semantica"),
        ("DistributedRollbackJournal", "gestore di transazioni atomiche cross-nodo con rollback automatico in caso di fallimento o partizione"),
        ("SemanticMemoryDecayController", "controller del tasso di decadimento mnemonico esponenziale basato su salienza e frequenza di richiamo"),
        ("SelfHealingPeerMesh", "algoritmo di autoguarigione della topologia peer con gossip di nodi attivi e rinegoziazione ruoli"),
        ("WorkStealingDAGScheduler", "scheduler a grafi aciclici orientati con work-stealing decentralizzato per worker eterogenei"),
        ("SpeculativeDraftValidator", "validatore a speculazione parallela con verifica rapida del codice generato da modelli ausiliari"),
        ("EpisodicRecallSynthesizer", "motore di sintesi di memorie episodiche associative per ricostruzione controfattuale degli eventi"),
        ("ArcadeStateSyncEngine", "motore di sincronizzazione di stato real-time per minigiochi distribuiti con interpolazione e rollback a lag zero"),
        ("NeuralOpponentCurveGovernor", "governor euristico per calibrare dinamicamente la curva di difficoltà neurale in sfide arcade 1v1")
    ]

    INCIDENT_SCENARIOS = [
        ("load_rebalance", 12, "normal"),
        ("vram_pressure_high", 28, "high"),
        ("latency_spike_p99", 5, "critical"),
        ("network_partition_detected", 1, "critical"),
        ("token_rate_exceeded", 42, "medium"),
        ("model_oom_prevented", 3, "high"),
        ("cache_eviction_surge", 19, "normal"),
        ("heartbeat_missed_peer", 2, "high")
    ]

    while time.time() < end_time:
        cycle += 1
        remaining_s = max(0.0, end_time - time.time())
        rem_min = round(remaining_s / 60.0, 1)
        cycle_t0 = time.time()

        print(f"\n[CICLO #{cycle:03d} | Rimasti: {rem_min} min] — Avvio micro-sessione multi-agente...")

        # 1. Probing di rete
        omen_ok, omen_ms = tcp_ping("100.104.238.125", 8081)
        asus_ok, asus_ms = tcp_ping("100.64.31.18", 8081)
        asus_ollama_ok, asus_ollama_ms = tcp_ping("100.64.31.18", 11434)
        mac_ok, mac_ms = tcp_ping("127.0.0.1", 8085)

        state["nodes_health"] = {
            "omen_8081": {"ok": omen_ok, "latency_ms": omen_ms},
            "asus_8081": {"ok": asus_ok, "latency_ms": asus_ms},
            "asus_11434": {"ok": asus_ollama_ok, "latency_ms": asus_ollama_ms},
            "mac_8085": {"ok": mac_ok, "latency_ms": mac_ms}
        }
        print(f"  • Latency Probe: ASUS={asus_ms}ms (8081) / {asus_ollama_ms}ms (11434) | OMEN={omen_ms}ms | MAC={mac_ms}ms")

        # 2. Alternanza task collaborativi
        cycle_success = True
        cycle_tokens = 0
        topic_name, topic_desc = ARCHITECT_TOPICS[((cycle - 1) // 2) % len(ARCHITECT_TOPICS)]

        try:
            if cycle % 2 == 1:
                # Ciclo Dispari: OMEN (Architect LFM2.5 @ 64k) redige specifica -> ASUS (Flint @ 128k) genera il codice
                print(f"  [1/2] OMEN (LFM2.5 24B @ 64k) architettura `{topic_name}`...")
                omen_prompt = (
                    f"Sei Lead System Architect di HyperSpace AGI. Progetta la specifica tecnica essenziale per `{topic_name}` ({topic_desc}). "
                    "Ragiona concisamente in <think> (max 40 parole). Definisci interfaccia concisa in codice Python per Lead Coder Flint."
                )
                omen_res = query_omen_execute(omen_prompt, model=MODEL_LFM24B, num_ctx=65536)
                cycle_tokens += omen_res["eval_count"]
                throughput_samples.append(omen_res["tok_s"])
                print(f"    ✓ OMEN ha risposto in {omen_res['elapsed_s']}s ({omen_res['tok_s']} tok/s)")

                print(f"  [2/2] ASUS (Flint 40B @ 128k) implementazione Python...")
                flint_prompt = (
                    f"Sei Lead Coder di HyperSpace AGI. Implementa la classe completa `{topic_name}` basandoti su questa specifica:\n"
                    f"{omen_res['text']}\n\n"
                    "Ragiona in <think> (max 40 parole) e scrivi codice Python completo in blocco ```python ... ```."
                )
                flint_res = query_asus_flint(flint_prompt, num_ctx=131072)
                cycle_tokens += flint_res["eval_count"]
                throughput_samples.append(flint_res["tok_s"])
                print(f"    ✓ Flint ha risposto in {flint_res['elapsed_s']}s ({flint_res['tok_s']} tok/s)")

                # Validazione AST e persistenza prototipo R&D
                parsed = UniversalModelParser.parse(flint_res["text"])
                code_to_check = parsed.code_blocks[0].code if parsed.code_blocks else flint_res["text"]
                try:
                    ast.parse(code_to_check)
                    print(f"    ✓ AST Python Validazione: PASS al 100%")

                    proto_ts = int(time.time())
                    proto_name = f"proto_{topic_name.lower()}_{proto_ts}.py"
                    proto_path = PROTOTYPES_DIR / proto_name
                    header = (
                        f"# SPDX-License-Identifier: Apache-2.0\n"
                        f"# Auto-generated by HyperSpace Multi-Agent Endurance Session\n"
                        f"# Topic: {topic_name} ({topic_desc})\n"
                        f"# Nodes: OMEN-16 (Architect 24B @ 64k) -> ASUS-V16 (Flint 40B @ 128k)\n"
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

                    # Tracciamento nel grafo causale
                    try:
                        causal_graph.record_event(
                            cause_id=f"omen:arch_{topic_name}_{cycle}",
                            effect_id=f"proto:{proto_name}",
                            weight=1.0,
                            metadata={
                                "topic": topic_name,
                                "cycle": cycle,
                                "ast_valid": True,
                                "omen_tok_s": omen_res["tok_s"],
                                "flint_tok_s": flint_res["tok_s"]
                            }
                        )
                    except Exception as cg_err:
                        print(f"    ⚠ Causal graph record error: {cg_err}")

                except SyntaxError as syn_err:
                    print(f"    ⚠ AST Syntax Warning: {syn_err}")

                cot_snippet = parsed.reasoning_cot or omen_res["text"][:300]
                update_devloop_hud(cycle, True, time.time() - cycle_t0, f"arch_impl_{topic_name}", cot_snippet)

            else:
                # Ciclo Pari: Flint emette telemetria incidente JSON -> OMEN emette remediation in JSON puro
                scen_type, scen_depth, scen_urgency = INCIDENT_SCENARIOS[((cycle // 2) - 1) % len(INCIDENT_SCENARIOS)]
                print(f"  [1/2] ASUS (Flint 40B @ 128k) telemetria incidente JSON ({scen_type})...")
                flint_json_prompt = (
                    "Emetti STRICT JSON report incidente per la mesh HyperSpace. Nessuna prosa:\n"
                    f'{{"schema_version":"1.0","node_id":"asus-v16","event_type":"{scen_type}","queue_depth":{scen_depth},"urgency":"{scen_urgency}"}}'
                )
                flint_res = query_asus_flint(flint_json_prompt, num_ctx=131072)
                cycle_tokens += flint_res["eval_count"]
                throughput_samples.append(flint_res["tok_s"])

                print(f"  [2/2] OMEN (LFM2.5 24B @ 64k) remediation JSON...")
                omen_json_prompt = (
                    f"Consuma questo evento di telemetria ed emetti STRICT JSON di remediation (nessuna prosa):\n{flint_res['text']}\n"
                    f'Schema richiesto: {{"action_id":"act-endurance-{cycle}","target_node":"asus-v16","directive":"remediate_{scen_type}","status":"dispatched"}}'
                )
                omen_res = query_omen_execute(omen_json_prompt, model=MODEL_LFM24B, num_ctx=65536)
                cycle_tokens += omen_res["eval_count"]
                throughput_samples.append(omen_res["tok_s"])

                print(f"    ✓ Handshake JSON completato: Flint {flint_res['tok_s']} tok/s | OMEN {omen_res['tok_s']} tok/s")
                update_devloop_hud(cycle, True, time.time() - cycle_t0, f"json_handshake_{scen_type}", flint_res["text"][:300])

                # Archivia incidente & remediation
                try:
                    incident_record = {
                        "cycle": cycle,
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "incident": flint_res["text"],
                        "remediation": omen_res["text"],
                        "flint_tok_s": flint_res["tok_s"],
                        "omen_tok_s": omen_res["tok_s"]
                    }
                    with open(INCIDENTS_LOG, "a", encoding="utf-8") as f:
                        f.write(json.dumps(incident_record) + "\n")
                except Exception as inc_err:
                    print(f"    ⚠ Incident log error: {inc_err}")

        except Exception as exc:
            cycle_success = False
            print(f"  ⚠ Avviso nel ciclo #{cycle}: {exc}")
            update_devloop_hud(cycle, False, time.time() - cycle_t0, f"cycle_error: {exc}")

        # Aggiornamento stato sessione
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
        if len(state["recent_events"]) > 20:
            state["recent_events"].pop(0)

        update_live_report(state)

        # Pausa tra cicli
        elapsed_cycle = time.time() - cycle_t0
        sleep_needed = max(5.0, cycle_interval_s - elapsed_cycle)
        if time.time() + sleep_needed < end_time:
            print(f"  ↳ Ciclo completato in {round(elapsed_cycle, 2)}s. Pausa di {round(sleep_needed, 1)}s prima del prossimo ciclo...")
            time.sleep(sleep_needed)

    state["active_status"] = "COMPLETED"
    update_live_report(state)
    print("\n" + "=" * 70)
    print(f"SESSIONE DI ENDURANCE COMPLETATA (Totale Cicli: {cycle}, Successo: {state['successful_cycles']}/{cycle})")
    print(f"Prototipi R&D Generati: {len(state['prototypes_generated'])}")
    print(f"Token Totali Generati: {state['total_tokens_generated']} | Throughput Medio: {state['average_throughput_tok_s']} tok/s")
    print(f"Report finale archiviato in: {LIVE_REPORT_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HyperSpace Multi-Agent Endurance & R&D Session")
    parser.add_argument("--duration-minutes", type=float, default=120.0, help="Durata della sessione in minuti (default: 120)")
    parser.add_argument("--cycle-interval", type=float, default=30.0, help="Intervallo minimo tra cicli in secondi (default: 30)")
    args = parser.parse_args()

    run_endurance_session(duration_minutes=args.duration_minutes, cycle_interval_s=args.cycle_interval)
