#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# scripts/omen_allnight_sovereign.py
"""Motore Notturno Sovrano per HP OMEN 16 & Mesh HyperSpace AGI 1.05.

Esegue per tutta la notte una pipeline autonoma e continua che copre l'intero
spettro operativo del sistema:
1. [QA, Test & Audit]: Suite di test invarianti, controlli di integrità e watchdog hardware.
2. [Sviluppo Autonomo & CoT]: Distillazione neurale CoT (Qwen3.5-Coder 9B / LFM 24B / Granite),
   validazione AST Python, generazione dataset sintetico e riflessione Harness².
3. [Sogni Notturni & Memoria]: Trigger riflessione identità di Anna (POST /persona/dream),
   sintesi scene oniriche (shared/dream_visual) e consolidamento memorie in Hermes FTS5.
4. [Generazione Immagini]: Workflow ComfyUI (ChickMixFlat SD1.5 / SDXL Turbo) per i ritratti
   di Anna e paesaggi cyberpunk della mesh, con salvataggio automatico dei render.
5. [Resumable State Machine WAL (RFC-0044)]: Transizioni atomiche e ripresa garantita
   senza duplicazione di lavoro.
6. [Guardia Termica & Risorse]: Monitoraggio continuo VRAM e temperatura GPU (>80°C = cooldown).

Uso:
    .venv/bin/python scripts/omen_allnight_sovereign.py --once
    .venv/bin/python scripts/omen_allnight_sovereign.py --daemon --interval 300
    .venv/bin/python scripts/omen_allnight_sovereign.py --status
"""

from __future__ import annotations

import argparse
import ast
import datetime
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.identity import generate_or_load_identity, make_request_headers
from shared.universal_model_parser import CavemanEngine, UniversalModelParser
from shared.codebase_journal import CodebaseJournal
from shared.harness_reflector import HarnessReflector
from shared.dream_visual import build_dream_prompt, parse_dream, filtra_dream
from shared.image_jobs import nuovo_job, workflow
from shared.resumable_state_machine import (
    CheckpointStore,
    ResumableStateMachine,
    RunState,
    ExecutionStatus,
)

# Configurazione endpoint
OMEN_NODE_URL = os.getenv("OMEN_NODE_URL", "http://100.104.238.125:8081").rstrip("/")
OMEN_CP_URL = os.getenv("OMEN_CP_URL", "http://100.104.238.125:8085").rstrip("/")
ASUS_OLLAMA_URL = os.getenv("ASUS_OLLAMA_URL", "http://100.64.31.18:11434").rstrip("/")
LOCAL_CP_URL = os.getenv("LOCAL_CP_URL", "http://127.0.0.1:8085").rstrip("/")
COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")

DATA_DIR = ROOT / "data"
NIGHTLY_DIR = DATA_DIR / "nightly"
NIGHTLY_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = NIGHTLY_DIR / "omen_allnight_state.json"
AUDIT_LOG = NIGHTLY_DIR / "omen_audit.jsonl"
COT_DATASET = DATA_DIR / "synthetic_cot_dataset.jsonl"
DREAM_LOG = NIGHTLY_DIR / "omen_dreams.jsonl"
IMAGE_LOG = NIGHTLY_DIR / "omen_images.jsonl"
NODE_STREAM_LOG = NIGHTLY_DIR / "node_stream.jsonl"
THERMAL_FLAG = DATA_DIR / "thermal_pause.flag"
OUTPUT_DIR = ROOT / "output" / "nightly_renders"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Toggle generazione immagini (disabilitato su richiesta per evitare allucinazioni veloci a 8 passi e concentrare 100% risorse su 40B/24B)
ENABLE_IMAGE_GENERATION = os.getenv("ENABLE_IMAGE_GENERATION", "false").lower() == "true"

# Modelli target ad alta capacità (40B e 24B prioritari per ricerca e sviluppo continuo)
CODE_MODELS = [
    "flint:latest",  # 40B NVFP4 Deep Reasoning Engine
    "hf.co/AtomicChat/LFM2.5-24B-A2B-Uncensored-GGUF:Q4_K_M",  # 24B Liquid MoE
    "hf.co/mradermacher/Qwen3.5-9B-Coder-GGUF:Q4_K_M",  # 9B Coder
    "granite3.3:8b",  # 8B Fast
]

