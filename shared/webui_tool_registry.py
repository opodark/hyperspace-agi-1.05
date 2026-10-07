# SPDX-License-Identifier: Apache-2.0
"""One-file custom tools with generated OpenAPI schemas."""

import importlib
import inspect
import json
import pkgutil
import re
from dataclasses import dataclass
from typing import get_args, get_origin


TOOLS = {}
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_loaded = False


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    function: object
    properties: dict
    required: list


def _schema(annotation):
    if annotation is str:
        return {"type": "string"}
    if annotation is int:
        return {"type": "integer"}
    if annotation is float:
        return {"type": "number"}
    if annotation is bool:
        return {"type": "boolean"}
    if get_origin(annotation) is list and len(get_args(annotation)) == 1:
        return {"type": "array", "items": _schema(get_args(annotation)[0])}
    raise TypeError(f"Tipo non supportato per un tool: {annotation!r}")


def tool(function=None, *, description=None):
    """Register a function as a WebUI tool; supported args: str/int/float/bool/list[T]."""
    def register(fn):
        name = fn.__name__
        if not NAME_RE.fullmatch(name):
            raise ValueError(f"Nome tool non valido: {name}")
        if name in TOOLS:
            raise ValueError(f"Tool duplicato: {name}")
        text = (description or inspect.getdoc(fn) or "").strip()
        if not text:
            raise ValueError(f"Aggiungi una descrizione al tool {name}")
        properties, required = {}, []
        for arg_name, param in inspect.signature(fn).parameters.items():
            if param.kind not in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY):
                raise TypeError(f"Argomento non supportato: {arg_name}")
            properties[arg_name] = _schema(param.annotation)
            if param.default is inspect.Parameter.empty:
                required.append(arg_name)
            else:
                properties[arg_name]["default"] = param.default
        TOOLS[name] = Tool(name, text, fn, properties, required)
        return fn
    return register(function) if function is not None else register


def load_tools():
    global _loaded
    if not _loaded:
        import shared.webui_custom_tools as package
        for item in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
            importlib.import_module(item.name)
        _loaded = True
    return TOOLS


def _matches(value, schema):
    kind = schema["type"]
    if kind == "string":
        return isinstance(value, str)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "array":
        return isinstance(value, list) and all(_matches(item, schema["items"]) for item in value)
    return False


def execute(name, args):
    selected = load_tools().get(name)
    if selected is None:
        raise KeyError(name)
    if not isinstance(args, dict):
        raise ValueError("Gli argomenti devono essere un oggetto JSON")
    unknown = set(args) - set(selected.properties)
    missing = set(selected.required) - set(args)
    if unknown or missing:
        raise ValueError(f"Argomenti non validi; mancanti={sorted(missing)}, sconosciuti={sorted(unknown)}")
    for key, value in args.items():
        if not _matches(value, selected.properties[key]):
            raise ValueError(f"Tipo non valido per {key}")
    result = selected.function(**args)
    try:
        json.dumps(result)
    except (TypeError, ValueError) as exc:
        raise TypeError("Il risultato del tool deve essere serializzabile in JSON") from exc
    return result
