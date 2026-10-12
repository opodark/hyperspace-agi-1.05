#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Dispatcher di carichi computazionali distribuiti per i Web Node della mesh.

Permette a Mission Control, agenti autonomi, pipeline RAG e memory sync di
delegare compiti computazionali (embed_texts, summarize, validate_json, translate)
ai browser connessi al Web-Node, sfruttando le loro capacità WebGPU e multi-core.

Caratteristiche:
- Sharding Map-Reduce per batch di testi o documenti
- Matching intelligente delle capability dichiarate dai client
- Bilanciamento Round-Robin con monitoraggio delle code
- Hedged requests e fallback automatico trasparente
"""
from __future__ import annotations

import concurrent.futures
from typing import Any, Callable, Sequence

from shared.web_node import WebNodeRegistry, WebTaskRejected, WebNodeError


class NoWebNodeAvailable(RuntimeError):
    """Nessun web-node attivo con la capability richiesta."""


class WebDispatcher:
    def __init__(self, registry: WebNodeRegistry | None = None):
        self._registry = registry
        self._rr_index = 0

    @property
    def registry(self) -> WebNodeRegistry:
        if self._registry is not None:
            return self._registry
        try:
            from cp.webnode import web_registry
            return web_registry
        except ImportError:
            raise RuntimeError("WebNodeRegistry non disponibile")

    def capable_nodes(self, capability: str) -> list[dict]:
        """Restituisce i nodi attivi che hanno dichiarato la capability specificata."""
        all_nodes = self.registry.nodes()
        return [n for n in all_nodes if capability in n.get("capabilities", [])]

    def has_capability(self, capability: str) -> bool:
        """Indica se c'è almeno un web-node attivo con tale capability."""
        return len(self.capable_nodes(capability)) > 0

    def select_node(self, capability: str) -> str:
        """Seleziona un nodo idoneo tramite round-robin bilanciato."""
        nodes = self.capable_nodes(capability)
        if not nodes:
            raise NoWebNodeAvailable(f"Nessun web-node attivo supporta '{capability}'")
        self._rr_index = (self._rr_index + 1) % len(nodes)
        return nodes[self._rr_index]["node_id"]

    def dispatch_task(
        self,
        task_type: str,
        payload: dict,
        *,
        timeout_s: float = 20.0,
        node_id: str | None = None,
        constraints: dict | None = None,
        fallback_fn: Callable[[dict], Any] | None = None,
    ) -> dict:
        """Invia un singolo task a un web node e attende il risultato.

        Se nessun nodo è disponibile o il nodo fallisce/scade, esegue fallback_fn se fornita.
        """
        target_node = node_id or None
        if not target_node:
            try:
                target_node = self.select_node(task_type)
            except NoWebNodeAvailable:
                if fallback_fn is not None:
                    return {"ok": True, "result": fallback_fn(payload), "source": "fallback", "node_id": None}
                raise

        try:
            task = self.registry.enqueue(target_node, task_type, payload, constraints=constraints)
            task_id = task["task_id"]
        except (WebTaskRejected, WebNodeError) as err:
            if fallback_fn is not None:
                return {"ok": True, "result": fallback_fn(payload), "source": "fallback", "error": str(err)}
            return {"ok": False, "error": str(err), "source": "web-node"}

        result_record = self.registry.wait_for_result(task_id, timeout_s=timeout_s)
        if result_record is None or not result_record.get("ok"):
            err_msg = result_record.get("error") if result_record else f"timeout ({timeout_s}s)"
            if fallback_fn is not None:
                return {"ok": True, "result": fallback_fn(payload), "source": "fallback", "error": err_msg}
            return {"ok": False, "error": err_msg, "source": "web-node"}

        return {
            "ok": True,
            "result": result_record.get("result"),
            "source": "web-node",
            "node_id": target_node,
            "duration_ms": result_record.get("duration_ms"),
        }

    def dispatch_batch(
        self,
        task_type: str,
        payloads: Sequence[dict],
        *,
        timeout_s: float = 30.0,
        max_workers: int = 8,
        fallback_fn: Callable[[dict], Any] | None = None,
    ) -> list[dict]:
        """Distribuisce un batch di payload su più web-node in parallelo.

        Mantiene l'ordine dei payload originali nei risultati.
        """
        if not payloads:
            return []

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(max_workers, len(payloads))) as executor:
            futures = [
                executor.submit(
                    self.dispatch_task,
                    task_type,
                    p,
                    timeout_s=timeout_s,
                    fallback_fn=fallback_fn,
                )
                for p in payloads
            ]
            return [f.result() for f in futures]

    def embed_texts(
        self,
        texts: list[str],
        *,
        batch_size: int = 16,
        timeout_s: float = 25.0,
        fallback_fn: Callable[[list[str]], list[list[float]]] | None = None,
    ) -> list[list[float]] | None:
        """Batch embedding di testi delegato a WebGPU dei client (Transformers.js).

        Restituisce la lista di vettori float o None se fallito e nessun fallback.
        """
        if not texts:
            return []

        chunks = [texts[i:i + batch_size] for i in range(0, len(texts), batch_size)]
        payloads = [{"texts": c} for c in chunks]

        fb_chunk = (lambda p: fallback_fn(p["texts"])) if fallback_fn else None
        results = self.dispatch_batch("embed_texts", payloads, timeout_s=timeout_s, fallback_fn=fb_chunk)

        combined_embeddings = []
        for res in results:
            if not res.get("ok"):
                return None
            val = res.get("result")
            embs = val.get("embeddings") if isinstance(val, dict) else val
            if isinstance(embs, list):
                combined_embeddings.extend(embs)
            else:
                return None
        return combined_embeddings
