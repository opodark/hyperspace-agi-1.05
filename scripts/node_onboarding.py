#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""HyperSpace AGI — Node Onboarding Tool V2.

Guida automatizzata e interattiva per l'onboarding e la ricostruzione dei nodi
della mesh secondo le specifiche di docs/node-onboarding-v2.md:
1. Rileva automaticamente l'hardware locale (OS, RAM, CPU, GPU, VRAM).
2. Propone il profilo ottimale (compute, dev, hub, edge, custom).
3. Riconcilia il file .env in modo non distruttivo (preserva chiavi e commenti).
4. Genera istruzioni operative su misura per Docker e servizi host.

Uso:
  python scripts/node_onboarding.py                         # Modalità interattiva guidata
  python scripts/node_onboarding.py --profile compute       # Dry-run per nodo GPU (OMEN)
  python scripts/node_onboarding.py --profile dev --apply   # Applica configurazione Workstation Mac
  python scripts/node_onboarding.py --profile hub --json    # Output JSON per automazioni cloud
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.node_telemetry import get_system_hardware

PROFILES = ("compute", "dev", "hub", "edge", "custom")

PROFILE_TEMPLATES: Dict[str, Dict[str, str]] = {
    "compute": {
        "NODE_TIER": "hub",
        "NODE_ROLE": "compute_worker",
        "INFERENCE_BACKEND": "ollama",
        "COMFYUI_URL": "http://localhost:8188",
        "REEL_EDITOR_URL": "http://127.0.0.1:7860",
        "KOKORO_TTS_URL": "http://localhost:8880",
        "BUILDER_PUBLIC_BASE_URL": "http://localhost:8085",
    },
    "dev": {
        "NODE_TIER": "hub",
        "NODE_ROLE": "dev_workstation",
        "MEMORY_BACKEND": "hermes",
        "HERMES_MEMORY_URL": "http://127.0.0.1:8098",
        "MCP_CLIENTS": "openwork=hyperspace_openwork_local_client_token_32chars",
        "MCP_CLIENT_TOOLS": "openwork=code_sandbox,omega_query,web_search",
        "BUILDER_PUBLIC_BASE_URL": "http://localhost:8085",
    },
    "hub": {
        "NODE_TIER": "root",
        "NODE_ROLE": "mesh_authority",
        "MEMORY_BACKEND": "hermes",
        "HERMES_MEMORY_URL": "http://127.0.0.1:8098",
        "SEARXNG_URL": "http://localhost:8080",
        "BUILDER_PUBLIC_BASE_URL": "http://localhost:8085",
    },
    "edge": {
        "NODE_TIER": "leaf",
        "NODE_ROLE": "light_edge_watchdog",
        "VRAM_GB": "0",
        "MEMORY_BACKEND": "legacy",
    },
}

SERVICES_BY_PROFILE: Dict[str, Dict[str, List[str]]] = {
    "compute": {
        "docker": ["node-1", "ollama-nvidia (o ollama locale)"],
        "host": [
            "ComfyUI (porta :8188)",
            "TikTok Editor / Reel Forge (scripts/tiktok_editor_service.py :7860)",
            "Voicebox / Kokoro TTS",
            "Unsloth Fine-Tuning (scripts/unsloth/)",
            "Mesh Patch Watcher (scripts/mesh_patch_watcher.py)",
        ],
    },
    "dev": {
        "docker": ["code-sandbox"],
        "host": [
            "OpenWork Desktop UI (different-ai/openwork)",
            "OpenCode sidecar (via scripts/mcp_stdio_bridge.py)",
            "Hermes Memory Bridge (scripts/hermes_memory_bridge.py :8098)",
            "Graphify Surface (scripts/graphify_surface.py :7871)",
            "OpenClaw / Strix (CLI terminal agent)",
        ],
    },
    "hub": {
        "docker": [
            "control-plane (:8085)",
            "registry (:8086)",
            "searxng (:8080)",
            "open-webui (:3000)",
            "federation-gateway",
        ],
        "host": [
            "Telegram Business Bot Vittoria (scripts/telegram_business_bot.py)",
            "Hermes Memory Bridge (scripts/hermes_memory_bridge.py :8098)",
            "Multi-Cloud Vault Monitor (scripts/diagnostics/hermes_resilience_probe.py)",
        ],
    },
    "edge": {
        "docker": ["web-node"],
        "host": [
            "Watchdog P2P Relay (scripts/diagnostics/web_node_health.py)",
            "Ollama Vulkan / llama.cpp mobile",
        ],
    },
}