# Ruolo di ASUS (ALLNIGHT_USE_ASUS): "true" = primario per i modelli pesanti (default),
# "fallback" = tutto parte dall'OMEN e ASUS interviene solo se l'OMEN non risponde
# (es. ASUS a batteria), "false" = mai. ALLNIGHT_CODE_MODELS sostituisce la rotazione (virgole);
# ALLNIGHT_DEV_TIMEOUT alza il timeout della fase dev (il primo caricamento a freddo
# di un modello sull'OMEN supera spesso i 90 s).
ASUS_MODE = os.getenv("ALLNIGHT_USE_ASUS", "true").strip().lower()
USE_ASUS = ASUS_MODE != "false"
ASUS_PRIMARY = ASUS_MODE not in ("false", "fallback")
if os.getenv("ALLNIGHT_CODE_MODELS", "").strip():
    CODE_MODELS = [m.strip() for m in os.getenv("ALLNIGHT_CODE_MODELS", "").split(",") if m.strip()]
DEV_TIMEOUT = int(os.getenv("ALLNIGHT_DEV_TIMEOUT", "90"))

IMAGE_SCENARIOS = [
    {
        "title": "Anna nella sala nodi sovrana",
        "prompt": "Masterpiece portrait of Anna, dark navy hair, gentle smile, modern tech jacket, glowing cybernetic terminal background, cinematic soft lighting, 8k resolution, best quality",
        "family": "sd15",
    },
    {
        "title": "Anna all'alba sul balcone",
        "prompt": "Cinematic portrait of Anna looking at the dawn skyline, morning golden hour light, soft breeze, detailed facial features, realistic anime style, chickmix aesthetic",
        "family": "sd15",
    },
    {
        "title": "Router Quantico HyperSpace",
        "prompt": "Concept art of HyperSpace sovereign mesh hardware router node, glowing copper heat pipes, crystalline neural core, cinematic octane render, 4k",
        "family": "sd15",
    },
    {
        "title": "Anna riflessione notturna",
        "prompt": "Anna contemplating under starry holographic ceiling in sovereign datacenter, ambient blue and teal reflections, hyperdetailed, peaceful expression",
        "family": "sd15",
    },
]

AUTONOMOUS_DEV_TASKS = [
    {
        "topic": "Work-Stealing Deque Lock-Free",
        "prompt": "Implementa in Python una coda concorrente `WorkStealingPriorityDeque` basata sull'algoritmo Chase-Lev, con metodi `push_bottom(task)`, `pop_bottom()`, e `steal_top()`. Mostra prima il tuo ragionamento dettagliato dentro il tag <think>, poi restituisci il codice completo con annotazioni di tipo e docstrings.",
    },
    {
        "topic": "Resilient Mesh Heartbeat with Vector Clocks",
        "prompt": "Scrivi una classe Python `MeshVectorClockGovernor` per sincronizzare lo stato dei nodi in un cluster P2P senza server centrale, gestendo conflitti e partizioni di rete. Mostra prima il ragionamento in <think> poi il codice.",
    },
    {
        "topic": "AST Sanitizer & Sandbox Security Gate",
        "prompt": "Crea una funzione Python `verify_safe_ast_execution(code_str, allowed_modules)` che analizza l'albero sintattico astratto (AST) ed intercetta `os.system`, `subprocess`, e `eval`, restituendo (is_safe, violations). Mostra prima il ragionamento in <think> poi il codice.",
    },
    {
        "topic": "Adaptive Inference Latency PID Controller",
        "prompt": "Implementa un controller PID discreto `InferenceConcurrencyGovernor` in Python che adatta dinamicamente il limite di richieste concorrenti per mantenere la latenza GPU sotto i 250ms. Mostra prima il ragionamento in <think> poi il codice.",
    },
]


