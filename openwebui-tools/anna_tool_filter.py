# SPDX-License-Identifier: Apache-2.0
"""
title: HyperSpace Anna — attiva i tool in Gemma
description: Rende disponibili i tool HyperSpace nelle chat Gemma.
version: 0.2.0
"""

# Managed by HyperSpace webui-tools-register.


class Filter:
    def inlet(self, body: dict) -> dict:
        """Aggiunge il tool prima che Open WebUI risolva le chiamate del modello."""
        model = str(body.get("model") or "")
        if model not in {
            "🕸️ huihui_ai/gemma-4-abliterated:12b",
            "🕸️ huihui_ai/gemma-4-abliterated:12b::macbook",
        }:
            return body
        ids = list(body.get("tool_ids") or [])
        for tool_id in ("server:hyperspace-files",):
            if tool_id not in ids:
                ids.append(tool_id)
        body["tool_ids"] = ids
        return body
