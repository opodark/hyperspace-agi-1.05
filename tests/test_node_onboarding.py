#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""tests/test_node_onboarding.py.

Suite di verifica per il tool di onboarding e ricostruzione nodi V2 (scripts/node_onboarding.py):
1. Riconoscimento hardware e raccomandazione profilo (NVIDIA -> compute, Darwin -> dev, ARM/Android -> edge, Linux -> hub).
2. Generazione del piano di configurazione e diff rispetto a .env esistente.
3. Riconciliazione non distruttiva del file .env (preservazione commenti, chiavi custom, ordine).
4. Scrittura del file .env in UTF-8 senza BOM (compatibilità Windows PowerShell 5.1 / Docker Compose).
5. Servizi Docker e Host previsti per ciascun profilo architetturale.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.node_onboarding import (
    NodeOnboarder,
    read_env_file,
    reconcile_env_content,
    recommend_profile,
)


class TestNodeOnboarding(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.env_path = self.tmp_path / ".env"

    def tearDown(self):
        self.tmp.cleanup()

    def test_recommend_profile_nvidia_gpu(self):
        """Un sistema con GPU NVIDIA discreta e VRAM >= 6 GB riceve il profilo compute."""
        hw = {
            "os": "Windows",
            "gpu_name": "NVIDIA GeForce RTX 3060 Laptop GPU",
            "vram_total_gb": 8.0,
            "ram_total_gb": 48.0,
        }
        self.assertEqual(recommend_profile(hw), "compute")

    def test_recommend_profile_darwin_apple_silicon(self):
        """Un Mac Apple Silicon riceve il profilo dev workstation."""
        hw = {
            "os": "Darwin",
            "gpu_name": "Apple Silicon Unified Memory",
            "vram_total_gb": 16.0,
            "ram_total_gb": 16.0,
        }
        self.assertEqual(recommend_profile(hw), "dev")

    def test_recommend_profile_android_mobile(self):
        """Un dispositivo mobile Android o ARM embedded riceve il profilo edge."""
        hw = {
            "os": "Android",
            "gpu_name": "Adreno 750",
            "vram_total_gb": 0.0,
            "ram_total_gb": 12.0,
        }
        self.assertEqual(recommend_profile(hw), "edge")

    def test_recommend_profile_generic_linux_server(self):
        """Un server Linux senza GPU discreta dedicata riceve il profilo hub."""
        hw = {
            "os": "Linux",
            "gpu_name": "unknown",
            "vram_total_gb": 0.0,
            "ram_total_gb": 32.0,
        }
        self.assertEqual(recommend_profile(hw), "hub")

    def test_reconcile_env_content_preserves_custom_and_updates_target(self):
        """Riconcilia le variabili target senza cancellare personalizzazioni locali né commenti."""
        existing_lines = [
            "# HyperSpace custom configuration",
            "CUSTOM_SECRET=my_secret_token_123",
            "PUBLIC_ENDPOINT=https://custom.tunnel.io",
            "VRAM_GB=0",
        ]
        existing_vars = {
            "CUSTOM_SECRET": "my_secret_token_123",
            "PUBLIC_ENDPOINT": "https://custom.tunnel.io",
            "VRAM_GB": "0",
        }
        target_vars = {
            "VRAM_GB": "8",
            "NODE_TIER": "hub",
            "COMFYUI_URL": "http://localhost:8188",
        }

        reconciled = reconcile_env_content(existing_lines, existing_vars, target_vars)

        # 1. Commento preservato
        self.assertIn("# HyperSpace custom configuration", reconciled)
        # 2. Chiave custom preservata
        self.assertIn("CUSTOM_SECRET=my_secret_token_123", reconciled)
        self.assertIn("PUBLIC_ENDPOINT=https://custom.tunnel.io", reconciled)
        # 3. Chiave esistente aggiornata al nuovo valore
        self.assertIn("VRAM_GB=8", reconciled)
        self.assertNotIn("VRAM_GB=0", reconciled)
        # 4. Nuove chiavi aggiunte
        self.assertIn("NODE_TIER=hub", reconciled)
        self.assertIn("COMFYUI_URL=http://localhost:8188", reconciled)

    def test_node_onboarder_generate_plan_compute(self):
        """Genera il piano di onboarding per il profilo compute incorporando la VRAM rilevata."""
        mock_hw = {
            "os": "Windows",
            "gpu_name": "NVIDIA GeForce RTX 3060",
            "vram_total_gb": 8.0,
            "ram_total_gb": 32.0,
            "cpu_count": 16,
        }
        with patch("scripts.node_onboarding.get_system_hardware", return_value=mock_hw):
            onboarder = NodeOnboarder(repo_root=self.tmp_path, env_path=self.env_path)
            plan = onboarder.generate_plan("compute")

            self.assertEqual(plan["profile"], "compute")
            self.assertEqual(plan["recommended_profile"], "compute")
            self.assertEqual(plan["target_variables"]["VRAM_GB"], "8")
            self.assertEqual(plan["target_variables"]["COMFYUI_URL"], "http://localhost:8188")
            self.assertIn("node-1", plan["services_to_run"]["docker"])
            self.assertTrue(any("ComfyUI" in s for s in plan["services_to_run"]["host"]))

    def test_node_onboarder_generate_plan_dev(self):
        """Genera il piano per il profilo dev con token MCP per OpenWork e OpenCode."""
        mock_hw = {
            "os": "Darwin",
            "gpu_name": "Apple Silicon Unified Memory",
            "vram_total_gb": 16.0,
            "ram_total_gb": 16.0,
            "cpu_count": 10,
        }
        with patch("scripts.node_onboarding.get_system_hardware", return_value=mock_hw):
            onboarder = NodeOnboarder(repo_root=self.tmp_path, env_path=self.env_path)
            plan = onboarder.generate_plan("dev")

            self.assertEqual(plan["profile"], "dev")
            self.assertEqual(plan["target_variables"]["MEMORY_BACKEND"], "hermes")
            self.assertIn("hyperspace_openwork_local_client_token_32chars", plan["target_variables"]["MCP_CLIENTS"])
            self.assertIn("code-sandbox", plan["services_to_run"]["docker"])
            self.assertTrue(any("OpenWork" in s for s in plan["services_to_run"]["host"]))

    def test_node_onboarder_apply_plan_utf8_no_bom(self):
        """La scrittura di .env avviene in UTF-8 senza byte-order-mark (BOM)."""
        mock_hw = {"os": "Linux", "gpu_name": "unknown", "vram_total_gb": 0.0}
        with patch("scripts.node_onboarding.get_system_hardware", return_value=mock_hw):
            onboarder = NodeOnboarder(repo_root=self.tmp_path, env_path=self.env_path)
            plan = onboarder.generate_plan("hub")
            ok = onboarder.apply_plan(plan)
            self.assertTrue(ok)
            self.assertTrue(self.env_path.is_file())

            raw_bytes = self.env_path.read_bytes()
            # Non deve iniziare con il BOM UTF-8 (\xef\xbb\xbf)
            self.assertFalse(raw_bytes.startswith(b"\xef\xbb\xbf"))
            self.assertIn(b"NODE_ROLE=mesh_authority", raw_bytes)


if __name__ == "__main__":
    unittest.main()
