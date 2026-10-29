# SPDX-License-Identifier: Apache-2.0
"""GBNF (GGML BNF) Grammar Generator & Constraint Enforcer per HyperSpace Mesh.

Ispirato al paradigma local-first di Atomic Agent:
vincola fisicamente il campionamento dei token dei modelli open-weight (Qwen, LFM, Flint)
in esecuzione su llama.cpp o endpoint compatibili, impedendo alla radice allucinazioni sintattiche,
JSON corrotti o deviazioni nelle chiamate dei tool.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Union


# Grammatiche GBNF canoniche per campionamento vincolato
GBNF_WS = 'ws ::= [ \\t\\n\\r]*\n'

GBNF_PRIMITIVES = (
    'string ::= "\\"" ([^"\\\\\\n] | "\\\\" ["\\\\/bfnrt] | "\\\\" "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F])* "\\""\n'
    'number ::= ("-"? [0-9]+ ("." [0-9]+)? ([eE] [-+]? [0-9]+)?)\n'
    'boolean ::= "true" | "false"\n'
    'null ::= "null"\n'
    'value ::= string | number | boolean | null | object | array\n'
    'array ::= "[" ws (value (ws "," ws value)*)? ws "]"\n'
    'object ::= "{" ws (pair (ws "," ws pair)*)? ws "}"\n'
    'pair ::= string ws ":" ws value\n'
)

GBNF_JSON_OBJECT = (
    'root ::= object\n'
    + GBNF_WS
    + GBNF_PRIMITIVES
)

GBNF_JSON_ARRAY = (
    'root ::= array\n'
    + GBNF_WS
    + GBNF_PRIMITIVES
)

GBNF_PYTHON_AST_PROPOSAL = (
    'root ::= "{" ws '
    '"\\"file_path\\"" ws ":" ws string ws "," ws '
    '"\\"reason\\"" ws ":" ws string ws "," ws '
    '"\\"code\\"" ws ":" ws string ws '
    '"}"\n'
    + GBNF_WS
    + GBNF_PRIMITIVES
)


class GBNFBuilder:
    """Generatore dinamico di grammatiche GBNF per schemi e tool call."""

    @classmethod
    def escape_gbnf_string(cls, text: str) -> str:
        """Esegue l'escape per stringhe costanti all'interno di regole GBNF."""
        return text.replace('\\', '\\\\').replace('"', '\\"')

    @classmethod
    def build_tool_call_grammar(cls, tools: List[Dict[str, Any]]) -> str:
        """Costruisce una grammatica GBNF rigorosa che forza l'output ad essere

        un singolo ToolCall o una lista di ToolCall validi tra quelli offerti:
        {"name": "<tool_name>", "arguments": {...}}
        """
        if not tools:
            return GBNF_JSON_OBJECT

        tool_rules: List[str] = []
        tool_identifiers: List[str] = []

        for idx, tool in enumerate(tools):
            func = tool.get("function", tool)
            name = func.get("name", f"tool_{idx}")
            tool_id = f"tool_{re.sub(r'[^a-zA-Z0-9_]', '_', name)}"
            tool_identifiers.append(tool_id)

            # Regola specifica per ciascun tool
            rule = (
                f'{tool_id} ::= "{{" ws '
                f'"\\"name\\"" ws ":" ws "\\"{cls.escape_gbnf_string(name)}\\"" ws "," ws '
                f'"\\"arguments\\"" ws ":" ws object ws "}}"'
            )
            tool_rules.append(rule)

        choice_rule = ' | '.join(tool_identifiers)
        single_or_list_rule = (
            f'single-call ::= {choice_rule}\n'
            f'call-list ::= "[" ws (single-call (ws "," ws single-call)*)? ws "]"\n'
            f'root ::= single-call | call-list\n'
        )

        return (
            single_or_list_rule
            + '\n'.join(tool_rules) + '\n'
            + GBNF_WS
            + GBNF_PRIMITIVES
        )

    @classmethod
    def build_schema_grammar(cls, properties: Dict[str, str], required: Optional[List[str]] = None) -> str:
        """Genera una grammatica GBNF a chiavi prefissate per formati strutturati.

        properties: dict di campo -> tipo ('string', 'number', 'boolean', 'object', 'array')
        """
        req_set = set(required or properties.keys())
        pair_rules = []
        for prop, ptype in properties.items():
            rule_type = ptype if ptype in ("string", "number", "boolean", "object", "array") else "value"
            pair_rules.append(f'"\\"{cls.escape_gbnf_string(prop)}\\"" ws ":" ws {rule_type}')

        # Costruisce la sequenza dei campi
        inner = ' ws "," ws '.join(pair_rules)
        root_rule = f'root ::= "{{" ws {inner} ws "}}"\n'
        return root_rule + GBNF_WS + GBNF_PRIMITIVES


def inject_gbnf_constraint(
    payload: Dict[str, Any],
    grammar: Optional[str] = None,
    backend: str = "llama.cpp",
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Inietta il vincolo grammaticale nel payload di inferenza.

    Supporta llama.cpp (parametro `grammar`), endpoint OpenAI-compatibili
    (`response_format: {"type": "json_object"}`) e Ollama options.
    """
    out = dict(payload)

    # Se non è passata una grammatica esplicita ma ci sono i tool, costruiscila
    if not grammar and tools:
        grammar = GBNFBuilder.build_tool_call_grammar(tools)
    elif not grammar:
        grammar = GBNF_JSON_OBJECT

    backend_norm = (backend or "").lower().strip()

    if "ollama" in backend_norm:
        # Ollama nativo usa `format: "json"`
        out["format"] = "json"
        options = dict(out.get("options") or {})
        # Alcuni build Ollama con custom mod accettano la grammatica nelle options
        options["grammar"] = grammar
        out["options"] = options
    elif "llama" in backend_norm or "cpp" in backend_norm or backend_norm == "local":
        out["grammar"] = grammar
        # Molte versioni di llama-server accettano anche response_format json
        out["response_format"] = {"type": "json_object"}
    else:
        # Standard OpenAI / vLLM
        out["response_format"] = {"type": "json_object"}

    return out
