# SPDX-License-Identifier: Apache-2.0
"""Regressione (S24, 2026-10-31): il nodo mobile vedeva "0 peer attivi su 0".

Causa: `_discover_peers_from_registry` provava solo REGISTRY_URL/
REGISTRY_PUBLIC_URL, e quel registry elencava un solo nodo con endpoint
interno a Docker (`http://node-1:8084`), irraggiungibile dal telefono. I
nodi veri (OMEN, Mac, nodi browser) stanno nel control-plane (`/nodes/
active`), mai interrogato dal nodo mobile. `_nodes_from_active_response`
normalizza le due forme di risposta (registry: `{"nodes": [...]}` con
`public_address`; control-plane: lista grezza con `endpoint`) così lo
stesso discovery può usare entrambe le fonti.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NODE_MAIN = ROOT / "node" / "main.py"


def _nodes_from_active_response():
    """Estratta via AST, come cp_source: `node/main.py` non si importa (serve
    fastapi/httpx e tocca DATA_DIR al modulo-livello)."""
    albero = ast.parse(NODE_MAIN.read_text(encoding="utf-8"))
    nodo = next(n for n in albero.body
                if isinstance(n, ast.FunctionDef) and n.name == "_nodes_from_active_response")
    scope: dict = {}
    exec(compile(ast.Module(body=[nodo], type_ignores=[]), "node_main", "exec"), scope)
    return scope["_nodes_from_active_response"]


def test_registry_shape_with_nodes_key_and_public_address():
    fn = _nodes_from_active_response()
    data = {"nodes": [
        {"node_id": "abc", "public_address": "http://node-1:8084"},
        {"node_id": "def", "public_address": ""},
    ]}
    out = fn(data)
    assert out == [
        {"node_id": "abc", "public_address": "http://node-1:8084"},
        {"node_id": "def", "public_address": ""},
    ]


def test_control_plane_shape_flat_list_with_endpoint():
    fn = _nodes_from_active_response()
    data = [
        {"node_id": "omen", "endpoint": "http://100.104.238.125:8081"},
        {"node_id": "mac", "endpoint": "http://100.81.234.102:8080"},
    ]
    out = fn(data)
    assert out == [
        {"node_id": "omen", "public_address": "http://100.104.238.125:8081"},
        {"node_id": "mac", "public_address": "http://100.81.234.102:8080"},
    ]


def test_unrecognized_shape_yields_no_nodes():
    fn = _nodes_from_active_response()
    assert fn({"unexpected": True}) == []
    assert fn(None) == []
