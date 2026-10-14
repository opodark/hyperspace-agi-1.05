# SPDX-License-Identifier: Apache-2.0
# shared/power_policy.py
# HyperSpace AGI 1.05 — Policy Energetica & Gestione Batteria della Mesh
"""Regole formali di approvvigionamento energetico, allocazione del carico e
resilienza a batteria per la flotta di nodi distribuiti HyperSpace 1.05.

Principi guida:
1. Privilegio della Presa Elettrica (Grid-First):
   I carichi computazionali pesanti (generazione diffusion ComfyUI, cicli di sogno
   notturni, fine-tuning e modelli >10B) vengono instradati prioritariamente sui nodi
   alimentati stabilmente dalla rete elettrica fissa (AC Line).
2. Protezione dell'Autonomia dei Portatili (Battery Preservation):
   Quando un nodo (MacBook, laptop Windows) opera a batteria:
   - Se esistono nodi AC nella mesh: il traffico viene deviato per preservare la batteria.
   - I task differibili (dream consolidation, indicizzazione Knowledge Graph) vengono sospesi.
   - Sotto il 20% di carica: scatta l'allerta 'critical', il nodo entra in modalità 'degraded'
     e respinge task non-vitali per prevenire arresti anomali del sistema operativo.
3. Resilienza a Blackout Totale (Cooperative Survival):
   Se l'intera flotta opera a batteria (nessun nodo su rete AC):
   - I task pesanti vengono congelati.
   - Il carico di inferenza essenziale viene distribuito proporzionalmente alla
     percentuale di carica residua di ciascun nodo.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

# Profili Energetici
PROFILE_GRID_AC = "grid_ac"                    # Alimentazione continua da rete elettrica
PROFILE_BATTERY_OPTIMAL = "battery_optimal"    # Batteria sana (> 50%) o in ricarica attiva
PROFILE_BATTERY_ECO = "battery_eco"            # Risparmio energetico (20% - 50%)
PROFILE_BATTERY_CRITICAL = "battery_critical"  # Emergenza batteria (< 20%)

# Soglie di default
THRESHOLD_ECO_PCT = float(os.getenv("POWER_THRESHOLD_ECO_PCT", "50.0"))
THRESHOLD_CRITICAL_PCT = float(os.getenv("POWER_THRESHOLD_CRITICAL_PCT", "20.0"))

# Classi di Task
TASK_LIGHT_INFERENCE = "light_inference"            # Laya decision engine (sub-50ms), triage, routing
TASK_STANDARD_INFERENCE = "standard_inference"      # LLM chat, completion standard (Qwen 4B/8B)
TASK_HEAVY_GPU = "heavy_gpu"                        # ComfyUI diffusion, SDXL, video rendering, training
TASK_DREAM_CONSOLIDATION = "dream_consolidation"    # Ciclo di riflessione notturna e insight
TASK_CODE_SANDBOX = "code_sandbox"                  # Esecuzione codice in container isolato
TASK_GRAPHIFY_INDEXING = "graphify_indexing"        # Rianalisi del Knowledge Graph repo


def classify_power_profile(
    ac_line: bool,
    battery_pct: Optional[float] = None,
    charging: bool = False,
    is_battery: bool = False,
) -> str:
    """Classifica lo stato energetico del nodo in uno dei 4 profili formali."""
    # Se il nodo è collegato alla presa elettrica fissa o non possiede batteria fisica
    if ac_line and not is_battery:
        return PROFILE_GRID_AC
    if ac_line and is_battery:
        # Portatile collegato all'alimentatore di rete
        if charging or (battery_pct is not None and battery_pct >= 90.0):
            return PROFILE_GRID_AC
        return PROFILE_BATTERY_OPTIMAL

    # Funzionamento a batteria (discharging o senza AC)
    pct = battery_pct if battery_pct is not None else 50.0
    if pct < THRESHOLD_CRITICAL_PCT:
        return PROFILE_BATTERY_CRITICAL
    elif pct < THRESHOLD_ECO_PCT:
        return PROFILE_BATTERY_ECO
    else:
        return PROFILE_BATTERY_OPTIMAL


def get_power_profile(power_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Genera un riepilogo del profilo energetico con moltiplicatore di capacità e vincoli."""
    pwr = power_info or {}
    ac_line = bool(pwr.get("ac_line", True))
    pct = pwr.get("battery_pct")
    charging = bool(pwr.get("charging", False))
    discharging = bool(pwr.get("discharging", False))
    is_battery = bool(pwr.get("is_battery", pct is not None))

    profile = classify_power_profile(
        ac_line=ac_line,
        battery_pct=pct,
        charging=charging,
        is_battery=is_battery,
    )

    if profile == PROFILE_GRID_AC:
        multiplier = 1.0
        max_concurrent = 4
        allow_heavy_gpu = True
        allow_dreams = True
        degraded = False
        desc = "Rete elettrica fissa (AC): capacità e prestazioni al 100%"
    elif profile == PROFILE_BATTERY_OPTIMAL:
        multiplier = 0.75
        max_concurrent = 2
        allow_heavy_gpu = ac_line  # Solo se collegato
        allow_dreams = ac_line
        degraded = False
        desc = f"Batteria ottimale ({pct:.0f}%): inferenza attiva, carichi pesanti deviati se possibile" if pct else "Batteria ottimale"
    elif profile == PROFILE_BATTERY_ECO:
        multiplier = 0.40
        max_concurrent = 1
        allow_heavy_gpu = False
        allow_dreams = False
        degraded = False
        desc = f"Modalità Eco ({pct:.0f}%): concorrenza ridotta a 1, esclusi carichi pesanti e sogni" if pct else "Modalità Eco"
    else:  # PROFILE_BATTERY_CRITICAL
        multiplier = 0.05
        max_concurrent = 1
        allow_heavy_gpu = False
        allow_dreams = False
        degraded = True
        desc = f"BATTERIA CRITICA ({pct:.0f}% < {THRESHOLD_CRITICAL_PCT:.0f}%): rifiuto carichi non-vitali per prevenire spegnimento" if pct else "Batteria critica"

    return {
        "profile": profile,
        "ac_line": ac_line,
        "battery_pct": pct,
        "charging": charging,
        "discharging": discharging,
        "is_battery": is_battery,
        "capacity_multiplier": multiplier,
        "max_concurrent": max_concurrent,
        "allow_heavy_gpu": allow_heavy_gpu,
        "allow_dreams": allow_dreams,
        "degraded": degraded,
        "description": desc,
    }


