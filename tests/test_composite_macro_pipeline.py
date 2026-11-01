#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
tests/test_composite_macro_pipeline.py
Unit and integration tests per il motore di Macro-Workflow Compositi Concatenati.
Verifica:
- Esecuzione end-to-end della catena: Grafo -> Causal Dream -> Swarm -> Bio-Mesh -> Multimodale
- Predisposizione e integrazione per voce clonata Voicebox / Qwen ('voicebox:Albi ita@qwen')
- Self-healing topologico e allerta stigmergica feromonica
"""

import json
import unittest
from unittest.mock import patch

from shared.composite_macro_pipeline import CompositeMacroPipeline, MultimodalArtifactDescriptor


class TestCompositeMacroPipeline(unittest.TestCase):
    def setUp(self):
        self.pipeline = CompositeMacroPipeline(node_id="Mac_M5_Test")
        # Popola la memoria modulare con nodi tematici
        doc_id = self.pipeline.modular_intellect.store_experience(
            kind="document",
            content="Architettura AGI e Coscienza Sintetica Sovrana su Hardware Eterogeneo",
            refs=[],
        )
        self.pipeline.modular_intellect.store_experience(
            kind="note",
            content="Riflessione Anna: I cicli onirici notturni consolidano il lineage causale di rete",
            refs=[doc_id],
        )

    def test_chained_cognitive_cycle_execution(self):
        """Verifica la concatenazione completa dei 5 stadi cognitivi."""
        artifact = self.pipeline.run_chained_cognitive_cycle(
            theme="Coscienza Sintetica",
            max_hops=2,
            n_scenarios=4,
            style="watercolor",
            voice_profile="voicebox:Albi ita@qwen",
        )

        self.assertIsInstance(artifact, MultimodalArtifactDescriptor)
        self.assertIn("Macro-Workflow", artifact.title)
        self.assertTrue(len(artifact.narrative_text.strip()) > 0)
        self.assertIn("positive_prompt", artifact.visual_prompt)
        self.assertIn("typography", artifact.visual_prompt)

        # Verifica configurazione voce clonata dell'utente
        self.assertEqual(artifact.voice_config["voice"], "voicebox:Albi ita@qwen")
        self.assertEqual(artifact.voice_config["engine"], "qwen")
        self.assertEqual(artifact.voice_config["language"], "it")

        # Verifica metriche integrate dei piloni
        self.assertIsNotNone(artifact.causal_event_id)
        self.assertGreater(artifact.imagination_entropy, 0.0)
        self.assertGreater(artifact.mesh_entropy, 0.0)
        self.assertEqual(artifact.evidence_tier, "verified")

        # Verifica che il segnale sia stato depositato nello swarm
        gradients = self.pipeline.swarm.sense_gradient("cognitive_consolidation")
        self.assertGreaterEqual(len(gradients), 1)
        self.assertEqual(gradients[0]["node_id"], "Mac_M5_Test")

    def test_self_healing_mesh_action(self):
        """Verifica il concatenamento del circuito auto-riparante della mesh."""
        res = self.pipeline.execute_self_healing_mesh_action(
            incident_cause="vram_overload",
            affected_node="OMEN16",
        )

        self.assertEqual(res["status"], "mitigated")
        self.assertIn("causal_event_id", res)
        self.assertIn("stolen_cycles", res)
        self.assertGreater(res["mesh_entropy"], 0.0)

        # Verifica traccia causale nel DAG
        event = self.pipeline.causal_graph.get_event(res["causal_event_id"])
        self.assertIsNotNone(event)
        self.assertIn("vram_overload", event["cause_id"])

        # Verifica allerta nei feromoni
        alerts = self.pipeline.swarm.sense_gradient("mesh_incident_alert")
        self.assertEqual(len(alerts), 1)

    def test_artifact_serialization_and_voicebox_integration(self):
        """Verifica la serializzazione e la chiamata di sintesi verso Voicebox."""
        artifact = self.pipeline.run_chained_cognitive_cycle(
            theme="Autosufficienza Digitale",
            voice_profile="voicebox:Albi ita@qwen",
        )
        d = artifact.to_dict()
        json_str = json.dumps(d)
        self.assertIn("voicebox:Albi ita@qwen", json_str)

        # Test sintesi con mock di voicebox_client per isolamento test
        with patch("shared.voicebox_client.synthesize", return_value=b"RIFF_MOCK_WAV_BYTES"):
            audio = self.pipeline.synthesize_artifact_audio(artifact, use_cache=True)
            self.assertEqual(audio, b"RIFF_MOCK_WAV_BYTES")
            self.assertEqual(artifact.voice_config["status"], "synthesized")
            self.assertIsNotNone(artifact.audio_bytes)


if __name__ == "__main__":
    unittest.main()