def recommend_profile(hw: Dict[str, Any]) -> str:
    """Consiglia il profilo architetturale basandosi sui sensori hardware."""
    sys_name = hw.get("os", "").lower()
    vram = float(hw.get("vram_total_gb") or 0.0)
    gpu_name = str(hw.get("gpu_name") or "").lower()

    # GPU NVIDIA dedicata con almeno 6GB VRAM -> compute
    if ("nvidia" in gpu_name or "geforce" in gpu_name or "rtx" in gpu_name) and vram >= 5.5:
        return "compute"

    # Mac Apple Silicon con RAM abbondante -> dev workstation
    if "darwin" in sys_name or "apple" in gpu_name:
        return "dev"

    # Mobile o ARM embedded -> edge
    if "android" in sys_name or "armv7" in platform.machine().lower():
        return "edge"

    # Linux server con CPU/RAM standard -> hub
    return "hub"


def read_env_file(path: Path) -> Tuple[List[str], Dict[str, str]]:
    """Legge un file .env preservando commenti e ordine delle righe."""
    if not path.is_file():
        return [], {}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    data: Dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, val = stripped.split("=", 1)
        data[key.strip()] = val.strip()
    return lines, data


def reconcile_env_content(
    existing_lines: List[str],
    existing_vars: Dict[str, str],
    target_vars: Dict[str, str],
) -> str:
    """Riconcilia le variabili desiderate nel .env senza distruggere personalizzazioni locali."""
    out_lines: List[str] = []
    seen_keys = set()

    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out_lines.append(line)
            continue
        key, _ = stripped.split("=", 1)
        k = key.strip()
        seen_keys.add(k)
        if k in target_vars:
            # Aggiorna con valore del target
            out_lines.append(f"{k}={target_vars[k]}")
        else:
            # Preserva variabile locale esistente
            out_lines.append(line)

    # Aggiungi chiavi mancanti in coda
    added = []
    for k, v in target_vars.items():
        if k not in seen_keys:
            added.append(f"{k}={v}")

    if added:
        if out_lines and out_lines[-1].strip():
            out_lines.append("")
        out_lines.append("# --- Aggiunte da HyperSpace Node Onboarding V2 ---")
        out_lines.extend(added)

    return "\n".join(out_lines) + "\n"


