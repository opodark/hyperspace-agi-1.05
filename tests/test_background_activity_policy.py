# SPDX-License-Identifier: Apache-2.0
import ast
from pathlib import Path


def _policy():
    source = (Path(__file__).resolve().parents[1] / "control-plane" / "main.py").read_text()
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "_background_allowed")
    scope = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "main.py", "exec"), scope)
    return scope[node.name]


def test_recent_webui_activity_blocks_even_during_night():
    assert not _policy()(last_activity=990, now=1000, night=True, idle_seconds=300)


def test_idle_period_allows_background_during_day():
    assert _policy()(last_activity=600, now=1000, night=False, idle_seconds=300)


def test_recent_activity_blocks_during_day():
    assert not _policy()(last_activity=990, now=1000, night=False, idle_seconds=300)
