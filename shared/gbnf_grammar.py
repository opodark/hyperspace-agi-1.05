# SPDX-License-Identifier: Apache-2.0
"""GBNF (GGML BNF) Grammar Generator & Schema Constraints per HyperSpace Mesh.

Ispirato al paradigma di campionamento vincolato di Atomic Agent:
- Per backend nativi llama.cpp / llama-server: genera e inietta grammatiche GBNF formali
  (parametro `grammar`) vincolando a livello token l'output.
- Per backend Ollama (>= 0.5): inietta Structured Outputs nativi via schema JSON nel
  parametro `format` (poiché Ollama standard ignora la sintassi GBNF nelle options).
- Per backend OpenAI-compatibili / vLLM: inietta `response_format: {"type": "json_schema"}`
  o `response_format: {"type": "json_object"}`.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Union


# Grammatiche GBNF canoniche per campionamento vincolato su llama.cpp
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
    """Generatore dinamico di grammatiche GBNF e schemi strutturati."""

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
        """Genera una grammatica GBNF per llama.cpp a chiavi prefissate."""
        pair_rules = []
        for prop, ptype in properties.items():
            rule_type = ptype if ptype in ("string", "number", "boolean", "object", "array") else "value"
            pair_rules.append(f'"\\"{cls.escape_gbnf_string(prop)}\\"" ws ":" ws {rule_type}')

        inner = ' ws "," ws '.join(pair_rules)
        root_rule = f'root ::= "{{" ws {inner} ws "}}"\n'
        return root_rule + GBNF_WS + GBNF_PRIMITIVES

    @classmethod
    def build_json_schema(cls, properties: Dict[str, str], required: Optional[List[str]] = None) -> Dict[str, Any]:
        """Genera un JSON Schema compatibile con gli Structured Outputs di Ollama e OpenAI."""
        schema_props = {}
        for prop, ptype in properties.items():
            norm_type = ptype if ptype in ("string", "number", "boolean", "object", "array", "integer") else "string"
            schema_props[prop] = {"type": norm_type}

        req = required if required is not None else list(properties.keys())
        return {
            "type": "object",
            "properties": schema_props,
            "required": req,
        }


def inject_gbnf_constraint(
    payload: Dict[str, Any],
    grammar: Optional[str] = None,
    json_schema: Optional[Dict[str, Any]] = None,
    backend: str = "llama.cpp",
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Inietta il vincolo strutturale/grammaticale nel payload in base al backend effettivo.

    - Ollama: usa `format: <json_schema>` (Structured Output nativo) o `format: "json"`.
    - llama.cpp / llama-server: usa il parametro nativo `grammar`.
    - OpenAI / vLLM: usa `response_format`.
    """
    out = dict(payload)
    backend_norm = (backend or "").lower().strip()

    # Se non è passata una grammatica ma ci sono i tool, costruiscila
    if not grammar and tools:
        grammar = GBNFBuilder.build_tool_call_grammar(tools)
    elif not grammar and not json_schema:
        grammar = GBNF_JSON_OBJECT

    if "ollama" in backend_norm:
        # Nota: Ollama standard non interpreta stringhe GBNF in options.
        # Per vincolare lo schema si passa direttamente il dizionario JSON Schema in 'format'.
        if json_schema:
            out["format"] = json_schema
        else:
            out["format"] = "json"

    elif "llama" in backend_norm or "cpp" in backend_norm or backend_norm == "local":
        if grammar:
            out["grammar"] = grammar
        out["response_format"] = {"type": "json_object"}

    else:
        # Standard OpenAI / vLLM
        if json_schema:
            out["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response_constraint", "schema": json_schema, "strict": True},
            }
        else:
            out["response_format"] = {"type": "json_object"}

    return out
