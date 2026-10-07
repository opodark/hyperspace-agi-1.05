# SPDX-License-Identifier: Apache-2.0
"""Le rotte notturne dei sogni: chi può chiamarle, e cosa NON può succedere.

Due cose vanno difese da qui, perché nessuna delle due si vede a occhio:

1. `POST /dreams/nightly/tick` fa sognare: deve restare dietro il token
   amministrativo di rete, e deve applicare **le stesse guardie** del loop
   (`_tick_sogni`), non una seconda copia che sogna due volte la stessa notte.
2. `INSTAGRAM_DREAM_PUBLISH_ENABLED=true` con la policy di default (sola lettura,
   nessuna allowlist) non pubblica niente. `docs/connectors.md` lo dichiara
   misurato a mano il 2026-10-01 e nota che **nessun test lo asserisce**: questo
   è quel test mancante.
"""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from shared.connector_policy import ConnectorPolicy  # noqa: E402


def functions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name: node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


class DreamNightlyRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cp = functions(ROOT / "control-plane" / "main.py")
        cls.source = (ROOT / "control-plane" / "main.py").read_text(encoding="utf-8")

    def test_tick_route_requires_the_network_admin_token(self):
        fonte = ast.unparse(self.cp["dream_nightly_tick"])
        self.assertIn("_network_admin_error", fonte)
        self.assertIn("_tick_sogni", fonte)

    def test_monitor_route_reads_and_never_dreams(self):
        fonte = ast.unparse(self.cp["dream_nightly_status"])
        self.assertIn("_sogni_stato", fonte)
        self.assertNotIn("_tick_sogni", fonte)

    def test_loop_and_scheduler_share_one_copy_of_the_guards(self):
        tick = ast.unparse(self.cp["_tick_sogni"])
        self.assertIn("_decisione_sogno", tick)
        self.assertNotIn("choose_author", tick)
        self.assertIn("_tick_sogni", ast.unparse(self.cp["dream_loop"]))

    def test_the_detailed_journal_is_written_at_every_stage(self):
        for fase in ("scritto", "sketch", "disegnato", "pubblicato", "fallito",
                     "scartato", "saltato"):
            self.assertIn(f'fase="{fase}"', self.source, f"manca la fase {fase} nel codice")
        self.assertIn("salto_da_scrivere(", self.source)


class InstagramDreamPublishPolicyTests(unittest.TestCase):
    def test_default_policy_mutes_the_dream_publish_even_with_the_flag_on(self):
        policy = ConnectorPolicy.from_env({"INSTAGRAM_DREAM_PUBLISH_ENABLED": "true"})
        self.assertTrue(policy.read_only)
        self.assertFalse(policy.write_allowed("instagram", "instagram_publish_image",
                                              write=True))
        riga = policy.annotate([{"name": "instagram",
                                 "write_tools": ["instagram_publish_image"]}])[0]
        self.assertEqual(riga["write_tools_exposed"], [])
        self.assertEqual(riga["write_tools_blocked"], ["instagram_publish_image"])

    def test_the_explicit_allowlist_unlocks_the_publish(self):
        policy = ConnectorPolicy.from_env({
            "CONNECTOR_READ_ONLY": "false",
            "CONNECTOR_WRITE_TOOLS": "instagram=instagram_publish_image"})
        self.assertFalse(policy.read_only)
        self.assertTrue(policy.write_allowed("instagram", "instagram_publish_image",
                                             write=True))
        self.assertFalse(policy.write_allowed("instagram", "instagram_send_message",
                                              write=True))

    def test_the_publish_path_goes_through_the_governed_connector_manager(self):
        """La pubblicazione non parla con Instagram: chiede al manager, che applica la policy."""
        fonte = ast.unparse(functions(ROOT / "control-plane" / "main.py")["_instagram_publish_voce"])
        self.assertIn("connector_manager.execute", fonte)
        self.assertIn("INSTAGRAM_DREAM_PUBLISH_ENABLED", fonte)