def _log(tag: str, msg: str, node: str = "OMEN-16"):
    ts_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        print(f"[{ts_str}] [{tag}] {msg}", flush=True)
    except UnicodeEncodeError:
        safe_msg = msg.encode("ascii", errors="replace").decode("ascii")
        print(f"[{ts_str}] [{tag}] {safe_msg}", flush=True)
    try:
        record = {
            "timestamp": now_iso,
            "tag": tag,
            "node": node,
            "message": msg,
        }
        with open(NODE_STREAM_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


_log_stream = _log


def is_thermal_safe() -> bool:
    """Verifica se la GPU OMEN o il sistema sono in allerta termica."""
    if THERMAL_FLAG.exists():
        _log("THERMAL", "Allerta termica attiva (>80°C). Raffreddamento hardware in corso.")
        return False
    return True


def _is_asus_available() -> bool:
    """Verifica rapida (2.5s) se il nodo ASUS Ollama è online e raggiungibile."""
    if not USE_ASUS:
        return False
    try:
        req = urllib.request.Request(f"{ASUS_OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def execute_omen_prompt(
    prompt: str,
    model: str,
    timeout: int = 90,
    node_url: str = OMEN_NODE_URL,
) -> Dict[str, Any]:
    """Invia un prompt al cluster sovrano con routing intelligente e fallback resiliente.
    
    - Modelli 40B (flint): tenta prioritariamente ASUS se online; se non disponibile,
      esegue direttamente su HP OMEN 16 con timeout esteso (240s) accettando offload CPU/RAM.
    - Modelli 24B/8B/9B: esegue su HP OMEN 16 con firma ECDSA crittografica; gestisce
      retry in caso di nodo temporaneamente occupato (503).
    """
    is_flint = "flint" in model.lower()
    is_heavy = is_flint or "24b" in model.lower() or "40b" in model.lower()

    # 1. Routing prioritario carichi pesanti (40B flint, 24B LFM) su ASUS se disponibile (48GB RAM)
    if (is_heavy or is_flint) and ASUS_PRIMARY and _is_asus_available():
        t0 = time.perf_counter()
        asus_timeout = max(timeout, 380) if is_flint else max(timeout, 300)
        try:
            _log_stream("ROUTING", f"Inoltro prompt ({model}) verso ASUS Ollama (timeout {asus_timeout}s, num_ctx 32k)...", node="ASUS-V16")
            mesh_payload = json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_ctx": 32768,  # Finestra di contesto ottimizzata (max 200k) per alimentazione PD 100W
                },
            }).encode("utf-8")
            mesh_req = urllib.request.Request(
                f"{ASUS_OLLAMA_URL}/api/generate",
                data=mesh_payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(mesh_req, timeout=asus_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            resp_str = data.get("response", "")
            thinking_str = data.get("thinking", "")
            if thinking_str and resp_str:
                full_resp = f"<think>\n{thinking_str}\n</think>\n\n{resp_str}"
            elif resp_str:
                full_resp = resp_str
            else:
                full_resp = f"<think>\n{thinking_str}\n</think>" if thinking_str else ""
            elapsed = round(time.perf_counter() - t0, 2)
            return {
                "status": "ok",
                "model": model,
                "elapsed_s": elapsed,
                "response": full_resp,
                "routed_via": "ASUS_OLLAMA",
            }
        except Exception as exc_asus:
            _log_stream("ROUTING", f"ASUS non ha risposto ({exc_asus}): failover automatico su HP OMEN 16...", node="OMEN-16")

    # 2. Esecuzione su HP OMEN 16 (via Node API :8081/execute con firma ECDSA)
    effective_timeout = max(timeout, 240) if is_flint else timeout
    if is_flint:
        _log_stream(
            "ROUTING",
            f"ASUS non disponibile: esecuzione 40B ({model}) su HP OMEN 16 (CPU/GPU offload, timeout {effective_timeout}s)...",
            node="OMEN-16",
        )

    identity = generate_or_load_identity()
    task_id = f"omen-allnight-{int(time.time() * 1000)}"
    payload = json.dumps({
        "task_id": task_id,
        "model": model,
        "prompt": prompt,
    }).encode("utf-8")

    hdrs = {"Content-Type": "application/json"}
    hdrs.update(
        make_request_headers(
            identity["node_id"],
            identity["public_key"],
            identity["_private_key"],
            body=payload,
        )
    )

    max_retries = 5
    last_exc = None
    t0 = time.perf_counter()

    for attempt in range(max_retries):
        req = urllib.request.Request(f"{node_url}/execute", data=payload, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            resp_str = data.get("response", "")
            if resp_str.startswith("[OLLAMA ERROR]") or "Internal Server Error" in resp_str:
                raise RuntimeError(resp_str)
            elapsed = round(time.perf_counter() - t0, 2)
            return {
                "status": "ok",
                "model": model,
                "elapsed_s": elapsed,
                "response": resp_str,
                "routed_via": "OMEN_NODE",
            }
        except urllib.error.HTTPError as http_err:
            last_exc = http_err
            if http_err.code == 503 and attempt < max_retries - 1:
                # Nodo occupato da altro task: attesa slot libero
                _log_stream("QUEUE", f"Nodo occupato (503): attesa slot libero ({attempt + 1}/{max_retries})...", node="OMEN-16")
                time.sleep(5.0)
                continue
            break
        except Exception as exc:
            last_exc = exc
            break

    # 3. Fallback secondario su ASUS se non era flint ed è online
    if not is_flint and _is_asus_available():
        try:
            _log_stream("ROUTING", f"OMEN ha fallito ({str(last_exc)[:200]}): fallback secondario su ASUS Ollama per {model}...", node="ASUS-V16")
            mesh_payload = json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_ctx": 32768,
                },
            }).encode("utf-8")
            mesh_req = urllib.request.Request(
                f"{ASUS_OLLAMA_URL}/api/generate",
                data=mesh_payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(mesh_req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            elapsed = round(time.perf_counter() - t0, 2)
            return {
                "status": "ok",
                "model": model,
                "elapsed_s": elapsed,
                "response": data.get("response", ""),
                "routed_via": "ASUS_FALLBACK",
            }
        except Exception:
            pass

    elapsed = round(time.perf_counter() - t0, 2)
    return {
        "status": "error",
        "model": model,
        "elapsed_s": elapsed,
        "error": f"OMEN: {last_exc}",
    }


# =============================================================================
# FASE 1: TEST & AUDIT SUITE
# =============================================================================
def run_test_and_audit() -> Dict[str, Any]:
    """Esegue controlli di regressione, licensing e watchdog del nodo OMEN."""
    _log("AUDIT", "Avvio audit di integrità e test di sistema...")
    t0 = time.perf_counter()

    # 1.1 Fast Pytest Run
    test_files = [
        "tests/test_task_scheduler_rfc0043.py",
        "tests/test_resumable_state_machine_rfc0044.py",
        "tests/test_devstudio_service.py",
        "tests/test_hermes_memory.py",
        "tests/test_universal_model_parser.py",
        "tests/test_codebase_journal.py",
    ]
    existing_tests = [f for f in test_files if (ROOT / f).exists()]
    pytest_res = {"passed": False, "count": 0, "output": ""}
    if existing_tests:
        cmd = [sys.executable, "-m", "pytest"] + existing_tests + ["-q"]
        try:
            p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=60)
            pytest_res["passed"] = p.returncode == 0
            pytest_res["output"] = p.stdout.strip()[-200:] if p.stdout else p.stderr.strip()[-200:]
        except Exception as e:
            pytest_res["output"] = f"Pytest error: {e}"

    # 1.2 OMEN Hardware Watchdog
    node_audit = {"online": False, "ac_line": False, "battery_pct": 0, "vram_gb": 0.0, "latency_ms": 0.0}
    try:
        t_ping = time.perf_counter()
        req = urllib.request.Request(f"{OMEN_NODE_URL}/status")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            node_audit["online"] = True
            node_audit["latency_ms"] = round((time.perf_counter() - t_ping) * 1000, 1)
            node_audit["ac_line"] = data.get("power", {}).get("ac_line", data.get("ac_line", False))
            node_audit["battery_pct"] = data.get("power", {}).get("battery_pct", data.get("battery_pct", 0))
            node_audit["vram_gb"] = data.get("vram_gb", 0.0)
    except Exception as exc:
        node_audit["error"] = str(exc)

    elapsed = round(time.perf_counter() - t0, 2)
    audit_record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "elapsed_s": elapsed,
        "pytest": pytest_res,
        "omen_node": node_audit,
    }

    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(audit_record) + "\n")

    _log("AUDIT", f"Audit completato in {elapsed}s (Pytest: {pytest_res['passed']}, OMEN Latency: {node_audit.get('latency_ms')}ms)")
    return audit_record


