#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
scripts/sun_power_swarm_rd_1h.py — HyperSpace Solar Power 1-Hour Swarm R&D Engine

Spinge la ricerca e sviluppo continua per 1 ora (3600s) distribuendo il carico su tutto il cluster:
- ASUS V16 (100.64.31.18): inferenze pesanti Flint 40B NVFP4 e LFM 24B MoE
- HP OMEN 16 (100.104.238.125): esecuzione distillazione modelli veloci e onirica
- Mac M5 (Hub locale): validazione AST, indicizzazione albero di ricerca, sintesi AGI
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.agi_research_engine import AGIResearchEngine, RESEARCH_PILLARS
from scripts.omen_allnight_sovereign import execute_omen_prompt, run_nightly_dreams

LOG_DIR = ROOT / "data" / "research"
LOG_DIR.mkdir(parents=True, exist_ok=True)
SESSION_LOG = LOG_DIR / "sun_power_rd_1h.log"
SUMMARY_FILE = LOG_DIR / "sun_power_rd_summary.json"


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("SolarPowerSwarmRD")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # File handler
    fh = logging.FileHandler(SESSION_LOG, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


def run_1h_swarm_research(duration_seconds: int = 3600, cycle_pause: int = 15):
    logger = setup_logger()
    logger.info("=" * 70)
    logger.info("☀️ AVVIO SESSIONE R&D SOLARE 1 ORA (HYPERSPACE MULTI-NODE SWARM)")
    logger.info(f"Durata pianificata: {duration_seconds}s (~{round(duration_seconds / 60, 1)} min)")
    logger.info("Nodi coinvolti: Mac M5 (Hub), HP OMEN 16 (100.104.238.125), ASUS V16 (100.64.31.18)")
    logger.info("=" * 70)

    start_time = time.time()
    end_time = start_time + duration_seconds
    engine = AGIResearchEngine()

    cycles_completed = 0
    ast_valid_count = 0
    records = []

    pillar_index = 0
    total_pillars = len(RESEARCH_PILLARS)

    while time.time() < end_time:
        cycle_num = cycles_completed + 1
        remaining_s = max(0, int(end_time - time.time()))
        pillar = RESEARCH_PILLARS[pillar_index % total_pillars]
        pillar_id = pillar["id"]
        pillar_domain = pillar["domain"]

        logger.info(
            f"🔄 [Ciclo {cycle_num}] Avvio studio: {pillar_id} ({pillar_domain}) | Tempo residuo: {remaining_s}s"
        )

        cycle_start = time.perf_counter()
        try:
            # 1. Esegui ciclo di studio R&D distribuito (ASUS 40B/24B o OMEN)
            record = engine.execute_study_cycle(
                pillar_id=pillar_id,
                omen_executor_fn=execute_omen_prompt,
            )
            elapsed = round(time.perf_counter() - cycle_start, 2)
            is_valid = bool(record.get("ast_valid"))
            model_used = record.get("model_used") or record.get("model", "unknown")
            proto_name = record.get("prototype_file") or record.get("prototype", "none")

            if is_valid:
                ast_valid_count += 1

            logger.info(
                f"✓ [Ciclo {cycle_num}] Completato in {elapsed}s | Modello: {model_used} | "
                f"AST Valid: {is_valid} | Prototipo: {proto_name}"
            )

            records.append({
                "cycle": cycle_num,
                "pillar_id": pillar_id,
                "domain": pillar_domain,
                "elapsed_s": elapsed,
                "model": model_used,
                "ast_valid": is_valid,
                "prototype": proto_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # 2. Ogni 2 cicli, esegui anche un'esplorazione onirica di Anna
            if cycle_num % 2 == 0:
                try:
                    logger.info("🌙 [Anna Onirica] Esecuzione ciclo onirico e riflessione poetica...")
                    dream_res = run_nightly_dreams()
                    dreams_count = len(dream_res.get("dreams", []))
                    logger.info(f"✓ [Anna Onirica] Sogni consolidati: {dreams_count}")
                except Exception as exc_dream:
                    logger.warning(f"⚠️ Errore durante ciclo onirico: {exc_dream}")

        except Exception as exc:
            logger.error(f"❌ [Ciclo {cycle_num}] Errore durante lo studio di {pillar_id}: {exc}", exc_info=True)

        cycles_completed += 1
        pillar_index += 1

        # Aggiorna il sommario persistente
        summary_data = {
            "session_start": datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat(),
            "last_update": datetime.now(timezone.utc).isoformat(),
            "target_duration_s": duration_seconds,
            "elapsed_total_s": round(time.time() - start_time, 1),
            "cycles_completed": cycles_completed,
            "ast_valid_count": ast_valid_count,
            "success_rate_pct": round((ast_valid_count / max(1, cycles_completed)) * 100, 1),
            "records": records,
        }
        try:
            with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
                json.dump(summary_data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        # Breve pausa termica tra cicli se c'è ancora tempo
        if time.time() + cycle_pause < end_time:
            time.sleep(cycle_pause)

    total_elapsed = round(time.time() - start_time, 1)
    logger.info("=" * 70)
    logger.info(
        f"🎉 SESSIONE R&D COMPLETATA: {cycles_completed} cicli eseguiti ({ast_valid_count} AST validi) "
        f"in {total_elapsed}s."
    )
    logger.info(f"Sommario salvato in: {SUMMARY_FILE}")
    logger.info("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sessione di Ricerca e Sviluppo Solare 1 Ora per HyperSpace Mesh")
    parser.add_argument("--duration", type=int, default=3600, help="Durata in secondi (default: 3600 = 1h)")
    parser.add_argument("--pause", type=int, default=15, help="Pausa termica fra i cicli in secondi (default: 15s)")
    args = parser.parse_args()

    run_1h_swarm_research(duration_seconds=args.duration, cycle_pause=args.pause)
