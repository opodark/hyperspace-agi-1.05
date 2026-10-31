# SPDX-License-Identifier: Apache-2.0
"""Registra la persona aziendale 'Vittoria' in Open WebUI come modello dedicato."""

import json
import os
import sqlite3
import sys
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.persona import PersonaStore

MODEL_ID = "vittoria"
MODEL_NAME = "Vittoria · Assistente PMI"
PERSONA_PATH = REPO_ROOT / "data" / "persona-vittoria.json"


def register_vittoria(db_path: str, base_model: str = "🕸️ flint:latest") -> bool:
    if not os.path.exists(PERSONA_PATH):
        raise FileNotFoundError(f"File persona non trovato: {PERSONA_PATH}")

    store = PersonaStore.load(str(PERSONA_PATH))
    sys_prompt = store.system_block(surface="business")

    db_file = Path(db_path)
    if not db_file.is_file():
        raise FileNotFoundError(f"Database WebUI non trovato: {db_path}")

    now = int(time.time())
    with sqlite3.connect(db_file, timeout=10) as db:
        admin_row = db.execute("SELECT id FROM user WHERE role = 'admin' LIMIT 1").fetchone()
        user_id = admin_row[0] if admin_row else "default-admin"

        # Se il base_model specificato non è fra i modelli disponibili, trova un fallback
        model_rows = [r[0] for r in db.execute("SELECT id FROM model").fetchall()]
        available_base = base_model if base_model in model_rows else None

        params = json.dumps({"system": sys_prompt})
        meta = json.dumps({
            "description": "Consulente operativa aziendale per PMI, botteghe e professionisti. Gestione preventivi, fatture, corrispondenza e scadenze.",
            "profile_image_url": "/static/favicon.png",
            "suggestion_prompts": [
                {
                    "title": ["Preventivo fornitura", "Falegnameria Rossi"],
                    "content": "Preparami un preventivo per una boiserie in rovere a 2.800€ e finitura a 450€ con IVA al 22% per lo Studio Architettura Bianchi."
                },
                {
                    "title": ["Fattura di acconto", "Nuova commessa"],
                    "content": "Preparami la fattura di acconto del 50% per la fornitura confermata da 3.250€ imponibile con IVA al 22%."
                },
                {
                    "title": ["Analisi sito fornitore", "Studio catalogo"],
                    "content": "Leggi il sito web https://example.com ed estrai i principali servizi e materiali offerti per predisporre il preventivo."
                },
                {
                    "title": ["Ricerca prezzi mercato", "Indagine web"],
                    "content": "Cerca sul web il costo medio al metro quadro per la fornitura e posa di parquet in rovere massello."
                }
            ]
        }, ensure_ascii=False)

        existing = db.execute("SELECT id FROM model WHERE id = ?", (MODEL_ID,)).fetchone()
        if existing:
            db.execute(
                "UPDATE model SET name = ?, base_model_id = ?, params = ?, meta = ?, updated_at = ?, is_active = 1 WHERE id = ?",
                (MODEL_NAME, available_base or base_model, params, meta, now, MODEL_ID)
            )
            print(f"Modello {MODEL_ID} aggiornato con successo in Open WebUI.")
        else:
            version_id = str(uuid.uuid4())
            db.execute(
                "INSERT INTO model (id, user_id, base_model_id, name, params, meta, updated_at, created_at, is_active, version_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (MODEL_ID, user_id, available_base or base_model, MODEL_NAME, params, meta, now, now, version_id)
            )
            print(f"Modello {MODEL_ID} registrato con successo in Open WebUI.")

    return True


if __name__ == "__main__":
    target_db = sys.argv[1] if len(sys.argv) > 1 else "/app/backend/data/webui.db"
    base = sys.argv[2] if len(sys.argv) > 2 else "🕸️ flint:latest"
    register_vittoria(target_db, base)
