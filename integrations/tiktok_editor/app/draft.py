# SPDX-License-Identifier: Apache-2.0
"""Persistent single-user draft for the local Reel Editor."""
from __future__ import annotations

import json
import os
from pathlib import Path


def draft_path(data_dir: Path) -> Path:
    return data_dir / "draft.json"


def read_draft(data_dir: Path) -> dict:
    path = draft_path(data_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_draft(data_dir: Path, updates: dict) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    data = read_draft(data_dir)
    data.update(updates)
    path = draft_path(data_dir)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def valid_state(state: object) -> bool:
    if not isinstance(state, dict):
        return False
    try:
        return (Path(state["media_dir"]).is_dir()
                and Path(state["audio"]).is_file()
                and all((Path(state["media_dir"]) / m["name"]).is_file()
                        for m in state["metas"]))
    except (KeyError, TypeError, ValueError):
        return False