def evaluate_task_admission(
    power_info: Optional[Dict[str, Any]],
    task_type: str = TASK_STANDARD_INFERENCE,
    any_ac_in_mesh: bool = True,
) -> Dict[str, Any]:
    """Valuta se il nodo locale deve accettare, deviare, differire o rifiutare un task.

    Ritorna:
        {
            "admitted": bool,
            "action": "allow" | "divert" | "defer" | "reject",
            "profile": str,
            "reason": str
        }
    """
    profile_data = get_power_profile(power_info)
    profile = profile_data["profile"]
    ac_line = profile_data["ac_line"]
    pct = profile_data["battery_pct"] or 50.0

    # 1. Rete AC: esecuzione sempre permessa al 100%
    if profile == PROFILE_GRID_AC:
        return {
            "admitted": True,
            "action": "allow",
            "profile": profile,
            "reason": "Alimentazione di rete stabile (AC): task autorizzato a piena potenza.",
        }

    # 2. Batteria Critica (< 20%): rifiuto assoluto tranne triage ultra-leggero di sopravvivenza
    if profile == PROFILE_BATTERY_CRITICAL:
        if task_type == TASK_LIGHT_INFERENCE:
            return {
                "admitted": True,
                "action": "allow",
                "profile": profile,
                "reason": "Batteria critica: autorizzato solo triage sub-50ms di emergenza.",
            }
        return {
            "admitted": False,
            "action": "reject",
            "profile": profile,
            "reason": f"Rifiuto preventivo: batteria al {pct:.0f}% inferiore alla soglia critica ({THRESHOLD_CRITICAL_PCT:.0f}%).",
        }

    # 3. Task grafici / diffusion pesanti (ComfyUI)
    if task_type == TASK_HEAVY_GPU:
        if not ac_line:
            return {
                "admitted": False,
                "action": "divert" if any_ac_in_mesh else "defer",
                "profile": profile,
                "reason": "Carico grafico pesante (diffusion/ComfyUI) vietato a batteria; deviato su nodi AC o differito.",
            }

    # 4. Consolidamento sogni notturno (Dream Loop)
    if task_type in (TASK_DREAM_CONSOLIDATION, TASK_GRAPHIFY_INDEXING):
        if not ac_line:
            return {
                "admitted": False,
                "action": "defer",
                "profile": profile,
                "reason": "Attività di background differibile: sospesa in assenza di alimentazione da rete elettrica.",
            }

    # 5. Inferenza standard (LLM chat / code sandbox)
    if profile == PROFILE_BATTERY_ECO:
        if any_ac_in_mesh:
            return {
                "admitted": False,
                "action": "divert",
                "profile": profile,
                "reason": f"Modalità Eco ({pct:.0f}%): carico deviato verso nodi alimentati da presa elettrica.",
            }
        else:
            return {
                "admitted": True,
                "action": "allow",
                "profile": profile,
                "reason": "Modalità Blackout: autorizzata inferenza essenziale a concorrenza unitaria.",
            }

    # 6. Profilo Battery Optimal (> 50%)
    if any_ac_in_mesh and task_type in (TASK_CODE_SANDBOX, TASK_HEAVY_GPU):
        return {
            "admitted": False,
            "action": "divert",
            "profile": profile,
            "reason": "Disponibili nodi AC nella mesh: task ad alto consumo energetico deviato.",
        }

    return {
        "admitted": True,
        "action": "allow",
        "profile": profile,
        "reason": f"Batteria sufficiente ({pct:.0f}%): inferenza autorizzata.",
    }


