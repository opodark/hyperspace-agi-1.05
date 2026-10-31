# SPDX-License-Identifier: Apache-2.0
"""Regressione: Granite (e modelli simili) a volte mimano una tool call come
JSON "piatto" con chiave 'action' invece di 'function'/'name' + 'arguments'
annidati. Prima del fix, _extract_raw_tool_calls non riconosceva questo
formato: il modello descriveva business_create_document a parole, nessun PDF
veniva generato, e il bot Telegram di Vittoria non aveva nulla da allegare.

Trovato durante un test di consolidamento di Vittoria (bot + tool + skill):
una richiesta naturale di fattura ("Prepara una fattura...") produceva un
blocco ```json {"action": "business_create_document", ...}``` mai eseguito.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "control-plane"))

from cp.chat import _extract_raw_tool_calls  # noqa: E402


def test_flat_action_format_is_extracted_as_tool_call():
    content = (
        "Ecco la fattura:\n"
        "```json\n"
        "{\n"
        '  "action": "business_create_document",\n'
        '  "doc_type": "FATTURA",\n'
        '  "number": "FATT-TEST-999",\n'
        '  "items": [{"description": "Manodopera", "quantity": 10, "unit_price": 35}],\n'
        '  "withholding_tax_rate": 20\n'
        "}\n"
        "```"
    )
    cleaned, calls = _extract_raw_tool_calls(content)

    assert len(calls) == 1
    call = calls[0]
    assert call["function"]["name"] == "business_create_document"
    args = json.loads(call["function"]["arguments"])
    assert args["doc_type"] == "FATTURA"
    assert args["number"] == "FATT-TEST-999"
    assert args["withholding_tax_rate"] == 20
    assert "action" not in args
    assert "```" not in cleaned


def test_standard_function_name_format_still_works():
    """Il formato originale (chiave 'function'/'name' + 'arguments' annidati) non deve rompersi."""
    content = (
        "```json\n"
        '{"function": {"name": "web_search", "arguments": {"query": "prezzo rame al kg"}}}\n'
        "```"
    )
    _, calls = _extract_raw_tool_calls(content)
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "web_search"
    args = json.loads(calls[0]["function"]["arguments"])
    assert args["query"] == "prezzo rame al kg"


def test_plain_text_without_tool_call_is_untouched():
    content = "Il totale è di 530 euro IVA inclusa."
    cleaned, calls = _extract_raw_tool_calls(content)
    assert calls == []
    assert cleaned == content
