# SPDX-License-Identifier: Apache-2.0
# tests/test_power_policy.py
"""Test di unità per la formalizzazione della Power Policy (HyperSpace 1.05)."""

import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.power_policy import (
    PROFILE_GRID_AC,
    PROFILE_BATTERY_OPTIMAL,
    PROFILE_BATTERY_ECO,
    PROFILE_BATTERY_CRITICAL,
    TASK_LIGHT_INFERENCE,
    TASK_STANDARD_INFERENCE,
    TASK_HEAVY_GPU,
    TASK_DREAM_CONSOLIDATION,
    TASK_CODE_SANDBOX,
    classify_power_profile,
    get_power_profile,
    evaluate_task_admission,
    should_defer_dream_cycle,
    should_defer_image_generation,
    assess_cluster_energy_status,
)
from shared.dream_schedule import check_dream_power_guard


class TestPowerPolicy(unittest.TestCase):
    def test_classify_power_profile_grid_fixed(self):
        """Nodo desktop/server fisso sempre su rete AC."""
        prof = classify_power_profile(ac_line=True, is_battery=False)
        self.assertEqual(prof, PROFILE_GRID_AC)

    def test_classify_power_profile_laptop_plugged(self):
        """Laptop su presa di rete in carica attiva o con carica >= 90%."""
        prof_charging = classify_power_profile(ac_line=True, battery_pct=40.0, charging=True, is_battery=True)
        self.assertEqual(prof_charging, PROFILE_GRID_AC)

        prof_full = classify_power_profile(ac_line=True, battery_pct=95.0, charging=False, is_battery=True)
        self.assertEqual(prof_full, PROFILE_GRID_AC)

        # Se collegato ma non in carica e sotto il 90%, è battery_optimal
        prof_idle = classify_power_profile(ac_line=True, battery_pct=75.0, charging=False, is_battery=True)
        self.assertEqual(prof_idle, PROFILE_BATTERY_OPTIMAL)

    def test_classify_power_profile_battery_levels(self):
        """Classificazione in scarica sui 3 livelli batteria."""
        # > 50%
        prof_opt = classify_power_profile(ac_line=False, battery_pct=70.0, is_battery=True)
        self.assertEqual(prof_opt, PROFILE_BATTERY_OPTIMAL)

        # 20% - 50%
        prof_eco = classify_power_profile(ac_line=False, battery_pct=35.0, is_battery=True)
        self.assertEqual(prof_eco, PROFILE_BATTERY_ECO)

        # < 20%
        prof_crit = classify_power_profile(ac_line=False, battery_pct=15.0, is_battery=True)
        self.assertEqual(prof_crit, PROFILE_BATTERY_CRITICAL)

    def test_get_power_profile_multipliers_and_limits(self):
        """Verifica moltiplicatori di capacità e vincoli per ciascun profilo."""
        # Grid AC
        p_ac = get_power_profile({"ac_line": True, "is_battery": False})
        self.assertEqual(p_ac["profile"], PROFILE_GRID_AC)
        self.assertEqual(p_ac["capacity_multiplier"], 1.0)
        self.assertEqual(p_ac["max_concurrent"], 4)
        self.assertTrue(p_ac["allow_heavy_gpu"])
        self.assertTrue(p_ac["allow_dreams"])
        self.assertFalse(p_ac["degraded"])

        # Battery Eco
        p_eco = get_power_profile({"ac_line": False, "battery_pct": 35.0, "is_battery": True})
        self.assertEqual(p_eco["profile"], PROFILE_BATTERY_ECO)
        self.assertEqual(p_eco["capacity_multiplier"], 0.40)
        self.assertEqual(p_eco["max_concurrent"], 1)
        self.assertFalse(p_eco["allow_heavy_gpu"])
        self.assertFalse(p_eco["allow_dreams"])
        self.assertFalse(p_eco["degraded"])

        # Battery Critical
        p_crit = get_power_profile({"ac_line": False, "battery_pct": 12.0, "is_battery": True})
        self.assertEqual(p_crit["profile"], PROFILE_BATTERY_CRITICAL)
        self.assertEqual(p_crit["capacity_multiplier"], 0.05)
        self.assertTrue(p_crit["degraded"])

    def test_task_admission_grid_ac(self):
        """Su rete AC tutti i task sono autorizzati al 100%."""
        p_ac = {"ac_line": True, "is_battery": False}
        for task in (TASK_LIGHT_INFERENCE, TASK_STANDARD_INFERENCE, TASK_HEAVY_GPU, TASK_DREAM_CONSOLIDATION, TASK_CODE_SANDBOX):
            res = evaluate_task_admission(p_ac, task_type=task, any_ac_in_mesh=True)
            self.assertTrue(res["admitted"])
            self.assertEqual(res["action"], "allow")

    def test_task_admission_battery_critical(self):
        """Sotto il 20% di batteria solo light triage è ammesso; tutto il resto è rifiutato."""
        p_crit = {"ac_line": False, "battery_pct": 10.0, "is_battery": True}

        res_light = evaluate_task_admission(p_crit, task_type=TASK_LIGHT_INFERENCE)
        self.assertTrue(res_light["admitted"])
        self.assertEqual(res_light["action"], "allow")

        res_std = evaluate_task_admission(p_crit, task_type=TASK_STANDARD_INFERENCE)
        self.assertFalse(res_std["admitted"])
        self.assertEqual(res_std["action"], "reject")

        res_gpu = evaluate_task_admission(p_crit, task_type=TASK_HEAVY_GPU)
        self.assertFalse(res_gpu["admitted"])
        self.assertEqual(res_gpu["action"], "reject")

    def test_task_admission_heavy_gpu_and_dreams_on_battery(self):
        """Carichi pesanti e cicli di sogno sono sospesi/deviati su batteria."""
        p_batt = {"ac_line": False, "battery_pct": 75.0, "is_battery": True}

        # Heavy GPU su batteria con nodi AC presenti -> divert
        res_gpu_ac = evaluate_task_admission(p_batt, task_type=TASK_HEAVY_GPU, any_ac_in_mesh=True)
        self.assertFalse(res_gpu_ac["admitted"])
        self.assertEqual(res_gpu_ac["action"], "divert")

        # Heavy GPU su batteria in blackout (nessun AC) -> defer
        res_gpu_no_ac = evaluate_task_admission(p_batt, task_type=TASK_HEAVY_GPU, any_ac_in_mesh=False)
        self.assertFalse(res_gpu_no_ac["admitted"])
        self.assertEqual(res_gpu_no_ac["action"], "defer")

        # Dream consolidation -> sempre defer a batteria
        res_dream = evaluate_task_admission(p_batt, task_type=TASK_DREAM_CONSOLIDATION)
        self.assertFalse(res_dream["admitted"])
        self.assertEqual(res_dream["action"], "defer")

    def test_task_admission_eco_mode_diverts_if_ac_present(self):
        """In modalità Eco, l'inferenza ordinaria è deviata se ci sono nodi AC; altrimenti ammessa."""
        p_eco = {"ac_line": False, "battery_pct": 30.0, "is_battery": True}

        res_mixed = evaluate_task_admission(p_eco, task_type=TASK_STANDARD_INFERENCE, any_ac_in_mesh=True)
        self.assertFalse(res_mixed["admitted"])
        self.assertEqual(res_mixed["action"], "divert")

        res_blackout = evaluate_task_admission(p_eco, task_type=TASK_STANDARD_INFERENCE, any_ac_in_mesh=False)
        self.assertTrue(res_blackout["admitted"])
        self.assertEqual(res_blackout["action"], "allow")

    def test_should_defer_helpers(self):
        """Verifica gli helper dedicati a sogni e ComfyUI."""
        p_batt = {"ac_line": False, "battery_pct": 65.0, "is_battery": True}
        defer_dream, reason_dream = should_defer_dream_cycle(p_batt)
        self.assertTrue(defer_dream)
        self.assertIn("sospesa", reason_dream)

        defer_img, reason_img = should_defer_image_generation(p_batt)
        self.assertTrue(defer_img)

        p_ac = {"ac_line": True, "is_battery": False}
        defer_dream_ac, _ = should_defer_dream_cycle(p_ac)
        self.assertFalse(defer_dream_ac)

    def test_check_dream_power_guard(self):
        """Verifica la guardia nel modulo dream_schedule."""
        ok_ac, _ = check_dream_power_guard({"ac_line": True})
        self.assertTrue(ok_ac)

        ok_batt, reason = check_dream_power_guard({"ac_line": False, "battery_pct": 60.0})
        self.assertFalse(ok_batt)
        self.assertIn("sospesa", reason)

    def test_assess_cluster_energy_status(self):
        """Verifica la diagnosi olistica della flotta per Doctor Mesh."""
        # 1. Tutti AC
        telemetries_ac = [
            {"node_id": "node-1", "alias": "MainPC", "hardware": {"power": {"ac_line": True}}},
            {"node_id": "node-2", "alias": "ServerLab", "hardware": {"power": {"ac_line": True}}},
        ]
        eval_ac = assess_cluster_energy_status(telemetries_ac)
        self.assertEqual(eval_ac["regime"], "all_grid_ac")
        self.assertEqual(eval_ac["status"], "ok")
        self.assertTrue(eval_ac["any_ac"])

        # 2. Rete mista
        telemetries_mixed = [
            {"node_id": "node-1", "alias": "MainPC", "hardware": {"power": {"ac_line": True}}},
            {"node_id": "node-2", "alias": "MacBook", "hardware": {"power": {"ac_line": False, "battery_pct": 72.0}}},
        ]
        eval_mixed = assess_cluster_energy_status(telemetries_mixed)
        self.assertEqual(eval_mixed["regime"], "mixed_grid_preference")
        self.assertEqual(eval_mixed["status"], "ok")
        self.assertEqual(eval_mixed["ac_count"], 1)
        self.assertEqual(eval_mixed["battery_count"], 1)

        # 3. Rete mista con nodo critico
        telemetries_crit = [
            {"node_id": "node-1", "alias": "MainPC", "hardware": {"power": {"ac_line": True}}},
            {"node_id": "node-2", "alias": "MacBook", "hardware": {"power": {"ac_line": False, "battery_pct": 14.0}}},
        ]
        eval_crit = assess_cluster_energy_status(telemetries_crit)
        self.assertEqual(eval_crit["status"], "warn")
        self.assertEqual(eval_crit["critical_count"], 1)

        # 4. Blackout completo (tutti a batteria)
        telemetries_blackout = [
            {"node_id": "node-1", "alias": "Laptop1", "hardware": {"power": {"ac_line": False, "battery_pct": 80.0}}},
            {"node_id": "node-2", "alias": "Laptop2", "hardware": {"power": {"ac_line": False, "battery_pct": 45.0}}},
        ]
        eval_blackout = assess_cluster_energy_status(telemetries_blackout)
        self.assertEqual(eval_blackout["regime"], "blackout_cooperative")
        self.assertFalse(eval_blackout["any_ac"])


if __name__ == "__main__":
    unittest.main()
