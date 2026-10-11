# SPDX-License-Identifier: Apache-2.0
"""La vista pubblica della topologia mostra solo nodi vivi e non fa trapelare nulla.

shared/web_topology.py e' una proiezione pura: qui la si nutre con un registro
finto che contiene apposta tutto quello che NON deve uscire (endpoint interni,
indirizzi Tailscale, node_id completi, etichette e user agent dei visitatori).
"""
import json
import unittest

from shared.web_topology import public_topology

NOW = 1_800_000_000.0

SECRET_BITS = (
    "100.64.0.7", "tail453db3", "http://", "https://", "browser://",
    "a1b2c3d4e5f6", "Portatile di Alberto", "Mozilla/5.0",
)


def _registry():
    nodes = [
        {"node_id": "a1b2c3d4e5f6-mac", "status": "active", "tier": "hub",
         "endpoint": "http://100.64.0.7:8090", "public_endpoint": "https://mac.tail453db3.ts.net",
         "vram_gb": 16.4, "saturation": 0.37, "active_requests": 2,
         "last_seen": "2027-01-15T08:00:00Z", "alias": ""},
        {"node_id": "ffee-windows", "status": "active", "tier": "leaf",
         "endpoint": "http://100.64.0.9:8090", "vram_gb": 8, "saturation": 3,
         "last_seen": NOW - 4, "alias": "rtx5060"},
        {"node_id": "dead-node", "status": "unreachable", "endpoint": "http://100.64.0.12:8090"},
        {"node_id": "local-cp", "status": "active", "endpoint": "", "is_local": True},
        {"node_id": "web-xyz", "status": "active", "endpoint": "browser://web-xyz",
         "is_web_node": True, "label": "Portatile di Alberto"},
    ]
    per_node = [
        {"node_id": "a1b2c3d4e5f6-mac", "base_model": "qwen3-8b-abliterated-g8k"},
        {"node_id": "a1b2c3d4e5f6-mac", "base_model": "granite3.3-g8k"},
        {"node_id": "ffee-windows", "base_model": "qwen3-8b-abliterated-g8k"},
        {"node_id": "dead-node", "base_model": "ghost-model"},
    ]
    browsers = [{"node_id": "web-xyz", "label": "Portatile di Alberto",
                 "browser": "Mozilla/5.0 (Macintosh)", "capabilities": ["summarize", "validate_json"]}]
    callable_ids = {"a1b2c3d4e5f6-mac", "ffee-windows", "dead-node"}
    return nodes, per_node, browsers, callable_ids


class PublicTopologyTests(unittest.TestCase):
    def setUp(self):
        nodes, per_node, browsers, callable_ids = _registry()
        self.view = public_topology(
            nodes, per_node, browsers, callable_ids=callable_ids,
            aliases={"ffee-windows": "rtx5060"},
            hub_models=["qwen3-8b-abliterated-g8k", "llama3.2:3b"], now=NOW)

    def test_only_active_callable_machines_are_drawn(self):
        self.assertEqual(self.view["totals"]["machines"], 2)
        tiers = sorted(m["tier"] for m in self.view["machines"])
        self.assertEqual(tiers, ["hub", "leaf"])

    def test_unreachable_nodes_and_their_models_stay_out(self):
        self.assertNotIn("ghost-model", self.view["models"])

    def test_alias_wins_otherwise_an_opaque_stable_label(self):
        labels = {m["label"] for m in self.view["machines"]}
        self.assertIn("rtx5060", labels)
        other = (labels - {"rtx5060"}).pop()
        self.assertRegex(other, r"^nodo-[0-9a-f]{4}$")
        nodes, per_node, browsers, callable_ids = _registry()
        again = public_topology(nodes, per_node, browsers, callable_ids=callable_ids, now=NOW)
        self.assertIn(other, {m["label"] for m in again["machines"]})

    def test_unsafe_alias_is_not_echoed(self):
        nodes, per_node, browsers, callable_ids = _registry()
        view = public_topology(nodes, per_node, browsers, callable_ids=callable_ids,
                               aliases={"ffee-windows": "<script>alert(1)</script>"}, now=NOW)
        self.assertNotIn("<script>", json.dumps(view))

    def test_browsers_are_only_counted(self):
        self.assertEqual(self.view["browsers"], {"count": 1, "capabilities": ["summarize", "validate_json"]})

    def test_nothing_internal_leaks(self):
        blob = json.dumps(self.view)
        for secret in SECRET_BITS:
            with self.subTest(secret=secret):
                self.assertNotIn(secret, blob)
        for machine in self.view["machines"]:
            self.assertFalse({"endpoint", "public_endpoint", "node_id"} & set(machine))

    def test_load_and_vram_are_clamped_and_rounded(self):
        by_label = {m["label"]: m for m in self.view["machines"]}
        self.assertEqual(by_label["rtx5060"]["load"], 1.0)
        self.assertEqual(by_label["rtx5060"]["vram_gb"], 8)
        self.assertEqual(by_label["rtx5060"]["last_seen_s"], 4)

    def test_direct_hub_models_exclude_those_served_by_workers(self):
        self.assertEqual(self.view["hub"]["models"], ["llama3.2:3b"])
        self.assertEqual(self.view["totals"]["models"], 3)

    def test_empty_registry_is_an_honest_empty_view(self):
        view = public_topology([], [], [], callable_ids=set(), now=NOW)
        self.assertEqual(view["totals"], {"machines": 0, "models": 0, "browsers": 0})
        self.assertEqual(view["machines"], [])


if __name__ == "__main__":
    unittest.main()
