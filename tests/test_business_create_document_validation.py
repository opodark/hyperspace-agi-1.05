# SPDX-License-Identifier: Apache-2.0
"""Regressione: Flint 40B (tool call nativa, non mimata a testo) a volte
chiamava business_create_document per una FATTURA senza l'oggetto 'client'
(o con solo campi vuoti). Il PDF usciva con placeholder "Committente"
generico, niente P.IVA/CF, e il totale rifletteva una withholding_tax_rate
assente anche quando il testo del modello la citava. _handlers_nativi_105
ora rifiuta la generazione per una FATTURA senza client.name, invece di
produrre silenziosamente un documento fiscale incompleto.

Stesso schema di estrazione via AST di test_tool_passthrough.py: main.py
non si importa direttamente (avvia thread, Flask, Ollama...), si estrae e
si esegue solo la funzione interessata.
"""
import ast
import json
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests import cp_source  # noqa: E402


def _carica_handler(tmp_dir: str):
    albero = cp_source.albero()
    nodo = next(n for n in albero.body
                if isinstance(n, ast.FunctionDef) and n.name == "_handlers_nativi_105")
    _nomi_esterni = ("_tool_create_website", "_tool_website_status", "_tool_wayfinder_map",
                      "_tool_reel_prepare_project", "_reel_subject_fx_preview",
                      "_reel_subject_fx_status")
    scope = {
        "json": json, "os": os, "time": time, "datetime": datetime,
        "NIGHTLY_DEV_DATA_DIR": tmp_dir,
    }
    scope.update({nome: (lambda args: "") for nome in _nomi_esterni})
    exec(compile(ast.Module(body=[nodo], type_ignores=[]), "cp", "exec"), scope)
    return scope["_handlers_nativi_105"]()["business_create_document"]


def test_fattura_without_client_name_is_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        handler = _carica_handler(tmp)
        result = json.loads(handler({
            "doc_type": "FATTURA",
            "number": "FATT-TEST-REJECT",
            "items": [{"description": "Manodopera", "quantity": 1, "unit_price": 100}],
        }))
        assert result["ok"] is False
        assert "client.name" in result["error"]


def test_preventivo_without_client_name_still_works():
    """Un preventivo informale può restare generico: solo la FATTURA è bloccante."""
    with tempfile.TemporaryDirectory() as tmp:
        handler = _carica_handler(tmp)
        result = json.loads(handler({
            "doc_type": "PREVENTIVO",
            "number": "PREV-TEST-OK",
            "items": [{"description": "Manodopera", "quantity": 1, "unit_price": 100}],
        }))
        assert result["ok"] is True


def test_fattura_with_client_name_works():
    with tempfile.TemporaryDirectory() as tmp:
        handler = _carica_handler(tmp)
        result = json.loads(handler({
            "doc_type": "FATTURA",
            "number": "FATT-TEST-OK",
            "client": {"name": "Cliente Vero Srl", "vat_number": "IT12345678901"},
            "items": [{"description": "Manodopera", "quantity": 1, "unit_price": 100}],
        }))
        assert result["ok"] is True
