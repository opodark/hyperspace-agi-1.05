#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Test per shared/web_dispatcher.py."""
import threading
import time
import unittest

from shared.web_dispatcher import NoWebNodeAvailable, WebDispatcher
from shared.web_node import WebNodeRegistry


class WebDispatcherTests(unittest.TestCase):
    def setUp(self):
        self.registry = WebNodeRegistry(
            max_nodes=10,
            max_queue=10,
            max_payload_bytes=64 * 1024,
            task_ttl_s=10,
            max_poll_s=2,
        )
        self.dispatcher = WebDispatcher(registry=self.registry)

    def test_capable_nodes_and_select(self):
        self.registry.register("node-a", capabilities=["summarize", "validate_json"])
        self.registry.register("node-b", capabilities=["embed_texts", "summarize"])

        summary_nodes = [n["node_id"] for n in self.dispatcher.capable_nodes("summarize")]
        self.assertEqual(sorted(summary_nodes), ["node-a", "node-b"])

        embed_nodes = [n["node_id"] for n in self.dispatcher.capable_nodes("embed_texts")]
        self.assertEqual(embed_nodes, ["node-b"])

        self.assertTrue(self.dispatcher.has_capability("embed_texts"))
        self.assertFalse(self.dispatcher.has_capability("translate"))

        with self.assertRaises(NoWebNodeAvailable):
            self.dispatcher.select_node("translate")

    def test_dispatch_task_success(self):
        self.registry.register("worker-1", capabilities=["embed_texts"])

        def worker_sim():
            task = self.registry.poll("worker-1", timeout_s=2)
            if task:
                self.registry.complete(
                    "worker-1",
                    task["task_id"],
                    ok=True,
                    result={"embeddings": [[0.1, 0.2, 0.3]]},
                    duration_ms=45,
                )

        t = threading.Thread(target=worker_sim)
        t.start()

        res = self.dispatcher.dispatch_task(
            "embed_texts",
            {"texts": ["ciao"]},
            timeout_s=3.0,
        )
        t.join()

        self.assertTrue(res["ok"])
        self.assertEqual(res["result"], {"embeddings": [[0.1, 0.2, 0.3]]})
        self.assertEqual(res["source"], "web-node")
        self.assertEqual(res["node_id"], "worker-1")

    def test_dispatch_task_fallback_when_no_node(self):
        # Nessun nodo registrato
        res = self.dispatcher.dispatch_task(
            "embed_texts",
            {"texts": ["test"]},
            timeout_s=1.0,
            fallback_fn=lambda p: {"embeddings": [[0.9, 0.9, 0.9]]},
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["source"], "fallback")
        self.assertEqual(res["result"], {"embeddings": [[0.9, 0.9, 0.9]]})

    def test_dispatch_batch_parallel(self):
        self.registry.register("worker-a", capabilities=["summarize"])

        def worker_loop():
            for _ in range(2):
                task = self.registry.poll("worker-a", timeout_s=2)
                if task:
                    self.registry.complete(
                        "worker-a",
                        task["task_id"],
                        ok=True,
                        result={"summary": f"sum-{task['payload'].get('doc_id')}"},
                    )

        t = threading.Thread(target=worker_loop)
        t.start()

        payloads = [{"doc_id": 1}, {"doc_id": 2}]
        results = self.dispatcher.dispatch_batch("summarize", payloads, timeout_s=3.0)
        t.join()

        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["ok"] for r in results))
        self.assertEqual(results[0]["result"]["summary"], "sum-1")
        self.assertEqual(results[1]["result"]["summary"], "sum-2")

    def test_embed_texts_helper(self):
        self.registry.register("embed-worker", capabilities=["embed_texts"])

        def worker():
            task = self.registry.poll("embed-worker", timeout_s=2)
            if task:
                self.registry.complete(
                    "embed-worker",
                    task["task_id"],
                    ok=True,
                    result={"embeddings": [[1.0, 2.0], [3.0, 4.0]]},
                )

        t = threading.Thread(target=worker)
        t.start()

        vectors = self.dispatcher.embed_texts(["a", "b"], batch_size=2, timeout_s=3.0)
        t.join()

        self.assertEqual(vectors, [[1.0, 2.0], [3.0, 4.0]])


if __name__ == "__main__":
    unittest.main()