class NodeOnboarder:
    """Motore di configurazione e diagnostica onboarding per HyperSpace Mesh."""

    def __init__(self, repo_root: Optional[Path] = None, env_path: Optional[Path] = None):
        self.root = repo_root or ROOT
        self.env_path = env_path or (self.root / ".env")
        self.example_env_path = self.root / ".env.example"
        self.hw = get_system_hardware()

    def generate_plan(
        self,
        profile: str,
        custom_overrides: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Elabora il piano di configurazione senza applicare modifiche."""
        if profile not in PROFILES:
            raise ValueError(f"Profilo non valido: {profile}. Scegli tra: {PROFILES}")

        recommended = recommend_profile(self.hw)
        base_template = dict(PROFILE_TEMPLATES.get(profile, {}))

        # Integrazione VRAM rilevata per profili con GPU
        if profile == "compute" and self.hw.get("vram_total_gb", 0) > 0:
            base_template["VRAM_GB"] = str(int(self.hw["vram_total_gb"]))

        if custom_overrides:
            base_template.update(custom_overrides)

        # Legge .env esistente
        lines, existing = read_env_file(self.env_path)
        if not lines and self.example_env_path.is_file():
            # Inizializza dallo scheletro .env.example
            lines, existing = read_env_file(self.example_env_path)

        new_content = reconcile_env_content(lines, existing, base_template)

        # Rileva modifiche
        diffs = {}
        for k, v in base_template.items():
            if k not in existing or existing[k] != v:
                diffs[k] = {"current": existing.get(k, "(assente)"), "target": v}

        services = SERVICES_BY_PROFILE.get(profile, {"docker": [], "host": []})

        return {
            "profile": profile,
            "recommended_profile": recommended,
            "hardware": self.hw,
            "env_path": str(self.env_path),
            "target_variables": base_template,
            "changes_detected": len(diffs),
            "diffs": diffs,
            "new_env_content": new_content,
            "services_to_run": services,
        }

    def apply_plan(self, plan: Dict[str, Any]) -> bool:
        """Scrive il file .env su disco in UTF-8 senza BOM."""
        content = plan["new_env_content"]
        try:
            # Scrittura atomica senza BOM (cruciale per compatibilità Windows PowerShell / Compose)
            self.env_path.write_bytes(content.encode("utf-8"))
            return True
        except Exception as exc:
            print(f"[ERRORE] Impossibile scrivere {self.env_path}: {exc}", file=sys.stderr)
            return False


def run_interactive(onboarder: NodeOnboarder, apply: bool = False) -> int:
    """Interfaccia interattiva a menu da terminale per Cips."""
    hw = onboarder.hw
    rec = recommend_profile(hw)

    print("\n" + "=" * 74)
    print("  HYPERSPACE AGI — ONBOARDING E RICOSTRUZIONE NODI V2")
    print("=" * 74)
    print(f"  Sistema:     {hw.get('os')} ({hw.get('arch')})")
    print(f"  CPU / RAM:   {hw.get('cpu_count')} core · {hw.get('ram_total_gb')} GB RAM")
    print(f"  GPU / VRAM:  {hw.get('gpu_name')} · {hw.get('vram_total_gb')} GB VRAM")
    print(f"  Profilo Suggerito: 👉 [{rec.upper()}]")
    print("-" * 74)
    print("  Profili disponibili:")
    print("    1. compute  -> Worker GPU (Ollama CUDA, Unsloth, ComfyUI, TTS, Video)")
    print("    2. dev      -> Workstation (OpenWork, OpenCode, OpenClaw, Hermes, Graph)")
    print("    3. hub      -> Gateway Mesh (Control Plane, Registry, Telegram, WebUI)")
    print("    4. edge     -> Mobile/Light (Termux S24 Vulkan, Web Node, Watchdog)")
    print("    5. custom   -> Configurazione avanzata passo-passo")
    print("-" * 74)

    choice = input(f"Seleziona profilo [default: {rec}]: ").strip().lower()
    mapping = {"1": "compute", "2": "dev", "3": "hub", "4": "edge", "5": "custom"}
    selected = mapping.get(choice, choice if choice in PROFILES else rec)

    custom_overrides = {}
    if selected == "custom":
        print("\nConfigurazione personalizzata:")
        selected = "dev"
        ow = input("Abilitare OpenWork & OpenCode? (s/N): ").strip().lower() == "s"
        if ow:
            custom_overrides["MCP_CLIENTS"] = "openwork=hyperspace_openwork_local_client_token_32chars"
            custom_overrides["MCP_CLIENT_TOOLS"] = "openwork=code_sandbox,omega_query,web_search"
        unsloth = input("Abilitare Unsloth Fine-Tuning? (s/N): ").strip().lower() == "s"
        if unsloth:
            custom_overrides["UNSLOTH_ENABLED"] = "true"
        tg = input("Abilitare Bot Telegram Aziendale? (s/N): ").strip().lower() == "s"
        if tg:
            custom_overrides["TELEGRAM_BOT_ENABLED"] = "true"

    plan = onboarder.generate_plan(selected, custom_overrides=custom_overrides)

    print("\n" + "=" * 74)
    print(f"  PIANO DI CONFIGURAZIONE PROFILO: [{selected.upper()}]")
    print("=" * 74)
    if plan["changes_detected"] == 0:
        print("  ✅ Il file .env è già perfettamente allineato con questo profilo.")
    else:
        print(f"  Variabili da aggiornare ({plan['changes_detected']}):")
        for k, v in plan["diffs"].items():
            print(f"    ~ {k:22} : {v['current']} -> {v['target']}")

    print("\n  Container Docker consigliati:")
    for s in plan["services_to_run"]["docker"]:
        print(f"    🐳 {s}")

    print("\n  Servizi Host/Python da avviare:")
    for s in plan["services_to_run"]["host"]:
        print(f"    🐍 {s}")

    print("=" * 74)

    if not apply:
        confirm = input("\nApplicare le modifiche a .env? (S/n): ").strip().lower()
        if confirm in ("n", "no"):
            print("Operazione annullata. Nessuna modifica salvata.")
            return 0

    success = onboarder.apply_plan(plan)
    if success:
        print(f"\n✅ File {plan['env_path']} aggiornato con successo!")
        print("\nPassi successivi raccomandati:")
        if selected == "compute":
            print("  1. Avvia container: docker compose up -d --build node-1")
            print("  2. Avvia watcher:   bash scripts/mesh_node_deploy.sh")
        elif selected == "dev":
            print("  3. Avvia Hermes:    .venv/bin/python scripts/hermes_memory_bridge.py &")
            print("  4. Avvia Graphify:  .venv/bin/python scripts/graphify_surface.py &")
        elif selected == "hub":
            print("  1. Avvia stack:     docker compose up -d --build control-plane registry open-webui")
            print("  2. Avvia Telegram:  .venv/bin/python scripts/telegram_business_bot.py &")
    return 0 if success else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="HyperSpace AGI — Node Onboarding Tool V2 (docs/node-onboarding-v2.md)"
    )
    parser.add_argument(
        "--profile",
        choices=PROFILES,
        help="Profilo di configurazione nodo desiderato (compute, dev, hub, edge, custom)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Applica effettivamente le modifiche al file .env (altrimenti esegue in dry-run)",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Esegue senza prompt interattivi (obbligatorio specificare --profile)",
    )
    parser.add_argument(
        "--env-file",
        type=str,
        default=None,
        help="Percorso personalizzato del file .env (default: .env nella radice del repo)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Stampa il piano di onboarding in formato JSON strutturato",
    )

    args = parser.parse_args()
    env_path = Path(args.env_file) if args.env_file else (ROOT / ".env")
    onboarder = NodeOnboarder(repo_root=ROOT, env_path=env_path)

    if args.json:
        prof = args.profile or recommend_profile(onboarder.hw)
        plan = onboarder.generate_plan(prof)
        plan.pop("new_env_content", None)
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0

    if args.non_interactive or args.profile:
        prof = args.profile or recommend_profile(onboarder.hw)
        plan = onboarder.generate_plan(prof)
        print(f"HyperSpace Onboarding V2 — Profilo: {prof} (apply={args.apply})")
        print(f"Modifiche rilevate a .env: {plan['changes_detected']}")
        for k, v in plan["diffs"].items():
            print(f"  {k}: {v['current']} -> {v['target']}")
        if args.apply:
            ok = onboarder.apply_plan(plan)
            print(f"Applicazione: {'OK' if ok else 'FALLITA'}")
            return 0 if ok else 1
        print("Dry-run completato. Usa --apply per salvare.")
        return 0

    return run_interactive(onboarder, apply=args.apply)


if __name__ == "__main__":
    sys.exit(main())
