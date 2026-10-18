# SPDX-License-Identifier: Apache-2.0
"""
Test di conformità e compatibilità per l'estensione Chrome 00MESH Local Bridge.
Verifica:
1. Manifest V3 valido, permessi host localhost, service worker e popup.
2. Presenza di tutti i componenti UI, logica e icone.
3. Compatibilità del protocollo di registrazione (/web/register) e polling (/web/poll, /web/result).
"""

import json
from pathlib import Path
import pytest
from shared.web_node import WebNodeRegistry


EXTENSION_DIR = Path(__file__).resolve().parent.parent / "integrations" / "chrome-extension"


def test_chrome_extension_manifest():
    manifest_path = EXTENSION_DIR / "manifest.json"
    assert manifest_path.exists(), "manifest.json non trovato"

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("manifest_version") == 3
    assert data.get("name") == "00MESH Local Bridge — AI Node Connector"
    assert "background" in data
    assert data["background"].get("service_worker") == "background.js"
    assert "action" in data
    assert data["action"].get("default_popup") == "popup.html"

    # Permessi host obbligatori per bypassare CORS su Ollama e LM Studio
    host_perms = data.get("host_permissions", [])
    assert any("localhost" in p for p in host_perms)
    assert any("127.0.0.1" in p for p in host_perms)


def test_chrome_extension_files_and_spdx():
    files_to_check = [
        "background.js",
        "popup.html",
        "popup.js",
        "popup.css",
        "icons/icon16.png",
        "icons/icon48.png",
        "icons/icon128.png",
        "README.md",
    ]

    for rel_path in files_to_check:
        full_path = EXTENSION_DIR / rel_path
        assert full_path.exists(), f"File mancante: {rel_path}"

        if rel_path.endswith((".js", ".css")):
            first_lines = full_path.read_text(encoding="utf-8")[:100]
            assert "SPDX-License-Identifier: Apache-2.0" in first_lines, f"Header SPDX mancante in {rel_path}"


def test_extension_registration_compatibility_with_web_registry():
    """Verifica che il payload annunciato dall'estensione sia compatibile con WebNodeRegistry."""
    registry = WebNodeRegistry()
    node_id = "ext-test-12345"

    capabilities = ["summarize", "translate"]

    record = registry.register(
        node_id,
        capabilities=capabilities,
        label="Chrome Bridge (2 models)",
        browser="Chrome Extension 00MESH Local Bridge v1.0",
        limits={"concurrency": 1},
    )

    assert record["node_id"] == node_id
    assert "summarize" in record["capabilities"]
    assert record["browser"].startswith("Chrome Extension")

    # Accoda un task per questo nodo
    task = registry.enqueue(node_id, "summarize", {"model": "qwen3:8b", "prompt": "test"})
    assert task["task_id"] is not None

    # Esegui poll
    polled = registry.poll(node_id, timeout_s=1)
    assert polled is not None
    assert polled["task_id"] == task["task_id"]

    # Simula invio risultato
    completed = registry.complete(
        node_id,
        task["task_id"],
        ok=True,
        result={"content": "risposta test", "tokens_generated": 10},
        duration_ms=450,
    )
    assert completed["ok"] is True
    assert completed["result"]["tokens_generated"] == 10
