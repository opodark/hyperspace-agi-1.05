# SPDX-License-Identifier: Apache-2.0
# tests/test_power_routing.py
"""Test di unità per la gestione energetica (Power-Aware Routing & Mesh Resilience)."""

import json
import shutil
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CP_PATH = ROOT / "control-plane"
if str(CP_PATH) not in sys.path:
    sys.path.insert(0, str(CP_PATH))

from shared.power_sense import detect_host_power, save_host_power
from shared.node_telemetry import get_system_hardware
import routing


class PowerRoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_save_and_detect_host_power_file(self):
        """Verifica scrittura e lettura atomica di host_power.json."""
        sample = {
            "ac_line": False,
            "battery_pct": 74.0,
            "is_battery": True,
            "charging": False,
            "discharging": True,
        }
        saved_file = save_host_power(sample, data_dir=self.tmp_dir)
        self.assertTrue(saved_file.exists())

        loaded = detect_host_power(data_dir=self.tmp_dir)
        self.assertFalse(loaded["ac_line"])
        self.assertEqual(loaded["battery_pct"], 74.0)
        self.assertTrue(loaded["is_battery"])
        self.assertIn("file:", loaded["source"])

    def test_get_system_hardware_includes_power(self):
        """get_system_hardware include la sezione power e le relative chiavi veloci."""
        hw = get_system_hardware()
        self.assertIn("power", hw)
        self.assertIn("ac_line", hw)
        self.assertIsInstance(hw["ac_line"], bool)

    def test_routing_favors_ac_node_over_battery_node(self):
        """Quando un nodo è a presa (AC) e uno a batteria, il nodo a presa ha uno score energetico nettamente superiore."""
        node_ac = {
            "node_id": "laptop_plugged",
            "vram_gb": 8.0,
            "tier": "hub",
            "uptime_s": 3600,
            "ac_line": True,
            "battery_pct": 100.0,
            "power": {"ac_line": True, "battery_pct": 100.0},
        }
        node_batt = {
            "node_id": "laptop_on_battery",
            "vram_gb": 8.0,
            "tier": "hub",
            "uptime_s": 3600,
            "ac_line": False,
            "battery_pct": 60.0,
            "power": {"ac_line": False, "battery_pct": 60.0},
        }

        weights = {"vram": 0.5, "load": 0.2, "tier": 0.1, "uptime": 0.1, "backend": 0.1, "power": 0.4}

        sig_ac = routing.extract_signal(node_ac, None)
        sig_batt = routing.extract_signal(node_batt, None)

        sigs = routing.rank_signals([sig_ac, sig_batt], weights)

        # Il nodo a rete deve avere power_s == 1.0
        self.assertEqual(sig_ac["power_s"], 1.0)
        # Il nodo a batteria con presenza di nodo AC riceve penalità progressiva (< 0.50)
        self.assertLessEqual(sig_batt["power_s"], 0.50)

        score_ac, breakdown_ac = routing.compute_score(sig_ac, weights)
        score_batt, breakdown_batt = routing.compute_score(sig_batt, weights)

        # Il punteggio strutturale del nodo collegato alla presa deve vincere
        self.assertGreater(score_ac, score_batt)
        self.assertGreater(breakdown_ac["power_s"], breakdown_batt["power_s"])

    def test_routing_blackout_distributes_by_remaining_charge(self):
        """Durante un blackout (tutti a batteria), il carico viene bilanciato in base alla carica residua."""
        node_batt_high = {
            "node_id": "laptop_80pct",
            "vram_gb": 8.0,
            "tier": "hub",
            "ac_line": False,
            "battery_pct": 80.0,
            "power": {"ac_line": False, "battery_pct": 80.0},
        }
        node_batt_low = {
            "node_id": "laptop_30pct",
            "vram_gb": 8.0,
            "tier": "hub",
            "ac_line": False,
            "battery_pct": 30.0,
            "power": {"ac_line": False, "battery_pct": 30.0},
        }

        weights = {"vram": 0.5, "load": 0.2, "tier": 0.1, "uptime": 0.1, "backend": 0.1, "power": 0.4}

        sig_high = routing.extract_signal(node_batt_high, None)
        sig_low = routing.extract_signal(node_batt_low, None)

        sigs = routing.rank_signals([sig_high, sig_low], weights)

        # Nessun nodo ha la presa AC, quindi non c'è penalità AC vs Batt, ma proporzione di carica
        self.assertGreater(sig_high["power_s"], sig_low["power_s"])
        score_high, _ = routing.compute_score(sig_high, weights)
        score_low, _ = routing.compute_score(sig_low, weights)
        self.assertGreater(score_high, score_low)

    def test_routing_critical_battery_cutoff(self):
        """Un nodo con batteria critica (< 15%) viene marcato degraded e penalizzato drasticamente."""
        node_crit = {
            "node_id": "laptop_dying",
            "vram_gb": 8.0,
            "tier": "hub",
            "ac_line": False,
            "battery_pct": 10.0,
            "power": {"ac_line": False, "battery_pct": 10.0},
        }
        weights = {"vram": 0.5, "load": 0.2, "tier": 0.1, "uptime": 0.1, "backend": 0.1, "power": 0.4}

        sig = routing.extract_signal(node_crit, None)
        routing.rank_signals([sig], weights)

        self.assertLessEqual(sig["power_s"], 0.05)
        self.assertTrue(sig["degraded"])


if __name__ == "__main__":
    unittest.main()