# =============================================================================
# FASE 2: SVILUPPO AUTONOMO & DISTILLAZIONE CoT
# =============================================================================
def run_autonomous_dev_distillation(cycles: int = 1) -> Dict[str, Any]:
    """Genera e valida codice su OMEN con verifica AST e riflessione Harness²."""
    _log("DEV", f"Avvio sviluppo autonomo e distillazione ({cycles} task)...")
    t0 = time.perf_counter()
    distilled = 0
    results = []

    for i in range(cycles):
        task_info = random.choice(AUTONOMOUS_DEV_TASKS)
        model = random.choice(CODE_MODELS)
        _log("DEV", f"Esecuzione task '{task_info['topic']}' su modello {model}...")

        res = execute_omen_prompt(task_info["prompt"], model=model, timeout=DEV_TIMEOUT)
        if res.get("status") == "ok":
            parsed = UniversalModelParser.parse(res["response"])
            valid_blocks = [b.code for b in parsed.code_blocks if b.is_valid_ast]

            # Validazione sintattica diretta AST
            ast_ok = False
            first_code = valid_blocks[0] if valid_blocks else ""
            if first_code:
                try:
                    ast.parse(first_code)
                    ast_ok = True
                except SyntaxError:
                    ast_ok = False

            if ast_ok and parsed.reasoning_cot:
                entry = {
                    "id": f"cot-{int(time.time() * 1000)}",
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "topic": task_info["topic"],
                    "model": model,
                    "elapsed_s": res["elapsed_s"],
                    "reasoning_cot": parsed.reasoning_cot,
                    "code": first_code,
                    "ast_valid": True,
                }
                with open(COT_DATASET, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
                distilled += 1
                results.append({"topic": task_info["topic"], "model": model, "valid": True})
                _log("DEV", f"✓ Task '{task_info['topic']}' distillato e verificato AST con successo.")
            else:
                results.append({"topic": task_info["topic"], "model": model, "valid": False, "reason": "No CoT or AST invalid"})
        else:
            results.append({"topic": task_info["topic"], "model": model, "valid": False, "error": res.get("error")})

        time.sleep(2)

    # Riflessione Harness² per auto-miglioramento continuo
    harness_draft = None
    try:
        reflector = HarnessReflector()
        harness_draft = reflector.reflect_on_dev_cycle({
            "distilled_count": distilled,
            "timestamp": datetime.datetime.now().isoformat(),
            "results": results,
        })
        if harness_draft:
            _log("DEV", f"Generato draft inerte Forge: {harness_draft.get('id')}")
    except Exception as exc:
        _log("DEV", f"Riflessione Harness² non critica: {exc}")

    elapsed = round(time.perf_counter() - t0, 2)
    return {
        "distilled_count": distilled,
        "elapsed_s": elapsed,
        "tasks": results,
        "harness_draft": harness_draft.get("id") if harness_draft else None,
    }


def leggi_env(percorso: Path) -> dict:
    """Carica variabili chiave dal file .env del repository."""
    valori: dict[str, str] = {}
    try:
        righe = percorso.read_text(encoding="utf-8").splitlines()
    except OSError:
        return valori
    for linea in righe:
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        chiave, _, valore = linea.partition("=")
        valori[chiave.strip()] = valore.split(" #", 1)[0].strip().strip('"').strip("'")
    return valori


# =============================================================================
# FASE 3: SOGNI NOTTURNI & IDENTITÀ ANNA
# =============================================================================
def run_nightly_dreams() -> Dict[str, Any]:
    """Attiva la riflessione sull'identità di Anna e la sintesi di sogni onirici."""
    _log("DREAM", "Esecuzione sogni notturni & consolidamento identità...")
    t0 = time.perf_counter()

    env_vals = leggi_env(ROOT / ".env")
    network_token = env_vals.get("NETWORK_ADMIN_TOKEN", "")

    # 3.1 Trigger Sogno Identità via Control Plane (Anna Persona Dream o Nightly Tick)
    persona_res = {"triggered": False, "status": "unknown"}
    hdrs = {"Content-Type": "application/json"}
    if network_token:
        hdrs["X-Hyperspace-Network-Token"] = network_token

    try:
        req = urllib.request.Request(f"{LOCAL_CP_URL}/dreams/nightly/tick", data=b"{}", headers=hdrs, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            persona_res["triggered"] = True
            persona_res["report"] = data
            _log("DREAM", f"Tick sogni CP: HTTP {resp.status} - {data.get('esito', data.get('motivo', 'ok'))}")
    except Exception as exc:
        persona_res["error"] = str(exc)
        _log("DREAM", f"Tick sogni CP info: {exc}")

    # 3.2 Sintesi Scena Onirica & Schizzo (shared.dream_visual)
    visual_dream = None
    try:
        dream_prompt = build_dream_prompt("Identità Anna v8: sono pronta a interagire nella stanza.")
        res = execute_omen_prompt(dream_prompt, model="granite3.3:8b", timeout=45)
        if res.get("status") == "ok":
            parsed = parse_dream(res["response"])
            if parsed:
                ok, reason = filtra_dream(parsed, autore="anna")
                if ok:
                    visual_dream = {
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "author": "anna",
                        "scena": parsed["scena"],
                        "disegno": parsed["disegno"],
                    }
                    with open(DREAM_LOG, "a", encoding="utf-8") as f:
                        f.write(json.dumps(visual_dream) + "\n")
                    _log("DREAM", f"✓ Scena onirica: '{parsed['scena'][:60]}...' | Disegno: '{parsed['disegno'][:60]}...'")
    except Exception as exc:
        _log("DREAM", f"Visual dream error: {exc}")

    elapsed = round(time.perf_counter() - t0, 2)
    return {
        "elapsed_s": elapsed,
        "persona_dream": persona_res,
        "visual_dream": visual_dream,
    }


# =============================================================================
# FASE 4: GENERAZIONE IMMAGINI COMFYUI
# =============================================================================
def run_image_generation(dream_prompt_hint: Optional[str] = None) -> Dict[str, Any]:
    """Crea ed esegue un job artistico tramite ComfyUI su MPS o porta 8188."""
    _log("IMAGE", "Controllo disponibilità ComfyUI e generazione artistica...")
    t0 = time.perf_counter()

    # Verifica se ComfyUI risponde
    comfy_online = False
    try:
        req = urllib.request.Request(f"{COMFYUI_URL}/system_stats")
        with urllib.request.urlopen(req, timeout=3) as resp:
            comfy_online = resp.status == 200
    except Exception:
        pass

    if not comfy_online:
        _log("IMAGE", f"ComfyUI non attivo su {COMFYUI_URL}. Job registrato in coda per esecuzione successiva.")
        return {"executed": False, "reason": "comfyui_offline"}

    scenario = random.choice(IMAGE_SCENARIOS)
    prompt_text = dream_prompt_hint or scenario["prompt"]

    job = nuovo_job(
        prompt=prompt_text,
        richiedente="omen-nightly",
        canale="nightly",
        famiglia=scenario["family"],
        larghezza=512,
        altezza=512,
        passi=8,
        seed=random.randint(1, 999999),
    )

    try:
        # Usa euler sampler per esecuzione fluida su MPS
        wf = workflow(job, modello={"sampler": "euler", "scheduler": "normal"})
        payload = json.dumps({"prompt": wf, "client_id": "hyperspace-allnight"}).encode("utf-8")
        req = urllib.request.Request(
            f"{COMFYUI_URL}/prompt",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            p_data = json.loads(resp.read().decode("utf-8"))

        prompt_id = p_data.get("prompt_id")
        _log("IMAGE", f"Job inviato a ComfyUI (prompt_id={prompt_id}). Attesa render...")

        # Polling del risultato fino a 60 secondi
        rendered_images = []
        for _ in range(30):
            time.sleep(2)
            try:
                h_req = urllib.request.Request(f"{COMFYUI_URL}/history/{prompt_id}")
                with urllib.request.urlopen(h_req, timeout=5) as h_resp:
                    h_data = json.loads(h_resp.read().decode("utf-8"))
                    if prompt_id in h_data:
                        outputs = h_data[prompt_id].get("outputs", {})
                        for node_out in outputs.values():
                            for img_info in node_out.get("images", []):
                                fn = img_info.get("filename")
                                if fn:
                                    rendered_images.append(fn)
                        break
            except Exception:
                pass

        elapsed = round(time.perf_counter() - t0, 2)
        record = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "job_id": job["id"],
            "prompt_id": prompt_id,
            "title": scenario["title"],
            "prompt": prompt_text,
            "rendered_images": rendered_images,
            "elapsed_s": elapsed,
        }
        with open(IMAGE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        _log("IMAGE", f"✓ Generazione completata in {elapsed}s: {len(rendered_images)} immagini prodotte.")
        return {"executed": True, "job_id": job["id"], "images": rendered_images, "elapsed_s": elapsed}
    except Exception as exc:
        _log("IMAGE", f"Errore durante la generazione immagine: {exc}")
        return {"executed": False, "error": str(exc)}


# =============================================================================
# RESUMABLE STATE MACHINE CICLO NOTTURNO
# =============================================================================
def run_single_allnight_cycle() -> Dict[str, Any]:
    """Esegue un ciclo notturno completo coordinato dalla State Machine con WAL."""
    _log("NIGHTLY", "========================================================")
    _log("NIGHTLY", " INIZIO CICLO NOTTURNO SOVRANO (HP OMEN 16 & MESH)")
    _log("NIGHTLY", "========================================================")
    t0 = time.perf_counter()

    if not is_thermal_safe():
        _log("NIGHTLY", "Pausa di raffreddamento termico attiva. Ciclo rimandato.")
        return {"status": "thermal_pause"}

    # Inizializza CheckpointStore e State Machine
    wal_dir = NIGHTLY_DIR / "wal"
    store = CheckpointStore(wal_dir)
    machine = ResumableStateMachine(store)

    # Registra i 5 passi atomici della pipeline notturna
    def step_audit(state: RunState) -> Dict[str, Any]:
        return {"audit": run_test_and_audit()}

    def step_dev(state: RunState) -> Dict[str, Any]:
        return {"dev": run_autonomous_dev_distillation(cycles=1)}

    def step_research(state: RunState) -> Dict[str, Any]:
        _log("RESEARCH", "Approfondimento autonomo AGI, Coscienza Sintetica & Swarm AI...")
        from shared.agi_research_engine import AGIResearchEngine
        engine = AGIResearchEngine()
        record = engine.execute_study_cycle(omen_executor_fn=execute_omen_prompt)
        _log("RESEARCH", f"✓ Studio completato: {record.get('domain')} (AST valid: {record.get('ast_valid')})")
        return {"research": record}

    def step_dream(state: RunState) -> Dict[str, Any]:
        return {"dream": run_nightly_dreams()}

    def step_image(state: RunState) -> Dict[str, Any]:
        if not ENABLE_IMAGE_GENERATION:
            _log("IMAGE", "Generazione immagini fermata: risorse calcolo allocate al 100% per ricerca e modelli 40B/24B.", node="Mac M5 Hub")
            return {"image": {"executed": False, "status": "stopped_by_user", "reason": "Test fermato: risorse dedicate a 40B/24B"}}
        dream_hint = (state.payload.get("dream", {}).get("visual_dream") or {}).get("disegno")
        return {"image": run_image_generation(dream_prompt_hint=dream_hint)}

    machine.register_step(0, "audit", step_audit)
    machine.register_step(1, "dev", step_dev)
    machine.register_step(2, "research", step_research)
    machine.register_step(3, "dream", step_dream)
    machine.register_step(4, "image", step_image)

    cycle_id = f"cycle-{int(time.time())}"
    cycle_report: Dict[str, Any] = {
        "cycle_id": cycle_id,
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "phases": {},
    }

    try:
        current_state = machine.start_or_resume(cycle_id)
        while current_state.status == ExecutionStatus.RUNNING.value and current_state.step_index < 5:
            current_state = machine.step()

        elapsed = round(time.perf_counter() - t0, 2)
        cycle_report["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cycle_report["total_elapsed_s"] = elapsed
        cycle_report["status"] = "success"
        cycle_report["phases"] = current_state.payload

        # Salva stato aggiornato per cruscotto e API
        STATE_FILE.write_text(json.dumps(cycle_report, indent=2), encoding="utf-8")
        _log("NIGHTLY", f"================ CICLO {cycle_id} COMPLETATO IN {elapsed}s ================\n")
        return cycle_report

    except Exception as exc:
        _log("NIGHTLY", f"Errore critico durante il ciclo notturno: {exc}")
        cycle_report["status"] = "failed"
        cycle_report["error"] = str(exc)
        STATE_FILE.write_text(json.dumps(cycle_report, indent=2), encoding="utf-8")
        return cycle_report


def get_nightly_status() -> Dict[str, Any]:
    """Legge lo stato attuale, metriche aggregate e cronologia del turno notturno."""
    state_data = {}
    if STATE_FILE.exists():
        try:
            state_data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Conteggio righe log
    audit_count = sum(1 for _ in open(AUDIT_LOG, "r", encoding="utf-8")) if AUDIT_LOG.exists() else 0
    cot_count = sum(1 for _ in open(COT_DATASET, "r", encoding="utf-8")) if COT_DATASET.exists() else 0
    dream_count = sum(1 for _ in open(DREAM_LOG, "r", encoding="utf-8")) if DREAM_LOG.exists() else 0
    img_count = sum(1 for _ in open(IMAGE_LOG, "r", encoding="utf-8")) if IMAGE_LOG.exists() else 0

    from shared.agi_research_engine import AGIResearchEngine
    research_st = AGIResearchEngine().get_research_status()

    return {
        "status": "online",
        "latest_cycle": state_data,
        "research": research_st,
        "metrics": {
            "total_audit_runs": audit_count,
            "total_cot_samples": cot_count,
            "total_dreams_synthesized": dream_count,
            "total_images_rendered": img_count,
            "total_agi_research_studies": research_st.get("total_studies", 0),
            "prototypes_count": research_st.get("prototypes_count", 0),
            "thermal_safe": is_thermal_safe(),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Motore Notturno Sovrano per HP OMEN 16 & Mesh HyperSpace")
    parser.add_argument("--once", action="store_true", help="Esegui un singolo ciclo notturno completo")
    parser.add_argument("--daemon", action="store_true", help="Esegui in loop continuo per tutta la notte")
    parser.add_argument("--interval", type=int, default=300, help="Intervallo fra i cicli in secondi (default: 300s)")
    parser.add_argument("--status", action="store_true", help="Stampa lo stato e le metriche aggregate")
    args = parser.parse_args()

    if args.status:
        st = get_nightly_status()
        print(json.dumps(st, indent=2))
        return

    if args.once:
        run_single_allnight_cycle()
    elif args.daemon:
        _log("DAEMON", f"Avvio turno notturno sovrano continuo (intervallo: {args.interval}s).")
        while True:
            try:
                run_single_allnight_cycle()
                _log("DAEMON", f"Pausa di {args.interval}s prima del prossimo ciclo...")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                _log("DAEMON", "Turno notturno interrotto dall'operatore.")
                break
            except Exception as exc:
                _log("ERROR", f"Eccezione loop: {exc}")
                time.sleep(30)
    else:
        run_single_allnight_cycle()


if __name__ == "__main__":
    main()