def should_defer_dream_cycle(power_info: Optional[Dict[str, Any]], any_ac_in_mesh: bool = True) -> Tuple[bool, str]:
    """Helper specializzato per il dream loop: True se il sogno deve essere rinviato per batteria."""
    res = evaluate_task_admission(power_info, task_type=TASK_DREAM_CONSOLIDATION, any_ac_in_mesh=any_ac_in_mesh)
    return (not res["admitted"], res["reason"])


def should_defer_image_generation(power_info: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
    """Helper specializzato per la generazione immagini ComfyUI: True se non alimentato da AC."""
    res = evaluate_task_admission(power_info, task_type=TASK_HEAVY_GPU, any_ac_in_mesh=False)
    return (not res["admitted"], res["reason"])


def assess_cluster_energy_status(telemetries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analisi olistica dell'energia del cluster per Doctor Mesh e Dashboard."""
    total_nodes = len(telemetries)
    ac_nodes = []
    batt_nodes = []
    critical_nodes = []

    for t in telemetries:
        hw = t.get("hardware", {})
        pwr = hw.get("power", {})
        label = t.get("alias") or (t.get("node_id", "?")[:8] + (" [Local]" if t.get("is_local") else ""))
        is_ac = pwr.get("ac_line", hw.get("ac_line", True))
        pct = pwr.get("battery_pct", hw.get("battery_pct"))

        profile_data = get_power_profile({
            "ac_line": is_ac,
            "battery_pct": pct,
            "is_battery": pwr.get("is_battery", pct is not None),
            "charging": pwr.get("charging", False),
        })

        if profile_data["profile"] == PROFILE_GRID_AC:
            ac_nodes.append({"label": label, "data": profile_data})
        else:
            batt_nodes.append({"label": label, "data": profile_data})
            if profile_data["profile"] == PROFILE_BATTERY_CRITICAL:
                critical_nodes.append({"label": label, "data": profile_data})

    any_ac = len(ac_nodes) > 0
    all_battery = (len(batt_nodes) == total_nodes) and total_nodes > 0

    if all_battery:
        regime = "blackout_cooperative"
        status = "warn" if critical_nodes else "notice"
        summary = (
            f"REGIME BLACKOUT: Tutti i {total_nodes} nodi operano a batteria. "
            "Carichi pesanti e consolidamento sogni congelati; carico ripartito per carica residua."
        )
    elif batt_nodes:
        regime = "mixed_grid_preference"
        status = "warn" if critical_nodes else "ok"
        summary = (
            f"RETE MISTA: {len(ac_nodes)} nodo/i a rete fissa AC, {len(batt_nodes)} a batteria. "
            "Traffico prioritario indirizzato sulla rete elettrica."
        )
    else:
        regime = "all_grid_ac"
        status = "ok"
        summary = "STABILE: Tutti i nodi sono alimentati da rete elettrica fissa (AC Line)."

    return {
        "regime": regime,
        "status": status,
        "summary": summary,
        "any_ac": any_ac,
        "ac_count": len(ac_nodes),
        "battery_count": len(batt_nodes),
        "critical_count": len(critical_nodes),
        "ac_nodes": [n["label"] for n in ac_nodes],
        "battery_nodes": [f"{n['label']} ({n['data']['battery_pct']:.0f}%)" if n['data']['battery_pct'] else n['label'] for n in batt_nodes],
        "critical_nodes": [n["label"] for n in critical_nodes],
    }
