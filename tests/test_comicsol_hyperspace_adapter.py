# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts/comicsol_hyperspace_adapter.py"
SPEC = importlib.util.spec_from_file_location("comicsol_adapter", MODULE_PATH)
ADAPTER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ADAPTER)


def test_hyperspace_plan_has_real_lettering_and_no_legacy_empty_sentinels():
    project = json.loads((Path(__file__).parents[1] / "data/control-plane/comics/hyperspace-memories-956e1ab5.json").read_text())
    story, characters, storyboard = ADAPTER.build_plan(project)
    assert story["title"] == "HyperSpace Memories"
    assert [item["id"] for item in characters["characters"]] == ["anna", "aurora"]
    assert len(storyboard["pages"]) == 2
    assert all(page["layout"] == "three-horizontal" for page in storyboard["pages"])
    text = [item for page in storyboard["pages"] for panel in page["panels"] for item in panel["text"]]
    assert any(item["kind"] == "dialogue" and item["speaker"] == "aurora" for item in text)
    assert all("Nessun testo" not in item["content"] for item in text)
